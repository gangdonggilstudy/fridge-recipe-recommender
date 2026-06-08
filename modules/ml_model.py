"""사용자별 선택 확률 LR 파사드 — 활성화·재학습 정책만 책임, 나머지는 위임."""
from __future__ import annotations

from pathlib import Path

from .context import temporal_fit_score
from .contracts import LinearContribution
from .db_paths import get_app_db_path
from .ml_training_data import TrainingDataRepository
from .ml_trainer import MLTrainer
from .model_registry import ModelRegistry
from .user_model_store import UserModelStore

ACTIVATION_THRESHOLD = 50
RETRAIN_INTERVAL = 25
LR_MAX_ITER = 1000
# L2 강도 — 소표본 + 5차원에서 과적합 억제와 신호 보존의 균형.
LR_C = 1.0
# ┌─ AI 가 "사용자가 보고도 안 고른 추천"을 얼마나 신경 쓸지 정하는 값 ─┐
# │  키우면(예 0.3): 더 적극적으로 개인화 (단, 노이즈 과신 위험↑)        │
# │  줄이면(예 0.1): 더 얌전하게 (룰 추천에 가까워짐)                     │
# │  None:          이 기능 끔 — 옛날처럼 '별로에요' 없으면 학습 안 됨     │
# │  권장 0.1~0.3. 바꾸는 법: docs/06_ml_explained.md '가중치를 조정하는 법'│
# └──────────────────────────────────────────────────────────────────┘
# (왜 1.0 이 아니라 0.2? '안 고름'은 '싫음'이 아닐 수 있어 명시 신호 1.0 보다 낮게 둠.
#  scripts/tune_weak_weight.py 실험: 0.05~1.0 모두 룰을 +0.20 상회하며 통계적으로
#  동등 → 중간 노이즈에 강건하고 과신 않는 보수값 0.2 채택. 0 은 퇴화라 금지.)
WEAK_NEGATIVE_WEIGHT: float | None = 0.2

# (history DB 컬럼, 한글 라벨) 페어 단일 출처 — 순서 어긋남을 컴파일타임에 차단.
# 구 month_match·season_match 두 0/1 은 포함관계라 공선 중복 → temporal_fit 서수로 통합.
FEATURES: tuple[tuple[str, str], ...] = (
    ("ingredient_score",  "재료 일치도"),
    ("consumption_score", "소모 우선순위"),
    ("preference_score",  "선호도"),
    ("context_score",     "상황 적합도"),
    ("temporal_fit",      "시기 적합"),
)
FEATURE_COLUMNS: tuple[str, ...] = tuple(col for col, _ in FEATURES)
FEATURE_LABELS: list[str] = [label for _, label in FEATURES]
FEATURE_DIM: int = len(FEATURES)


def build_feature(
    scores: dict[str, float],
    recipe: dict | None = None,
    context: dict | None = None,
) -> list[float]:
    """규칙 4점수 + 시기 적합 서수(0/0.5/1) → 5차원. 계산은 history INSERT 와 단일 출처."""
    # 앞 4개: 규칙 점수를 그대로 피처로 사용.
    base = [
        float(scores.get("ingredient", 0.0)),
        float(scores.get("consumption", 0.0)),
        float(scores.get("preference", 0.0)),
        float(scores.get("context", 0.0)),
    ]
    # 5번째: 시기 적합 서수(0/0.5/1). history 저장 때와 같은 함수를 써서
    # 학습 데이터와 예측 입력이 어긋나지 않게 한다(train/serve skew 방지).
    month = (context or {}).get("month")
    months = (recipe or {}).get("suitable_month") or []
    return base + [temporal_fit_score(month, months)]


class MLModel:
    """외부 인터페이스: is_ready / train / predict / linear_contributions / maybe_train."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        threshold: int = ACTIVATION_THRESHOLD,
        registry: ModelRegistry | None = None,
        weak_weight: float | None = WEAK_NEGATIVE_WEIGHT,
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
            weak_weight=weak_weight,
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
        # 기록이 활성화 임계값(50) 미만이면 아직 학습 안 함 → 룰 레짐 유지.
        if count < self.threshold:
            return False
        # 아직 모델이 없으면 첫 학습.
        if self.store.get(user_id) is None:
            return self.train(user_id)
        # 모델이 있으면 마지막 학습 이후 +25건 이상 쌓였을 때만 재학습.
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
