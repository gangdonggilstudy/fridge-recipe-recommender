"""운영자 대시보드용 코호트·시스템 차원 집계 함수 모음 (read-only)."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from .history_repo import HistoryRepo
from .like_repo import LIKE_HALFLIFE_DAYS, LIKE_SATURATION_COUNT, LikeRepo
from .ml_model import ACTIVATION_THRESHOLD
from .model_registry import ModelRegistry
from .user_model_store import UserModelStore


def _iter_user_dirs(registry: ModelRegistry) -> Iterator[Path]:
    """`registry.base_dir` 안 user_id 디렉토리만 안전 순회 (미존재·파일 graceful)."""
    base_dir = registry.base_dir
    if not base_dir.exists():
        return
    for p in base_dir.iterdir():
        if p.is_dir():
            yield p


def _bin_counts(
    values: pd.Series,
    bins: list[tuple[str, float, float]],
    *,
    inclusive_hi: bool,
) -> pd.DataFrame:
    """`inclusive_hi=True` → `lo ≤ x ≤ hi`, False → `lo ≤ x < hi`. bin 정의 순 유지."""
    if inclusive_hi:
        counts = [int(((values >= lo) & (values <= hi)).sum()) for _label, lo, hi in bins]
    else:
        counts = [int(((values >= lo) & (values < hi)).sum()) for _label, lo, hi in bins]
    return pd.DataFrame(
        {"사용자 수": counts},
        index=[label for label, _lo, _hi in bins],
    )


def _user_history_counts(history_repo: HistoryRepo) -> pd.DataFrame:
    with history_repo._connect() as con:
        rows = con.execute(
            "SELECT user_id, COUNT(*) AS history_n FROM history GROUP BY user_id"
        ).fetchall()
    return pd.DataFrame(
        [{"user_id": r["user_id"], "history_n": int(r["history_n"])} for r in rows],
    )


def count_active_users(
    history_repo: HistoryRepo,
    threshold: int = ACTIVATION_THRESHOLD,
) -> int:
    """학습 트리거 가능 풀 크기 — 실제 학습된 모델 수와 다를 수 있음."""
    df = _user_history_counts(history_repo)
    if df.empty:
        return 0
    return int((df["history_n"] >= threshold).sum())


def users_with_models(
    registry: ModelRegistry,
    history_repo: HistoryRepo,
    store: UserModelStore,
) -> pd.DataFrame:
    """history_n / has_model / last_trained_size / versions 표."""
    counts_df = _user_history_counts(history_repo)
    history_users = set(counts_df["user_id"]) if not counts_df.empty else set()
    model_users = {p.name for p in _iter_user_dirs(registry)}

    rows: list[dict] = []
    for user_id in sorted(history_users | model_users):
        n = int(
            counts_df.loc[counts_df["user_id"] == user_id, "history_n"].iloc[0]
            if user_id in history_users
            else 0
        )
        versions = registry.list_versions(user_id)
        rows.append({
            "user_id":            user_id,
            "history_n":          n,
            "has_model":          bool(versions),
            "last_trained_size":  store.last_trained_size(user_id) or 0,
            "versions":           len(versions),
        })
    return pd.DataFrame(rows)


# ACTIVATION_THRESHOLD=50 분기점. 사용자 수 무관 5 막대 표현.
HISTORY_BINS: list[tuple[str, int, int]] = [
    ("0",     0,   0),
    ("1-9",   1,   9),
    ("10-49", 10,  49),
    ("50-99", 50,  99),
    ("100+",  100, 10**9),
]


def history_size_distribution(history_repo: HistoryRepo) -> pd.DataFrame:
    """구간별 사용자 수 (st.bar_chart 호환). 빈 결과면 빈 DataFrame."""
    df = _user_history_counts(history_repo)
    if df.empty:
        return df
    return _bin_counts(df["history_n"], HISTORY_BINS, inclusive_hi=True)


def model_disk_stats(registry: ModelRegistry) -> dict[str, object]:
    """`models/` 디렉토리 사용자 수·파일 수·총 바이트 (KB/MB 환산은 표시 측)."""
    base_dir = registry.base_dir
    if not base_dir.exists():
        return {
            "n_users": 0, "n_files": 0,
            "total_bytes": 0, "base_dir": str(base_dir),
        }
    files = list(base_dir.glob("*/*.pkl"))
    users = {f.parent.name for f in files}
    total = sum(f.stat().st_size for f in files)
    return {
        "n_users": len(users),
        "n_files": len(files),
        "total_bytes": total,
        "base_dir": str(base_dir),
    }


ACCURACY_BINS: list[tuple[str, float, float]] = [
    ("0.0-0.5", 0.0, 0.5),
    ("0.5-0.7", 0.5, 0.7),
    ("0.7-0.9", 0.7, 0.9),
    ("0.9-1.0", 0.9, 1.0 + 1e-9),  # 1.0 포함
]


def recent_training_activity(
    registry: ModelRegistry, limit: int = 10,
) -> pd.DataFrame:
    """최근 학습 모델 `limit` 개 (user_id/version/created_at/training_size/train_accuracy)."""
    rows: list[dict] = []
    for user_dir in _iter_user_dirs(registry):
        for meta in registry.list_versions(user_dir.name):
            rows.append({
                "user_id":        meta.get("user_id", user_dir.name),
                "version":        meta.get("version", ""),
                "created_at":     meta.get("created_at", ""),
                "training_size":  meta.get("training_size", 0),
                "train_accuracy": meta.get("train_accuracy", 0.0),
            })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("created_at", ascending=False).head(limit)
    return df.reset_index(drop=True)


def accuracy_distribution(registry: ModelRegistry) -> dict[str, object]:
    """각 사용자 **최신** 모델의 train_accuracy 통계 + bin 분포.

    반환 키: count, mean, median, bins. 모델 0개면 모든 수치 0.
    """
    accs: list[float] = []
    for user_dir in _iter_user_dirs(registry):
        versions = registry.list_versions(user_dir.name)
        if not versions:
            continue
        acc = versions[0].get("train_accuracy")
        if acc is not None:
            accs.append(float(acc))

    empty_bins = _bin_counts(pd.Series(dtype=float), ACCURACY_BINS, inclusive_hi=False)
    if not accs:
        return {"count": 0, "mean": 0.0, "median": 0.0, "bins": empty_bins}

    series = pd.Series(accs)
    return {
        "count":  int(len(accs)),
        "mean":   float(series.mean()),
        "median": float(series.median()),
        "bins":   _bin_counts(series, ACCURACY_BINS, inclusive_hi=False),
    }


LIKE_COUNT_BINS: list[tuple[str, int, int]] = [
    ("1",     1,   1),
    ("2-3",   2,   3),
    ("4-5",   4,   5),
    ("6-10",  6,   10),
    ("11-20", 11,  20),
    ("21+",   21,  10**9),
]


def like_count_distribution(like_repo: LikeRepo) -> dict[str, object]:
    """좋아요 카운트 분포 + saturation 도달률 + 신선도 + P90 권장 SATURATION.

    반환 키: total_recipes_liked, saturation_count, saturation_rate, percentiles
    (p50/p75/p90/max), bins, recommended_saturation, weighted_total_ratio.
    """
    with like_repo._connect() as con:
        rows = con.execute(
            """SELECT recipe_id,
                      julianday('now') - julianday(updated_at) AS age_days
               FROM recipe_likes
               WHERE liked = 1"""
        ).fetchall()

    empty_bins = pd.DataFrame(
        {"레시피 수": [0] * len(LIKE_COUNT_BINS)},
        index=[label for label, _lo, _hi in LIKE_COUNT_BINS],
    )
    if not rows:
        return {
            "total_recipes_liked":    0,
            "saturation_count":       LIKE_SATURATION_COUNT,
            "saturation_rate":        0.0,
            "percentiles":            {"p50": 0, "p75": 0, "p90": 0, "max": 0},
            "bins":                   empty_bins,
            "recommended_saturation": LIKE_SATURATION_COUNT,
            "weighted_total_ratio":   0.0,
        }

    count_by_recipe: dict[str, int] = defaultdict(int)
    weighted_total = 0.0
    for r in rows:
        count_by_recipe[r["recipe_id"]] += 1
        # like_repo.like_weighted_count 와 동일 클리핑.
        weighted_total += 0.5 ** (max(0.0, float(r["age_days"])) / LIKE_HALFLIFE_DAYS)

    counts = pd.Series(list(count_by_recipe.values()))
    bin_counts = [
        int(((counts >= lo) & (counts <= hi)).sum()) for _label, lo, hi in LIKE_COUNT_BINS
    ]
    bins = pd.DataFrame(
        {"레시피 수": bin_counts},
        index=[label for label, _lo, _hi in LIKE_COUNT_BINS],
    )
    percentiles = {
        "p50": int(counts.quantile(0.5)),
        "p75": int(counts.quantile(0.75)),
        "p90": int(counts.quantile(0.9)),
        "max": int(counts.max()),
    }
    return {
        "total_recipes_liked":    int(len(counts)),
        "saturation_count":       LIKE_SATURATION_COUNT,
        "saturation_rate":        float((counts >= LIKE_SATURATION_COUNT).mean()),
        "percentiles":            percentiles,
        "bins":                   bins,
        "recommended_saturation": max(1, percentiles["p90"]),
        "weighted_total_ratio":   weighted_total / len(rows),
    }


def model_coefficients(
    store: UserModelStore, user_id: str, feature_labels: list[str],
) -> dict[str, object] | None:
    """최신 LR 모델 계수·절편을 피처 라벨에 매핑. 모델 미존재·차원 불일치 시 None."""
    model = store.get(user_id)
    if model is None or not hasattr(model, "coef_") or not hasattr(model, "intercept_"):
        return None
    coef = model.coef_[0]
    if len(coef) != len(feature_labels):
        return None
    return {
        "coef":      {label: float(w) for label, w in zip(feature_labels, coef, strict=True)},
        "intercept": float(model.intercept_[0]),
    }
