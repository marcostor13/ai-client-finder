"""
Outbound API routes — /api/outbound/*
All endpoints require JWT auth (reuses existing get_current_user).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from backend.main import get_current_user
from backend.database import get_collection
from backend.outbound import email_sender, jobs, suppression
from backend.outbound.models import ICPConfigCreate, SuppressionEntryCreate
from backend.outbound import llm_router, prospect_router, email_drafter

router = APIRouter(prefix="/api/outbound", tags=["outbound"])


# ── ICP Config ────────────────────────────────────────────────────────────────

@router.post("/icp-config")
async def upsert_icp_config(
    body: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_icp_config")

    # Deactivate previous versions
    await col.update_many({"active": True}, {"$set": {"active": False}})

    # Get next version number
    last = await col.find_one({}, sort=[("version", -1)])
    version = (last["version"] + 1) if last else 1

    doc = {
        "version": version,
        "active": True,
        "config_json": body,
        "updated_by": current_user["email"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return {"status": "ok", "config": doc}


@router.get("/icp-config")
async def get_icp_config(current_user: dict = Depends(get_current_user)):
    col = get_collection("outbound_icp_config")
    doc = await col.find_one({"active": True}, sort=[("version", -1)])
    if not doc:
        return {"status": "ok", "config": None}
    doc["_id"] = str(doc["_id"])
    return {"status": "ok", "config": doc}


@router.get("/icp-config/history")
async def get_icp_config_history(current_user: dict = Depends(get_current_user)):
    col = get_collection("outbound_icp_config")
    docs = await col.find({}).sort("version", -1).limit(10).to_list(10)
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"status": "ok", "configs": docs}


# ── Prospects ────────────────────────────────────────────────────────────────

@router.get("/prospects")
async def list_prospects(
    tier: Optional[str] = Query(None, description="A, B, C or rejected"),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    skip: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_prospects")
    filt: dict = {}
    if tier:
        filt["tier"] = tier
    if status:
        filt["status"] = status
    total = await col.count_documents(filt)
    docs = await col.find(filt).sort("icp_score", -1).skip(skip).limit(limit).to_list(limit)
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"status": "ok", "total": total, "prospects": docs}


@router.get("/prospects/{prospect_id}")
async def get_prospect(
    prospect_id: str,
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_prospects")
    try:
        doc = await col.find_one({"_id": ObjectId(prospect_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prospect ID")
    if not doc:
        raise HTTPException(status_code=404, detail="Prospect not found")
    doc["_id"] = str(doc["_id"])
    return {"status": "ok", "prospect": doc}


@router.delete("/prospects/{prospect_id}")
async def delete_prospect(
    prospect_id: str,
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_prospects")
    try:
        result = await col.delete_one({"_id": ObjectId(prospect_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prospect ID")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return {"status": "ok"}


# ── Approval queue ────────────────────────────────────────────────────────────

@router.get("/approvals")
async def list_approvals(
    status: Optional[str] = Query("pending_approval"),
    limit: int = Query(50, le=200),
    skip: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_email_drafts")
    filt = {"status": status} if status else {}
    total = await col.count_documents(filt)
    docs = await col.find(filt).sort("created_at", 1).skip(skip).limit(limit).to_list(limit)
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"status": "ok", "total": total, "drafts": docs}


async def _send_batch(drafts: list[dict]) -> None:
    """Background task: send each approved draft and mark as sent."""
    col = get_collection("outbound_email_drafts")
    from bson import ObjectId
    for draft in drafts:
        sent = await email_sender.send_draft(draft)
        now = datetime.now(timezone.utc).isoformat()
        new_status = "sent" if sent else "approved"
        sent_at = now if sent else None
        update: dict = {"status": new_status, "updated_at": now}
        if sent_at:
            update["sent_at"] = sent_at
        await col.update_one({"_id": draft["_id"]}, {"$set": update})


@router.post("/approvals/approve-all")
async def approve_all_drafts(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Approves all pending drafts and sends them in the background."""
    col = get_collection("outbound_email_drafts")
    now = datetime.now(timezone.utc).isoformat()
    pending = await col.find({"status": "pending_approval"}).to_list(500)
    if not pending:
        return {"status": "ok", "approved": 0}
    ids = [d["_id"] for d in pending]
    await col.update_many(
        {"_id": {"$in": ids}},
        {"$set": {"status": "approved", "reviewed_by": current_user["email"], "reviewed_at": now, "updated_at": now}},
    )
    background_tasks.add_task(_send_batch, pending)
    return {"status": "ok", "approved": len(pending)}


@router.post("/approvals/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_email_drafts")
    now = datetime.now(timezone.utc).isoformat()
    try:
        result = await col.update_one(
            {"_id": ObjectId(draft_id), "status": "pending_approval"},
            {"$set": {"status": "approved", "reviewed_by": current_user["email"], "reviewed_at": now, "updated_at": now}},
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid draft ID")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Draft not found or already reviewed")

    # Send immediately
    draft = await col.find_one({"_id": ObjectId(draft_id)})
    sent = False
    if draft and draft.get("contact_email"):
        sent = await email_sender.send_draft(draft)
        now2 = datetime.now(timezone.utc).isoformat()
        update: dict = {"updated_at": now2}
        if sent:
            update["status"] = "sent"
            update["sent_at"] = now2
        await col.update_one({"_id": ObjectId(draft_id)}, {"$set": update})

    return {"status": "ok", "sent": sent}


