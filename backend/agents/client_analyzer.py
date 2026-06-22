"""
Phase 2 — Deep analysis of a single business (on-demand).

Models:
  - gpt-5.4-mini  → analysis + recommendations + pitch
  - gpt-4.1-nano  → quick extraction from raw text

Scraping sources:
  1. Website: home + contact/about/team subpages
  2. JSON-LD / Schema.org structured data
  3. Páginas Amarillas PE
  4. DDG: ONE combined people search (rate-limit aware)
  5. Playwright: sync API in thread (Windows-compatible fix)

Special handling:
  - goo.gl/maps and Google Maps URLs: resolve redirect → find real website
"""
import asyncio
import json
import random
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from openai import OpenAI

from backend.database import get_collection, settings

try:
    from ddgs import DDGS
    DDG_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        DDG_AVAILABLE = True
    except Exception:
        DDG_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

openai = OpenAI(api_key=settings.openai_api_key)

MODEL_ANALYSIS = "gpt-4.1-mini"
MODEL_EXTRACT  = "gpt-4.1-nano"

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
}

CONTACT_PATHS = [
    "/contacto", "/contactos", "/contact", "/contact-us",
    "/nosotros", "/about", "/about-us", "/quienes-somos",
    "/equipo", "/team", "/staff", "/profesionales",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s\-.]?)?(?:\(?\d{1,4}\)?[\s\-.]?)?\d{2,4}[\s\-.]?\d{2,4}[\s\-.]?\d{2,4}(?!\d)"
)
EMAIL_BLOCK = (
    "sentry", "wixpress", "example.com", "domain.com", "test.com",
    "noreply", "no-reply", "donotreply", "postmaster", "abuse@",
    "your-email", "youremail", "mailer-daemon", "@2x", ".png", ".jpg",
)
SOCIAL_DOMAINS = (
    "instagram.com", "facebook.com", "linkedin.com",
    "twitter.com", "x.com", "tiktok.com", "youtube.com",
)
TECH_FINGERPRINTS: List[tuple] = [
    (r"wp-content|wp-includes|wordpress", "WordPress"),
    (r"cdn\.shopify\.com|shopify\.com/s/", "Shopify"),
    (r"wixsite\.com|wix\.com", "Wix"),
    (r"squarespace\.com", "Squarespace"),
    (r"webflow\.com", "Webflow"),
    (r"joomla", "Joomla"),
    (r"drupal", "Drupal"),
    (r"prestashop", "PrestaShop"),
    (r"magento", "Magento"),
    (r"tiendanube\.com|nuvemshop\.com", "Tiendanube"),
    (r"_next/static|nextjs", "Next.js"),
    (r"__nuxt|nuxtjs", "Nuxt.js"),
    (r"react(?:\.min)?\.js|react-dom", "React"),
    (r"vue(?:\.min)?\.js", "Vue.js"),
    (r"angular(?:\.min)?\.js", "Angular"),
    (r"bootstrap", "Bootstrap"),
    (r"jquery", "jQuery"),
    (r"gtag\(|google-analytics|analytics\.js", "Google Analytics"),
    (r"fbq\(|facebook\.net/en_US/fbevents", "Facebook Pixel"),
    (r"hotjar", "Hotjar"),
    (r"tawk\.to", "Tawk.to Chat"),
    (r"hubspot", "HubSpot"),
]


# ── Playwright helper (sync, runs in thread — Windows compatible) ──────────
def _playwright_fetch_sync(url: str, user_agent: str) -> Optional[str]:
    if not PLAYWRIGHT_AVAILABLE:
        return None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=user_agent, locale="es-PE")
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"[playwright_sync] {url}: {e}")
        return None


