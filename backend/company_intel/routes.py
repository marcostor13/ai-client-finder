"""
Company Intel API routes — /api/company-intel/*
Requires JWT auth (reuses existing get_current_user).
"""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from typing import List, Optional

from backend.main import get_current_user
from backend.database import get_collection
from backend.company_intel.models import JobStatus
from backend.company_intel.pipeline import COLLECTION, run_pipeline
from backend.company_intel import outbound_bridge

router = APIRouter(prefix="/api/company-intel", tags=["company-intel"])


class SearchRequest(BaseModel):
    query: str          # RUC (11 dígitos) o nombre de la empresa
    country: str = "PE"


class DraftRequest(BaseModel):
    indices: Optional[List[int]] = None   # personas a redactar; None = todas con email


def _clean(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.post("/search")
async def start_search(
    body: SearchRequest,
    background: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    query = (body.query or "").strip()
    if len(query) < 3:
        raise HTTPException(400, "Ingresa un RUC o nombre de empresa válido.")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "query": query,
        "country": body.country,
        "status": JobStatus.PENDING.value,
        "progress": 0,
        "message": "En cola…",
        "owner_email": current_user["email"],
        "created_at": now,
        "updated_at": now,
    }
    res = await get_collection(COLLECTION).insert_one(doc)
    job_id = str(res.inserted_id)
    background.add_task(run_pipeline, job_id, query)
    return {"id": job_id, "status": doc["status"]}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    try:
        doc = await get_collection(COLLECTION).find_one({"_id": ObjectId(job_id)})
    except Exception:
        raise HTTPException(400, "ID inválido.")
    if not doc:
        raise HTTPException(404, "Job no encontrado.")
    return _clean(doc)


@router.post("/jobs/{job_id}/draft")
async def draft_from_job(
    job_id: str,
    body: DraftRequest,
    current_user: dict = Depends(get_current_user),
):
    """Crea prospects + drafts de outbound para las personas con email del job.
    Los drafts aparecen en la Cola de aprobación de outbound."""
    try:
        job = await get_collection(COLLECTION).find_one({"_id": ObjectId(job_id)})
    except Exception:
        raise HTTPException(400, "ID inválido.")
    if not job:
        raise HTTPException(404, "Job no encontrado.")
    if job.get("status") != JobStatus.DONE.value:
        raise HTTPException(409, "El análisis aún no ha terminado.")
    return await outbound_bridge.draft_for_job(job, body.indices)


@router.get("/jobs")
async def list_jobs(current_user: dict = Depends(get_current_user), limit: int = 20):
    cur = get_collection(COLLECTION).find(
        {"owner_email": current_user["email"]}
    ).sort("created_at", -1).limit(min(limit, 100))
    return [_clean(d) for d in await cur.to_list(length=limit)]
