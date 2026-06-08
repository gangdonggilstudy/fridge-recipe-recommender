"""ML 학습 데이터 로더. 피처 차원·순서는 `ml_model.build_feature` 와 단일 출처.

`load`: history(명시 선택/거부)만 → (X, y).
`load_with_weak`: history + recommendation_impressions 의 약한 미선택(acted=0)을
합쳐 → (X, y, is_weak). 후자가 기본 학습 경로(블렌더 활성화).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ._base_repo import BaseRepository


def row_to_feature(row) -> list[float]:
    """history row → 5차원 피처 벡터.

    `build_feature()` 와 반드시 같은 순서를 유지. temporal_fit 이 NULL(recipe
    미전달 INSERT) 이면 0.0 — '시기 불명' 으로 처리.
    """
    return [
        float(row["ingredient_score"] or 0.0),
        float(row["consumption_score"] or 0.0),
        float(row["preference_score"] or 0.0),
        float(row["context_score"] or 0.0),
        float(row["temporal_fit"] or 0.0),
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
                          context_score, temporal_fit, selected
                   FROM history WHERE user_id = ?
                   ORDER BY timestamp, rowid""",
                (user_id,),
            ).fetchall()

        X = np.array([row_to_feature(r) for r in rows])
        y = np.array([r["selected"] for r in rows])
        return X, y

    def load_with_weak(
        self, user_id: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """history(명시 신호) + impression 약한 미선택 → (X, y, is_weak).

        - history: 선택(1)·별로에요(0) 명시 신호. is_weak=False.
        - recommendation_impressions WHERE acted=0: 노출됐으나 안 누른 약한 음성.
          항상 라벨 0, is_weak=True. (acted=1 행은 history 와 중복이라 제외.)

        시간순 통합 정렬 — 호출자가 recency 감쇠를 인덱스로 적용한다.
        반환 X 가 비어있을 수 있으니 호출부에서 size 가드 필요.
        """
        with self._connect() as con:
            hist = con.execute(
                """SELECT ingredient_score, consumption_score, preference_score,
                          context_score, temporal_fit, selected, timestamp
                   FROM history WHERE user_id = ?""",
                (user_id,),
            ).fetchall()
            # ingredient_score IS NOT NULL: 피처 컬럼 추가 '이전'에 쌓인 노출 행은
            # 5피처가 NULL → 0벡터가 되어 학습에 잡음이 되므로 제외. 신규(피처 보존)
            # 행만 약한 음성으로 쓴다. (구 DB 를 ALTER 로 마이그레이션해도 옛 행은
            # 자동 배제되어 안전.)
            weak = con.execute(
                """SELECT ingredient_score, consumption_score, preference_score,
                          context_score, temporal_fit, timestamp
                   FROM recommendation_impressions
                   WHERE user_id = ? AND acted = 0
                     AND ingredient_score IS NOT NULL""",
                (user_id,),
            ).fetchall()

        # (timestamp, features, label, is_weak) 로 모은 뒤 시간순 정렬.
        merged: list[tuple] = []
        for r in hist:
            merged.append((r["timestamp"] or "", row_to_feature(r), int(r["selected"]), False))
        for r in weak:
            merged.append((r["timestamp"] or "", row_to_feature(r), 0, True))
        merged.sort(key=lambda t: t[0])

        if not merged:
            empty = np.empty((0, 0))
            return empty, np.array([]), np.array([], dtype=bool)
        X = np.array([m[1] for m in merged])
        y = np.array([m[2] for m in merged])
        is_weak = np.array([m[3] for m in merged], dtype=bool)
        return X, y, is_weak
