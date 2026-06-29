"""
B-roll mixer — intercala imágenes y videos LIBRES (stock gratuito) con la
toma original, relevantes a lo que se dice en cada momento del video.

Pipeline (per video):
  • plan_segments()  → divide el video en segmentos y marca ~60% como B-roll,
                       alternando entre imagen y video.
  • fetch_broll()    → para cada segmento B-roll busca media libre (Pexels)
                       usando las palabras del transcript en ese instante, y la
                       descarga.
  • mix_sync()       → arma el video final: las imágenes reciben efecto Ken
                       Burns, los videos se escalan/recortan al formato, y a
                       ambos se les queman los subtítulos del tramo. El audio
                       original (continuo) se conserva.

Ken Burns variants (8 effects, shuffled per video) — solo para imágenes:
  0 zoom-in punch · 1 zoom-out reveal · 2 pan L→R · 3 pan R→L ·
  4 diagonal push-in · 5 vertical scan · 6 vertical reveal · 7 slow drift
"""

import asyncio
import os
import random
import re
import shutil
import subprocess
from collections import Counter
from typing import Optional

from backend.video import stock

_STOP = {
    "de", "la", "el", "en", "y", "a", "que", "los", "las", "un", "una",
    "es", "se", "no", "con", "por", "su", "para", "este", "esta", "lo",
    "más", "como", "pero", "sus", "le", "ya", "fue", "al", "del", "muy",
    "tiene", "hay", "si", "cuando", "sobre", "también", "son", "todo",
    "bien", "ser", "puede", "hace", "me", "mi", "tu",
    "the", "and", "is", "in", "it", "of", "to", "that", "with", "this",
    "for", "are", "was", "on", "at", "be", "have", "from", "by", "not",
}

# Proportion of the video covered by B-roll (imágenes + videos).
_BROLL_RATIO = 0.60

# zoompan expressions — {d} frames, {w}×{h} output size
# Input is pre-scaled to 1.5× so the max zoom of 1.35 always has headroom.
_EFFECTS = [
    # 0: Zoom-in punch — fast hook, 1.0→1.35 (most thumb-stopping)
    "zoompan=z='min(zoom+0.0023,1.35)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30",
    # 1: Zoom-out reveal — starts 1.35, dramatically pulls back
    "zoompan=z='if(lte(zoom,1.0),1.35,max(1.001,zoom-0.0023))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30",
    # 2: Pan left→right + slow zoom
    "zoompan=z='min(zoom+0.0008,1.25)':x='if(lte(on,1),0,min(x+2.0,iw/5))':y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30",
    # 3: Pan right→left + slow zoom
    "zoompan=z='min(zoom+0.0008,1.25)':x='if(lte(on,1),iw/5,max(0,x-2.0))':y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30",
    # 4: Diagonal push-in — zoom + drift top-left→bottom-right
    "zoompan=z='min(zoom+0.0018,1.35)':x='if(lte(on,1),0,min(x+1.4,iw/5))':y='if(lte(on,1),0,min(y+1.4,ih/5))':d={d}:s={w}x{h}:fps=30",
    # 5: Vertical scan top→bottom
    "zoompan=z='1.22':x='iw/2-(iw/zoom/2)':y='if(lte(on,1),0,min(y+2.0,ih/5))':d={d}:s={w}x{h}:fps=30",
    # 6: Vertical reveal bottom→top
    "zoompan=z='1.22':x='iw/2-(iw/zoom/2)':y='if(lte(on,1),ih/5,max(0,y-2.0))':d={d}:s={w}x{h}:fps=30",
    # 7: Slow cinematic drift
    "zoompan=z='min(zoom+0.0005,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30",
]


# ── Keyword / topic helpers ───────────────────────────────────────────────────

def _keywords(transcript: list, t_start: float, t_end: float) -> str:
    """Content keywords spoken within a transcript time window."""
    words = []
    for item in transcript:
        t = item.get("start", 0)
        if t_start <= t < t_end:
            w = re.sub(r"[^\w]", "", item.get("word", "")).strip().lower()
            if w and len(w) > 3 and w not in _STOP:
                words.append(w)
    seen: set = set()
    unique = [w for w in words if not (w in seen or seen.add(w))]  # type: ignore
    return " ".join(unique[:5])


def _global_topic(transcript: list) -> str:
    """Top content words from the full transcript (overall video subject)."""
    words = []
    for item in transcript:
        w = re.sub(r"[^\w]", "", item.get("word", "")).strip().lower()
        if w and len(w) > 4 and w not in _STOP:
            words.append(w)
    return " ".join(w for w, _ in Counter(words).most_common(4))


