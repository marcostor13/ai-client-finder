"""Telegram Bot integration — webhook mode via python-telegram-bot."""
import asyncio
import base64
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


def _token_of(doc: dict) -> str:
    return _fernet().decrypt(doc["bot_token_enc"].encode()).decode()


async def send_reply(user_id: str, chat_id: int | str, text: str) -> None:
    col = get_collection(COL)
    doc = await col.find_one({"user_id": user_id})
    if not doc:
        return
    await _send_text(_token_of(doc), chat_id, text)


async def _send_text(token: str, chat_id, text: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
        )
    if resp.status_code >= 400:
        # Surface Telegram errors (bad token / chat not found) instead of failing silently.
        print(f"[telegram] sendMessage {resp.status_code}: {resp.text[:200]}")


async def _get_file_bytes(token: str, file_id: str) -> bytes:
    """Download a Telegram file (voice/photo/document) by its file_id."""
    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
        r = await client.get(f"https://api.telegram.org/bot{token}/getFile",
                             params={"file_id": file_id})
        r.raise_for_status()
        file_path = r.json()["result"]["file_path"]
        fr = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
        fr.raise_for_status()
        return fr.content


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    """`data:audio/wav;base64,xxxx` → (bytes, mime). Tolerates a bare b64 string."""
    mime = "application/octet-stream"
    b64 = data_url
    if data_url.startswith("data:") and "," in data_url:
        header, b64 = data_url.split(",", 1)
        mime = header[5:].split(";")[0] or mime
    return base64.b64decode(b64), mime


async def _send_audio(token: str, chat_id, audio_b64: str) -> None:
    """Send a TTS reply as a Telegram audio message."""
    raw, mime = _decode_data_url(audio_b64)
    ext = "ogg" if "ogg" in mime else "wav" if "wav" in mime else "mp3"
    async with httpx.AsyncClient(timeout=45) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendAudio",
            data={"chat_id": str(chat_id)},
            files={"audio": (f"respuesta.{ext}", raw, mime)},
        )


async def _send_photo(token: str, chat_id, image_url: str) -> None:
    async with httpx.AsyncClient(timeout=45) as client:
        if image_url.startswith("data:"):
            raw, mime = _decode_data_url(image_url)
            await client.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id": str(chat_id)},
                files={"photo": ("imagen.png", raw, mime or "image/png")},
            )
        else:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                json={"chat_id": chat_id, "photo": image_url},
            )


async def _safe_tts(text: str) -> str | None:
    from backend.agent_hub import gateway
    from backend.agent_hub.gateway import AllModelsExhausted
    try:
        r = await gateway.route("tts", [{"role": "user", "content": text[:1200]}])
        return r.audio_b64
    except (AllModelsExhausted, Exception):
        return None


async def handle_webhook(user_id: str, body: dict) -> None:
    """Process a Telegram Update — text, voice/audio (→ spoken reply), or image."""
    message = body.get("message") or body.get("edited_message")
    if not message:
        return
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return

    col = get_collection(COL)
    doc = await col.find_one({"user_id": user_id})
    if not doc:
        return
    try:
        token = _token_of(doc)
    except Exception:
        return

    text = message.get("text", "") or ""
    caption = message.get("caption", "") or ""

    try:
        from backend.agent_hub import coach, gateway, memory, multimodal

        coach_on = await coach.is_enabled(user_id)
        if coach_on:
            # Captura el chat para los mensajes proactivos del cron
            cfg = await coach.get_config(user_id)
            if not (cfg and cfg.get("telegram_chat_id")):
                await coach.set_chat_id(user_id, chat_id)
                from backend.agent_hub import coach_scheduler
                coach_scheduler.apply_user_schedule(user_id, coach.get_schedule(cfg))
                await coach.log_event(
                    user_id, "Chat de Telegram capturado — proactivos activados",
                    "success", f"chat_id={chat_id}")

        # ── Detectar la modalidad de entrada ────────────────────────────────
        voice = message.get("voice") or message.get("audio")
        photo_list = message.get("photo")
        document = message.get("document") or {}
        doc_mime = document.get("mime_type", "")

        audio_bytes = None
        image_b64 = None
        image_mime = None
        if voice:
            audio_bytes = await _get_file_bytes(token, voice["file_id"])
        elif doc_mime.startswith("audio/"):
            audio_bytes = await _get_file_bytes(token, document["file_id"])
        elif photo_list:
            img = await _get_file_bytes(token, photo_list[-1]["file_id"])
            image_b64, image_mime = base64.b64encode(img).decode(), "image/jpeg"
        elif doc_mime.startswith("image/"):
            img = await _get_file_bytes(token, document["file_id"])
            image_b64, image_mime = base64.b64encode(img).decode(), doc_mime

        # ── Comandos de texto del coach (no para audio/imagen) ──────────────
        if coach_on and text and not (audio_bytes or image_b64):
            if await _handle_coach_message(user_id, chat_id, text, coach):
                return

        # ── Resolver el texto del usuario (transcribir audio si aplica) ─────
        want_audio = False
        if audio_bytes:
            want_audio = True
            try:
                stt = await gateway.route(
                    "audio_stt", [{"role": "user", "content": "[audio]"}],
                    audio_bytes=audio_bytes, filename="voice.ogg",
                )
                user_text = (stt.content or "").strip()
            except Exception:
                user_text = ""
            if not user_text:
                await _send_text(token, chat_id, "No pude entender el audio 🎤. ¿Puedes repetirlo?")
                return
        elif image_b64:
            user_text = caption or "Analiza esta imagen y descríbela en detalle. Si tiene texto, transcríbelo."
        else:
            user_text = text

        if not user_text and not image_b64:
            return  # nada accionable (p.ej. sticker)

        conv_id = await memory.get_or_create_conversation(user_id, "telegram", str(chat_id))

        # ── Modo coach: loop agéntico (texto/audio; las imágenes van a visión) ──
        if coach_on and not image_b64:
            from backend.agent_hub import coach_agent
            history = await memory.get_history(conv_id)
            hist_msgs = [{"role": m["role"],
                          "content": m["content"] if isinstance(m["content"], str) else str(m["content"])}
                         for m in history[-8:]]
            reply = await coach_agent.run_coach_turn(user_id, user_text, hist_msgs)
            await memory.append_message(conv_id, "user", (f"🎤 {user_text}" if audio_bytes else user_text))
            await memory.append_message(conv_id, "assistant", reply, model_used="coach")
            await _send_text(token, chat_id, reply)
            if want_audio and reply:
                tts = await _safe_tts(reply)
                if tts:
                    await _send_audio(token, chat_id, tts)
            return

        # ── Turno multimodal (siempre responde; audio→audio, visión, imágenes) ──
        persist = (f"🎤 {user_text}" if audio_bytes
                   else (f"🖼️ imagen{': ' + caption if caption else ''}" if image_b64 else user_text))
        result = await multimodal.run_turn(
            user_id, conv_id, user_text,
            image_b64=image_b64, image_mime=image_mime,
            want_audio=want_audio, persist_user=persist,
        )
        reply = result.get("reply") or ""
        if reply:
            await _send_text(token, chat_id, reply)
        if result.get("image_url"):
            await _send_photo(token, chat_id, result["image_url"])
        if result.get("audio_b64"):
            await _send_audio(token, chat_id, result["audio_b64"])
        if not (reply or result.get("image_url") or result.get("audio_b64")):
            await _send_text(token, chat_id, "Listo ✅")
    except Exception as exc:
        await _send_text(token, chat_id, f"Lo siento, hubo un error: {str(exc)[:100]}")


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
