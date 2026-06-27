"""Per-user conversation history stored in MongoDB."""
from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId

from backend.database import get_collection

MAX_MESSAGES = 20
COL = "agent_conversations"


def _col():
    return get_collection(COL)


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
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(result.inserted_id)


async def get_history(conversation_id: str) -> list[dict]:
    col = _col()
    doc = await col.find_one({"_id": ObjectId(conversation_id)})
    return doc["messages"] if doc else []


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
    # Append and keep only last MAX_MESSAGES
    doc = await col.find_one({"_id": ObjectId(conversation_id)})
    if not doc:
        return
    messages = doc.get("messages", []) + [message]
    if len(messages) > MAX_MESSAGES:
        messages = messages[-MAX_MESSAGES:]
    await col.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"messages": messages, "updated_at": now}},
    )


async def clear_conversation(user_id: str) -> None:
    await _col().delete_many({"user_id": user_id, "channel": "web"})


async def get_web_conversation(user_id: str) -> dict | None:
    return await _col().find_one({"user_id": user_id, "channel": "web"})
