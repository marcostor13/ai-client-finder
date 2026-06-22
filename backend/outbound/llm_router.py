"""
LLM Router — Groq (free, primary) → OpenAI nano (fallback).
Tracks daily usage per provider in MongoDB to stay within free limits.
"""
from datetime import date
from typing import Optional

from backend.database import get_collection, settings

# Providers in priority order. daily_limit is conservative to stay in free tier.
_PROVIDERS = [
    {
        "name": "groq",
        "model": "llama-3.3-70b-versatile",
        "daily_limit": 400,
        "api_key": settings.groq_api_key,
    },
    {
        "name": "openai",
        "model": "gpt-4.1-mini",
        "daily_limit": 80,
        "api_key": settings.openai_api_key,
    },
]


async def _usage_today(provider: str) -> int:
    col = get_collection("outbound_llm_usage")
    doc = await col.find_one({"provider": provider, "date": date.today().isoformat()})
    return doc["count"] if doc else 0


async def _inc_usage(provider: str) -> None:
    col = get_collection("outbound_llm_usage")
    await col.update_one(
        {"provider": provider, "date": date.today().isoformat()},
        {"$inc": {"count": 1}},
        upsert=True,
    )


async def _call_groq(api_key: str, model: str, system: str, messages: list, temperature: float) -> str:
    from groq import AsyncGroq
    client = AsyncGroq(api_key=api_key)
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    resp = await client.chat.completions.create(
        model=model,
        messages=msgs,
        temperature=temperature,
        max_tokens=1024,
    )
    return resp.choices[0].message.content


async def _call_openai(api_key: str, model: str, system: str, messages: list, temperature: float) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key)
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    resp = await client.chat.completions.create(
        model=model,
        messages=msgs,
        temperature=temperature,
        max_tokens=1024,
    )
    return resp.choices[0].message.content


async def chat(
    messages: list,
    system: str = "",
    temperature: float = 0.3,
) -> tuple[str, str, str]:
    """
    Returns (response_text, provider_name, model_name).
    Tries providers in order, skips if daily limit reached or key missing.
    """
    for p in _PROVIDERS:
        if not p["api_key"]:
            continue
        usage = await _usage_today(p["name"])
        if usage >= p["daily_limit"]:
            print(f"[llm_router] {p['name']} daily limit reached ({usage}/{p['daily_limit']}), trying next")
            continue
        try:
            if p["name"] == "groq":
                text = await _call_groq(p["api_key"], p["model"], system, messages, temperature)
            else:
                text = await _call_openai(p["api_key"], p["model"], system, messages, temperature)
            await _inc_usage(p["name"])
            return text, p["name"], p["model"]
        except Exception as e:
            print(f"[llm_router] {p['name']} error: {e}")
            continue

    raise RuntimeError("All LLM providers exhausted or unavailable. Check API keys and daily limits.")


async def get_usage_summary() -> list[dict]:
    col = get_collection("outbound_llm_usage")
    today = date.today().isoformat()
    docs = await col.find({"date": today}).to_list(10)
    limits = {p["name"]: p["daily_limit"] for p in _PROVIDERS}
    return [
        {"provider": d["provider"], "used": d["count"], "limit": limits.get(d["provider"], "?")}
        for d in docs
    ]
