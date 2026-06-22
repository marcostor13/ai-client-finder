"""
Video + AI Images mixer — viral-optimized.

Replaces every other segment (~50%) with a gpt-image-2 image + Ken Burns effect.
Falls back to gpt-image-1 if gpt-image-2 is not yet available on the account.
GPT-4o-mini (with visual-director system prompt) generates rich scene descriptions
from surrounding transcript context so DALL-E images are highly relevant.
Subtitles are burned onto image clips at matching timestamps.

Ken Burns variants (8 effects, shuffled per video):
  0 — zoom-in punch (fast hook)
  1 — zoom-out dramatic reveal
  2 — pan left→right + zoom (tracking shot)
  3 — pan right→left + zoom (reverse tracking)
  4 — diagonal push-in (zoom + drift, most viral)
  5 — vertical scan top→bottom (portrait/vertical)
  6 — vertical reveal bottom→top (upward reveal)
  7 — slow cinematic drift (emotional/calm)
"""

import asyncio
import base64
import os
import random
import re
import shutil
import subprocess
from collections import Counter
from typing import Optional

_STOP = {
    "de", "la", "el", "en", "y", "a", "que", "los", "las", "un", "una",
    "es", "se", "no", "con", "por", "su", "para", "este", "esta", "lo",
    "más", "como", "pero", "sus", "le", "ya", "fue", "al", "del", "muy",
    "tiene", "hay", "si", "cuando", "sobre", "también", "son", "todo",
    "bien", "ser", "puede", "hace", "me", "mi", "tu",
    "the", "and", "is", "in", "it", "of", "to", "that", "with", "this",
    "for", "are", "was", "on", "at", "be", "have", "from", "by", "not",
}

# zoompan expressions — {d} frames, {w}×{h} output size
# Input is pre-scaled to 1.5× so the max zoom of 1.35 always has headroom (1.5/1.35 = 11%)
_EFFECTS = [
    # 0: Zoom-in punch — fast hook, 1.0→1.35 (most thumb-stopping)
    "zoompan=z='min(zoom+0.0023,1.35)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30",
    # 1: Zoom-out reveal — starts 1.35, dramatically pulls back (creates suspense)
    "zoompan=z='if(lte(zoom,1.0),1.35,max(1.001,zoom-0.0023))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30",
    # 2: Pan left→right + slow zoom (cinematic tracking feel)
    "zoompan=z='min(zoom+0.0008,1.25)':x='if(lte(on,1),0,min(x+2.0,iw/5))':y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30",
    # 3: Pan right→left + slow zoom (reverse tracking shot)
    "zoompan=z='min(zoom+0.0008,1.25)':x='if(lte(on,1),iw/5,max(0,x-2.0))':y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30",
    # 4: Diagonal push-in — zoom + drift top-left→bottom-right (highest virality)
    "zoompan=z='min(zoom+0.0018,1.35)':x='if(lte(on,1),0,min(x+1.4,iw/5))':y='if(lte(on,1),0,min(y+1.4,ih/5))':d={d}:s={w}x{h}:fps=30",
    # 5: Vertical scan top→bottom (great for 9:16 vertical content)
    "zoompan=z='1.22':x='iw/2-(iw/zoom/2)':y='if(lte(on,1),0,min(y+2.0,ih/5))':d={d}:s={w}x{h}:fps=30",
    # 6: Vertical reveal bottom→top (upward reveal, aspirational feel)
    "zoompan=z='1.22':x='iw/2-(iw/zoom/2)':y='if(lte(on,1),ih/5,max(0,y-2.0))':d={d}:s={w}x{h}:fps=30",
    # 7: Slow cinematic drift — near-imperceptible zoom, emotional/calm moments
    "zoompan=z='min(zoom+0.0005,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30",
]

# Max unique images per video (cost control)
_MAX_UNIQUE_IMAGES = 8

# gpt-image-2 released 2026-04-21 — falls back to gpt-image-1 if not yet on the account
_IMAGE_MODEL          = "gpt-image-2"
_IMAGE_MODEL_FALLBACK = "gpt-image-1"


# ── Keyword / topic helpers ───────────────────────────────────────────────────

def _keywords(transcript: list, t_start: float, t_end: float) -> str:
    """Extract content keywords from a transcript time window."""
    words = []
    for item in transcript:
        t = item.get("start", 0)
        if t_start <= t < t_end:
            w = re.sub(r"[^\w]", "", item.get("word", "")).strip().lower()
            if w and len(w) > 3 and w not in _STOP:
                words.append(w)
    seen: set = set()
    unique = [w for w in words if not (w in seen or seen.add(w))]  # type: ignore
    return " ".join(unique[:7]) or "professional business"


