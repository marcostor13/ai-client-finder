"""
APScheduler jobs for the outbound pipeline.

Job A — discover_prospects  : daily 08:00 — find companies, score, enrich contact
Job B — draft_emails        : daily 09:00 — generate email drafts
Job C — send_approved       : hourly 10-18h — send approved emails (Phase 3)
"""
import asyncio
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.database import get_collection, settings
from backend.outbound import email_drafter, icp_scorer, prospect_router, suppression

scheduler = AsyncIOScheduler(timezone="America/Lima")
_circuit_failures: dict[str, int] = {}
_CIRCUIT_THRESHOLD = 5


def _trip(service: str) -> None:
    _circuit_failures[service] = _circuit_failures.get(service, 0) + 1
    if _circuit_failures[service] >= _CIRCUIT_THRESHOLD:
        print(f"[circuit_breaker] {service} tripped after {_CIRCUIT_THRESHOLD} failures — pausing")


def _reset(service: str) -> None:
    _circuit_failures[service] = 0


def _is_open(service: str) -> bool:
    return _circuit_failures.get(service, 0) >= _CIRCUIT_THRESHOLD


# ── Job A: discover_prospects ──────────────────────────────────────────────────

async def discover_prospects() -> dict:
    """
    Finds companies via DDG scraper, scores them, enriches with contact.
    Saves Prospect documents to MongoDB.
    Returns summary dict.
    """
    print(f"[job:discover] starting — {datetime.now(timezone.utc).isoformat()}")

    if _is_open("ddg_scraper"):
        print("[job:discover] circuit open for ddg_scraper, skipping")
        return {"status": "skipped", "reason": "circuit_breaker"}

    col = get_collection("outbound_prospects")
    icp_col = get_collection("outbound_icp_config")
    metrics_col = get_collection("outbound_metrics")

    # Load active ICP config
    icp_doc = await icp_col.find_one({"active": True}, sort=[("version", -1)])
    icp_config = (icp_doc or {}).get("config_json", {})

    search_queries: list[str] = icp_config.get("search_queries") or [
        "clínicas dentales Lima sin presencia digital",
        "restaurantes Lima sin página web",
        "spas masajes Lima contacto",
        "empresas retail Lima página web",
    ]

    max_per_day = settings.max_companies_per_day
    discovered = 0
    enriched = 0
    today = date.today().isoformat()

    # Check daily cap
    today_count = await col.count_documents({"discovered_at_date": today})
    if today_count >= max_per_day:
        print(f"[job:discover] daily cap reached ({today_count}/{max_per_day})")
        return {"status": "capped", "discovered": 0}

    remaining = max_per_day - today_count

    for query in search_queries:
        if remaining <= 0:
            break
        try:
            companies = await prospect_router.find_companies(query, max_results=min(remaining, 80))
            _reset("ddg_scraper")
        except Exception as e:
            print(f"[job:discover] scraper error: {e}")
            _trip("ddg_scraper")
            break

        for company in companies:
            website = company.get("website") or company.get("link") or ""
            domain = urlparse(website).netloc.lower().lstrip("www.") if website else ""

            if not domain:
                continue

            # Skip already seen domains
            exists = await col.find_one({"company_domain": domain})
            if exists:
                continue

            # ICP scoring
            score, signals, tier = icp_scorer.score_company(company, icp_config=icp_config)

            if tier == "rejected":
                print(f"[job:discover] rejected {company.get('name')} (score={score})")
                continue

            prospect_doc = {
                "company_name": company.get("name", ""),
                "company_domain": domain,
                "location": company.get("location", ""),
                "description": company.get("description", ""),
                "website": website,
                "icp_score": score,
                "tier": tier,
                "signals_detected": signals,
                "source": "ddg_scraper",
                "status": "discovered",
                "contact_email": None,
                "contact_full_name": None,
                "contact_title": None,
                "contact_linkedin_url": None,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "discovered_at_date": today,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            # Enrich with contact (only for tier A and B to save quota)
            if tier in ("A", "B"):
                try:
                    contact = await prospect_router.find_contact(company.get("name", ""), website)
                    if contact:
                        # Check suppression
                        email = contact.get("contact_email") or ""
                        if email:
                            suppressed, reason = await suppression.is_suppressed(email)
                            if suppressed:
                                contact = {}
                                print(f"[job:discover] {email} suppressed: {reason}")
                        prospect_doc.update(contact)
                        if prospect_doc.get("contact_email"):
                            prospect_doc["status"] = "enriched"
                            enriched += 1
                except Exception as e:
                    print(f"[job:discover] contact enrichment failed for {domain}: {e}")

            await col.insert_one(prospect_doc)
            discovered += 1
            remaining -= 1
            print(f"[job:discover] saved {company.get('name')} tier={tier} score={score}")

    # Update daily metrics
    await metrics_col.update_one(
        {"date": today},
        {"$inc": {"prospects_discovered": discovered}},
        upsert=True,
    )

    summary = {"status": "ok", "discovered": discovered, "enriched": enriched}
    print(f"[job:discover] done — {summary}")
    return summary


# ── Job B: draft_emails ───────────────────────────────────────────────────────

async def draft_emails() -> dict:
    """
    Takes enriched prospects (tier A/B) and generates email drafts via LLM.
    Max settings.max_emails_per_day per day. Skips suppressed contacts.
    """
    print(f"[job:draft] starting — {datetime.now(timezone.utc).isoformat()}")

    if _is_open("llm"):
        print("[job:draft] circuit open for llm, skipping")
        return {"status": "skipped", "reason": "circuit_breaker"}

    col = get_collection("outbound_prospects")
    drafts_col = get_collection("outbound_email_drafts")
    icp_col = get_collection("outbound_icp_config")
    metrics_col = get_collection("outbound_metrics")

    icp_doc = await icp_col.find_one({"active": True}, sort=[("version", -1)])
    icp_config = (icp_doc or {}).get("config_json", {})

    max_per_day = settings.max_emails_per_day
    today = date.today().isoformat()

    today_drafted = await drafts_col.count_documents({"created_at": {"$gte": today}})
    if today_drafted >= max_per_day:
        print(f"[job:draft] daily cap reached ({today_drafted}/{max_per_day})")
        return {"status": "capped", "drafted": 0}

    remaining = max_per_day - today_drafted

    # Include both "enriched" (newly found) and any that have an email but
    # weren't drafted yet (e.g. status stuck at "discovered" due to past bugs).
    prospects = await col.find(
        {
            "status": {"$in": ["enriched", "discovered"]},
            "tier": {"$in": ["A", "B"]},
            "contact_email": {"$nin": [None, ""]},
        }
    ).sort("icp_score", -1).limit(remaining).to_list(remaining)

    drafted = 0
    skipped = 0

    for prospect in prospects:
        email = prospect.get("contact_email", "")
        if email:
            is_sup, reason = await suppression.is_suppressed(email)
            if is_sup:
                print(f"[job:draft] skipping {email}: {reason}")
                skipped += 1
                continue

        try:
            await email_drafter.draft_email(prospect, icp_config)
            _reset("llm")
            drafted += 1
        except Exception as e:
            print(f"[job:draft] LLM error for {prospect.get('company_name')}: {e}")
            _trip("llm")
            if _is_open("llm"):
                break

    await metrics_col.update_one(
        {"date": today},
        {"$inc": {"emails_drafted": drafted}},
        upsert=True,
    )

    summary = {"status": "ok", "drafted": drafted, "skipped": skipped}
    print(f"[job:draft] done — {summary}")
    return summary


# ── Scheduler setup ────────────────────────────────────────────────────────────

def start_scheduler() -> None:
    # Auto-schedule disabled — pipeline runs manually from the UI.
    # To re-enable cron, uncomment the add_job blocks below.
    #
    # scheduler.add_job(discover_prospects, trigger="cron", hour=8, minute=0,
    #     id="discover_prospects", replace_existing=True, misfire_grace_time=3600)
    # scheduler.add_job(draft_emails, trigger="cron", hour=9, minute=0,
    #     id="draft_emails", replace_existing=True, misfire_grace_time=3600)
    scheduler.start()
    print("[scheduler] started — manual mode (no cron jobs registered)")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
