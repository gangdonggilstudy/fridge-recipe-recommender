"""테스트·발표 데모용 대량 데이터 종합 시드.

다음을 모두 한 번에 시드:
1. seed_demo: 데모 사용자 3명(demo_A/B/C) 선호 벡터 + 냉장고 재료
2. demo_A/B 에 history 60건씩 (ML 활성화 임계값 50 통과)
3. 관리자 사용자(gangdonggil) 에 history 80건 + 좋아요 다수 — 모니터링·드리프트·ML 모든 화면 진입 시 의미 있는 데이터
4. seed_metrics: 31일치 recommendation_impressions 약 1,870 행 (일별 분포)
5. 추가 좋아요: 인기 레시피 시드 (스타일별·날짜별 분포)

결정적(seed=42). 재실행 가능 — 기존 시드 데이터 clear 후 재시딩.

실행:
    python scripts/seed_full.py        # 전체
    python scripts/seed_full.py --reset # data/app.db 통째 삭제 후 fresh
"""

from __future__ import annotations

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

from modules.db_init import ensure_user, init_db  # noqa: E402
from modules.fridge_repo import FridgeRepo  # noqa: E402
from modules.history_repo import HistoryRepo  # noqa: E402
from modules.like_repo import LikeRepo  # noqa: E402
from modules.preference import PreferenceManager  # noqa: E402

APP_DB = PROJECT_ROOT / "data" / "app.db"

ADMIN_ID = "gangdonggil"   # .env 의 ADMIN_USER_IDS 와 일치
USERS = ["demo_A", "demo_B", "demo_C", "user_x", "user_y", ADMIN_ID]
RECIPES = [f"r{i:03d}" for i in range(1, 41)]   # r001~r040
GROUPS = ["rule", "blender"]
STYLES = ["한식", "양식", "중식", "일식"]
WEATHERS = ["맑음", "비", "눈", "더위", "추위"]


# ── 1. 데모 사용자 선호 벡터 ──

PROFILES = {
    "demo_A": {  # 한식 매운맛
        "한식": 3.0, "양식": 0.0, "중식": 1.0, "일식": 0.0,
        "매운맛": 3.0, "담백함": 0.0, "단맛": 0.0,
        "짭짤함": 0.0, "고소함": 0.0, "감칠맛": 0.0,
        "short": 2.0, "medium": 1.0, "long": 0.0,
    },
    "demo_B": {  # 양식 담백함
        "한식": 0.0, "양식": 3.0, "중식": 0.0, "일식": 1.0,
        "매운맛": 0.0, "담백함": 3.0, "단맛": 1.0,
        "짭짤함": 0.0, "고소함": 0.0, "감칠맛": 0.0,
        "short": 1.0, "medium": 2.0, "long": 0.0,
    },
    ADMIN_ID: {  # 운영자 — 한·중 혼합
        "한식": 2.0, "양식": 0.5, "중식": 2.0, "일식": 0.5,
        "매운맛": 2.0, "담백함": 0.5, "단맛": 0.0,
        "짭짤함": 1.5, "고소함": 0.5, "감칠맛": 1.0,
        "short": 1.5, "medium": 1.5, "long": 0.0,
    },
}

FRIDGE_SETS = {
    "demo_A": [("김치", 3), ("계란", 14), ("밥", None), ("대파", 5), ("두부", 7), ("마늘", 30)],
    "demo_B": [("파스타", None), ("토마토소스", 180), ("양파", 10), ("마늘", 30), ("베이컨", 5), ("생크림", 14)],
    "demo_C": [("김치", 5), ("계란", 10), ("양파", 15), ("파스타", None), ("토마토소스", 90), ("두부", 7)],
    ADMIN_ID: [
        ("김치", 4), ("계란", 7), ("밥", None), ("양파", 12), ("두부", 5),
        ("마늘", 25), ("파스타", None), ("간장", None), ("대파", 6),
    ],
}


# ── 2. history 시드 ──

