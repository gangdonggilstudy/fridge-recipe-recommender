"""LLM 기반 추천 이유 (gemini/openai, 키 없거나 실패 시 템플릿 폴백)."""

import base64
import os
from typing import Literal, Protocol

import requests

from modules.logging_setup import get_logger

_logger = get_logger(__name__)


PROMPT_TEMPLATE = """\
당신은 요리 추천 도우미입니다.
아래 정보를 바탕으로 사용자에게 추천 이유를 자연스러운 한국어 1~2문장으로 설명하세요.

- 추천 요리: {name}
- 주요 재료: {ingredients}
- 음식 스타일: {style}
- 가장 큰 추천 이유: {top_reason}

설명:"""


# LLM 기본값 — 환경변수로 오버라이드 가능 (.env.example 참조)
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_TEXT_TIMEOUT_SEC = 10
DEFAULT_VISION_TIMEOUT_SEC = 30
DEFAULT_MAX_TOKENS_TEXT = 200
DEFAULT_MAX_TOKENS_VISION = 500


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str: ...

    def generate_vision(self, prompt: str, image: bytes, mime: str) -> str:
        """이미지 + 프롬프트 멀티모달 호출 (영수증 OCR 등). 텍스트 응답 반환."""
        ...


class GeminiProvider:
    """Google Gemini Flash."""

    URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = os.getenv("LLM_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.text_timeout = int(os.getenv("LLM_TEXT_TIMEOUT_SEC", str(DEFAULT_TEXT_TIMEOUT_SEC)))
        self.vision_timeout = int(os.getenv("LLM_VISION_TIMEOUT_SEC", str(DEFAULT_VISION_TIMEOUT_SEC)))

    @property
    def url(self) -> str:
        return self.URL_TEMPLATE.format(model=self.model)

    def generate(self, prompt: str) -> str:
        resp = requests.post(
            f"{self.url}?key={self.api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=self.text_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    def generate_vision(self, prompt: str, image: bytes, mime: str) -> str:
        b64 = base64.b64encode(image).decode("ascii")
        resp = requests.post(
            f"{self.url}?key={self.api_key}",
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": mime, "data": b64}},
                        ]
                    }
                ]
            },
            timeout=self.vision_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


class OpenAIProvider:
    """OpenAI GPT-4o-mini."""

    URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = os.getenv("LLM_OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self.text_timeout = int(os.getenv("LLM_TEXT_TIMEOUT_SEC", str(DEFAULT_TEXT_TIMEOUT_SEC)))
        self.vision_timeout = int(os.getenv("LLM_VISION_TIMEOUT_SEC", str(DEFAULT_VISION_TIMEOUT_SEC)))
        self.max_tokens_text = int(os.getenv("LLM_MAX_TOKENS_TEXT", str(DEFAULT_MAX_TOKENS_TEXT)))
        self.max_tokens_vision = int(os.getenv("LLM_MAX_TOKENS_VISION", str(DEFAULT_MAX_TOKENS_VISION)))

    def generate(self, prompt: str) -> str:
        resp = requests.post(
            self.URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_tokens_text,
            },
            timeout=self.text_timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def generate_vision(self, prompt: str, image: bytes, mime: str) -> str:
        b64 = base64.b64encode(image).decode("ascii")
        resp = requests.post(
            self.URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{b64}"
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": self.max_tokens_vision,
            },
            timeout=self.vision_timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


def _is_placeholder(value: str | None) -> bool:
    # .env.example 견본값(your_*_here)을 실제 키로 오인하지 않게 거름 → 템플릿 폴백.
    if not value:
        return True
    return value.startswith("your_") or value.endswith("_here")


def make_provider(
    name: Literal["gemini", "openai"] | None = None,
    api_key: str | None = None,
) -> LLMProvider | None:
    """환경변수 또는 인자 기반으로 프로바이더 생성. 키 없으면 None."""
    name = name or os.getenv("LLM_PROVIDER")
    api_key = api_key or os.getenv("LLM_API_KEY")
    if not name or _is_placeholder(api_key):
        return None

    if name == "gemini":
        return GeminiProvider(api_key)
    if name == "openai":
        return OpenAIProvider(api_key)
    return None


class Narrator:
    """추천 설명 자연어 생성."""

    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider

    def generate(self, recipe: dict, top_reason: str) -> str:
        """LLM 시도 → 실패/미설정 시 템플릿 fallback."""
        if self.provider is not None:
            try:
                prompt = PROMPT_TEMPLATE.format(
                    name=recipe.get("name", ""),
                    ingredients=", ".join(recipe.get("ingredients", [])),
                    style=recipe.get("style", ""),
                    top_reason=top_reason,
                )
                return self.provider.generate(prompt)
            except Exception as e:  # noqa: BLE001 — LLM 호출/응답 파싱 어떤 실패든 템플릿 폴백
                _logger.warning("LLM 호출 실패, 템플릿 fallback: %s", e)
        return self._template(recipe, top_reason)

    @staticmethod
    def _template(recipe: dict, top_reason: str) -> str:
        name = recipe.get("name", "이 요리")
        style = recipe.get("style", "")
        ingredients = recipe.get("ingredients", [])
        sample = ", ".join(ingredients[:3])
        return (
            f"{name}은(는) {style} 스타일이며, 보유한 {sample} 등을 활용할 수 있고 "
            f"{top_reason} 측면에서 가장 적합하여 추천했습니다."
        )
