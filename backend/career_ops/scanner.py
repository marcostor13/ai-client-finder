"""
Scanner — builds a dynamic portal list from the user's preferred countries and roles.

Flow:
  1. Load profile (countries + primary_roles)
  2. _build_scan_portals() → generates (platform × role) combinations per country
     + LATAM ATS companies if any LatAm country is selected
     + Global ATS companies (filtered strictly by location later)
  3. Fetch each portal → country/keyword filter → AI evaluate
"""
import asyncio
import json
import re
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from backend.career_ops.evaluator import evaluate_job
from backend.database import get_collection

_TIMEOUT          = 25
_EVAL_CONCURRENCY = 3
MAX_EVALS_PER_RUN = 30
MIN_SCORE_TO_SAVE = 2.0

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}
_JSON_HEADERS = {**_HEADERS, "Accept": "application/json"}


def _is_bot_blocked(html: str) -> bool:
    """Detect Cloudflare / bot-protection challenge pages — these contain no jobs."""
    lower = html[:3000].lower()
    return any(phrase in lower for phrase in [
        "just a moment", "checking your browser", "enable javascript and cookies",
        "cloudflare ray id", "cf-browser-verification", "ddos protection",
        "access denied", "403 forbidden", "robot", "captcha",
    ])


# ── Location signal sets ──────────────────────────────────────────────────────

_GLOBAL_REMOTE_SIGNALS = {
    "anywhere", "worldwide", "global", "distributed", "sin fronteras",
    "todo el mundo", "work from anywhere", "fully remote", "100% remote",
    "remoto global", "remote global",
}
_LATAM_SIGNALS = {
    "latam", "latin america", "latinoamerica", "america latina",
    "south america", "sudamerica", "americas", "latam remote", "remote latam",
}
_GENERIC_REMOTE = {"remote", "remoto", "teletrabajo", "work from home", "wfh", "desde casa"}

_COUNTRY_ALIASES: dict[str, list[str]] = {
    "peru":       ["peru", "pe"],
    "mexico":     ["mexico", "mx", "mejico"],
    "brasil":     ["brasil", "brazil", "br"],
    "argentina":  ["argentina", "ar"],
    "colombia":   ["colombia", "co"],
    "chile":      ["chile", "cl"],
    "ecuador":    ["ecuador", "ec"],
    "bolivia":    ["bolivia", "bo"],
    "uruguay":    ["uruguay", "uy"],
    "paraguay":   ["paraguay", "py"],
    "venezuela":  ["venezuela", "ve"],
    "panama":     ["panama", "pa"],
    "costa rica": ["costa rica", "cr"],
    "espana":     ["espana", "spain", "es"],
    "estados unidos": ["estados unidos", "united states", "usa", "us", "eeuu"],
    "reino unido":    ["reino unido", "united kingdom", "uk", "gb"],
}

_LATAM_COUNTRIES = {
    "peru", "argentina", "mexico", "colombia", "chile", "brasil",
    "uruguay", "ecuador", "bolivia", "paraguay", "venezuela",
    "panama", "costa rica", "guatemala", "honduras",
}

_STOP_WORDS = {
    "de", "el", "la", "en", "y", "a", "the", "of", "and", "in", "for", "to",
    "con", "por", "un", "una", "del", "al", "los", "las", "or", "at", "an",
    "se", "es", "que", "su", "como", "mas", "pero", "sin",
}


# ── Country-specific scraper portal templates ─────────────────────────────────
# Each entry generates one portal per role in primary_roles.
# board_type "computrabajo" / "bumeran" → domain is used in the URL.
# board_type "aptitus" → Peru-only, uses category slug (no role search).

_COUNTRY_SCRAPERS: dict[str, list[dict]] = {
    # indeed_rss = reliable XML feed, no JS needed, aggregates from many local sources
    # computrabajo / bumeran / aptitus = HTML scrapers (may be blocked by Cloudflare)
    "peru": [
        {"board_type": "indeed_rss",   "domain": "pe.indeed.com",        "company_prefix": "Indeed Perú",         "region": "peru"},
        {"board_type": "computrabajo", "domain": "pe.computrabajo.com",  "company_prefix": "Computrabajo Perú",   "region": "peru"},
        {"board_type": "bumeran",      "domain": "bumeran.com.pe",       "company_prefix": "Bumeran Perú",        "region": "peru"},
        {"board_type": "aptitus",      "domain": "aptitus.com",          "company_prefix": "Aptitus",             "region": "peru"},
    ],
    "mexico": [
        {"board_type": "indeed_rss",   "domain": "mx.indeed.com",        "company_prefix": "Indeed México",       "region": "latam"},
        {"board_type": "computrabajo", "domain": "mx.computrabajo.com",  "company_prefix": "Computrabajo México", "region": "latam"},
    ],
    "argentina": [
        {"board_type": "indeed_rss",   "domain": "ar.indeed.com",        "company_prefix": "Indeed Argentina",    "region": "latam"},
        {"board_type": "computrabajo", "domain": "ar.computrabajo.com",  "company_prefix": "Computrabajo Argentina","region": "latam"},
        {"board_type": "bumeran",      "domain": "bumeran.com.ar",       "company_prefix": "Bumeran Argentina",   "region": "latam"},
    ],
    "colombia": [
        {"board_type": "indeed_rss",   "domain": "co.indeed.com",        "company_prefix": "Indeed Colombia",     "region": "latam"},
        {"board_type": "computrabajo", "domain": "co.computrabajo.com",  "company_prefix": "Computrabajo Colombia","region": "latam"},
    ],
    "chile": [
        {"board_type": "indeed_rss",   "domain": "cl.indeed.com",        "company_prefix": "Indeed Chile",        "region": "latam"},
        {"board_type": "computrabajo", "domain": "cl.computrabajo.com",  "company_prefix": "Computrabajo Chile",  "region": "latam"},
    ],
    "ecuador": [
        {"board_type": "computrabajo", "domain": "ec.computrabajo.com",  "company_prefix": "Computrabajo Ecuador","region": "latam"},
    ],
    "bolivia": [
        {"board_type": "computrabajo", "domain": "bo.computrabajo.com",  "company_prefix": "Computrabajo Bolivia","region": "latam"},
    ],
    "venezuela": [
        {"board_type": "computrabajo", "domain": "ve.computrabajo.com",  "company_prefix": "Computrabajo Venezuela","region": "latam"},
    ],
    "panama": [
        {"board_type": "computrabajo", "domain": "pa.computrabajo.com",  "company_prefix": "Computrabajo Panamá", "region": "latam"},
    ],
    "costa rica": [
        {"board_type": "computrabajo", "domain": "cr.computrabajo.com",  "company_prefix": "Computrabajo Costa Rica","region": "latam"},
    ],
}

