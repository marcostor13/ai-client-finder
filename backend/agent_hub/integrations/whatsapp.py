"""WhatsApp integration via WAHA (WhatsApp HTTP API)."""
import base64
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

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
            col = get_collection(COL)
            await col.update_one({"session_id": session_id}, {"$set": {"status": "WORKING"}})
            return {"qr_base64": None, "status": "WORKING"}

        if waha_status == "FAILED":
            logger.warning("WAHA session %s FAILED — deleting and recreating in WAHA", session_id)
            await client.delete(f"{base}/api/sessions/{session_id}", headers=headers)
            create_resp = await client.post(
                f"{base}/api/sessions",
                headers={**headers, "Content-Type": "application/json"},
                json={"name": session_id, "config": {"webhooks": []}},
            )
            logger.warning("WAHA recreate: status=%s body=%s", create_resp.status_code, create_resp.text[:200])
            await client.post(f"{base}/api/sessions/{session_id}/start", headers=headers)
            return {"qr_base64": None, "status": "STARTING"}

        if waha_status == "STOPPED":
            logger.warning("WAHA session %s STOPPED — restarting", session_id)
            await client.post(f"{base}/api/sessions/{session_id}/start", headers=headers)
            return {"qr_base64": None, "status": "STARTING"}

        # Get QR from WAHA: correct endpoint is /api/{session}/auth/qr
        qr_resp = await client.get(
            f"{base}/api/{session_id}/auth/qr",
            headers={**headers, "Accept": "image/png"},
            timeout=30,
        )
        logger.warning("WAHA QR endpoint status=%s content-type=%s body=%s",
                    qr_resp.status_code,
                    qr_resp.headers.get("content-type", ""),
                    qr_resp.text[:300] if "image" not in qr_resp.headers.get("content-type", "") else f"<image {len(qr_resp.content)} bytes>")
        qr_b64 = None
        if qr_resp.status_code == 200:
            ct = qr_resp.headers.get("content-type", "")
            if "image" in ct:
                qr_b64 = "data:image/png;base64," + base64.b64encode(qr_resp.content).decode()
            else:
                data = qr_resp.json()
                logger.warning("WAHA QR JSON keys: %s", list(data.keys()))
                raw = data.get("value") or data.get("qr") or data.get("data") or None
                if raw and not raw.startswith("data:"):
                    qr_b64 = "data:image/png;base64," + raw
                else:
                    qr_b64 = raw
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


async def _download_media(url: str) -> bytes:
    """Download a WAHA-served media file (voice/image/document)."""
    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as c:
        r = await c.get(url, headers=_waha_headers())
        r.raise_for_status()
        return r.content


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    """`data:audio/wav;base64,xxxx` → (bytes, mime). Tolerates a bare b64 string."""
    mime = "application/octet-stream"
    b64 = data_url
    if data_url.startswith("data:") and "," in data_url:
        header, b64 = data_url.split(",", 1)
        mime = header[5:].split(";")[0] or mime
    return base64.b64decode(b64), mime


async def _send_image(session_id: str, chat_id: str, image_url: str) -> None:
    base = _waha_url()
    headers = {**_waha_headers(), "Content-Type": "application/json"}
    if image_url.startswith("data:"):
        raw, mime = _decode_data_url(image_url)
        file = {"mimetype": mime or "image/png", "filename": "imagen.png",
                "data": base64.b64encode(raw).decode()}
    else:
        file = {"url": image_url}
    async with httpx.AsyncClient(timeout=45) as c:
        await c.post(f"{base}/api/sendImage", headers=headers,
                     json={"session": session_id, "chatId": chat_id, "file": file})


async def _send_voice(session_id: str, chat_id: str, audio_b64: str) -> None:
    """Send a TTS reply as a WhatsApp voice note; fall back to a file."""
    raw, mime = _decode_data_url(audio_b64)
    ext = "ogg" if "ogg" in mime else "wav" if "wav" in mime else "mp3"
    file = {"mimetype": mime, "filename": f"respuesta.{ext}",
            "data": base64.b64encode(raw).decode()}
    base = _waha_url()
    headers = {**_waha_headers(), "Content-Type": "application/json"}
    payload = {"session": session_id, "chatId": chat_id, "file": file}
    async with httpx.AsyncClient(timeout=45) as c:
        try:
            r = await c.post(f"{base}/api/sendVoice", headers=headers, json=payload)
            if r.status_code < 400:
                return
        except Exception:
            pass
        try:
            await c.post(f"{base}/api/sendFile", headers=headers, json=payload)
        except Exception:
            pass


