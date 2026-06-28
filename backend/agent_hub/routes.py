"""AI Agent Hub — FastAPI routes."""
import os
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from backend.database import get_collection
from backend.deps import get_current_user
from backend.agent_hub import gateway, memory, rag
from backend.agent_hub.gateway import AllModelsExhausted
from backend.agent_hub.models.usage import POOL_ORDER, get_all_status

router = APIRouter(prefix="/agent", tags=["agent-hub"])


# ── Helpers ────────────────────────────────────────────────────────────────

def _uid(user: dict) -> str:
    return str(user["_id"])


# ── Chat ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/chat")
async def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    uid = _uid(user)
    conv_id = req.conversation_id or await memory.get_or_create_conversation(uid)
    if not req.conversation_id:
        pass  # already created above
    else:
        # Verify conversation belongs to user
        col = get_collection("agent_conversations")
        doc = await col.find_one({"_id": ObjectId(conv_id), "user_id": uid})
        if not doc:
            conv_id = await memory.get_or_create_conversation(uid)

    # Build context: system prompt + calendar if connected
    history = await memory.get_history(conv_id)
    messages = [{"role": m["role"], "content": m["content"] if isinstance(m["content"], str) else str(m["content"])}
                for m in history[-10:]]  # last 10 messages for context
    messages.append({"role": "user", "content": req.message})

    # Inject RAG context from user's uploaded files
    rag_context = await rag.search_context(uid, req.message)
    if rag_context:
        messages = [{"role": "system", "content": rag_context}] + messages

    # Coach mode: prepend focused persona + plan + metas so it never drifts
    from backend.agent_hub import coach
    if await coach.is_enabled(uid):
        messages = await coach.build_context(uid, query=req.message) + messages

    # Inject Outlook calendar context if connected
    messages = await _maybe_inject_calendar(uid, req.message, messages)

    intent = await gateway.detect_intent(req.message)

    try:
        result = await gateway.route(intent, messages)
    except AllModelsExhausted as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Persist both turns
    await memory.append_message(conv_id, "user", req.message)
    reply_content = result.image_url or result.audio_b64 or result.content
    if result.image_url:
        reply_content = {"type": "image", "url": result.image_url}
    await memory.append_message(
        conv_id, "assistant", reply_content,
        intent=intent, model_used=result.model_id, response_ms=result.response_ms,
    )

    return {
        "conversation_id": conv_id,
        "reply": result.content if not result.image_url else None,
        "image_url": result.image_url,
        "audio_b64": result.audio_b64,
        "intent": intent,
        "model_used": result.model_id,
        "response_ms": result.response_ms,
    }


async def _maybe_inject_calendar(uid: str, message: str, messages: list[dict]) -> list[dict]:
    """If Outlook is connected and message mentions calendar, prepend today's events as system context."""
    calendar_kw = ("calendar", "meeting", "schedule", "evento", "reunión", "cita", "agenda", "appointment")
    if not any(k in message.lower() for k in calendar_kw):
        return messages
    try:
        from backend.agent_hub.integrations.outlook import get_todays_events_summary
        summary = await get_todays_events_summary(uid)
        if summary:
            system_msg = {"role": "system", "content": f"User's calendar context:\n{summary}"}
            return [system_msg] + messages
    except Exception:
        pass
    return messages