# LATAM-focused tech companies — included when any LatAm country is selected
_LATAM_ATS_PORTALS = [
    {"company": "Rappi",         "board_type": "lever",      "board_id": "rappi",         "region": "latam", "enabled": True},
    {"company": "Despegar",      "board_type": "lever",      "board_id": "despegar",      "region": "latam", "enabled": True},
    {"company": "dLocal",        "board_type": "lever",      "board_id": "dlocal",        "region": "latam", "enabled": True},
    {"company": "Aleph",         "board_type": "lever",      "board_id": "aleph",         "region": "latam", "enabled": True},
    {"company": "Crehana",       "board_type": "lever",      "board_id": "crehana",       "region": "latam", "enabled": True},
    {"company": "Kavak",         "board_type": "lever",      "board_id": "kavak",         "region": "latam", "enabled": True},
    {"company": "Konfío",        "board_type": "lever",      "board_id": "konfio",        "region": "latam", "enabled": True},
    {"company": "Pomelo",        "board_type": "lever",      "board_id": "pomelo",        "region": "latam", "enabled": True},
    {"company": "Kushki",        "board_type": "lever",      "board_id": "kushki",        "region": "latam", "enabled": True},
    {"company": "Frubana",       "board_type": "lever",      "board_id": "frubana",       "region": "latam", "enabled": True},
    {"company": "Lemon Cash",    "board_type": "lever",      "board_id": "lemoncash",     "region": "latam", "enabled": True},
    {"company": "Mercado Libre", "board_type": "greenhouse", "board_id": "mercadolibre",  "region": "latam", "enabled": True},
    {"company": "Globant",       "board_type": "greenhouse", "board_id": "globant",       "region": "latam", "enabled": True},
    {"company": "NEORIS",        "board_type": "greenhouse", "board_id": "neoris",        "region": "latam", "enabled": True},
    {"company": "Endava",        "board_type": "greenhouse", "board_id": "endava",        "region": "latam", "enabled": True},
    {"company": "Wizeline",      "board_type": "greenhouse", "board_id": "wizeline",      "region": "latam", "enabled": True},
    {"company": "Gorilla Logic", "board_type": "greenhouse", "board_id": "gorillalogic",  "region": "latam", "enabled": True},
    {"company": "CI&T",          "board_type": "greenhouse", "board_id": "ciandt",        "region": "latam", "enabled": True},
    {"company": "10Pearls",      "board_type": "greenhouse", "board_id": "10pearls",      "region": "latam", "enabled": True},
    {"company": "Encora",        "board_type": "greenhouse", "board_id": "encora",        "region": "latam", "enabled": True},
    {"company": "Softtek",       "board_type": "greenhouse", "board_id": "softtek",       "region": "latam", "enabled": True},
    {"company": "Bitso",         "board_type": "ashby",      "board_id": "bitso",         "region": "latam", "enabled": True},
    {"company": "Pomelo (Ashby)","board_type": "ashby",      "board_id": "pomelo",        "region": "latam", "enabled": True},
]

# Global companies — only pass filter when job explicitly says remote/LATAM/country match
_GLOBAL_ATS_PORTALS = [
    {"company": "Notion",           "board_type": "lever",      "board_id": "notion",      "region": "global", "enabled": True},
    {"company": "Vercel",           "board_type": "lever",      "board_id": "vercel",      "region": "global", "enabled": True},
    {"company": "Retool",           "board_type": "lever",      "board_id": "retool",      "region": "global", "enabled": True},
    {"company": "Weights & Biases", "board_type": "lever",      "board_id": "wandb",       "region": "global", "enabled": True},
    {"company": "Replit",           "board_type": "lever",      "board_id": "replit",      "region": "global", "enabled": True},
    {"company": "Hugging Face",     "board_type": "lever",      "board_id": "huggingface", "region": "global", "enabled": True},
    {"company": "Stripe",           "board_type": "greenhouse", "board_id": "stripe",      "region": "global", "enabled": True},
    {"company": "Scale AI",         "board_type": "greenhouse", "board_id": "scaleai",     "region": "global", "enabled": True},
    {"company": "Cognizant",        "board_type": "greenhouse", "board_id": "cognizant",   "region": "global", "enabled": True},
    {"company": "Slalom",           "board_type": "greenhouse", "board_id": "slalom",      "region": "global", "enabled": True},
    {"company": "Linear",           "board_type": "ashby",      "board_id": "linear",      "region": "global", "enabled": True},
]

# Aptitus category mapping (Peru-only, category-based portal)
_APTITUS_CATEGORIES = [
    "tecnologia-de-informacion-y-sistemas",
    "ingenieria-de-sistemas-e-informatica",
]

# English → Spanish role translations for local job boards
# Peruvian platforms list jobs in Spanish, so we search in both languages.
_ROLE_ES: dict[str, str] = {
    "frontend developer":       "desarrollador frontend",
    "front end developer":      "desarrollador frontend",
    "backend developer":        "desarrollador backend",
    "back end developer":       "desarrollador backend",
    "full stack developer":     "desarrollador full stack",
    "fullstack developer":      "desarrollador full stack",
    "software engineer":        "ingeniero de software",
    "software developer":       "desarrollador de software",
    "web developer":            "desarrollador web",
    "react developer":          "desarrollador react",
    "angular developer":        "desarrollador angular",
    "vue developer":            "desarrollador vue",
    "python developer":         "desarrollador python",
    "java developer":           "desarrollador java",
    "node developer":           "desarrollador node",
    "mobile developer":         "desarrollador movil",
    "android developer":        "desarrollador android",
    "ios developer":            "desarrollador ios",
    "data scientist":           "cientifico de datos",
    "data engineer":            "ingeniero de datos",
    "data analyst":             "analista de datos",
    "devops engineer":          "ingeniero devops",
    "cloud engineer":           "ingeniero cloud",
    "machine learning engineer":"ingeniero machine learning",
    "ai engineer":              "ingeniero inteligencia artificial",
    "qa engineer":              "ingeniero qa",
    "ux designer":              "disenador ux",
    "ui designer":              "disenador ui",
    "product manager":          "gerente de producto",
    "project manager":          "gerente de proyectos",
    "tech lead":                "lider tecnico",
    "engineering manager":      "gerente de ingenieria",
    "head of engineering":      "head de ingenieria",
}


