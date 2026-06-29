"""
B-roll planner — picks congruent stock media for each phrase.

The spoken transcript (Spanish) is a poor stock-search query: Pexels is an
English catalogue and literal words rarely map to a good *visual*. This module
turns each B-roll moment into:

  • query : a concise ENGLISH visual search phrase (concrete, 2-4 words)
  • mood  : a tone tag used to colour-grade the clip to match the message
  • prefer: "video" | "image" hint

Strategy:
  1. If OPENAI_API_KEY is set → ONE batched GPT-4o-mini call sees the whole
     transcript and plans every segment together, so the B-roll stays coherent
     with the overall topic.
  2. Otherwise → a heuristic: salient nouns + a Spanish→English concept map,
     anchored to the global topic, with keyword-based mood detection.
"""
import json
import re
from collections import Counter
from typing import Dict, List, Optional

MOODS = ("energetic", "success", "calm", "serious", "dramatic",
         "tech", "nature", "urban", "neutral")

# Dynamic moods read better as motion (video); concept/static moods as stills.
_DYNAMIC_MOODS = {"energetic", "dramatic", "urban", "tech"}


def _prefer_for_mood(mood: Optional[str]) -> str:
    return "video" if (mood or "").lower() in _DYNAMIC_MOODS else "image"

# Spanish stopwords (broader than the basic set) for noun extraction.
_STOP = {
    "de", "la", "el", "en", "y", "a", "que", "los", "las", "un", "una", "es",
    "se", "no", "con", "por", "su", "para", "este", "esta", "esto", "lo", "más",
    "como", "pero", "sus", "le", "ya", "fue", "al", "del", "muy", "tiene", "hay",
    "si", "cuando", "sobre", "también", "son", "todo", "toda", "bien", "ser",
    "puede", "hace", "me", "mi", "tu", "te", "nos", "yo", "él", "ella", "eso",
    "ese", "esa", "porque", "cada", "vez", "ti", "uno", "dos", "tres", "vas",
    "voy", "vamos", "estar", "estoy", "está", "están", "tus", "mis", "soy",
    "the", "and", "is", "in", "it", "of", "to", "that", "with", "this", "for",
    "are", "was", "on", "at", "be", "have", "from", "by", "not", "you", "your",
}

# Concept map: Spanish content word → English visual search term.
_ES_EN = {
    "dinero": "money cash", "finanzas": "finance growth", "riqueza": "wealth luxury",
    "exito": "success achievement", "éxito": "success achievement",
    "fracaso": "failure struggle", "meta": "goal target", "metas": "goals target",
    "habito": "daily routine discipline", "hábito": "daily routine discipline",
    "habitos": "daily routine discipline", "hábitos": "daily routine discipline",
    "disciplina": "discipline focus", "tiempo": "time clock hourglass",
    "salud": "healthy lifestyle", "cuerpo": "fitness body workout",
    "fisico": "athlete training", "físico": "athlete training",
    "mente": "mindset meditation", "cerebro": "brain neurons",
    "miedo": "fear darkness", "exitoso": "successful entrepreneur",
    "trabajo": "work office", "negocio": "business startup",
    "empresa": "corporate office", "equipo": "team collaboration",
    "futuro": "future horizon city", "pasado": "old vintage memories",
    "familia": "family together", "amor": "love couple",
    "viaje": "travel landscape", "naturaleza": "nature landscape",
    "ciudad": "city skyline", "tecnologia": "technology data",
    "tecnología": "technology data", "energia": "energy motion",
    "energía": "energy motion", "crecimiento": "growth plant sunrise",
    "esfuerzo": "effort climbing", "victoria": "victory celebration",
    "libertad": "freedom open road", "sueño": "dream aspiration",
    "sueno": "dream aspiration", "decision": "decision crossroads",
    "decisión": "decision crossroads", "cambio": "transformation change",
    "vida": "lifestyle people", "comida": "food cooking",
    "comes": "food meal", "personas": "people crowd", "gente": "people crowd",
    "criticos": "crowd judging", "críticos": "crowd judging",
    "victimas": "shadow figure", "víctimas": "shadow figure",
}

# Mood detection cue words (Spanish).
_MOOD_CUES = {
    "success": ("exito", "éxito", "logro", "ganar", "rico", "riqueza", "victoria", "triunfo", "dinero"),
    "dramatic": ("miedo", "fracaso", "muerte", "dolor", "crisis", "oscuro", "víctima", "victima", "perder"),
    "serious": ("problema", "error", "critic", "advert", "cuidado", "riesgo", "deuda"),
    "energetic": ("acción", "accion", "rápido", "rapido", "energía", "energia", "fuerza", "ahora", "vamos", "explos"),
    "calm": ("paz", "calma", "tranquil", "respira", "descanso", "medita", "silencio"),
    "nature": ("naturaleza", "mar", "montaña", "montana", "bosque", "río", "rio", "sol", "playa"),
    "tech": ("tecnolog", "datos", "digital", "inteligencia", "algoritmo", "software", "internet"),
    "urban": ("ciudad", "calle", "tráfico", "trafico", "oficina", "edificio"),
}


