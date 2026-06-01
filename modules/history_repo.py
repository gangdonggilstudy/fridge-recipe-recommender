"""선택 기록(history) — ML 학습 레이블·피처 + 드리프트. 노출/CTR 은 별도 repo."""

from pathlib import Path

from ._base_repo import BaseRepository
from .context import compute_month_season_match
from .db_init import ensure_user


def _extract_history_month_season_match(
    context: dict, recipe: dict | None,
) -> tuple[int | None, int | None]:
    """INSERT 시점 계산 — 학습 시 recipe 재조회·라벨 불일치 회피."""
    if recipe is None:
        return None, None
    month_match, season_match = compute_month_season_match(
        context.get("month"), recipe.get("suitable_month") or [],
    )
    return int(month_match), int(season_match)


class HistoryRepo(BaseRepository):
    def __init__(self, db_path: str | Path | None = None, init_app_db: bool = True):
        super().__init__(db_path, init_app_db=init_app_db)

    def log_history(
        self,
        user_id: str,
        recipe_id: str,
        selected: bool,
        scores: dict[str, float],
        context: dict[str, str | int] | None = None,
        model_group: str | None = None,
        rec_rank: int | None = None,
        recipe: dict | None = None,
    ) -> None:
        """`recipe` 전달 시 블렌더 5·6번 피처(month/season match)도 컬럼 저장."""
        ensure_user(self.db_path, user_id)
        context = context or {}
        month_match, season_match = _extract_history_month_season_match(context, recipe)
        with self._connect() as con:
            con.execute(
                """INSERT INTO history
                   (user_id, recipe_id, selected,
                    ingredient_score, consumption_score, preference_score, context_score,
                    hour, weather, month, month_match, season_match,
                    model_group, rec_rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    recipe_id,
                    1 if selected else 0,
                    scores.get("ingredient", 0.0),
                    scores.get("consumption", 0.0),
                    scores.get("preference", 0.0),
                    scores.get("context", 0.0),
                    context.get("hour"),
                    context.get("weather"),
                    context.get("month"),
                    month_match,
                    season_match,
                    model_group,
                    rec_rank,
                ),
            )
            con.commit()

    def mark_unselected(self, user_id: str, recipe_id: str) -> None:
        """별로에요 — (user, recipe) 최신 row 만 selected=0. 매칭 0건이면 no-op."""
        with self._connect() as con:
            con.execute(
                """UPDATE history SET selected = 0
                   WHERE id = (
                       SELECT MAX(id) FROM history
                       WHERE user_id = ? AND recipe_id = ?
                   )""",
                (user_id, recipe_id),
            )
            con.commit()

    def history_count(self, user_id: str) -> int:
        with self._connect() as con:
            return con.execute(
                "SELECT COUNT(*) FROM history WHERE user_id = ?", (user_id,)
            ).fetchone()[0]

    def detect_drift(
        self,
        user_id: str,
        recent_n: int = 20,
        min_history: int = 40,
    ) -> float | None:
        """최근 N vs 이전의 4점수 평균 유클리드 거리 → 0~1. 데이터 부족 시 None."""
        with self._connect() as con:
            rows = con.execute(
                """SELECT ingredient_score, consumption_score,
                          preference_score, context_score
                   FROM history WHERE user_id = ?
                   ORDER BY timestamp DESC""",
                (user_id,),
            ).fetchall()

        if len(rows) < min_history:
            return None

        recent = rows[:recent_n]
        prev = rows[recent_n:]
        if not prev:
            return None

        def avg_vec(rs):
            n = len(rs)
            return [
                sum(r["ingredient_score"] for r in rs) / n,
                sum(r["consumption_score"] for r in rs) / n,
                sum(r["preference_score"] for r in rs) / n,
                sum(r["context_score"] for r in rs) / n,
            ]

        a = avg_vec(recent)
        b = avg_vec(prev)
        # 4차원 최대 거리 = √4 = 2.
        dist = (sum((x - y) ** 2 for x, y in zip(a, b, strict=True))) ** 0.5
        return min(1.0, dist / 2.0)
