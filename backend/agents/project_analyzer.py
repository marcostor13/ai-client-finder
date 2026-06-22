"""
Project Analyzer — deep analysis of a freelance project listing.
Extracts budget, skills, client info, and generates an application pitch.
"""
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Dict

import httpx
from bs4 import BeautifulSoup
from openai import OpenAI

from backend.database import get_collection, settings

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


class ProjectAnalyzerAgent:

    async def _fetch_page(self, http: httpx.AsyncClient, url: str) -> str:
        try:
            r = await http.get(url, timeout=12.0)
            if r.status_code < 400 and "text/html" in r.headers.get("content-type", ""):
                return r.text[:20000]
        except Exception as e:
            print(f"[project_analyzer fetch] {url}: {e}")
        return ""

    async def analyze(
        self,
        project: Dict,
        user_prompt: str,
        user_email: str,
        session_id: str = "",
    ) -> Dict:
        url = project.get("url", "")
        title = project.get("title", "")
        platform = project.get("platform", "")
        description = project.get("description", "")

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=HEADERS) as http:
            html = await self._fetch_page(http, url)

        page_text = ""
        if html:
            soup = BeautifulSoup(html, "html.parser")
            # Remove scripts/styles
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            page_text = soup.get_text(separator=" ", strip=True)[:8000]

        # Fall back to snippet if page scraping failed
        context_text = page_text if len(page_text) > 100 else description

        system = (
            "You are an expert freelance project evaluator for a senior full-stack developer. "
            "Given a project listing page (or snippet), extract all details and return ONLY valid JSON:\n"
            "- title (string): exact project title\n"
            "- platform (string): platform name\n"
            "- budget_type (string): 'fixed', 'hourly', or 'unknown'\n"
            "- budget_display (string|null): budget as shown (e.g. '$500-$1500' or '$25-$50/hr')\n"
            "- duration (string|null): project duration if mentioned\n"
            "- skills_required (array): all tech skills/tools mentioned\n"
            "- description_summary (string): 2-3 sentence summary of what the client needs\n"
            "- client_location (string|null): client country/location\n"
            "- client_rating (number|null): client rating 0-5 if visible\n"
            "- client_spent (string|null): total spent by client (e.g. '$10k+')\n"
            "- proposals_count (string|null): number of bids/proposals visible\n"
            "- experience_level (string|null): 'entry', 'intermediate', or 'expert'\n"
            "- match_score (number 0-100): quality score for a skilled developer "
            "(higher = better: clear requirements, fair budget, verified client, interesting tech)\n"
            "- match_summary (string): 2-3 sentences on opportunity quality and fit\n"
            "- pitch_suggestion (string): compelling 2-3 sentence proposal opening showing "
            "deep understanding of this specific project's needs\n"
            "- red_flags (array): concerns (vague spec, very low budget, suspicious, etc.)\n"
            "- green_flags (array): positives (verified client, clear requirements, good budget, etc.)"
        )

        user_content = (
            f"Platform: {platform}\n"
            f"URL: {url}\n"
            f"Title: {title}\n"
            f"User search context: {user_prompt}\n\n"
            f"Page content:\n{context_text}"
        )

        try:
            resp = openai.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=1200,
            )
            analysis = json.loads(resp.choices[0].message.content)
        except Exception as e:
            print(f"[project_analyzer] LLM error: {e}")
            analysis = {
                "title": title,
                "platform": platform,
                "budget_type": project.get("budget_type", "unknown"),
                "budget_display": project.get("budget"),
                "skills_required": [],
                "description_summary": description[:300],
                "match_score": 50,
                "match_summary": "No se pudo analizar completamente el proyecto.",
                "pitch_suggestion": "I'm excited about this project and have the relevant skills to deliver it.",
                "red_flags": [],
                "green_flags": [],
            }

        result = {
            "user_email": user_email,
            "session_id": session_id,
            "title": analysis.get("title") or title,
            "platform": analysis.get("platform") or platform,
            "url": url,
            "budget_type": analysis.get("budget_type", "unknown"),
            "budget_display": analysis.get("budget_display") or project.get("budget"),
            "duration": analysis.get("duration"),
            "skills_required": analysis.get("skills_required", []),
            "description_summary": analysis.get("description_summary") or description[:300],
            "client_location": analysis.get("client_location"),
            "client_rating": analysis.get("client_rating"),
            "client_spent": analysis.get("client_spent"),
            "proposals_count": analysis.get("proposals_count"),
            "experience_level": analysis.get("experience_level"),
            "match_score": analysis.get("match_score", 50),
            "match_summary": analysis.get("match_summary", ""),
            "pitch_suggestion": analysis.get("pitch_suggestion", ""),
            "red_flags": analysis.get("red_flags", []),
            "green_flags": analysis.get("green_flags", []),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        inserted = await get_collection("analyzed_projects").insert_one(result)
        result["_id"] = str(inserted.inserted_id)
        return result
