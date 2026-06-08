"""발표·데모용 시드 — 10명 사용자 × 약 2년치 활동 + ML 모델까지 미리 학습.

생성물 (실제 위치에 직접):
  - data/app.db : 사용자 10명(demo_01~demo_10)의 선호 벡터·냉장고·history·impressions
  - models/<user>/ : 각 사용자의 학습된 개인 AI(.pkl) — maybe_train 으로 미리 구움

핵심 설계:
  - 약 2년(730일)에 걸쳐 사용자별 ~180 세션. timestamp 를 직접 박아 '2년치'를 만든다
    (log_history 는 timestamp=now 라 직접 SQL 사용).
  - 사용자마다 '진짜 취향'(5피처 가중치)이 달라, 그에 맞게 추천을 고른다 → 개인 모델이
    서로 달라짐(개인화 시연).
  - 노출 5개 중 1개 선택 → history(선택) + impression(acted=1). 나머지는 impression
    (acted=0) = ML '약한 미선택' 학습 신호(5피처 동봉). 일부는 '별로에요'(history selected=0).
  - 누적 선택 50건 전까지 model_group='rule', 이후 'blender' 로 기록 → 룰 vs 블렌더 평가 시연.
  - 끝에 maybe_train 호출로 ML 활성화(50건↑ + 클래스 균형) → 데모가 바로 ML 상태.

결정적(seed 고정). 실행:
    python scripts/seed_demo_2y.py          # data/app.db 가 없으면 생성, 있으면 데모 사용자만 갱신
    python scripts/seed_demo_2y.py --reset  # data/app.db + 데모 모델 통째 삭제 후 fresh
"""
from __future__ import annotations

import argparse
import math
import random
import shutil
import sqlite3
import sys
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    with suppress(AttributeError, OSError):
        sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.db_init import ensure_user, init_db  # noqa: E402
from modules.db_paths import get_recipes_db_path  # noqa: E402
from modules.fridge_repo import FridgeRepo  # noqa: E402
from modules.ml_model import ACTIVATION_THRESHOLD, MLModel  # noqa: E402
from modules.model_registry import ModelRegistry  # noqa: E402
from modules.preference import PreferenceManager  # noqa: E402

APP_DB = PROJECT_ROOT / "data" / "app.db"

SEED = 20260609
SPAN_DAYS = 730                 # 약 2년
SESSIONS_PER_USER = 180         # 사용자당 추천 세션 수(≈ 주 1.7회)
CANDIDATES_PER_SESSION = 5
ENGAGE_PROB = 0.85              # 세션에서 무언가 고를 확률
DISLIKE_PROB = 0.10            # 고른 것 중 '별로에요'(history selected=0) 비율
NOISE = 1.2                     # 선택 노이즈(클수록 취향 약하게 반영)

USERS = [f"demo_{i:02d}" for i in range(1, 11)]
WEATHERS = ["맑음", "비", "눈", "더위", "추위"]
STYLE_BY_IDX = ["한식", "양식", "중식", "일식"]
TASTE_BY_IDX = ["매운맛", "담백함", "감칠맛", "고소함", "단맛"]
COOK_BUCKETS = ["short", "medium", "long"]

# 사용자별 '진짜 취향' = 5피처(재료·소모·선호·상황·시기) 가중치. 서로 달라 개인화가 보임.
PERSONA_COEFS = [
    [3.0, 1.0, 2.0, 1.0, 1.0],   # demo_01 재료 중시
    [1.0, 3.0, 2.0, 1.0, 1.0],   # demo_02 유통기한(소모) 중시
    [1.0, 1.0, 3.0, 1.0, 2.0],   # demo_03 취향 + 시기
    [2.0, 2.0, 2.0, 2.0, 1.0],   # demo_04 균형
    [1.0, 1.0, 2.0, 3.0, 1.0],   # demo_05 상황(시간·날씨) 중시
    [3.0, 2.0, 1.0, 1.0, 2.0],   # demo_06
    [1.0, 3.0, 1.0, 2.0, 2.0],   # demo_07
    [2.0, 1.0, 3.0, 1.0, 1.0],   # demo_08
    [1.0, 2.0, 2.0, 1.0, 3.0],   # demo_09 시기 중시
    [2.0, 2.0, 1.0, 2.0, 2.0],   # demo_10
]
PERSONA_INTERCEPT = -3.5