# ── Segment planning ──────────────────────────────────────────────────────────

def plan_segments(total_duration: float, seg_sec: float = 5.0,
                  ratio: float = _BROLL_RATIO) -> tuple:
    """
    Split the video into N equal segments and mark ~`ratio` of them as B-roll.

    Uses a fractional accumulator so the B-roll share matches `ratio` closely
    (e.g. 0.6 → 3 of every 5 segments). The first segment stays as the original
    take (establishing shot). B-roll segments alternate image / video so the
    final cut interleaves both, per the request.

    Returns (all_segments, broll_segments). Each segment dict has:
      idx, start, end, dur, use_image (=is B-roll), media_type ("image"|"video").
    """
    n = max(1, round(total_duration / seg_sec))
    actual = total_duration / n

    all_segs, broll_segs = [], []
    acc = 0.0
    broll_count = 0
    for i in range(n):
        acc += ratio
        use = False
        if i > 0 and acc >= 1.0:      # keep segment 0 as the original take
            use = True
            acc -= 1.0
        media_type = None
        if use:
            media_type = "image" if broll_count % 2 == 0 else "video"
            broll_count += 1

        seg = {
            "idx": i,
            "start": i * actual,
            "end": min((i + 1) * actual, total_duration),
            "dur": actual if i < n - 1 else total_duration - i * actual,
            "use_image": use,
            "media_type": media_type,
        }
        all_segs.append(seg)
        if use:
            broll_segs.append(seg)

    return all_segs, broll_segs


# ── Stock fetching ────────────────────────────────────────────────────────────

async def fetch_broll(
    transcript: list,
    broll_segments: list,
    tmpdir: str,
    orientation: str = "all",
    openai_key: str = "",
) -> dict:
    """
    Download one congruent stock asset per B-roll segment.

    A planner (LLM when OPENAI_API_KEY is set, else a heuristic) turns each
    phrase into an English visual query + a mood, so the footage matches what's
    said and the colour grade matches the tone.
    Returns {segment_idx: {"type", "path", "mood", "query"}}.
    """
    if not stock.available():
        return {}

    from backend.video import broll_planner
    plan = await broll_planner.plan_broll(transcript, broll_segments, openai_key)
    global_topic = _global_topic(transcript) if transcript else ""
    seen: set = set()
    results: dict = {}

    for seg in broll_segments:
        entry = plan.get(seg["idx"], {})
        query = entry.get("query") or _keywords(transcript, seg["start"], seg["end"]) or global_topic
        mood = entry.get("mood", "neutral")
        # Mood drives image-vs-video: dynamic tones → motion, concepts → stills.
        want_video = entry.get("prefer", seg.get("media_type")) == "video"
        base = os.path.join(tmpdir, f"broll_{seg['idx']:03d}")

        got = await stock.fetch_media(query, want_video, orientation, base, seen)
        if got:
            path, mtype = got
            results[seg["idx"]] = {"type": mtype, "path": path, "mood": mood, "query": query}
            print(f"[broll] seg {seg['idx']:>3} {mtype:<5} [{mood}] ← '{query[:48]}'")
        else:
            print(f"[broll] seg {seg['idx']:>3} no media for '{query[:48]}'")

    print(f"[broll] {len(results)}/{len(broll_segments)} B-roll segments covered")
    return results


# ── ffmpeg helpers ────────────────────────────────────────────────────────────