def _expand_roles_for_local_search(roles: list[str]) -> list[str]:
    """
    For each role add a Spanish equivalent if one exists.
    Local Peruvian boards (Computrabajo, Bumeran) index jobs in Spanish,
    so searching only in English yields very few results.
    """
    seen = {}
    for role in roles:
        seen[role] = True
        role_lower = role.lower().strip()
        for en_key, es_val in _ROLE_ES.items():
            if en_key in role_lower:
                if es_val not in seen:
                    seen[es_val] = True
                break  # one translation per role

    return list(seen.keys())[:8]  # cap to avoid too many requests


def _build_scan_portals(profile: dict) -> list[dict]:
    """
    Build the list of portals to scan.

    When preferred_countries is configured:
      1. Local scrapers (Indeed RSS / Computrabajo / Bumeran / Aptitus) — primary, country-specific
      2. LATAM ATS portals (Greenhouse/Lever/Ashby of LatAm companies) — secondary/reliable fallback.
         These APIs never have bot-blocking, and LatAm companies regularly hire remotely across LATAM.
         Global ATS portals (US/EU companies) are excluded to avoid noisy foreign results.

    When no countries are configured → full scan: LATAM ATS + Global ATS.
    """
    preferred_countries = profile.get("preferred_countries", [])
    primary_roles       = profile.get("primary_roles", [])
    roles               = primary_roles[:4] if primary_roles else []

    portals: list[dict] = []

    if preferred_countries:
        # ── Primary: local scrapers per country ──────────────────────────────
        for country_raw in preferred_countries:
            country_key = _ascii(country_raw)
            if country_key not in _COUNTRY_SCRAPERS:
                continue

            for scraper in _COUNTRY_SCRAPERS[country_key]:
                board_type = scraper["board_type"]

                if board_type == "aptitus":
                    for cat in _APTITUS_CATEGORIES:
                        portals.append({
                            "company":    f"{scraper['company_prefix']} — TI",
                            "board_type": "aptitus",
                            "board_id":   cat,
                            "domain":     scraper["domain"],
                            "region":     scraper["region"],
                            "enabled":    True,
                        })
                else:
                    search_terms = (
                        _expand_roles_for_local_search(roles) if roles
                        else ["desarrollador", "programador", "software engineer"]
                    )
                    for term in search_terms:
                        portals.append({
                            "company":    f"{scraper['company_prefix']} — {term}",
                            "board_type": board_type,
                            "board_id":   term,
                            "domain":     scraper["domain"],
                            "region":     scraper["region"],
                            "enabled":    True,
                        })

        # ── Secondary: LATAM ATS portals (reliable JSON APIs, no bot-blocking) ─
        # Included whenever any LatAm country is selected. LatAm companies frequently
        # post remote roles open to all of LATAM; location filter handles the rest.
        has_latam = any(_ascii(c) in _LATAM_COUNTRIES for c in preferred_countries)
        if has_latam:
            portals.extend(_LATAM_ATS_PORTALS)
        # Global ATS (Stripe, Vercel, etc.) intentionally excluded when countries
        # are configured — they post US/EU jobs that aren't relevant to Peru.

    else:
        # ── Free-for-all mode: scan everything ───────────────────────────────
        portals.extend(_LATAM_ATS_PORTALS)
        portals.extend(_GLOBAL_ATS_PORTALS)

    return portals


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ascii(text: str) -> str:
    """Lowercase + strip diacritics: 'Perú' → 'peru', 'México' → 'mexico'."""
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


def _is_location_match(job: dict, preferred_countries: list, portal_region: str = "global") -> bool:
    """
    Return True if the job location is compatible with preferred_countries.

    portal_region == "peru"   → local scraper (pe.computrabajo.com, pe.indeed.com, etc.)
                                 These only surface Peru jobs — always accept.
    portal_region == "latam"  → LatAm company ATS (Rappi, Mercado Libre, Globant, etc.)
                                 Accept: empty location, any remote/LATAM signal, explicit country match.
                                 LatAm companies that post "Remote" mean "remote anywhere in LATAM".
    portal_region == "global" → US/EU company ATS — strict filtering; "Remote" here means US/EU.
    """
    if not preferred_countries:
        return True

    raw_loc = (job.get("location") or "").strip()

    # Local scrapers always return country-specific results — trust them entirely
    if portal_region == "peru":
        return True

    # Empty location
    if not raw_loc:
        # LATAM ATS: accept — companies hiring across LatAm often omit country
        # Global ATS: reject — can't verify the job is Peru-accessible
        return portal_region == "latam"

    location = _ascii(raw_loc)

    # "worldwide", "anywhere", "global", "work from anywhere" → always accept
    if any(_ascii(sig) in location for sig in _GLOBAL_REMOTE_SIGNALS):
        return True

    # "latam", "latin america", "americas" → accept for any LatAm preferred country
    if any(_ascii(sig) in location for sig in _LATAM_SIGNALS):
        for country in preferred_countries:
            if _ascii(country) in _LATAM_COUNTRIES:
                return True

    # Generic "remote" / "remoto":
    #   LATAM ATS → accept (Rappi/Globant/Mercado Libre "Remote" = open to Peru)
    #   Global ATS → reject (Stripe/Notion "Remote" = US/EU only)
    if any(_ascii(sig) in location for sig in _GENERIC_REMOTE):
        return portal_region == "latam"

    # Explicit preferred country name or alias match
    for country in preferred_countries:
        norm = _ascii(country)
        if norm in location:
            return True
        for alias in _COUNTRY_ALIASES.get(norm, []):
            if alias in location:
                return True

    return False