def _global_topic(transcript: list) -> str:
    """Top content words from the full transcript (video subject)."""
    words = []
    for item in transcript:
        w = re.sub(r"[^\w]", "", item.get("word", "")).strip().lower()
        if w and len(w) > 4 and w not in _STOP:
            words.append(w)
    return " ".join(w for w, _ in Counter(words).most_common(6))


# Viral photography style appended to every DALL-E 3 prompt
_VIRAL_STYLE = (
    "ARRI cinema camera aesthetic, "
    "cinematic teal-and-orange color grading, "
    "dramatic volumetric God rays, "
    "photorealistic 8K resolution, "
    "ultra-sharp foreground with beautiful bokeh background, "
    "rich vibrant saturated colors, extreme cinematic contrast, "
    "award-winning commercial photography, National Geographic quality"
)
_NO_TEXT = (
    "no text, no words, no letters, no logos, no watermarks, "
    "no human faces, no cartoons, no illustrations"
)


def _build_prompt(visual_desc: str) -> str:
    """Build a viral-optimized cinematic B-roll prompt for DALL-E 3."""
    return f"{visual_desc}. {_VIRAL_STYLE}. {_NO_TEXT}."


# ── GPT-4o-mini visual description ───────────────────────────────────────────

async def _gpt_visual_description(
    transcript: list,
    t_start: float,
    t_end: float,
    global_topic: str,
    client,
) -> str:
    """
    Ask GPT-4o-mini to generate a rich visual scene description
    using a ±12 s transcript window + overall video topic.
    Falls back to empty string on error.
    """
    window = 12.0
    context_words = [
        w.get("word", "") for w in transcript
        if t_start - window <= w.get("start", 0) < t_end + window
    ]
    context_text = " ".join(context_words).strip()
    if not context_text or len(context_text) < 10:
        return ""

    topic_line = f'Overall video topic: "{global_topic}".\n' if global_topic else ""
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a world-class visual director specializing in viral TikTok, "
                        "Instagram Reels, and YouTube Shorts B-roll. "
                        "Given a transcript excerpt, you describe the single most visually "
                        "striking cinematic image that would maximize viewer engagement and "
                        "thumb-stopping power. "
                        "Always reply with ONLY a scene description of 12-18 words. "
                        "Always specify: dramatic lighting type (golden hour, neon city lights, "
                        "God rays through fog, studio strobe, blue hour), "
                        "a strong perspective (extreme macro close-up, sweeping aerial, "
                        "low-angle heroic, dutch tilt, wide establishing), "
                        "texture and atmosphere (misty, crystalline water, gritty urban, "
                        "lush tropical, sleek minimalist), "
                        "and an emotional mood (powerful, serene, intense, aspirational, mysterious). "
                        "Never include human faces, text, logos, or watermarks."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{topic_line}"
                        f'Transcript near this moment: "{context_text}"\n\n'
                        "Describe the perfect cinematic B-roll image to accompany this content."
                    ),
                },
            ],
            max_tokens=80,
            temperature=0.88,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[images] GPT describe error: {e}")
        return ""


# ── Segment planning ──────────────────────────────────────────────────────────

def plan_segments(total_duration: float, seg_sec: float = 5.0) -> tuple:
    """
    Split video into N equal segments alternating video / image (odd = image).
    Returns (all_segments, image_segments).
    """
    n = max(1, int(total_duration / seg_sec))
    actual = total_duration / n

    all_segs, img_segs = [], []
    for i in range(n):
        seg = {
            "idx": i,
            "start": i * actual,
            "end": min((i + 1) * actual, total_duration),
            "dur": actual if i < n - 1 else total_duration - i * actual,
            "use_image": (i % 2 == 1),
        }
        all_segs.append(seg)
        if seg["use_image"]:
            img_segs.append(seg)

    return all_segs, img_segs


# ── gpt-image-1 generation ────────────────────────────────────────────────────

