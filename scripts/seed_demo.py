"""
시연용 사용자·냉장고 데이터 시딩.

실행:
    python scripts/seed_demo.py                # 기본 (선호 + 냉장고)
    python scripts/seed_demo.py --with-history # + history 60건씩 (ML 학습 가능)

시딩 대상:
- demo_A: 한식 매운맛 선호 + 한식 재료 세트
- demo_B: 양식 담백함 선호 + 양식 재료 세트
- demo_C: 신규 사용자 (선호 벡터 없음) + 혼합 재료 세트

--with-history 옵션 (W3-③):
- demo_A, demo_B 에게 각 60건의 history 자동 생성
- ML 모델 활성화 임계값(50) 초과 → 추천 시 즉시 ML 가중치 적용
- 오프라인 평가도 의미 있는 결과 산출 가능

docs/시연_시나리오.md 의 표준 시연 케이스와 일치한다.
"""

import argparse
import random
import sys
from contextlib import suppress
from datetime import date, timedelta
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    with suppress(AttributeError, OSError):
        sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.fridge_repo import FridgeRepo  # noqa: E402
from modules.history_repo import HistoryRepo  # noqa: E402
from modules.preference import PreferenceManager  # noqa: E402


APP_DB = PROJECT_ROOT / "data" / "app.db"


# ─── 선호 벡터 정의 ───

PROFILES = {
    "demo_A": {
        "한식": 3.0, "양식": 0.0, "중식": 1.0, "일식": 0.0,
        "매운맛": 3.0, "담백함": 0.0, "단맛": 0.0,
        "짭짤함": 0.0, "고소함": 0.0, "감칠맛": 0.0,
        "short": 2.0, "medium": 1.0, "long": 0.0,
    },
    "demo_B": {
        "한식": 0.0, "양식": 3.0, "중식": 0.0, "일식": 1.0,
        "매운맛": 0.0, "담백함": 3.0, "단맛": 1.0,
        "짭짤함": 0.0, "고소함": 0.0, "감칠맛": 0.0,
        "short": 1.0, "medium": 2.0, "long": 0.0,
    },
    # demo_C는 의도적으로 비어둠 (cold-start 시연용)
}


# ─── 냉장고 재료 세트 ───

FRIDGE_SETS = {
    "demo_A": [  # 세트 1: 한식 중심 — (재료명, 만료까지 일수 또는 None)
        ("김치", 3),
        ("계란", 14),
        ("밥", None),
        ("대파", 5),
        ("두부", 7),
        ("마늘", 30),
    ],
    "demo_B": [  # 세트 2: 양식 중심
        ("파스타", None),
        ("토마토소스", 180),
        ("양파", 10),
        ("마늘", 30),
        ("베이컨", 5),
        ("생크림", 14),
    ],
    "demo_C": [  # 세트 3: 혼합
        ("김치", 5),
        ("계란", 10),
        ("양파", 15),
        ("파스타", None),
        ("토마토소스", 90),
        ("두부", 7),
    ],
}


# ─── History 시딩 패턴 (W3-③) ───

# 각 프로필의 행동 패턴 — 높은 점수 + 선택, 낮은 점수 + 미선택 비율을 의미 있게
HISTORY_PATTERNS = {
    "demo_A": {  # 한식·매운맛 선호 — 높은 ingredient/preference 점수 시 선택
        "high_select_ratio": 0.8,   # 점수 높을 때 선택률
        "low_select_ratio": 0.15,   # 점수 낮을 때 선택률
        "n_total": 60,
    },
    "demo_B": {  # 양식·담백함 선호 — 비슷한 패턴
        "high_select_ratio": 0.75,
        "low_select_ratio": 0.2,
        "n_total": 60,
    },
}