def _phrase_text(transcript: list, t_start: float, t_end: float) -> str:
    """Raw spoken text within a time window."""
    words = [w.get("word", "") for w in transcript
             if t_start <= w.get("start", 0) < t_end]
    return re.sub(r"\s+", " ", " ".join(words)).strip()


def _tokens(text: str) -> List[str]:
    out = []
    for w in re.sub(r"[^\wáéíóúñü]", " ", text.lower()).split():
        if len(w) > 3 and w not in _STOP:
            out.append(w)
    return out


def global_topic(transcript: list) -> str:
    counts = Counter(_tokens(" ".join(w.get("word", "") for w in transcript)))
    return " ".join(w for w, _ in counts.most_common(4))


def _heuristic_query(text: str, topic_terms: List[str]) -> str:
    toks = _tokens(text)
    mapped = []
    for t in toks:
        if t in _ES_EN:
            mapped.append(_ES_EN[t])
        if len(mapped) >= 2:
            break
    if not mapped:
        # No known concept — fall back to the global topic, mapped if possible.
        for t in topic_terms:
            mapped.append(_ES_EN.get(t, t))
            if len(mapped) >= 2:
                break
    return " ".join(dict.fromkeys(" ".join(mapped).split()))[:60] or "cinematic abstract background"


def _heuristic_mood(text: str) -> str:
    low = text.lower()
    for mood, cues in _MOOD_CUES.items():
        if any(c in low for c in cues):
            return mood
    return "neutral"


def _heuristic_plan(transcript: list, segments: list) -> Dict[int, dict]:
    topic_terms = _tokens(global_topic(transcript))
    plan: Dict[int, dict] = {}
    for seg in segments:
        text = _phrase_text(transcript, seg["start"], seg["end"])
        mood = _heuristic_mood(text)
        plan[seg["idx"]] = {
            "query": _heuristic_query(text, topic_terms),
            "mood": mood,
            "prefer": _prefer_for_mood(mood),
        }
    return plan


def dominant_mood(transcript: list) -> str:
    """Most common mood across the whole transcript (for background music)."""
    text = " ".join(w.get("word", "") for w in transcript)
    counts = Counter()
    low = text.lower()
    for mood, cues in _MOOD_CUES.items():
        hits = sum(low.count(c) for c in cues)
        if hits:
            counts[mood] += hits
    return counts.most_common(1)[0][0] if counts else "neutral"


async def _llm_plan(transcript: list, segments: list, openai_key: str) -> Optional[Dict[int, dict]]:
    """One batched GPT-4o-mini call → coherent plan for every segment."""
    try:
        from openai import AsyncOpenAI
    except Exception:
        return None
    client = AsyncOpenAI(api_key=openai_key)

    topic = global_topic(transcript)
    items = []
    order = []
    for seg in segments:
        text = _phrase_text(transcript, seg["start"], seg["end"])
        if not text:
            continue
        order.append(seg["idx"])
        items.append(f'[{seg["idx"]}] "{text[:160]}"')
    if not items:
        return {}

    sys = (
        "You are a visual director choosing B-roll for a short vertical video. "
        "For each transcript excerpt, output the MOST congruent stock footage: a "
        "concise ENGLISH search query (2-4 words, concrete and visual, no quotes) "
        "and a mood. Keep every choice consistent with the overall topic so the "
        "video feels coherent. Avoid literal translations — pick a strong VISUAL "
        f"metaphor. mood must be one of: {', '.join(MOODS)}. "
        'Reply ONLY with a JSON array: [{"i": <idx>, "query": "...", "mood": "..."}].'
    )
    user = f"Overall topic: {topic}\n\nExcerpts:\n" + "\n".join(items)

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": sys},
                      {"role": "user", "content": user}],
            max_tokens=900,
            temperature=0.7,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.I | re.M).strip()
        data = json.loads(raw)
    except Exception as e:
        print(f"[broll] LLM plan failed, using heuristic: {e}")
        return None

    plan: Dict[int, dict] = {}
    for obj in data if isinstance(data, list) else []:
        try:
            i = int(obj["i"])
            q = str(obj.get("query", "")).strip()
            mood = str(obj.get("mood", "neutral")).strip().lower()
            if q:
                plan[i] = {"query": q[:60], "mood": mood if mood in MOODS else "neutral"}
        except Exception:
            continue
    # Fill any missing segment from the heuristic so none ends up empty.
    if plan:
        heur = _heuristic_plan(transcript, segments)
        for seg in segments:
            entry = plan.get(seg["idx"])
            if not entry:
                plan[seg["idx"]] = heur[seg["idx"]]
            else:
                entry["prefer"] = _prefer_for_mood(entry.get("mood"))
        return plan
    return None


async def plan_broll(transcript: list, segments: list,
                     openai_key: str = "") -> Dict[int, dict]:
    """Return {segment_idx: {query, mood, prefer}} for every B-roll segment."""
    if openai_key:
        plan = await _llm_plan(transcript, segments, openai_key)
        if plan:
            return plan
    return _heuristic_plan(transcript, segments)
