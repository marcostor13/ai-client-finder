from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ModelResponse:
    content: str
    model_id: str
    intent: Literal["text", "image", "audio_stt", "tts"]
    tokens_used: int = 0
    image_url: str | None = None
    audio_b64: str | None = None
    response_ms: int = 0


class ModelAdapter(ABC):
    model_id: str

    @abstractmethod
    async def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        """Call the underlying model and return a ModelResponse."""
