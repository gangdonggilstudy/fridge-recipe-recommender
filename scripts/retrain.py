"""
모든 사용자에 대한 ML 모델 일괄 재학습 스크립트.

실행:
    python scripts/retrain.py            # 일회성 실행
    python scripts/retrain.py --user u1  # 특정 사용자만

cron / 작업스케줄러 등록 예 (매일 새벽 3시):
    0 3 * * * cd /path/to/fridge-recipe-recommender && .venv/bin/python scripts/retrain.py
"""

import argparse
import os
import sqlite3
import sys
from contextlib import suppress
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    with suppress(AttributeError, OSError):
        sys.stdout.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - 최소 CLI 폴백
    def load_dotenv(*_args, **_kwargs):
        return False

from modules.ml_model import MLModel  # noqa: E402


load_dotenv(PROJECT_ROOT / ".env")


from modules.db_paths import get_app_db_path  # noqa: E402


def _project_path(raw: str | os.PathLike) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


APP_DB = _project_path(get_app_db_path())


def list_users(db_path: Path) -> list[str]:
    """users 테이블의 전체 user_id 목록."""
    with sqlite3.connect(db_path) as con:
        rows = con.execute("SELECT user_id FROM users").fetchall()
    return [r[0] for r in rows]


def retrain_all(target_user: str | None = None) -> None:
    """전체(또는 지정) 사용자 ML 모델 일괄 재학습. 기록 부족·단일 클래스는 skip."""
    if not APP_DB.exists():
        print(f"[ERROR] app.db 없음: {APP_DB}")
        sys.exit(1)

    model = MLModel(APP_DB)
    users = [target_user] if target_user else list_users(APP_DB)

    if not users:
        print("[INFO] 등록된 사용자 없음")
        return

    success_count = 0
    skip_count = 0
    for user_id in users:
        if not model.is_ready(user_id):
            print(f"  · {user_id}: 기록 부족, skip")
            skip_count += 1
            continue
        ok = model.train(user_id)
        if ok:
            print(f"  ✓ {user_id}: 학습 완료")
            success_count += 1
        else:
            print(f"  · {user_id}: 단일 클래스, skip")
            skip_count += 1

    print(f"\n[DONE] {success_count}명 학습, {skip_count}명 skip")


def main() -> None:
    """CLI: `python scripts/retrain.py [--user X]` — ML 모델 일괄/단일 재학습."""
    parser = argparse.ArgumentParser(description="ML 모델 일괄 재학습")
    parser.add_argument("--user", help="특정 사용자만 학습")
    args = parser.parse_args()
    retrain_all(args.user)


if __name__ == "__main__":
    main()
