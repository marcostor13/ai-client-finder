import json

from openai import AsyncOpenAI

from backend.database import settings

_MODEL = "gpt-4o-mini"


def _salary_line(profile: dict) -> str:
    """Build a human-readable salary expectation line for the evaluator prompt."""
    cur    = profile.get("currency", "USD")
    period = profile.get("salary_period", "monthly")
    lo     = profile.get("target_min", 0)
    hi     = profile.get("target_max", 0)
    legacy = profile.get("target_range", "")
    label  = "month" if period == "monthly" else "year"

    if lo or hi:
        lo_s = f"{cur} {lo:,}" if lo else ""
        hi_s = f"{cur} {hi:,}" if hi else ""
        if lo_s and hi_s:
            return f"{lo_s} – {hi_s} / {label}"
        return f"{lo_s or hi_s} / {label}"
    if legacy:
        return f"{legacy} {cur}"
    return "Not specified"

_SYSTEM = "You are an expert career advisor. Evaluate job opportunities and return ONLY valid JSON."

_PROMPT_TEMPLATE = """Evaluate this job for the candidate. Return ONLY a valid JSON object.

CANDIDATE PROFILE:
{profile_summary}

JOB{job_header}:
{job_text}

{{
  "overall_score": <float 1.0-5.0>,
  "grade": <"A"|"B"|"C"|"D"|"F">,
  "recommendation": <"apply"|"maybe"|"skip">,
  "role_fit":     {{"score": <1.0-5.0>, "label": <"Excellent"|"Good"|"Fair"|"Poor"|"Very Poor">, "notes": "<1-2 sentences>"}},
  "compensation": {{"score": <1.0-5.0>, "label": <"Excellent"|"Good"|"Fair"|"Poor"|"Very Poor">, "notes": "<1-2 sentences>"}},
  "growth":       {{"score": <1.0-5.0>, "label": <"Excellent"|"Good"|"Fair"|"Poor"|"Very Poor">, "notes": "<1-2 sentences>"}},
  "culture":      {{"score": <1.0-5.0>, "label": <"Excellent"|"Good"|"Fair"|"Poor"|"Very Poor">, "notes": "<1-2 sentences>"}},
  "location":     {{"score": <1.0-5.0>, "label": <"Excellent"|"Good"|"Fair"|"Poor"|"Very Poor">, "notes": "<1-2 sentences>"}},
  "team":         {{"score": <1.0-5.0>, "label": <"Excellent"|"Good"|"Fair"|"Poor"|"Very Poor">, "notes": "<1-2 sentences>"}},
  "strengths":      ["<2-4 bullet points>"],
  "red_flags":      ["<0-3 bullet points, empty array if none>"],
  "talking_points": ["<2-3 key points to highlight>"],
  "summary": "<1 concise paragraph>"
}}

Grade: A≥4.5, B=3.5-4.4, C=2.5-3.4, D=1.5-2.4, F<1.5
Recommend "apply" if ≥4.0, "maybe" if 3.0-3.9, "skip" if <3.0"""


async def evaluate_job(
    job_text: str,
    profile: dict,
    job_title: str = "",
    company: str = "",
) -> dict:
    client = AsyncOpenAI(api_key=settings.openai_api_key.strip())

    profile_summary = "\n".join(filter(None, [
        f"Candidate: {profile.get('full_name', 'Not specified')}",
        f"Location: {profile.get('location', 'Not specified')}",
        f"Target roles: {', '.join(profile.get('primary_roles', [])) or 'Not specified'}",
        f"Headline: {profile.get('headline', '')}",
        f"Superpowers: {', '.join(profile.get('superpowers', [])) or 'Not specified'}",
        f"Target salary: {_salary_line(profile)}",
        f"Location flexibility: {profile.get('location_flexibility', 'Not specified')}",
        f"Must-haves: {', '.join(profile.get('must_haves', [])) or 'None'}",
        f"Deal-breakers: {', '.join(profile.get('deal_breakers', [])) or 'None'}",
        f"Value proposition: {profile.get('exit_story', '')}",
    ]))

    job_header = f" — {job_title} at {company}" if (job_title or company) else ""

    prompt = _PROMPT_TEMPLATE.format(
        profile_summary=profile_summary,
        job_header=job_header,
        job_text=job_text[:4000],
    )

    response = await client.chat.completions.create(
        model=_MODEL,
        temperature=0,
        max_tokens=900,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )

    return json.loads(response.choices[0].message.content)
