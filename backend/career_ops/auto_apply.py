"""
Auto-apply: generates a personalized cover letter with OpenAI,
then submits to Lever via their public API (most LatAm tech companies use Lever).
Greenhouse / Ashby don't expose public apply APIs, so for those
we store the cover letter and return it for the user to paste.
"""
import base64
import re

import httpx
from openai import AsyncOpenAI

from backend.database import get_collection, settings

_MODEL = "gpt-4o-mini"

_COVER_LETTER_SYSTEM = (
    "You are an expert career coach and professional writer. "
    "Write persuasive, concise cover letters tailored to specific job postings."
)

_COVER_LETTER_PROMPT = """Write a professional cover letter for this candidate applying to this job.

CANDIDATE:
{profile_summary}

JOB:
{job_summary}

Instructions:
- 3-4 paragraphs, under 350 words
- Open with a specific hook related to the company/role (avoid "I am writing to apply")
- Highlight 2-3 matching skills from the candidate's superpowers
- Close with a clear next-step call to action
- Professional but warm tone, first person, no salutation or signature

Return ONLY the cover letter text, nothing else."""


async def generate_cover_letter(profile: dict, eval_doc: dict) -> str:
    client = AsyncOpenAI(api_key=settings.openai_api_key.strip())

    profile_summary = "\n".join(filter(None, [
        f"Name: {profile.get('full_name', '')}",
        f"Roles: {', '.join(profile.get('primary_roles', []))}",
        f"Headline: {profile.get('headline', '')}",
        f"Superpowers: {', '.join(profile.get('superpowers', []))}",
        f"Value proposition: {profile.get('exit_story', '')}",
        f"Location: {profile.get('location', '')}",
    ]))

    job_summary = (
        f"Title: {eval_doc.get('job_title', '')}\n"
        f"Company: {eval_doc.get('company_name', '')}\n\n"
        f"{eval_doc.get('job_text_snippet', '')}"
    )

    prompt = _COVER_LETTER_PROMPT.format(
        profile_summary=profile_summary,
        job_summary=job_summary,
    )

    response = await client.chat.completions.create(
        model=_MODEL,
        temperature=0.7,
        max_tokens=600,
        messages=[
            {"role": "system", "content": _COVER_LETTER_SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def _parse_lever_url(job_url: str):
    """Return (board_id, posting_id) if URL is a Lever job posting, else (None, None)."""
    m = re.match(r"https?://jobs\.lever\.co/([^/]+)/([a-f0-9-]{36})", job_url or "")
    if m:
        return m.group(1), m.group(2)
    return None, None


async def _apply_lever(
    board_id: str,
    posting_id: str,
    profile: dict,
    cover_letter: str,
    resume_bytes: bytes | None,
    user_email: str,
) -> dict:
    url = f"https://api.lever.co/v0/postings/{board_id}/{posting_id}/apply"

    data = {
        "name": profile.get("full_name", ""),
        "email": profile.get("email", "") or user_email,
        "phone": profile.get("phone", ""),
        "org": board_id,
        "comments": cover_letter,
    }

    files: dict = {k: (None, v) for k, v in data.items()}
    if resume_bytes:
        files["resume"] = ("resume.pdf", resume_bytes, "application/pdf")

    async with httpx.AsyncClient(timeout=20, verify=False) as client:
        r = await client.post(url, files=files)

    if r.status_code in (200, 201):
        return {"success": True, "status_code": r.status_code}
    return {"success": False, "status_code": r.status_code, "error": r.text[:300]}


async def auto_apply(eval_doc: dict, user_email: str) -> dict:
    """
    Main entry point. Returns:
      {
        "cover_letter": str,
        "applied": bool,
        "platform": str,
        "message": str,
      }
    """
    profile = await get_collection("career_ops_config").find_one({"user_email": user_email}) or {}

    cover_letter = await generate_cover_letter(profile, eval_doc)

    job_url = eval_doc.get("job_url", "")
    board_id, posting_id = _parse_lever_url(job_url)

    if board_id and posting_id:
        resume_doc = await get_collection("career_ops_resume").find_one({"user_email": user_email})
        resume_bytes: bytes | None = None
        if resume_doc and resume_doc.get("content_b64"):
            try:
                resume_bytes = base64.b64decode(resume_doc["content_b64"])
            except Exception:
                resume_bytes = None

        lever_result = await _apply_lever(board_id, posting_id, profile, cover_letter, resume_bytes, user_email)
        applied = lever_result["success"]
        message = (
            "Aplicación enviada vía Lever API."
            if applied
            else f"Error en Lever API (código {lever_result.get('status_code')}). "
                 "Cover letter generada — puedes usarla al aplicar manualmente."
        )
        return {"cover_letter": cover_letter, "applied": applied, "platform": "lever", "message": message}

    # Greenhouse / Ashby / unknown — no public apply API
    return {
        "cover_letter": cover_letter,
        "applied": False,
        "platform": "other",
        "message": "Cover letter generada. Abre el enlace de la oferta y úsala para aplicar.",
    }
