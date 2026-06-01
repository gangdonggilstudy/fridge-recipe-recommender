"""DB 파일 경로 단일 출처 — 환경변수 우선 (`APP_DB_PATH`/`RECIPES_DB_PATH`)."""

import os

DEFAULT_APP_DB_PATH = "data/app.db"
DEFAULT_RECIPES_DB_PATH = "data/recipes.db"


def get_app_db_path() -> str:
    return os.getenv("APP_DB_PATH", DEFAULT_APP_DB_PATH)


def get_recipes_db_path() -> str:
    """레시피 카탈로그 (read-only)."""
    return os.getenv("RECIPES_DB_PATH", DEFAULT_RECIPES_DB_PATH)
