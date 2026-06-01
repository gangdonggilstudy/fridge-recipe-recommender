"""영수증 이미지 → 재료 항목 (Gemini Vision). 정규화는 IngredientParser 재사용."""
from __future__ import annotations

from llm.ingredient_parser import IngredientParser, ParsedItem
from llm.narrator import LLMProvider
from modules.logging_setup import get_logger

_logger = get_logger(__name__)


_RECEIPT_PROMPT = """이 영수증 이미지에서 식재료 품목명만 추출하세요.

규칙:
- 반드시 JSON 배열만 반환. 다른 문장·코드블록 금지.
- 각 항목: {"name": "재료명"}
- 식품·식재료만. 비식품(봉투·결제·포인트·할인 등)은 제외.
- 영수증 축약·코드명은 일반적인 재료명으로 풀어서.
- 수량·단위는 추출하지 않는다 (이름만).

JSON:"""


class ReceiptParser:
    """영수증 이미지를 ParsedItem 리스트로 변환. IngredientParser 재사용."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        ingredient_parser: IngredientParser | None = None,
    ) -> None:
        self.provider = provider
        # 정규화·canonical fuzzy·중복 병합 로직 재사용 (단일 출처)
        self._ip = ingredient_parser or IngredientParser()

    def parse(self, image: bytes, mime: str = "image/jpeg") -> list[ParsedItem]:
        if self.provider is None or not image:
            return []
        try:
            response = self.provider.generate_vision(
                _RECEIPT_PROMPT, image, mime
            )
        except Exception as e:  # noqa: BLE001 — 어떤 호출 오류든 빈 결과
            _logger.warning("영수증 비전 호출 실패: %s", e)
            return []

        # JSON→ParsedItem 변환은 IngredientParser 단일 출처 재사용
        # (default_raw=None → 항목 name 을 raw 로). 중복 병합은 호출자 책임.
        items = self._ip.items_from_llm_json(response)
        return self._ip._merge_duplicates(items)
