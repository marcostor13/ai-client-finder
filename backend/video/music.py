"""
Free background music — keyless by default.

Providers, tried in order:
  1. ccMixter  — open API, NO key/signup needed (dig.ccmixter.org). Creative
     Commons remixable music. This is the default so auto-music works out of
     the box with zero configuration.
  2. Jamendo   — only if JAMENDO_CLIENT_ID is set (larger/cleaner catalogue).

(Pixabay/Pexels APIs only expose images & videos, so they can't supply music.)

A track is picked to match the video's mood; the pipeline then mixes it under
the voice with ducking.
"""
import os
from typing import Optional

import httpx

from backend.database import settings

CCMIXTER_API = "http://dig.ccmixter.org/api/query"
JAMENDO_TRACKS = "https://api.jamendo.com/v3.0/tracks/"

# Mood → search tags per provider.
_MOOD_CCMIXTER = {
    "energetic": "instrumental,energetic,electronic",
    "success":   "instrumental,uplifting,inspirational",
    "calm":      "instrumental,ambient,mellow",
    "serious":   "instrumental,cinematic,emotional",
    "dramatic":  "instrumental,dark,cinematic",
    "tech":      "instrumental,electronic,glitch",
    "nature":    "instrumental,acoustic,mellow",
    "urban":     "instrumental,trip_hop,beats",
    "neutral":   "instrumental,background,chill",
}
_MOOD_JAMENDO = {
    "energetic": "energetic,upbeat,powerful",
    "success":   "uplifting,inspiring,corporate",
    "calm":      "calm,relaxing,ambient",
    "serious":   "dramatic,cinematic,emotional",
    "dramatic":  "dark,epic,tension",
    "tech":      "electronic,technology,futuristic",
    "nature":    "acoustic,peaceful,calm",
    "urban":     "hiphop,groove,electronic",
    "neutral":   "background,corporate,motivational",
}


def available() -> bool:
    """Auto-music is always available — ccMixter needs no key."""
    return True


async def _download(url: str, dest_path: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(r.content)
        if os.path.getsize(dest_path) > 0:
            return dest_path
    except Exception as e:
        print(f"[music] download failed: {e}")
    return None


async def _fetch_ccmixter(mood: str, dest_path: str) -> Optional[str]:
    tags = _MOOD_CCMIXTER.get((mood or "neutral").lower(), _MOOD_CCMIXTER["neutral"])
    params = {"f": "json", "tags": tags, "limit": 20, "sort": "rank"}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(CCMIXTER_API, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"[music] ccMixter search failed: {e}")
        return None

    uploads = data if isinstance(data, list) else (data.get("results") or [])
    for up in uploads:
        for f in (up.get("files") or []):
            fmt = str(f.get("file_format") or "").lower()
            name = str(f.get("file_name") or "").lower()
            url = f.get("download_url") or f.get("file_url") or ""
            is_mp3 = name.endswith(".mp3") or url.lower().endswith(".mp3") or "mp3" in fmt
            if url and is_mp3:
                got = await _download(url, dest_path)
                if got:
                    print(f"[music] ccMixter [{mood}] ← '{up.get('upload_name', '?')}' "
                          f"by {up.get('user_name') or up.get('artist_page_name', '?')}")
                    return got
    return None


async def _fetch_jamendo(mood: str, dest_path: str) -> Optional[str]:
    cid = settings.jamendo_client_id
    if not cid:
        return None
    tags = _MOOD_JAMENDO.get((mood or "neutral").lower(), _MOOD_JAMENDO["neutral"])
    params = {
        "client_id": cid, "format": "json", "limit": 15, "fuzzytags": tags,
        "vocalinstrumental": "instrumental", "audioformat": "mp31",
        "order": "popularity_month",
    }
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(JAMENDO_TRACKS, params=params)
            resp.raise_for_status()
            tracks = resp.json().get("results", [])
    except Exception as e:
        print(f"[music] Jamendo search failed: {e}")
        return None
    for t in tracks:
        url = t.get("audiodownload") or t.get("audio")
        if url and await _download(url, dest_path):
            print(f"[music] Jamendo [{mood}] ← '{t.get('name', '?')}'")
            return dest_path
    return None


async def fetch_track(mood: str, dest_path: str) -> Optional[str]:
    """
    Download one CC track matching `mood` → dest_path. Tries Jamendo first when a
    client id is configured (cleaner catalogue), then falls back to the keyless
    ccMixter. Returns the path, or None if nothing could be fetched.
    """
    if settings.jamendo_client_id:
        got = await _fetch_jamendo(mood, dest_path)
        if got:
            return got
    return await _fetch_ccmixter(mood, dest_path)
