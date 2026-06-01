"""User-based CF — cosine similarity 상위 K명 가중 평균. (보존된 미사용 모듈)"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from ._base_repo import BaseRepository


DEFAULT_TOP_K = 5
MIN_USERS = 2


class CollaborativeFilter(BaseRepository):
    """User-based CF — selected=1 기록 기반."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        min_users: int = MIN_USERS,
    ):
        super().__init__(db_path)
        self.min_users = min_users
        self._cache: dict | None = None

    # ── 행렬 구성 ──

    def _load_matrix(self) -> dict | None:
        """user-item 행렬 + 인덱스 반환. 사용자 < min_users면 None."""
        with self._connect() as con:
            df = pd.read_sql(
                """SELECT user_id, recipe_id, MAX(selected) AS selected
                   FROM history
                   GROUP BY user_id, recipe_id""",
                con,
            )
        if len(df) == 0:
            return None
        df = df[df["selected"] == 1]
        if df["user_id"].nunique() < self.min_users:
            return None
        pivot = df.pivot_table(
            index="user_id",
            columns="recipe_id",
            values="selected",
            fill_value=0,
        )
        return {
            "users":   pivot.index.tolist(),
            "recipes": pivot.columns.tolist(),
            "matrix":  pivot.values.astype(float),
        }

    def invalidate_cache(self) -> None:
        """history 갱신 후 다음 호출 시 다시 로드하도록 캐시 무효화."""
        self._cache = None

    def _get_cached_matrix(self) -> dict | None:
        if self._cache is None:
            self._cache = self._load_matrix()
        return self._cache

    # ── 공개 API ──

    def has_enough_data(self) -> bool:
        return self._get_cached_matrix() is not None

    def cf_score(
        self,
        target_user: str,
        recipe_id: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> float:
        """타깃 사용자가 해당 레시피를 좋아할 예측 점수 (0~1)."""
        data = self._get_cached_matrix()
        if data is None:
            return 0.0
        users, recipes, matrix = data["users"], data["recipes"], data["matrix"]
        if target_user not in users or recipe_id not in recipes:
            return 0.0

        target_idx = users.index(target_user)
        recipe_idx = recipes.index(recipe_id)

        # 자기 자신은 sim=1.0 이라 가중평균을 지배하므로 제외해야
        # "유사한 남들의 선택"이라는 CF 본래 신호가 나온다.
        similarities = cosine_similarity(matrix)[target_idx].copy()
        similarities[target_idx] = 0.0

        # 유사도 상위 K명만 사용 (먼 사용자 노이즈 차단)
        top_indices = np.argsort(-similarities)[:top_k]
        weights = similarities[top_indices]
        # 합 0 = 유사한 사용자가 한 명도 없음 → CF 신호 없음(0). 0 나눗셈도 방지.
        if float(weights.sum()) == 0.0:
            return 0.0

        # 유사도 가중 투표: 비슷한 사람이 그 레시피를 골랐을수록 점수↑
        # (∑ 유사도×선택여부) / ∑유사도  → 0~1 정규화
        selections = matrix[top_indices, recipe_idx]
        return float(np.dot(weights, selections) / weights.sum())

    def recommend_for_user(
        self,
        target_user: str,
        top_n: int = 10,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[tuple[str, float]]:
        """전체 레시피에 대해 CF 점수를 계산하여 상위 N개 (recipe_id, score) 반환.

        주: 본인이 이미 선택한 레시피는 결과에서 제외.
        """
        data = self._get_cached_matrix()
        if data is None or target_user not in data["users"]:
            return []
        users, recipes, matrix = data["users"], data["recipes"], data["matrix"]
        target_idx = users.index(target_user)
        already_selected = set(np.where(matrix[target_idx] > 0)[0])

        similarities = cosine_similarity(matrix)[target_idx].copy()
        similarities[target_idx] = 0.0
        top_user_idx = np.argsort(-similarities)[:top_k]
        weights = similarities[top_user_idx]
        if float(weights.sum()) == 0.0:
            return []

        scores: list[tuple[str, float]] = []
        for recipe_index, recipe_id in enumerate(recipes):
            if recipe_index in already_selected:
                continue
            selections = matrix[top_user_idx, recipe_index]
            score = float(np.dot(weights, selections) / weights.sum())
            if score > 0:
                scores.append((recipe_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]
