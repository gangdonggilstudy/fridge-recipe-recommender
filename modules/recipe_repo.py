"""레시피 카탈로그 조회 (`data/recipes.db` read-only)."""

import sqlite3
from pathlib import Path

from ._base_repo import BaseRepository
from .contracts import Recipe
from .normalize import split_multi


class RecipeRepo(BaseRepository):
    def __init__(self, db_path: str | Path = "data/recipes.db"):
        path = Path(db_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Recipe DB not found: {path}. "
                "Run `python recipes/tools/build_recipes.py` first."
            )
        super().__init__(path, init_app_db=False)

    def _row_to_recipe(self, row: sqlite3.Row, ingredients: list[str]) -> Recipe:
        return {
            "id":               row["id"],
            "name":             row["name"],
            "style":            row["style"],
            "taste":            split_multi(row["taste"]),
            "cook_time":        row["cook_time"],
            "difficulty":       row["difficulty"],
            "suitable_time":    split_multi(row["suitable_time"]),
            "suitable_weather": split_multi(row["suitable_weather"]),
            "suitable_month":   split_multi(row["suitable_month"]),
            "ingredients":      ingredients,
            "review_keywords":  split_multi(row["review_keywords"]) if row["review_keywords"] else [],
            "instructions":     row["instructions"] or "",
        }

    def _ingredients_for(self, con: sqlite3.Connection, recipe_id: str) -> list[str]:
        rows = con.execute(
            "SELECT ingredient FROM recipe_ingredients WHERE recipe_id = ?",
            (recipe_id,),
        ).fetchall()
        return [r["ingredient"] for r in rows]

    def _ingredients_grouped(
        self, con: sqlite3.Connection, recipe_ids: list[str],
    ) -> dict[str, list[str]]:
        """N+1 회피 — list 메서드용 batch."""
        if not recipe_ids:
            return {}
        placeholders = ",".join("?" * len(recipe_ids))
        rows = con.execute(
            f"SELECT recipe_id, ingredient FROM recipe_ingredients WHERE recipe_id IN ({placeholders})",
            recipe_ids,
        ).fetchall()
        return self._group_ingredient_rows(rows)

    def _rows_to_recipes(
        self, con: sqlite3.Connection, rows: list[sqlite3.Row],
    ) -> list[Recipe]:
        ings = self._ingredients_grouped(con, [r["id"] for r in rows])
        return [self._row_to_recipe(r, ings.get(r["id"], [])) for r in rows]

    def get_all(self) -> list[Recipe]:
        with self._connect() as con:
            rows = con.execute("SELECT * FROM recipes").fetchall()
            return self._rows_to_recipes(con, rows)

    def get_by_id(self, recipe_id: str) -> Recipe | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_recipe(row, self._ingredients_for(con, recipe_id))

    def search_by_ingredients(self, owned: set[str]) -> list[Recipe]:
        """보유 재료 1+ 포함 레시피."""
        if not owned:
            return []
        placeholders = ",".join("?" * len(owned))
        sql = f"""
            SELECT DISTINCT r.*
            FROM recipes r
            JOIN recipe_ingredients ri ON r.id = ri.recipe_id
            WHERE ri.ingredient IN ({placeholders})
        """
        with self._connect() as con:
            rows = con.execute(sql, tuple(owned)).fetchall()
            return self._rows_to_recipes(con, rows)

    def get_all_ingredients(self) -> list[str]:
        """자동완성용 통합 목록 (중복 제거, 정렬)."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT DISTINCT ingredient FROM recipe_ingredients ORDER BY ingredient"
            ).fetchall()
            return [r["ingredient"] for r in rows]

    def get_version(self) -> str:
        with self._connect() as con:
            row = con.execute("SELECT value FROM meta WHERE key = 'version'").fetchone()
            return row["value"] if row else "unknown"

    def get_recipe_count(self) -> int:
        with self._connect() as con:
            return con.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
