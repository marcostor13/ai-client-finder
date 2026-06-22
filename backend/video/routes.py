"""
Video editor API routes.

POST   /video/upload                      — upload raw video → S3 → start pipeline
GET    /video/jobs                        — list user jobs
GET    /video/jobs/{job_id}               — get job status + presigned URLs
DELETE /video/jobs/{job_id}              — delete job + S3 files

POST   /video/jobs/{job_id}/publish       — publish a processed version
GET    /video/jobs/{job_id}/refresh-urls  — renew presigned URLs (expire after 24h)

GET    /video/social/status               — connected accounts per platform
POST   /video/social/connect              — store access token (Instagram / TikTok)
GET    /video/social/youtube/connect      — redirect to Google OAuth
GET    /video/social/youtube/callback     — OAuth callback
DELETE /video/social/{platform}           — disconnect account
"""
import os
import secrets
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiofiles
from bson import ObjectId
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form,
    HTTPException, Request, UploadFile,
)
from fastapi.responses import RedirectResponse, JSONResponse

from backend.deps import get_current_user
from backend.database import get_collection, settings
from backend.video import storage, processor, social as social_mod

router = APIRouter(prefix="/video", tags=["video"])

ALLOWED_MIME = {"video/mp4", "video/quicktime", "video/x-msvideo",
                "video/webm", "video/x-matroska", "video/avi"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB


# ── helpers ────────────────────────────────────────────────────────────────────

def _oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(400, "Invalid ID")


async def _get_job(job_id: str, user_email: str) -> Dict:
    doc = await get_collection("video_jobs").find_one(
        {"_id": _oid(job_id), "user_email": user_email}
    )
    if not doc:
        raise HTTPException(404, "Job not found")
    doc["_id"] = str(doc["_id"])
    return doc


# ── Upload ─────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    silence_threshold_db: float = Form(-40.0),
    silence_min_duration: float = Form(0.5),
    subtitle_style: str = Form("tiktok"),
    subtitles_enabled: bool = Form(True),
    images_enabled: bool = Form(False),
    platforms: str = Form("tiktok,reels,youtube,shorts,instagram_feed"),
    current_user: dict = Depends(get_current_user),
):
    if not settings.s3_bucket or not settings.aws_access_key_id:
        raise HTTPException(
            400,
            "S3 not configured. Add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, "
            "S3_BUCKET and S3_REGION to your .env file and restart the server."
        )
    if images_enabled and not settings.openai_api_key:
        raise HTTPException(
            400,
            "Imágenes activadas pero OPENAI_API_KEY no está configurada. "
            "Agrégala al .env para usar DALL-E 3."
        )
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    user_email = current_user["email"]
    job_id = str(ObjectId())
    now = datetime.now(timezone.utc).isoformat()

    # Save to temp file
    suffix = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        size = 0
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                os.unlink(tmp_path)
                raise HTTPException(413, "File too large (max 500 MB)")
            tmp.write(chunk)

    try:
        # Upload original to S3
        s3_key = await storage.upload_file(
            tmp_path, user_email, job_id, f"original{suffix}"
        )
    finally:
        os.unlink(tmp_path)

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]

    # Create job document
    job_doc = {
        "_id": ObjectId(job_id),
        "user_email": user_email,
        "original_filename": file.filename,
        "s3_key_original": s3_key,
        "file_size_bytes": size,
        "status": "processing",
        "progress": 0,
        "current_step": "queued",
        "silence_count": 0,
        "trimmed_duration": None,
        "word_count": 0,
        "processed_versions": {},
        "transcript": [],
        "published_to": [],
        "error": None,
        "settings": {
            "silence_threshold_db": silence_threshold_db,
            "silence_min_duration": silence_min_duration,
            "subtitle_style": subtitle_style,
            "subtitles_enabled": subtitles_enabled,
            "images_enabled": images_enabled,
            "platforms": platform_list,
        },
        "created_at": now,
        "updated_at": now,
    }
    await get_collection("video_jobs").insert_one(job_doc)

    # Start pipeline in background
    background_tasks.add_task(processor.run_pipeline, job_id)

    return {
        "status": "success",
        "job_id": job_id,
        "message": "Processing started",
    }


# ── Job status ─────────────────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(current_user: dict = Depends(get_current_user)):
    docs = await (
        get_collection("video_jobs")
        .find(
            {"user_email": current_user["email"]},
            {"transcript": 0},  # exclude large field
        )
        .sort("created_at", -1)
        .limit(50)
        .to_list(50)
    )
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"status": "success", "jobs": docs}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    job = await _get_job(job_id, current_user["email"])
    return {"status": "success", "job": job}


@router.get("/jobs/{job_id}/refresh-urls")
async def refresh_presigned_urls(
    job_id: str, current_user: dict = Depends(get_current_user)
):
    job = await _get_job(job_id, current_user["email"])
    versions = job.get("processed_versions", {})
    updated = {}
    for platform, data in versions.items():
        url = await storage.get_presigned_url(data["s3_key"], expires=86400)
        updated[platform] = {**data, "presigned_url": url}

    await get_collection("video_jobs").update_one(
        {"_id": _oid(job_id)},
        {"$set": {"processed_versions": updated}},
    )
    return {"status": "success", "processed_versions": updated}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, current_user: dict = Depends(get_current_user)):
    job = await _get_job(job_id, current_user["email"])
    await storage.delete_job_files(current_user["email"], job_id)
    await get_collection("video_jobs").delete_one({"_id": _oid(job_id)})
    return {"status": "success"}


