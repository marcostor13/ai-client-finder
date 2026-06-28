"""
Subtitle generation: Whisper API → word timestamps → ASS animated file.

Styles:
  tiktok      — word-by-word, Impact, elastic pop-in, white + thick black outline
  minimal     — 4-word chunks, Arial Black, grow + fade, clean shadow
  bold_yellow — 3-word sliding window, Impact, yellow active word (CapCut style)
  cinematic   — word-by-word, Impact, white + purple glow outline
"""
import asyncio
import os
import re
from typing import List, Dict

from openai import OpenAI
from backend.database import settings

openai = OpenAI(api_key=settings.openai_api_key)

# ── Timecode helper ────────────────────────────────────────────────────────────

def _tc(seconds: float) -> str:
    """Seconds → ASS timecode  H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ── ASS header ────────────────────────────────────────────────────────────────

# PlayRes for 9:16 canvas; ffmpeg scales for other formats via ScaledBorderAndShadow
_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
{styles}

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

# ASS color format: &HAABBGGRR
# Purple #6D28D9 → BGR: B=D9, G=28, R=6D → &H00D9286D
# Yellow #FFFF00 → BGR: B=00, G=FF, R=FF → &H0000FFFF
# Gray dim #C0C0C0 → &H00C0C0C0

STYLES = {
    "tiktok": (
        # Impact 130pt — viral word-pop: huge, thick 9px outline, no shadow
        # 130/1920 ≈ 6.8% frame height per word → very prominent on mobile
        "Style: tiktok,Impact,130,&H00FFFFFF,&H00FFFFFF,"
        "&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,9,0,2,80,80,210,1"
    ),
    "minimal": (
        # Arial Black 84pt — clean word-groups, thin outline, soft shadow
        "Style: minimal,Arial Black,84,&H00FFFFFF,&H00FFFFFF,"
        "&H00000000,&H88000000,-1,0,0,0,100,100,0,0,1,3,4,2,80,80,160,1"
    ),
    "bold_yellow": (
        # Impact 108pt — 3-word sliding window, yellow active via inline tags
        "Style: active,Impact,108,&H00FFFFFF,&H00FFFFFF,"
        "&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,8,0,2,80,80,195,1"
    ),
    "cinematic": (
        # Impact 124pt — ALL CAPS, purple glow outline+shadow
        "Style: cinematic,Impact,124,&H00FFFFFF,&H00FFFFFF,"
        "&H00D9286D,&H80D9286D,-1,0,0,0,100,100,0,0,1,6,4,2,80,80,200,1"
    ),
    "kinetic": (
        # Impact 96pt, centred (Alignment 5). Keyword/connector size & colour
        # come from inline tags in _events_kinetic.
        "Style: kinetic,Impact,96,&H00FFFFFF,&H00FFFFFF,"
        "&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,5,90,90,0,1"
    ),
}


def _build_header(style: str) -> str:
    return _HEADER.format(styles=STYLES.get(style, STYLES["tiktok"]))


# ── ASS event builders ────────────────────────────────────────────────────────

def _events_tiktok(words: List[Dict]) -> str:
    """Word-by-word with elastic bounce: scale 120% → 95% → 100%."""
    lines = []
    for i, w in enumerate(words):
        start = w["start"]
        end = words[i + 1]["start"] + 0.02 if i < len(words) - 1 else w["end"] + 0.4
        end = max(end, start + 0.12)
        text = w["word"].strip()
        if not text:
            continue
        # Elastic pop: appear at 120%, bounce to 95%, settle at 100%
        anim = (
            r"{\an2\fad(40,0)"
            r"\fscx120\fscy120"
            r"\t(0,80,\fscx95\fscy95)"
            r"\t(80,160,\fscx100\fscy100)}"
        )
        lines.append(f"Dialogue: 0,{_tc(start)},{_tc(end)},tiktok,,0,0,0,,{anim}{text}")
    return "\n".join(lines)


def _events_minimal(words: List[Dict], chunk: int = 3) -> str:
    """Groups of 3 words — grow from 94% + fade in, fade out."""
    lines = []
    groups = [words[i:i + chunk] for i in range(0, len(words), chunk)]
    for g in groups:
        start = g[0]["start"]
        end = g[-1]["end"] + 0.3
        text = " ".join(w["word"].strip() for w in g if w["word"].strip())
        if not text:
            continue
        # Start slightly small, grow to full size while fading in
        anim = (
            r"{\an2\fad(120,80)"
            r"\fscx94\fscy94"
            r"\t(0,180,\fscx100\fscy100)}"
        )
        lines.append(f"Dialogue: 0,{_tc(start)},{_tc(end)},minimal,,0,0,0,,{anim}{text}")
    return "\n".join(lines)


def _events_bold_yellow(words: List[Dict]) -> str:
    """
    3-word sliding window: prev (white/small) + ACTIVE (yellow/pop) + next (white/small).
    Uses inline ASS color override tags.
    """
    # Yellow in ASS BGR: &H0000FFFF  |  Dim white: &H00C8C8C8
    TAG_YELLOW = r"{\c&H0000FFFF&\fscx100\fscy100\t(0,80,\fscx110\fscy110)\t(80,160,\fscx100\fscy100)}"
    TAG_DIM    = r"{\c&H00C0C0C0&\fscx84\fscy84}"
    TAG_RESET  = r"{\r}"

    lines = []
    for i, w in enumerate(words):
        start = w["start"]
        end = words[i + 1]["start"] + 0.02 if i < len(words) - 1 else w["end"] + 0.4
        end = max(end, start + 0.15)
        curr = w["word"].strip()
        if not curr:
            continue

        prev_w = words[i - 1]["word"].strip() if i > 0 else ""
        next_w = words[i + 1]["word"].strip() if i < len(words) - 1 else ""

        parts = [r"{\an2\fad(30,0)}"]
        if prev_w:
            parts.append(TAG_DIM + prev_w + TAG_RESET + " ")
        parts.append(TAG_YELLOW + curr + TAG_RESET)
        if next_w:
            parts.append(" " + TAG_DIM + next_w + TAG_RESET)

        text = "".join(parts)
        lines.append(f"Dialogue: 0,{_tc(start)},{_tc(end)},active,,0,0,0,,{text}")
    return "\n".join(lines)


def _events_cinematic(words: List[Dict]) -> str:
    """Word-by-word with soft fade + subtle scale — purple glow via style outline."""
    lines = []
    for i, w in enumerate(words):
        start = w["start"]
        end = words[i + 1]["start"] + 0.02 if i < len(words) - 1 else w["end"] + 0.4
        end = max(end, start + 0.12)
        text = w["word"].strip().upper()   # all-caps for cinematic feel
        if not text:
            continue
        # Soft grow + fade in
        anim = (
            r"{\an2\fad(100,40)"
            r"\fscx96\fscy96"
            r"\t(0,150,\fscx100\fscy100)}"
        )
        lines.append(f"Dialogue: 0,{_tc(start)},{_tc(end)},cinematic,,0,0,0,,{anim}{text}")
    return "\n".join(lines)


# ── Kinetic typography (big multi-colour phrase captions) ──────────────────────

# Palette in ASS BGR (&H00BBGGRR). Cycles per phrase.
_KINETIC_COLORS = [
    "&H002D2DFF&",   # red    #FF2D2D
    "&H00EED322&",   # cyan   #22D3EE
    "&H0080DE4A&",   # green  #4ADE80
    "&H00FA8BA7&",   # purple #A78BFA
    "&H003BD4FF&",   # yellow #FFD43B
]

_KIN_STOP = {
    "de", "la", "el", "en", "y", "a", "que", "los", "las", "un", "una", "es",
    "se", "no", "con", "por", "su", "para", "este", "esta", "lo", "más", "como",
    "pero", "sus", "le", "ya", "al", "del", "muy", "si", "tu", "te", "me", "mi",
    "o", "u", "ni", "yo", "él", "ella", "eso", "esa", "ese", "son", "fue", "ser",
    "the", "and", "is", "in", "it", "of", "to", "that", "with", "this", "for",
    "are", "was", "on", "at", "be", "you", "your",
}


def _kin_phrases(words: List[Dict], max_words: int = 6, gap: float = 0.5) -> List[List[Dict]]:
    """Group consecutive words into short phrases by timing gaps / length."""
    phrases: List[List[Dict]] = []
    cur: List[Dict] = []
    for w in words:
        if not w["word"].strip():
            continue
        if cur:
            prev_end = cur[-1].get("end", cur[-1]["start"])
            if (w["start"] - prev_end) > gap or len(cur) >= max_words:
                phrases.append(cur)
                cur = []
        cur.append(w)
    if cur:
        phrases.append(cur)
    return phrases


def _kin_keyword_idx(phrase: List[Dict]) -> int:
    """Index of the word to emphasise: the longest content word."""
    best_i, best_len = 0, -1
    for i, w in enumerate(phrase):
        tok = re.sub(r"[^\wáéíóúñü]", "", w["word"].strip().lower())
        if tok in _KIN_STOP or len(tok) < 3:
            continue
        if len(tok) > best_len:
            best_i, best_len = i, len(tok)
    return best_i if best_len > 0 else len(phrase) - 1


def _events_kinetic(words: List[Dict]) -> str:
    """
    Viral kinetic typography: small italic connector words + the keyword huge and
    coloured on its own line, with a pop-in bounce. Palette cycles per phrase.
    """
    phrases = _kin_phrases(words)
    lines = []
    for pi, phrase in enumerate(phrases):
        start = phrase[0]["start"]
        if pi < len(phrases) - 1:
            end = max(phrases[pi + 1][0]["start"], start + 0.4)
        else:
            end = phrase[-1].get("end", start) + 0.5
        kw_i = _kin_keyword_idx(phrase)
        color = _KINETIC_COLORS[pi % len(_KINETIC_COLORS)]

        small = lambda t: (r"{\fscx52\fscy52\b0\i1\c&H00FFFFFF&\3c&H00000000&}"
                           + t + r"{\r}")
        big = lambda t: (
            r"{\b1\i0\c" + color + r"\3c&H00000000&"
            r"\fscx150\fscy150\t(0,110,\fscx170\fscy170)\t(110,210,\fscx150\fscy150)}"
            + t.upper() + r"{\r}"
        )

        pre = [w["word"].strip() for w in phrase[:kw_i] if w["word"].strip()]
        kw = phrase[kw_i]["word"].strip()
        post = [w["word"].strip() for w in phrase[kw_i + 1:] if w["word"].strip()]

        chunks = []
        if pre:
            chunks.append(small(" ".join(pre)))
        chunks.append(big(kw))
        if post:
            chunks.append(small(" ".join(post)))
        text = r"\N".join(chunks)

        lines.append(f"Dialogue: 0,{_tc(start)},{_tc(end)},kinetic,,0,0,0,,"
                     r"{\an5\fad(60,40)}" + text)
    return "\n".join(lines)


EVENT_BUILDERS = {
    "tiktok":      _events_tiktok,
    "minimal":     _events_minimal,
    "bold_yellow": _events_bold_yellow,
    "cinematic":   _events_cinematic,
    "kinetic":     _events_kinetic,
}


# ── Whisper transcription ─────────────────────────────────────────────────────

def _transcribe_sync(audio_path: str) -> List[Dict]:
    """Returns list of {word, start, end} dicts."""
    with open(audio_path, "rb") as f:
        resp = openai.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    return [{"word": w.word, "start": w.start, "end": w.end} for w in (resp.words or [])]


async def transcribe(audio_path: str) -> List[Dict]:
    return await asyncio.to_thread(_transcribe_sync, audio_path)


# ── ASS file generation ───────────────────────────────────────────────────────

def generate_ass(words: List[Dict], style: str = "tiktok") -> str:
    """Return full ASS file content as string."""
    if not words:
        return ""
    builder = EVENT_BUILDERS.get(style, _events_tiktok)
    events = builder(words)
    return _build_header(style) + events + "\n"


def write_ass(words: List[Dict], out_path: str, style: str = "tiktok") -> str:
    content = generate_ass(words, style)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path
