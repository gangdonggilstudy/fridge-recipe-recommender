"""환경 플래그 기능 게이팅 — streamlit 무의존 (테스트 가능)."""
from __future__ import annotations

from llm.narrator import make_provider

from .env_flag import env_flag


def receipt_ocr_enabled() -> bool:
    """`RECEIPT_OCR_ENABLED=true` + 유효 LLM 공급자."""
    if not env_flag("RECEIPT_OCR_ENABLED", default=False):
        return False
    return make_provider() is not None
