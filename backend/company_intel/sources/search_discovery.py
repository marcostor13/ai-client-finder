"""
OSINT discovery via search engines (DuckDuckGo HTML — no API key).

Finds the company website, public social profiles, and people (managers →
employees) from public search snippets. Only public, surfaced-in-search data.
"""
import re
from typing import Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from backend.company_intel.models import (Person, SeniorityRank, SocialProfile,
                                          classify_seniority)
from backend.company_intel.sources.http import headers

DDG_HTML = "https://html.duckduckgo.com/html/"

SOCIAL_HOSTS = {
    "linkedin.com": "linkedin",
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "twitter.com": "x",
    "x.com": "x",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
}


def _unwrap(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href or href.startswith("/l/"):
        q = parse_qs(urlparse(href).query)
        if "uddg" in q:
            return unquote(q["uddg"][0])
    return href


async def ddg_search(query: str, max_results: int = 10) -> List[Dict]:
    """Return [{title, url, snippet}] from DuckDuckGo HTML."""
    out: List[Dict] = []
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.post(DDG_HTML, data={"q": query}, headers=headers())
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for res in soup.select(".result")[: max_results * 2]:
                a = res.select_one(".result__a")
                if not a:
                    continue
                url = _unwrap(a.get("href", ""))
                if not url.startswith("http"):
                    continue
                snip = res.select_one(".result__snippet")
                out.append({
                    "title": a.get_text(" ", strip=True),
                    "url": url,
                    "snippet": snip.get_text(" ", strip=True) if snip else "",
                })
                if len(out) >= max_results:
                    break
    except Exception:
        pass
    return out


def _social_network(url: str) -> Optional[str]:
    host = urlparse(url).netloc.lower().replace("www.", "")
    for h, net in SOCIAL_HOSTS.items():
        if host.endswith(h):
            return net
    return None


async def find_website(company_name: str) -> Optional[str]:
    """Best-effort official website for a company name."""
    results = await ddg_search(f'{company_name} sitio web oficial Perú', 8)
    for r in results:
        net = _social_network(r["url"])
        host = urlparse(r["url"]).netloc.lower()
        skip = ("wikipedia", "facebook", "linkedin", "instagram", "youtube",
                "mercadolibre", "google.", "datospe", "universidadperu", "infoempresa")
        if net or any(s in host for s in skip):
            continue
        return f"{urlparse(r['url']).scheme}://{urlparse(r['url']).netloc}"
    return None


# Directorios públicos de empresas en Perú que exponen la razón social junto al RUC.
_RUC_DIRECTORY_HOSTS = ("universidadperu", "datosperu", "infoempresa", "deperu",
                        "peru-info", "ruc.com.pe", "comprasperu", "convoca")
# Sufijos societarios que confirman que un título contiene una razón social.
_LEGAL_SUFFIX_RE = re.compile(
    r"\b(S\.?A\.?C\.?|S\.?A\.?A\.?|S\.?A\.?|E\.?I\.?R\.?L\.?|S\.?R\.?L\.?|S\.?C\.?R\.?L\.?)\b",
    re.I)


async def find_company_name(ruc: str) -> Optional[str]:
    """Best-effort razón social for a RUC from public business directories.

    Fallback for when SUNAT (apis.net.pe) has no token or fails, so the rest of
    the pipeline searches by company name instead of by the bare RUC number.
    """
    for r in await ddg_search(f'"{ruc}" razón social', 8):
        host = urlparse(r["url"]).netloc.lower()
        if not any(h in host for h in _RUC_DIRECTORY_HOSTS):
            continue
        # El título suele ser "RAZON SOCIAL S.A.C. - RUC 20XXXXXXXXX | sitio".
        head = re.split(r"\b(?:ruc|r\.u\.c)\b|[|–-]", r["title"], flags=re.I)[0].strip()
        if _LEGAL_SUFFIX_RE.search(head) and 3 <= len(head.split()) <= 12:
            return re.sub(r"\s+", " ", head)
    return None


async def find_socials(company_name: str, domain: Optional[str] = None) -> List[SocialProfile]:
    """Discover PUBLIC social profiles of the company."""
    found: Dict[str, SocialProfile] = {}
    queries = [f'{company_name} linkedin', f'{company_name} facebook',
               f'{company_name} instagram']
    for q in queries:
        for r in await ddg_search(q, 6):
            net = _social_network(r["url"])
            if net and net not in found:
                found[net] = SocialProfile(network=net, url=r["url"], public=True,
                                           source="ddg:search")
    return list(found.values())


# Roles to search for, top→bottom.
_ROLE_QUERIES = [
    "gerente general", "director", "gerente", "jefe", "subgerente",
    "coordinador", "líder", "responsable",
]


# Tokens del nombre legal que no ayudan a confirmar pertenencia a la empresa.
_COMPANY_STOPTOKENS = {
    "sa", "sac", "saa", "eirl", "srl", "scrl", "sociedad", "anonima", "anónima",
    "comercial", "empresa", "grupo", "group", "corporacion", "corporación", "del",
    "los", "las", "and", "the", "peru", "perú", "sociedad",
}


def _company_tokens(company_name: str) -> set:
    """Significant lowercase tokens of a company name, sans legal/filler words."""
    toks = re.sub(r"[^a-z0-9\s]", " ", _deburr(company_name).lower()).split()
    return {t for t in toks if len(t) >= 3 and t not in _COMPANY_STOPTOKENS}


def _deburr(s: str) -> str:
    for a, b in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}.items():
        s = s.replace(a, b)
    return s


