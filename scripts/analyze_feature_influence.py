"""
사용자별 피처 영향 분석 — 어떤 점수 요소가 그 사람의 선택을 끄는가.

누적된 history(선택/미선택 로그)를 (X, y) 로 만들어, 사용자마다:
  1) Logistic Regression 표준화 계수 — 부호 있는 영향력 (양수=그 피처 클수록 선택↑)
  2) Decision Tree feature_importances_ — 모델 기준 중요도 순위
  3) point-biserial 상관 — 모델 무관 교차검증용

피처 벡터는 modules.ml_model 의 학습 파이프라인을 그대로 재사용한다
(분석과 실제 모델이 보는 피처가 어긋나지 않도록).

실행:
    python scripts/analyze_feature_influence.py                 # 임계값 넘는 전체 사용자
    python scripts/analyze_feature_influence.py demo_A          # 특정 사용자만
    python scripts/analyze_feature_influence.py --threshold 30  # 활성화 기준 낮춰서

한계:
- 분석 단위는 '규칙 4개 점수'(재료·소모·선호·상황)다. 원재료 수준은 안 나온다.
- 4개 점수는 규칙 엔진의 상관된 출력이라 LR 계수는 단독 인과로 읽으면 안 된다.
- 표본이 적으면(특히 selected 클래스가 희소하면) 계수 신뢰도가 낮다.
"""

import argparse
import sqlite3
import sys
from contextlib import closing, suppress
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    with suppress(AttributeError, OSError):
        sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.ml_model import FEATURE_LABELS, MLModel  # noqa: E402

APP_DB = PROJECT_ROOT / "data" / "app.db"

# 단일 출처 — XAI 카드(explainer)·블렌더 분해와 동일 라벨을 그대로 재사용
# (modules.ml_model.build_feature 의 5차원 순서와 1:1, 드리프트 방지)
FEATURE_NAMES = FEATURE_LABELS


def eligible_users(db_path: Path, threshold: int) -> list[str]:
    """history 가 threshold 건 이상인 사용자 목록."""
    if not db_path.exists():
        return []
    with closing(sqlite3.connect(db_path)) as con:
        rows = con.execute(
            "SELECT user_id, COUNT(*) AS n FROM history "
            "GROUP BY user_id HAVING n >= ? ORDER BY n DESC",
            (threshold,),
        ).fetchall()
    return [r[0] for r in rows]


def zscore(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """열별 표준화. 분산 0 열은 0 으로 두고 마스크 반환 (계수 해석 제외용)."""
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    zero_var = std == 0
    safe_std = np.where(zero_var, 1.0, std)
    Z = (X - mean) / safe_std
    Z[:, zero_var] = 0.0
    return Z, zero_var


def point_biserial(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """각 피처와 이진 레이블의 상관계수. 분산 0 이면 nan."""
    out = np.full(X.shape[1], np.nan)
    for j in range(X.shape[1]):
        col = X[:, j]
        if col.std() == 0 or y.std() == 0:
            continue
        out[j] = np.corrcoef(col, y)[0, 1]
    return out


def analyze_user(ml: MLModel, user_id: str) -> None:
    X, y = ml.data_repo.load(user_id)  # 학습과 동일 피처 파이프라인 재사용
    n = len(y)
    if n == 0:
        print(f"\n[{user_id}] history 없음 — 건너뜀")
        return
    selected_count = int(y.sum())
    if len(set(y.tolist())) < 2:
        only = "전부 선택" if selected_count == n else "전부 미선택"
        print(f"\n[{user_id}] 표본 {n}건이 {only} — 한 클래스뿐이라 분석 불가")
        return

    Z, zero_var = zscore(X)
    lr = LogisticRegression(max_iter=1000).fit(Z, y)
    lr_coefficients = lr.coef_[0]
    lr_acc = lr.score(Z, y)

    dt = DecisionTreeClassifier(max_depth=5).fit(X, y)
    dt_importances = dt.feature_importances_

    corr = point_biserial(X, y)

    order = np.argsort(-np.abs(lr_coefficients))  # |LR 표준계수| 큰 순

    selected_ratio = selected_count / n
    print(f"\n{'=' * 64}")
    print(f"[{user_id}]  표본 {n}건  ·  선택 {selected_count}건({selected_ratio:.0%})  ·  "
          f"LR 학습정확도 {lr_acc:.2f}")
    print(f"{'=' * 64}")
    print(f"{'피처':<14}{'LR표준계수':>11}  {'방향':<5}{'DT중요도':>9}{'상관':>8}")
    print(f"{'-' * 64}")
    for j in order:
        name = FEATURE_NAMES[j]
        if zero_var[j]:
            print(f"{name:<14}{'  (분산0)':>13}  {'-':<5}"
                  f"{dt_importances[j]:>9.3f}{'-':>8}")
            continue
        coef = lr_coefficients[j]
        arrow = "선택↑" if coef > 0 else "선택↓"
        c = corr[j]
        c_str = f"{c:+.2f}" if not np.isnan(c) else "  -"
        print(f"{name:<14}{coef:>+11.3f}  {arrow:<5}"
              f"{dt_importances[j]:>9.3f}{c_str:>8}")
    print(f"{'-' * 64}")
    top = FEATURE_NAMES[order[0]]
    print(f"→ 이 사용자 선택을 가장 강하게 가르는 요소: {top}")


def main() -> None:
    ap = argparse.ArgumentParser(description="사용자별 피처 영향 분석")
    ap.add_argument("user_id", nargs="?", help="특정 사용자만 분석 (생략 시 전체)")
    ap.add_argument("--db", default=str(APP_DB), help="app.db 경로")
    ap.add_argument("--threshold", type=int, default=50,
                    help="분석 대상 최소 history 건수 (기본 50)")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"app.db 없음: {db_path}", file=sys.stderr)
        sys.exit(1)

    ml = MLModel(db_path=db_path, threshold=args.threshold)

    if args.user_id:
        users = [args.user_id]
    else:
        users = eligible_users(db_path, args.threshold)
        if not users:
            print(f"history {args.threshold}건 이상인 사용자가 없습니다. "
                  f"(scripts/seed_demo.py --with-history 로 시연 데이터 생성 가능)")
            return
        print(f"분석 대상 {len(users)}명: {', '.join(users)}")

    for uid in users:
        analyze_user(ml, uid)


if __name__ == "__main__":
    main()
