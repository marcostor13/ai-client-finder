import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from backend.career_ops.auto_apply import auto_apply
from backend.career_ops.cv_extractor import (
    count_filled, extract_docx_text, extract_pdf_text_via_openai, extract_profile_from_cv_text,
)
from backend.career_ops.evaluator import evaluate_job
from backend.career_ops.models import (
    ApplicationStatus, CareerProfile, EvaluateJobRequest, UpdateApplicationRequest,
)
from backend.career_ops import scan_scheduler
from backend.career_ops.scanner import _build_scan_portals
from backend.database import get_collection
from backend.deps import get_current_user

router = APIRouter(prefix="/career-ops", tags=["career-ops"])


# ── Profile config ──────────────────────────────────────────────────────────────

@router.get("/config")
async def get_career_config(current_user: dict = Depends(get_current_user)):
    doc = await get_collection("career_ops_config").find_one(
        {"user_email": current_user["email"]}
    )
    if not doc:
        return {"status": "success", "config": None}
    doc["_id"] = str(doc["_id"])
    return {"status": "success", "config": doc}


@router.post("/config")
async def save_career_config(
    config: CareerProfile,
    current_user: dict = Depends(get_current_user),
):
    now = datetime.now(timezone.utc).isoformat()
    doc = config.model_dump()
    doc["user_email"] = current_user["email"]
    doc["updated_at"] = now

    await get_collection("career_ops_config").update_one(
        {"user_email": current_user["email"]},
        {"$set": doc},
        upsert=True,
    )
    return {"status": "success"}


