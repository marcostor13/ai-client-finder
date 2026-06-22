"""
Freelance Project Finder — searches worldwide freelance platforms.
Finds real project/job listings on Upwork, Freelancer, Toptal, Guru, etc.
LLM only used for query generation, never for URL creation.
"""
import asyncio
import json
import random
import re
from typing import Dict, List, Set
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
    "Accept-Language": "en-US,en;q=0.9",
}

FREELANCE_DOMAINS = frozenset({
    "upwork.com", "freelancer.com", "toptal.com", "guru.com",
    "peopleperhour.com", "fiverr.com", "99designs.com",
    "remotive.com", "weworkremotely.com", "remote.co",
    "wellfound.com", "angel.co", "truelancer.com",
    "outsourcely.com", "codeable.io", "gigster.com",
    "topcoder.com", "gun.io", "lemon.io", "arc.dev",
    "contra.com", "solidgigs.com", "flexjobs.com",
    "working-nomads.com", "jobspresso.co", "nodesk.co",
    "remoteleaf.com", "hired.com", "authenticjobs.com",
})

SKIP_ALWAYS = frozenset({
    "google.com", "bing.com", "duckduckgo.com", "yahoo.com",
    "wikipedia.org", "youtube.com", "reddit.com", "quora.com",
    "twitter.com", "x.com", "facebook.com", "instagram.com",
    "pinterest.com", "tiktok.com", "amazon.com",
    "glassdoor.com", "indeed.com", "monster.com",
    "tripadvisor.com", "yelp.com",
})

