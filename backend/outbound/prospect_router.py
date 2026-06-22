"""
Prospect Router — finds companies and contacts from multiple sources.

Contact priority:
  1. Hunter.io        (25/month free)
  2. Apollo People    (50/month free, fixed endpoint)
  3. Website scraping (free, unlimited — mailto: links on company site)
"""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.database import get_collection, settings
from backend.agents.client_finder import ClientFinderAgent

_DECISION_TITLES = [
    "CEO", "CTO", "COO", "Director", "Gerente", "Head",
    "Fundador", "Founder", "Manager", "Presidente",
]

_SKIP_EMAIL_PREFIXES = {
    "noreply", "no-reply", "notifications", "support", "spam",
    "donotreply", "info", "contact", "hello", "hola", "ventas",
    "admin", "webmaster", "mail", "newsletter", "bounce",
}


# ── Quota tracking ─────────────────────────────────────────────────────────────

async def _monthly_usage(source: str) -> int:
    col = get_collection("outbound_source_usage")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    doc = await col.find_one({"source": source, "month": month})
    return doc["count"] if doc else 0


async def _inc_usage(source: str, amount: int = 1) -> None:
    col = get_collection("outbound_source_usage")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    await col.update_one(
        {"source": source, "month": month},
        {"$inc": {"count": amount}},
        upsert=True,
    )


async def get_quota_summary() -> list[dict]:
    col = get_collection("outbound_source_usage")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    docs = await col.find({"month": month}).to_list(20)
    limits = {"hunter": 25, "apollo": 50, "ddg_scraper": None, "web_scrape": None}
    return [
        {"source": d["source"], "used": d["count"], "limit": limits.get(d["source"], "?")}
        for d in docs
    ]


# ── Company discovery ──────────────────────────────────────────────────────────

async def find_companies(search_query: str, max_results: int = 80) -> list[dict]:
    finder = ClientFinderAgent()
    results = await finder.find_clients(search_query)
    await _inc_usage("ddg_scraper", len(results))
    return results[:max_results]


# ── Contact finding — source 1: Hunter.io ─────────────────────────────────────

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
async def _hunter_domain_search(domain: str) -> dict:
    async with httpx.AsyncClient(timeout=12) as http:
        r = await http.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "domain": domain,
                "api_key": settings.hunter_api_key,
                "limit": 3,
                "type": "personal",
            },
        )
        r.raise_for_status()
        return r.json()


# ── Contact finding — source 2: Apollo People API ─────────────────────────────

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
async def _apollo_people_search(domain: str) -> dict:
    async with httpx.AsyncClient(timeout=12) as http:
        r = await http.post(
            "https://api.apollo.io/api/v1/people/search",   # fixed endpoint
            headers={
                "Content-Type": "application/json",
                "x-api-key": settings.apollo_api_key,
                "Cache-Control": "no-cache",
            },
            json={
                "q_organization_domains_fuzzy_match": domain,
                "page": 1,
                "per_page": 3,
                "person_titles": _DECISION_TITLES,
            },
        )
        if not r.is_success:
            print(f"[apollo] HTTP {r.status_code} for {domain}: {r.text[:200]}")
        r.raise_for_status()
        return r.json()


# ── Contact finding — source 3: Website email scraping (free, unlimited) ──────

async def _scrape_website_emails(website: str) -> str:
    """
    Fetches the company website and extracts the first useful email from
    mailto: links. Falls back to regex search in the page HTML.
    Returns empty string if nothing found.
    """
    if not website:
        return ""
    try:
        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        ) as http:
            r = await http.get(website)
            text = r.text

        # mailto: links first (most reliable)
        mailto_emails = re.findall(
            r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
            text, re.IGNORECASE,
        )
        # Plain email addresses in HTML
        plain_emails = re.findall(
            r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b',
            text,
        )

        # Deduplicate preserving order, mailto first
        seen = set()
        candidates = []
        for e in mailto_emails + plain_emails:
            e_lower = e.lower()
            if e_lower not in seen:
                seen.add(e_lower)
                candidates.append(e)

        domain = urlparse(website).netloc.lower().lstrip("www.")

        # Prefer emails from the company's own domain; skip generic prefixes
        for email in candidates:
            local, host = email.lower().split("@", 1)
            if host != domain:
                continue
            if any(local.startswith(p) for p in _SKIP_EMAIL_PREFIXES):
                continue
            return email

        # Second pass: accept generic prefixes from the company domain
        for email in candidates:
            _, host = email.lower().split("@", 1)
            if host == domain:
                return email

    except Exception as e:
        print(f"[web_scrape] failed for {website}: {type(e).__name__}")

    return ""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return url


# ── Main contact finder ────────────────────────────────────────────────────────

async def find_contact(company_name: str, website: str) -> dict:
    """
    Finds a decision-maker contact for a company.
    Returns dict with contact fields, or {} if nothing found.
    """
    domain = _extract_domain(website)
    if not domain:
        return {}

    # ── 1. Hunter.io ──────────────────────────────────────────────────────────
    if settings.hunter_api_key:
        usage = await _monthly_usage("hunter")
        if usage < 25:
            try:
                data = await _hunter_domain_search(domain)
                emails = (data.get("data") or {}).get("emails") or []
                for e in emails:
                    pos = (e.get("position") or "").lower()
                    if any(t.lower() in pos for t in _DECISION_TITLES):
                        await _inc_usage("hunter")
                        return {
                            "contact_email": e.get("value"),
                            "contact_full_name": f"{e.get('first_name','')} {e.get('last_name','')}".strip(),
                            "contact_title": e.get("position", ""),
                            "contact_linkedin_url": e.get("linkedin", ""),
                            "contact_source": "hunter",
                        }
                if emails:
                    e = emails[0]
                    await _inc_usage("hunter")
                    return {
                        "contact_email": e.get("value"),
                        "contact_full_name": f"{e.get('first_name','')} {e.get('last_name','')}".strip(),
                        "contact_title": e.get("position", ""),
                        "contact_linkedin_url": e.get("linkedin", ""),
                        "contact_source": "hunter",
                    }
            except Exception as e:
                print(f"[prospect_router] hunter failed for {domain}: {e}")

    # ── 2. Apollo People API ──────────────────────────────────────────────────
    if settings.apollo_api_key:
        usage = await _monthly_usage("apollo")
        if usage < 50:
            try:
                data = await _apollo_people_search(domain)
                people = data.get("people") or []
                for p in people:
                    if p.get("email"):
                        await _inc_usage("apollo")
                        return {
                            "contact_email": p.get("email"),
                            "contact_full_name": p.get("name", ""),
                            "contact_title": p.get("title", ""),
                            "contact_linkedin_url": p.get("linkedin_url", ""),
                            "contact_source": "apollo",
                        }
            except Exception as e:
                print(f"[prospect_router] apollo failed for {domain}: {e}")

    # ── 3. Website scraping (free, unlimited) ─────────────────────────────────
    email = await _scrape_website_emails(website)
    if email:
        await _inc_usage("web_scrape")
        print(f"[prospect_router] web_scrape found {email} on {domain}")
        return {
            "contact_email": email,
            "contact_full_name": "",
            "contact_title": "",
            "contact_linkedin_url": "",
            "contact_source": "web_scrape",
        }

    return {}