def _build_profile_keywords(profile: dict) -> set[str]:
    keywords: set[str] = set()
    sources = profile.get("primary_roles", []) + profile.get("superpowers", [])
    for phrase in sources:
        for word in re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ+#.]+", phrase.lower()):
            if len(word) >= 3 and word not in _STOP_WORDS:
                keywords.add(word)
    return keywords


def _is_relevant(job: dict, keywords: set[str]) -> bool:
    if not keywords:
        return True
    title = job.get("title", "").lower()
    desc  = (job.get("description", "") or "")[:400].lower()
    return any(kw in f"{title} {desc}" for kw in keywords)


# ── Fetchers ──────────────────────────────────────────────────────────────────

async def _fetch_indeed_page(search_term: str, client: httpx.AsyncClient,
                              domain: str = "pe.indeed.com",
                              pw_browser=None) -> list[dict]:
    """
    Fetch Indeed jobs via embedded JSON (window.mosaic.providerData).

    Strategy A (httpx): GET the search page and extract JSON from the page source.
    Strategy B (Playwright fallback): If httpx returns no jobs and pw_browser is
    provided, use a real browser to render the page and extract the same JSON or
    fall back to DOM scraping.
    """
    query       = urllib.parse.quote(search_term)
    is_peru     = domain.startswith("pe.")
    loc_param   = "&l=Lima" if is_peru else ""
    url         = f"https://{domain}/jobs?q={query}{loc_param}&sort=date&fromage=30"
    default_loc = "Lima, Perú" if is_peru else domain.split(".")[0].upper()

    _JSON_PATTERN = re.compile(
        r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\})\s*;',
        re.DOTALL,
    )

    def _parse_indeed_json(raw_html: str) -> list[dict]:
        """Extract job listings from Indeed's embedded JSON blob."""
        m = _JSON_PATTERN.search(raw_html)
        if not m:
            return []
        try:
            data    = json.loads(m.group(1))
            results = (
                data.get("metaData", {})
                    .get("mosaicProviderJobCardsModel", {})
                    .get("results")
                or data.get("results")
                or []
            )
        except (json.JSONDecodeError, AttributeError):
            return []

        jobs = []
        for r in results:
            title   = (r.get("title") or "").strip()
            company = (r.get("company") or "").strip()
            loc     = (r.get("formattedLocation") or default_loc).strip()
            jk      = r.get("jk", "")
            snippet = BeautifulSoup(r.get("snippet") or "", "lxml").get_text(" ", strip=True)[:600]
            job_url = f"https://{domain}/viewjob?jk={jk}" if jk else ""
            if title and job_url:
                jobs.append({
                    "title":        title,
                    "url":          job_url,
                    "location":     loc,
                    "description":  snippet,
                    "company_hint": company,
                })
        return jobs

    # ── Strategy A: plain httpx ───────────────────────────────────────────────
    try:
        r = await client.get(url, timeout=_TIMEOUT, headers=_HEADERS)
        print(f"[scanner] indeed/{domain} HTTP {r.status_code} for '{search_term}'")
        if r.status_code == 200 and not _is_bot_blocked(r.text):
            jobs = _parse_indeed_json(r.text)
            if jobs:
                print(f"[scanner] indeed/{domain}: {len(jobs)} jobs (httpx) for '{search_term}'")
                return jobs
            print(f"[scanner] indeed/{domain}: embedded JSON not found via httpx for '{search_term}'")
    except Exception as e:
        print(f"[scanner] indeed/{domain} httpx error for '{search_term}': {type(e).__name__}: {e}")

    # ── Strategy B: Playwright fallback ──────────────────────────────────────
    if not pw_browser:
        return []

    print(f"[scanner] indeed/{domain}: trying Playwright for '{search_term}'")
    page = None
    try:
        page = await pw_browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        html = await page.content()
        if _is_bot_blocked(html):
            print(f"[scanner] indeed/{domain}: BOT BLOCKED (Playwright) for '{search_term}'")
            return []

        # Try embedded JSON first
        jobs = _parse_indeed_json(html)
        if jobs:
            print(f"[scanner] indeed/{domain}: {len(jobs)} jobs (Playwright/JSON) for '{search_term}'")
            return jobs

        # Fall back to DOM scraping via page.evaluate
        print(f"[scanner] indeed/{domain}: falling back to DOM scraping for '{search_term}'")
        domain_js = json.dumps(domain)
        default_loc_js = json.dumps(default_loc)
        raw_jobs = await page.evaluate(f"""() => {{
            const domainBase = {domain_js};
            const defaultLoc = {default_loc_js};
            const cards = Array.from(document.querySelectorAll('.job_seen_beacon'));
            return cards.slice(0, 40).map(card => {{
                const titleEl = card.querySelector('h2.jobTitle a');
                const compEl  = card.querySelector('.companyName');
                const locEl   = card.querySelector('.companyLocation');
                const title   = titleEl ? titleEl.innerText.trim() : '';
                const href    = titleEl ? titleEl.getAttribute('href') : '';
                const company = compEl  ? compEl.innerText.trim()  : '';
                const loc     = locEl   ? locEl.innerText.trim()   : defaultLoc;
                const url     = href
                    ? (href.startsWith('http') ? href : 'https://' + domainBase + href)
                    : '';
                return {{ title, url, company, location: loc, description: '' }};
            }}).filter(j => j.title && j.url);
        }}""")
        jobs = [
            {
                "title":        j.get("title", ""),
                "url":          j.get("url", ""),
                "location":     j.get("location", default_loc),
                "description":  j.get("description", ""),
                "company_hint": j.get("company", ""),
            }
            for j in (raw_jobs or [])
        ]
        print(f"[scanner] indeed/{domain}: {len(jobs)} jobs (Playwright/DOM) for '{search_term}'")
        return jobs

    except Exception as e:
        print(f"[scanner] indeed/{domain} Playwright error for '{search_term}': {type(e).__name__}: {e}")
        return []
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def _fetch_greenhouse(board_id: str, client: httpx.AsyncClient) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs"
    try:
        r = await client.get(url, timeout=_TIMEOUT, headers=_JSON_HEADERS)
        r.raise_for_status()
        jobs = []
        for j in r.json().get("jobs", []):
            jobs.append({
                "title":       j.get("title", ""),
                "url":         j.get("absolute_url", ""),
                "location":    j.get("location", {}).get("name", ""),
                "description": "",
            })
        print(f"[scanner] greenhouse/{board_id}: {len(jobs)} jobs")
        return jobs
    except Exception as e:
        print(f"[scanner] greenhouse/{board_id} error: {type(e).__name__}: {e}")
        return []


