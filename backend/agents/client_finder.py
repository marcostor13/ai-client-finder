"""
Phase 1 — Real business listing. ZERO hallucinations.

Sources (in order):
  1. DuckDuckGo HTML endpoint  — html.duckduckgo.com/html/ — no JS, no key, reliable
  2. DuckDuckGo library        — backup with delay to avoid rate limits

Every URL is HEAD-validated before being returned.
LLM is ONLY used for prompt analysis (query generation), never for creating URLs.
"""
import asyncio
import json
import random
import re
from typing import Dict, List, Optional, Set
from urllib.parse import quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup
from openai import OpenAI

from backend.database import settings

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except Exception:
        DDGS = None

openai = OpenAI(api_key=settings.openai_api_key)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
}

SKIP_DOMAINS = frozenset({
    # Social / video
    "wikipedia.org", "youtube.com", "facebook.com", "instagram.com",
    "reddit.com", "quora.com", "twitter.com", "x.com",
    "tiktok.com", "pinterest.com", "linkedin.com",
    # E-commerce aggregators
    "amazon.com", "amazon.com.pe", "mercadolibre.com", "mercadolibre.com.pe",
    "ebay.com", "aliexpress.com", "linio.com.pe", "falabella.com", "ripley.com",
    # Search engines / maps
    "google.com", "goo.gl", "bing.com", "duckduckgo.com", "yahoo.com",
    "maps.google.com", "apple.com",
    # Review / travel aggregators
    "tripadvisor.com", "yelp.com", "foursquare.com", "trustpilot.com",
    "glassdoor.com", "indeed.com", "buscojobs.com", "computrabajo.com",
    # Business directories — Spanish/LatAm
    "paginasamarillas.com.pe", "paginasamarillas.com",
    "cylex.com.pe", "cylex.com",
    "hotfrog.com.pe", "hotfrog.com",
    "empresite.com.pe", "empresite.com",
    "einforma.com", "infobel.com",
    "guialocal.com", "guia.com.pe",
    "buscapaginas.pe", "directorioempresarial.pe",
    "dondeir.pe", "adondevivir.com",
    "peru.com", "rpp.pe",
    "yellowpages.com", "yp.com",
    "manta.com", "chambeadoras.com",
    "kompass.com", "dnb.com", "zoominfo.com",
    "clutch.co", "g2.com", "capterra.com",
    # News / portals
    "elcomercio.pe", "larepublica.pe", "gestion.pe",
    "andina.pe", "peru21.pe", "trome.pe", "correo.pe",
})

