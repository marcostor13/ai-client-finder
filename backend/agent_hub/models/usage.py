"""Daily quota tracker for free-tier model limits."""
from datetime import datetime, timezone

from backend.database import get_collection

# Daily limits per model_id (requests/day). None = unlimited.
DAILY_LIMITS: dict[str, int | None] = {
    "deepseek/deepseek-v3":             1000,
    "groq/llama-4-scout":              14400,   # Llama 4 Scout (reemplaza 3.3-70b deprecated jun 2026)
    # Cerebras (jun 2026): llama-3.3-70b retirado; lineup actual ↓
    # Free tier: 30 RPM · 30K–100K TPM · 1M TPD · 8192 tok ctx cap
    "cerebras/gpt-oss-120b":           1000,   # OpenAI GPT OSS 120B — prod, ~3000 tok/s
    "cerebras/gemma-4-31b":            1000,   # Gemma 4 31B — preview, ~1850 tok/s
    "cerebras/zai-glm-4.7":            1000,   # Z.ai GLM 4.7 355B — preview, best reasoning
    "google/gemini-2.5-flash":          1500,   # gemini-1.5-flash y 2.0-flash retirados jun 2026
    "together/qwen2.5-72b":              500,
    "openrouter/llama-3.3-70b-free":     200,   # 70B gratis (reemplaza mistral-7b:free)
    "huggingface/zephyr-7b":             100,
    "huggingface/flux-schnell":          100,
    "prodia/sdxl":                        50,
    "fal/flux-schnell":                   30,
    "groq/whisper-large-v3":             100,
    "huggingface/whisper-large-v3":       50,
    "huggingface/kokoro-82m":            100,
    "elevenlabs/multilingual-v2":         20,
}

TOKEN_LIMITS: dict[str, int | None] = {
    "deepseek/deepseek-v3":           500_000,
    "groq/llama-4-scout":             500_000,
    "cerebras/gpt-oss-120b":        1_000_000,
    "cerebras/gemma-4-31b":         1_000_000,
    "cerebras/zai-glm-4.7":         1_000_000,
    "google/gemini-2.5-flash":      1_000_000,
    "together/qwen2.5-72b":           200_000,
    "openrouter/llama-3.3-70b-free":  200_000,
    "huggingface/zephyr-7b":           50_000,
    "elevenlabs/multilingual-v2":      10_000,
}

POOL_ORDER: dict[str, list[str]] = {
    "text": [
        "deepseek/deepseek-v3",
        "groq/llama-4-scout",
        "cerebras/gpt-oss-120b",
        "cerebras/gemma-4-31b",
        "cerebras/zai-glm-4.7",
        "google/gemini-2.5-flash",
        "together/qwen2.5-72b",
        "openrouter/llama-3.3-70b-free",
        "huggingface/zephyr-7b",
    ],
    "image": [
        "huggingface/flux-schnell",
        "prodia/sdxl",
        "fal/flux-schnell",
    ],
    "vision": [
        "google/gemini-2.5-flash",
    ],
    "audio_stt": [
        "groq/whisper-large-v3",
        "huggingface/whisper-large-v3",
    ],
    "tts": [
        "huggingface/kokoro-82m",
        "elevenlabs/multilingual-v2",
    ],
}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def get_usage(model_id: str) -> dict:
    col = get_collection("agent_model_usage")
    doc = await col.find_one({"model_id": model_id, "date": _today()})
    if not doc:
        return {"request_count": 0, "token_count": 0, "last_error": None, "last_error_at": None}
    # record_error() upserts docs without request_count — always merge with safe defaults
    return {
        "request_count": doc.get("request_count", 0),
        "token_count": doc.get("token_count", 0),
        "last_error": doc.get("last_error"),
        "last_error_at": doc.get("last_error_at"),
    }


async def is_quota_exhausted(model_id: str) -> bool:
    limit = DAILY_LIMITS.get(model_id)
    if limit is None:
        return False
    usage = await get_usage(model_id)
    return usage["request_count"] >= limit


async def increment_usage(model_id: str, tokens: int = 0) -> None:
    col = get_collection("agent_model_usage")
    await col.update_one(
        {"model_id": model_id, "date": _today()},
        {"$inc": {"request_count": 1, "token_count": tokens},
         "$set": {"updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def record_error(model_id: str, error: str) -> None:
    col = get_collection("agent_model_usage")
    now = datetime.now(timezone.utc)
    await col.update_one(
        {"model_id": model_id, "date": _today()},
        {"$set": {"last_error": error, "last_error_at": now, "updated_at": now}},
        upsert=True,
    )


async def get_all_status() -> dict[str, dict]:
    """Return status dict for every known model."""
    col = get_collection("agent_model_usage")
    today = _today()
    docs = await col.find({"date": today}).to_list(None)
    by_model = {d["model_id"]: d for d in docs}

    result = {}
    for model_id, limit in DAILY_LIMITS.items():
        doc = by_model.get(model_id, {})
        req = doc.get("request_count", 0)
        last_error = doc.get("last_error")

        if last_error and req == 0:
            status = "error"
        elif limit is not None and req >= limit:
            status = "quota_exhausted"
        elif last_error:
            status = "error"
        else:
            status = "active"

        result[model_id] = {
            "model_id": model_id,
            "status": status,
            "requests_today": req,
            "daily_limit": limit,
            "token_count": doc.get("token_count", 0),
            "last_error": last_error,
            "last_error_at": doc.get("last_error_at"),
        }
    return result
