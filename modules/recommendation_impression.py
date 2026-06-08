"""추천 노출 로그 — CTR/평가용 (학습 피드백은 `history` 별도)."""

from pathlib import Path

from ._base_repo import BaseRepository
from .context import temporal_fit_score
from .db_init import ensure_user


class RecommendationImpressionRepo(BaseRepository):
    """추천 화면 노출 세션과 이후 액션을 기록한다."""

    def __init__(self, db_path: str | Path | None = None):
        super().__init__(db_path)

    def log_view(
        self,
        user_id: str,
        session_id: str,
        recipes: list[dict],
        context: dict[str, str | int] | None = None,
    ) -> None:
        """현재 화면에 보인 추천 카드들을 한 세션으로 저장한다.

        `INSERT OR IGNORE` 로 같은 session_id/recipe_id 의 Streamlit rerun 중복
        기록을 막는다. `recipes` 는 이미 화면 표시 순서로 정렬되어 있어야 한다.
        """
        if not user_id or not session_id or not recipes:
            return
        ensure_user(self.db_path, user_id)
        context = context or {}
        rows = []
        for rank, recipe in enumerate(recipes, start=1):
            scores = recipe.get("scores", {})
            # 5피처를 노출 시점에 스냅샷 — 안 고른(acted=0) 행을 나중에 약한 음성
            # 학습 데이터로 쓰기 위함. temporal_fit 은 history 와 동일한 단일 출처
            # 함수로 계산해 train/serve skew 를 막는다.
            temporal_fit = temporal_fit_score(
                context.get("month"), recipe.get("suitable_month") or [],
            )
            rows.append(
                (
                    session_id,
                    user_id,
                    recipe["id"],
                    rank,
                    0,
                    0,
                    scores.get("combine", "rule"),
                    scores.get("total", 0.0),
                    context.get("hour"),
                    context.get("weather"),
                    context.get("month"),
                    scores.get("ingredient", 0.0),
                    scores.get("consumption", 0.0),
                    scores.get("preference", 0.0),
                    scores.get("context", 0.0),
                    temporal_fit,
                )
            )

        with self._connect() as con:
            con.executemany(
                """INSERT OR IGNORE INTO recommendation_impressions
                   (session_id, user_id, recipe_id, rec_rank, selected, acted,
                    model_group, total_score, hour, weather, month,
                    ingredient_score, consumption_score, preference_score,
                    context_score, temporal_fit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            con.commit()

    def mark_action(self, session_id: str, recipe_id: str, selected: bool) -> None:
        """노출된 카드에 대한 선택/관심없음 액션을 반영한다."""
        if not session_id or not recipe_id:
            return
        with self._connect() as con:
            con.execute(
                """UPDATE recommendation_impressions
                   SET selected = ?, acted = 1
                   WHERE session_id = ? AND recipe_id = ?""",
                (1 if selected else 0, session_id, recipe_id),
            )
            con.commit()
