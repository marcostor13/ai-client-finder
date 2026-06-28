"""Telegram Bot integration — webhook mode via python-telegram-bot."""
import asyncio
import os
from datetime import datetime, timezone

import httpx
from cryptography.fernet import Fernet

from backend.database import get_collection

COL = "agent_telegram_connections"


def _fernet() -> Fernet:
    key = os.getenv("MS_TOKEN_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError("MS_TOKEN_ENCRYPTION_KEY not set (used for all token encryption)")
    return Fernet(key.encode() if isinstance(key, str) else key)


def _webhook_url(user_id: str) -> str:
    base = os.getenv("APP_BASE_URL", "http://localhost:8000")
    return f"{base}/agent/telegram/webhook/{user_id}"


async def connect_bot(user_id: str, token: str) -> dict:
    # Validate token
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
    if resp.status_code != 200 or not resp.json().get("ok"):
        raise ValueError("Invalid bot token")
    bot_info = resp.json()["result"]
    username = bot_info.get("username", "")

    # Register webhook
    webhook = _webhook_url(user_id)
    async with httpx.AsyncClient(timeout=10) as client:
        wh_resp = await client.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": webhook, "allowed_updates": ["message"]},
        )
    wh_data = wh_resp.json()
    registered = wh_data.get("ok", False)

    f = _fernet()
    token_enc = f.encrypt(token.encode()).decode()

    col = get_collection(COL)
    await col.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "bot_token_enc": token_enc,
            "bot_username": f"@{username}",
            "webhook_url": webhook,
            "webhook_registered": registered,
            "connected_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )

    return {"connected": True, "bot_username": f"@{username}", "webhook_url": webhook}


async def disconnect_bot(user_id: str) -> dict:
    col = get_collection(COL)
    doc = await col.find_one({"user_id": user_id})
    if doc and doc.get("bot_token_enc"):
        try:
            f = _fernet()
            token = f.decrypt(doc["bot_token_enc"].encode()).decode()
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
        except Exception:
            pass
    await col.delete_many({"user_id": user_id})
    return {"disconnected": True}


async def get_status(user_id: str) -> dict:
    col = get_collection(COL)
    doc = await col.find_one({"user_id": user_id})
    if not doc:
        return {"connected": False}
    return {
        "connected": True,
        "bot_username": doc.get("bot_username", ""),
        "webhook_registered": doc.get("webhook_registered", False),
    }


async def send_reply(user_id: str, chat_id: int | str, text: str) -> None:
    col = get_collection(COL)
    doc = await col.find_one({"user_id": user_id})
    if not doc:
        return
    f = _fernet()
    token = f.decrypt(doc["bot_token_enc"].encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )


async def handle_webhook(user_id: str, body: dict) -> None:
    """Process a Telegram Update and reply via the gateway."""
    message = body.get("message") or body.get("edited_message")
    if not message:
        return

    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    if not text or not chat_id:
        return

    # Look up this user's connection to get their user_id (path param is already user_id)
    col = get_collection(COL)
    doc = await col.find_one({"user_id": user_id})
    if not doc:
        return

    try:
        from backend.agent_hub import coach, gateway, memory

        coach_on = await coach.is_enabled(user_id)
        if coach_on:
            # Captura el chat para los mensajes proactivos del cron
            cfg = await coach.get_config(user_id)
            if not (cfg and cfg.get("telegram_chat_id")):
                await coach.set_chat_id(user_id, chat_id)
                # Primer mensaje: registra los jobs del cron para este usuario
                from backend.agent_hub import coach_scheduler
                coach_scheduler.apply_user_schedule(user_id, coach.get_schedule(cfg))
            # Comandos y flujos del coach (tareas, guardar conocimiento)
            handled = await _handle_coach_message(user_id, chat_id, text, coach)
            if handled:
                return

        channel_id = str(chat_id)
        conv_id = await memory.get_or_create_conversation(user_id, "telegram", channel_id)
        history = await memory.get_history(conv_id)
        messages = [{"role": m["role"], "content": m["content"] if isinstance(m["content"], str) else str(m["content"])}
                    for m in history[-8:]]

        # Modo coach: inyecta foco (persona + plan + metas) antes del historial
        if coach_on:
            context = await coach.build_context(user_id, query=text)
            messages = context + messages

        messages.append({"role": "user", "content": text})

        intent = await gateway.detect_intent(text)
        result = await gateway.route(intent, messages)

        reply = result.image_url or result.content
        if result.image_url:
            reply = f"[Image generated] {result.image_url}"

        await memory.append_message(conv_id, "user", text)
        await memory.append_message(conv_id, "assistant", reply, intent=intent, model_used=result.model_id)
        await send_reply(user_id, chat_id, reply)
    except Exception as exc:
        await send_reply(user_id, chat_id, f"Lo siento, hubo un error: {str(exc)[:100]}")


