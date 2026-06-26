"""
Video processing pipeline — all heavy work runs in asyncio thread executor.

Steps:
  1. Download original from S3 → temp dir
  2. Detect & remove silences (ffmpeg silencedetect + select filter)
  3. Extract audio → Whisper transcription
  4. Generate ASS subtitle file
  5. Burn subtitles into trimmed video
  5b. (optional) Mix ~60% of segments with free stock B-roll (Pexels images + videos)
  6. Reformat for each requested platform
  7. Upload all outputs to S3
  8. Update job status in MongoDB
"""
import asyncio
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.database import get_collection, settings as app_settings
from backend.video import storage, subtitles as subs_mod
from backend.video import images as img_mod
from backend.video import stock as stock_mod

# ── Ensure ffmpeg is findable on Windows WinGet installs ─────────────────────

def _find_ffmpeg_bin() -> str:
    """Return the directory containing ffmpeg.exe, or empty string if in PATH."""
    if shutil.which("ffmpeg"):
        return ""
    # WinGet install location
    pattern = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft", "WinGet", "Packages",
        "Gyan.FFmpeg*", "ffmpeg-*", "bin",
    )
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    # Chocolatey / manual install fallbacks
    for candidate in [r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin"]:
        if os.path.isdir(candidate):
            return candidate
    return ""

_ffbin = _find_ffmpeg_bin()
if _ffbin and _ffbin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ffbin + os.pathsep + os.environ["PATH"]

# ── Platform format specs ─────────────────────────────────────────────────────

PLATFORM_SPECS = {
    "tiktok":          {"w": 1080, "h": 1920, "fps": 30, "max_sec": None},
    "reels":           {"w": 1080, "h": 1920, "fps": 30, "max_sec": 90},
    "stories":         {"w": 1080, "h": 1920, "fps": 30, "max_sec": 60},
    "youtube":         {"w": 1920, "h": 1080, "fps": 30, "max_sec": None},
    "shorts":          {"w": 1080, "h": 1920, "fps": 30, "max_sec": 60},
    "instagram_feed":  {"w": 1080, "h": 1080, "fps": 30, "max_sec": 60},
}

# ── Subprocess helpers ─────────────────────────────────────────────────────────

def _run(cmd: List[str], timeout: int = 600) -> Tuple[int, str, str]:
    """Run an ffmpeg command synchronously. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    return result.returncode, result.stdout, result.stderr


def _check_ffmpeg() -> bool:
    rc, _, _ = _run(["ffmpeg", "-version"])
    return rc == 0


def _get_duration(path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    rc, out, _ = _run(cmd, timeout=30)
    try:
        return float(out.strip())
    except Exception:
        return 0.0


def _get_dimensions(path: str) -> tuple:
    """Return (width, height) of the first video stream."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        path,
    ]
    rc, out, _ = _run(cmd, timeout=15)
    try:
        w, h = out.strip().split(",")
        return int(w), int(h)
    except Exception:
        return 1920, 1080


# ── Step 1: silence detection ─────────────────────────────────────────────────

def _detect_silences_sync(
    path: str, threshold_db: float = -40.0, min_duration: float = 0.5
) -> List[Tuple[float, float]]:
    cmd = [
        "ffmpeg", "-i", path,
        "-af", f"silencedetect=n={threshold_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]
    _, _, stderr = _run(cmd)
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", stderr)]
    ends   = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", stderr)]
    return list(zip(starts, ends))


# ── Step 2: cut silence ───────────────────────────────────────────────────────

def _build_keep_segments(
    silences: List[Tuple[float, float]],
    duration: float,
    padding: float = 0.1,
) -> List[Tuple[float, float]]:
    keep = []
    cur = 0.0
    for s_start, s_end in silences:
        seg_end = max(0.0, s_start - padding)
        if seg_end > cur + 0.05:
            keep.append((cur, seg_end))
        cur = s_end + padding
    if cur < duration - 0.05:
        keep.append((cur, duration))
    return keep


def _remove_silences_sync(
    input_path: str, output_path: str,
    silences: List[Tuple[float, float]], duration: float,
    padding: float = 0.1,
) -> str:
    segs = _build_keep_segments(silences, duration, padding)

    if not segs:
        # Nothing to cut — just copy
        _run(["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path])
        return output_path

    # Build select / aselect filter
    cond = "+".join(f"between(t,{s:.4f},{e:.4f})" for s, e in segs)
    vf = f"select='{cond}',setpts=N/FRAME_RATE/TB"
    af = f"aselect='{cond}',asetpts=N/SR/TB"

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf, "-af", af,
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        output_path,
    ]
    rc, _, stderr = _run(cmd)
    if rc != 0:
        raise RuntimeError(f"ffmpeg silence removal failed: {stderr[-500:]}")
    return output_path


# ── Step 3: extract audio for Whisper ─────────────────────────────────────────

def _extract_audio_sync(video_path: str, audio_path: str) -> str:
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-ar", "16000", "-ac", "1",
        "-c:a", "libmp3lame", "-b:a", "64k",
        audio_path,
    ]
    rc, _, stderr = _run(cmd)
    if rc != 0:
        raise RuntimeError(f"Audio extraction failed: {stderr[-300:]}")
    return audio_path


# ── Step 4+5: burn subtitles ──────────────────────────────────────────────────

def _burn_subtitles_sync(
    video_path: str, ass_path: str, output_path: str
) -> str:
    # Use just the filename (no drive-letter path) + cwd to avoid Windows
    # colon-in-path issues inside ffmpeg's filter string parser.
    ass_dir  = os.path.dirname(ass_path)
    ass_name = os.path.basename(ass_path)   # e.g. "subs.ass" — no colons
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"ass={ass_name}",
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=600, cwd=ass_dir
    )
    if result.returncode != 0:
        raise RuntimeError(f"Subtitle burn failed: {result.stderr[-500:]}")
    return output_path


