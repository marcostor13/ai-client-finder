"""
People & contact enrichment from compliant providers.

- Apollo.io  — B2B people search by company domain (names, titles, email/phone).
- Hunter.io  — domain search (emails + positions) and email verification.
- Pattern inference — guess emails from name + domain (low confidence, optional verify).

All providers are optional; functions no-op gracefully when keys are missing.
"""
import re
from typing import Dict, List, Optional

import httpx

from backend.database import settings
from backend.company_intel.models import Person, classify_seniority
from backend.company_intel.sources.http import headers

# Titles we prioritize when querying Apollo, top→bottom.
_APOLLO_TITLES = [
    "owner", "founder", "president", "ceo", "chief executive officer", "managing director",
    "cfo", "cto", "coo", "director", "gerente general", "gerente", "director general",
    "head", "manager", "jefe", "subgerente", "coordinator", "coordinador",
]


def _slug(s: str) -> str:
    s = s.lower().strip()
    repl = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for k, v in repl.items():
        s = s.replace(k, v)
    return re.sub(r"[^a-z]", "", s)


async def enrich_via_apollo(domain: Optional[str], company_name: str,
                            per_page: int = 25) -> List[Person]:
    key = settings.apollo_api_key
    if not key or not domain:
        return []
    payload = {
        "api_key": key,
        "page": 1,
        "per_page": per_page,
        "person_titles": _APOLLO_TITLES,
    }
    payload["q_organization_domains"] = domain
    people: List[Person] = []
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(
                "https://api.apollo.io/v1/mixed_people/search",
                json=payload,
                headers={**headers(), "Content-Type": "application/json",
                         "Cache-Control": "no-cache", "X-Api-Key": key},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    for p in data.get("people", []):
        name = " ".join(filter(None, [p.get("first_name"), p.get("last_name")])) or p.get("name")
        if not name:
            continue
        title = p.get("title")
        emails = []
        em = p.get("email")
        if em and "email_not_unlocked" not in em and "@" in em:
            emails.append(em.lower())
        phones = []
        for ph in (p.get("phone_numbers") or []):
            if ph.get("sanitized_number"):
                phones.append(ph["sanitized_number"])
        people.append(Person(
            name=name, title=title, rank=classify_seniority(title),
            emails=emails, phones=phones,
            location=p.get("city"),
            sources=["apollo"], confidence=0.8,
        ))
    return people


async def enrich_via_hunter(domain: Optional[str]) -> Dict:
    """Returns {people: [Person], company_emails: [str]} from Hunter domain search."""
    key = settings.hunter_api_key
    if not key or not domain:
        return {"people": [], "company_emails": []}
    people: List[Person] = []
    company_emails: List[str] = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.hunter.io/v2/domain-search",
                params={"domain": domain, "api_key": key, "limit": 50},
                headers=headers(),
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
    except Exception:
        return {"people": [], "company_emails": []}

    for e in data.get("emails", []):
        addr = e.get("value")
        first, last = e.get("first_name"), e.get("last_name")
        title = e.get("position")
        if first or last:
            name = " ".join(filter(None, [first, last]))
            phones = [e["phone_number"]] if e.get("phone_number") else []
            people.append(Person(
                name=name, title=title, rank=classify_seniority(title),
                emails=[addr.lower()] if addr else [], phones=phones,
                sources=["hunter"],
                confidence=min(1.0, (e.get("confidence") or 50) / 100),
            ))
        elif addr and e.get("type") == "generic":
            company_emails.append(addr.lower())
    return {"people": people, "company_emails": company_emails}


# Common corporate email patterns (best-effort, low confidence).
def infer_emails(person: Person, domain: str) -> List[str]:
    parts = person.name.split()
    if len(parts) < 2 or not domain:
        return []
    first = _slug(parts[0])
    last = _slug(parts[-1])
    if not first or not last:
        return []
    fi, li = first[0], last[0]
    patterns = [
        f"{first}.{last}", f"{first}{last}", f"{fi}{last}", f"{first}_{last}",
        f"{first}", f"{fi}.{last}", f"{first}.{li}",
    ]
    return [f"{p}@{domain}" for p in patterns]


async def verify_email(email: str) -> Optional[str]:
    """Verify an email via Hunter. Returns 'valid'|'accept_all'|'invalid'|None."""
    key = settings.hunter_api_key
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.hunter.io/v2/email-verifier",
                params={"email": email, "api_key": key},
                headers=headers(),
            )
            resp.raise_for_status()
            return resp.json().get("data", {}).get("status")
    except Exception:
        return None
