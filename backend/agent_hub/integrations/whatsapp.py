"""WhatsApp integration via WAHA (WhatsApp HTTP API)."""
import base64
import os
import uuid
from datetime import datetime, timezone

import httpx

from backend.database import get_collection

COL = "agent_whatsapp_sessions"


def _waha_url() -> str:
    return os.getenv("WAHA_URL", "http://localhost:3000")


def _waha_headers() -> dict:
    key = os.getenv("WAHA_API_KEY", "")
    return {"X-Api-Key": key} if key else {}


async def create_session(user_id: str, display_name: str) -> dict:
    session_id = f"{user_id[:8]}-{uuid.uuid4().hex[:8]}"
    base = _waha_url()
    headers = _waha_headers()

    async with httpx.AsyncClient(timeout=15) as client:
        # Create WAHA session
        resp = await client.post(
            f"{base}/api/sessions",
            headers={**headers, "Content-Type": "application/json"},
            json={"name": session_id, "config": {"webhooks": []}},
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"WAHA session create failed: {resp.text}")

        # Start session so WAHA begins QR generation
        await client.post(f"{base}/api/sessions/{session_id}/start", headers=headers)

        # Register webhook (best-effort — session still usable without it)
        webhook_url = f"{os.getenv('APP_BASE_URL', 'http://localhost:8000')}/agent/whatsapp/webhook"
        try:
            await client.post(
                f"{base}/api/sessions/{session_id}/webhooks",
                headers={**headers, "Content-Type": "application/json"},
                json={"url": webhook_url, "events": ["message"]},
            )
        except Exception:
            pass

    col = get_collection(COL)
    await col.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "display_name": display_name,
        "phone_number": None,
        "status": "PENDING_QR",
        "waha_session_created": True,
        "webhook_registered": True,
        "created_at": datetime.now(timezone.utc),
        "connected_at": None,
        "last_message_at": None,
    })

    return {"session_id": session_id, "status": "PENDING_QR"}


async def get_qr(session_id: str) -> dict:
    base = _waha_url()
    headers = _waha_headers()
    async with httpx.AsyncClient(timeout=10) as client:
        # Check status
        status_resp = await client.get(f"{base}/api/sessions/{session_id}", headers=headers)
        waha_status = "UNKNOWN"
        if status_resp.status_code == 200:
            waha_status = status_resp.json().get("status", "UNKNOWN")

        if waha_status == "WORKING":
            # Update MongoDB
            col = get_collection(COL)
            await col.update_one({"session_id": session_id}, {"$set": {"status": "WORKING"}})
            return {"qr_base64": None, "status": "WORKING"}

        # Get QR — try PNG image first, fall back to JSON value
        qr_resp = await client.get(
            f"{base}/api/{session_id}/auth/qr",
            headers={**headers, "Accept": "image/png"},
        )
        qr_b64 = None
        if qr_resp.status_code == 200:
            ct = qr_resp.headers.get("content-type", "")
            if "image" in ct:
                qr_b64 = "data:image/png;base64," + base64.b64encode(qr_resp.content).decode()
            else:
                # JSON response: {"value": "raw_qr_string"}
                data = qr_resp.json()
                qr_b64 = data.get("value") or data.get("qr") or None
        if qr_b64:
            col = get_collection(COL)
            await col.update_one({"session_id": session_id}, {"$set": {"status": "SCAN_QR_CODE"}})
            return {"qr_base64": qr_b64, "status": "SCAN_QR_CODE"}

    return {"qr_base64": None, "status": waha_status}


async def list_sessions(user_id: str) -> dict:
    col = get_collection(COL)
    docs = await col.find({"user_id": user_id}).to_list(None)
    sessions = []
    for d in docs:
        sessions.append({
            "session_id": d["session_id"],
            "display_name": d.get("display_name", ""),
            "phone_number": d.get("phone_number"),
            "status": d.get("status", "UNKNOWN"),
            "connected_at": d.get("connected_at", "").isoformat() if d.get("connected_at") else None,
        })
    return {"sessions": sessions}


async def send_message(session_id: str, chat_id: str, text: str) -> None:
    base = _waha_url()
    headers = {**_waha_headers(), "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"{base}/api/sendText",
            headers=headers,
            json={"session": session_id, "chatId": chat_id, "text": text},
        )


async def delete_session(session_id: str) -> dict:
    base = _waha_url()
    headers = _waha_headers()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.delete(f"{base}/api/sessions/{session_id}", headers=headers)
    except Exception:
        pass
    col = get_collection(COL)
    await col.delete_many({"session_id": session_id})
    return {"deleted": True}


async def handle_webhook(body: dict) -> None:
    """Process incoming WAHA webhook and dispatch to gateway."""
    payload = body.get("payload", {})
    session_id = body.get("session", "")
    from_me = payload.get("fromMe", False)
    is_group = payload.get("isGroup", False)
    text = payload.get("body", "")
    from_chat = payload.get("from", "")

    if from_me or is_group or not text or not session_id:
        return

    # Look up user from session
    col = get_collection(COL)
    doc = await col.find_one({"session_id": session_id})
    if not doc:
        return
    user_id = doc["user_id"]

    # Update last_message_at
    await col.update_one({"session_id": session_id}, {
        "$set": {"last_message_at": datetime.now(timezone.utc)}
    })

    try:
        from backend.agent_hub import gateway, memory

        conv_id = await memory.get_or_create_conversation(user_id, "whatsapp", from_chat)
        history = await memory.get_history(conv_id)
        messages = [{"role": m["role"], "content": m["content"] if isinstance(m["content"], str) else str(m["content"])}
                    for m in history[-8:]]
        messages.append({"role": "user", "content": text})

        intent = await gateway.detect_intent(text)
        result = await gateway.route(intent, messages)

        reply = result.image_url or result.content
        if result.image_url:
            reply = f"[Imagen generada]: {result.image_url}"

        await memory.append_message(conv_id, "user", text)
        await memory.append_message(conv_id, "assistant", reply, intent=intent, model_used=result.model_id)
        await send_message(session_id, from_chat, reply)
    except Exception as exc:
        await send_message(session_id, from_chat, f"Error: {str(exc)[:100]}")