# ── Step 6: reformat for platform ─────────────────────────────────────────────

def _format_platform_sync(
    input_path: str, output_path: str, spec: Dict
) -> str:
    w, h, fps = spec["w"], spec["h"], spec["fps"]
    max_sec = spec.get("max_sec")

    # Duration cap
    dur_args = ["-t", str(max_sec)] if max_sec else []

    # Determine scaling strategy
    src_w_out, src_h_out = w, h

    if w == h:
        # 1:1 square — centre crop
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}"
        )
    elif w < h:
        # Vertical (9:16) — blur-pad background + centred overlay
        vf = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},boxblur=25:10[bg];"
            f"[0:v]scale={w}:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        # This uses filtergraph — need -filter_complex
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
        ] + dur_args + [
            "-filter_complex", vf,
            "-r", str(fps),
            "-c:v", "libx264", "-crf", "22", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ]
        rc, _, stderr = _run(cmd)
        if rc != 0:
            raise RuntimeError(f"Format {w}x{h} failed: {stderr[-400:]}")
        return output_path
    else:
        # Horizontal (16:9) — scale + letterbox pad
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
        )

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
    ] + dur_args + [
        "-vf", vf,
        "-r", str(fps),
        "-c:v", "libx264", "-crf", "22", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        output_path,
    ]
    rc, _, stderr = _run(cmd)
    if rc != 0:
        raise RuntimeError(f"Format {w}x{h} failed: {stderr[-400:]}")
    return output_path


# ── MongoDB helpers ────────────────────────────────────────────────────────────

