"""
Social media upload helpers.

YouTube  — google-api-python-client + OAuth2 (full implementation)
Instagram — Meta Graph API (requires access token stored per user)
TikTok   — Content Posting API (requires approved developer account)
"""
import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Dict, Optional

import httpx
from backend.database import get_collection, settings


# ── Token storage ──────────────────────────────────────────────────────────────

async def get_social_account(user_email: str, platform: str) -> Optional[Dict]:
    doc = await get_collection("social_accounts").find_one(
        {"user_email": user_email, "platform": platform}
    )
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def upsert_social_account(user_email: str, platform: str, data: Dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await get_collection("social_accounts").update_one(
        {"user_email": user_email, "platform": platform},
        {"$set": {**data, "updated_at": now}},
        upsert=True,
    )


# ── YouTube ────────────────────────────────────────────────────────────────────

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

YOUTUBE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def get_youtube_auth_url(redirect_uri: str, state: str) -> str:
    from urllib.parse import urlencode
    params = {
        "client_id": settings.youtube_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(YOUTUBE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{YOUTUBE_AUTH_URL}?{urlencode(params)}"


async def exchange_youtube_code(code: str, redirect_uri: str) -> Dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(YOUTUBE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.youtube_client_id,
            "client_secret": settings.youtube_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
    resp.raise_for_status()
    return resp.json()


async def refresh_youtube_token(refresh_token: str) -> Dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(YOUTUBE_TOKEN_URL, data={
            "refresh_token": refresh_token,
            "client_id": settings.youtube_client_id,
            "client_secret": settings.youtube_client_secret,
            "grant_type": "refresh_token",
        })
    resp.raise_for_status()
    return resp.json()


def _upload_youtube_sync(
    video_path: str, access_token: str,
    title: str, description: str, tags: list,
    privacy: str = "public",
) -> Dict:
    """Resumable YouTube upload — runs synchronously in thread executor."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials
    except ImportError:
        raise RuntimeError("google-api-python-client not installed")

    creds = Credentials(token=access_token)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:500],
            "categoryId": "22",  # People & Blogs
        },
        "status": {"privacyStatus": privacy},
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(
        part=",".join(body.keys()), body=body, media_body=media
    )
    response = None
    while response is None:
        _, response = request.next_chunk()

    return {"video_id": response["id"],
            "url": f"https://youtu.be/{response['id']}"}


async def upload_to_youtube(
    video_path: str, user_email: str,
    title: str, description: str = "", tags: list = None, privacy: str = "public"
) -> Dict:
    account = await get_social_account(user_email, "youtube")
    if not account or not account.get("access_token"):
        raise ValueError("YouTube account not connected. Please connect in settings.")

    access_token = account["access_token"]
    # Refresh if needed
    if account.get("refresh_token"):
        try:
            tokens = await refresh_youtube_token(account["refresh_token"])
            access_token = tokens["access_token"]
            await upsert_social_account(user_email, "youtube", {
                "access_token": access_token,
                "token_expires_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass  # Use existing token

    result = await asyncio.to_thread(
        _upload_youtube_sync,
        video_path, access_token, title, description, tags or [], privacy
    )
    return result


# ── Instagram ─────────────────────────────────────────────────────────────────

INSTAGRAM_GRAPH_URL = "https://graph.facebook.com/v19.0"


async def upload_to_instagram(
    video_url: str,  # must be a public URL (S3 presigned)
    user_email: str,
    caption: str = "",
    media_type: str = "REELS",  # REELS | STORIES | FEED
) -> Dict:
    account = await get_social_account(user_email, "instagram")
    if not account or not account.get("access_token"):
        raise ValueError("Instagram account not connected.")

    token = account["access_token"]
    ig_user_id = account.get("platform_user_id")
    if not ig_user_id:
        raise ValueError("Instagram user ID not found. Reconnect account.")

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Create media container
        container_resp = await client.post(
            f"{INSTAGRAM_GRAPH_URL}/{ig_user_id}/media",
            params={"access_token": token},
            json={
                "media_type": media_type,
                "video_url": video_url,
                "caption": caption[:2200],
                "share_to_feed": True,
            },
        )
        container_resp.raise_for_status()
        container_id = container_resp.json()["id"]

        # Step 2: Poll until processing complete (max 5 min)
        for _ in range(60):
            await asyncio.sleep(5)
            status_resp = await client.get(
                f"{INSTAGRAM_GRAPH_URL}/{container_id}",
                params={"fields": "status_code", "access_token": token},
            )
            status = status_resp.json().get("status_code", "")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise RuntimeError("Instagram video processing failed.")

        # Step 3: Publish
        pub_resp = await client.post(
            f"{INSTAGRAM_GRAPH_URL}/{ig_user_id}/media_publish",
            params={"access_token": token},
            json={"creation_id": container_id},
        )
        pub_resp.raise_for_status()
        media_id = pub_resp.json()["id"]

    return {"media_id": media_id,
            "url": f"https://www.instagram.com/p/{media_id}/"}


# ── TikTok ────────────────────────────────────────────────────────────────────

TIKTOK_API_URL = "https://open.tiktokapis.com/v2"


async def upload_to_tiktok(
    video_path: str, user_email: str,
    title: str = "", privacy: str = "PUBLIC_TO_EVERYONE"
) -> Dict:
    account = await get_social_account(user_email, "tiktok")
    if not account or not account.get("access_token"):
        raise ValueError("TikTok account not connected.")

    token = account["access_token"]
    file_size = os.path.getsize(video_path)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Init upload
        init_resp = await client.post(
            f"{TIKTOK_API_URL}/post/publish/video/init/",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json; charset=UTF-8"},
            json={
                "post_info": {
                    "title": title[:150] or "My Video",
                    "privacy_level": privacy,
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": file_size,
                    "total_chunk_count": 1,
                },
            },
        )
        init_resp.raise_for_status()
        data = init_resp.json().get("data", {})
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")

        # Upload chunk
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        await client.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
                "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            },
            content=video_bytes,
        )

    return {"publish_id": publish_id,
            "url": "https://www.tiktok.com — check your profile"}


# ── Instagram OAuth helper (get long-lived token) ─────────────────────────────

async def get_instagram_user_id(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{INSTAGRAM_GRAPH_URL}/me",
            params={"fields": "id,name", "access_token": access_token},
        )
    resp.raise_for_status()
    return resp.json()["id"]