def seed_history_for(history_repo: HistoryRepo, user_id: str) -> None:
    """W3-③: ML 학습 가능한 수준의 history 자동 생성."""
    pattern = HISTORY_PATTERNS.get(user_id)
    if pattern is None:
        return

    rng = random.Random(hash(user_id))  # 결정적 (재현 가능)
    n_total = pattern["n_total"]
    half = n_total // 2

    # 3개 컨텍스트 + 각각의 (제철·비제철) recipe 페어 — 블렌더가 시기 적합
    # 차원(5번 피처 temporal_fit)에 가중치를 학습하도록 매치/미스 시그널을 균형 시드.
    seasonal_slots = [
        ({"hour": 12, "weather": "맑음", "month": "4월"},   # 봄
         ["3월", "4월", "5월"], ["7월", "8월"]),
        ({"hour": 19, "weather": "추위", "month": "1월"},   # 겨울
         ["12월", "1월", "2월"], ["6월", "7월", "8월"]),
        ({"hour": 8, "weather": "비", "month": "10월"},     # 가을
         ["9월", "10월", "11월"], ["3월", "4월", "5월"]),
    ]

    # 절반은 높은 점수 + 제철 일치 레시피, 절반은 낮은 점수 + 비제철 레시피
    for i in range(half):
        context, in_season, _ = seasonal_slots[i % 3]
        scores = {
            "ingredient": round(rng.uniform(0.7, 0.95), 2),
            "consumption": round(rng.uniform(0.5, 0.9), 2),
            "preference": round(rng.uniform(0.6, 0.95), 2),
            "context": round(rng.uniform(0.5, 0.9), 2),
        }
        selected = rng.random() < pattern["high_select_ratio"]
        history_repo.log_history(
            user_id, f"r{i:03d}", selected, scores, context,
            recipe={"suitable_month": in_season},
        )

    for i in range(half):
        context, _, out_season = seasonal_slots[i % 3]
        scores = {
            "ingredient": round(rng.uniform(0.1, 0.4), 2),
            "consumption": round(rng.uniform(0.1, 0.4), 2),
            "preference": round(rng.uniform(0.1, 0.4), 2),
            "context": round(rng.uniform(0.1, 0.4), 2),
        }
        selected = rng.random() < pattern["low_select_ratio"]
        history_repo.log_history(
            user_id, f"r{i + 500:03d}", selected, scores, context,
            recipe={"suitable_month": out_season},
        )


def seed(with_history: bool = False) -> None:
    """시연용 데모 사용자·냉장고·선호를 app.db 에 적재. with_history 시 추천 기록도 시딩."""
    preference_manager = PreferenceManager(APP_DB)
    fridge = FridgeRepo(APP_DB)
    history_repo = HistoryRepo(APP_DB, init_app_db=False)

    # 기존 시연 데이터 초기화 (재시딩 가능하도록)
    for user_id in list(PROFILES.keys()) + ["demo_C"]:
        fridge.clear(user_id)
        preference_manager.save(user_id, {})

    # 선호 벡터 적용
    for user_id, vector in PROFILES.items():
        preference_manager.save(user_id, vector)
        print(f"[OK] {user_id} 선호 벡터 저장 ({len(vector)}개 feature)")

    print("[INFO] demo_C 는 cold-start 시연용으로 선호 벡터 없음")

    # 냉장고 시딩
    today = date.today()
    for user_id, items in FRIDGE_SETS.items():
        for name, days in items:
            expiry = today + timedelta(days=days) if days is not None else None
            fridge.upsert(user_id, name, expiry)
        print(f"[OK] {user_id} 냉장고 {len(items)}개 재료 시딩")

    # history 시딩 (W3-③, 옵션)
    if with_history:
        for user_id in HISTORY_PATTERNS:
            seed_history_for(history_repo, user_id)
            n = history_repo.history_count(user_id)
            print(f"[OK] {user_id} history {n}건 시딩 (ML 학습 가능)")
        print("[INFO] demo_C 는 cold-start 시연용으로 history 없음")

    print(f"\n[DONE] 시연 데이터 시딩 완료: {APP_DB.relative_to(PROJECT_ROOT)}")
    print("       streamlit run app.py 로 실행 → 사이드바에서 demo_A / demo_B / demo_C 선택")


def main() -> None:
    """CLI: `python scripts/seed_demo.py [--with-history]` — 시연 데이터 시딩."""
    parser = argparse.ArgumentParser(description="시연 데이터 시딩")
    parser.add_argument(
        "--with-history", action="store_true",
        help="ML 학습 가능한 history 60건씩 추가 (demo_A / demo_B)",
    )
    args = parser.parse_args()
    seed(with_history=args.with_history)


if __name__ == "__main__":
    main()
