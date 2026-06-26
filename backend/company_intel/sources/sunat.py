"""
SUNAT RUC resolution (Perú).

Resolution chain (first reliable hit wins), so the razón social is *certain*
even without a paid token:

  1. apis.net.pe v2          — needs APIS_NET_PE_TOKEN
  2. decolecta.com           — needs DECOLECTA_TOKEN (free tier)
  3. public business directories (scraping, no token) — fetches the result page
     and extracts the razón social, so natural-person RUCs (prefix 10) also work.

The RUC is validated with its módulo-11 check digit *before* any network call, so
a mistyped number never reaches the web search (which is what used to return a
random, unrelated company).
"""
import re
from typing import List, Optional
from urllib.parse import urlparse

import httpx

from backend.database import settings
from backend.company_intel.models import CompanyProfile
from backend.company_intel.sources.http import headers, fetch

# RUC = 11 dígitos. Prefijos válidos: 10/15 (persona natural), 16, 17 (no
# domiciliado), 20 (persona jurídica).
RUC_RE = re.compile(r"^(?:10|15|16|17|20)\d{9}$")
_RUC_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def clean_ruc(query: str) -> str:
    return re.sub(r"\D", "", query or "")


def is_ruc(query: str) -> bool:
    """True if the input *looks like* a RUC (11 digits, valid prefix)."""
    return bool(RUC_RE.match(clean_ruc(query)))


def validate_ruc(query: str) -> bool:
    """True only if the input is a structurally valid RUC (prefix + módulo-11).

    Stops mistyped/invalid numbers before they trigger a (wrong) web search.
    """
    ruc = clean_ruc(query)
    if not RUC_RE.match(ruc):
        return False
    total = sum(int(d) * w for d, w in zip(ruc[:10], _RUC_WEIGHTS))
    check = 11 - (total % 11)
    check = {10: 0, 11: 1}.get(check, check)
    return check == int(ruc[10])


async def resolve_ruc(ruc: str) -> Optional[CompanyProfile]:
    """Resolve a RUC to a CompanyProfile, trying each provider until one returns
    a razón social. None if the input is not a valid RUC."""
    ruc = clean_ruc(ruc)
    if not validate_ruc(ruc):
        return None

    for provider in (_via_apis_net_pe, _via_decolecta, _via_directories):
        try:
            profile = await provider(ruc)
        except Exception:
            profile = None
        if profile and (profile.legal_name or profile.trade_name):
            return profile

    # Nothing resolved the name. Return a minimal profile so the pipeline can
    # report the situation clearly instead of searching by the bare number.
    return CompanyProfile(
        query=ruc, ruc=ruc,
        sources=["sunat:no-resuelto (configura APIS_NET_PE_TOKEN o DECOLECTA_TOKEN)"],
    )


# ── Providers ────────────────────────────────────────────────────────────────

