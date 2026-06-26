"""
Free stock media (imágenes y videos libres) for B-roll, vía Pexels.

Pexels tiene un plan gratuito (PEXELS_API_KEY) con fotos + videos de licencia
libre. El mixer pide media relevante a un momento del transcript (una query
corta de keywords) y devolvemos la ruta local del archivo descargado + su tipo.
Los resultados se de-duplican por job mediante un set `seen` provisto por quien
llama, para no reutilizar el mismo clip dos veces.
"""
import os
import random
from typing import Optional, Tuple

import httpx

from backend.database import settings

PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"

# Generic fallback queries when a moment has no usable keywords.
_FALLBACK_QUERIES = [
    "business meeting", "technology", "city skyline", "nature landscape",
    "people working", "abstract motion", "office team", "sunrise",
]

# Pexels orientation values keyed by our internal orientation label.
_PEXELS_ORIENT = {"vertical": "portrait", "horizontal": "landscape", "all": "square"}


def available() -> bool:
    """True if the Pexels provider is configured."""
    return bool(settings.pexels_api_key)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def _get_json(url: str, *, params: dict = None, headers: dict = None) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[stock] request failed {url}: {e}")
        return None


async def _download(url: str, dest: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as c:
            r = await c.get(url)
            r.raise_for_status()
            with open(dest, "wb") as f:
                f.write(r.content)
        if os.path.getsize(dest) > 0:
            return dest
    except Exception as e:
        print(f"[stock] download failed {url}: {e}")
    return None


# ── Pexels ────────────────────────────────────────────────────────────────────

async def _pexels_photo(query: str, orientation: str, seen: set) -> Optional[str]:
    data = await _get_json(
        PEXELS_PHOTO_URL,
        params={
            "query": query, "per_page": 15,
            "orientation": _PEXELS_ORIENT.get(orientation, "square"),
            "locale": "es-ES",
        },
        headers={"Authorization": settings.pexels_api_key},
    )
    if not data:
        return None
    photos = data.get("photos", [])
    random.shuffle(photos)
    for photo in photos:
        src = (photo.get("src") or {}).get("large2x") or (photo.get("src") or {}).get("large")
        if src and src not in seen:
            seen.add(src)
            return src
    return None


def _pick_pexels_video_file(files: list) -> Optional[str]:
    """Choose a reasonably-sized mp4 (prefer ~720-1080p) to keep downloads light."""
    mp4s = [f for f in files if (f.get("file_type") == "video/mp4") and f.get("link")]
    if not mp4s:
        return None
    # Prefer files with height between 720 and 1280; else the smallest available.
    ideal = [f for f in mp4s if 700 <= (f.get("height") or 0) <= 1300]
    chosen = sorted(ideal or mp4s, key=lambda f: f.get("height") or 0)
    return chosen[len(chosen) // 2].get("link")


async def _pexels_video(query: str, orientation: str, seen: set) -> Optional[str]:
    data = await _get_json(
        PEXELS_VIDEO_URL,
        params={
            "query": query, "per_page": 12,
            "orientation": _PEXELS_ORIENT.get(orientation, "square"),
        },
        headers={"Authorization": settings.pexels_api_key},
    )
    if not data:
        return None
    vids = data.get("videos", [])
    random.shuffle(vids)
    for v in vids:
        link = _pick_pexels_video_file(v.get("video_files", []))
        if link and link not in seen:
            seen.add(link)
            return link
    return None


# ── Public API ────────────────────────────────────────────────────────────────

async def fetch_media(
    query: str,
    want_video: bool,
    orientation: str,
    dest_basepath: str,
    seen: set,
) -> Optional[Tuple[str, str]]:
    """
    Fetch one free stock asset relevant to `query` from Pexels.

    Tries the requested type first (video or photo), falling back to the other
    type so a segment rarely ends up empty.
    Returns (local_path, media_type) where media_type is "video" | "image",
    or None if nothing could be downloaded.
    """
    query = (query or "").strip() or random.choice(_FALLBACK_QUERIES)

    if not settings.pexels_api_key:
        return None

    # Ordered list of (provider_coroutine_factory, media_type) attempts.
    attempts = []
    if want_video:
        attempts.append((lambda: _pexels_video(query, orientation, seen), "video"))
    attempts.append((lambda: _pexels_photo(query, orientation, seen), "image"))
    if not want_video:
        attempts.append((lambda: _pexels_video(query, orientation, seen), "video"))

    for make_coro, media_type in attempts:
        url = await make_coro()
        if not url:
            continue
        ext = ".mp4" if media_type == "video" else ".jpg"
        dest = f"{dest_basepath}{ext}"
        path = await _download(url, dest)
        if path:
            return path, media_type
    return None
