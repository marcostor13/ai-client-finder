"""
On-screen overlays: big "listicle" numbers and a phone-frame border.

- Listicle numbers: detects spoken ordinals in the transcript ("uno/dos/tres",
  "primero/segundo…", or digits) and drops a huge "1." "2." … at that moment —
  the numbered-tips look.
- Phone frame: a thin border framing the subject (drawbox; no PNG asset needed).

Applied to the base video before platform formatting, using frame-relative
coordinates so it survives reformatting. Opt-in: only invoked when enabled.
"""
import re
import subprocess
from typing import Dict, List, Optional


def _run(cmd: list, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# Spoken ordinals → number (Spanish). Word-boundary matched in the transcript.
_ORDINALS = {
    "uno": 1, "primero": 1, "primera": 1, "primer": 1,
    "dos": 2, "segundo": 2, "segunda": 2,
    "tres": 3, "tercero": 3, "tercera": 3, "tercer": 3,
    "cuatro": 4, "cuarto": 4, "cuarta": 4,
    "cinco": 5, "quinto": 5, "quinta": 5,
    "seis": 6, "sexto": 6, "sexta": 6,
    "siete": 7, "septimo": 7, "séptimo": 7,
    "ocho": 8, "octavo": 8,
    "nueve": 9, "noveno": 9,
    "diez": 10, "decimo": 10, "décimo": 10,
}


def detect_listicle_numbers(transcript: list, min_gap: float = 2.0,
                            hold: float = 1.6) -> List[Dict]:
    """
    Return [{n, start, dur}] where a big number should appear. Picks ascending
    ordinals (1,2,3…) as they're spoken, ignoring out-of-order/duplicate hits.
    """
    out: List[Dict] = []
    expected = 1
    last_t = -999.0
    for w in transcript:
        tok = re.sub(r"[^\wáéíóú]", "", (w.get("word") or "").strip().lower())
        n = None
        if tok.isdigit():
            n = int(tok)
        elif tok in _ORDINALS:
            n = _ORDINALS[tok]
        if n is None or n != expected:
            continue
        t = float(w.get("start", 0))
        if t - last_t < min_gap:
            continue
        out.append({"n": n, "start": t, "dur": hold})
        last_t = t
        expected += 1
    return out


def _esc(text: str) -> str:
    """Escape text for ffmpeg drawtext."""
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def build_overlay_vf(numbers: List[Dict], phone_frame: bool,
                     fontfile: Optional[str] = None) -> Optional[str]:
    """Build a -vf chain for the requested overlays, or None if nothing to do."""
    parts: List[str] = []

    if phone_frame:
        parts.append(
            "drawbox=x=iw*0.05:y=ih*0.06:w=iw*0.90:h=ih*0.88:"
            "color=black@0.85:t=max(iw/180\\,4)"
        )

    font = f"fontfile='{fontfile}':" if fontfile else ""
    for item in numbers:
        start = float(item["start"])
        end = start + float(item.get("dur", 1.6))
        txt = _esc(f"{item['n']}.")
        parts.append(
            f"drawtext={font}text='{txt}':fontsize=h/4:fontcolor=black:"
            f"borderw=max(h/220\\,6):bordercolor=white:"
            f"x=(w-text_w)/2:y=h*0.16:"
            f"enable='between(t,{start:.2f},{end:.2f})'"
        )

    return ",".join(parts) if parts else None


def apply_overlays_sync(
    video_path: str,
    output_path: str,
    numbers: List[Dict],
    phone_frame: bool = False,
    fontfile: Optional[str] = None,
) -> str:
    """Apply listicle numbers + phone frame. Returns output_path, or the input
    unchanged if there's nothing to draw."""
    vf = build_overlay_vf(numbers, phone_frame, fontfile)
    if not vf:
        return video_path
    r = _run([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ])
    if r.returncode != 0:
        raise RuntimeError(f"overlays failed: {r.stderr[-400:]}")
    return output_path
