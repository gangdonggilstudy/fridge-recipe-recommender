"""도메인 dict 계약 (TypedDict) — 문서·IDE·정적검증용, 런타임 무영향."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


class Context(TypedDict):
    """`ContextAnalyzer.get_context()` 출력. season 은 UI 표시용 (점수는 month)."""

    hour: int
    time: str
    weather: str
    month: str
    season: str


class ScoreComponents(TypedDict):
    """`contrib` 은 블렌더 레짐에서만 채워짐."""

    ingredient: float
    consumption: float
    preference: float
    context: float
    diversity: float
    combine: Literal["rule", "blender"]
    intercept: float
    ml: float
    like_bonus: float
    base: float
    total: float
    contrib: NotRequired[dict[str, float]]


class Recipe(TypedDict):
    """`is_custom` 은 커스텀만, `scores` 는 추천 결과 attach 시만."""

    id: str
    name: str
    style: str
    taste: list[str]
    cook_time: int
    difficulty: str
    suitable_time: list[str]
    suitable_weather: list[str]
    suitable_month: list[str]
    ingredients: list[str]
    review_keywords: list[str]
    instructions: str
    source_url: NotRequired[str]
    is_custom: NotRequired[bool]
    scores: NotRequired[ScoreComponents]


class LinearContribution(TypedDict):
    """불변: `intercept + Σ contrib == decision_function`."""

    contrib: dict[str, float]
    intercept: float
