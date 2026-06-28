"""
Multimodal turn runner for the agent.

One entry point — `run_turn` — drives every chat turn so the agent ALWAYS
responds, regardless of the input type:

  • text                → normal LLM reply
  • image  (bytes)      → vision analysis (Gemini multimodal)
  • audio  (transcribed) → reply, optionally spoken back (TTS)
  • any other file       → text extracted (or acknowledged) and answered

It also enables PROACTIVE attachments: the model may emit, anywhere in its reply,
  [[IMAGE: a prompt]]                  → backend generates & attaches an image
  [[FILE: name.ext]]...content...[[/FILE]] → backend attaches a downloadable file
These markers are stripped from the visible text and turned into attachments.

Never raises for model exhaustion — it returns a graceful fallback so the user
always gets an answer.
"""
import base64
import re

from backend.agent_hub import gateway, memory, rag
from backend.agent_hub.gateway import AllModelsExhausted
from backend.agent_hub.models.base import ModelResponse

_IMG_MARKER = re.compile(r"\[\[IMAGE:\s*(.+?)\]\]", re.IGNORECASE | re.DOTALL)
_FILE_MARKER = re.compile(
    r"\[\[FILE(?::|\s+name=)\s*([\w.\- ]+?)\s*\]\](.*?)\[\[/FILE\]\]",
    re.IGNORECASE | re.DOTALL,
)

# Tells the model it may attach media proactively and must always answer.
_SYSTEM_PREAMBLE = {
    "role": "system",
    "content": (
        "Eres un asistente multimodal. SIEMPRE respondes algo útil, en el mismo "
        "idioma del usuario, aunque el mensaje venga de un audio, una imagen o un "
        "archivo. Si analizas un archivo o imagen, resume lo relevante y responde.\n"
        "Puedes adjuntar contenido de forma proactiva cuando aporte valor:\n"
        "• Para incluir una imagen generada, escribe en su propia línea: "
        "[[IMAGE: descripción visual en inglés]].\n"
        "• Para entregar un archivo descargable (texto, código, csv, md), escribe: "
        "[[FILE: nombre.ext]]el contenido completo aquí[[/FILE]].\n"
        "Usa estos marcadores solo cuando realmente ayuden; no los menciones de otra forma."
    ),
}

_CALENDAR_KW = ("calendar", "meeting", "schedule", "evento", "reunión",
                "cita", "agenda", "appointment")


async def _build_messages(uid: str, conv_id: str, message: str) -> list[dict]:
    """Assemble the full prompt: preamble + RAG + coach + calendar + history."""
    history = await memory.get_history(conv_id)
    messages = [
        {"role": m["role"],
         "content": m["content"] if isinstance(m["content"], str) else str(m["content"])}
        for m in history[-10:]
    ]
    messages.append({"role": "user", "content": message})

    rag_context = await rag.search_context(uid, message)
    if rag_context:
        messages = [{"role": "system", "content": rag_context}] + messages

    # Coach persona/plan/goals, if enabled.
    try:
        from backend.agent_hub import coach
        if await coach.is_enabled(uid):
            messages = await coach.build_context(uid, query=message) + messages
    except Exception:
        pass

    # Outlook calendar context, if connected and relevant.
    if any(k in message.lower() for k in _CALENDAR_KW):
        try:
            from backend.agent_hub.integrations.outlook import get_todays_events_summary
            summary = await get_todays_events_summary(uid)
            if summary:
                messages = [{"role": "system", "content": f"User's calendar context:\n{summary}"}] + messages
        except Exception:
            pass

    return [_SYSTEM_PREAMBLE] + messages


async def _safe_route(intent: str, messages: list[dict], **kwargs) -> ModelResponse | None:
    try:
        return await gateway.route(intent, messages, **kwargs)
    except AllModelsExhausted:
        return None


async def run_turn(
    uid: str,
    conv_id: str,
    message: str,
    *,
    image_b64: str | None = None,
    image_mime: str | None = None,
    want_audio: bool = False,
    persist_user: str | None = None,
) -> dict:
    """
    Run one multimodal turn and return a response dict:
      {reply, image_url, audio_b64, file, intent, model_used, response_ms}

    image_b64 present  → vision analysis of the image.
    want_audio         → the text reply is also synthesized to speech (audio_b64).
    persist_user       → text stored as the user turn (defaults to `message`).
    """
    messages = await _build_messages(uid, conv_id, message)

    # Decide intent: an attached image forces vision; otherwise classify text.
    if image_b64:
        intent = "vision"
        result = await _safe_route("vision", messages, image_b64=image_b64, image_mime=image_mime)
    else:
        intent = await gateway.detect_intent(message)
        if intent == "image":
            result = await _safe_route("image", messages)
        else:
            # tts intent still needs a text reply first; treat as text here.
            intent = "text" if intent == "tts" else intent
            want_audio = want_audio or False
            result = await _safe_route("text", messages)

    if result is None:
        # Always respond, even when every model is exhausted.
        result = ModelResponse(
            content=("Recibí tu mensaje, pero ahora mismo no hay modelos disponibles "
                     "para procesarlo. Inténtalo de nuevo en unos minutos."),
            model_id="fallback", intent="text",
        )

    reply = result.content or ""
    image_url = result.image_url
    audio_b64 = result.audio_b64
    file_attachment = None

    # Proactive attachments (only meaningful for text replies).
    if reply and not image_url:
        m = _IMG_MARKER.search(reply)
        if m:
            img = await _safe_route("image", [{"role": "user", "content": m.group(1).strip()}])
            if img and img.image_url:
                image_url = img.image_url
            reply = _IMG_MARKER.sub("", reply).strip()

        fm = _FILE_MARKER.search(reply)
        if fm:
            fname = (fm.group(1) or "archivo.txt").strip()
            fbody = (fm.group(2) or "").strip()
            file_attachment = {
                "filename": fname,
                "mime": "text/plain",
                "content_b64": base64.b64encode(fbody.encode("utf-8")).decode(),
            }
            reply = _FILE_MARKER.sub("", reply).strip()

    # Audio out: synthesize the (cleaned) text reply when requested.
    if want_audio and reply and not audio_b64:
        tts = await _safe_route("tts", [{"role": "user", "content": reply[:1200]}])
        if tts and tts.audio_b64:
            audio_b64 = tts.audio_b64

    # Persist both turns.
    await memory.append_message(conv_id, "user", persist_user if persist_user is not None else message)
    stored = reply or ("[imagen generada]" if image_url else "[media]")
    await memory.append_message(
        conv_id, "assistant", stored,
        intent=intent, model_used=result.model_id, response_ms=result.response_ms,
    )

    return {
        "reply": reply or None,
        "image_url": image_url,
        "audio_b64": audio_b64,
        "file": file_attachment,
        "intent": intent,
        "model_used": result.model_id,
        "response_ms": result.response_ms,
    }
