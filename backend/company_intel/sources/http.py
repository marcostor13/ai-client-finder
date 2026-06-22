"""
Shared HTTP utilities for compliant scraping.

Applies the web-scraping best practices: realistic headers, polite rate limiting,
robots.txt checking, retries with backoff, graceful error handling.
"""
import asyncio
import random
import re
import time
from typing import Dict, List, Optional, Set
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
}

# Minimum seconds between requests to the same host (politeness).
_MIN_DELAY = 1.0
_last_hit: Dict[str, float] = {}
_robots_cache: Dict[str, Optional[robotparser.RobotFileParser]] = {}

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
# Peru / generic phone: optional +51, then 6-12 digits with separators.
PHONE_RE = re.compile(
    r"(?:(?:\+?51)[\s\-.]?)?(?:\(?0?1\)?[\s\-.]?)?(?:9\d{2}[\s\-.]?\d{3}[\s\-.]?\d{3}"
    r"|\d{3}[\s\-.]?\d{4}|\d{2}[\s\-.]?\d{3}[\s\-.]?\d{3})"
)


def headers() -> Dict[str, str]:
    return {"User-Agent": random.choice(USER_AGENTS), **DEFAULT_HEADERS}


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower()


async def _throttle(url: str) -> None:
    host = host_of(url)
    now = time.monotonic()
    last = _last_hit.get(host, 0.0)
    wait = _MIN_DELAY - (now - last)
    if wait > 0:
        await asyncio.sleep(wait + random.uniform(0, 0.4))
    _last_hit[host] = time.monotonic()


async def allowed_by_robots(client: httpx.AsyncClient, url: str) -> bool:
    """Return True if robots.txt allows fetching `url` (fail-open on errors)."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base not in _robots_cache:
        rp = robotparser.RobotFileParser()
        try:
            resp = await client.get(f"{base}/robots.txt", headers=headers(), timeout=8)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                rp = None  # no robots.txt → allow
        except Exception:
            rp = None
        _robots_cache[base] = rp
    rp = _robots_cache[base]
    if rp is None:
        return True
    try:
        return rp.can_fetch(USER_AGENTS[0], url)
    except Exception:
        return True


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    resp = await client.get(url, headers=headers(), timeout=15, follow_redirects=True)
    resp.raise_for_status()
    return resp


async def fetch(client: httpx.AsyncClient, url: str, respect_robots: bool = True) -> Optional[str]:
    """Polite GET → HTML text, or None on failure / disallowed."""
    try:
        if respect_robots and not await allowed_by_robots(client, url):
            return None
        await _throttle(url)
        resp = await _get(client, url)
        ctype = resp.headers.get("content-type", "")
        if "text/html" not in ctype and "text" not in ctype and "xml" not in ctype:
            return None
        return resp.text
    except Exception:
        return None


def extract_emails(text: str) -> List[str]:
    found = {e.lower() for e in EMAIL_RE.findall(text or "")}
    # Drop obvious junk (asset filenames mistaken as emails, etc.)
    bad_ext = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")
    return sorted(e for e in found if not e.endswith(bad_ext))


def extract_phones(text: str) -> List[str]:
    raw = PHONE_RE.findall(text or "")
    out: Set[str] = set()
    for r in raw:
        digits = re.sub(r"\D", "", r)
        if 6 <= len(digits) <= 12:
            out.add(r.strip())
    return sorted(out)
