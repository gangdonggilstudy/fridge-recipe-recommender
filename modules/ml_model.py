"""사용자별 선택 확률 LR 파사드 — 활성화·재학습 정책만 책임, 나머지는 위임."""
from __future__ import annotations

from pathlib import Path

from .context import compute_month_season_match
from .contracts import LinearContribution
from .db_paths import get_app_db_path
from .ml_training_data import TrainingDataRepository
from .ml_trainer import MLTrainer
from .model_registry import ModelRegistry
from .user_model_store import UserModelStore

ACTIVATION_THRESHOLD = 50
RETRAIN_INTERVAL = 25
LR_MAX_ITER = 1000
# L2 강도 — 누적 데이터로 month vs season 가중치 분배되는 progressive learning 의 핵.
LR_C = 1.0

# (history DB 컬럼, 한글 라벨) 페어 단일 출처 — 순서 어긋남을 컴파일타임에 차단.
FEATURES: tuple[tuple[str, str], ...] = (
    ("ingredient_score",  "재료 일치도"),
    ("consumption_score", "소모 우선순위"),
    ("preference_score",  "선호도"),
    ("context_score",     "상황 적합도"),
    ("month_match",       "월 적합"),
    ("season_match",      "계절 적합"),
)
FEATURE_COLUMNS: tuple[str, ...] = tuple(col for col, _ in FEATURES)
FEATURE_LABELS: list[str] = [label for _, label in FEATURES]
FEATURE_DIM: int = len(FEATURES)


def build_feature(
    scores: dict[str, float],
    recipe: dict | None = None,
    context: dict | None = None,
) -> list[float]:
    """규칙 4점수 + 월·계절 매칭 → 6차원. 매치 계산은 history INSERT 와 단일 출처."""
    base = [
        float(scores.get("ingredient", 0.0)),
        float(scores.get("consumption", 0.0)),
        float(scores.get("preference", 0.0)),
        float(scores.get("context", 0.0)),
    ]
    month = (context or {}).get("month")
    months = (recipe or {}).get("suitable_month") or []
    m_match, s_match = compute_month_season_match(month, months)
    return base + [1.0 if m_match else 0.0, 1.0 if s_match else 0.0]


class MLModel:
    """외부 인터페이스: is_ready / train / predict / linear_contributions / maybe_train."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        threshold: int = ACTIVATION_THRESHOLD,
        registry: ModelRegistry | None = None,
    ):
        self.db_path = Path(db_path) if db_path is not None else get_app_db_path()
        self.threshold = threshold
        self.registry = registry or ModelRegistry()
        self.data_repo = TrainingDataRepository(self.db_path)
        # feature_dim 전달 → 구버전 모델 차원 불일치 자동 무효화.
        self.store = UserModelStore(self.registry, feature_dim=FEATURE_DIM)
        self.trainer = MLTrainer(
            self.data_repo, self.store, FEATURE_LABELS,
            lr_c=LR_C, lr_max_iter=LR_MAX_ITER,
        )

    def is_ready(self, user_id: str) -> bool:
        return self.data_repo.count(user_id) >= self.threshold

    def train(self, user_id: str) -> bool:
        if not self.is_ready(user_id):
            return False
        return self.trainer.train(user_id)

    def maybe_train(self, user_id: str) -> bool:
        """첫 학습: 모델 없음 + count ≥ threshold. 재학습: count − last ≥ INTERVAL.

        구버전 (count == threshold or (count-threshold)%INTERVAL == 0) 은 seed
        60건처럼 그리드 벗어난 사용자가 영영 활성 안 되던 버그(리뷰 H1).
        """
        count = self.data_repo.count(user_id)
        if count < self.threshold:
            return False
        if self.store.get(user_id) is None:
            return self.train(user_id)
        last = self.store.last_trained_size(user_id)
        if last is None or (count - last) >= RETRAIN_INTERVAL:
            return self.train(user_id)
        return False

    def predict(
        self,
        user_id: str,
        scores: dict[str, float],
        recipe: dict,
        context: dict | None = None,
    ) -> float | None:
        return self.trainer.predict(user_id, build_feature(scores, recipe, context))

    def linear_contributions(
        self,
        user_id: str,
        scores: dict[str, float],
        recipe: dict,
        context: dict | None = None,
    ) -> LinearContribution | None:
        """반환: `{"contrib": {라벨: w_i·x_i}, "intercept": b}` 또는 None.

        불변: `intercept + Σ contrib == model.decision_function([x])`.
        """
        return self.trainer.linear_contributions(
            user_id, build_feature(scores, recipe, context),
        )
