"""냉장고 재료 영속 (이름 + 유통기한; 양·단위 미수집)."""

import sqlite3
from datetime import date
from pathlib import Path

from ._base_repo import BaseRepository
from .db_init import ensure_user


class FridgeRepo(BaseRepository):
    # expiry_date PARSE_COLNAMES 자동 변환
    detect_types = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES

    def __init__(self, db_path: str | Path | None = None):
        super().__init__(db_path)

    def load(self, user_id: str) -> list[dict]:
        """`updated_at` 은 SELECT 절 제외 — Python 3.12+ timestamp 컨버터 회피."""
        with self._connect() as con:
            rows = con.execute(
                """SELECT ingredient,
                          expiry_date AS "expiry_date [date]"
                   FROM fridge
                   WHERE user_id = ?
                   ORDER BY ingredient""",
                (user_id,),
            ).fetchall()
            return [
                {
                    "name":        r["ingredient"],
                    "expiry_date": r["expiry_date"],
                }
                for r in rows
            ]

    def upsert(
        self,
        user_id: str,
        ingredient: str,
        expiry_date: date | None = None,
    ) -> None:
        """동일 (user_id, ingredient) → expiry 갱신, 없으면 추가."""
        ensure_user(self.db_path, user_id)
        with self._connect() as con:
            con.execute(
                """INSERT INTO fridge (user_id, ingredient, expiry_date, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT (user_id, ingredient) DO UPDATE SET
                       expiry_date = excluded.expiry_date,
                       updated_at = CURRENT_TIMESTAMP""",
                (user_id, ingredient, expiry_date),
            )
            con.commit()

    def delete(self, user_id: str, ingredient: str) -> None:
        with self._connect() as con:
            con.execute(
                "DELETE FROM fridge WHERE user_id = ? AND ingredient = ?",
                (user_id, ingredient),
            )
            con.commit()

    def clear(self, user_id: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM fridge WHERE user_id = ?", (user_id,))
            con.commit()
