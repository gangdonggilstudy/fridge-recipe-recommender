"""LR 학습 + 예측 + 인스턴스 충실 분해 — 분해 정합성 보장 위해 동일 클래스."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

from .contracts import LinearContribution
from .logging_setup import get_logger
from .ml_training_data import TrainingDataRepository
from .preference import DECAY_RATE
from .user_model_store import UserModelStore

_logger = get_logger(__name__)


class MLTrainer:
    def __init__(
        self,
        data_repo: TrainingDataRepository,
        store: UserModelStore,
        feature_labels: list[str],
        *,
        lr_c: float = 1.0,
        lr_max_iter: int = 1000,
    ):
        self.data_repo = data_repo
        self.store = store
        self.feature_labels = feature_labels
        self.lr_c = lr_c
        self.lr_max_iter = lr_max_iter

    def train(self, user_id: str) -> bool:
        """클래스 한 종류만 있으면 False (모두 선택 또는 모두 미선택)."""
        X, y = self.data_repo.load(user_id)
        # 선택/미선택이 한 종류만 있으면 분류기를 학습할 수 없음 → 보류.
        if len(set(y)) < 2:
            return False

        # 시간순 행에 DECAY_RATE 가중 — 선호 벡터와 동일 0.95 반감기 (recency 일관).
        # np.arange(n-1,...,0) 로 '최신=지수 0=가중치 1.0', 오래될수록 가중치↓.
        n = len(y)
        sample_weight = DECAY_RATE ** np.arange(n - 1, -1, -1)

        # 로지스틱 회귀 학습: X(피처)→y(선택 0/1), 최신 기록을 더 비중 있게.
        model = LogisticRegression(C=self.lr_c, max_iter=self.lr_max_iter)
        model.fit(X, y, sample_weight=sample_weight)
        accuracy = float(model.score(X, y, sample_weight=sample_weight))
        self.store.put(
            user_id, model,
            training_size=int(len(y)),
            train_accuracy=accuracy,
        )
        return True

    def predict(
        self,
        user_id: str,
        features: list[float],
    ) -> float | None:
        """차원 불일치 모델(메모리 잔존 구버전)은 None 폴백 → scorer 가 rule 사용."""
        model = self.store.get(user_id)
        if model is None:
            return None
        x = np.asarray(features, dtype=float)
        coef = getattr(model, "coef_", None)
        if coef is not None and np.asarray(coef).ravel().shape[0] != x.shape[0]:
            _logger.warning(
                "LR predict 차원 불일치 (model=%d, feature=%d) — rule 레짐 폴백",
                np.asarray(coef).ravel().shape[0], x.shape[0],
            )
            return None
        # predict_proba 는 classes_ 순서대로 확률을 반환. 그중 '선택(class=1)' 칸을
        # 찾아 그 확률만 돌려준다.
        probabilities = model.predict_proba(x.reshape(1, -1))[0]
        if 1 in getattr(model, "classes_", []):
            selected_class_index = list(model.classes_).index(1)
            return float(probabilities[selected_class_index])
        return 0.0

    def linear_contributions(
        self,
        user_id: str,
        features: list[float],
    ) -> LinearContribution | None:
        """반환: `{"contrib": {라벨: w_i·x_i}, "intercept": b}` 또는 None.

        불변: `intercept + Σ contrib == model.decision_function([x])`.
        """
        model = self.store.get(user_id)
        if not isinstance(model, LogisticRegression):
            return None
        x = np.asarray(features, dtype=float)
        # 학습된 가중치(coef)와 절편(intercept) 추출.
        coef = np.asarray(model.coef_, dtype=float).ravel()
        intercept = float(np.asarray(model.intercept_, dtype=float).ravel()[0])
        if coef.shape[0] != x.shape[0]:
            _logger.warning(
                "LR 피처 차원 불일치 (model=%d, feature=%d) — rule 레짐 폴백",
                coef.shape[0], x.shape[0],
            )
            return None
        # 피처별 기여도 = 가중치 × 입력값(wᵢ·xᵢ). 라벨을 붙여 반환 →
        # 절편 + 기여도 합 = 모델의 실제 점수(z) 이므로 설명이 거짓이 아님(충실성).
        contrib = {
            self.feature_labels[i]: float(coef[i] * x[i]) for i in range(x.shape[0])
        }
        return {"contrib": contrib, "intercept": intercept}