@router.post("/chat/audio")
async def chat_audio(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    uid = _uid(user)
    audio_bytes = await file.read()
    filename = file.filename or "audio.mp3"

    conv_id = await memory.get_or_create_conversation(uid)
    messages = [{"role": "user", "content": f"[Audio file: {filename}]"}]

    try:
        result = await gateway.route("audio_stt", messages, audio_bytes=audio_bytes, filename=filename)
    except AllModelsExhausted as e:
        raise HTTPException(status_code=503, detail=str(e))

    await memory.append_message(conv_id, "user", f"[Audio: {filename}]")
    await memory.append_message(conv_id, "assistant", result.content, intent="audio_stt", model_used=result.model_id)

    return {
        "conversation_id": conv_id,
        "transcription": result.content,
        "model_used": result.model_id,
        "response_ms": result.response_ms,
    }


@router.get("/conversations")
async def get_conversations(user: dict = Depends(get_current_user)):
    uid = _uid(user)
    doc = await memory.get_web_conversation(uid)
    if not doc:
        return {"conversation_id": None, "messages": []}
    messages = []
    for m in doc.get("messages", []):
        messages.append({
            "role": m["role"],
            "content": m["content"],
            "intent": m.get("intent"),
            "model_used": m.get("model_used"),
            "created_at": m.get("created_at", "").isoformat() if hasattr(m.get("created_at", ""), "isoformat") else str(m.get("created_at", "")),
        })
    return {
        "conversation_id": str(doc["_id"]),
        "messages": messages,
        "updated_at": doc.get("updated_at", "").isoformat() if hasattr(doc.get("updated_at", ""), "isoformat") else "",
    }


@router.delete("/conversations")
async def clear_conversations(user: dict = Depends(get_current_user)):
    await memory.clear_conversation(_uid(user))
    return {"deleted": True}


# ── Model Status ────────────────────────────────────────────────────────────

@router.get("/models/status")
async def models_status(user: dict = Depends(get_current_user)):
    all_status = await get_all_status()
    pools: dict[str, list] = {pool: [] for pool in POOL_ORDER}
    for pool, model_ids in POOL_ORDER.items():
        for mid in model_ids:
            entry = all_status.get(mid, {})
            last_err_at = entry.get("last_error_at")
            pools[pool].append({
                "model_id": mid,
                "display_name": mid.split("/")[-1].replace("-", " ").title(),
                "status": entry.get("status", "unknown"),
                "requests_today": entry.get("requests_today", 0),
                "daily_limit": entry.get("daily_limit"),
                "last_error": entry.get("last_error"),
                "last_error_at": last_err_at.isoformat() if last_err_at else None,
            })
    return {"pools": pools, "as_of": datetime.now(timezone.utc).isoformat()}


# ── Outlook Calendar ────────────────────────────────────────────────────────

@router.get("/outlook/auth-url")
async def outlook_auth_url(user: dict = Depends(get_current_user)):
    from backend.agent_hub.integrations.outlook import get_auth_url
    url = get_auth_url(state=_uid(user))
    return {"auth_url": url}


@router.get("/outlook/callback")
async def outlook_callback(code: str, state: str, request: Request):
    from backend.agent_hub.integrations.outlook import exchange_code_for_tokens
    try:
        await exchange_code_for_tokens(user_id=state, code=code)
    except Exception as e:
        frontend = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")[0].strip()
        return RedirectResponse(url=f"{frontend}/agent?outlook=error&msg={str(e)[:80]}")
    frontend = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")[0].strip()
    return RedirectResponse(url=f"{frontend}/agent?outlook=connected")


@router.get("/outlook/status")
async def outlook_status(user: dict = Depends(get_current_user)):
    from backend.agent_hub.integrations.outlook import get_connection_status
    return await get_connection_status(_uid(user))


@router.delete("/outlook/disconnect")
async def outlook_disconnect(user: dict = Depends(get_current_user)):
    col = get_collection("agent_outlook_connections")
    await col.delete_many({"user_id": _uid(user)})
    return {"disconnected": True}


# ── Telegram ────────────────────────────────────────────────────────────────

class TelegramConnectRequest(BaseModel):
    bot_token: str


@router.post("/telegram/connect")
async def telegram_connect(req: TelegramConnectRequest, user: dict = Depends(get_current_user)):
    from backend.agent_hub.integrations.telegram import connect_bot
    result = await connect_bot(_uid(user), req.bot_token)
    return result


@router.get("/telegram/status")
async def telegram_status(user: dict = Depends(get_current_user)):
    from backend.agent_hub.integrations.telegram import get_status
    return await get_status(_uid(user))


@router.delete("/telegram/disconnect")
async def telegram_disconnect(user: dict = Depends(get_current_user)):
    from backend.agent_hub.integrations.telegram import disconnect_bot
    return await disconnect_bot(_uid(user))


@router.post("/telegram/webhook/{user_id}")
async def telegram_webhook(user_id: str, request: Request):
    from backend.agent_hub.integrations.telegram import handle_webhook
    body = await request.json()
    await handle_webhook(user_id, body)
    return {}


# ── WhatsApp (WAHA) ─────────────────────────────────────────────────────────

class WhatsAppSessionRequest(BaseModel):
    display_name: str


@router.get("/whatsapp/sessions")
async def whatsapp_sessions(user: dict = Depends(get_current_user)):
    from backend.agent_hub.integrations.whatsapp import list_sessions
    return await list_sessions(_uid(user))


@router.post("/whatsapp/sessions", status_code=201)
async def whatsapp_create_session(req: WhatsAppSessionRequest, user: dict = Depends(get_current_user)):
    from backend.agent_hub.integrations.whatsapp import create_session
    return await create_session(_uid(user), req.display_name)


@router.get("/whatsapp/sessions/{session_id}/qr")
async def whatsapp_qr(session_id: str, user: dict = Depends(get_current_user)):
    from backend.agent_hub.integrations.whatsapp import get_qr
    col = get_collection("agent_whatsapp_sessions")
    doc = await col.find_one({"session_id": session_id, "user_id": _uid(user)})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return await get_qr(session_id)


@router.delete("/whatsapp/sessions/{session_id}")
async def whatsapp_delete_session(session_id: str, user: dict = Depends(get_current_user)):
    from backend.agent_hub.integrations.whatsapp import delete_session
    col = get_collection("agent_whatsapp_sessions")
    doc = await col.find_one({"session_id": session_id, "user_id": _uid(user)})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return await delete_session(session_id)


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    from backend.agent_hub.integrations.whatsapp import handle_webhook
    waha_key = os.getenv("WAHA_API_KEY", "")
    if waha_key:
        incoming_key = request.headers.get("X-Api-Key", "")
        if incoming_key != waha_key:
            raise HTTPException(status_code=401, detail="Unauthorized")
    body = await request.json()
    await handle_webhook(body)
    return {}


# ── RAG / File Library ──────────────────────────────────────────────────────────

ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "text/x-python",
    "application/javascript",
    "text/javascript",
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/files", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 20 MB")
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "file"
    # Allow anything text-like even if MIME isn't in the list
    is_allowed = (
        content_type in ALLOWED_MIME
        or content_type.startswith("text/")
        or filename.lower().endswith(
            (".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".json",
             ".py", ".js", ".ts", ".jsx", ".tsx", ".yaml", ".yml", ".xml")
        )
    )
    if not is_allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Tipo de archivo no soportado: {content_type}. Sube PDF, DOCX, TXT, MD, CSV, JSON o código fuente.",
        )
    file_doc = await rag.ingest_file(_uid(user), data, filename, content_type)
    return file_doc


