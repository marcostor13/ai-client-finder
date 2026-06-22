"""
Company website crawler.

Crawls a bounded set of high-signal pages (home, about, team, contact, products)
and extracts company emails/phones, team members, and products/services.
httpx + BeautifulSoup; respects robots.txt and rate limits via sources.http.
"""
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from backend.company_intel.models import (Person, ProductService, SocialProfile,
                                          classify_seniority)
from backend.company_intel.sources.http import (extract_emails, extract_phones, fetch,
                                                headers, host_of)
from backend.company_intel.sources.search_discovery import SOCIAL_HOSTS

# Path keywords → page category. Used to find internal links worth crawling.
_PAGE_HINTS = {
    "about": ["nosotros", "about", "quienes-somos", "quienes_somos", "empresa", "conocenos"],
    "team": ["equipo", "team", "directorio", "directores", "gerencia", "nuestra-gente",
             "staff", "personas", "lideres"],
    "contact": ["contacto", "contact", "contactanos", "contactenos"],
    "products": ["productos", "servicios", "products", "services", "soluciones", "catalogo"],
}
_MAX_PAGES = 8
_TITLE_WORDS = ("gerente", "director", "directora", "jefe", "jefa", "ceo", "cto", "cfo",
                "coo", "presidente", "fundador", "founder", "head", "lead", "coordinador",
                "subgerente", "supervisor", "encargado", "analista", "especialista")


def _normalize_base(url: str) -> str:
    p = urlparse(url if url.startswith("http") else "https://" + url)
    return f"{p.scheme}://{p.netloc}"


def _categorize(href: str) -> Optional[str]:
    low = href.lower()
    for cat, kws in _PAGE_HINTS.items():
        if any(k in low for k in kws):
            return cat
    return None


async def crawl_site(website: str) -> Dict:
    """
    Returns {emails, phones, socials, people, products, pages_crawled}.
    """
    base = _normalize_base(website)
    base_host = host_of(base)
    emails: Set[str] = set()
    phones: Set[str] = set()
    socials: Dict[str, SocialProfile] = {}
    people: Dict[str, Person] = {}
    products: Dict[str, ProductService] = {}
    crawled: List[str] = []

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        home = await fetch(client, base)
        to_visit: List[Tuple[str, str]] = [(base, "home")]
        if home:
            soup = BeautifulSoup(home, "html.parser")
            for a in soup.find_all("a", href=True):
                full = urljoin(base, a["href"])
                if host_of(full) != base_host:
                    net = _social_of(full)
                    if net and net not in socials:
                        socials[net] = SocialProfile(network=net, url=full, public=True,
                                                     source="website")
                    continue
                cat = _categorize(a["href"])
                if cat and all(full != u for u, _ in to_visit):
                    to_visit.append((full, cat))

        for url, cat in to_visit[:_MAX_PAGES]:
            html = home if url == base else await fetch(client, url)
            if not html:
                continue
            crawled.append(url)
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ", strip=True)
            for e in extract_emails(html):
                emails.add(e)
            for ph in extract_phones(text):
                phones.add(ph)
            for a in soup.find_all("a", href=True):
                net = _social_of(urljoin(base, a["href"]))
                if net and net not in socials:
                    socials[net] = SocialProfile(network=net, url=urljoin(base, a["href"]),
                                                 public=True, source="website")
            if cat == "team":
                for m in _extract_team(soup):
                    key = m["name"].lower()
                    if key in people:
                        continue
                    socials = []
                    if m.get("linkedin"):
                        socials.append(SocialProfile(network="linkedin", url=m["linkedin"],
                                                     public=True, source="website:team"))
                    people[key] = Person(
                        name=m["name"], title=m.get("title"),
                        rank=classify_seniority(m.get("title")),
                        emails=[m["email"]] if m.get("email") else [],
                        socials=socials,
                        sources=["website:team"], confidence=0.75,
                    )
            if cat == "products":
                for name, desc in _extract_products(soup):
                    if name.lower() not in products:
                        products[name.lower()] = ProductService(
                            name=name, description=desc, source="website:products")

    return {
        "emails": sorted(emails),
        "phones": sorted(phones),
        "socials": list(socials.values()),
        "people": list(people.values()),
        "products": list(products.values()),
        "pages_crawled": crawled,
    }


