"""
Free background music from Jamendo (Creative Commons).

Jamendo has an official API with a free client id, so (unlike Pixabay/Pexels,
whose APIs only expose images & videos) we can search and download tracks
programmatically. We pick an instrumental track whose vibe matches the video's
mood, then the pipeline mixes it under the voice with ducking.
"""
import os
from typing import Optional

import httpx

from backend.database import settings

JAMENDO_TRACKS = "https://api.jamendo.com/v3.0/tracks/"

# Mood → Jamendo fuzzytags (vibe of the track).
_MOOD_TAGS = {
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
    """True if a Jamendo client id is configured."""
    return bool(settings.jamendo_client_id)


async def fetch_track(mood: str, dest_path: str) -> Optional[str]:
    """
    Download one instrumental CC track matching `mood` → dest_path (mp3).
    Returns the path, or None if nothing could be fetched.
    """
    cid = settings.jamendo_client_id
    if not cid:
        return None
    tags = _MOOD_TAGS.get((mood or "neutral").lower(), _MOOD_TAGS["neutral"])
    params = {
        "client_id": cid,
        "format": "json",
        "limit": 15,
        "fuzzytags": tags,
        "vocalinstrumental": "instrumental",   # no competing vocals under the voice
        "audioformat": "mp31",
        "include": "musicinfo",
        "order": "popularity_month",
        "boost": "popularity_month",
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
        if not url:
            continue
        try:
            async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
                r = await client.get(url)
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    f.write(r.content)
            if os.path.getsize(dest_path) > 0:
                print(f"[music] Jamendo [{mood}] ← '{t.get('name', '?')}' by {t.get('artist_name', '?')}")
                return dest_path
        except Exception as e:
            print(f"[music] download failed: {e}")
            continue
    return None