async def _safe_tts(text: str):
    from backend.agent_hub import gateway
    try:
        r = await gateway.route("tts", [{"role": "user", "content": text[:1200]}])
        return r.audio_b64
    except Exception:
        return None


async def handle_webhook(body: dict) -> None:
    """Process a WAHA webhook — text, voice/audio (→ spoken reply), or image."""
    payload = body.get("payload", {})
    session_id = body.get("session", "")
    if payload.get("fromMe") or payload.get("isGroup") or not session_id:
        return
    from_chat = payload.get("from", "")
    if not from_chat:
        return

    col = get_collection(COL)
    doc = await col.find_one({"session_id": session_id})
    if not doc:
        return
    user_id = doc["user_id"]
    await col.update_one({"session_id": session_id},
                         {"$set": {"last_message_at": datetime.now(timezone.utc)}})

    body_text = payload.get("body", "") or ""
    media = payload.get("media") or {}
    media_url = media.get("url") or payload.get("mediaUrl")
    mimetype = (media.get("mimetype") or payload.get("mimetype") or "").lower()
    ptype = (payload.get("type") or "").lower()

    # ── Detect media modality ────────────────────────────────────────────────
    audio_bytes = None
    image_b64 = None
    image_mime = None
    if media_url and (mimetype.startswith("audio") or ptype in ("audio", "ptt", "voice")):
        try:
            audio_bytes = await _download_media(media_url)
        except Exception:
            audio_bytes = None
    elif media_url and (mimetype.startswith("image") or ptype == "image"):
        try:
            img = await _download_media(media_url)
            image_b64 = base64.b64encode(img).decode()
            image_mime = (mimetype.split(";")[0] or "image/jpeg")
        except Exception:
            image_b64 = None

    if not body_text and not audio_bytes and not image_b64:
        return  # nothing actionable (sticker, reaction, status…)

    try:
        from backend.agent_hub import coach, gateway, memory, multimodal

        coach_on = await coach.is_enabled(user_id)

        # Transcribe audio / resolve the user's text.
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
                await send_message(session_id, from_chat, "No pude entender el audio 🎤. ¿Puedes repetirlo?")
                return
        elif image_b64:
            user_text = body_text or "Analiza esta imagen y descríbela en detalle. Si tiene texto, transcríbelo."
        else:
            user_text = body_text

        conv_id = await memory.get_or_create_conversation(user_id, "whatsapp", from_chat)

        # Coach agentic loop (text/audio; images go to vision below).
        if coach_on and not image_b64:
            from backend.agent_hub import coach_agent
            history = await memory.get_history(conv_id)
            hist_msgs = [{"role": m["role"],
                          "content": m["content"] if isinstance(m["content"], str) else str(m["content"])}
                         for m in history[-8:]]
            reply = await coach_agent.run_coach_turn(user_id, user_text, hist_msgs)
            await memory.append_message(conv_id, "user", (f"🎤 {user_text}" if audio_bytes else user_text))
            await memory.append_message(conv_id, "assistant", reply, model_used="coach")
            await send_message(session_id, from_chat, reply)
            if want_audio and reply:
                tts = await _safe_tts(reply)
                if tts:
                    await _send_voice(session_id, from_chat, tts)
            return

        # Multimodal turn — always responds (audio→audio, vision, images).
        persist = (f"🎤 {user_text}" if audio_bytes
                   else (f"🖼️ imagen{': ' + body_text if body_text else ''}" if image_b64 else user_text))
        result = await multimodal.run_turn(
            user_id, conv_id, user_text,
            image_b64=image_b64, image_mime=image_mime,
            want_audio=want_audio, persist_user=persist,
        )
        reply = result.get("reply") or ""
        if reply:
            await send_message(session_id, from_chat, reply)
        if result.get("image_url"):
            await _send_image(session_id, from_chat, result["image_url"])
        if result.get("audio_b64"):
            await _send_voice(session_id, from_chat, result["audio_b64"])
        if not (reply or result.get("image_url") or result.get("audio_b64")):
            await send_message(session_id, from_chat, "Listo ✅")
    except Exception as exc:
        await send_message(session_id, from_chat, f"Error: {str(exc)[:100]}")