async def _fetch_lever(board_id: str, client: httpx.AsyncClient) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{board_id}"
    try:
        r = await client.get(url, timeout=_TIMEOUT, headers=_JSON_HEADERS,
                             params={"mode": "json", "limit": 500})
        r.raise_for_status()
        data  = r.json()
        items = data if isinstance(data, list) else data.get("data", [])
        jobs  = []
        for j in items:
            jobs.append({
                "title":       j.get("text", ""),
                "url":         j.get("hostedUrl", "") or j.get("applyUrl", ""),
                "location":    (j.get("categories") or {}).get("location", ""),
                "description": j.get("descriptionPlain", "")[:2000],
            })
        print(f"[scanner] lever/{board_id}: {len(jobs)} jobs")
        return jobs
    except Exception as e:
        print(f"[scanner] lever/{board_id} error: {type(e).__name__}: {e}")
        return []


async def _fetch_ashby(board_id: str, client: httpx.AsyncClient) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-public/v1/{board_id}/job-listing"
    try:
        r = await client.get(url, timeout=_TIMEOUT, headers=_JSON_HEADERS)
        r.raise_for_status()
        data  = r.json()
        items = data.get("results", data) if isinstance(data, dict) else data
        jobs  = []
        for j in items:
            jobs.append({
                "title":       j.get("title", ""),
                "url":         j.get("jobPostingUrl", ""),
                "location":    j.get("locationName", ""),
                "description": j.get("descriptionPlain", "")[:2000],
            })
        print(f"[scanner] ashby/{board_id}: {len(jobs)} jobs")
        return jobs
    except Exception as e:
        print(f"[scanner] ashby/{board_id} error: {type(e).__name__}: {e}")
        return []


async def _fetch_computrabajo_httpx(search_term: str, client: httpx.AsyncClient,
                                     domain: str = "pe.computrabajo.com") -> list[dict]:
    """
    Search Computrabajo via plain httpx.
    Tries multiple CSS selector strategies; falls back to any <article> tag.
    Will return 0 results when Cloudflare blocks the request.
    """
    query       = urllib.parse.quote(search_term)
    loc_param   = "&l=Lima" if domain.startswith("pe.") else ""
    url         = f"https://{domain}/ofertas-de-trabajo?q={query}{loc_param}"
    default_loc = "Lima, Perú" if domain.startswith("pe.") else domain.split(".")[0].upper()

    try:
        r = await client.get(url, timeout=_TIMEOUT, headers=_HEADERS)
        print(f"[scanner] computrabajo/{domain} HTTP {r.status_code} for '{search_term}'")
        if r.status_code != 200:
            return []
        if _is_bot_blocked(r.text):
            print(f"[scanner] computrabajo/{domain}: BOT BLOCKED (Cloudflare) for '{search_term}'")
            return []

        soup = BeautifulSoup(r.text, "lxml")
        jobs = []

        # Strategy 1: standard article cards
        cards = soup.select(
            "article.box_offer, article[data-qa='job-card'], "
            "div.bx_offer, article.offerBlock, article[class*='offer']"
        )
        # Strategy 2: any <article> on the page
        if not cards:
            cards = soup.find_all("article")
        # Strategy 3: <li> items inside a job list
        if not cards:
            cards = soup.select("ul.jobsearch-ResultsList li, li[data-jk]")

        print(f"[scanner] computrabajo/{domain}: {len(cards)} cards found for '{search_term}'")

        for card in cards[:40]:
            title_el = card.select_one(
                "h2 a, a.title_offer, a.js-o-link, a[data-qa='job-title'], "
                "h3 a, h2[class*='title'], a[class*='title']"
            )
            if not title_el:
                title_el = card.find(["h2", "h3"])
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title:
                continue

            href = title_el.get("href", "") if title_el.name == "a" else ""
            if not href:
                a = card.find("a", href=True)
                href = a["href"] if a else ""
            if href and not href.startswith("http"):
                href = f"https://{domain}{href}"

            company_el = card.select_one(
                "p.emp, a.emp, span.emp, [class*='company'], [class*='empresa'], "
                "a[data-qa='company-name']"
            )
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.select_one(
                "p.ubic, span.ubic, [class*='location'], [class*='ciudad'], "
                "[class*='ubicacion'], span[data-qa='job-location']"
            )
            location = location_el.get_text(strip=True) if location_el else default_loc

            desc_el = card.select_one("p.bb, p[class*='desc'], [class*='resumen'], [class*='description']")
            desc    = desc_el.get_text(strip=True)[:500] if desc_el else ""

            if title and href:
                jobs.append({
                    "title": title, "url": href,
                    "location": location or default_loc,
                    "description": desc, "company_hint": company,
                })

        print(f"[scanner] computrabajo/{domain}: {len(jobs)} valid jobs (httpx) for '{search_term}'")
        return jobs
    except Exception as e:
        print(f"[scanner] computrabajo/{domain} httpx error for '{search_term}': {type(e).__name__}: {e}")
        return []


