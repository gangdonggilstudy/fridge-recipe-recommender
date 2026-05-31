"""커스텀 레시피 CRUD. ID = `c{6 hex}` (시스템 `r001` 와 구분)."""

import sqlite3
import uuid
from pathlib import Path

from ._base_repo import BaseRepository
from .db_init import ensure_user
from .normalize import infer_taste, normalize_ingredient, split_multi, validate_enum


class CustomRecipeRepo(BaseRepository):
    """app.db.custom_recipes 전담 Repository."""

    def __init__(self, db_path: str | Path | None = None):
        super().__init__(db_path)

    @staticmethod
    def _new_id() -> str:
        return f"c{uuid.uuid4().hex[:6]}"

    @staticmethod
    def _encode_list(items: list[str]) -> str:
        return ",".join(items)

    def _row_to_recipe(self, row: sqlite3.Row, ingredients: list[str]) -> dict:
        return {
            "id":               row["id"],
            "author_id":        row["author_id"],
            "name":             row["name"],
            "style":            row["style"],
            "taste":            split_multi(row["taste"]),
            "cook_time":        row["cook_time"],
            "difficulty":       row["difficulty"],
            "suitable_time":    split_multi(row["suitable_time"]),
            "suitable_weather": split_multi(row["suitable_weather"]),
            "suitable_month":   split_multi(row["suitable_month"]),
            "is_shared":        bool(row["is_shared"]),
            "ingredients":      ingredients,
            "review_keywords":  split_multi(row["review_keywords"]) if row["review_keywords"] else [],
            "instructions":     row["instructions"] or "",
            "is_custom":        True,
        }

    def _ingredients_for(self, con: sqlite3.Connection, recipe_id: str) -> list[str]:
        """단일 레시피 재료. `get_by_id` 1회 호출용 — list 케이스는 batch 사용."""
        rows = con.execute(
            "SELECT ingredient FROM custom_recipe_ingredients WHERE recipe_id = ?",
            (recipe_id,),
        ).fetchall()
        return [r["ingredient"] for r in rows]

    def _ingredients_grouped(
        self, con: sqlite3.Connection, recipe_ids: list[str],
    ) -> dict[str, list[str]]:
        """recipe_ids 의 재료를 단일 쿼리로 batch 조회 → recipe_id → [ingredient] 매핑.

        list_by_author / list_shared / search_by_ingredients_for_user 의 N+1 회피.
        """
        if not recipe_ids:
            return {}
        placeholders = ",".join("?" * len(recipe_ids))
        rows = con.execute(
            f"SELECT recipe_id, ingredient FROM custom_recipe_ingredients WHERE recipe_id IN ({placeholders})",
            recipe_ids,
        ).fetchall()
        return self._group_ingredient_rows(rows)

    def _rows_to_recipes(
        self, con: sqlite3.Connection, rows: list[sqlite3.Row],
    ) -> list[dict]:
        """row 목록 → recipe dict 목록. ingredients 단일 batch 쿼리로 매핑."""
        ings = self._ingredients_grouped(con, [r["id"] for r in rows])
        return [self._row_to_recipe(r, ings.get(r["id"], [])) for r in rows]

    # ── CRUD ──

    def add(
        self,
        author_id: str,
        name: str,
        style: str,
        ingredients: list[str],
        cook_time: int = 30,
        difficulty: str = "보통",
        suitable_time: list[str] | None = None,
        suitable_weather: list[str] | None = None,
        suitable_month: list[str] | None = None,
        is_shared: bool = False,
        review_keywords: list[str] | None = None,
        instructions: str = "",
    ) -> str:
        """새 커스텀 레시피 등록. 생성된 ID 반환.

        맛(taste)은 시스템 레시피와 동일하게 재료에서 자동 추론 — 사용자 입력 불필요.
        나머지 enum(style/difficulty/time/weather/month)은 DB 쓰기 전 검증.
        """
        style = validate_enum("style", style)
        difficulty = validate_enum("difficulty", difficulty)
        suitable_time = [validate_enum("time", t) for t in (suitable_time or [])]
        suitable_weather = [validate_enum("weather", w) for w in (suitable_weather or [])]
        suitable_month = [validate_enum("month", m) for m in (suitable_month or [])]

        # 재료 정규화 후 맛 자동 추론 — build_recipes.py 와 동일 정책
        normalized_ings = [normalize_ingredient(i) for i in ingredients if i.strip()]
        taste = infer_taste(normalized_ings)

        ensure_user(self.db_path, author_id)
        recipe_id = self._new_id()

        with self._connect() as con:
            con.execute(
                """INSERT INTO custom_recipes
                   (id, author_id, name, style, taste, cook_time, difficulty,
                    suitable_time, suitable_weather, suitable_month, is_shared,
                    review_keywords, instructions)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    recipe_id, author_id, name, style,
                    self._encode_list(taste),
                    cook_time, difficulty,
                    self._encode_list(suitable_time or []),
                    self._encode_list(suitable_weather or []),
                    self._encode_list(suitable_month or []),
                    1 if is_shared else 0,
                    self._encode_list(review_keywords or []),
                    instructions,
                ),
            )
            for normalized in normalized_ings:
                con.execute(
                    "INSERT OR IGNORE INTO custom_recipe_ingredients VALUES (?, ?)",
                    (recipe_id, normalized),
                )
            con.commit()
        return recipe_id

    def list_by_author(self, author_id: str) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM custom_recipes WHERE author_id = ? ORDER BY created_at DESC",
                (author_id,),
            ).fetchall()
            return self._rows_to_recipes(con, rows)

    def list_shared(self) -> list[dict]:
        """공유된 레시피만."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM custom_recipes WHERE is_shared = 1 ORDER BY created_at DESC"
            ).fetchall()
            return self._rows_to_recipes(con, rows)

    def get_by_id(self, recipe_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM custom_recipes WHERE id = ?", (recipe_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_recipe(row, self._ingredients_for(con, recipe_id))

    def search_by_ingredients_for_user(
        self,
        author_id: str,
        owned: set[str],
    ) -> list[dict]:
        """사용자 본인 레시피 + 다른 사용자가 공유한 레시피 중 매칭."""
        if not owned:
            return []
        placeholders = ",".join("?" * len(owned))
        sql = f"""
            SELECT DISTINCT r.*
            FROM custom_recipes r
            JOIN custom_recipe_ingredients ri ON r.id = ri.recipe_id
            WHERE ri.ingredient IN ({placeholders})
              AND (r.author_id = ? OR r.is_shared = 1)
        """
        with self._connect() as con:
            rows = con.execute(sql, (*owned, author_id)).fetchall()
            return self._rows_to_recipes(con, rows)

    def update_sharing(self, recipe_id: str, is_shared: bool, *, author_id: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE custom_recipes SET is_shared = ? WHERE id = ? AND author_id = ?",
                (1 if is_shared else 0, recipe_id, author_id),
            )
            con.commit()

    @staticmethod
    def cascade_delete_recipe(con: sqlite3.Connection, recipe_id: str) -> None:
        """한 커스텀 레시피의 자식 row 4종 + 본체 삭제. 커밋은 호출자 책임.

        PRAGMA foreign_keys 미설정이라 cascade 수동. 두 호출처(`delete()` 와
        `db_init.delete_user_complete()`)가 같은 정책을 공유하도록 단일 출처화 —
        새 자식 테이블이 생기면 한 곳만 갱신하면 된다.
        """
        con.execute("DELETE FROM recipe_keyword_votes WHERE recipe_id = ?", (recipe_id,))
        con.execute("DELETE FROM recommendation_impressions WHERE recipe_id = ?", (recipe_id,))
        con.execute("DELETE FROM recipe_likes WHERE recipe_id = ?", (recipe_id,))
        con.execute("DELETE FROM custom_recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
        con.execute("DELETE FROM custom_recipes WHERE id = ?", (recipe_id,))

    def delete(self, recipe_id: str, *, author_id: str) -> None:
        with self._connect() as con:
            row = con.execute(
                "SELECT id FROM custom_recipes WHERE id = ? AND author_id = ?",
                (recipe_id, author_id),
            ).fetchone()
            if row:
                self.cascade_delete_recipe(con, recipe_id)
                con.commit()