def load_recipe_ids() -> list[str]:
    con = sqlite3.connect(get_recipes_db_path())
    try:
        return [r[0] for r in con.execute("SELECT id FROM recipes ORDER BY id")]
    finally:
        con.close()


def build_preference_vector(idx: int) -> dict[str, float]:
    """사용자 인덱스로 테마(스타일·맛·조리시간) 선호 벡터 생성 — 룰 추천 개인화용."""
    style = STYLE_BY_IDX[idx % len(STYLE_BY_IDX)]
    taste = TASTE_BY_IDX[idx % len(TASTE_BY_IDX)]
    bucket = COOK_BUCKETS[idx % len(COOK_BUCKETS)]
    return {style: 3.0, taste: 2.5, bucket: 2.0}


FRIDGE_TEMPLATES = [
    [("김치", 3), ("계란", 14), ("밥", None), ("대파", 5), ("두부", 7)],
    [("파스타", None), ("토마토소스", 180), ("양파", 10), ("베이컨", 5), ("생크림", 14)],
    [("돼지고기", 4), ("양파", 12), ("마늘", 30), ("간장", None), ("대파", 6)],
    [("두부", 5), ("애호박", 6), ("계란", 10), ("고추장", None), ("밥", None)],
]


def gumbel(rng: random.Random, scale: float) -> float:
    """Gumbel(0, scale) 노이즈 — Plackett-Luce top-1 선택용."""
    u = rng.random()
    # u=0 방어
    u = min(max(u, 1e-12), 1 - 1e-12)
    return -scale * math.log(-math.log(u))


def gen_session_features(rng: random.Random) -> list[list[float]]:
    """세션 후보 5개의 5피처. 앞 4개 U(0,1), 5번째 temporal_fit ∈ {0,0.5,1}."""
    feats = []
    for _ in range(CANDIDATES_PER_SESSION):
        feats.append([
            round(rng.uniform(0.0, 1.0), 3),
            round(rng.uniform(0.0, 1.0), 3),
            round(rng.uniform(0.0, 1.0), 3),
            round(rng.uniform(0.0, 1.0), 3),
            rng.choice([0.0, 0.5, 1.0]),
        ])
    return feats


def seed_user(
    con: sqlite3.Connection,
    user_id: str,
    coef: list[float],
    recipe_ids: list[str],
    rng: random.Random,
) -> tuple[int, int]:
    """한 사용자의 2년치 history + impressions 직접 INSERT. (history건수, 노출건수) 반환."""
    start = datetime.now() - timedelta(days=SPAN_DAYS)
    hist_rows: list[tuple] = []
    imp_rows: list[tuple] = []
    pick_count = 0

    for k in range(SESSIONS_PER_USER):
        # 세션 시각: 2년 구간을 균등 분포 + 지터(시간순 증가 유지).
        frac = (k + rng.uniform(0.0, 0.9)) / SESSIONS_PER_USER
        t = start + timedelta(days=frac * SPAN_DAYS, hours=rng.uniform(0, 12))
        ts = t.strftime("%Y-%m-%d %H:%M:%S")
        month = f"{t.month}월"
        hour = rng.randint(8, 22)
        weather = rng.choice(WEATHERS)
        session_id = f"{user_id}_s{k:04d}"
        # 누적 선택 50건 전후로 서빙 레짐이 바뀐다고 가정(평가 시연용).
        model_group = "blender" if pick_count >= ACTIVATION_THRESHOLD else "rule"

        cands = rng.sample(recipe_ids, CANDIDATES_PER_SESSION)
        feats = gen_session_features(rng)
        utils = [sum(c * f for c, f in zip(coef, feats[i])) + PERSONA_INTERCEPT
                 + gumbel(rng, NOISE) for i in range(CANDIDATES_PER_SESSION)]

        engaged = rng.random() < ENGAGE_PROB
        picked = max(range(CANDIDATES_PER_SESSION), key=lambda i: utils[i]) if engaged else -1
        disliked = picked >= 0 and rng.random() < DISLIKE_PROB

        for rank, rid in enumerate(cands):
            f = feats[rank]
            is_pick = rank == picked
            imp_selected = 1 if (is_pick and not disliked) else 0
            acted = 1 if is_pick else 0
            total = round(sum(coef[j] * f[j] for j in range(5)) / sum(coef), 4)
            imp_rows.append((
                session_id, user_id, rid, rank + 1, imp_selected, acted,
                model_group, total, hour, weather, month,
                f[0], f[1], f[2], f[3], f[4], ts,
            ))
            if is_pick:
                hist_selected = 0 if disliked else 1
                hist_rows.append((
                    user_id, rid, hist_selected,
                    f[0], f[1], f[2], f[3], hour, weather, month, f[4],
                    model_group, rank + 1, ts,
                ))
        if picked >= 0:
            pick_count += 1

    con.executemany(
        """INSERT INTO history
           (user_id, recipe_id, selected, ingredient_score, consumption_score,
            preference_score, context_score, hour, weather, month, temporal_fit,
            model_group, rec_rank, timestamp)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        hist_rows,
    )
    con.executemany(
        """INSERT OR IGNORE INTO recommendation_impressions
           (session_id, user_id, recipe_id, rec_rank, selected, acted,
            model_group, total_score, hour, weather, month,
            ingredient_score, consumption_score, preference_score,
            context_score, temporal_fit, timestamp)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        imp_rows,
    )
    con.commit()
    return len(hist_rows), len(imp_rows)