async def _fetch_computrabajo_pw(search_term: str, browser,
                                  domain: str = "pe.computrabajo.com") -> list[dict]:
    """
    Search Computrabajo using a Playwright browser to bypass Cloudflare.
    """
    query       = urllib.parse.quote(search_term)
    loc_param   = "&l=Lima" if domain.startswith("pe.") else ""
    url         = f"https://{domain}/ofertas-de-trabajo?q={query}{loc_param}"
    default_loc = "Lima, Perú" if domain.startswith("pe.") else domain.split(".")[0].upper()

    page = None
    try:
        page = await browser.new_page()
        await page.set_extra_http_headers({"Accept-Language": "es-PE,es;q=0.9"})
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        html = await page.content()
        if _is_bot_blocked(html):
            print(f"[scanner] computrabajo/{domain}: BOT BLOCKED (Playwright) for '{search_term}'")
            return []

        domain_js      = json.dumps(domain)
        default_loc_js = json.dumps(default_loc)
        raw_jobs = await page.evaluate(f"""() => {{
            const domain     = {domain_js};
            const defaultLoc = {default_loc_js};
            const cards = Array.from(document.querySelectorAll(
                'article.box_offer, article[data-qa="job-card"], article[class*="offer"]'
            ));
            return cards.slice(0, 40).map(card => {{
                const titleEl = card.querySelector(
                    'h2 a.js-o-link, h2 a, a.title_offer, a[data-qa="job-title"]'
                );
                const compEl  = card.querySelector('.emp, a.emp, [data-qa="company-name"]');
                const locEl   = card.querySelector('.ubic, span.ubic, [data-qa="job-location"]');
                const descEl  = card.querySelector('.bb, p.bb, [class*="desc"]');

                const title   = titleEl ? titleEl.innerText.trim() : '';
                let   href    = titleEl ? (titleEl.getAttribute('href') || '') : '';
                if (href && !href.startsWith('http')) href = 'https://' + domain + href;
                const company = compEl  ? compEl.innerText.trim()   : '';
                const loc     = locEl   ? locEl.innerText.trim()    : defaultLoc;
                const desc    = descEl  ? descEl.innerText.trim().slice(0, 500) : '';
                return {{ title, url: href, company, location: loc, description: desc }};
            }}).filter(j => j.title && j.url);
        }}""")

        jobs = [
            {
                "title":        j.get("title", ""),
                "url":          j.get("url", ""),
                "location":     j.get("location", default_loc),
                "description":  j.get("description", ""),
                "company_hint": j.get("company", ""),
            }
            for j in (raw_jobs or [])
        ]
        print(f"[scanner] computrabajo/{domain}: {len(jobs)} jobs (Playwright) for '{search_term}'")
        return jobs

    except Exception as e:
        print(f"[scanner] computrabajo/{domain} Playwright error for '{search_term}': {type(e).__name__}: {e}")
        return []
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def _fetch_computrabajo(search_term: str, client: httpx.AsyncClient,
                               domain: str = "pe.computrabajo.com",
                               pw_browser=None) -> list[dict]:
    """
    Public API: dispatch to Playwright version when available, otherwise httpx.
    """
    if pw_browser:
        return await _fetch_computrabajo_pw(search_term, pw_browser, domain)
    return await _fetch_computrabajo_httpx(search_term, client, domain)


async def _fetch_bumeran_httpx(search_term: str, client: httpx.AsyncClient,
                                domain: str = "bumeran.com.pe") -> list[dict]:
    """
    Search Bumeran via plain httpx.
    Tries slug URL first, then query-param URL as fallback.
    Will return 0 results when Cloudflare blocks the request.
    """
    slug        = re.sub(r"[^a-zA-Z0-9]+", "-", search_term.lower()).strip("-")
    url_slug    = f"https://www.{domain}/empleos-busqueda-{slug}.html"
    url_query   = f"https://www.{domain}/empleos.html?q={slug.replace('-', '+')}"
    default_loc = "Lima, Perú" if domain.endswith(".pe") else domain

    async def _parse(html: str) -> list[dict]:
        soup  = BeautifulSoup(html, "lxml")
        cards = soup.select(
            "div[class*='avisoContainer'], div[class*='AvisoContainer'], "
            "article[class*='aviso'], div[class*='JobCard'], div[class*='job-card'], "
            "li[class*='aviso']"
        )
        if not cards:
            cards = soup.find_all("article")
        if not cards:
            # generic: any element that contains a job link
            cards = [a.parent for a in soup.select("a[href*='/empleos/']") if a.parent]

        print(f"[scanner] bumeran/{domain}: {len(cards)} cards found for '{search_term}'")
        jobs = []
        for card in cards[:40]:
            title_el = card.select_one(
                "h2 a, h3 a, a[class*='title'], a[class*='Title'], "
                "span[class*='title'], div[class*='title'] a"
            )
            if not title_el:
                title_el = card.find(["h2", "h3"])
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title:
                continue

            href = title_el.get("href", "") if title_el.name == "a" else ""
            if not href:
                a = card.find("a", href=True)
                href = a["href"] if a else ""
            if href and not href.startswith("http"):
                href = f"https://www.{domain}{href}"

            company_el = card.select_one(
                "[class*='company'], [class*='Company'], [class*='empresa'], "
                "[class*='Empresa']"
            )
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.select_one(
                "[class*='location'], [class*='Location'], [class*='ubicacion'], "
                "[class*='ciudad'], [class*='Ciudad']"
            )
            location = location_el.get_text(strip=True) if location_el else default_loc

            desc_el = card.select_one("[class*='desc'], [class*='Desc'], [class*='resumen'], p")
            desc    = desc_el.get_text(strip=True)[:400] if desc_el else ""

            if title and href:
                jobs.append({
                    "title": title, "url": href,
                    "location": location or default_loc,
                    "description": desc, "company_hint": company,
                })
        return jobs

    try:
        r = await client.get(url_slug, timeout=_TIMEOUT, headers=_HEADERS)
        print(f"[scanner] bumeran/{domain} HTTP {r.status_code} for '{search_term}'")
        if r.status_code == 200 and not _is_bot_blocked(r.text):
            jobs = await _parse(r.text)
            if jobs:
                print(f"[scanner] bumeran/{domain}: {len(jobs)} jobs (httpx) for '{search_term}'")
                return jobs
        elif r.status_code == 200:
            print(f"[scanner] bumeran/{domain}: BOT BLOCKED for '{search_term}'")

        # Fallback: query-param URL
        r2 = await client.get(url_query, timeout=_TIMEOUT, headers=_HEADERS)
        if r2.status_code == 200 and not _is_bot_blocked(r2.text):
            jobs = await _parse(r2.text)
            print(f"[scanner] bumeran/{domain} fallback: {len(jobs)} jobs (httpx) for '{search_term}'")
            return jobs

        return []
    except Exception as e:
        print(f"[scanner] bumeran/{domain} httpx error for '{search_term}': {type(e).__name__}: {e}")
        return []