# Path patterns that indicate a search/listing page, not a business homepage
_SKIP_PATH_RE = re.compile(
    r"/(search|busqueda|resultados|listing|directorio|categoria|category"
    r"|empresas|negocios|servicios|find|results|s\?|query)[/?]",
    re.IGNORECASE,
)


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _is_usable(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    d = _domain(url)
    if not d:
        return False
    # Block known aggregator/directory domains
    if any(s in d for s in SKIP_DOMAINS):
        return False
    # Block URLs whose path looks like a search/listing page
    parsed = urlparse(url)
    if _SKIP_PATH_RE.search(parsed.path):
        return False
    return True


def _unwrap_ddg_url(href: str) -> str:
    """DDG wraps links in /l/?uddg=ENCODED_URL — extract the real URL."""
    if "uddg=" in href:
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            return unquote(m.group(1))
    return href


class ClientFinderAgent:

    # ── 1. Prompt → queries (gpt-4.1-nano, only role of LLM here) ─────────
    async def analyze_prompt(self, user_prompt: str) -> Dict:
        system = (
            "Eres experto en búsqueda B2B local. Devuelve SOLO JSON con:\n"
            "- business_types (array): tipos de negocio exactos.\n"
            "- locations (array): distritos/ciudades mencionados. "
            "Si no se especifica, inferir la más probable (Lima, Perú por defecto).\n"
            "- search_queries (array, 14 elementos): queries para buscadores que encuentren el SITIO WEB OFICIAL "
            "de empresas individuales (no directorios). Usa términos como 'sitio web', 'página web', 'contacto', "
            "'nosotros', 'quienes somos', 'servicios'. Máx 8 palabras c/u. Varía MUCHO el tipo de negocio, "
            "zona y palabras clave para maximizar cobertura geográfica y semántica. Mezcla distritos distintos, "
            "sinónimos del sector, términos de contacto, y versiones en inglés del sector si aplica. "
            "Los 14 queries deben ser lo más distintos posible entre sí para cubrir más empresas únicas. "
            "Ejemplo para 'spas en Lima': "
            "['spa masajes Miraflores Lima sitio web', 'centro bienestar Lima contacto', "
            "'spa relajacion San Isidro página oficial', 'masajes terapeuticos Lima nosotros', "
            "'wellness center Lima web', 'spa corporal facial Barranco contacto', "
            "'masajes spa Lima norte página', 'centro relajacion Lima este servicios', "
            "'beauty spa Lima quienes somos', 'spa tratamientos Lima sur web', "
            "'masajes Lima servicios página web', 'wellness Lima contacto nosotros', "
            "'spa estética Lima sitio oficial', 'masajes terapeuticos Lima servicios'].\n"
            "- language: 'es'."
        )
        try:
            resp = openai.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=900,
            )
            data = json.loads(resp.choices[0].message.content)
            queries = [q[:70] for q in (data.get("search_queries") or []) if q][:14]
            if not queries:
                queries = [user_prompt[:60]]
            data["search_queries"] = queries
            return data
        except Exception as e:
            print(f"[analyze_prompt] {e}")
            return {
                "business_types": [],
                "locations": ["Lima"],
                "search_queries": [user_prompt[:60]],
                "language": "es",
            }

    # ── 2a. DDG HTML endpoint (primary — no rate-limit issues) ────────────
    async def _ddg_html(self, http: httpx.AsyncClient,
                        query: str, max_results: int = 15) -> List[Dict]:
        results: List[Dict] = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=xl-es"
            resp = await http.get(url, headers=HEADERS)
            if resp.status_code != 200:
                return results

            soup = BeautifulSoup(resp.text, "html.parser")

            for block in soup.select(".result"):
                title_el  = block.select_one(".result__title a, .result__a")
                snip_el   = block.select_one(".result__snippet")
                url_el    = block.select_one(".result__url")

                if not title_el:
                    continue

                raw_href = title_el.get("href", "")
                href = _unwrap_ddg_url(raw_href)

                if not _is_usable(href):
                    continue

                results.append({
                    "name":    title_el.get_text(strip=True),
                    "link":    href,
                    "snippet": snip_el.get_text(strip=True)[:280] if snip_el else "",
                })
                if len(results) >= max_results:
                    break

        except Exception as e:
            print(f"[ddg_html] '{query}': {e}")
        return results

    # ── 2b. Bing HTML endpoint (parallel source) ──────────────────────────
    async def _bing_html(self, http: httpx.AsyncClient,
                         query: str, max_results: int = 15) -> List[Dict]:
        results: List[Dict] = []
        try:
            url = f"https://www.bing.com/search?q={quote_plus(query)}&count=20&setlang=es"
            resp = await http.get(url, headers={**HEADERS, "Accept-Language": "es-ES,es;q=0.9"})
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "html.parser")
            for li in soup.select("li.b_algo"):
                a = li.select_one("h2 a")
                if not a:
                    continue
                href = a.get("href", "")
                if not _is_usable(href):
                    continue
                snip_el = li.select_one(".b_caption p, .b_snippet, p")
                results.append({
                    "name":    a.get_text(strip=True),
                    "link":    href,
                    "snippet": snip_el.get_text(strip=True)[:280] if snip_el else "",
                })
                if len(results) >= max_results:
                    break
        except Exception as e:
            print(f"[bing_html] '{query}': {e}")
        return results

    # ── 2c. DDG library (backup, with delay) ──────────────────────────────
    def _ddg_lib_sync(self, query: str, max_results: int = 10) -> List[Dict]:
        if not DDGS:
            return []
        out: List[Dict] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, region="xl-es", safesearch="off",
                                   max_results=max_results):
                    link = r.get("href", "")
                    if _is_usable(link):
                        out.append({
                            "name":    r.get("title", ""),
                            "link":    link,
                            "snippet": r.get("body", "")[:280],
                        })
        except Exception as ex:
            print(f"[ddg_lib] '{query}': {ex}")
        return out

    async def _ddg_lib(self, query: str) -> List[Dict]:
        await asyncio.sleep(random.uniform(3.0, 5.0))
        for attempt in range(2):
            if attempt > 0:
                await asyncio.sleep(4.0)
            res = await asyncio.to_thread(self._ddg_lib_sync, query, 6)
            if res:
                return res
        return []

    # ── 3. URL validation ──────────────────────────────────────────────────
    async def _validate(self, http: httpx.AsyncClient, url: str) -> bool:
        if not _is_usable(url):
            return False
        try:
            r = await http.head(url, timeout=5.0)
            return _is_usable(str(r.url)) and r.status_code < 400
        except Exception:
            try:
                r = await http.get(url, timeout=5.0)
                return r.status_code < 400
            except Exception:
                return False

    # ── 4. Light scrape (meta tags, enrich name/description) ──────────────
    async def _light_scrape(self, http: httpx.AsyncClient, url: str) -> Dict:
        out: Dict = {"name": None, "description": None}
        if not _is_usable(url):
            return out
        try:
            r = await http.get(url, timeout=8.0)
            if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", ""):
                return out
            soup = BeautifulSoup(r.text, "html.parser")

            og_site  = soup.find("meta", attrs={"property": "og:site_name"})
            og_title = soup.find("meta", attrs={"property": "og:title"})
            title_tag = soup.find("title")
            raw_name = (
                (og_site  and og_site.get("content"))
                or (og_title and og_title.get("content"))
                or (title_tag and title_tag.string)
            )
            if raw_name:
                # Strip common SEO suffixes
                name = re.split(r"\s*[-|–]\s*", raw_name.strip())[0].strip()
                out["name"] = name if len(name) > 2 else raw_name.strip()

            meta_d = soup.find("meta", attrs={"name": "description"})
            og_d   = soup.find("meta", attrs={"property": "og:description"})
            desc = (meta_d and meta_d.get("content")) or (og_d and og_d.get("content"))
            if desc:
                out["description"] = desc.strip()[:280]
        except Exception as e:
            print(f"[light_scrape] {url}: {e}")
        return out

    # ── 5. Orchestrator ────────────────────────────────────────────────────
    async def find_clients(self, user_prompt: str) -> List[Dict]:
        analysis = await self.analyze_prompt(user_prompt)
        queries  = analysis.get("search_queries", [user_prompt[:60]])
        location = (analysis.get("locations") or ["Lima"])[0]
        print(f"[find_clients] queries={queries}")

        seen_domains: Set[str] = set()
        candidates:   List[Dict] = []

        async with httpx.AsyncClient(
            timeout=12.0, follow_redirects=True, headers=HEADERS
        ) as http:

            # Run DDG HTML + Bing HTML in parallel for all queries
            ddg_tasks  = [self._ddg_html(http, q, max_results=20) for q in queries]
            bing_tasks = [self._bing_html(http, q, max_results=15) for q in queries]
            all_batches = await asyncio.gather(*ddg_tasks, *bing_tasks, return_exceptions=True)

            for batch in all_batches:
                if isinstance(batch, Exception) or not batch:
                    continue
                for r in batch:
                    d = _domain(r.get("link", ""))
                    if d and d not in seen_domains:
                        seen_domains.add(d)
                        candidates.append(r)

            # If still < 20, fall back to DDG library
            if len(candidates) < 20:
                print(f"[find_clients] only {len(candidates)} from html, trying DDG lib")
                for q in queries:
                    lib_results = await self._ddg_lib(q)
                    for r in lib_results:
                        d = _domain(r.get("link", ""))
                        if d and d not in seen_domains:
                            seen_domains.add(d)
                            candidates.append(r)
                    if len(candidates) >= 40:
                        break

            print(f"[find_clients] {len(candidates)} raw candidates, validating URLs…")

            # Validate all URLs (remove dead links) — cap at 120 to avoid timeout
            to_validate = candidates[:120]
            flags = await asyncio.gather(
                *[self._validate(http, c.get("link", "")) for c in to_validate],
                return_exceptions=True,
            )
            live = [c for c, ok in zip(to_validate, flags)
                    if not isinstance(ok, Exception) and ok]

            print(f"[find_clients] {len(live)} live URLs")

            # Enrich with meta tags (parallel, up to 80)
            scrapes = await asyncio.gather(
                *[self._light_scrape(http, c.get("link", "")) for c in live[:80]],
                return_exceptions=True,
            )

        # Build results
        results = []
        for i, (cand, scrape) in enumerate(zip(live[:80], scrapes), start=1):
            if isinstance(scrape, Exception):
                scrape = {}
            name = (scrape.get("name") if scrape else None) or cand.get("name") or "Sin nombre"
            results.append({
                "id":          i,
                "name":        name,
                "website":     cand.get("link", ""),
                "location":    location,
                "description": (
                    (scrape.get("description") if scrape else None)
                    or cand.get("snippet", "")
                )[:280],
                "analyzed":    False,
            })

        return results
