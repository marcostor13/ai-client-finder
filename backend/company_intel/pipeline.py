"""
Company Intel pipeline orchestrator.

resolve → crawl → discover → enrich → rank → analyze, persisting progress to the
`company_intel_jobs` Mongo collection so the frontend can poll a job by id.
"""
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bson import ObjectId

from backend.database import get_collection
from backend.company_intel.models import (CompanyProfile, IntelReport, JobStatus,
                                          Person, ProductService, SocialProfile,
                                          classify_seniority)
from backend.company_intel.sources import sunat, search_discovery, website_crawler
from backend.company_intel.sources import people_enrichment as enrich
from backend.company_intel.analysis import reports

COLLECTION = "company_intel_jobs"


def _domain_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    host = urlparse(url if url.startswith("http") else "https://" + url).netloc.lower()
    return host.replace("www.", "") or None


def _norm_name(name: str) -> str:
    s = name.lower().strip()
    for a, b in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z\s]", "", s)).strip()


def _merge_people(groups: List[List[Person]]) -> List[Person]:
    """Merge people from multiple sources, dedupe by normalized name."""
    by_name: Dict[str, Person] = {}
    for group in groups:
        for p in group:
            key = _norm_name(p.name)
            if not key:
                continue
            if key not in by_name:
                by_name[key] = p.copy(deep=True)
                continue
            cur = by_name[key]
            if p.title and (not cur.title or cur.rank == classify_seniority(None)):
                cur.title = cur.title or p.title
                cur.rank = min(cur.rank, p.rank)
            cur.emails = sorted(set(cur.emails) | set(p.emails))
            cur.phones = sorted(set(cur.phones) | set(p.phones))
            nets = {s.network for s in cur.socials}
            cur.socials += [s for s in p.socials if s.network not in nets]
            cur.sources = sorted(set(cur.sources) | set(p.sources))
            cur.confidence = max(cur.confidence, p.confidence)
    people = list(by_name.values())
    # Rank top→bottom; people with contacts and higher confidence first within a rank.
    people.sort(key=lambda p: (int(p.rank), -len(p.emails), -len(p.phones), -p.confidence))
    return people


async def _update(job_id: str, **fields) -> None:
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    await get_collection(COLLECTION).update_one(
        {"_id": ObjectId(job_id)}, {"$set": fields}
    )


async def run_pipeline(job_id: str, query: str) -> None:
    """Full pipeline. Updates the job doc as it progresses. Never raises."""
    try:
        # 1. Resolve company ────────────────────────────────────────────────
        await _update(job_id, status=JobStatus.RESOLVING, progress=10,
                      message="Resolviendo empresa…")
        looks_like_ruc = sunat.is_ruc(query)
        if looks_like_ruc:
            # Reject a structurally invalid RUC before any web search — buscar por
            # un número con typo es justo lo que devolvía empresas equivocadas.
            if not sunat.validate_ruc(query):
                await _update(job_id, status=JobStatus.FAILED, progress=100,
                              message="RUC inválido",
                              error=(f"El RUC {sunat.clean_ruc(query)} no es válido "
                                     "(dígito verificador incorrecto). Revísalo."))
                return
            company = await sunat.resolve_ruc(query) or CompanyProfile(query=query)
        else:
            company = CompanyProfile(query=query, legal_name=query)

        # Guardia clave: con un RUC, NUNCA continuar con el número desnudo como
        # nombre. Si no se resolvió la razón social, fallar con un mensaje
        # accionable en vez de buscar y crawlear una empresa al azar.
        if looks_like_ruc and not (company.trade_name or company.legal_name):
            await _update(
                job_id, status=JobStatus.FAILED, progress=100,
                message="No se pudo resolver el RUC",
                company=company.dict(),
                error=(f"No se pudo obtener la razón social del RUC "
                       f"{sunat.clean_ruc(query)} de ninguna fuente. Configura "
                       "APIS_NET_PE_TOKEN o DECOLECTA_TOKEN para una resolución "
                       "confiable, o ingresa el nombre de la empresa."))
            return

        name = company.trade_name or company.legal_name or query

        if not company.website:
            company.website = await search_discovery.find_website(name)
            if company.website:
                company.sources.append("ddg:website")
        company.domain = _domain_of(company.website)

        # 2. Crawl website ──────────────────────────────────────────────────
        await _update(job_id, status=JobStatus.CRAWLING, progress=30,
                      message="Crawleando sitio web…",
                      company=company.dict())
        crawl: Dict = {}
        site_people: List[Person] = []
        products: List[ProductService] = []
        if company.website:
            crawl = await website_crawler.crawl_site(company.website)
            company.emails = sorted(set(company.emails) | set(crawl.get("emails", [])))
            company.phones = sorted(set(company.phones) | set(crawl.get("phones", [])))
            existing_nets = {s.network for s in company.socials}
            company.socials += [s for s in crawl.get("socials", [])
                                if s.network not in existing_nets]
            site_people = crawl.get("people", [])
            products = crawl.get("products", [])

        # Discover company socials via search if still missing.
        if not company.socials:
            company.socials = await search_discovery.find_socials(name, company.domain)

        # 3. Discover people (search) ───────────────────────────────────────
        await _update(job_id, status=JobStatus.DISCOVERING, progress=50,
                      message="Descubriendo personas…", company=company.dict())
        search_people = await search_discovery.find_people(name)

        # 4. Enrich contacts (Apollo + Hunter) ──────────────────────────────
        await _update(job_id, status=JobStatus.ENRICHING, progress=70,
                      message="Enriqueciendo contactos…")
        # If website discovery failed, recover the domain from the company name so
        # Apollo and Hunter can still scope to the right company.
        if not company.domain:
            company.domain = await enrich.resolve_company_domain(name)
            if company.domain:
                company.sources.append("apollo:domain")
        apollo_people = await enrich.enrich_via_apollo(company.domain, name)
        hunter = await enrich.enrich_via_hunter(company.domain, name)
        company.emails = sorted(set(company.emails) | set(hunter.get("company_emails", [])))

        people = _merge_people([apollo_people, hunter.get("people", []),
                                site_people, search_people])

        # Infer + verify emails for people still missing one (compliant best-effort).
        if company.domain:
            for p in people[:20]:
                if p.emails:
                    continue
                for guess in enrich.infer_emails(p, company.domain):
                    status = await enrich.verify_email(guess)
                    if status in ("valid", "accept_all"):
                        p.emails.append(guess)
                        p.sources.append(f"inferido:{status}")
                        break

        # 5. Analyze / reports ──────────────────────────────────────────────
        await _update(job_id, status=JobStatus.ANALYZING, progress=88,
                      message="Generando informes…",
                      people=[p.dict() for p in people],
                      products=[pr.dict() for pr in products])
        try:
            report = await reports.generate_report(company, people, products)
        except Exception as e:
            report = IntelReport(weaknesses=f"(No se pudo generar el informe LLM: {e})")

        # 6. Done ───────────────────────────────────────────────────────────
        await _update(job_id, status=JobStatus.DONE, progress=100,
                      message="Completado",
                      company=company.dict(),
                      people=[p.dict() for p in people],
                      products=[pr.dict() for pr in products],
                      report=report.dict())
    except Exception as e:
        await _update(job_id, status=JobStatus.FAILED, progress=100,
                      message="Error", error=str(e))