async def _fetch_bumeran_pw(search_term: str, browser,
                             domain: str = "bumeran.com.pe") -> list[dict]:
    """
    Search Bumeran using a Playwright browser to bypass Cloudflare.
    """
    slug        = re.sub(r"[^a-zA-Z0-9]+", "-", search_term.lower()).strip("-")
    url         = f"https://www.{domain}/empleos-busqueda-{slug}.html"
    default_loc = "Lima, Perú" if domain.endswith(".pe") else domain

    page = None
    try:
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        html = await page.content()
        if _is_bot_blocked(html):
            print(f"[scanner] bumeran/{domain}: BOT BLOCKED (Playwright) for '{search_term}'")
            return []

        domain_js      = json.dumps(domain)
        default_loc_js = json.dumps(default_loc)
        raw_jobs = await page.evaluate(f"""() => {{
            const domain     = {domain_js};
            const defaultLoc = {default_loc_js};
            const cards = Array.from(document.querySelectorAll(
                '[class*="avisoContainer"], [class*="AvisoContainer"], ' +
                'article[class*="aviso"], [data-qa="aviso-item"]'
            ));
            return cards.slice(0, 40).map(card => {{
                const titleEl = card.querySelector(
                    '[data-qa="aviso-title"], h2 a, h3 a, [class*="title"] a'
                );
                const compEl  = card.querySelector(
                    '[data-qa="company-link"], [class*="company"], [class*="Company"]'
                );
                const locEl   = card.querySelector(
                    '[data-qa="location"], [class*="location"], [class*="Location"]'
                );
                const descEl  = card.querySelector('[class*="desc"], [class*="resumen"]');

                const title   = titleEl ? titleEl.innerText.trim() : '';
                let   href    = titleEl ? (titleEl.getAttribute('href') || '') : '';
                if (href && !href.startsWith('http')) href = 'https://www.' + domain + href;
                const company = compEl  ? compEl.innerText.trim()   : '';
                const loc     = locEl   ? locEl.innerText.trim()    : defaultLoc;
                const desc    = descEl  ? descEl.innerText.trim().slice(0, 400) : '';
                return {{ title, url: href, company, location: loc, description: desc }};
            }}).filter(j => j.title && j.url);
        }}""")

        jobs = [
            {
                "title":        j.get("title", ""),
                "url":          j.get("url", ""),
                "location":     j.get("location", default_loc),
                "description":  j.get("description", ""),
                "company_hint": j.get("company", ""),
            }
            for j in (raw_jobs or [])
        ]
        print(f"[scanner] bumeran/{domain}: {len(jobs)} jobs (Playwright) for '{search_term}'")
        return jobs

    except Exception as e:
        print(f"[scanner] bumeran/{domain} Playwright error for '{search_term}': {type(e).__name__}: {e}")
        return []
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def _fetch_bumeran(search_term: str, client: httpx.AsyncClient,
                          domain: str = "bumeran.com.pe",
                          pw_browser=None) -> list[dict]:
    """
    Public API: dispatch to Playwright version when available, otherwise httpx.
    """
    if pw_browser:
        return await _fetch_bumeran_pw(search_term, pw_browser, domain)
    return await _fetch_bumeran_httpx(search_term, client, domain)


async def _fetch_aptitus(category_slug: str, client: httpx.AsyncClient,
                          domain: str = "aptitus.com") -> list[dict]:
    """
    Scrape Aptitus Peru (category-based).
    Tries category/city URL and a search URL as fallback.
    """
    url_cat    = f"https://{domain}/empleos/{category_slug}/lima"
    url_search = f"https://{domain}/empleos/buscar?q=tecnologia&r=lima"

    async def _parse(html: str) -> list[dict]:
        soup  = BeautifulSoup(html, "lxml")
        cards = soup.select(
            "div[class*='job-item'], article[class*='job'], div[class*='JobCard'], "
            "li[class*='job'], article[class*='aviso'], div[class*='aviso']"
        )
        if not cards:
            cards = soup.find_all("article")

        print(f"[scanner] aptitus/{category_slug}: {len(cards)} cards found")
        jobs = []
        for card in cards[:40]:
            title_el = card.select_one(
                "h2 a, h3 a, a[class*='title'], a[class*='Title'], a[class*='name']"
            )
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            href = title_el.get("href", "")
            if href and not href.startswith("http"):
                href = f"https://{domain}{href}"

            company_el = card.select_one("[class*='company'], [class*='empresa'], [class*='Company']")
            company    = company_el.get_text(strip=True) if company_el else ""

            location_el = card.select_one("[class*='location'], [class*='ciudad'], [class*='ubic']")
            location    = location_el.get_text(strip=True) if location_el else "Lima, Perú"

            desc_el = card.select_one("[class*='desc'], [class*='resumen'], p")
            desc    = desc_el.get_text(strip=True)[:400] if desc_el else ""

            if title and href:
                jobs.append({
                    "title": title, "url": href,
                    "location": location or "Lima, Perú",
                    "description": desc, "company_hint": company,
                })
        return jobs

    try:
        r = await client.get(url_cat, timeout=_TIMEOUT, headers=_HEADERS)
        print(f"[scanner] aptitus HTTP {r.status_code} for '{category_slug}'")
        if r.status_code == 200:
            jobs = await _parse(r.text)
            if jobs:
                return jobs
        # Fallback
        r2 = await client.get(url_search, timeout=_TIMEOUT, headers=_HEADERS)
        if r2.status_code == 200:
            return await _parse(r2.text)
        return []
    except Exception as e:
        print(f"[scanner] aptitus error for '{category_slug}': {type(e).__name__}: {e}")
        return []