def clear_demo(con: sqlite3.Connection) -> None:
    """데모 사용자 흔적만 제거(재실행 시 중복 방지). 다른 사용자 데이터는 보존."""
    qmarks = ",".join("?" * len(USERS))
    for table in ("history", "recommendation_impressions", "fridge",
                  "preference_vectors", "recipe_likes", "user_restrictions", "users"):
        con.execute(f"DELETE FROM {table} WHERE user_id IN ({qmarks})", USERS)
    con.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="10명 × 2년치 데모 시드 + ML 학습")
    parser.add_argument("--reset", action="store_true",
                        help="data/app.db + 데모 모델 통째 삭제 후 fresh")
    args = parser.parse_args()
    rng = random.Random(SEED)

    if args.reset:
        for ext in ("", "-wal", "-shm", "-journal"):
            p = APP_DB.with_name(APP_DB.name + ext)
            if p.exists():
                p.unlink()
        print(f"[RESET] {APP_DB.name} 삭제")

    init_db(APP_DB)
    recipe_ids = load_recipe_ids()
    print(f"[OK] 레시피 {len(recipe_ids)}개 로드, 사용자 {len(USERS)}명 시드 시작")

    # 데모 사용자 모델 디렉토리 정리(이전 학습 잔재 제거).
    registry = ModelRegistry()
    for u in USERS:
        with suppress(ValueError, OSError):
            udir = Path(registry.base_dir) / u
            if udir.exists():
                shutil.rmtree(udir)

    pref = PreferenceManager(APP_DB)
    fridge = FridgeRepo(APP_DB)
    today = datetime.now().date()

    con = sqlite3.connect(APP_DB)
    clear_demo(con)
    for u in USERS:
        ensure_user(APP_DB, u)
    total_h = total_i = 0
    for idx, u in enumerate(USERS):
        h, i = seed_user(con, u, PERSONA_COEFS[idx], recipe_ids, rng)
        total_h += h
        total_i += i
    con.close()
    print(f"[OK] history {total_h}건, impressions {total_i}건 (약 2년 분포)")

    # 선호 벡터 + 냉장고
    for idx, u in enumerate(USERS):
        pref.save(u, build_preference_vector(idx))
        for name, days in FRIDGE_TEMPLATES[idx % len(FRIDGE_TEMPLATES)]:
            expiry = today + timedelta(days=days) if days is not None else None
            fridge.upsert(u, name, expiry)
    print(f"[OK] 선호 벡터 + 냉장고: {len(USERS)}명")

    # ML 모델 미리 학습(앱에서 클릭 안 해도 바로 ML 상태가 되도록)
    model = MLModel(db_path=APP_DB)
    trained = 0
    for u in USERS:
        if model.maybe_train(u):
            trained += 1
    print(f"[OK] ML 학습: {trained}/{len(USERS)}명 모델 생성 → {registry.base_dir}/")

    print(f"\n[DONE] 데모 준비 완료 — {APP_DB.relative_to(PROJECT_ROOT)}")
    print("       streamlit 실행 후 사이드바에서 demo_01 ~ demo_10 선택")


if __name__ == "__main__":
    main()
