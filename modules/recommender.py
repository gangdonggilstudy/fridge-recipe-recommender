"""추천 오케스트레이션 — 필터 → 점수(Scorer 위임) → 정렬 → 다양성 → top N."""

import logging

from .contracts import Recipe
from .custom_recipe_repo import CustomRecipeRepo
from .demographics_repo import DemographicsRepo
from .fridge_repo import FridgeRepo
from .history_repo import HistoryRepo
from .like_repo import LikeRepo
from .ml_model import MLModel
from .preference import PreferenceManager
from .recipe_repo import RecipeRepo
from .recommendation_impression import RecommendationImpressionRepo
from .restriction_repo import RestrictionRepo
from .scorer import Scorer

_logger = logging.getLogger(__name__)

DEFAULT_TOP_N = 5
# 가산값 = weights["diversity"] × DIVERSITY_BONUS = 0.05 × 0.2 = 0.010.
DIVERSITY_BONUS = 0.2
TOP_STYLES_FOR_DIVERSITY = 3


class Recommender:

    def __init__(
        self,
        recipe_repo: RecipeRepo,
        preference_manager: PreferenceManager,
        fridge_repo: FridgeRepo,
        *,
        history_repo: HistoryRepo,
        demographics_repo: DemographicsRepo,
        scorer: Scorer | None = None,
        custom_repo: CustomRecipeRepo | None = None,
        like_repo: LikeRepo | None = None,
        restriction_repo: RestrictionRepo | None = None,
        ml_model: MLModel | None = None,
    ):
        self.recipes = recipe_repo
        self.preference_manager = preference_manager
        self.fridge = fridge_repo
        self.history_repo = history_repo
        self.demographics_repo = demographics_repo
        self.scorer = scorer or Scorer()
        self.custom_repo = custom_repo
        self.like_repo = like_repo
        self.restriction_repo = restriction_repo
        self.ml_model = ml_model

    def recommend(
        self,
        user_id: str,
        context: dict,
        top_n: int = DEFAULT_TOP_N,
    ) -> list[Recipe]:
        """반환 형식: `[{recipe + "scores": {...}}]`.

        scores 키: ingredient, consumption, preference, context, diversity, like_bonus, total.
        """
        # 보유 재료 로드 → 이름 집합으로 후보 검색에 사용.
        owned_items = self.fridge.load(user_id)
        owned_names = {i["name"] for i in owned_items}

        # 재료가 겹치는 레시피만 추리고 알레르기·기피는 제거. 후보 없으면 종료.
        candidates = self._filter_candidates(user_id, owned_names)
        if not candidates:
            return []

        user_vector = self.preference_manager.load(user_id)
        history_count = self.history_repo.history_count(user_id)

        # 콜드스타트: 개인 벡터도 기록도 없으면 같은 인구통계 그룹의 평균 취향을 대체.
        group_vector: dict[str, float] | None = None
        if not user_vector and history_count == 0:
            gender, age_group = self.demographics_repo.get_demographics(user_id)
            if gender or age_group:
                group_vector = self.demographics_repo.get_group_vector(gender, age_group)
                group_vector = group_vector or None

        # 후보마다 5요소 점수 계산(학습 모델 있으면 블렌더, 없으면 룰).
        scored = self._score_all(
            user_id, candidates, owned_items, user_vector, context,
            history_count=history_count,
            group_vector=group_vector,
        )
        # 2-pass: ①1차 정렬로 상위 스타일을 확정 → ②그 외에 다양성 보너스 → ③재정렬.
        #  (보너스 주기 전에 정렬해야 '현재 상위 스타일'을 알 수 있어 2번 정렬한다)
        scored.sort(key=lambda x: x["scores"]["total"], reverse=True)
        self._apply_diversity(scored)
        scored.sort(key=lambda x: x["scores"]["total"], reverse=True)
        return scored[:top_n]

    def record_choice(
        self,
        user_id: str,
        recipe: dict,
        selected: bool,
        context: dict,
        *,
        rank: int,
        impression_repo: RecommendationImpressionRepo | None = None,
        impression_session_id: str | None = None,
    ) -> bool:
        """선택 부수효과 — 노출 액션 → 선호 벡터 → history → 학습 트리거.

        반환: 학습이 실제 발생했으면 True.
        """
        if impression_repo is not None and impression_session_id:
            impression_repo.mark_action(
                impression_session_id, recipe["id"], selected
            )
        self.preference_manager.update(user_id, recipe, selected=selected)
        self.history_repo.log_history(
            user_id, recipe["id"], selected, recipe["scores"], context,
            model_group=recipe["scores"].get("combine", "rule"),
            rec_rank=rank,
            recipe=recipe,
        )
        return self._safe_maybe_train(user_id)

    def record_dislike(
        self,
        user_id: str,
        recipe: dict,
        context: dict,
        *,
        rank: int,
        impression_repo: RecommendationImpressionRepo | None = None,
        impression_session_id: str | None = None,
    ) -> bool:
        """'별로에요' — 직전 record_choice(selected=True) 의 거울 트랜잭션.

        impressions selected=0, 선호 벡터 -1.5(상쇄 +1.0 + 패널티 -0.5, DECAY 없음),
        history 직전 row UPDATE selected=0, ml_model 비치명 재학습. context·rank 는
        record_choice 와 시그니처 일관성용.
        """
        del context, rank
        if impression_repo is not None and impression_session_id:
            impression_repo.mark_action(
                impression_session_id, recipe["id"], False,
            )
        self.preference_manager.revert_then_dislike(user_id, recipe)
        self.history_repo.mark_unselected(user_id, recipe["id"])
        return self._safe_maybe_train(user_id)

    def _safe_maybe_train(self, user_id: str) -> bool:
        """학습 실패가 사용자 흐름을 막지 않도록 swallow."""
        if self.ml_model is None:
            return False
        try:
            return bool(self.ml_model.maybe_train(user_id))
        except Exception:  # noqa: BLE001
            _logger.warning("ml_model.maybe_train failed for user_id=%s", user_id, exc_info=True)
            return False

    def _filter_candidates(self, user_id: str, owned_names: set[str]) -> list[dict]:
        """시스템 + 커스텀(본인 + 공유) 레시피 → 알레르기·기피 hard filter."""
        candidates = self.recipes.search_by_ingredients(owned_names)
        if self.custom_repo is not None:
            candidates += self.custom_repo.search_by_ingredients_for_user(user_id, owned_names)
        return self._apply_restrictions(user_id, candidates)

    def _apply_restrictions(self, user_id: str, candidates: list[dict]) -> list[dict]:
        if self.restriction_repo is None:
            return candidates
        restricted = self.restriction_repo.list_ingredients(user_id)
        if not restricted:
            return candidates
        return [r for r in candidates if not (restricted & set(r.get("ingredients", [])))]

    def _score_all(
        self,
        user_id: str,
        candidates: list[dict],
        owned_items: list[dict],
        user_vector: dict[str, float],
        context: dict,
        history_count: int,
        group_vector: dict[str, float] | None = None,
    ) -> list[dict]:
        """학습된 LR 있으면 블렌더 레짐, 없으면 규칙 레짐."""
        scored: list[dict] = []
        for recipe in candidates:
            like_bonus = (
                self.like_repo.like_bonus(recipe["id"]) if self.like_repo else 0.0
            )
            # 학습 모델이 있으면, scorer 가 호출할 '기여도 분해 함수'를 만들어 넘긴다.
            # bound_recipe/bound_context 기본인자 = 반복문 변수의 '현재 값'을 즉시
            # 묶어두는 트릭(late-binding 회피). 안 하면 모든 클로저가 마지막 recipe 를
            # 가리키게 된다.
            ml_blend_fn = None
            if self.ml_model is not None:
                def _compute_linear_contributions(
                    components,
                    bound_recipe=recipe,
                    bound_context=context,
                ):
                    return self.ml_model.linear_contributions(
                        user_id, components, bound_recipe, bound_context,
                    )
                ml_blend_fn = _compute_linear_contributions

            scores = self.scorer.score(
                recipe, owned_items, user_vector, context,
                diversity_bonus=0.0,
                like_bonus=like_bonus,
                history_count=history_count,
                ml_blend_fn=ml_blend_fn,
                group_vector=group_vector,
            )
            scored.append({**recipe, "scores": scores})
        return scored

    def _apply_diversity(self, scored: list[dict]) -> None:
        """top N 외 스타일에 보너스. in-place. 호출 전 정렬 필수, 호출 후 재정렬 호출자 책임."""
        # 현재 상위 3개 항목의 스타일 = '이미 강한' 스타일 → 보너스 제외 대상.
        top_styles = {r["style"] for r in scored[:TOP_STYLES_FOR_DIVERSITY]}
        w_div = self.scorer.weights["diversity"]
        for entry in scored:
            s = entry["scores"]
            # 상위 스타일이 아니면 다양성 보너스(0.2) 부여, 맞으면 0.
            div = DIVERSITY_BONUS if entry["style"] not in top_styles else 0.0
            s["diversity"] = div
            # total 을 base(다양성 전 점수)에서 매번 새로 계산 → 여러 번 불러도
            # 보너스가 누적되지 않음(멱등). 실제 가산값은 0.05×0.2=0.01.
            s["total"] = s["base"] + w_div * div + s.get("like_bonus", 0.0)