async def find_people(company_name: str, max_people: int = 25) -> List[Person]:
    """
    Discover people associated with the company from public search snippets,
    including public LinkedIn profile URLs (not logged-in scraping).

    Noise control: a person is only kept when the snippet actually mentions the
    company (token overlap) AND the extracted title maps to a known seniority
    rank — otherwise search results bleed in unrelated people and page fragments.
    """
    people: Dict[str, Person] = {}
    tokens = _company_tokens(company_name)
    for role in _ROLE_QUERIES:
        q = f'"{company_name}" {role}'
        for r in await ddg_search(q, 8):
            net = _social_network(r["url"])
            text = f'{r["title"]} {r["snippet"]}'
            # Require the company to be named in the result, else it's not about them.
            if tokens and not (tokens & _company_tokens(text)):
                continue
            for name, title in _extract_name_title(text, role):
                # Drop matches whose "title" isn't a real role (page fragments, etc.).
                if classify_seniority(title) == SeniorityRank.UNKNOWN:
                    continue
                key = name.lower()
                p = people.get(key) or Person(name=name, title=title,
                                              rank=classify_seniority(title),
                                              confidence=0.45)
                if title and not p.title:
                    p.title = title
                    p.rank = classify_seniority(title)
                if net == "linkedin" and "/in/" in r["url"]:
                    if not any(s.network == "linkedin" for s in p.socials):
                        p.socials.append(SocialProfile(network="linkedin", url=r["url"],
                                                        public=True, source="ddg:search"))
                if "ddg:search" not in p.sources:
                    p.sources.append("ddg:search")
                people[key] = p
            if len(people) >= max_people:
                break
        if len(people) >= max_people:
            break
    return list(people.values())


# Pattern: "Nombre Apellido - Cargo en Empresa" / "Cargo: Nombre Apellido"
_NAME_TITLE_PATTERNS = [
    re.compile(r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})\s*[-–|]\s*"
               r"([^|–\-\n]{3,60})"),
]


def _extract_name_title(text: str, role_hint: str) -> List[tuple]:
    out = []
    for pat in _NAME_TITLE_PATTERNS:
        for m in pat.finditer(text):
            name = m.group(1).strip()
            title = m.group(2).strip()
            # Heuristics: a person name has 2-4 capitalized words, not the company.
            if 2 <= len(name.split()) <= 4 and not _looks_like_company(name):
                out.append((name, title))
    return out[:3]


_NON_PERSON_TOKENS = (
    "s.a", "sac", "s.a.c", "eirl", "srl", "group", "perú", "peru", "corporation",
    "inc", "ltda", "team", "equipo", "management", "board", "directorio", "gerencia",
    "chart", "org chart", "official", "executive team", "staff", "company", "empresa",
    "linkedin", "facebook", "profile", "perfil",
)


def _looks_like_company(name: str) -> bool:
    low = name.lower()
    return any(t in low for t in _NON_PERSON_TOKENS)
