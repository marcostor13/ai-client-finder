"""
Suppression list — check before sending any email.
Stores opt-outs, bounces, do-not-contact in MongoDB.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.database import get_collection

_BLOCKED_DOMAINS = {
    "gov", "gob", "edu", "google", "meta", "microsoft",
    "apple", "amazon", "facebook", "instagram", "linkedin",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize(email: str) -> str:
    return email.strip().lower()


def _domain_of(email: str) -> str:
    parts = email.rsplit("@", 1)
    return parts[1] if len(parts) == 2 else ""


async def is_suppressed(email: str) -> tuple[bool, str]:
    """
    Returns (suppressed: bool, reason: str).
    Checks: suppression list, blocked domains, sent in last 90 days.
    """
    email = _normalize(email)

    if not _EMAIL_RE.match(email):
        return True, "invalid_email"

    domain = _domain_of(email)
    if any(b in domain for b in _BLOCKED_DOMAINS):
        return True, f"blocked_domain:{domain}"

    col = get_collection("outbound_suppression")
    entry = await col.find_one({"email": email})
    if entry:
        return True, entry.get("reason", "suppressed")

    # Check not contacted in last 90 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    sent_col = get_collection("outbound_email_drafts")
    recent = await sent_col.find_one({
        "contact_email": email,
        "status": "sent",
        "sent_at": {"$gte": cutoff.isoformat()},
    })
    if recent:
        return True, "contacted_recently"

    return False, ""


async def add_suppression(email: str, reason: str, source: str = "manual") -> None:
    email = _normalize(email)
    col = get_collection("outbound_suppression")
    await col.update_one(
        {"email": email},
        {"$set": {
            "email": email,
            "reason": reason,
            "source": source,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


async def remove_suppression(email: str) -> bool:
    email = _normalize(email)
    col = get_collection("outbound_suppression")
    result = await col.delete_one({"email": email})
    return result.deleted_count > 0


async def list_suppressed(limit: int = 100, skip: int = 0) -> list[dict]:
    col = get_collection("outbound_suppression")
    docs = await col.find({}).sort("added_at", -1).skip(skip).limit(limit).to_list(limit)
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs
