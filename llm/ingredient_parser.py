"""텍스트 → 재료 이름 — 정규식 1차, LLM 2차. normalize + canonical 매칭."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import get_close_matches

from llm.narrator import LLMProvider
from modules.logging_setup import get_logger
from modules.normalize import normalize_ingredient

_logger = get_logger(__name__)


# 한국어 수사 — "양파 두 개" 의 "두" 같은 양 토큰을 chunk 에서 떼내기 위함.
KOREAN_NUMBERS: set[str] = {
    "반", "한", "하나", "두", "둘", "세", "셋", "네", "넷",
    "다섯", "여섯", "일곱", "여덟", "아홉", "열",
}

# 알려진 단위 토큰 — 긴 것부터 매칭되도록 정렬되어 사용.
UNIT_TOKENS: list[str] = [
    "큰술", "작은술", "봉지", "공기", "송이",
    "개", "통", "장", "봉", "마리", "줌", "컵", "모", "쪽", "캔", "병", "팩",
    "ml", "mL", "g", "kg", "L", "리터",
]

# canonical 매칭 신뢰도 단계 — `_item_confirm` 의 표시 분기와 공유.
# 1.0: exact 매치, 0.7: fuzzy (오타 1-2자), 0.5: 미등록(unknown).
CONFIDENCE_EXACT: float = 1.0
CONFIDENCE_FUZZY: float = 0.7
CONFIDENCE_UNKNOWN: float = 0.5
# get_close_matches cutoff — fuzzy 매칭으로 인정할 최소 유사도 (의미상 CONFIDENCE_FUZZY 와 동일 임계).
FUZZY_MATCH_CUTOFF: float = CONFIDENCE_FUZZY


# 긴 토큰 우선 정렬: 정규식 교대(|)는 앞 패턴이 먼저 매칭되므로
# "kg" 가 "g" 보다, "큰술" 이 "술" 보다 앞서야 한다.
_UNIT_PAT = "|".join(re.escape(u) for u in sorted(UNIT_TOKENS, key=len, reverse=True))
_KOREAN_NUM_PAT = "|".join(
    re.escape(k) for k in sorted(KOREAN_NUMBERS, key=len, reverse=True)
)

# 구분자 — "랑/이랑"은 뒤에 공백 있을 때만 (노랑파프리카 같은 단어 보호)
_SEPARATOR_RE = re.compile(
    r"\s*[,，]\s*|\s+그리고\s+|이?랑\s+|\s+하고\s+|\s+또\s+|\s+및\s+"
)
# 양·단위 한 묶음을 chunk 에서 제거하는 패턴 (아라비아 / 한국어 둘 다)
_QTY_UNIT_RE = re.compile(
    rf"(?:[\d]+(?:\.\d+)?|{_KOREAN_NUM_PAT})\s*(?:{_UNIT_PAT})"
)


@dataclass(frozen=True)
class ParsedItem:
    """음성·영수증 파싱 결과 한 항목 (양·단위 미보유)."""
    name: str           # normalize_ingredient + canonical 매칭 후 표기
    raw: str            # 원본 chunk (UI 표시용)
    confidence: float   # 1.0 정확, 0.7 LLM/fuzzy, 0.5 unknown


_LLM_PROMPT = """다음 한국어 발화에서 식재료 이름만 추출하세요.

발화: "{text}"

출력 규칙:
- 반드시 JSON 배열만 반환. 다른 문장·코드블록 금지.
- 각 항목: {{"name": "재료명"}}
- 수량·단위는 제외하고 이름만.

예시:
- 입력: "양파 2개, 김치 한 통" → [{{"name":"양파"}},{{"name":"김치"}}]
- 입력: "두부 반 모" → [{{"name":"두부"}}]

JSON:"""


class IngredientParser:
    """음성·영수증 텍스트를 ParsedItem(이름만) 리스트로 변환."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        canonical_names: list[str] | None = None,
    ) -> None:
        self.provider = provider
        self.canonical_names = list(canonical_names) if canonical_names else []

    def parse(self, text: str) -> list[ParsedItem]:
        text = (text or "").strip()
        if not text:
            return []

        # 1차: 정규식
        items = self._parse_regex(text)
        if items:
            return self._merge_duplicates(items)

        # 2차: LLM 폴백
        if self.provider is not None:
            try:
                items = self._parse_llm(text)
                if items:
                    return self._merge_duplicates(items)
            except Exception as e:  # noqa: BLE001
                _logger.warning("LLM 파싱 실패: %s", e)

        return []

    # ── 정규식 ──

    def _parse_regex(self, text: str) -> list[ParsedItem]:
        chunks = _SEPARATOR_RE.split(text)
        results: list[ParsedItem] = []
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            results.extend(self._parse_chunk(chunk))
        return results

    def _parse_chunk(self, chunk: str) -> list[ParsedItem]:
        # 양·단위 토큰 묶음을 제거해 이름만 남긴다 ("양파 2개" → "양파").
        # 매칭 없으면 chunk 자체가 이름.
        name = _QTY_UNIT_RE.sub("", chunk).strip()
        if not name:
            return []
        return self._make_items(name, chunk)

    def _make_items(self, name: str, raw: str) -> list[ParsedItem]:
        """canonical 재료 여러 개가 띄어쓰기 없이 합쳐진 경우 분리해 복수 항목 반환.

        STT 가 "간장 양파 두부" 를 "간장양파두부" 로 출력하거나(붙임), 사용자가 한 chunk
        안에 여러 재료를 공백 구분으로 말한 경우 둘 다 `normalize_ingredient` 의 공백
        제거로 같은 합성 문자열이 된다. canonical 사전이 있으면 longest-match-first
        그리디로 분해 — "고추기름" 처럼 긴 canonical 이 우선되어 잘못 쪼개지지 않는다.
        canonical 미전달 시(테스트·디폴트) 단일 항목으로 폴백.
        """
        clean = normalize_ingredient(name)
        if not clean:
            return []
        parts = self._split_compound_name(clean)
        return [self._make_item(p, raw) for p in parts]

    def _split_compound_name(self, clean: str) -> list[str]:
        """canonical 사전 기반 longest-match-first 완전 분해.

        **완전성 가드**: 모든 글자가 canonical 토큰에 흡수돼야만 분해를 적용한다.
        한 글자라도 매칭 실패하면 원본 유지 — "고추기름"(canonical 미등록)이
        ["고추", "기름(미등록)"] 으로 잘못 쪼개지는 케이스 차단. canonical 에
        없는 재료를 임의로 분해해 의미가 바뀌는 위험보다 원본 그대로 두고
        confidence=0.5(unknown) 폴백을 거치는 편이 안전.
        """
        if not self.canonical_names or clean in self.canonical_names:
            return [clean]
        sorted_canon = sorted(self.canonical_names, key=len, reverse=True)
        remaining = clean
        parts: list[str] = []
        while remaining:
            matched = next(
                (c for c in sorted_canon if remaining.startswith(c)),
                None,
            )
            if matched is None:
                # 한 글자라도 canonical 에 안 흡수되면 분해 포기 — 원본 유지.
                return [clean]
            parts.append(matched)
            remaining = remaining[len(matched):]
        # 2개 이상으로 깔끔히 분해된 경우만 split 적용. 1개면 원본과 동일.
        return parts if len(parts) > 1 else [clean]

    def _make_item(self, name: str, raw: str) -> ParsedItem:
        clean = normalize_ingredient(name)
        confidence = CONFIDENCE_EXACT

        if self.canonical_names:
            if clean in self.canonical_names:
                confidence = CONFIDENCE_EXACT
            else:
                close = get_close_matches(
                    clean, self.canonical_names, n=1, cutoff=FUZZY_MATCH_CUTOFF,
                )
                if close:
                    clean = close[0]
                    confidence = CONFIDENCE_FUZZY
                else:
                    confidence = CONFIDENCE_UNKNOWN

        return ParsedItem(name=clean, raw=raw, confidence=confidence)

    # ── LLM ──

    def _parse_llm(self, text: str) -> list[ParsedItem]:
        assert self.provider is not None  # noqa: S101 — caller guarantees
        prompt = _LLM_PROMPT.format(text=text)
        response = self.provider.generate(prompt)
        return self.items_from_llm_json(response, default_raw=text)

    def items_from_llm_json(
        self, response: str, default_raw: str | None = None
    ) -> list[ParsedItem]:
        """LLM JSON 배열 응답 → ParsedItem 리스트. 중복 병합은 호출자 책임.

        음성(`_parse_llm`)·영수증(`ReceiptParser`) 공용 단일 출처. LLM 이
        코드블록·설명을 곁들여도 JSON 배열만 뽑아내려는 의도 — `\\[.*\\]` +
        DOTALL 은 greedy 라 첫 '[' ~ 마지막 ']' 전체를 잡고, 잘못 잡히면
        아래 json.loads 에서 걸러져 [] 반환. LLM 신뢰도는 정규식보다 한
        단계 낮춰 0.7 상한. `default_raw=None` 이면 항목 name 을 raw 로
        (영수증), 문자열이면 그 값을 공통 raw 로(음성 transcript).

        구버전 응답 형식(`qty`, `unit` 키 포함)도 그냥 무시 — 호환 처리 없음.
        """
        match = re.search(r"\[.*\]", response, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []

        results: list[ParsedItem] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            item = self._make_item(
                name, name if default_raw is None else default_raw,
            )
            results.append(
                ParsedItem(
                    name=item.name, raw=item.raw,
                    confidence=min(item.confidence, CONFIDENCE_FUZZY),
                )
            )
        return results

    @staticmethod
    def _merge_duplicates(items: list[ParsedItem]) -> list[ParsedItem]:
        merged: dict[str, ParsedItem] = {}
        for item in items:
            if item.name in merged:
                prev = merged[item.name]
                merged[item.name] = ParsedItem(
                    name=prev.name,
                    raw=f"{prev.raw}, {item.raw}",
                    confidence=min(prev.confidence, item.confidence),
                )
            else:
                merged[item.name] = item
        return list(merged.values())