def _social_of(url: str) -> Optional[str]:
    host = urlparse(url).netloc.lower().replace("www.", "")
    for h, net in SOCIAL_HOSTS.items():
        if host.endswith(h):
            return net
    return None


_TITLE_RE = re.compile("|".join(_TITLE_WORDS), re.I)
_MAILTO_RE = re.compile(r"^mailto:", re.I)
_LINKEDIN_RE = re.compile(r"linkedin\.com/(in|pub)/", re.I)
_CARD_HINT = re.compile(
    r"(member|miembro|integrante|persona|profile|perfil|card|col[-_ ]|item|"
    r"team[-_]|directiv|staff|leader|equipo[-_])", re.I)


def _card_of(h):
    """Smallest ancestor that represents this person's individual card.
    Prefers an ancestor with a card-like class/id; falls back to the first
    ancestor that contains a title keyword; else the immediate parent."""
    title_fallback = None
    node = h
    for _ in range(4):
        node = node.parent
        if node is None:
            break
        attrs = " ".join((node.get("class") or []) + [node.get("id") or ""])
        if _CARD_HINT.search(attrs):
            return node
        if title_fallback is None and node.find(string=_TITLE_RE):
            title_fallback = node
    return title_fallback or h.parent


def _extract_team(soup: BeautifulSoup) -> List[Dict]:
    """
    Name-anchored team extraction. For each heading that looks like a person name,
    find its individual card and pull the title, email (mailto) and LinkedIn from
    WITHIN that card only (so contacts don't bleed between members).
    Returns dicts: {name, title, email, linkedin}.
    """
    out: List[Dict] = []
    seen: Set[str] = set()
    for h in soup.find_all(["h2", "h3", "h4", "h5", "h6", "strong", "b"]):
        name = h.get_text(" ", strip=True)
        if not _is_person_name(name) or name.lower() in seen:
            continue
        card = _card_of(h)
        title = email = linkedin = None
        if card is not None:
            tnode = card.find(string=_TITLE_RE)
            if tnode and tnode.strip().lower() != name.lower() and len(tnode.strip()) <= 80:
                title = tnode.strip()
            a = card.find("a", href=_MAILTO_RE)
            if a and a.get("href"):
                email = a["href"].split(":", 1)[1].split("?")[0].strip().lower()
            a = card.find("a", href=_LINKEDIN_RE)
            if a:
                linkedin = a.get("href")
        seen.add(name.lower())
        out.append({"name": name, "title": title, "email": email, "linkedin": linkedin})
    return out[:50]


def _extract_products(soup: BeautifulSoup) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for h in soup.find_all(["h2", "h3", "h4"]):
        name = h.get_text(" ", strip=True)
        if 3 <= len(name) <= 80 and name.lower() not in seen and not _is_person_name(name):
            seen.add(name.lower())
            sib = h.find_next(["p", "li"])
            desc = sib.get_text(" ", strip=True)[:280] if sib else None
            out.append((name, desc))
    return out[:30]


_NAME_STOPWORDS = {
    "nuestro", "nuestra", "nuestros", "nuestras", "nosotros", "equipo", "mision",
    "misión", "vision", "visión", "valores", "contacto", "servicios", "productos",
    "inicio", "empresa", "sobre", "trabaja", "conoce", "team", "about", "management",
    "board", "staff", "gerencia", "directorio", "historia", "quienes", "somos",
    "politica", "política", "privacidad", "terminos", "términos", "blog", "noticias",
}


def _is_person_name(text: str) -> bool:
    words = text.split()
    if not (2 <= len(words) <= 4):
        return False
    low = [w.lower().strip(".,;:") for w in words]
    if any(w in _NAME_STOPWORDS for w in low):
        return False
    caps = sum(1 for w in words if w[:1].isupper())
    return caps >= 2 and all(len(w) > 1 for w in words)
