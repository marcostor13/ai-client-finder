"""
Scheduler for the Career Ops scanner.
State is persisted to MongoDB so it survives restarts.
"""
import asyncio
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.career_ops.scanner import run_scan
from backend.database import get_collection

_JOB_ID = "career_ops_scan"
scheduler = AsyncIOScheduler(timezone="UTC")
_started = False


def _ensure_started() -> None:
    global _started
    if not _started:
        scheduler.start()
        _started = True


async def _set_state(user_email: str, **fields) -> None:
    await get_collection("career_ops_scan_state").update_one(
        {"user_email": user_email},
        {"$set": {"user_email": user_email, **fields}},
        upsert=True,
    )


async def _scan_job(user_email: str) -> None:
    await _set_state(user_email, status="running", last_run_at=datetime.now(timezone.utc).isoformat())
    try:
        summary = await run_scan(user_email)
        await _set_state(
            user_email,
            status="idle",
            last_summary=summary,
            last_error="",
        )
    except Exception as e:
        print(f"[scan_scheduler] error: {e}")
        await _set_state(user_email, status="error", last_error=str(e))


_STALE_SECONDS = 20 * 60  # 20 min without finishing → assume crashed


async def get_state(user_email: str) -> dict:
    doc = await get_collection("career_ops_scan_state").find_one({"user_email": user_email})
    if not doc:
        return {
            "active":         False,
            "status":         "idle",
            "interval_hours": 6,
            "last_run_at":    None,
            "next_run_at":    None,
            "last_summary":   None,
            "last_error":     "",
        }
    doc.pop("_id", None)
    doc.pop("user_email", None)

    # Auto-recover from stale "running" state (e.g. server restarted mid-scan)
    if doc.get("status") == "running" and doc.get("last_run_at"):
        try:
            last = datetime.fromisoformat(doc["last_run_at"])
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if elapsed > _STALE_SECONDS:
                await _set_state(
                    user_email,
                    status="error",
                    last_error=f"Scan interrumpido — sin respuesta por {int(elapsed // 60)} min (posible reinicio del servidor).",
                )
                doc["status"] = "error"
                doc["last_error"] = f"Scan interrumpido — sin respuesta por {int(elapsed // 60)} min."
        except Exception:
            pass

    # Enrich with live next-run info from scheduler
    job = scheduler.get_job(_JOB_ID)
    if job and job.next_run_time:
        doc["next_run_at"] = job.next_run_time.isoformat()
        doc["active"] = True
    else:
        doc["next_run_at"] = None
        doc["active"] = False

    return doc


async def reset_state(user_email: str) -> None:
    """Force-reset a stuck running/error state to idle."""
    await _set_state(user_email, status="idle", last_error="")


async def start_scan_schedule(user_email: str, interval_hours: int = 6) -> None:
    _ensure_started()

    existing = scheduler.get_job(_JOB_ID)
    if existing:
        existing.remove()

    scheduler.add_job(
        lambda: asyncio.ensure_future(_scan_job(user_email)),
        trigger="interval",
        hours=interval_hours,
        id=_JOB_ID,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    await _set_state(user_email, active=True, interval_hours=interval_hours, status="idle", last_error="")
    print(f"[scan_scheduler] started — every {interval_hours}h for {user_email}")


async def stop_scan_schedule(user_email: str) -> None:
    job = scheduler.get_job(_JOB_ID)
    if job:
        job.remove()
    await _set_state(user_email, active=False, status="idle")
    print(f"[scan_scheduler] stopped for {user_email}")


async def run_now(user_email: str) -> None:
    _ensure_started()
    asyncio.ensure_future(_scan_job(user_email))


def start_scheduler() -> None:
    _ensure_started()


def stop_scheduler() -> None:
    global _started
    if _started and scheduler.running:
        scheduler.shutdown(wait=False)
        _started = False
