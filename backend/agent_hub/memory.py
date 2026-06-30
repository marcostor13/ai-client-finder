"""Per-user conversation history stored in MongoDB."""
from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId

from backend.database import get_collection

# Messages stored raw in MongoDB (40 = 20 turns of history)
MAX_MESSAGES = 40
# Messages returned to the LLM on each call (12 = 6 turns)
WINDOW_SIZE = 12
COL = "agent_conversations"


def _col():
    return get_collection(COL)


def _compact_summary(messages: list[dict]) -> str:
    """Build a concise summary of old messages to preserve context without full tokens."""
    parts = ["[Resumen de conversación anterior]"]
    for m in messages:
        role = "Usuario" if m.get("role") == "user" else "Asistente"
        text = str(m.get("content", "")).strip()
        snippet = text[:180].replace("\n", " ")
        if len(text) > 180:
            snippet += "…"
        parts.append(f"{role}: {snippet}")
    return "\n".join(parts)


async def get_or_create_conversation(
    user_id: str,
    channel: Literal["web", "telegram", "whatsapp"] = "web",
    channel_id: str | None = None,
) -> str:
    if channel_id is None:
        channel_id = user_id
    col = _col()
    doc = await col.find_one({"user_id": user_id, "channel": channel, "channel_id": channel_id})
    if doc:
        return str(doc["_id"])
    result = await col.insert_one({
        "user_id": user_id,
        "channel": channel,
        "channel_id": channel_id,
        "messages": [],
        "context_summary": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(result.inserted_id)


async def get_history(conversation_id: str) -> list[dict]:
    """Return raw stored messages (includes MongoDB metadata fields)."""
    col = _col()
    doc = await col.find_one({"_id": ObjectId(conversation_id)})
    return doc["messages"] if doc else []


async def get_windowed_messages(conversation_id: str) -> list[dict]:
    """
    Return LLM-ready messages with context continuity:
    - Prepends a compact summary of older turns as a system message (if any).
    - Returns only the last WINDOW_SIZE messages to keep token usage low.
    - Each item contains only {role, content} — no MongoDB metadata.
    """
    col = _col()
    doc = await col.find_one({"_id": ObjectId(conversation_id)})
    if not doc:
        return []

    messages = doc.get("messages", [])
    summary = (doc.get("context_summary") or "").strip()

    window = messages[-WINDOW_SIZE:] if len(messages) > WINDOW_SIZE else messages

    result = [
        {
            "role": m["role"],
            "content": m["content"] if isinstance(m["content"], str) else str(m["content"]),
        }
        for m in window
    ]

    # Older context injected as a system message so it survives model switches
    if summary:
        result = [{"role": "system", "content": summary}] + result

    return result


async def append_message(
    conversation_id: str,
    role: Literal["user", "assistant"],
    content: str | dict,
    intent: str | None = None,
    model_used: str | None = None,
    response_ms: int | None = None,
) -> None:
    col = _col()
    message = {
        "role": role,
        "content": content,
        "intent": intent,
        "model_used": model_used,
        "response_ms": response_ms,
        "created_at": datetime.now(timezone.utc),
    }
    now = datetime.now(timezone.utc)
    doc = await col.find_one({"_id": ObjectId(conversation_id)})
    if not doc:
        return

    messages = doc.get("messages", []) + [message]
    existing_summary = (doc.get("context_summary") or "").strip()
    update: dict = {"updated_at": now}

    # When messages overflow, compress the oldest into the running summary
    if len(messages) > MAX_MESSAGES:
        overflow = messages[: len(messages) - MAX_MESSAGES]
        new_piece = _compact_summary(overflow)
        if existing_summary:
            combined = existing_summary + "\n\n" + new_piece
            # Cap summary at 3000 chars to prevent unbounded growth
            update["context_summary"] = combined[-3000:]
        else:
            update["context_summary"] = new_piece
        messages = messages[-MAX_MESSAGES:]

    update["messages"] = messages
    await col.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": update},
    )


async def clear_conversation(user_id: str) -> None:
    await _col().delete_many({"user_id": user_id, "channel": "web"})


async def get_web_conversation(user_id: str) -> dict | None:
    return await _col().find_one({"user_id": user_id, "channel": "web"})