async def _set_progress(job_id: str, step: str, pct: int, extra: dict = None):
    update = {
        "current_step": step,
        "progress": pct,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        update.update(extra)
    await get_collection("video_jobs").update_one(
        {"_id": __import__("bson").ObjectId(job_id)},
        {"$set": update},
    )


async def _set_error(job_id: str, msg: str):
    await get_collection("video_jobs").update_one(
        {"_id": __import__("bson").ObjectId(job_id)},
        {"$set": {
            "status": "error",
            "error": msg,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run_pipeline(job_id: str):
    """
    Full async pipeline. Called as a background task after video upload.
    Reads job config from MongoDB, processes video, uploads results to S3.
    """
    from bson import ObjectId

    jobs_col = get_collection("video_jobs")
    job = await jobs_col.find_one({"_id": ObjectId(job_id)})
    if not job:
        return

    user_email = job["user_email"]
    s3_key_original = job["s3_key_original"]
    cfg = job.get("settings", {})

    threshold_db    = float(cfg.get("silence_threshold_db", -40))
    min_silence_dur = float(cfg.get("silence_min_duration", 0.5))
    subtitle_style  = cfg.get("subtitle_style", "tiktok")
    subtitle_on     = cfg.get("subtitles_enabled", True)
    images_on       = cfg.get("images_enabled", False)
    platforms       = cfg.get("platforms", list(PLATFORM_SPECS.keys()))

    tmpdir = tempfile.mkdtemp(prefix=f"vid_{job_id}_")
    try:
        await _set_progress(job_id, "downloading", 2)

        # ── 1. Download original ──────────────────────────────────────
        original = os.path.join(tmpdir, "original.mp4")
        await storage.download_file(s3_key_original, original)

        duration = await asyncio.to_thread(_get_duration, original)
        await _set_progress(job_id, "silence_detection", 10)

        # ── 2. Detect silences ────────────────────────────────────────
        silences = await asyncio.to_thread(
            _detect_silences_sync, original, threshold_db, min_silence_dur
        )
        await _set_progress(job_id, "silence_removal", 20,
                             {"silence_count": len(silences)})

        # ── 3. Cut silence ────────────────────────────────────────────
        trimmed = os.path.join(tmpdir, "trimmed.mp4")
        await asyncio.to_thread(
            _remove_silences_sync, original, trimmed, silences, duration
        )
        trimmed_duration = await asyncio.to_thread(_get_duration, trimmed)
        await _set_progress(job_id, "transcription", 35,
                             {"trimmed_duration": round(trimmed_duration, 1)})

        # ── 4. Transcribe (Whisper) ───────────────────────────────────
        words = []
        ass_path = None
        subtitled = trimmed   # default: no subtitles

        if subtitle_on:
            audio = os.path.join(tmpdir, "audio.mp3")
            await asyncio.to_thread(_extract_audio_sync, trimmed, audio)
            words = await subs_mod.transcribe(audio)
            await _set_progress(job_id, "subtitles", 55,
                                 {"word_count": len(words)})

            # ── 5. Generate & burn ASS ────────────────────────────────
            if words:
                ass_path = os.path.join(tmpdir, "subs.ass")
                await asyncio.to_thread(subs_mod.write_ass, words, ass_path, subtitle_style)

                subtitled = os.path.join(tmpdir, "subtitled.mp4")
                await asyncio.to_thread(
                    _burn_subtitles_sync, trimmed, ass_path, subtitled
                )

        # ── 5b. Mix with free stock B-roll (imágenes + videos) ───────
        base_video = subtitled   # this is the input to platform formatting

        if images_on and stock_mod.available():
            await _set_progress(job_id, "images", 62)
            w, h = await asyncio.to_thread(_get_dimensions, subtitled)
            orientation = "vertical" if h > w else "horizontal" if w > h else "all"

            all_segs, broll_segs = img_mod.plan_segments(
                await asyncio.to_thread(_get_duration, subtitled)
            )
            print(f"[pipeline] broll: {len(broll_segs)}/{len(all_segs)} segments → stock media")

            media = await img_mod.fetch_broll(words, broll_segs, tmpdir, orientation)

            if media:
                mixed = os.path.join(tmpdir, "mixed.mp4")
                await asyncio.to_thread(
                    img_mod.mix_sync,
                    subtitled, mixed, words, w, h,
                    media, all_segs, tmpdir,
                    subtitle_style,
                )
                base_video = mixed
                print(f"[pipeline] broll mixed: {len(media)} segments")
            else:
                print("[pipeline] broll: no stock media fetched, skipping mix")
        elif images_on and not stock_mod.available():
            print("[pipeline] broll: no PEXELS_API_KEY set, skipping")

        await _set_progress(job_id, "formatting", 65)

        # ── 6. Format per platform ────────────────────────────────────
        processed_versions = {}
        total_plat = len(platforms)
        for idx, platform in enumerate(platforms):
            spec = PLATFORM_SPECS.get(platform)
            if not spec:
                continue
            out_path = os.path.join(tmpdir, f"{platform}.mp4")
            await asyncio.to_thread(_format_platform_sync, base_video, out_path, spec)

            s3_key = await storage.upload_file(
                out_path, user_email, job_id, f"{platform}.mp4"
            )
            presigned = await storage.get_presigned_url(s3_key, expires=86400)
            processed_versions[platform] = {
                "s3_key": s3_key,
                "presigned_url": presigned,
                "presigned_expires": datetime.now(timezone.utc).isoformat(),
            }

            pct = 65 + int(30 * (idx + 1) / total_plat)
            await _set_progress(job_id, "formatting", pct)

        # ── 7. Upload transcript to S3 ────────────────────────────────
        if words:
            import json as _json
            transcript_path = os.path.join(tmpdir, "transcript.json")
            with open(transcript_path, "w") as f:
                _json.dump(words, f)
            await storage.upload_file(
                transcript_path, user_email, job_id, "transcript.json",
                content_type="application/json",
            )

        # ── 8. Done ───────────────────────────────────────────────────
        await jobs_col.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {
                "status": "ready",
                "progress": 100,
                "current_step": "done",
                "processed_versions": processed_versions,
                "transcript": words,
                "trimmed_duration": round(trimmed_duration, 1),
                "silence_count": len(silences),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    except Exception as exc:
        await _set_error(job_id, str(exc))
        raise

    finally:
        # Clean temp directory
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
