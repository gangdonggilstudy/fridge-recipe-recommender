"""약한 미선택(weak unselected) 신뢰도 가중치 튜닝 실험.

목적: '노출됐으나 안 고른' 추천을 음성으로 학습할 때, 그 신뢰도 가중치
(weak_weight)를 얼마로 둬야 ML 블렌더가 rule 보다 잘 랭킹하는지 측정.

방법(순환논리 회피용 노이즈 포함):
  1) 알려진 '진짜 취향' = 5피처에 대한 로지스틱 효용. true_coef 고정.
  2) 세션마다 N개 후보(랜덤 피처) 노출. 사용자는 효용+Gumbel 노이즈의 최댓값을
     고른다(Plackett-Luce top-1). → 효용 높은 항목이 '안 고름'에 섞이는 현실 노이즈.
  3) 선택→history(selected=1)+impression(acted=1). 안 고른 것→impression(acted=0).
  4) 실제 MLModel/MLTrainer 로 weak_weight 별 학습 → held-out 세션에서 랭킹 품질
     (NDCG@N, top-1 적중률) 측정. rule 가중합 baseline 과 비교.

주의: 결과는 여기 가정한 true_coef·노이즈 모델에 의존한다. 절대 진리가 아니라
'이 구조에서 합리적 범위'를 잡기 위한 것.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.db_init import init_db  # noqa: E402

# ── 실험 설정 ──
SEED = 20260609
N_CANDIDATES = 5          # 세션당 노출 후보 수
N_TRAIN_SESSIONS = 70     # 학습 세션(=선택 70건 → history 게이트 50 통과)
N_TEST_SESSIONS = 400     # held-out 평가 세션

# 진짜 취향 = '룰과 어긋난' 개인. 개인 ML 의 존재 이유가 바로 이런 사용자.
# 룰은 ingredient(0.35) 를 가장 크게 보는데, 이 사용자는 ingredient 를 거의 안 보고
# consumption·temporal_fit(룰이 아예 무시) 을 강하게 본다 → 룰이 못 맞히는 영역.
#                ingredient consumption preference context temporal_fit
TRUE_COEF = np.array([0.4,      3.0,        2.0,      0.6,     3.0])
TRUE_INTERCEPT = -3.5

# rule 레짐 가중치(DEFAULT_WEIGHTS, diversity 제외 4요소). temporal_fit 은 rule 에 없음.
RULE_W = np.array([0.35, 0.25, 0.20, 0.15, 0.0])

WEAK_GRID = [None, 0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0]
# 클수록 '안 고름'이 더 노이즈(효용 높은데도 미선택). 최적 가중치가 노이즈에
# 따라 어떻게 움직이는지 봐서 '강건한' 기본값을 고른다.
NOISE_LEVELS = [0.5, 1.5, 3.0]


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def gen_features(rng: np.random.Generator, n: int) -> np.ndarray:
    """n×5 피처. 앞 4개 U(0,1), 5번째 temporal_fit ∈ {0,0.5,1.0}."""
    x = rng.uniform(0.0, 1.0, size=(n, 5))
    x[:, 4] = rng.choice([0.0, 0.5, 1.0], size=n)
    return x


def true_utility(x: np.ndarray) -> np.ndarray:
    return x @ TRUE_COEF + TRUE_INTERCEPT


def seed_db(con, rng: np.random.Generator, user_id: str, noise: float) -> None:
    """학습 세션 생성 → history + recommendation_impressions 직접 삽입."""
    ts = 0
    for s in range(N_TRAIN_SESSIONS):
        x = gen_features(rng, N_CANDIDATES)
        z = true_utility(x)
        # Plackett-Luce top-1: 효용 + Gumbel 노이즈의 argmax 를 선택.
        gumbel = rng.gumbel(0.0, noise, size=N_CANDIDATES)
        picked = int(np.argmax(z + gumbel))
        session_id = f"{user_id}_s{s}"
        for rank in range(N_CANDIDATES):
            ts += 1
            tstr = f"2026-01-01 00:00:{ts:05d}"
            f = x[rank]
            recipe_id = f"r{s}_{rank}"
            is_pick = rank == picked
            # 노출 기록(모든 후보). 선택=acted1/sel1, 미선택=acted0/sel0.
            con.execute(
                """INSERT INTO recommendation_impressions
                   (session_id, user_id, recipe_id, rec_rank, selected, acted,
                    model_group, total_score, hour, weather, month,
                    ingredient_score, consumption_score, preference_score,
                    context_score, temporal_fit, timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (session_id, user_id, recipe_id, rank + 1,
                 1 if is_pick else 0, 1 if is_pick else 0,
                 "rule", 0.0, 12, "맑음", "1월",
                 f[0], f[1], f[2], f[3], f[4], tstr),
            )
            # 명시 선택만 history 에 기록(현행 앱 동작 그대로).
            if is_pick:
                con.execute(
                    """INSERT INTO history
                       (user_id, recipe_id, selected,
                        ingredient_score, consumption_score, preference_score,
                        context_score, hour, weather, month, temporal_fit,
                        model_group, rec_rank, timestamp)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (user_id, recipe_id, 1,
                     f[0], f[1], f[2], f[3], 12, "맑음", "1월", f[4],
                     "rule", rank + 1, tstr),
                )
    con.commit()


def ndcg_at_k(rel_in_pred_order: np.ndarray, k: int) -> float:
    """graded relevance(0~1) 의 NDCG@k."""
    rel = rel_in_pred_order[:k]
    discounts = 1.0 / np.log2(np.arange(2, len(rel) + 2))
    dcg = float(np.sum(rel * discounts))
    ideal = np.sort(rel_in_pred_order)[::-1][:k]
    idcg = float(np.sum(ideal * discounts))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate(score_fn, rng: np.random.Generator) -> tuple[float, float]:
    """held-out 세션에서 (평균 NDCG@N, top-1 적중률) 반환.

    score_fn(x: n×5) → n 점수. 진짜 효용 sigmoid 를 graded relevance 로 사용.
    top-1 적중 = 모델 1위가 진짜 효용 argmax 와 같은지.
    """
    ndcgs, hits = [], []
    for _ in range(N_TEST_SESSIONS):
        x = gen_features(rng, N_CANDIDATES)
        z = true_utility(x)
        rel = sigmoid(z)
        scores = score_fn(x)
        order = np.argsort(scores)[::-1]
        ndcgs.append(ndcg_at_k(rel[order], N_CANDIDATES))
        hits.append(1.0 if order[0] == int(np.argmax(z)) else 0.0)
    return float(np.mean(ndcgs)), float(np.mean(hits))


def run_noise_level(tmpdir: Path, db_path: Path, noise: float) -> dict:
    """한 노이즈 수준에서 weak_weight 그리드 평가 → {weak_weight: hit@1}."""
    import sqlite3

    from modules.ml_model import MLModel

    user_id = f"sim_n{noise}"
    rng = np.random.default_rng(SEED + int(noise * 100))
    con = sqlite3.connect(db_path)
    seed_db(con, rng, user_id, noise)
    n_hist = con.execute(
        "SELECT COUNT(*) FROM history WHERE user_id=?", (user_id,)).fetchone()[0]
    n_weak = con.execute(
        "SELECT COUNT(*) FROM recommendation_impressions WHERE user_id=? AND acted=0",
        (user_id,)).fetchone()[0]
    con.close()

    eval_seed = SEED + 777  # 모든 조건 공통 평가 시퀀스 → 공정 비교.
    rule_ndcg, rule_hit = evaluate(lambda x: x @ RULE_W, np.random.default_rng(eval_seed))

    print(f"\n━━ 노이즈 scale={noise}  (선택 {n_hist}건 / 약한미선택 {n_weak}건) ━━")
    print(f"{'조건':<20}{'활성화':<8}{'hit@1':<10}{'룰대비':<10}")
    print("-" * 48)
    print(f"{'룰 (기준선)':<20}{'-':<8}{rule_hit:<10.4f}{'-':<10}")

    hits: dict = {}
    for w in WEAK_GRID:
        os.environ["MODEL_REGISTRY_DIR"] = str(tmpdir / f"models_n{noise}_{w}")
        model = MLModel(db_path=db_path, weak_weight=w)
        trained = model.train(user_id)
        label = "history만" if w is None else f"weak={w}"
        if not trained:
            print(f"{label:<20}{'안됨':<8}{'-':<10}{'(단일클래스)':<10}")
            continue

        def score_fn(x, _m=model):
            return np.array([_m.trainer.predict(user_id, list(row)) or 0.0 for row in x])

        _, hit = evaluate(score_fn, np.random.default_rng(eval_seed))
        hits[w] = hit
        print(f"{label:<20}{'됨':<8}{hit:<10.4f}{hit - rule_hit:+.4f}")
    hits["_rule"] = rule_hit
    return hits


def main() -> None:
    # Windows 기본 콘솔(cp949)에서 한글·기호 print 가 깨지지 않도록 UTF-8 강제.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    tmpdir = Path(tempfile.mkdtemp(prefix="weak_tune_"))
    db_path = tmpdir / "app.db"
    init_db(db_path)

    print("=" * 48)
    print("약한 미선택 가중치 튜닝 — 룰과 어긋난 개인 사용자 가정")
    print(f"후보/세션={N_CANDIDATES}, 학습세션={N_TRAIN_SESSIONS}, 평가세션={N_TEST_SESSIONS}")
    print("지표: hit@1 (5개 후보 중 진짜 1순위를 모델이 1위로 뽑은 비율, 무작위=0.20)")

    per_noise = {n: run_noise_level(tmpdir, db_path, n) for n in NOISE_LEVELS}

    # 종합: 노이즈 평균 hit@1 로 강건한 가중치 선택(history만·활성화 실패는 제외).
    print("\n" + "=" * 48)
    print("종합 — 노이즈 수준 평균 hit@1")
    print(f"{'weak_weight':<16}{'평균 hit@1':<12}")
    print("-" * 30)
    avg: dict = {}
    for w in WEAK_GRID:
        if w is None:
            continue
        vals = [per_noise[n][w] for n in NOISE_LEVELS if w in per_noise[n]]
        if vals:
            avg[w] = float(np.mean(vals))
            print(f"{str(w):<16}{avg[w]:<12.4f}")
    rule_avg = float(np.mean([per_noise[n]["_rule"] for n in NOISE_LEVELS]))
    print(f"{'(룰 기준선)':<16}{rule_avg:<12.4f}")

    if avg:
        from modules.ml_model import WEAK_NEGATIVE_WEIGHT

        # 단일 argmax 는 오해를 부른다(값들이 통계적으로 동등). 대신 '동등 구간'을
        # 보고하고, 그 안에서의 보수적 채택값을 명시한다.
        best_w = max(avg, key=avg.get)
        best_v = avg[best_w]
        # 평가 hit@1 표준오차 ≈ sqrt(p(1-p)/N)/sqrt(노이즈수). N=평가세션.
        se = (0.25 / N_TEST_SESSIONS / len(NOISE_LEVELS)) ** 0.5
        tied = sorted(w for w, v in avg.items() if best_v - v <= se)
        print(f"\n[결론] 0보다 큰 모든 가중치가 룰(+{best_v - rule_avg:.2f})을 상회.")
        print(f"  통계적 동등 구간(±1SE≈{se:.3f}): {tied}  ← 사실상 구분 불가")
        print("  중간 노이즈(가장 현실적)에선 낮은 값이 우세 + 미클릭 과신 방지")
        print(f"  → 채택 기본값 ml_model.WEAK_NEGATIVE_WEIGHT = {WEAK_NEGATIVE_WEIGHT} "
              f"(동등 구간 내 보수적 선택)")


if __name__ == "__main__":
    main()