async def generate_images(
    transcript: list,
    image_segments: list,
    tmpdir: str,
    orientation: str = "all",
    openai_api_key: str = "",
) -> dict:
    """
    Generate one gpt-image-1 image per segment (up to _MAX_UNIQUE_IMAGES).
    Uses GPT-4o-mini to build richer visual prompts from transcript context.
    Returns base64-decoded PNGs. Remaining segments recycle generated images.
    Returns {segment_idx: local_path}.
    """
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=openai_api_key)

    # gpt-image-2 supports flexible sizes (multiples of 16, max 3840px)
    # gpt-image-1 fallback uses the same sizes
    size_map = {
        "vertical":   "1024x1792",   # close to 9:16, multiples of 16 ✓
        "horizontal": "1792x1024",   # 16:9
        "all":        "1024x1024",
    }
    size = size_map.get(orientation, "1024x1024")

    global_topic = _global_topic(transcript) if transcript else ""
    results: dict = {}
    generated_paths: list = []
    unique_count = min(len(image_segments), _MAX_UNIQUE_IMAGES)

    for i, seg in enumerate(image_segments):
        if i < unique_count:
            kw = _keywords(transcript, seg["start"], seg["end"])
            path = os.path.join(tmpdir, f"img_{seg['idx']:03d}.png")

            # GPT-4o-mini generates a richer visual description
            visual_desc = await _gpt_visual_description(
                transcript, seg["start"], seg["end"], global_topic, client
            )
            prompt = _build_prompt(visual_desc or kw)
            print(f"[images] gpt-image-1 seg {seg['idx']}: '{(visual_desc or kw)[:70]}'")

            ok = False
            for model in (_IMAGE_MODEL, _IMAGE_MODEL_FALLBACK):
                try:
                    resp = await client.images.generate(
                        model=model,
                        prompt=prompt,
                        size=size,
                        quality="high",
                        n=1,
                    )
                    img_bytes = base64.b64decode(resp.data[0].b64_json)
                    with open(path, "wb") as f:
                        f.write(img_bytes)
                    results[seg["idx"]] = path
                    generated_paths.append(path)
                    print(f"[images] {model} ✓ → {os.path.basename(path)}")
                    ok = True
                    break
                except Exception as e:
                    if model == _IMAGE_MODEL:
                        print(f"[images] {model} unavailable, trying fallback: {e}")
                        continue
                    print(f"[images] image error seg {seg['idx']}: {e}")
            if ok and i < unique_count - 1:
                await asyncio.sleep(1.0)
            else:
                if generated_paths:
                    src = random.choice(generated_paths)
                    dst = os.path.join(tmpdir, f"img_{seg['idx']:03d}.png")
                    if os.path.abspath(src) != os.path.abspath(dst):
                        shutil.copy(src, dst)
                    else:
                        dst = src  # same file, reuse directly
                    results[seg["idx"]] = dst

    print(f"[images] {len(generated_paths)} unique images, {len(results)} segments covered")
    return results


# ── ffmpeg helpers ────────────────────────────────────────────────────────────

def _run(cmd: list, timeout: int = 300, cwd: str = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


def _even(n: int) -> int:
    """Round up to even (required by libx264)."""
    return n + (n % 2)


def _ken_burns(image_path: str, out: str, duration: float,
               w: int, h: int, effect: int) -> bool:
    """
    Generate a silent video clip from a still image with Ken Burns effect.
    Pre-scales image to 1.4× output for zoompan headroom.
    """
    d = max(1, int(duration * 30))
    pw = _even(int(w * 1.5))
    ph = _even(int(h * 1.5))

    pre = f"scale={pw}:{ph}:force_original_aspect_ratio=increase,crop={pw}:{ph}"
    kb  = _EFFECTS[effect].format(d=d, w=w, h=h)
    vf  = f"{pre},{kb}"

    r = _run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-vf", vf,
        "-t", f"{duration:.3f}",
        "-r", "30",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-an",
        out,
    ], timeout=180)
    if r.returncode != 0:
        print(f"[images] ken_burns effect {effect} failed: {r.stderr[-300:]}")
    return r.returncode == 0


def _extract_seg(video: str, out: str, t_start: float,
                 dur: float, w: int, h: int) -> bool:
    """Extract a video-only (no audio) segment from source."""
    r = _run([
        "ffmpeg", "-y",
        "-i", video,
        "-ss", f"{t_start:.3f}", "-t", f"{dur:.3f}",
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=disable",
        "-r", "30",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-an",
        out,
    ])
    if r.returncode != 0:
        print(f"[images] extract_seg failed: {r.stderr[-200:]}")
    return r.returncode == 0


# ── Subtitle helpers for image clips ─────────────────────────────────────────

