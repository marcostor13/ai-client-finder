"""Adapter factory — returns the right ModelAdapter for a given model_id."""
import os

from backend.agent_hub.models.base import ModelAdapter


def get_adapter(model_id: str) -> ModelAdapter | None:
    """Return an instantiated adapter for model_id, or None if the API key is missing."""
    from backend.agent_hub.models.text import (
        DeepSeekAdapter, GroqAdapter, CerebrasAdapter,
        GeminiAdapter, TogetherAdapter, OpenRouterAdapter, HuggingFaceTextAdapter,
    )
    from backend.agent_hub.models.image import (
        HuggingFaceImageAdapter, ProdiaAdapter, FalAdapter,
    )
    from backend.agent_hub.models.audio import (
        GroqWhisperAdapter, HuggingFaceWhisperAdapter,
        KokoroAdapter, ElevenLabsAdapter,
    )

    mapping: dict[str, tuple[type[ModelAdapter], str]] = {
        "deepseek/deepseek-v3":           (DeepSeekAdapter,           "DEEPSEEK_API_KEY"),
        "groq/llama-3.3-70b":            (GroqAdapter,               "GROQ_API_KEY"),
        "cerebras/llama-3.3-70b":        (CerebrasAdapter,           "CEREBRAS_API_KEY"),
        "google/gemini-1.5-flash":       (GeminiAdapter,             "GEMINI_API_KEY"),
        "together/qwen2.5-72b":          (TogetherAdapter,           "TOGETHER_API_KEY"),
        "openrouter/mistral-7b-free":    (OpenRouterAdapter,         "OPENROUTER_API_KEY"),
        "huggingface/zephyr-7b":         (HuggingFaceTextAdapter,    "HUGGINGFACE_API_KEY"),
        "huggingface/flux-schnell":      (HuggingFaceImageAdapter,   "HUGGINGFACE_API_KEY"),
        "prodia/sdxl":                   (ProdiaAdapter,             "PRODIA_API_KEY"),
        "fal/flux-schnell":              (FalAdapter,                "FAL_API_KEY"),
        "groq/whisper-large-v3":         (GroqWhisperAdapter,        "GROQ_API_KEY"),
        "huggingface/whisper-large-v3":  (HuggingFaceWhisperAdapter, "HUGGINGFACE_API_KEY"),
        "huggingface/kokoro-82m":        (KokoroAdapter,             "HUGGINGFACE_API_KEY"),
        "elevenlabs/multilingual-v2":    (ElevenLabsAdapter,         "ELEVENLABS_API_KEY"),
    }

    entry = mapping.get(model_id)
    if not entry:
        return None
    adapter_cls, env_var = entry
    api_key = os.getenv(env_var, "")
    if not api_key:
        return None
    return adapter_cls(api_key)
