"""기존 app.db 스키마 보강(추가형 컬럼)을 명시적으로 트리거한다.

실제 마이그레이션 로직은 `modules.db_init._reconcile_columns` 단일 출처에 있고,
`init_db()` 가 매 기동 시 자동 실행한다 — 즉 앱을 그냥 실행하면 자동으로 보강된다.
이 스크립트는 앱을 띄우지 않고 **수동으로** 보강만 하고 싶을 때 쓰는 얇은 래퍼다.

사용: python scripts/migrate_impression_features.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.db_init import init_db  # noqa: E402
from modules.db_paths import get_app_db_path  # noqa: E402

if __name__ == "__main__":
    path = init_db(get_app_db_path())  # CREATE IF NOT EXISTS + 누락 컬럼 ALTER 보강
    print(f"[ok] {path} 스키마 보강 완료 (추가형 컬럼 자동 반영, 멱등)")
