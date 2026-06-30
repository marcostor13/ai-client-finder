"""
AI Gateway — intent detection + model pool routing with fallback.
Intent detection uses DeepSeek-V3 (falls back to keyword heuristics).
"""
import os
import re
import time
from typing import Literal

import httpx

from backend.agent_hub.models.base import ModelResponse
from backend.agent_hub.models.usage import (
    POOL_ORDER,
    increment_usage,
    is_quota_exhausted,
    record_error,
)

Intent = Literal["text", "image", "audio_stt", "tts", "vision"]

_IMAGE_KEYWORDS = re.compile(
    r"\b(genera|crea|dibuja|imagen|foto|picture|image|draw|generate|render|diseña|ilustra|paint)\b",
    re.IGNORECASE,
)
_TTS_KEYWORDS = re.compile(
    r"\b(lee en voz alta|text to speech|tts|speak|habla|di esto|narrate|read aloud)\b",
    re.IGNORECASE,
)

# Conservative input token budgets per model (leaves ~2K tokens headroom for output).
# Approximation: ~4 chars per token for mixed Spanish/English.
_MODEL_INPUT_BUDGET: dict[str, int] = {
    "deepseek/deepseek-v3":            48_000,
    "groq/llama-4-scout":             100_000,
    # Cerebras free tier caps context at 8192 tokens → budget ~6K (leaves 2K for output)
    "cerebras/gpt-oss-120b":            6_000,
    "cerebras/gemma-4-31b":             6_000,
    "cerebras/zai-glm-4.7":             6_000,
    "google/gemini-2.5-flash":        800_000,
    "together/qwen2.5-72b":            24_000,
    "openrouter/llama-3.3-70b-free":    6_000,
    "huggingface/zephyr-7b":            3_000,
}
_DEFAULT_INPUT_BUDGET = 4_000


def _estimate_tokens(text: str) -> int:
    """Approximate token count: ~4 chars per token."""
    return max(1, len(text) // 4)


def _messages_tokens(messages: list[dict]) -> int:
    return sum(_estimate_tokens(str(m.get("content", ""))) for m in messages)


def _trim_to_budget(messages: list[dict], max_tokens: int) -> list[dict]:
    """
    Trim oldest non-system messages to fit within max_tokens.
    Always preserves system messages and the last user message so context
    continuity is maintained when falling back to a smaller-context model.
    """
    if _messages_tokens(messages) <= max_tokens:
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    # Always keep the last user message — it's the current request
    last_user = next((m for m in reversed(non_system) if m.get("role") == "user"), None)
    reserved = sum(_estimate_tokens(str(m.get("content", ""))) for m in system_msgs)
    if last_user:
        reserved += _estimate_tokens(str(last_user.get("content", "")))

    history_budget = max(0, max_tokens - reserved)
    history = [m for m in non_system if m is not last_user]

    # Walk from newest → oldest, keep as many history messages as fit
    kept: list[dict] = []
    tokens_used = 0
    for m in reversed(history):
        t = _estimate_tokens(str(m.get("content", "")))
        if tokens_used + t <= history_budget:
            kept.insert(0, m)
            tokens_used += t
        else:
            break

    result = system_msgs + kept
    if last_user:
        result.append(last_user)
    return result


async def detect_intent(message: str) -> Intent:
    """Classify message intent. Uses DeepSeek first, falls back to regex."""
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Classify the user message into exactly one category: "
                                    "text, image, audio_stt, tts. "
                                    "text = general questions, chat, code, analysis. "
                                    "image = requests to generate/draw/create an image. "
                                    "audio_stt = requests to transcribe audio. "
                                    "tts = requests to read text aloud or generate speech. "
                                    "Reply with only the category word, nothing else."
                                ),
                            },
                            {"role": "user", "content": message},
                        ],
                        "max_tokens": 10,
                        "temperature": 0,
                    },
                )
            if resp.status_code == 200:
                intent = resp.json()["choices"][0]["message"]["content"].strip().lower()
                if intent in ("text", "image", "audio_stt", "tts"):
                    return intent  # type: ignore[return-value]
        except Exception:
            pass

    # Keyword fallback
    if _IMAGE_KEYWORDS.search(message):
        return "image"
    if _TTS_KEYWORDS.search(message):
        return "tts"
    return "text"


class AllModelsExhausted(Exception):
    def __init__(self, intent: str):
        super().__init__(f"All models exhausted for intent '{intent}'")
        self.intent = intent


async def route(
    intent: Intent,
    messages: list[dict],
    **kwargs,
) -> ModelResponse:
    """
    Iterate the pool for the given intent, skip quota-exhausted models,
    call the first available adapter, and increment usage on success.

    Before calling each adapter, messages are trimmed to fit that model's
    input token budget — preserving context continuity across fallbacks.

    Raises AllModelsExhausted if no model can serve the request.
    """
    from backend.agent_hub.models import get_adapter  # lazy to avoid circular

    errors: list[str] = []
    for model_id in POOL_ORDER.get(intent, []):
        if await is_quota_exhausted(model_id):
            errors.append(f"{model_id}: quota exhausted")
            continue

        adapter = get_adapter(model_id)
        if adapter is None:
            errors.append(f"{model_id}: no api key / adapter unavailable")
            continue

        # Fit messages within this model's context window before calling it
        budget = _MODEL_INPUT_BUDGET.get(model_id, _DEFAULT_INPUT_BUDGET)
        model_messages = _trim_to_budget(messages, budget)

        try:
            t0 = time.monotonic()
            response = await adapter.generate(model_messages, **kwargs)
            response.response_ms = int((time.monotonic() - t0) * 1000)
            await increment_usage(model_id, response.tokens_used)
            return response
        except Exception as exc:
            err_msg = str(exc)[:200]
            errors.append(f"{model_id}: {err_msg}")
            await record_error(model_id, err_msg)
            continue

    raise AllModelsExhausted(intent)
