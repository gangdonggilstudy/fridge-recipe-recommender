"""history → (X, y). 피처 차원·순서는 `ml_model.build_feature` 와 단일 출처."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ._base_repo import BaseRepository


def row_to_feature(row) -> list[float]:
    """history row → 6차원 피처 벡터.

    `build_feature()` 와 반드시 같은 순서를 유지. match 컬럼이 NULL(구 데이터)
    이면 0.0 — '매칭 불명' 으로 처리.
    """
    return [
        float(row["ingredient_score"] or 0.0),
        float(row["consumption_score"] or 0.0),
        float(row["preference_score"] or 0.0),
        float(row["context_score"] or 0.0),
        float(row["month_match"] or 0.0),
        float(row["season_match"] or 0.0),
    ]


class TrainingDataRepository(BaseRepository):
    """`history` 테이블에서 ML 학습 데이터(X, y) 를 읽는다."""

    def __init__(self, db_path: str | Path | None = None):
        super().__init__(db_path)

    def count(self, user_id: str) -> int:
        """사용자 history 건수. 활성화 임계값 비교용."""
        with self._connect() as con:
            row = con.execute(
                "SELECT COUNT(*) FROM history WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row[0] if row else 0

    def load(self, user_id: str) -> tuple[np.ndarray, np.ndarray]:
        """history → (X, y). 시간순 정렬(recency 가중 학습에 사용)."""
        with self._connect() as con:
            rows = con.execute(
                """SELECT ingredient_score, consumption_score, preference_score,
                          context_score, month_match, season_match, selected
                   FROM history WHERE user_id = ?
                   ORDER BY timestamp, rowid""",
                (user_id,),
            ).fetchall()

        X = np.array([row_to_feature(r) for r in rows])
        y = np.array([r["selected"] for r in rows])
        return X, y
