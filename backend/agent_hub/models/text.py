"""Text LLM adapters — 7 free-tier providers with uniform interface."""
import asyncio
import base64

import httpx

from backend.agent_hub.models.base import ModelAdapter, ModelResponse


class _OpenAICompatAdapter(ModelAdapter):
    """Base for all OpenAI-compatible chat completion APIs."""

    base_url: str
    model: str
    extra_headers: dict = {}

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        tokens = usage.get("total_tokens", 0)
        return ModelResponse(content=content, model_id=self.model_id, intent="text", tokens_used=tokens)


# ── DeepSeek V3 ────────────────────────────────────────────────────────────

class DeepSeekAdapter(_OpenAICompatAdapter):
    model_id = "deepseek/deepseek-v3"
    base_url = "https://api.deepseek.com/v1"
    model = "deepseek-chat"


# ── Groq / Llama 4 Scout ───────────────────────────────────────────────────
# llama-3.3-70b-versatile deprecated on Groq free tier June 17 2026.

class GroqAdapter(_OpenAICompatAdapter):
    model_id = "groq/llama-4-scout"
    base_url = "https://api.groq.com/openai/v1"
    model = "meta-llama/llama-4-scout"


# ── Cerebras ───────────────────────────────────────────────────────────────
# llama-3.3-70b retired. Current lineup (jun 2026): gpt-oss-120b (prod),
# gemma-4-31b and zai-glm-4.7 (preview). All share the same OpenAI-compat API.

class CerebrasAdapter(_OpenAICompatAdapter):
    """OpenAI GPT OSS 120B — production model, ~3000 tok/s."""
    model_id = "cerebras/gpt-oss-120b"
    base_url = "https://api.cerebras.ai/v1"
    model = "gpt-oss-120b"


class CerebrasGemmaAdapter(_OpenAICompatAdapter):
    """Google Gemma 4 31B on Cerebras — preview, ~1850 tok/s."""
    model_id = "cerebras/gemma-4-31b"
    base_url = "https://api.cerebras.ai/v1"
    model = "gemma-4-31b"


class CerebrasGLMAdapter(_OpenAICompatAdapter):
    """Z.ai GLM 4.7 355B on Cerebras — preview, ~1000 tok/s, best reasoning."""
    model_id = "cerebras/zai-glm-4.7"
    base_url = "https://api.cerebras.ai/v1"
    model = "zai-glm-4.7"


# ── Google Gemini 2.5 Flash ────────────────────────────────────────────────
# gemini-1.5-flash and 2.0-flash retired June 2026; 2.5-flash is current free tier.

class GeminiAdapter(ModelAdapter):
    model_id = "google/gemini-2.5-flash"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        # Translate OpenAI-style messages to Gemini contents format
        contents = []
        system_text = ""
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
                continue
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})

        # Vision: attach an inline image to the last user turn (Gemini is multimodal).
        image_b64: str = kwargs.get("image_b64", "") or ""
        if image_b64:
            raw = image_b64.split(",", 1)[-1]  # strip data: URL prefix if present
            mime = kwargs.get("image_mime") or "image/png"
            if not contents or contents[-1]["role"] != "user":
                contents.append({"role": "user", "parts": []})
            contents[-1]["parts"].append(
                {"inline_data": {"mime_type": mime, "data": raw}}
            )

        payload: dict = {"contents": contents}
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        payload["generationConfig"] = {
            "maxOutputTokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
        }

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={self.api_key}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["candidates"][0]["content"]["parts"][0]["text"]
        tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
        return ModelResponse(content=content, model_id=self.model_id, intent="text", tokens_used=tokens)


# ── Together AI / Qwen2.5-72B ──────────────────────────────────────────────

class TogetherAdapter(_OpenAICompatAdapter):
    model_id = "together/qwen2.5-72b"
    base_url = "https://api.together.xyz/v1"
    model = "Qwen/Qwen2.5-72B-Instruct-Turbo"


# ── OpenRouter / Llama 3.3 70B free ───────────────────────────────────────
# Upgraded from mistral-7b:free (7B) to llama-3.3-70b:free (70B) — 10x más capaz.

class OpenRouterAdapter(_OpenAICompatAdapter):
    model_id = "openrouter/llama-3.3-70b-free"
    base_url = "https://openrouter.ai/api/v1"
    model = "meta-llama/llama-3.3-70b-instruct:free"
    extra_headers = {
        "HTTP-Referer": "https://github.com/ai-client-finder",
        "X-Title": "AI Client Finder",
    }


# ── HuggingFace Inference API / Zephyr-7B ─────────────────────────────────

class HuggingFaceTextAdapter(ModelAdapter):
    model_id = "huggingface/zephyr-7b"
    _HF_MODEL = "HuggingFaceH4/zephyr-7b-beta"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        # Convert to single prompt string for HF text-generation models
        prompt = "\n".join(
            f"<|{m['role']}|>\n{m['content']}" for m in messages
        ) + "\n<|assistant|>\n"

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": kwargs.get("max_tokens", 512),
                "temperature": kwargs.get("temperature", 0.7),
                "return_full_text": False,
            },
        }
        url = f"https://api-inference.huggingface.co/models/{self._HF_MODEL}"

        async with httpx.AsyncClient(timeout=60) as client:
            for attempt in range(3):
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 503:
                    # Model loading — wait and retry
                    estimated = resp.json().get("estimated_time", 20)
                    await asyncio.sleep(min(estimated, 20))
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            else:
                raise RuntimeError("HuggingFace model failed to load after retries")

        if isinstance(data, list):
            content = data[0].get("generated_text", "")
        else:
            content = str(data)

        return ModelResponse(content=content, model_id=self.model_id, intent="text")
