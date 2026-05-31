"""리뷰 키워드 추출 — LLM 우선, 템플릿 폴백. 차원은 `REVIEW_KEYWORD_DIMS` 고정."""

from modules.logging_setup import get_logger

from .narrator import LLMProvider

_logger = get_logger(__name__)


# 고정 키워드 차원 (preference.FEATURE_KEYS 와 일치해야 함)
REVIEW_KEYWORD_DIMS: list[str] = [
    "신선함", "푸짐함", "가벼움", "든든함", "자극적", "부드러움",
]


PROMPT_TEMPLATE = """\
다음 한국 음식의 일반적인 리뷰·인상에서 두드러지는 특징 키워드를
아래 목록에서 골라 콤마로 구분해 답하세요. 최대 4개까지 선택.

키워드 후보: {candidates}

음식 정보:
- 이름: {name}
- 스타일: {style}
- 맛: {taste}

답변 (키워드만, 콤마 구분):"""


# 스타일·맛 조합 기반 fallback 매핑 (LLM 미사용 시)
_STYLE_FALLBACK: dict[str, list[str]] = {
    "한식": ["푸짐함", "든든함"],
    "양식": ["부드러움", "푸짐함"],
    "중식": ["푸짐함", "자극적"],
    "일식": ["신선함", "가벼움"],
}

_TASTE_FALLBACK: dict[str, list[str]] = {
    "매운맛": ["자극적"],
    "담백함": ["가벼움", "부드러움"],
    "단맛":   ["부드러움"],
}


class ReviewAnalyzer:
    """레시피 리뷰 키워드 생성기. narrator.Narrator 와 동일 패턴."""

    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider

    def generate_keywords(
        self,
        recipe_name: str,
        style: str,
        taste: str | list[str],
    ) -> list[str]:
        """LLM 또는 fallback 으로 키워드 리스트 반환. REVIEW_KEYWORD_DIMS 부분집합."""
        taste_str = ", ".join(taste) if isinstance(taste, list) else (taste or "")

        if self.provider is not None:
            try:
                prompt = PROMPT_TEMPLATE.format(
                    candidates=", ".join(REVIEW_KEYWORD_DIMS),
                    name=recipe_name,
                    style=style or "",
                    taste=taste_str,
                )
                raw = self.provider.generate(prompt)
                return self._parse(raw)
            except Exception as e:  # noqa: BLE001 — 어떤 LLM 오류든 fallback
                _logger.warning("리뷰 키워드 LLM 실패, fallback 사용: %s", e)

        return self._fallback(style, taste_str)

    @staticmethod
    def _parse(raw: str) -> list[str]:
        """LLM 응답에서 유효 키워드만 추출 (중복 제거, 순서 유지).

        REVIEW_KEYWORD_DIMS 화이트리스트 필터가 핵심: LLM 이 목록 밖
        단어를 만들어내도(환각) FEATURE_KEYS 차원과 어긋나지 않게 막는다.
        """
        tokens = [t.strip() for t in raw.replace("\n", ",").split(",")]
        seen: set[str] = set()
        result: list[str] = []
        for t in tokens:
            if t in REVIEW_KEYWORD_DIMS and t not in seen:
                seen.add(t)
                result.append(t)
        return result

    @staticmethod
    def _fallback(style: str, taste_str: str) -> list[str]:
        """스타일·맛 조합 기반 결정적 키워드 (재현 가능)."""
        keywords: list[str] = []
        seen: set[str] = set()

        for keyword in _STYLE_FALLBACK.get(style, []):
            if keyword not in seen:
                keywords.append(keyword)
                seen.add(keyword)

        for taste in taste_str.split(", "):
            for keyword in _TASTE_FALLBACK.get(taste.strip(), []):
                if keyword not in seen:
                    keywords.append(keyword)
                    seen.add(keyword)

        return keywords