async def _via_apis_net_pe(ruc: str) -> Optional[CompanyProfile]:
    token = settings.apis_net_pe_token
    if not token:
        return None
    url = f"https://api.apis.net.pe/v2/sunat/ruc?numero={ruc}"
    h = {**headers(), "Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=h)
        resp.raise_for_status()
        data = resp.json()
    name = data.get("razonSocial") or data.get("nombre")
    if not name:
        return None
    return CompanyProfile(
        query=ruc, ruc=ruc,
        legal_name=name,
        trade_name=data.get("nombreComercial"),
        status=data.get("estado"),
        condition=data.get("condicion"),
        address=_join_address(data),
        sources=["sunat:apis.net.pe"],
    )


async def _via_decolecta(ruc: str) -> Optional[CompanyProfile]:
    token = settings.decolecta_token
    if not token:
        return None
    url = f"https://api.decolecta.com/v1/sunat/ruc?numero={ruc}"
    h = {**headers(), "Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=h)
        resp.raise_for_status()
        data = resp.json()
    name = data.get("razon_social") or data.get("nombre_o_razon_social") or data.get("razonSocial")
    if not name:
        return None
    return CompanyProfile(
        query=ruc, ruc=ruc,
        legal_name=name,
        trade_name=data.get("nombre_comercial"),
        status=data.get("estado"),
        condition=data.get("condicion"),
        address=data.get("direccion") or _join_address(data),
        sources=["sunat:decolecta"],
    )


# Directorios públicos que exponen la razón social junto al RUC.
_DIRECTORY_HOSTS = ("universidadperu", "datosperu", "infoempresa", "deperu",
                    "peru-info", "ruc.com.pe", "comprasperu", "convoca",
                    "datospe", "perulista", "ruc.pe")
_LEGAL_SUFFIX_RE = re.compile(
    r"\b(S\.?A\.?C\.?|S\.?A\.?A\.?|S\.?A\.?|E\.?I\.?R\.?L\.?|S\.?R\.?L\.?|S\.?C\.?R\.?L\.?)\b",
    re.I)
# Etiqueta "Razón Social" / "razon_social" en HTML o JSON de un directorio.
_RAZON_LABEL_RE = re.compile(r"raz[oó]n[\s_]*social", re.I)


def _clean_name(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip(" ,-–|:\"").strip()


def _razon_social_from_page(html: str) -> Optional[str]:
    """Extract the razón social from a directory page (HTML *or* JSON),
    tolerating the label and value being in separate cells/keys."""
    m = _RAZON_LABEL_RE.search(html or "")
    if not m:
        return None
    window = html[m.end(): m.end() + 400]
    text = re.sub(r"<[^>]+>", "  ", window)     # tags → límite de celda
    text = re.sub(r'[\"|,{}]', "  ", text)      # delimitadores → límite
    text = re.sub(r"^[\s:>=\-]+", "", text)     # separadores iniciales
    chunk = re.split(r"\s{2,}", text, 1)[0]     # primer "campo"
    chunk = re.split(r"\bruc\b", chunk, flags=re.I)[0]   # cortar "… RUC 20…"
    return _clean_name(chunk)


def _is_plausible_name(name: str, ruc: str) -> bool:
    if not name or ruc in name:
        return False
    words = name.split()
    if not (1 <= len(words) <= 14):
        return False
    # Persona jurídica → sufijo societario; persona natural (10/15) → 2-6 palabras.
    if ruc[:2] == "20":
        return bool(_LEGAL_SUFFIX_RE.search(name))
    return 2 <= len(words) <= 6


async def _via_directories(ruc: str) -> Optional[CompanyProfile]:
    """Scrape public directories. Fetches the result page (not just the snippet)
    and extracts the razón social — covers natural persons too."""
    # Import local para evitar dependencia circular en import-time.
    from backend.company_intel.sources import search_discovery as sd

    results: List[dict] = []
    for q in (f'"{ruc}"', f'RUC {ruc} razón social', f'{ruc} razón social'):
        results += await sd.ddg_search(q, 8)
        if results:
            break

    candidates = [r for r in results
                  if any(h in urlparse(r["url"]).netloc.lower() for h in _DIRECTORY_HOSTS)]

    # 1) Intentar con el título del snippet (rápido).
    for r in candidates:
        head = re.split(r"\b(?:ruc|r\.u\.c)\b|[|–-]", r["title"], flags=re.I)[0]
        name = _clean_name(head)
        if _is_plausible_name(name, ruc):
            return CompanyProfile(query=ruc, ruc=ruc, legal_name=name,
                                  website=None, sources=["sunat:directorio"])

    # 2) Bajar la página del primer directorio y extraer "Razón Social: …".
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for r in candidates[:3]:
            html = await fetch(client, r["url"])
            if not html:
                continue
            name = _razon_social_from_page(html)
            if name and _is_plausible_name(name, ruc):
                return CompanyProfile(query=ruc, ruc=ruc, legal_name=name,
                                      sources=["sunat:directorio"])
    return None


def _join_address(data: dict) -> Optional[str]:
    parts = [data.get("direccion"), data.get("distrito"), data.get("provincia"),
             data.get("departamento")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None
