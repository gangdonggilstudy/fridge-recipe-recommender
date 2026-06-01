"""추천 점수 계산 — 규칙 5요소 가중합 / 학습 LR 블렌더 + 좋아요·다양성 가산."""

import logging
import math

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .contracts import ScoreComponents
from .context import CONTEXT_WEIGHTS, get_month, get_time_label
from .ingredient_matcher import consumption_score, ingredient_score
from .preference import FEATURE_KEYS, cook_time_bucket

_logger = logging.getLogger(__name__)


DEFAULT_WEIGHTS: dict[str, float] = {
    "ingredient":  0.35,
    "consumption": 0.25,
    "preference":  0.20,
    "context":     0.15,
    "diversity":   0.05,
}

# 시간대는 적합 범위가 좁아 가장 강하게, 날씨·월은 약하게.
TIME_MISMATCH_PENALTY = 0.2
WEATHER_MISMATCH_PENALTY = 0.25
MONTH_MISMATCH_PENALTY = 0.25


def build_recipe_vector(recipe: dict) -> dict[str, float]:
    """레시피 → 선호 벡터와 같은 키 공간(FEATURE_KEYS) one-hot 인코딩."""
    vec = dict.fromkeys(FEATURE_KEYS, 0.0)

    if (style := recipe.get("style")) in vec:
        vec[style] = 1.0
    for t in recipe.get("taste", []):
        if t in vec:
            vec[t] = 1.0

    vec[cook_time_bucket(recipe.get("cook_time", 0))] = 1.0

    # 리뷰 키워드 차원
    for keyword in recipe.get("review_keywords", []):
        if keyword in vec:
            vec[keyword] = 1.0
    return vec


def preference_score(user_vector: dict[str, float], recipe: dict) -> float:
    """Cosine similarity. 선호 벡터 음수 허용(싫어요 누적) → 결과는 [0,1] 클리핑."""
    if not user_vector:
        return 0.0
    recipe_vec = build_recipe_vector(recipe)
    user_arr = np.array([user_vector.get(k, 0.0) for k in FEATURE_KEYS]).reshape(1, -1)
    recipe_arr = np.array([recipe_vec.get(k, 0.0) for k in FEATURE_KEYS]).reshape(1, -1)
    if not np.any(user_arr) or not np.any(recipe_arr):
        return 0.0
    raw = float(cosine_similarity(user_arr, recipe_arr)[0][0])
    return max(0.0, min(1.0, raw))



def time_score(recipe: dict, hour: int) -> float:
    label = get_time_label(hour)
    return 1.0 if label in recipe.get("suitable_time", []) else TIME_MISMATCH_PENALTY


def weather_score(recipe: dict, weather: str) -> float:
    return 1.0 if weather in recipe.get("suitable_weather", []) else WEATHER_MISMATCH_PENALTY


def month_score(recipe: dict, month: str | None = None) -> float:
    month = month or get_month()
    return 1.0 if month in recipe.get("suitable_month", []) else MONTH_MISMATCH_PENALTY


def context_score(recipe: dict, context: dict) -> float:
    """`CONTEXT_WEIGHTS` 가설 가중합 (운영 데이터로 재산출 예정)."""
    return (
        CONTEXT_WEIGHTS["time"]    * time_score(recipe, context["hour"])
        + CONTEXT_WEIGHTS["weather"] * weather_score(recipe, context["weather"])
        + CONTEXT_WEIGHTS["month"]   * month_score(recipe, context.get("month"))
    )


def _sigmoid(z: float) -> float:
    """수치 안정 로지스틱."""
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


class Scorer:
    def __init__(
        self,
        weights: dict[str, float] | None = None,
        ingredient_category_weight: float = 0.3,
    ):
        self.weights = weights or DEFAULT_WEIGHTS
        # 0 = 정확 매치만 / >0 = 부족 재료 카테고리 부분 점수.
        self.ingredient_category_weight = ingredient_category_weight

    def score(
        self,
        recipe: dict,
        owned_items: list[dict],
        user_vector: dict[str, float],
        context: dict,
        diversity_bonus: float = 0.0,
        like_bonus: float = 0.0,
        history_count: int = 0,
        ml_blend_fn=None,
        group_vector: dict[str, float] | None = None,
    ) -> ScoreComponents:
        """`ml_blend_fn` 있으면 정착 σ(b + Σ wᵢxᵢ), 없으면 cold-start 5요소 합.

        다양성·좋아요는 두 레짐 공통 투명 가산항. group_vector 는 cold-start
        보강용 (개인 기록·벡터 없을 때 그룹 평균으로 preference 보정).
        """
        effective_pref_vec = user_vector
        if not user_vector and history_count == 0 and group_vector:
            effective_pref_vec = group_vector

        owned_names = {i["name"] for i in owned_items}
        components: dict = {
            "ingredient":  ingredient_score(
                owned_names,
                recipe.get("ingredients", []),
                category_weight=self.ingredient_category_weight,
            ),
            "consumption": consumption_score(owned_items, recipe.get("ingredients", [])),
            "preference":  preference_score(effective_pref_vec, recipe),
            "context":     context_score(recipe, context),
            "diversity":   diversity_bonus,
        }
        blend = None
        if ml_blend_fn is not None:
            try:
                blend = ml_blend_fn(components)
            except Exception:  # noqa: BLE001 — 분해 실패 시 규칙 폴백
                _logger.warning("blender contribution failed; falling back to rule regime", exc_info=True)
                blend = None

        if blend is not None:
            base = self._apply_blend(components, blend)
        else:
            base = self._rule_total(components)
            components["combine"] = "rule"
            components["intercept"] = 0.0
            components["ml"] = 0.0

        components["like_bonus"] = like_bonus
        # base 보존 → recommender._apply_diversity 가 멱등 재계산.
        components["base"] = base
        components["total"] = base + like_bonus
        return components

    def _rule_total(self, components: dict) -> float:
        return sum(
            self.weights[k] * components[k]
            for k in ("ingredient", "consumption", "preference", "context", "diversity")
        )

    def _apply_blend(self, components: dict, blend: dict) -> float:
        """충실성 불변: `intercept + Σcontrib == decision_function`."""
        z = float(blend["intercept"]) + sum(blend["contrib"].values())
        base = _sigmoid(z)
        components["combine"] = "blender"
        components["contrib"] = dict(blend["contrib"])
        components["intercept"] = float(blend["intercept"])
        components["ml"] = base
        return base
