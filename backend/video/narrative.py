"""
Análisis de narrativa — elimina información repetida (retomas).

Cuando alguien graba a una sola toma suele repetir la misma frase varias veces
hasta que le sale bien. Este módulo agrupa las palabras del transcript en frases,
detecta corridas de frases consecutivas casi idénticas y marca todas menos la
ÚLTIMA para recortarlas del video. Así, si una frase se dice 3 veces, queda solo
la última versión.

Funciona sobre la lista de palabras de Whisper: [{"word", "start", "end"}, ...]
con timestamps relativos al video que se está procesando.

API:
  find_duplicate_ranges(words)        -> [(start, end), ...]  rangos a ELIMINAR
  keep_segments(ranges, total)        -> [(start, end), ...]  complemento (a CONSERVAR)
  remap_words(words, ranges)          -> words con timestamps recalculados
"""
import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

_PUNCT_END = (".", "?", "!", "…")


def _norm(text: str) -> str:
    """Normaliza para comparar: minúsculas, sin puntuación, espacios colapsados."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()


def _make_sentence(words: List[Dict], idxs: List[int]) -> Dict:
    text = " ".join(words[i].get("word", "").strip() for i in idxs).strip()
    first, last = words[idxs[0]], words[idxs[-1]]
    return {
        "text": text,
        "norm": _norm(text),
        "start": float(first.get("start", 0.0)),
        "end": float(last.get("end", last.get("start", 0.0))),
        "n": len(idxs),
    }


def build_sentences(words: List[Dict], max_gap: float = 0.8) -> List[Dict]:
    """Agrupa palabras en frases por puntuación final o pausa larga (>max_gap s)."""
    sentences: List[Dict] = []
    cur: List[int] = []
    for i, w in enumerate(words):
        cur.append(i)
        word = w.get("word", "").strip()
        ends_punct = word.endswith(_PUNCT_END)
        gap = False
        if i + 1 < len(words):
            nxt_start = float(words[i + 1].get("start", 0.0))
            cur_end = float(w.get("end", w.get("start", 0.0)))
            gap = (nxt_start - cur_end) >= max_gap
        if ends_punct or gap:
            sentences.append(_make_sentence(words, cur))
            cur = []
    if cur:
        sentences.append(_make_sentence(words, cur))
    return sentences


def _similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _merge_ranges(ranges: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if not ranges:
        return []
    ordered = sorted(ranges)
    merged = [list(ordered[0])]
    for rs, re_ in ordered[1:]:
        # Merge ranges separated by a tiny gap — between consecutive retakes
        # there is only a breath/pause, safe to drop along with the takes.
        if rs <= merged[-1][1] + 0.4:
            merged[-1][1] = max(merged[-1][1], re_)
        else:
            merged.append([rs, re_])
    return [(a, b) for a, b in merged]


def find_duplicate_ranges(
    words: List[Dict],
    threshold: float = 0.82,
    min_words: int = 3,
) -> List[Tuple[float, float]]:
    """
    Devuelve rangos de tiempo (start, end) de las repeticiones ANTERIORES que se
    deben eliminar, conservando la última ocurrencia de cada corrida repetida.

    Solo considera frases de al menos `min_words` palabras para no recortar
    muletillas cortas legítimas ("sí, sí").
    """
    if not words:
        return []
    sentences = build_sentences(words)
    n = len(sentences)
    ranges: List[Tuple[float, float]] = []

    i = 0
    while i < n:
        j = i
        # Extiende la corrida mientras la frase siguiente sea casi idéntica.
        while (
            j + 1 < n
            and sentences[j]["n"] >= min_words
            and sentences[j + 1]["n"] >= min_words
            and _similar(sentences[j]["norm"], sentences[j + 1]["norm"]) >= threshold
        ):
            j += 1
        if j > i:
            # Conserva la última (j); elimina i..j-1.
            for k in range(i, j):
                ranges.append((sentences[k]["start"], sentences[k]["end"]))
        i = j + 1

    return _merge_ranges(ranges)


def keep_segments(
    remove_ranges: List[Tuple[float, float]],
    total_duration: float,
    padding: float = 0.05,
) -> List[Tuple[float, float]]:
    """Complemento de los rangos a eliminar → segmentos a conservar."""
    ranges = _merge_ranges(remove_ranges)
    keep: List[Tuple[float, float]] = []
    cur = 0.0
    for rs, re_ in ranges:
        seg_end = max(0.0, rs - padding)
        if seg_end > cur + 0.05:
            keep.append((cur, seg_end))
        cur = re_ + padding
    if cur < total_duration - 0.05:
        keep.append((cur, total_duration))
    return keep


def remap_words(
    words: List[Dict],
    remove_ranges: List[Tuple[float, float]],
) -> List[Dict]:
    """
    Reconstruye la lista de palabras tras eliminar `remove_ranges`:
    descarta las palabras dentro de un rango eliminado y desplaza las restantes
    hacia la izquierda por la duración total removida antes de ellas.
    """
    ranges = _merge_ranges(remove_ranges)
    if not ranges:
        return words

    out: List[Dict] = []
    for w in words:
        ws = float(w.get("start", 0.0))
        we = float(w.get("end", ws))
        # Saltar si la palabra cae dentro de un rango eliminado.
        if any(rs <= ws < re_ for rs, re_ in ranges):
            continue
        shift = sum((re_ - rs) for rs, re_ in ranges if re_ <= ws)
        out.append({
            "word": w.get("word", ""),
            "start": max(0.0, ws - shift),
            "end": max(0.0, we - shift),
        })
    return out
