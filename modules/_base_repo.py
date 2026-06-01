"""Repository 공통 베이스 — `_connect()` + 그룹핑 헬퍼.

`init_app_db=False` 는 recipes.db 같은 read-only Repo 용.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .db_init import init_db
from .db_paths import get_app_db_path


class BaseRepository:
    # 서브클래스에서 override 가능
    detect_types: int = 0

    def __init__(self, db_path: str | Path | None = None, init_app_db: bool = True):
        self.db_path = Path(db_path) if db_path else get_app_db_path()
        if init_app_db:
            init_db(self.db_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """commit() 은 호출자 책임. PRAGMA: WAL 락 5초 재시도 + FK 안전망."""
        con = sqlite3.connect(self.db_path, detect_types=self.detect_types)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
        finally:
            con.close()

    @staticmethod
    def _group_ingredient_rows(rows: list[sqlite3.Row]) -> dict[str, list[str]]:
        """`recipe_id` + `ingredient` row → 매핑. recipe_repo/custom_recipe_repo 공통."""
        grouped: dict[str, list[str]] = {}
        for r in rows:
            grouped.setdefault(r["recipe_id"], []).append(r["ingredient"])
        return grouped
