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

Intent = Literal["text", "image", "audio_stt", "tts"]

_IMAGE_KEYWORDS = re.compile(
    r"\b(genera|crea|dibuja|imagen|foto|picture|image|draw|generate|render|diseña|ilustra|paint)\b",
    re.IGNORECASE,
)
_TTS_KEYWORDS = re.compile(
    r"\b(lee en voz alta|text to speech|tts|speak|habla|di esto|narrate|read aloud)\b",
    re.IGNORECASE,
)


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

        try:
            t0 = time.monotonic()
            response = await adapter.generate(messages, **kwargs)
            response.response_ms = int((time.monotonic() - t0) * 1000)
            await increment_usage(model_id, response.tokens_used)
            return response
        except Exception as exc:
            err_msg = str(exc)[:200]
            errors.append(f"{model_id}: {err_msg}")
            await record_error(model_id, err_msg)
            continue

    raise AllModelsExhausted(intent)