def _make_seg_ass(
    transcript: list, t_start: float, t_end: float,
    style: str, out_path: str,
) -> Optional[str]:
    """
    Generate an ASS subtitle file covering only words in [t_start, t_end],
    with timestamps offset to 0 (relative to the clip start).
    """
    from backend.video.subtitles import generate_ass

    seg_words = []
    for w in transcript:
        ws = w.get("start", 0)
        we = w.get("end", ws + 0.2)
        if t_start <= ws < t_end:
            seg_words.append({
                "word": w.get("word", ""),
                "start": max(0.0, ws - t_start),
                "end":   min(we - t_start, t_end - t_start),
            })

    if not seg_words:
        return None

    content = generate_ass(seg_words, style)
    if not content:
        return None

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path


def _burn_subs_on_clip(clip_path: str, ass_path: str, out_path: str) -> bool:
    """Burn an ASS subtitle file onto a video clip. Returns True on success."""
    ass_dir  = os.path.dirname(ass_path)
    ass_name = os.path.basename(ass_path)
    r = _run([
        "ffmpeg", "-y", "-i", clip_path,
        "-vf", f"ass={ass_name}",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-an",
        out_path,
    ], timeout=120, cwd=ass_dir)
    if r.returncode != 0:
        print(f"[images] burn_subs failed: {r.stderr[-200:]}")
    return r.returncode == 0


# ── Main mix ──────────────────────────────────────────────────────────────────

def mix_sync(
    video_path: str,
    output_path: str,
    transcript: list,
    w: int,
    h: int,
    image_paths: dict,
    segments: list,
    tmpdir: str,
    subtitle_style: str = "tiktok",
) -> str:
    """
    Build the final mixed video:
    - video segments  → extracted from source (already have subtitles burned in)
    - image segments  → Ken Burns clips + subtitles burned on top
    - audio           → original video audio track, continuous
    """
    effects = list(range(len(_EFFECTS)))
    random.shuffle(effects)

    clip_files = []
    effect_i = 0

    for seg in segments:
        out_seg = os.path.join(tmpdir, f"seg_{seg['idx']:03d}.mp4")

        if seg["use_image"] and seg["idx"] in image_paths:
            eff = effects[effect_i % len(effects)]
            effect_i += 1

            # 1. Generate Ken Burns clip (silent, no subs)
            tmp_kb = os.path.join(tmpdir, f"kb_{seg['idx']:03d}.mp4")
            ok = _ken_burns(image_paths[seg["idx"]], tmp_kb, seg["dur"], w, h, eff)

            if ok:
                # 2. Burn segment subtitles onto the image clip
                ass_seg = os.path.join(tmpdir, f"ass_{seg['idx']:03d}.ass")
                if transcript and _make_seg_ass(
                    transcript, seg["start"], seg["end"], subtitle_style, ass_seg
                ):
                    sub_ok = _burn_subs_on_clip(tmp_kb, ass_seg, out_seg)
                    if not sub_ok:
                        shutil.move(tmp_kb, out_seg)
                else:
                    shutil.move(tmp_kb, out_seg)
            else:
                # Ken Burns failed — fall back to original video segment
                ok = _extract_seg(video_path, out_seg, seg["start"], seg["dur"], w, h)

        else:
            ok = _extract_seg(video_path, out_seg, seg["start"], seg["dur"], w, h)

        if ok and os.path.exists(out_seg) and os.path.getsize(out_seg) > 0:
            clip_files.append(out_seg)
        else:
            print(f"[images] segment {seg['idx']} skipped")

    if not clip_files:
        raise RuntimeError("[images] No segments generated")

    # Concat list (forward slashes for ffmpeg on Windows)
    list_path = os.path.join(tmpdir, "mix_list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for cp in clip_files:
            f.write(f"file '{cp.replace(chr(92), chr(47))}'\n")

    # Concat all clips → single video track
    vtrack = os.path.join(tmpdir, "mixed_vtrack.mp4")
    r = _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_path,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        vtrack,
    ], timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"[images] concat failed: {r.stderr[-400:]}")

    # Mux video track + original continuous audio
    r2 = _run([
        "ffmpeg", "-y",
        "-i", vtrack,
        "-i", video_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        output_path,
    ])
    if r2.returncode != 0:
        raise RuntimeError(f"[images] mux failed: {r2.stderr[-400:]}")

    print(f"[images] mixed video ready → {os.path.basename(output_path)}")
    return output_path
