"""추천 평가 메트릭 (NDCG/Recall/HitRate) — `recommendation_impressions` 단일 소스."""
from __future__ import annotations

import math
from pathlib import Path

from ._base_repo import BaseRepository


def ndcg_at_k(ranking: list[float], k: int = 5) -> float:
    """Normalized DCG @ K. ranking[i] ∈ {0, 1}. 결과 [0, 1]."""
    if not ranking or k <= 0:
        return 0.0
    actual = ranking[:k]
    # log2(i+2): 1위 → log2(2)=1 (할인 없음), +1 이면 0 나눗셈.
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(actual))
    ideal = sorted(ranking, reverse=True)[:k]
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def recall_at_k(
    ranking: list[float],
    k: int = 5,
    n_relevant: int | None = None,
) -> float:
    """top-k 관련 항목 / 전체 관련 항목 (`n_relevant` 미지정 시 ranking 의 1 개수)."""
    if not ranking or k <= 0:
        return 0.0
    total = n_relevant if n_relevant is not None else sum(1 for r in ranking if r > 0)
    if total <= 0:
        return 0.0
    hits = sum(1 for r in ranking[:k] if r > 0)
    return hits / total


def hit_rate(rankings: list[list[float]], k: int = 5) -> float:
    """top-k 안에 1+ hit 가진 세션 비율."""
    if not rankings:
        return 0.0
    hit = sum(1 for r in rankings if any(v > 0 for v in r[:k]))
    return hit / len(rankings)


class RecommendEvaluator(BaseRepository):
    def __init__(self, db_path: str | Path | None = None):
        super().__init__(db_path)

    @staticmethod
    def _apply_filters(
        sql: str, user_id: str | None = None, model_group: str | None = None
    ) -> tuple[str, list]:
        """`WHERE 1=1` 기반 SQL 에 user_id·model_group 필터 덧붙이기."""
        args: list = []
        if user_id is not None:
            sql += " AND user_id = ?"
            args.append(user_id)
        if model_group is not None:
            sql += " AND model_group = ?"
            args.append(model_group)
        return sql, args

    @staticmethod
    def _group_selected(rows, key_fn) -> list[list[float]]:
        groups: dict[object, list[float]] = {}
        for r in rows:
            groups.setdefault(key_fn(r), []).append(float(r["selected"] or 0))
        return list(groups.values())

    @staticmethod
    def _aggregate(sessions: list[list[float]], k: int) -> dict[str, float]:
        ndcgs = [ndcg_at_k(s, k) for s in sessions]
        recalls = [recall_at_k(s, k) for s in sessions]
        return {
            "ndcg":     sum(ndcgs) / len(ndcgs),
            "recall":   sum(recalls) / len(recalls),
            "hit_rate": hit_rate(sessions, k),
        }

    def _load_sessions(
        self,
        user_id: str | None = None,
        model_group: str | None = None,
    ) -> list[list[float]]:
        sql, args = self._apply_filters(
            "SELECT user_id, session_id, selected "
            "FROM recommendation_impressions WHERE 1=1",
            user_id, model_group,
        )
        sql += (
            " ORDER BY user_id, timestamp, session_id, "
            "rec_rank IS NULL, rec_rank"
        )
        with self._connect() as con:
            rows = con.execute(sql, args).fetchall()
        return self._group_selected(rows, lambda r: (r["user_id"], r["session_id"]))

    def evaluate(
        self,
        k: int = 5,
        user_id: str | None = None,
        model_group: str | None = None,
    ) -> dict[str, float]:
        """반환 키: ndcg, recall, hit_rate, session_count. 세션 0개면 빈 dict."""
        sessions = self._load_sessions(user_id, model_group)
        if not sessions:
            return {}
        return {**self._aggregate(sessions, k), "session_count": float(len(sessions))}

    def compare_regimes(
        self,
        k: int = 5,
        user_id: str | None = None,
    ) -> dict[str, dict[str, float]]:
        """rule vs blender. delta = blender − rule (양수 = 블렌더 우위)."""
        rule = self.evaluate(k=k, user_id=user_id, model_group="rule")
        blender = self.evaluate(k=k, user_id=user_id, model_group="blender")
        delta: dict[str, float] = {}
        for key in ("ndcg", "recall", "hit_rate"):
            if key in rule and key in blender:
                delta[key] = round(blender[key] - rule[key], 4)
        return {"rule": rule, "blender": blender, "delta": delta}
