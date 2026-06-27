"""Audio adapters — STT (Groq Whisper, HF Whisper) + TTS (Kokoro, ElevenLabs)."""
import asyncio
import base64

import httpx

from backend.agent_hub.models.base import ModelAdapter, ModelResponse


# ── Groq Whisper large-v3 (STT) ────────────────────────────────────────────

class GroqWhisperAdapter(ModelAdapter):
    model_id = "groq/whisper-large-v3"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        audio_bytes: bytes = kwargs.get("audio_bytes", b"")
        filename: str = kwargs.get("filename", "audio.mp3")
        if not audio_bytes:
            raise ValueError("audio_bytes required for STT")

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (filename, audio_bytes, "audio/mpeg")},
                data={"model": "whisper-large-v3", "response_format": "json"},
            )
            resp.raise_for_status()

        text = resp.json().get("text", "")
        return ModelResponse(content=text, model_id=self.model_id, intent="audio_stt")


# ── HuggingFace Whisper large-v3 (STT fallback) ────────────────────────────

class HuggingFaceWhisperAdapter(ModelAdapter):
    model_id = "huggingface/whisper-large-v3"
    _HF_MODEL = "openai/whisper-large-v3"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        audio_bytes: bytes = kwargs.get("audio_bytes", b"")
        if not audio_bytes:
            raise ValueError("audio_bytes required for STT")

        url = f"https://api-inference.huggingface.co/models/{self._HF_MODEL}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=90) as client:
            for _ in range(3):
                resp = await client.post(url, headers=headers, content=audio_bytes)
                if resp.status_code == 503:
                    wait = min(resp.json().get("estimated_time", 20), 30)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            else:
                raise RuntimeError("HuggingFace Whisper failed to load")

        data = resp.json()
        text = data.get("text", "") if isinstance(data, dict) else str(data)
        return ModelResponse(content=text, model_id=self.model_id, intent="audio_stt")


# ── Kokoro-82M via HuggingFace (TTS) ──────────────────────────────────────

class KokoroAdapter(ModelAdapter):
    model_id = "huggingface/kokoro-82m"
    _HF_MODEL = "hexgrad/Kokoro-82M"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        text = messages[-1]["content"] if messages else ""
        if isinstance(text, dict):
            text = str(text)

        url = f"https://api-inference.huggingface.co/models/{self._HF_MODEL}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=60) as client:
            for _ in range(3):
                resp = await client.post(url, headers=headers, json={"inputs": text})
                if resp.status_code == 503:
                    wait = min(resp.json().get("estimated_time", 20), 30)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            else:
                raise RuntimeError("Kokoro model failed to load")

        b64 = base64.b64encode(resp.content).decode()
        audio_b64 = f"data:audio/wav;base64,{b64}"
        return ModelResponse(
            content="Audio generated.",
            model_id=self.model_id,
            intent="tts",
            audio_b64=audio_b64,
        )


# ── ElevenLabs (TTS) ───────────────────────────────────────────────────────

_ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — default free voice


class ElevenLabsAdapter(ModelAdapter):
    model_id = "elevenlabs/multilingual-v2"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        text = messages[-1]["content"] if messages else ""
        if isinstance(text, dict):
            text = str(text)

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{_ELEVENLABS_VOICE_ID}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()

        b64 = base64.b64encode(resp.content).decode()
        audio_b64 = f"data:audio/mpeg;base64,{b64}"
        return ModelResponse(
            content="Audio generated.",
            model_id=self.model_id,
            intent="tts",
            audio_b64=audio_b64,
            tokens_used=len(text),
        )
