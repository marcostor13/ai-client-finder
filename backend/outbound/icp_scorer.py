"""
ICP Scorer — scores a company dict (Phase 1 data) from 0-100.
Works with partial data (only name, website, location, description).
Phase 2 deep analysis adds tech_stack/SSL/social which can re-score.
"""
from typing import Any, Dict, List, Tuple

DEFAULT_WEIGHTS: Dict[str, int] = {
    "geo": 15,
    "industry": 25,
    "has_website": 10,
    "digital_gap": 30,   # signals that they need digital services
    "description": 20,
}

LATAM_GEOS = [
    "peru", "lima", "miraflores", "san isidro", "surco", "barranco",
    "mexico", "colombia", "chile", "argentina", "españa", "spain",
    "bogota", "santiago", "buenos aires", "ciudad de mexico",
]

TARGET_INDUSTRIES = [
    "dental", "clinica", "medico", "salud", "health",
    "spa", "masaje", "belleza", "salon", "estetica",
    "restaurant", "hotel", "hospedaje", "turismo",
    "retail", "tienda", "comercio",
    "logistic", "transporte", "almacen",
    "constructora", "inmobiliaria", "arquitectura",
    "legal", "abogado", "notaria",
    "contabilidad", "contador", "auditoria",
    "educacion", "colegio", "academia", "instituto",
    "manufactura", "fabrica", "industria",
    "consultora", "agencia",
]

DIGITAL_GAP_SIGNALS = [
    "wordpress", "wix", "blogspot", "jimdo",        # legacy CMS
    "sin presencia", "sin web", "no tiene web",     # explicit gap
    "whatsapp", "celular", "llamar",                # only phone contact
    "tradicional", "artesanal", "familiar",         # traditional business
]

POSITIVE_SIGNALS = [
    "tecnologia", "digital", "software", "sistema",
    "automatizar", "modernizar", "crecer", "expandir",
]


def score_company(
    company: Dict[str, Any],
    weights: Dict[str, int] | None = None,
    icp_config: Dict[str, Any] | None = None,
) -> Tuple[int, List[str], str]:
    """
    Returns (score 0-100, signals_detected, tier A/B/C/rejected).
    """
    w = weights or (icp_config or {}).get("scoring_weights") or DEFAULT_WEIGHTS
    score = 0
    signals: List[str] = []

    name = (company.get("name") or "").lower()
    desc = (company.get("description") or "").lower()
    location = (company.get("location") or "").lower()
    website = company.get("website") or company.get("link") or ""
    text = f"{name} {desc} {location}"

    # ── Geo (15 pts) ────────────────────────────────────────────────────────
    geo_pts = w.get("geo", 15)
    target_geos = (icp_config or {}).get("target_geos") or LATAM_GEOS
    if any(g in text for g in target_geos):
        score += geo_pts
        matched = next(g for g in target_geos if g in text)
        signals.append(f"geo:{matched}")

    # ── Industry (25 pts) ───────────────────────────────────────────────────
    ind_pts = w.get("industry", 25)
    target_inds = (icp_config or {}).get("target_industries") or TARGET_INDUSTRIES
    for ind in target_inds:
        if ind in text:
            score += ind_pts
            signals.append(f"industry:{ind}")
            break

    # ── Has website (10 pts) ────────────────────────────────────────────────
    if website and website.startswith("http"):
        score += w.get("has_website", 10)
        signals.append("has_website")

    # ── Digital gap signals (30 pts, up to 3 × 10) ─────────────────────────
    gap_pts = w.get("digital_gap", 30) // 3
    gap_count = 0
    for sig in DIGITAL_GAP_SIGNALS:
        if sig in text and gap_count < 3:
            score += gap_pts
            signals.append(f"gap:{sig}")
            gap_count += 1

    # ── Description quality signals (20 pts) ────────────────────────────────
    desc_pts = w.get("description", 20)
    if len(desc) > 80:
        score += desc_pts // 2
        signals.append("rich_description")
    if any(s in text for s in POSITIVE_SIGNALS):
        score += desc_pts // 2
        signals.append("digital_interest")

    score = min(score, 100)

    # ── Tier ────────────────────────────────────────────────────────────────
    if score >= 60:
        tier = "A"
    elif score >= 35:
        tier = "B"
    elif score >= 20:
        tier = "C"
    else:
        tier = "rejected"

    return score, signals, tier