@router.get("/files")
async def list_files(user: dict = Depends(get_current_user)):
    files = await rag.list_files(_uid(user))
    return {"files": files}


@router.delete("/files/{file_id}")
async def delete_file(file_id: str, user: dict = Depends(get_current_user)):
    deleted = await rag.delete_file(_uid(user), file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return {"deleted": True}


# ── Coach Mode (plan de vida + cron proactivo) ───────────────────────────────

class CoachGoalRequest(BaseModel):
    title: str
    horizon: str = "today"


class CoachStatusRequest(BaseModel):
    status: str


class CoachTriggerRequest(BaseModel):
    kind: str = "morning"


class CoachScheduleRequest(BaseModel):
    schedule: dict


@router.get("/coach/status")
async def coach_status(user: dict = Depends(get_current_user)):
    from backend.agent_hub import coach
    uid = _uid(user)
    cfg = await coach.get_config(uid)
    goals = await coach.list_goals(uid)
    return {
        "enabled": bool(cfg and cfg.get("enabled")),
        "telegram_connected": bool(cfg and cfg.get("telegram_chat_id")),
        "timezone": (cfg or {}).get("timezone", "America/Lima"),
        "goal_count": len(goals),
        "pending": len([g for g in goals if g["status"] in ("pending", "in_progress")]),
        "done": len([g for g in goals if g["status"] == "done"]),
    }


@router.get("/coach/metrics")
async def coach_metrics(user: dict = Depends(get_current_user)):
    from backend.agent_hub import coach, coach_scheduler
    uid = _uid(user)
    data = await coach.metrics(uid)
    data["next_runs"] = coach_scheduler.next_runs(uid)
    return data


@router.post("/coach/enable")
async def coach_enable(user: dict = Depends(get_current_user)):
    from backend.agent_hub import coach, coach_scheduler
    uid = _uid(user)
    cfg = await coach.enable(uid)
    seeded = await coach.seed_goals_from_plan(uid)
    coach_scheduler.apply_user_schedule(uid, coach.get_schedule(cfg))
    return {"enabled": True, "goals_seeded": seeded}


@router.post("/coach/disable")
async def coach_disable(user: dict = Depends(get_current_user)):
    from backend.agent_hub import coach, coach_scheduler
    uid = _uid(user)
    await coach.disable(uid)
    coach_scheduler._remove_user_jobs(uid)
    return {"enabled": False}


@router.get("/coach/schedule")
async def coach_get_schedule(user: dict = Depends(get_current_user)):
    from backend.agent_hub import coach, coach_scheduler
    uid = _uid(user)
    cfg = await coach.get_config(uid)
    return {"schedule": coach.get_schedule(cfg), "next_runs": coach_scheduler.next_runs(uid)}


@router.patch("/coach/schedule")
async def coach_set_schedule(req: CoachScheduleRequest, user: dict = Depends(get_current_user)):
    from backend.agent_hub import coach, coach_scheduler
    uid = _uid(user)
    saved = await coach.update_schedule(uid, req.schedule)
    coach_scheduler.apply_user_schedule(uid, saved)
    return {"schedule": saved, "next_runs": coach_scheduler.next_runs(uid)}


@router.get("/coach/goals")
async def coach_goals(user: dict = Depends(get_current_user)):
    from backend.agent_hub import coach
    return {"goals": await coach.list_goals(_uid(user))}


@router.post("/coach/goals", status_code=201)
async def coach_add_goal(req: CoachGoalRequest, user: dict = Depends(get_current_user)):
    from backend.agent_hub import coach
    gid = await coach.add_goal(_uid(user), req.title, req.horizon, source="user")
    return {"id": gid}


@router.patch("/coach/goals/{goal_id}")
async def coach_update_goal(goal_id: str, req: CoachStatusRequest, user: dict = Depends(get_current_user)):
    from backend.agent_hub import coach
    ok = await coach.set_goal_status(_uid(user), goal_id, req.status)
    if not ok:
        raise HTTPException(status_code=400, detail="Meta no encontrada o estado inválido")
    return {"updated": True}


@router.delete("/coach/goals/{goal_id}")
async def coach_delete_goal(goal_id: str, user: dict = Depends(get_current_user)):
    from backend.agent_hub import coach
    ok = await coach.delete_goal(_uid(user), goal_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Meta no encontrada")
    return {"deleted": True}


@router.post("/coach/trigger")
async def coach_trigger(req: CoachTriggerRequest, user: dict = Depends(get_current_user)):
    """Dispara un check-in proactivo ahora (para probar). Requiere chat de Telegram."""
    from backend.agent_hub import coach_scheduler
    sent = await coach_scheduler.trigger_now(_uid(user), req.kind)
    if not sent:
        raise HTTPException(
            status_code=400,
            detail="Primero escríbele al bot de Telegram para que capture tu chat, luego reintenta.",
        )
    return {"sent": True, "kind": req.kind}
