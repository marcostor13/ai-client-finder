"""Image generation adapters — HuggingFace FLUX, Prodia, Fal.ai."""
import asyncio
import base64

import httpx

from backend.agent_hub.models.base import ModelAdapter, ModelResponse


def _prompt_from_messages(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m["role"] == "user":
            return m["content"]
    return messages[-1]["content"] if messages else "a beautiful image"


# ── HuggingFace FLUX.1-schnell ─────────────────────────────────────────────

class HuggingFaceImageAdapter(ModelAdapter):
    model_id = "huggingface/flux-schnell"
    _HF_MODEL = "black-forest-labs/FLUX.1-schnell"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        prompt = _prompt_from_messages(messages)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"https://api-inference.huggingface.co/models/{self._HF_MODEL}"

        async with httpx.AsyncClient(timeout=90) as client:
            for _ in range(3):
                resp = await client.post(url, headers=headers, json={"inputs": prompt})
                if resp.status_code == 503:
                    data = resp.json()
                    wait = min(data.get("estimated_time", 20), 30)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            else:
                raise RuntimeError("FLUX model failed to warm up after retries")

        b64 = base64.b64encode(resp.content).decode()
        image_url = f"data:image/png;base64,{b64}"
        return ModelResponse(
            content="Image generated successfully.",
            model_id=self.model_id,
            intent="image",
            image_url=image_url,
        )


# ── Prodia SDXL ────────────────────────────────────────────────────────────

class ProdiaAdapter(ModelAdapter):
    model_id = "prodia/sdxl"
    _BASE = "https://api.prodia.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        prompt = _prompt_from_messages(messages)
        headers = {"X-Prodia-Key": self.api_key}

        async with httpx.AsyncClient(timeout=60) as client:
            # Submit job
            resp = await client.post(
                f"{self._BASE}/sd/generate",
                headers=headers,
                json={"prompt": prompt, "model": "sd_xl_base_1.0.safetensors [be9edd61]"},
            )
            resp.raise_for_status()
            job_id = resp.json()["job"]

            # Poll until done
            for _ in range(30):
                await asyncio.sleep(3)
                poll = await client.get(f"{self._BASE}/job/{job_id}", headers=headers)
                poll.raise_for_status()
                status_data = poll.json()
                if status_data.get("status") == "succeeded":
                    image_url = status_data["imageUrl"]
                    return ModelResponse(
                        content="Image generated successfully.",
                        model_id=self.model_id,
                        intent="image",
                        image_url=image_url,
                    )
                if status_data.get("status") == "failed":
                    raise RuntimeError("Prodia job failed")

        raise RuntimeError("Prodia job timed out")


# ── Fal.ai FLUX.1-schnell ──────────────────────────────────────────────────

class FalAdapter(ModelAdapter):
    model_id = "fal/flux-schnell"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        import os
        os.environ["FAL_KEY"] = self.api_key
        try:
            import fal_client  # type: ignore
        except ImportError:
            raise RuntimeError("fal-client not installed — run: pip install fal-client")

        prompt = _prompt_from_messages(messages)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: fal_client.run(
                "fal-ai/flux/schnell",
                arguments={"prompt": prompt, "num_images": 1},
            ),
        )
        images = result.get("images", [])
        if not images:
            raise RuntimeError("Fal.ai returned no images")

        image_url = images[0]["url"]
        return ModelResponse(
            content="Image generated successfully.",
            model_id=self.model_id,
            intent="image",
            image_url=image_url,
        )