@router.post("/approvals/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    body: Dict[str, Any] = {},
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_email_drafts")
    now = datetime.now(timezone.utc).isoformat()
    reason = (body or {}).get("reason", "")
    try:
        result = await col.update_one(
            {"_id": ObjectId(draft_id), "status": "pending_approval"},
            {"$set": {"status": "rejected", "reviewed_by": current_user["email"], "reviewed_at": now, "rejection_reason": reason, "updated_at": now}},
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid draft ID")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Draft not found or already reviewed")
    return {"status": "ok"}


@router.patch("/approvals/{draft_id}")
async def edit_draft(
    draft_id: str,
    body: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_email_drafts")
    now = datetime.now(timezone.utc).isoformat()
    updates: Dict[str, Any] = {"updated_at": now}
    if "subject" in body:
        updates["subject"] = body["subject"]
    if "body_text" in body:
        updates["body_text"] = body["body_text"]
        updates["body_html"] = email_drafter._to_html(body["body_text"])
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")
    try:
        result = await col.update_one({"_id": ObjectId(draft_id)}, {"$set": updates})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid draft ID")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Draft not found")
    doc = await col.find_one({"_id": ObjectId(draft_id)})
    doc["_id"] = str(doc["_id"])
    return {"status": "ok", "draft": doc}


# ── Manual job triggers ───────────────────────────────────────────────────────

@router.post("/jobs/discover")
async def trigger_discover(current_user: dict = Depends(get_current_user)):
    """Manually trigger the discover_prospects job (for testing)."""
    try:
        result = await jobs.discover_prospects()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/draft")
async def trigger_draft(current_user: dict = Depends(get_current_user)):
    """Manually trigger the draft_emails job."""
    try:
        result = await jobs.draft_emails()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/run-pipeline")
async def run_pipeline(current_user: dict = Depends(get_current_user)):
    """Run discover → draft in sequence. Returns both results."""
    discover_result = {}
    draft_result = {}
    try:
        discover_result = await jobs.discover_prospects()
    except Exception as e:
        discover_result = {"status": "error", "error": str(e)}
    try:
        draft_result = await jobs.draft_emails()
    except Exception as e:
        draft_result = {"status": "error", "error": str(e)}
    return {
        "status": "ok",
        "discover": discover_result,
        "draft": draft_result,
    }


# ── Sent emails & reply tracking ─────────────────────────────────────────────

@router.get("/sent")
async def list_sent_emails(
    status: Optional[str] = Query(None, description="sent, replied, or bounced"),
    limit: int = Query(100, le=500),
    skip: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_email_drafts")
    filt: dict = {"status": {"$in": ["sent", "replied", "bounced"]}}
    if status:
        filt["status"] = status
    total = await col.count_documents(filt)
    docs = await col.find(filt).sort("sent_at", -1).skip(skip).limit(limit).to_list(limit)
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"status": "ok", "total": total, "emails": docs}


@router.post("/sent/{draft_id}/reply")
async def mark_replied(
    draft_id: str,
    body: Dict[str, Any] = {},
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_email_drafts")
    now = datetime.now(timezone.utc).isoformat()
    notes = (body or {}).get("notes", "")
    try:
        result = await col.update_one(
            {"_id": ObjectId(draft_id), "status": {"$in": ["sent", "replied"]}},
            {"$set": {"status": "replied", "reply_received_at": now, "reply_notes": notes, "updated_at": now}},
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid draft ID")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Email not found or not in sent status")
    return {"status": "ok"}


@router.post("/sent/{draft_id}/bounce")
async def mark_bounced(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_email_drafts")
    now = datetime.now(timezone.utc).isoformat()
    try:
        result = await col.update_one(
            {"_id": ObjectId(draft_id), "status": {"$in": ["sent", "replied"]}},
            {"$set": {"status": "bounced", "updated_at": now}},
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid draft ID")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Email not found")
    return {"status": "ok"}


# ── Suppression ───────────────────────────────────────────────────────────────

@router.get("/suppression")
async def list_suppression(
    limit: int = Query(100, le=500),
    skip: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    entries = await suppression.list_suppressed(limit=limit, skip=skip)
    return {"status": "ok", "entries": entries}


@router.post("/suppression")
async def add_suppression(
    body: SuppressionEntryCreate,
    current_user: dict = Depends(get_current_user),
):
    await suppression.add_suppression(body.email, body.reason, source=current_user["email"])
    return {"status": "ok"}


@router.delete("/suppression/{email}")
async def remove_suppression(
    email: str,
    current_user: dict = Depends(get_current_user),
):
    removed = await suppression.remove_suppression(email)
    if not removed:
        raise HTTPException(status_code=404, detail="Email not in suppression list")
    return {"status": "ok"}


# ── Metrics & usage ───────────────────────────────────────────────────────────

@router.get("/metrics")
async def get_metrics(
    days: int = Query(30, le=90),
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("outbound_metrics")
    docs = await col.find({}).sort("date", -1).limit(days).to_list(days)
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"status": "ok", "metrics": docs}


@router.get("/usage")
async def get_usage(current_user: dict = Depends(get_current_user)):
    llm = await llm_router.get_usage_summary()
    sources = await prospect_router.get_quota_summary()
    return {"status": "ok", "llm_usage": llm, "source_usage": sources}