# ── Extract profile from CV file ───────────────────────────────────────────────

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/config/extract-from-cv")
async def extract_profile_from_cv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado: {ext}. Use PDF, DOCX, DOC, TXT o MD.",
        )

    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (máx. 10 MB).")

    try:
        if ext == ".pdf":
            profile = await extract_pdf_text_via_openai(content, file.filename or "cv.pdf")
        else:
            if ext in (".docx", ".doc"):
                text = extract_docx_text(content)
            else:
                text = content.decode("utf-8", errors="replace")

            if not text.strip():
                raise HTTPException(status_code=400, detail="No se pudo extraer texto del archivo.")

            profile = await extract_profile_from_cv_text(text)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al analizar el archivo: {e}")

    # Store raw file bytes so auto-apply can attach the resume later
    await get_collection("career_ops_resume").update_one(
        {"user_email": current_user["email"]},
        {"$set": {
            "user_email": current_user["email"],
            "filename": file.filename,
            "content_b64": base64.b64encode(content).decode(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    filled = count_filled(profile)
    return {"status": "success", "profile": profile, "fields_filled": filled}


# ── Evaluate a job ──────────────────────────────────────────────────────────────

@router.post("/evaluate")
async def evaluate_job_posting(
    request: EvaluateJobRequest,
    current_user: dict = Depends(get_current_user),
):
    profile_doc = await get_collection("career_ops_config").find_one(
        {"user_email": current_user["email"]}
    )
    profile = profile_doc or {}

    try:
        result = await evaluate_job(
            job_text=request.job_text,
            profile=profile,
            job_title=request.job_title,
            company=request.company_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation error: {e}")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_email": current_user["email"],
        "job_title": request.job_title,
        "company_name": request.company_name,
        "job_url": request.job_url,
        "job_text_snippet": request.job_text[:500],
        "evaluation": result,
        "status": ApplicationStatus.evaluated,
        "notes": "",
        "evaluated_at": now,
        "created_at": now,
    }
    inserted = await get_collection("career_ops_evaluations").insert_one(doc)
    doc["_id"] = str(inserted.inserted_id)
    return {"status": "success", "evaluation": doc}


# ── List evaluations ────────────────────────────────────────────────────────────

@router.get("/evaluations")
async def list_evaluations(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("career_ops_evaluations")
    q: dict = {"user_email": current_user["email"]}
    if status:
        q["status"] = status

    skip = (page - 1) * limit
    total = await col.count_documents(q)
    docs = await (
        col.find(q)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"status": "success", "evaluations": docs, "total": total, "page": page}


@router.get("/evaluations/{eval_id}")
async def get_evaluation(
    eval_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(eval_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
    doc = await get_collection("career_ops_evaluations").find_one(
        {"_id": oid, "user_email": current_user["email"]}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    doc["_id"] = str(doc["_id"])
    return {"status": "success", "evaluation": doc}


@router.delete("/evaluations/{eval_id}")
async def delete_evaluation(
    eval_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(eval_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
    result = await get_collection("career_ops_evaluations").delete_one(
        {"_id": oid, "user_email": current_user["email"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "success"}


class BulkDeleteRequest(BaseModel):
    ids: List[str]


@router.post("/evaluations/bulk-delete")
async def bulk_delete_evaluations(
    request: BulkDeleteRequest,
    current_user: dict = Depends(get_current_user),
):
    oids = []
    for raw_id in request.ids:
        try:
            oids.append(ObjectId(raw_id))
        except Exception:
            pass
    if not oids:
        raise HTTPException(status_code=400, detail="No valid IDs provided")
    result = await get_collection("career_ops_evaluations").delete_many(
        {"_id": {"$in": oids}, "user_email": current_user["email"]}
    )
    return {"status": "success", "deleted": result.deleted_count}


# ── Update application status ───────────────────────────────────────────────────

@router.patch("/evaluations/{eval_id}/status")
async def update_application_status(
    eval_id: str,
    request: UpdateApplicationRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(eval_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")

    update: dict = {
        "status": request.status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if request.notes:
        update["notes"] = request.notes
    if request.status == ApplicationStatus.applied:
        update["applied_at"] = datetime.now(timezone.utc).isoformat()

    result = await get_collection("career_ops_evaluations").update_one(
        {"_id": oid, "user_email": current_user["email"]},
        {"$set": update},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "success"}


# ── Stats ───────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_career_stats(current_user: dict = Depends(get_current_user)):
    col = get_collection("career_ops_evaluations")
    user_email = current_user["email"]

    total = await col.count_documents({"user_email": user_email})

    by_status: dict = {}
    for s in ApplicationStatus:
        by_status[s.value] = await col.count_documents(
            {"user_email": user_email, "status": s.value}
        )

    agg = await col.aggregate([
        {"$match": {"user_email": user_email}},
        {"$group": {
            "_id": None,
            "avg_score": {"$avg": "$evaluation.overall_score"},
            "high_scores": {
                "$sum": {"$cond": [{"$gte": ["$evaluation.overall_score", 4.0]}, 1, 0]}
            },
        }},
    ]).to_list(1)

    avg_score = round(agg[0]["avg_score"], 2) if agg and agg[0]["avg_score"] else 0.0
    high_scores = agg[0]["high_scores"] if agg else 0

    grades_raw = await col.aggregate([
        {"$match": {"user_email": user_email}},
        {"$group": {"_id": "$evaluation.grade", "count": {"$sum": 1}}},
    ]).to_list(10)
    grades = {g["_id"]: g["count"] for g in grades_raw if g["_id"]}

    return {
        "status": "success",
        "stats": {
            "total": total,
            "by_status": by_status,
            "avg_score": avg_score,
            "high_score_count": high_scores,
            "grades": grades,
        },
    }


# ── Scanner — portals config ────────────────────────────────────────────────────

class PortalItem(BaseModel):
    company: str
    board_type: str  # greenhouse | lever | ashby
    board_id: str
    enabled: bool = True


class PortalsConfig(BaseModel):
    portals: List[PortalItem]


@router.get("/portals")
async def get_portals(current_user: dict = Depends(get_current_user)):
    profile_doc = await get_collection("career_ops_config").find_one(
        {"user_email": current_user["email"]}
    )
    portals = _build_scan_portals(profile_doc or {})
    return {"status": "success", "portals": portals}


@router.post("/portals")
async def save_portals(
    config: PortalsConfig,
    current_user: dict = Depends(get_current_user),
):
    # Portals are now derived from profile (countries + roles) — this endpoint is a no-op
    return {"status": "success"}


# ── Scanner — control ───────────────────────────────────────────────────────────

class ScanStartRequest(BaseModel):
    interval_hours: int = 6


@router.get("/scan/state")
async def get_scan_state(current_user: dict = Depends(get_current_user)):
    state = await scan_scheduler.get_state(current_user["email"])
    return {"status": "success", "state": state}


@router.post("/scan/start")
async def start_scan(
    req: ScanStartRequest,
    current_user: dict = Depends(get_current_user),
):
    await scan_scheduler.start_scan_schedule(current_user["email"], req.interval_hours)
    return {"status": "success"}


@router.post("/scan/stop")
async def stop_scan(current_user: dict = Depends(get_current_user)):
    await scan_scheduler.stop_scan_schedule(current_user["email"])
    return {"status": "success"}


@router.post("/scan/run-now")
async def trigger_scan_now(current_user: dict = Depends(get_current_user)):
    await scan_scheduler.run_now(current_user["email"])
    return {"status": "success", "message": "Scan iniciado en segundo plano"}


@router.post("/scan/reset")
async def reset_scan_state(current_user: dict = Depends(get_current_user)):
    await scan_scheduler.reset_state(current_user["email"])
    return {"status": "success", "message": "Estado reseteado a idle"}


@router.get("/scan/test-scrapers")
async def test_scrapers(current_user: dict = Depends(get_current_user)):
    """Diagnostic: run Peru scrapers with Playwright + httpx and return counts + samples."""
    import httpx as _httpx
    from playwright.async_api import async_playwright
    from backend.career_ops.scanner import (
        _fetch_indeed_page, _fetch_computrabajo, _fetch_bumeran, _fetch_aptitus,
    )

    term = "desarrollador software"

    def _sample(jobs: list) -> list:
        return [
            {"title": j.get("title"), "location": j.get("location"),
             "company": j.get("company_name") or j.get("company_hint")}
            for j in jobs[:5]
        ]

    pw = pw_browser = None
    try:
        pw = await async_playwright().start()
        pw_browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    except Exception as e:
        pass

    results: Dict[str, Any] = {}
    try:
        async with _httpx.AsyncClient(follow_redirects=True, verify=False) as client:
            indeed  = await _fetch_indeed_page(term, client, "pe.indeed.com", pw_browser)
            ct      = await _fetch_computrabajo(term, client, "pe.computrabajo.com", pw_browser)
            bumeran = await _fetch_bumeran(term, client, "bumeran.com.pe", pw_browser)
            aptitus = await _fetch_aptitus("tecnologia-de-informacion-y-sistemas", client)

        results = {
            "playwright_available": pw_browser is not None,
            "indeed":       {"count": len(indeed),  "sample": _sample(indeed)},
            "computrabajo": {"count": len(ct),       "sample": _sample(ct)},
            "bumeran":      {"count": len(bumeran),  "sample": _sample(bumeran)},
            "aptitus":      {"count": len(aptitus),  "sample": _sample(aptitus)},
        }
    finally:
        if pw_browser:
            try: await pw_browser.close()
            except: pass
        if pw:
            try: await pw.stop()
            except: pass

    return {"status": "success", "search_term": term, "results": results}


# ── Auto-apply ──────────────────────────────────────────────────────────────────

@router.post("/evaluations/{eval_id}/auto-apply")
async def auto_apply_evaluation(
    eval_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(eval_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")

    doc = await get_collection("career_ops_evaluations").find_one(
        {"_id": oid, "user_email": current_user["email"]}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        result = await auto_apply(doc, current_user["email"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-apply error: {e}")

    update: dict = {
        "cover_letter": result["cover_letter"],
        "auto_apply_result": {k: v for k, v in result.items() if k != "cover_letter"},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if result.get("applied"):
        update["status"] = ApplicationStatus.applied
        update["applied_at"] = datetime.now(timezone.utc).isoformat()

    await get_collection("career_ops_evaluations").update_one(
        {"_id": oid}, {"$set": update}
    )

    return {"status": "success", "result": result}