class ClientAnalyzerAgent:

    # ── HTTP fetch ─────────────────────────────────────────────────────────
    async def _fetch(self, http: httpx.AsyncClient, url: str) -> Optional[str]:
        try:
            r = await http.get(url)
            if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
                return r.text
        except Exception as e:
            print(f"[fetch] {url}: {e}")
        return None

    async def _fetch_playwright(self, url: str) -> Optional[str]:
        # Run sync playwright in a thread pool (fixes Windows asyncio subprocess issue)
        return await asyncio.to_thread(_playwright_fetch_sync, url, HTTP_HEADERS["User-Agent"])

    # ── Resolve short URLs / Google Maps links ─────────────────────────────
    async def _resolve_url(self, http: httpx.AsyncClient, url: str) -> str:
        """Follow redirects and return the final URL."""
        if not url:
            return url
        try:
            r = await http.head(url, follow_redirects=True)
            return str(r.url)
        except Exception:
            try:
                r = await http.get(url, follow_redirects=True)
                return str(r.url)
            except Exception:
                return url

    async def _find_website_from_maps(self, http: httpx.AsyncClient,
                                      company_name: str, location: str) -> Optional[str]:
        """Search Bing for the company's real website when we only have a Maps link."""
        try:
            q = quote_plus(f"{company_name} {location} sitio web oficial")
            url = f"https://www.bing.com/search?q={q}&count=5&setlang=es"
            resp = await http.get(url, headers={
                **HTTP_HEADERS,
                "Referer": "https://www.bing.com/",
            })
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            for li in soup.select("li.b_algo"):
                a = li.find("h2", {}).find("a") if li.find("h2") else None
                if a and a.get("href"):
                    href = a["href"]
                    domain = urlparse(href).netloc.lower()
                    # Skip search engines and social networks
                    if not any(bad in domain for bad in (
                        "google.", "bing.", "facebook.", "instagram.", "youtube.",
                        "tripadvisor.", "yelp.", "wikipedia."
                    )):
                        return href
        except Exception as e:
            print(f"[find_website_from_maps] {e}")
        return None

    # ── Tech stack ─────────────────────────────────────────────────────────
    def _detect_tech(self, html: str) -> List[str]:
        return sorted({
            label for pat, label in TECH_FINGERPRINTS
            if re.search(pat, html, re.IGNORECASE)
        })

    # ── JSON-LD ────────────────────────────────────────────────────────────
    def _parse_jsonld(self, soup: BeautifulSoup) -> Dict:
        out: Dict = {}
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                raw = tag.string or tag.get_text()
                data = json.loads(raw) if raw else {}
            except Exception:
                continue
            items = data if isinstance(data, list) else [data]
            extras: List = []
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                    extras.extend(item["@graph"])
            for c in items + extras:
                if not isinstance(c, dict):
                    continue
                t = str(c.get("@type", ""))
                if not any(k in t for k in (
                    "Organization", "LocalBusiness", "Store", "Restaurant",
                    "MedicalOrganization", "Dentist", "Clinic", "Corporation",
                    "School", "Hotel", "Gym", "SportsClub", "HealthAndBeautyBusiness",
                )):
                    continue
                out.setdefault("name", c.get("name"))
                out.setdefault("phone", c.get("telephone"))
                out.setdefault("email", c.get("email"))
                out.setdefault("description", c.get("description"))
                employees = c.get("employee") or c.get("employees") or []
                if isinstance(employees, dict):
                    employees = [employees]
                if isinstance(employees, list) and employees:
                    out.setdefault("schema_employees", employees)
                addr = c.get("address")
                if isinstance(addr, dict) and not out.get("address"):
                    parts = [addr.get("streetAddress"), addr.get("addressLocality"),
                             addr.get("addressRegion"), addr.get("addressCountry")]
                    out["address"] = ", ".join(p for p in parts if p)
                elif isinstance(addr, str):
                    out.setdefault("address", addr)
        return out

    # ── Validators ─────────────────────────────────────────────────────────
    def _valid_email(self, e: str) -> bool:
        if not e or "@" not in e or len(e) > 100:
            return False
        return not any(b in e for b in EMAIL_BLOCK)

    def _valid_phone(self, p: str) -> bool:
        return 7 <= len(re.sub(r"\D", "", p)) <= 15

    # ── Contact extraction ─────────────────────────────────────────────────
    def _extract_contacts(self, html: str, base_url: str) -> Dict:
        soup = BeautifulSoup(html, "html.parser")
        jsonld = self._parse_jsonld(soup)

        emails: Set[str] = set()
        phones: Set[str] = set()
        socials: Set[str] = set()
        whatsapp: Optional[str] = None
        maps_link: Optional[str] = None
        raw_people_text = ""

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if href.startswith("mailto:"):
                e = href.replace("mailto:", "").split("?")[0].strip().lower()
                if self._valid_email(e):
                    emails.add(e)
            elif href.startswith("tel:"):
                p = href.replace("tel:", "").strip()
                if self._valid_phone(p):
                    phones.add(p)
            elif "wa.me/" in href or "api.whatsapp.com/send" in href:
                whatsapp = whatsapp or href
            elif any(x in href for x in ("maps.google.com", "goo.gl/maps", "maps.app.goo.gl")):
                maps_link = maps_link or href
            elif href.startswith("http") and any(d in href.lower() for d in SOCIAL_DOMAINS):
                socials.add(href)

        # Detect team/people page content
        page_text_lower = soup.get_text(" ", strip=True).lower()
        team_keywords = ("equipo", "team", "staff", "profesionales", "directorio", "nuestros")
        if any(k in page_text_lower for k in team_keywords):
            raw_people_text = soup.get_text(" ", strip=True)[:5000]

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)

        for m in EMAIL_RE.findall(text):
            if self._valid_email(m.lower()):
                emails.add(m.lower())
        for m in PHONE_RE.findall(text):
            if self._valid_phone(m):
                phones.add(m.strip())
                if len(phones) > 12:
                    break

        if jsonld.get("email") and self._valid_email(jsonld["email"].lower()):
            emails.add(jsonld["email"].lower())
        if jsonld.get("phone") and self._valid_phone(jsonld["phone"]):
            phones.add(jsonld["phone"])

        return {
            "jsonld": jsonld,
            "emails": sorted(emails)[:6],
            "phones": sorted(phones)[:6],
            "socials": sorted(socials)[:8],
            "whatsapp": whatsapp,
            "maps_link": maps_link,
            "raw_people_text": raw_people_text,
        }

    # ── Subpage discovery ──────────────────────────────────────────────────
    def _discover_links(self, html: str, base_url: str) -> List[str]:
        urls: List[str] = []
        base_domain = urlparse(base_url).netloc
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href_lower = a["href"].lower()
                if any(k in href_lower for k in (
                    "contact", "contacto", "nosotros", "about",
                    "equipo", "team", "staff", "quienes",
                )):
                    full = urljoin(base_url, a["href"])
                    if urlparse(full).netloc == base_domain and full not in urls:
                        urls.append(full)
        except Exception:
            pass
        for path in CONTACT_PATHS:
            candidate = urljoin(base_url, path)
            if candidate not in urls:
                urls.append(candidate)
        return urls[:6]

    # ── Páginas Amarillas ──────────────────────────────────────────────────
    async def _search_paginas_amarillas(self, http: httpx.AsyncClient,
                                        name: str, location: str) -> Dict:
        out: Dict = {"phone": None, "address": None}
        try:
            q = quote_plus(f"{name} {location}")
            html = await self._fetch(http, f"https://www.paginasamarillas.com.pe/busqueda/{q}")
            if not html:
                return out
            soup = BeautifulSoup(html, "html.parser")
            card = soup.find(class_=re.compile(r"listing|result|company", re.I)) or soup
            text = card.get_text(" ", strip=True)
            phones = PHONE_RE.findall(text)
            if phones:
                out["phone"] = phones[0].strip()
            addr = card.find(class_=re.compile(r"address|direccion|location", re.I))
            if addr:
                out["address"] = addr.get_text(strip=True)
        except Exception as e:
            print(f"[paginas_amarillas] {e}")
        return out

    # ── DDG people search (ONE call, rate-limit aware) ─────────────────────
    def _ddg_sync(self, query: str, max_results: int = 6) -> List[Dict]:
        if not DDG_AVAILABLE:
            return []
        out = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, region="xl-es", safesearch="off",
                                   max_results=max_results):
                    out.append({"title": r.get("title", ""), "body": r.get("body", ""),
                                "href": r.get("href", "")})
        except Exception as ex:
            print(f"[ddg people] '{query}': {ex}")
        return out

    async def _ddg_people_search(self, company: str, location: str) -> List[Dict]:
        # Single combined query to minimize DDG calls
        query = f'"{company}" {location} gerente director fundador linkedin'
        await asyncio.sleep(random.uniform(4.0, 6.0))  # wait before DDG call
        for attempt in range(2):
            if attempt > 0:
                await asyncio.sleep(4.0)
            res = await asyncio.to_thread(self._ddg_sync, query, 6)
            if res:
                return res
        return []

    # ── People extraction ──────────────────────────────────────────────────
    async def _find_people(self, company_name: str, location: str,
                           raw_people_texts: List[str]) -> List[Dict]:
        chunks: List[str] = [t for t in raw_people_texts if t]

        ddg_results = await self._ddg_people_search(company_name, location)
        if ddg_results:
            chunks.append(
                "BÚSQUEDA WEB:\n" +
                "\n".join(f"{r['title']}: {r['body']} | {r['href']}" for r in ddg_results)
            )

        if not chunks:
            return []

        combined = "\n\n---\n\n".join(chunks)[:6000]
        prompt = (
            f"Empresa: \"{company_name}\" en {location}.\n"
            "Extrae personas reales que trabajan ahí de estos datos:\n\n"
            f"{combined}\n\n"
            "JSON con clave 'people' (array, máx 8 items):\n"
            "{ \"name\": str, \"title\": str, \"linkedin_url\": str|null, "
            "\"email_hint\": str|null, \"confidence\": \"high|medium|low\" }\n"
            "Solo personas con nombre real identificable. "
            "confidence=high si aparece en web oficial, medium si es snippet LinkedIn, low si inferido."
        )
        try:
            resp = openai.chat.completions.create(
                model=MODEL_EXTRACT,
                messages=[
                    {"role": "system", "content": "Extraes personas reales. Solo JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            data = json.loads(resp.choices[0].message.content)
            people = data.get("people") or []
            return [p for p in people if p.get("name") and len(p.get("name", "")) > 3]
        except Exception as e:
            print(f"[find_people] {e}")
            return []

    # ── LLM deep analysis ──────────────────────────────────────────────────
    async def _llm_analyze(self, raw: Dict, user_prompt: str) -> Dict:
        prompt = (
            f"Usuario busca clientes: \"{user_prompt}\"\n\n"
            f"Empresa: \"{raw.get('name', '?')}\"\n"
            f"Datos scrapeados:\n{json.dumps(raw, ensure_ascii=False, default=str)[:9000]}\n\n"
            "Devuelve SOLO JSON:\n"
            "{\n"
            "  \"name\": str,\n"
            "  \"website\": str,\n"
            "  \"address\": str|null,\n"
            "  \"emails\": [str],\n"
            "  \"phones\": [str],\n"
            "  \"whatsapp\": str|null,\n"
            "  \"maps_link\": str|null,\n"
            "  \"social\": {\"instagram\":null,\"facebook\":null,\"linkedin\":null,\"tiktok\":null,\"youtube\":null},\n"
            "  \"tech_stack\": [str],\n"
            "  \"has_ssl\": bool,\n"
            "  \"digital_presence_score\": int 0-100,\n"
            "  \"digital_presence_summary\": str,\n"
            "  \"tech_recommendations\": [{\"title\":str,\"why\":str,\"impact\":\"Alto|Medio|Bajo\",\"effort\":\"Alto|Medio|Bajo\"}],\n"
            "  \"pitch_summary\": str\n"
            "}\n\n"
            "Reglas:\n"
            "- NO inventes contactos. Solo los que están en los datos.\n"
            "- 5-7 tech_recommendations específicas basadas en lo que falta/está obsoleto.\n"
            "- Scoring: -15 sin SSL, -10 por cada red social faltante, -20 web antigua (WordPress <2020/Wix), "
            "-15 sin email visible, -10 sin Analytics.\n"
            "- pitch_summary: menciona algo CONCRETO y específico de su situación actual."
        )
        try:
            resp = openai.chat.completions.create(
                model=MODEL_ANALYSIS,
                messages=[
                    {"role": "system", "content": "Analista digital experto. Solo JSON válido."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            print(f"[llm_analyze] {e}")
            return {
                "name": raw.get("name"), "website": raw.get("website"),
                "emails": raw.get("emails", []), "phones": raw.get("phones", []),
                "tech_stack": raw.get("tech_stack", []), "has_ssl": raw.get("has_ssl", False),
                "digital_presence_summary": "No se pudo analizar.",
                "tech_recommendations": [], "pitch_summary": "",
            }

    # ── Main entry point ───────────────────────────────────────────────────
    async def analyze(self, candidate: Dict, user_prompt: str, user_email: str,
                      session_id: str = "") -> Dict:
        company_name = candidate.get("name", "")
        location = candidate.get("location", "Lima, Perú")
        raw_url = (candidate.get("website") or candidate.get("link") or "").strip()

        all_emails: Set[str] = set()
        all_phones: Set[str] = set()
        all_socials: Set[str] = set()
        whatsapp: Optional[str] = None
        maps_link: Optional[str] = None
        jsonld_data: Dict = {}
        tech_stack: List[str] = []
        raw_people_texts: List[str] = []
        final_url = ""

        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True,
                                     headers=HTTP_HEADERS) as http:

            # ── Resolve URL (handle goo.gl/maps and redirects) ─────────────
            if raw_url:
                is_maps = any(x in raw_url for x in ("goo.gl/maps", "maps.google.com",
                                                      "maps.app.goo.gl", "google.com/maps"))
                if is_maps:
                    print(f"[analyze] Maps URL detected, searching for real website of '{company_name}'")
                    maps_link = raw_url
                    found = await self._find_website_from_maps(http, company_name, location)
                    final_url = found or ""
                else:
                    resolved = await self._resolve_url(http, raw_url)
                    final_url = resolved if not any(
                        x in resolved for x in ("google.com", "goo.gl")
                    ) else ""

            if final_url and not final_url.startswith("http"):
                final_url = "https://" + final_url

            has_ssl = final_url.startswith("https://") if final_url else False
            print(f"[analyze] '{company_name}' → {final_url or '(no website)'}")

            # ── Source 1: Website deep scrape ──────────────────────────────
            if final_url:
                home_html = await self._fetch(http, final_url)
                # Playwright fallback for JS-heavy sites (Windows-safe: sync in thread)
                if not home_html or len(home_html) < 500:
                    home_html = await self._fetch_playwright(final_url)

                if home_html:
                    tech_stack = self._detect_tech(home_html)
                    c0 = self._extract_contacts(home_html, final_url)
                    all_emails.update(c0["emails"])
                    all_phones.update(c0["phones"])
                    all_socials.update(c0["socials"])
                    whatsapp = c0["whatsapp"]
                    maps_link = maps_link or c0["maps_link"]
                    jsonld_data = c0["jsonld"]
                    if c0["raw_people_text"]:
                        raw_people_texts.append(c0["raw_people_text"])

                    sub_urls = self._discover_links(home_html, final_url)
                    sub_htmls = await asyncio.gather(
                        *[self._fetch(http, u) for u in sub_urls],
                        return_exceptions=True,
                    )
                    for sub in sub_htmls:
                        if isinstance(sub, Exception) or not sub:
                            continue
                        cx = self._extract_contacts(sub, final_url)
                        all_emails.update(cx["emails"])
                        all_phones.update(cx["phones"])
                        all_socials.update(cx["socials"])
                        whatsapp = whatsapp or cx["whatsapp"]
                        maps_link = maps_link or cx["maps_link"]
                        if not jsonld_data:
                            jsonld_data = cx["jsonld"]
                        if cx["raw_people_text"]:
                            raw_people_texts.append(cx["raw_people_text"])

            # ── Source 2: Páginas Amarillas ────────────────────────────────
            pa = await self._search_paginas_amarillas(http, company_name, location)
            if pa.get("phone"):
                all_phones.add(pa["phone"])

        # ── Source 3: People finder (DDG, rate-limit aware) ────────────────
        people = await self._find_people(company_name, location, raw_people_texts)

        # ── Assemble raw for LLM ───────────────────────────────────────────
        raw = {
            "name": company_name,
            "website": final_url or raw_url or "#",
            "location": location or jsonld_data.get("address"),
            "description": candidate.get("description") or jsonld_data.get("description"),
            "emails": sorted(all_emails)[:6],
            "phones": sorted(all_phones)[:6],
            "whatsapp": whatsapp,
            "maps_link": maps_link,
            "socials": sorted(all_socials)[:8],
            "tech_stack": tech_stack,
            "has_ssl": has_ssl,
            "jsonld_address": jsonld_data.get("address"),
        }

        analysis = await self._llm_analyze(raw, user_prompt)

        doc = {
            "user_email": user_email,
            "session_id": session_id,
            "search_prompt": user_prompt,
            "name": analysis.get("name") or company_name or "Sin nombre",
            "website": analysis.get("website") or final_url or raw_url or "#",
            "location": analysis.get("address") or location or "",
            "description": candidate.get("description", ""),
            "emails": analysis.get("emails") or [],
            "phones": analysis.get("phones") or [],
            "whatsapp": analysis.get("whatsapp"),
            "maps_link": analysis.get("maps_link") or maps_link,
            "social": analysis.get("social") or {},
            "tech_stack": analysis.get("tech_stack") or tech_stack,
            "has_ssl": analysis.get("has_ssl", has_ssl),
            "digital_presence_score": analysis.get("digital_presence_score"),
            "digital_presence_summary": analysis.get("digital_presence_summary", ""),
            "tech_recommendations": analysis.get("tech_recommendations") or [],
            "pitch_summary": analysis.get("pitch_summary", ""),
            "people": people,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            col = get_collection("analyzed_clients")
            result = await col.insert_one(doc)
            doc["_id"] = str(result.inserted_id)
        except Exception as e:
            print(f"[analyze] DB error: {e}")

        return doc
