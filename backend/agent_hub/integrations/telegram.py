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
        from backend.agent_hub import gateway, memory

        channel_id = str(chat_id)
        conv_id = await memory.get_or_create_conversation(user_id, "telegram", channel_id)
        history = await memory.get_history(conv_id)
        messages = [{"role": m["role"], "content": m["content"] if isinstance(m["content"], str) else str(m["content"])}
                    for m in history[-8:]]
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
        await send_reply(user_id, chat_id, f"Sorry, I encountered an error: {str(exc)[:100]}")
