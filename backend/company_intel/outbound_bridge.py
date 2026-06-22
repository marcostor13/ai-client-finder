"""
Bridge: company_intel → outbound.

Turns a discovered Person (with an email) into an outbound prospect and drafts a
personalized cold email via the existing email_drafter, landing it in the approval
queue. Respects the suppression list and de-duplicates prospects by email.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bson import ObjectId

from backend.database import get_collection
from backend.outbound import email_drafter, suppression

PROSPECTS = "outbound_prospects"
ICP = "outbound_icp_config"


def _signals(company: Dict, person: Dict) -> List[str]:
    sig: List[str] = []
    if not company.get("website"):
        sig.append("sin sitio web propio")
    if not company.get("socials"):
        sig.append("sin presencia en redes")
    elif len(company.get("socials") or []) <= 1:
        sig.append("presencia digital limitada")
    if not company.get("emails"):
        sig.append("sin canal de contacto público claro")
    return sig


def _linkedin(person: Dict) -> Optional[str]:
    for s in person.get("socials") or []:
        if s.get("network") == "linkedin":
            return s.get("url")
    return None


async def _active_icp() -> Dict:
    doc = await get_collection(ICP).find_one({"active": True}, sort=[("version", -1)])
    return (doc or {}).get("config_json", {})


async def draft_for_person(company: Dict, person: Dict, report: Optional[Dict] = None) -> Dict:
    """
    Returns {status: 'drafted'|'skipped'|'error', reason?, draft?, prospect_id?}.
    `company` and `person` are plain dicts (as stored in the job document).
    """
    emails = person.get("emails") or []
    if not emails:
        return {"status": "skipped", "reason": "sin email", "name": person.get("name")}
    email = emails[0].lower()

    is_sup, reason = await suppression.is_suppressed(email)
    if is_sup:
        return {"status": "skipped", "reason": f"suprimido ({reason})", "name": person.get("name")}

    domain = company.get("domain") or (urlparse(company.get("website") or "").netloc.replace("www.", "") or "")
    prospects_col = get_collection(PROSPECTS)

    # Dedupe by contact email; reuse existing prospect if present.
    existing = await prospects_col.find_one({"contact_email": email})
    if existing:
        prospect = existing
    else:
        overview = (report or {}).get("company_overview") or ""
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "company_name": company.get("legal_name") or company.get("trade_name") or company.get("query"),
            "company_domain": domain,
            "website": company.get("website"),
            "industry": company.get("industry"),
            "country": company.get("country", "PE"),
            "location": company.get("address"),
            "description": overview[:300],
            "contact_email": email,
            "contact_full_name": person.get("name"),
            "contact_title": person.get("title"),
            "contact_linkedin_url": _linkedin(person),
            "icp_score": int(round((person.get("confidence") or 0.5) * 100)),
            "tier": "B",
            "signals_detected": _signals(company, person),
            "source": "company_intel",
            "status": "discovered",
            "discovered_at": now,
            "created_at": now,
            "updated_at": now,
        }
        res = await prospects_col.insert_one(doc)
        doc["_id"] = res.inserted_id
        prospect = doc

    try:
        icp_config = await _active_icp()
        draft = await email_drafter.draft_email(prospect, icp_config)
    except Exception as e:
        return {"status": "error", "reason": str(e), "name": person.get("name")}

    return {
        "status": "drafted",
        "name": person.get("name"),
        "email": email,
        "prospect_id": str(prospect["_id"]),
        "draft_id": draft.get("_id"),
        "subject": draft.get("subject"),
    }


async def draft_for_job(job: Dict, indices: Optional[List[int]] = None) -> Dict:
    """Draft emails for selected people in a job (default: all with an email)."""
    company = job.get("company") or {}
    people = job.get("people") or []
    report = job.get("report")
    if indices is not None:
        people = [people[i] for i in indices if 0 <= i < len(people)]

    results = []
    for p in people:
        if p.get("emails"):
            results.append(await draft_for_person(company, p, report))

    drafted = [r for r in results if r["status"] == "drafted"]
    return {
        "drafted": len(drafted),
        "skipped": len([r for r in results if r["status"] == "skipped"]),
        "errors": len([r for r in results if r["status"] == "error"]),
        "results": results,
    }
