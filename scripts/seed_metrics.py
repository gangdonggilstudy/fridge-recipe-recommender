"""모니터링 대시보드 그래프 검증용 임의 데이터 시드.

30일치 노출(impression) + 선택 시그널을 사용자·레시피·날짜·시간대·날씨·모델그룹에
골고루 분포시켜 메트릭이 의미 있는 분포로 렌더되는지 확인한다.

실행: python scripts/seed_metrics.py
"""
import argparse
import random
import sqlite3
import sys
import uuid
from contextlib import suppress
from datetime import date, datetime, timedelta
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    with suppress(AttributeError, OSError):
        sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.db_init import init_db  # noqa: E402

APP_DB = PROJECT_ROOT / "data" / "app.db"

USERS = ["demo_A", "demo_B", "demo_C", "user_x", "user_y"]
# 시스템 레시피 ID 풀 — recipes.db 에 실제 존재해야 per_style_breakdown JOIN 동작
RECIPES = [f"r{i:03d}" for i in range(1, 41)]
GROUPS = ["rule", "blender"]
WEATHERS = ["맑음", "비", "눈", "더위", "추위"]


def seed(days: int = 30, sessions_per_day_min: int = 5, sessions_per_day_max: int = 18) -> None:
    """30일 전부터 오늘까지 매일 N개 세션의 추천 노출 + 선택 시그널 생성."""
    init_db(APP_DB)
    random.seed(42)
    today = date.today()
    con = sqlite3.connect(APP_DB)
    con.execute("DELETE FROM recommendation_impressions")
    inserted = 0

    for days_ago in range(days, -1, -1):
        d = today - timedelta(days=days_ago)
        n_sessions = random.randint(sessions_per_day_min, sessions_per_day_max)
        for _ in range(n_sessions):
            user_id = random.choice(USERS)
            session_id = uuid.uuid4().hex
            # 한 세션에 N=5 추천 노출, 그 중 0~1건 선택 (CTR ~ 20%)
            n_show = 5
            chosen_rank = random.randint(1, n_show) if random.random() < 0.25 else None
            sampled = random.sample(RECIPES, n_show)
            group = random.choice(GROUPS)
            hour = random.randint(8, 22)
            weather = random.choice(WEATHERS)
            month_label = f"{d.month}월"
            ts = datetime.combine(d, datetime.min.time()) + timedelta(
                hours=hour, minutes=random.randint(0, 59),
            )
            for rank, recipe_id in enumerate(sampled, start=1):
                selected = 1 if rank == chosen_rank else 0
                con.execute(
                    """INSERT INTO recommendation_impressions
                       (session_id, user_id, recipe_id, rec_rank, selected, acted,
                        model_group, total_score, hour, weather, month, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id, user_id, recipe_id, rank, selected, selected,
                        group, round(random.uniform(0.3, 0.95), 3),
                        hour, weather, month_label, ts.isoformat(timespec="seconds"),
                    ),
                )
                inserted += 1
            # users 테이블 행도 보장 (FK 없음 + ensure_user 가 다른 흐름에서 호출되지만
            # 모니터링이 user_id 표시에 join 안 하므로 필수 아님 — 안전상 추가)
            con.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))

    con.commit()
    con.close()
    print(f"[OK] {inserted} 노출 시그널 시딩 완료 ({days+1} 일치)")


def main() -> None:
    parser = argparse.ArgumentParser(description="모니터링 대시보드 검증용 데이터 시드")
    parser.add_argument("--days", type=int, default=30, help="과거 N일 (오늘 포함)")
    args = parser.parse_args()
    seed(days=args.days)


if __name__ == "__main__":
    main()
