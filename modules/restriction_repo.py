"""알레르기·기피 재료 — 추천 hard filter. normalize_ingredient 저장."""

from pathlib import Path
from typing import Literal

from ._base_repo import BaseRepository
from .db_init import ensure_user
from .normalize import normalize_ingredient

ReasonType = Literal["allergy", "avoid"]


class RestrictionRepo(BaseRepository):
    """app.db.user_restrictions 전담 Repository."""

    def __init__(self, db_path: str | Path | None = None):
        super().__init__(db_path)

    # ── CRUD ──

    def add(self, user_id: str, ingredient: str, reason: ReasonType = "avoid") -> None:
        """단일 재료 추가. 정규화 후 저장. 이미 있으면 reason 만 갱신."""
        ensure_user(self.db_path, user_id)
        normalized = normalize_ingredient(ingredient)
        if not normalized:
            return
        with self._connect() as con:
            con.execute(
                """INSERT INTO user_restrictions (user_id, ingredient, reason)
                   VALUES (?, ?, ?)
                   ON CONFLICT (user_id, ingredient) DO UPDATE SET
                       reason = excluded.reason""",
                (user_id, normalized, reason),
            )
            con.commit()

    def replace_all(self, user_id: str, ingredients: list[str], reason: ReasonType = "avoid") -> None:
        """기존 목록을 전체 교체. 온보딩·설정에서 일괄 저장 용도."""
        ensure_user(self.db_path, user_id)
        normalized_set = {
            normalize_ingredient(i) for i in ingredients if normalize_ingredient(i)
        }
        with self._connect() as con:
            con.execute("DELETE FROM user_restrictions WHERE user_id = ?", (user_id,))
            if normalized_set:
                con.executemany(
                    "INSERT INTO user_restrictions (user_id, ingredient, reason) VALUES (?, ?, ?)",
                    [(user_id, ing, reason) for ing in normalized_set],
                )
            con.commit()

    def remove(self, user_id: str, ingredient: str) -> None:
        normalized = normalize_ingredient(ingredient)
        with self._connect() as con:
            con.execute(
                "DELETE FROM user_restrictions WHERE user_id = ? AND ingredient = ?",
                (user_id, normalized),
            )
            con.commit()

    def list_ingredients(self, user_id: str) -> set[str]:
        """제한 재료 집합. Recommender hard filter 에서 사용."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT ingredient FROM user_restrictions WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return {r["ingredient"] for r in rows}

    def list_with_reason(self, user_id: str) -> list[dict]:
        """UI 표시용 — 재료 + reason 함께."""
        with self._connect() as con:
            rows = con.execute(
                """SELECT ingredient, reason FROM user_restrictions
                   WHERE user_id = ?
                   ORDER BY ingredient""",
                (user_id,),
            ).fetchall()
        return [{"ingredient": r["ingredient"], "reason": r["reason"]} for r in rows]

    def clear(self, user_id: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM user_restrictions WHERE user_id = ?", (user_id,))
            con.commit()
