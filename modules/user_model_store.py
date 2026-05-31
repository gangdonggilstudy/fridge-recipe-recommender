"""사용자별 모델 — 메모리 캐시 + ModelRegistry 디스크 폴백."""
from __future__ import annotations

from .logging_setup import get_logger
from .model_registry import ModelRegistry

_logger = get_logger(__name__)


class UserModelStore:
    """사용자 LR 모델 메모리 캐시 + 디스크 레지스트리 합성.

    - get(user_id): 메모리 → 디스크 순으로 로드 (feature_dim 불일치 시 무효화)
    - put(user_id, model, ...): 메모리 + 디스크 동시 저장 (feature_dim 메타 기록)
    - last_trained_size(user_id): 메모리 우선, 없으면 메타데이터 조회

    `feature_dim` 을 알면 디스크 로드 시 메타와 비교해 구버전(차원 다른) 모델을
    자동 무효화한다 — 새 피처 추가/제거 후에도 stale 모델이 살아남지 않도록.
    None 으로 만들면 검증 skip (테스트·하위호환 경로).
    """

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        feature_dim: int | None = None,
    ):
        self.registry = registry or ModelRegistry()
        self.feature_dim = feature_dim
        self._models: dict[str, object] = {}
        self._trained_size: dict[str, int] = {}

    def get(self, user_id: str) -> object | None:
        """메모리 → 디스크 순으로 모델 로드. 차원 불일치 모델은 None 반환."""
        model = self._models.get(user_id)
        if model is not None:
            return model
        result = self.registry.load_latest(user_id)
        if result is None:
            return None
        loaded, meta = result
        if self.feature_dim is not None:
            saved_dim = meta.get("feature_dim")
            if saved_dim is not None and int(saved_dim) != self.feature_dim:
                _logger.warning(
                    "디스크 모델 feature_dim 불일치(saved=%s, current=%d) — %s 모델 무효화. 다음 maybe_train 에서 자동 재학습 기대.",
                    saved_dim, self.feature_dim, user_id,
                )
                return None
        self._models[user_id] = loaded
        return loaded

    def put(
        self,
        user_id: str,
        model: object,
        *,
        training_size: int,
        train_accuracy: float,
    ) -> None:
        """메모리 + 디스크 동시 저장. 디스크 실패는 메모리 결과를 유지."""
        self._models[user_id] = model
        self._trained_size[user_id] = int(training_size)
        metadata: dict[str, object] = {
            "model_type":     "lr",
            "training_size":  int(training_size),
            "train_accuracy": round(float(train_accuracy), 4),
        }
        if self.feature_dim is not None:
            metadata["feature_dim"] = self.feature_dim
        try:
            self.registry.save(user_id, model, metadata=metadata)
        except Exception as e:  # noqa: BLE001 — 디스크 I/O 실패는 메모리 학습 결과를 유지하고 흐름 지속
            _logger.warning("ModelRegistry 저장 실패 (학습 결과는 메모리에 유지됨): %s", e)

    def last_trained_size(self, user_id: str) -> int | None:
        """마지막 학습 시 표본 수. 메모리 우선, 없으면 레지스트리 메타."""
        if user_id in self._trained_size:
            return self._trained_size[user_id]
        result = self.registry.load_latest(user_id)
        if result is None:
            return None
        _model, meta = result
        ts = meta.get("training_size")
        return int(ts) if ts is not None else None