# ── Coach: comandos y flujos de tareas / conocimiento ────────────────────────

_SAVE_TRIGGERS = ("guarda esto", "recuérdame", "recuerdame", "anota", "recuerda que")
_CONFIRM_SAVE = ("sí guarda", "si guarda", "sí, guarda", "si, guarda", "guárdalo", "guardalo")


async def _handle_coach_message(user_id: str, chat_id, text: str, coach) -> bool:
    """Maneja comandos y flujos del coach. Devuelve True si ya respondió."""
    t = text.strip()
    low = t.lower()

    # Confirmación de guardar conocimiento propuesto por el agente
    if any(low.startswith(c) or low == c.replace("sí ", "").replace("si ", "") for c in _CONFIRM_SAVE):
        pending = await coach.pop_pending_knowledge(user_id)
        if pending:
            await coach.save_knowledge(user_id, pending, source="coach")
            await send_reply(user_id, chat_id, "✅ Guardado en mi memoria. Lo usaré para ayudarte mejor.")
            return True

    # Guardar conocimiento que Marcos dicta explícitamente
    if any(low.startswith(s) for s in _SAVE_TRIGGERS):
        content = t
        for s in _SAVE_TRIGGERS:
            if low.startswith(s):
                content = t[len(s):].strip(" :,.-")
                break
        if content:
            await coach.save_knowledge(user_id, content, source="user")
            await send_reply(user_id, chat_id, f"✅ Anotado: {content[:120]}")
            return True

    # /tareas o /foco — lista metas vigentes
    if low in ("/tareas", "/foco", "/metas", "tareas"):
        goals = await coach.list_goals(user_id)
        active = [g for g in goals if g["status"] in ("pending", "in_progress")]
        if not active:
            await send_reply(user_id, chat_id, "No tienes metas pendientes registradas. Usa /nueva <texto> para agregar una.")
            return True
        lines = ["📋 Tus metas vigentes:\n"]
        label = {"today": "🔴 HOY", "short": "🟡 Corto", "mid": "🟢 Mediano", "long": "🔵 Largo"}
        for g in active:
            lines.append(f"[{g['_id'][-6:]}] {label.get(g['horizon'],'')} — {g['title']}")
        lines.append("\nMarca hecha con: /hecho <código>")
        await send_reply(user_id, chat_id, "\n".join(lines))
        return True

    # /hecho <id> — marca una meta como completada
    if low.startswith("/hecho") or low.startswith("/done"):
        code = t.split(maxsplit=1)
        if len(code) < 2:
            await send_reply(user_id, chat_id, "Uso: /hecho <código de la tarea> (ver /tareas)")
            return True
        target = code[1].strip()
        goals = await coach.list_goals(user_id)
        match = next((g for g in goals if g["_id"][-6:] == target or g["_id"] == target), None)
        if not match:
            await send_reply(user_id, chat_id, f"No encontré la tarea «{target}». Revisa /tareas.")
            return True
        await coach.set_goal_status(user_id, match["_id"], "done")
        await send_reply(user_id, chat_id, f"✅ ¡Hecho! «{match['title']}». No rompas la cadena. 🔥")
        return True

    # /nueva <texto> — agrega una meta de hoy
    if low.startswith("/nueva") or low.startswith("/tarea "):
        parts = t.split(maxsplit=1)
        if len(parts) < 2:
            await send_reply(user_id, chat_id, "Uso: /nueva <descripción de la tarea>")
            return True
        gid = await coach.add_goal(user_id, parts[1].strip(), horizon="today", source="user")
        await send_reply(user_id, chat_id, f"➕ Agregada [{gid[-6:]}]: {parts[1].strip()}")
        return True

    # /ayuda
    if low in ("/ayuda", "/help", "/start"):
        await send_reply(user_id, chat_id, _COACH_HELP)
        return True

    return False


_COACH_HELP = (
    "🎯 Soy tu coach. Estoy enfocado en tu Plan Integral y Financiero, y te escribo "
    "proactivamente cada día para que avances.\n\n"
    "Comandos:\n"
    "• /tareas — ver tus metas vigentes\n"
    "• /hecho <código> — marcar una tarea como completada\n"
    "• /nueva <texto> — agregar una tarea\n"
    "• «anota ...» o «recuerda que ...» — guardo eso en mi memoria\n\n"
    "O simplemente escríbeme y conversamos sobre tu plan."
)