PLATFORM_NAMES = {
    "upwork.com": "Upwork",
    "freelancer.com": "Freelancer",
    "toptal.com": "Toptal",
    "guru.com": "Guru",
    "peopleperhour.com": "PeoplePerHour",
    "fiverr.com": "Fiverr",
    "99designs.com": "99designs",
    "remotive.com": "Remotive",
    "weworkremotely.com": "We Work Remotely",
    "remote.co": "Remote.co",
    "wellfound.com": "Wellfound",
    "angel.co": "AngelList",
    "lemon.io": "Lemon.io",
    "arc.dev": "Arc.dev",
    "contra.com": "Contra",
    "topcoder.com": "Topcoder",
    "gun.io": "Gun.io",
    "flexjobs.com": "FlexJobs",
    "truelancer.com": "Truelancer",
    "hired.com": "Hired",
    "codeable.io": "Codeable",
    "authenticjobs.com": "Authentic Jobs",
}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _is_freelance_url(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    d = _domain(url)
    if not d:
        return False
    if any(s in d for s in SKIP_ALWAYS):
        return False
    return any(p in d for p in FREELANCE_DOMAINS)


def _detect_platform(url: str) -> str:
    d = _domain(url)
    for domain_key, name in PLATFORM_NAMES.items():
        if domain_key in d:
            return name
    return "Freelance"


def _unwrap_ddg_url(href: str) -> str:
    if "uddg=" in href:
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            return unquote(m.group(1))
    return href


class ProjectFinderAgent:

    async def analyze_prompt(self, user_prompt: str) -> Dict:
        system = (
            "You are an expert at finding freelance development projects worldwide. "
            "Given a description of the type of project or tech stack, return ONLY JSON:\n"
            "- tech_stack (array): technologies/skills mentioned or implied\n"
            "- project_types (array): types of projects (web app, mobile, API, dashboard, etc.)\n"
            "- search_queries (array, 10 elements): queries to find REAL project/job listings "
            "on platforms like Upwork, Freelancer, Toptal, Guru, PeoplePerHour, Remotive. "
            "Include platform names, tech keywords, and project terms. "
            "Mix fixed-price and hourly queries. Include both English and Spanish queries. "
            "Example for 'React dashboard development': "
            "['upwork React dashboard developer fixed price', "
            "'freelancer.com React TypeScript development project', "
            "'hire React developer remote contract 2024', "
            "'peopleperhour React dashboard job', "
            "'weworkremotely React developer remote', "
            "'remotive React developer job opening', "
            "'guru.com React frontend developer contract', "
            "'upwork Node.js React full stack project hourly', "
            "'freelance React developer sistemas web proyecto', "
            "'toptal React engineer remote contract']\n"
            "- language: 'en'"
        )
        try:
            resp = openai.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=700,
            )
            data = json.loads(resp.choices[0].message.content)
            queries = [q[:100] for q in (data.get("search_queries") or []) if q][:10]
            if not queries:
                queries = [f"freelance {user_prompt[:60]} developer project"]
            data["search_queries"] = queries
            return data
        except Exception as e:
            print(f"[project analyze_prompt] {e}")
            return {
                "tech_stack": [],
                "project_types": [],
                "search_queries": [f"freelance {user_prompt[:60]} developer project"],
                "language": "en",
            }

    async def _ddg_html(self, http: httpx.AsyncClient, query: str, max_results: int = 15) -> List[Dict]:
        results: List[Dict] = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=wt-wt"
            resp = await http.get(url, headers=HEADERS)
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "html.parser")
            for block in soup.select(".result"):
                title_el = block.select_one(".result__title a, .result__a")
                snip_el = block.select_one(".result__snippet")
                if not title_el:
                    continue
                raw_href = title_el.get("href", "")
                href = _unwrap_ddg_url(raw_href)
                if not _is_freelance_url(href):
                    continue
                results.append({
                    "title": title_el.get_text(strip=True),
                    "link": href,
                    "snippet": snip_el.get_text(strip=True)[:300] if snip_el else "",
                    "platform": _detect_platform(href),
                })
                if len(results) >= max_results:
                    break
        except Exception as e:
            print(f"[project ddg_html] '{query}': {e}")
        return results

    def _ddg_lib_sync(self, query: str, max_results: int = 10) -> List[Dict]:
        if not DDGS:
            return []
        out: List[Dict] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, region="wt-wt", safesearch="off", max_results=max_results):
                    link = r.get("href", "")
                    if _is_freelance_url(link):
                        out.append({
                            "title": r.get("title", ""),
                            "link": link,
                            "snippet": r.get("body", "")[:300],
                            "platform": _detect_platform(link),
                        })
        except Exception as ex:
            print(f"[project ddg_lib] '{query}': {ex}")
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

    async def _validate(self, http: httpx.AsyncClient, url: str) -> bool:
        if not _is_freelance_url(url):
            return False
        try:
            r = await http.head(url, timeout=5.0)
            # Accept 2xx, 3xx, 401, 403 — only reject server errors (5xx)
            return r.status_code < 500
        except Exception:
            # Trust known platforms even if unreachable at HEAD
            return True

    async def _light_scrape(self, http: httpx.AsyncClient, url: str, snippet: str) -> Dict:
        out = {"title": None, "description": snippet, "budget": None, "budget_type": None}
        try:
            r = await http.get(url, timeout=8.0)
            if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", ""):
                return out
            soup = BeautifulSoup(r.text, "html.parser")

            og_title = soup.find("meta", attrs={"property": "og:title"})
            title_tag = soup.find("title")
            raw_title = (og_title and og_title.get("content")) or (title_tag and title_tag.string)
            if raw_title:
                # Strip platform suffix from title
                cleaned = re.split(r"\s*[-|–|•|·]\s*(?:Upwork|Freelancer|Toptal|Guru|PeoplePerHour|Fiverr|Remotive)", raw_title.strip(), flags=re.IGNORECASE)
                out["title"] = cleaned[0].strip() if cleaned[0].strip() else raw_title.strip()

            og_desc = soup.find("meta", attrs={"property": "og:description"})
            meta_desc = soup.find("meta", attrs={"name": "description"})
            desc = (og_desc and og_desc.get("content")) or (meta_desc and meta_desc.get("content"))
            if desc:
                out["description"] = desc.strip()[:400]

            text = soup.get_text(separator=" ", strip=True)[:3000]
            budget_m = re.search(r'\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*/\s*(?:hr|hour|h))?', text)
            if budget_m:
                out["budget"] = budget_m.group(0).strip()
                out["budget_type"] = "hourly" if re.search(r'/\s*h', budget_m.group(0), re.IGNORECASE) else "fixed"
        except Exception as e:
            print(f"[project light_scrape] {url}: {e}")
        return out

    async def find_projects(self, user_prompt: str) -> List[Dict]:
        analysis = await self.analyze_prompt(user_prompt)
        queries = analysis.get("search_queries", [f"freelance {user_prompt[:60]}"])
        print(f"[find_projects] queries={queries}")

        seen_urls: Set[str] = set()
        candidates: List[Dict] = []

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=HEADERS) as http:

            html_batches = await asyncio.gather(
                *[self._ddg_html(http, q, max_results=15) for q in queries],
                return_exceptions=True,
            )

            for batch in html_batches:
                if isinstance(batch, Exception) or not batch:
                    continue
                for r in batch:
                    link = r.get("link", "")
                    if link and link not in seen_urls:
                        seen_urls.add(link)
                        candidates.append(r)

            if len(candidates) < 10:
                print(f"[find_projects] only {len(candidates)} from html, trying DDG lib")
                for q in queries[:5]:
                    lib_results = await self._ddg_lib(q)
                    for r in lib_results:
                        link = r.get("link", "")
                        if link and link not in seen_urls:
                            seen_urls.add(link)
                            candidates.append(r)
                    if len(candidates) >= 20:
                        break

            print(f"[find_projects] {len(candidates)} candidates, validating…")

            flags = await asyncio.gather(
                *[self._validate(http, c.get("link", "")) for c in candidates],
                return_exceptions=True,
            )
            live = [c for c, ok in zip(candidates, flags)
                    if not isinstance(ok, Exception) and ok]

            print(f"[find_projects] {len(live)} live URLs")

            scrapes = await asyncio.gather(
                *[self._light_scrape(http, c.get("link", ""), c.get("snippet", "")) for c in live[:30]],
                return_exceptions=True,
            )

        results = []
        for i, (cand, scrape) in enumerate(zip(live[:30], scrapes), start=1):
            if isinstance(scrape, Exception):
                scrape = {}
            title = (scrape.get("title") if scrape else None) or cand.get("title") or "Proyecto sin título"
            results.append({
                "id": i,
                "title": title,
                "platform": cand.get("platform", "Freelance"),
                "url": cand.get("link", ""),
                "budget": scrape.get("budget") if scrape else None,
                "budget_type": scrape.get("budget_type") if scrape else None,
                "description": (
                    (scrape.get("description") if scrape else None)
                    or cand.get("snippet", "")
                )[:300],
                "skills": [],
                "analyzed": False,
            })

        return results