SEASONAL_SLOTS = [
    ({"hour": 12, "weather": "맑음", "month": "4월"},  ["3월","4월","5월"], ["7월","8월"]),
    ({"hour": 19, "weather": "추위", "month": "1월"},  ["12월","1월","2월"], ["6월","7월","8월"]),
    ({"hour": 8,  "weather": "비",   "month": "10월"}, ["9월","10월","11월"], ["3월","4월","5월"]),
    ({"hour": 22, "weather": "맑음", "month": "7월"},  ["6월","7월","8월"], ["11월","12월","1월"]),
]


def seed_history(history_repo: HistoryRepo, user_id: str, n_total: int, rng: random.Random) -> None:
    """절반은 높은 점수+제철 일치(선택 75%), 절반은 낮은 점수+비제철(선택 15%)."""
    half = n_total // 2
    for i in range(half):
        context, in_season, _ = SEASONAL_SLOTS[i % len(SEASONAL_SLOTS)]
        scores = {
            "ingredient": round(rng.uniform(0.7, 0.95), 2),
            "consumption": round(rng.uniform(0.5, 0.9), 2),
            "preference": round(rng.uniform(0.6, 0.95), 2),
            "context": round(rng.uniform(0.5, 0.9), 2),
        }
        history_repo.log_history(
            user_id, f"r{(i % 40) + 1:03d}", rng.random() < 0.75, scores, context,
            recipe={"suitable_month": in_season},
        )
    for i in range(half):
        context, _, out_season = SEASONAL_SLOTS[i % len(SEASONAL_SLOTS)]
        scores = {
            "ingredient": round(rng.uniform(0.1, 0.4), 2),
            "consumption": round(rng.uniform(0.1, 0.4), 2),
            "preference": round(rng.uniform(0.1, 0.4), 2),
            "context": round(rng.uniform(0.1, 0.4), 2),
        }
        history_repo.log_history(
            user_id, f"r{(i + 500) % 40 + 1:03d}", rng.random() < 0.15, scores, context,
            recipe={"suitable_month": out_season},
        )


# ── 3. impression 시드 (직접 SQL — timestamp 명시 위해) ──