# ── Publish ────────────────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/publish")
async def publish_video(
    job_id: str,
    body: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    job = await _get_job(job_id, current_user["email"])
    if job["status"] != "ready":
        raise HTTPException(400, "Video not ready yet")

    platform = body.get("platform")          # youtube | instagram | tiktok
    target_format = body.get("format")       # tiktok | reels | youtube | etc.
    title = body.get("title", job["original_filename"] or "My Video")
    description = body.get("description", "")
    tags = body.get("tags", [])
    privacy = body.get("privacy", "public")

    versions = job.get("processed_versions", {})
    if target_format not in versions:
        raise HTTPException(400, f"Format '{target_format}' not available")

    s3_key = versions[target_format]["s3_key"]
    presigned_url = versions[target_format]["presigned_url"]

    async def _do_publish():
        try:
            if platform == "youtube":
                # Download from S3 to temp for resumable upload
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    await storage.download_file(s3_key, tmp_path)
                    result = await social_mod.upload_to_youtube(
                        tmp_path, current_user["email"],
                        title, description, tags, privacy
                    )
                finally:
                    os.unlink(tmp_path)

            elif platform == "instagram":
                result = await social_mod.upload_to_instagram(
                    presigned_url, current_user["email"],
                    caption=description,
                    media_type="REELS" if "reel" in target_format else "FEED",
                )

            elif platform == "tiktok":
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    await storage.download_file(s3_key, tmp_path)
                    result = await social_mod.upload_to_tiktok(
                        tmp_path, current_user["email"], title, privacy.upper()
                    )
                finally:
                    os.unlink(tmp_path)
            else:
                return

            now = datetime.now(timezone.utc).isoformat()
            await get_collection("video_jobs").update_one(
                {"_id": _oid(job_id)},
                {"$push": {"published_to": {
                    "platform": platform,
                    "format": target_format,
                    "url": result.get("url", ""),
                    "result": result,
                    "published_at": now,
                }}},
            )
        except Exception as exc:
            await get_collection("video_jobs").update_one(
                {"_id": _oid(job_id)},
                {"$push": {"published_to": {
                    "platform": platform,
                    "format": target_format,
                    "error": str(exc),
                    "published_at": datetime.now(timezone.utc).isoformat(),
                }}},
            )

    background_tasks.add_task(_do_publish)
    return {"status": "success", "message": f"Publishing to {platform} started"}


# ── Social account management ──────────────────────────────────────────────────

@router.get("/social/status")
async def social_status(current_user: dict = Depends(get_current_user)):
    platforms = ["youtube", "instagram", "tiktok"]
    status = {}
    for p in platforms:
        doc = await social_mod.get_social_account(current_user["email"], p)
        status[p] = {
            "connected": bool(doc and doc.get("access_token")),
            "username": doc.get("platform_username") if doc else None,
        }
    return {"status": "success", "accounts": status}


@router.post("/social/connect")
async def connect_social(
    body: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    """Store an access token for Instagram or TikTok (user provides it manually)."""
    platform = body.get("platform")
    access_token = body.get("access_token", "").strip()
    if platform not in ("instagram", "tiktok"):
        raise HTTPException(400, "Use YouTube OAuth flow for YouTube")
    if not access_token:
        raise HTTPException(400, "access_token required")

    data: Dict = {"access_token": access_token, "connected_at": datetime.now(timezone.utc).isoformat()}

    if platform == "instagram":
        try:
            ig_user_id = await social_mod.get_instagram_user_id(access_token)
            data["platform_user_id"] = ig_user_id
        except Exception:
            raise HTTPException(400, "Invalid Instagram token or insufficient permissions")

    await social_mod.upsert_social_account(current_user["email"], platform, data)
    return {"status": "success", "platform": platform}


@router.get("/social/youtube/auth-url")
async def youtube_auth_url(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Return the Google OAuth URL as JSON — frontend redirects the browser there."""
    if not settings.youtube_client_id:
        raise HTTPException(400, "YouTube OAuth not configured. Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env")
    state = f"{current_user['email']}:{secrets.token_hex(16)}"
    redirect_uri = f"{settings.app_base_url}/video/social/youtube/callback"
    auth_url = social_mod.get_youtube_auth_url(redirect_uri, state)
    return {"url": auth_url}


@router.get("/social/youtube/connect")
async def youtube_connect(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    if not settings.youtube_client_id:
        raise HTTPException(400, "YouTube OAuth not configured. Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env")
    state = f"{current_user['email']}:{secrets.token_hex(16)}"
    redirect_uri = f"{settings.app_base_url}/video/social/youtube/callback"
    auth_url = social_mod.get_youtube_auth_url(redirect_uri, state)
    return RedirectResponse(auth_url)


@router.get("/social/youtube/callback")
async def youtube_callback(
    code: str, state: str, request: Request
):
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(400, "Invalid OAuth state")
    user_email = parts[0]

    redirect_uri = f"{settings.app_base_url}/video/social/youtube/callback"
    try:
        tokens = await social_mod.exchange_youtube_code(code, redirect_uri)
    except Exception as e:
        raise HTTPException(400, f"OAuth exchange failed: {e}")

    await social_mod.upsert_social_account(user_email, "youtube", {
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token", ""),
        "token_expires_at": datetime.now(timezone.utc).isoformat(),
        "connected_at": datetime.now(timezone.utc).isoformat(),
    })

    # Redirect back to frontend
    frontend_url = settings.app_base_url.replace(":8000", ":5173")
    return RedirectResponse(f"{frontend_url}/video?connected=youtube")


@router.delete("/social/{platform}")
async def disconnect_social(
    platform: str,
    current_user: dict = Depends(get_current_user),
):
    await get_collection("social_accounts").delete_one(
        {"user_email": current_user["email"], "platform": platform}
    )
    return {"status": "success"}