async def _fetch_portal(portal: dict, client: httpx.AsyncClient,
                         pw_browser=None) -> list[dict]:
    board_type = portal["board_type"]
    board_id   = portal["board_id"]
    company    = portal["company"]
    domain     = portal.get("domain", "")

    if board_type == "indeed_rss":
        jobs = await _fetch_indeed_page(board_id, client,
                                        domain=domain or "pe.indeed.com",
                                        pw_browser=pw_browser)
    elif board_type == "greenhouse":
        jobs = await _fetch_greenhouse(board_id, client)
    elif board_type == "lever":
        jobs = await _fetch_lever(board_id, client)
    elif board_type == "ashby":
        jobs = await _fetch_ashby(board_id, client)
    elif board_type == "computrabajo":
        jobs = await _fetch_computrabajo(board_id, client,
                                         domain=domain or "pe.computrabajo.com",
                                         pw_browser=pw_browser)
    elif board_type == "bumeran":
        jobs = await _fetch_bumeran(board_id, client,
                                    domain=domain or "bumeran.com.pe",
                                    pw_browser=pw_browser)
    elif board_type == "aptitus":
        jobs = await _fetch_aptitus(board_id, client, domain=domain or "aptitus.com")
    else:
        return []

    for j in jobs:
        if not j.get("company_name"):
            j["company_name"] = j.pop("company_hint", company) or company

    return jobs


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _is_already_evaluated(url: str, user_email: str) -> bool:
    if not url:
        return True
    doc = await get_collection("career_ops_evaluations").find_one(
        {"job_url": url, "user_email": user_email}
    )
    return doc is not None


async def _evaluate_and_save(job: dict, profile: dict, user_email: str) -> bool:
    try:
        job_text = (
            f"Title: {job['title']}\n"
            f"Company: {job.get('company_name','')}\n"
            f"Location: {job['location']}\n\n"
            f"{job['description']}"
        )
        result = await evaluate_job(
            job_text=job_text,
            profile=profile,
            job_title=job["title"],
            company=job.get("company_name", ""),
        )

        score = result.get("overall_score", 0)
        if score < MIN_SCORE_TO_SAVE:
            print(f"[scanner] skip (score {score:.1f}): {job['title']}")
            return False

        now = datetime.now(timezone.utc).isoformat()
        await get_collection("career_ops_evaluations").insert_one({
            "user_email":       user_email,
            "job_title":        job["title"],
            "company_name":     job.get("company_name", ""),
            "job_url":          job["url"],
            "job_text_snippet": job_text[:500],
            "evaluation":       result,
            "status":           "evaluated",
            "notes":            "",
            "source":           "scanner",
            "evaluated_at":     now,
            "created_at":       now,
        })
        return True
    except Exception as e:
        print(f"[scanner] eval error for {job.get('title')}: {e}")
        return False


# ── Main scan ─────────────────────────────────────────────────────────────────

async def run_scan(user_email: str) -> dict:
    profile_doc = await get_collection("career_ops_config").find_one({"user_email": user_email})
    profile     = profile_doc or {}

    # Build portal list dynamically from profile (countries + roles)
    portals         = _build_scan_portals(profile)
    enabled_portals = [p for p in portals if p.get("enabled", True)]

    keywords            = _build_profile_keywords(profile)
    preferred_countries = profile.get("preferred_countries", [])
    print(
        f"[scanner] {len(enabled_portals)} portals | "
        f"keywords: {keywords or '(none)'} | "
        f"countries: {preferred_countries or '(all)'}"
    )

    # ── Start Playwright browser ──────────────────────────────────────────────
    from playwright.async_api import async_playwright
    pw = pw_browser = None
    try:
        pw = await async_playwright().start()
        pw_browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        print("[scanner] Playwright browser ready")
    except Exception as e:
        print(f"[scanner] Playwright unavailable — falling back to httpx only: {e}")

    found_total     = 0
    evaluated_total = 0
    skipped_total   = 0
    log_lines       = []
    evals_remaining = MAX_EVALS_PER_RUN

    try:
        async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
            for portal in enabled_portals:
                if evals_remaining <= 0:
                    log_lines.append(f"Límite {MAX_EVALS_PER_RUN} evaluaciones alcanzado — portales restantes omitidos")
                    break

                jobs = await _fetch_portal(portal, client, pw_browser)

                # Step 1 — skip already evaluated
                new_jobs = [j for j in jobs if j.get("url") and
                            not await _is_already_evaluated(j["url"], user_email)]

                # Step 2 — country/location filter
                portal_region = portal.get("region", "global")
                country_ok    = [j for j in new_jobs if _is_location_match(j, preferred_countries, portal_region)]
                loc_skipped   = len(new_jobs) - len(country_ok)

                # Step 3 — keyword relevance filter
                relevant_jobs = [j for j in country_ok if _is_relevant(j, keywords)]
                skipped       = len(country_ok) - len(relevant_jobs) + loc_skipped
                skipped_total += skipped

                batch        = relevant_jobs[:evals_remaining]
                found_total += len(batch)

                msg = (
                    f"{portal['company']}: {len(jobs)} total, "
                    f"{len(new_jobs)} nuevas, {skipped} irrelevantes, "
                    f"{len(batch)} a evaluar"
                )
                log_lines.append(msg)
                print(f"[scanner] {msg}")

                sem = asyncio.Semaphore(_EVAL_CONCURRENCY)

                async def eval_with_sem(job, _sem=sem):
                    async with _sem:
                        return await _evaluate_and_save(job, profile, user_email)

                results          = await asyncio.gather(*[eval_with_sem(j) for j in batch])
                count            = sum(results)
                evaluated_total += count
                evals_remaining -= len(batch)

                await asyncio.sleep(0.5)

    finally:
        if pw_browser:
            try:
                await pw_browser.close()
            except Exception:
                pass
        if pw:
            try:
                await pw.stop()
            except Exception:
                pass

    summary = {
        "found":     found_total,
        "evaluated": evaluated_total,
        "skipped":   skipped_total,
        "portals":   len(enabled_portals),
        "log":       log_lines[-20:],
    }
    print(f"[scanner] done — {summary}")
    return summary