def seed_impressions(con: sqlite3.Connection, days: int, rng: random.Random) -> int:
    """`days` 일치 노출 데이터. 한 세션당 5건 노출, 25% 확률로 그중 1건 선택."""
    today = date.today()
    inserted = 0
    for days_ago in range(days, -1, -1):
        d = today - timedelta(days=days_ago)
        sessions_per_day = rng.randint(5, 20)
        for _ in range(sessions_per_day):
            user_id = rng.choice(USERS)
            session_id = uuid.uuid4().hex
            picked_rank = rng.randint(0, 4) if rng.random() < 0.25 else -1
            chosen = rng.sample(RECIPES, 5)
            hour = rng.randint(8, 22)
            weather = rng.choice(WEATHERS)
            ts_iso = (
                datetime.combine(d, datetime.min.time()) + timedelta(hours=hour)
            ).strftime("%Y-%m-%d %H:%M:%S")
            for rank, recipe_id in enumerate(chosen):
                selected = 1 if rank == picked_rank else 0
                con.execute(
                    """INSERT INTO recommendation_impressions
                       (session_id, user_id, recipe_id, rec_rank, selected, acted,
                        model_group, total_score, hour, weather, month, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id, user_id, recipe_id, rank + 1, selected, selected,
                        rng.choice(GROUPS), round(rng.uniform(0.3, 0.95), 4),
                        hour, weather, f"{d.month}월", ts_iso,
                    ),
                )
                inserted += 1
            con.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,),
            )
    return inserted


# ── 4. 좋아요 시드 ──

def seed_likes(like_repo: LikeRepo, rng: random.Random) -> int:
    """인기 레시피 패턴 — 일부 recipe 에 다수 사용자 좋아요 + 일부 사용자 광범위 좋아요."""
    like_pairs: set[tuple[str, str]] = set()

    # 인기 top 5 레시피: 5명 사용자 모두 좋아요
    popular = rng.sample(RECIPES, 5)
    for r in popular:
        for u in USERS:
            like_pairs.add((u, r))

    # 그 외 30 recipe 에 무작위 1~3 명 좋아요
    for r in rng.sample([x for x in RECIPES if x not in popular], 30):
        for u in rng.sample(USERS, rng.randint(1, 3)):
            like_pairs.add((u, r))

    for u, r in like_pairs:
        # toggle_like 는 INSERT OR UPDATE 라 idempotent. 이미 liked=1 이면 한 번 더 호출 시
        # liked=0 으로 토글되므로, 직접 INSERT 하는 게 안전.
        ensure_user(like_repo.db_path, u)
        with like_repo._connect() as con:
            con.execute(
                """INSERT INTO recipe_likes (user_id, recipe_id, liked, updated_at)
                   VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                   ON CONFLICT (user_id, recipe_id) DO UPDATE SET liked = 1""",
                (u, r),
            )
            con.commit()
    return len(like_pairs)


# ── 5. 전체 시드 ──

def seed_all(reset: bool) -> None:
    rng = random.Random(42)

    if reset and APP_DB.exists():
        APP_DB.unlink()
        # WAL/journal 잔재도 정리
        for ext in (".db-journal", ".db-wal", ".db-shm"):
            p = APP_DB.with_name(APP_DB.name + ext)
            if p.exists():
                p.unlink()
        print(f"[RESET] {APP_DB} 삭제")

    init_db(APP_DB)

    # 1. 선호 + 냉장고
    preference_manager = PreferenceManager(APP_DB)
    fridge = FridgeRepo(APP_DB)
    history_repo = HistoryRepo(APP_DB, init_app_db=False)
    like_repo = LikeRepo(APP_DB)

    for user_id in USERS:
        ensure_user(APP_DB, user_id)
        fridge.clear(user_id)
        preference_manager.save(user_id, {})

    for user_id, vector in PROFILES.items():
        preference_manager.save(user_id, vector)
    print(f"[OK] 선호 벡터: {len(PROFILES)} 사용자")

    today = date.today()
    for user_id, items in FRIDGE_SETS.items():
        for name, days_until_expiry in items:
            expiry = today + timedelta(days=days_until_expiry) if days_until_expiry is not None else None
            fridge.upsert(user_id, name, expiry)
    print(f"[OK] 냉장고: {sum(len(v) for v in FRIDGE_SETS.values())} 행 ({len(FRIDGE_SETS)} 사용자)")

    # 2. history
    history_counts = {"demo_A": 60, "demo_B": 60, ADMIN_ID: 80}
    for user_id, n in history_counts.items():
        seed_history(history_repo, user_id, n, rng)
        actual = history_repo.history_count(user_id)
        print(f"[OK] history: {user_id} → {actual} 건 (ML 활성화 임계값 50 초과)")

    # 3. impressions
    with sqlite3.connect(APP_DB) as con:
        con.execute("DELETE FROM recommendation_impressions")
        inserted = seed_impressions(con, days=30, rng=rng)
        con.commit()
    print(f"[OK] recommendation_impressions: {inserted} 행 (31일)")

    # 4. likes
    n_likes = seed_likes(like_repo, rng)
    print(f"[OK] recipe_likes: {n_likes} 행")

    print(f"\n[DONE] 종합 시드 완료 — {APP_DB.relative_to(PROJECT_ROOT)}")
    print("       streamlit 재기동 후 모니터링 페이지 + 추천 흐름 모두 풍부한 데이터로 동작")


def main() -> None:
    parser = argparse.ArgumentParser(description="테스트·발표용 종합 시드")
    parser.add_argument(
        "--reset", action="store_true",
        help="data/app.db 통째 삭제 후 fresh 시드 (운영 데이터 있으면 주의)",
    )
    args = parser.parse_args()
    seed_all(reset=args.reset)


if __name__ == "__main__":
    main()