def _run(cmd: list, timeout: int = 300, cwd: str = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


def _even(n: int) -> int:
    """Round up to even (required by libx264)."""
    return n + (n % 2)


# Context-aware colour grade per mood (subtle, applied to every B-roll clip so
# the footage matches the tone of what's being said).
_MOOD_FILTERS = {
    "energetic": "eq=contrast=1.12:saturation=1.35:brightness=0.02,unsharp=5:5:0.6",
    "success":   "eq=contrast=1.08:saturation=1.22,colorbalance=rs=0.05:gs=0.02:bs=-0.05",
    "calm":      "eq=contrast=1.0:saturation=1.06:brightness=0.02,colorbalance=rs=0.03:bs=0.02",
    "serious":   "eq=contrast=1.16:saturation=0.82:brightness=-0.02,vignette",
    "dramatic":  "eq=contrast=1.25:saturation=0.72:brightness=-0.03,vignette",
    "tech":      "eq=contrast=1.1:saturation=0.92,colorbalance=bs=0.07:rs=-0.03",
    "nature":    "eq=contrast=1.06:saturation=1.26",
    "urban":     "eq=contrast=1.12:saturation=0.96,colorbalance=bs=0.03",
    "neutral":   "eq=contrast=1.05:saturation=1.1",
}


def _filter_for_mood(mood: Optional[str]) -> str:
    return _MOOD_FILTERS.get((mood or "neutral").lower(), _MOOD_FILTERS["neutral"])


def _ken_burns(image_path: str, out: str, duration: float,
               w: int, h: int, effect: int, mood: Optional[str] = None) -> bool:
    """Silent video clip from a still image with a Ken Burns effect + mood grade."""
    d = max(1, int(duration * 30))
    pw = _even(int(w * 1.5))
    ph = _even(int(h * 1.5))

    pre = f"scale={pw}:{ph}:force_original_aspect_ratio=increase,crop={pw}:{ph}"
    kb = _EFFECTS[effect].format(d=d, w=w, h=h)
    vf = f"{pre},{kb},{_filter_for_mood(mood)}"

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
        print(f"[broll] ken_burns effect {effect} failed: {r.stderr[-300:]}")
    return r.returncode == 0


def _prepare_video_clip(src: str, out: str, duration: float,
                        w: int, h: int, mood: Optional[str] = None) -> bool:
    """
    Turn a stock video into a silent clip of exactly `duration` at w×h, with a
    mood-matched colour grade. Loops the source if shorter than the segment.
    """
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1,{_filter_for_mood(mood)}"
    )
    r = _run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", src,
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-r", "30",
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-an",
        out,
    ], timeout=240)
    if r.returncode != 0:
        print(f"[broll] prepare_video failed: {r.stderr[-300:]}")
    return r.returncode == 0


def _extract_seg(video: str, out: str, t_start: float,
                 dur: float, w: int, h: int, zoom: bool = False) -> bool:
    """Extract a video-only (no audio) segment from the source take.

    zoom=True applies a subtle Ken-Burns punch-in (energy/variation on emphasis).
    """
    if zoom:
        d = max(1, int(dur * 30))
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
              f"zoompan=z='min(zoom+0.0010,1.12)':x='iw/2-(iw/zoom/2)':"
              f"y='ih/2-(ih/zoom/2)':d={d}:s={w}x{h}:fps=30")
    else:
        vf = f"scale={w}:{h}:force_original_aspect_ratio=disable"
    r = _run([
        "ffmpeg", "-y",
        "-i", video,
        "-ss", f"{t_start:.3f}", "-t", f"{dur:.3f}",
        "-vf", vf,
        "-r", "30",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-an",
        out,
    ])
    if r.returncode != 0:
        print(f"[broll] extract_seg failed: {r.stderr[-200:]}")
    return r.returncode == 0


def _concat_xfade(clip_files: list, out: str, dur: float = 0.3) -> bool:
    """Concatenate clips with a short crossfade between each (video only).

    Reads each clip's duration via ffprobe. Returns False on any failure so the
    caller can fall back to plain concat. Audio is muxed separately by caller.
    """
    if len(clip_files) < 2:
        return False
    durs = []
    for c in clip_files:
        p = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                  "-of", "default=noprint_wrappers=1:nokey=1", c], timeout=30)
        try:
            durs.append(float(p.stdout.strip()))
        except Exception:
            return False

    inputs = []
    for c in clip_files:
        inputs += ["-i", c]
    fc = ""
    prev = "0:v"
    offset = durs[0]
    for i in range(1, len(clip_files)):
        off = max(0.0, offset - dur)
        label = f"x{i}"
        fc += (f"[{prev}][{i}:v]xfade=transition=fade:duration={dur}:"
               f"offset={off:.3f}[{label}];")
        prev = label
        offset = off + durs[i]
    fc = fc.rstrip(";")
    r = _run(["ffmpeg", "-y"] + inputs + [
        "-filter_complex", fc,
        "-map", f"[{prev}]",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        out,
    ], timeout=600)
    if r.returncode != 0:
        print(f"[broll] xfade concat failed: {r.stderr[-300:]}")
    return r.returncode == 0


# ── Subtitle helpers for B-roll clips ─────────────────────────────────────────

