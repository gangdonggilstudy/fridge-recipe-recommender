"""좋아요 CRUD + 추천 점수 가산 (시간 가중 + 로그 saturation)."""

import math
from pathlib import Path

from ._base_repo import BaseRepository
from .db_init import ensure_user


LIKE_BONUS_WEIGHT = 0.05
# 운영 누적 후 좋아요 분포 P75~P90 카운트 기준으로 재조정 (관리자 페이지 권장값).
LIKE_SATURATION_COUNT = 10
# 음식 트렌드 사이클(분기~반년) 가정. 신선도 비율(weighted/raw)로 모니터링.
LIKE_HALFLIFE_DAYS = 180


class LikeRepo(BaseRepository):
    def __init__(self, db_path: str | Path | None = None):
        super().__init__(db_path)

    def toggle_like(self, user_id: str, recipe_id: str) -> bool:
        """좋아요 토글. 새 상태 반환."""
        ensure_user(self.db_path, user_id)
        with self._connect() as con:
            row = con.execute(
                "SELECT liked FROM recipe_likes WHERE user_id = ? AND recipe_id = ?",
                (user_id, recipe_id),
            ).fetchone()
            new_state = 0 if row and row["liked"] else 1
            con.execute(
                """INSERT INTO recipe_likes (user_id, recipe_id, liked, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT (user_id, recipe_id) DO UPDATE SET
                       liked = excluded.liked,
                       updated_at = CURRENT_TIMESTAMP""",
                (user_id, recipe_id, new_state),
            )
            con.commit()
            return bool(new_state)

    def is_liked(self, user_id: str, recipe_id: str) -> bool:
        with self._connect() as con:
            row = con.execute(
                "SELECT liked FROM recipe_likes WHERE user_id = ? AND recipe_id = ?",
                (user_id, recipe_id),
            ).fetchone()
        return bool(row and row["liked"])

    def like_count(self, recipe_id: str) -> int:
        with self._connect() as con:
            row = con.execute(
                "SELECT COUNT(*) AS c FROM recipe_likes WHERE recipe_id = ? AND liked = 1",
                (recipe_id,),
            ).fetchone()
        return int(row["c"]) if row else 0

    def like_weighted_count(self, recipe_id: str) -> float:
        """`Σ 0.5 ** (max(0, Δdays) / HALFLIFE)`. 미래 timestamp 클리핑."""
        with self._connect() as con:
            rows = con.execute(
                """SELECT julianday('now') - julianday(updated_at) AS age_days
                   FROM recipe_likes
                   WHERE recipe_id = ? AND liked = 1""",
                (recipe_id,),
            ).fetchall()
        return sum(
            0.5 ** (max(0.0, float(r["age_days"])) / LIKE_HALFLIFE_DAYS) for r in rows
        )

    def like_bonus(self, recipe_id: str) -> float:
        """`LIKE_BONUS_WEIGHT × log(1+W) / log(1+SAT)`, clipped to [0, W]."""
        weighted = self.like_weighted_count(recipe_id)
        if weighted <= 0:
            return 0.0
        ratio = math.log1p(weighted) / math.log1p(LIKE_SATURATION_COUNT)
        return LIKE_BONUS_WEIGHT * min(1.0, ratio)