def _make_seg_ass(
    transcript: list, t_start: float, t_end: float,
    style: str, out_path: str,
) -> Optional[str]:
    """ASS subtitle file for words in [t_start, t_end], offset to clip start."""
    from backend.video.subtitles import generate_ass

    seg_words = []
    for w in transcript:
        ws = w.get("start", 0)
        we = w.get("end", ws + 0.2)
        if t_start <= ws < t_end:
            seg_words.append({
                "word": w.get("word", ""),
                "start": max(0.0, ws - t_start),
                "end": min(we - t_start, t_end - t_start),
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
    """Burn an ASS subtitle file onto a clip. Returns True on success."""
    ass_dir = os.path.dirname(ass_path)
    ass_name = os.path.basename(ass_path)
    r = _run([
        "ffmpeg", "-y", "-i", clip_path,
        "-vf", f"ass={ass_name}",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-an",
        out_path,
    ], timeout=120, cwd=ass_dir)
    if r.returncode != 0:
        print(f"[broll] burn_subs failed: {r.stderr[-200:]}")
    return r.returncode == 0


# ── Main mix ──────────────────────────────────────────────────────────────────

def mix_sync(
    video_path: str,
    output_path: str,
    transcript: list,
    w: int,
    h: int,
    media: dict,
    segments: list,
    tmpdir: str,
    subtitle_style: str = "tiktok",
    zoom_punch: bool = False,
    transitions: bool = False,
) -> str:
    """
    Build the final mixed video:
      • original segments → extracted from source (subtitles already burned in),
                            with an optional subtle zoom-punch on alternate cuts
      • image  B-roll     → Ken Burns clip + subtitles burned on top
      • video  B-roll     → scaled/cropped stock clip + subtitles burned on top
      • audio             → original continuous audio track from `video_path`
      • transitions       → optional crossfade between clips

    `media` maps {segment_idx: {"type": "image"|"video", "path": ...}}.
    """
    effects = list(range(len(_EFFECTS)))
    random.shuffle(effects)

    clip_files = []
    effect_i = 0
    vid_seg_i = 0

    for seg in segments:
        out_seg = os.path.join(tmpdir, f"seg_{seg['idx']:03d}.mp4")
        asset = media.get(seg["idx"]) if seg.get("use_image") else None

        if asset and os.path.exists(asset.get("path", "")):
            tmp_clip = os.path.join(tmpdir, f"clip_{seg['idx']:03d}.mp4")
            mood = asset.get("mood")

            if asset["type"] == "video":
                ok = _prepare_video_clip(asset["path"], tmp_clip, seg["dur"], w, h, mood)
            else:
                eff = effects[effect_i % len(effects)]
                effect_i += 1
                ok = _ken_burns(asset["path"], tmp_clip, seg["dur"], w, h, eff, mood)

            if ok:
                # Burn the matching subtitles onto the B-roll clip.
                ass_seg = os.path.join(tmpdir, f"ass_{seg['idx']:03d}.ass")
                if transcript and _make_seg_ass(
                    transcript, seg["start"], seg["end"], subtitle_style, ass_seg
                ):
                    if not _burn_subs_on_clip(tmp_clip, ass_seg, out_seg):
                        shutil.move(tmp_clip, out_seg)
                else:
                    shutil.move(tmp_clip, out_seg)
            else:
                # B-roll clip failed — fall back to the original take.
                _extract_seg(video_path, out_seg, seg["start"], seg["dur"], w, h)
        else:
            # Talking-head segment. Zoom-punch alternate segments when enabled.
            zoom = zoom_punch and (vid_seg_i % 2 == 1)
            vid_seg_i += 1
            _extract_seg(video_path, out_seg, seg["start"], seg["dur"], w, h, zoom=zoom)

        if os.path.exists(out_seg) and os.path.getsize(out_seg) > 0:
            clip_files.append(out_seg)
        else:
            print(f"[broll] segment {seg['idx']} skipped")

    if not clip_files:
        raise RuntimeError("[broll] No segments generated")

    vtrack = os.path.join(tmpdir, "mixed_vtrack.mp4")

    # Optional crossfade transitions; fall back to plain concat on failure.
    if transitions and _concat_xfade(clip_files, vtrack):
        pass
    else:
        # Concat list (forward slashes for ffmpeg on Windows)
        list_path = os.path.join(tmpdir, "mix_list.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for cp in clip_files:
                f.write(f"file '{cp.replace(chr(92), chr(47))}'\n")

        r = _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            vtrack,
        ], timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"[broll] concat failed: {r.stderr[-400:]}")

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
        raise RuntimeError(f"[broll] mux failed: {r2.stderr[-400:]}")

    print(f"[broll] mixed video ready → {os.path.basename(output_path)}")
    return output_path
