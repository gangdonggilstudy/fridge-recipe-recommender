"""피처×selected 코호트 분석 — Pearson r / 분포 / 글로벌 LR coef (가설 검증)."""

import sqlite3
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression

from ._base_repo import BaseRepository
from .logging_setup import get_logger
from .ml_model import FEATURE_COLUMNS, FEATURE_LABELS  # 5차원 (컬럼·라벨) 단일출처

# 데이터 충분 임계 — 너무 적으면 상관계수/LR 가 의미 없음.
MIN_ROWS_FOR_CORR = 10
MIN_ROWS_FOR_LR = 20

_logger = get_logger(__name__)


class FeatureAnalyzer(BaseRepository):
    """피처×선택 상관관계 분석 (전체 사용자 데이터 통합)."""

    def __init__(self, db_path: str | Path | None = None):
        super().__init__(db_path, init_app_db=False)

    def _load_history_df(self) -> pd.DataFrame:
        """history 의 피처 5컬럼 + selected 를 DataFrame 으로 로드.

        NULL 은 0.0 으로 폴백 — `MLModel._row_to_feature` 의 `or 0.0` 패턴과
        동일 의미. recipe 미전달 INSERT(`temporal_fit` NULL) 호환.

        FEATURE_COLUMNS 가 변경됐는데 DB 마이그레이션이 안 끝난 환경에서도
        대시보드가 깨지지 않도록 OperationalError 는 빈 DataFrame 으로 폴백.
        호출 측은 이미 빈 결과 안내 흐름이 있어 사용자엔 graceful 메시지.
        """
        try:
            with self._connect() as con:
                df = pd.read_sql(
                    f"SELECT {', '.join(FEATURE_COLUMNS)}, selected FROM history",
                    con,
                )
        except (sqlite3.OperationalError, pd.errors.DatabaseError) as e:
            _logger.warning(
                "FeatureAnalyzer: history 피처 컬럼 로드 실패(%s) — 대시보드 분석 폴백. "
                "FEATURE_COLUMNS 와 history 스키마 정합 확인 필요.", e,
            )
            return pd.DataFrame(columns=[*FEATURE_COLUMNS, "selected"])
        return df.fillna(0.0)

    def feature_correlation(self) -> pd.DataFrame:
        """피처 × selected Pearson 상관계수 매트릭스 (한글 라벨).

        반환:
            6×6 DataFrame — 5 피처(한글 라벨) + 'selected'.
            데이터 부족(< MIN_ROWS_FOR_CORR) 또는 selected 분산 0 이면 빈 DataFrame.
        """
        df = self._load_history_df()
        if len(df) < MIN_ROWS_FOR_CORR or df["selected"].nunique() < 2:
            return pd.DataFrame()
        rename_map = dict(zip(FEATURE_COLUMNS, FEATURE_LABELS, strict=True))
        return df.rename(columns=rename_map).corr(method="pearson")

    def feature_distribution(self) -> pd.DataFrame:
        """피처별 selected=선택/미선택 분포 (altair 박스플롯용 long-format).

        반환:
            ['feature', 'selected', 'value'] 컬럼.
            'selected' 값은 한글 라벨('선택'/'미선택') 으로 매핑되어 차트에
            그대로 노출 가능. 데이터 없으면 빈 DataFrame.
        """
        df = self._load_history_df()
        if df.empty:
            return pd.DataFrame(columns=["feature", "selected", "value"])
        rename_map = dict(zip(FEATURE_COLUMNS, FEATURE_LABELS, strict=True))
        long_df = df.rename(columns=rename_map).melt(
            id_vars="selected",
            value_vars=list(FEATURE_LABELS),
            var_name="feature",
            value_name="value",
        )
        long_df["selected"] = long_df["selected"].map({1: "선택", 0: "미선택"})
        return long_df

    def global_lr_coefficients(self) -> dict | None:
        """전체 사용자 history 로 LR 1회 학습한 coef (가설 가중치 검증).

        반환:
            {"coef": {라벨: float}, "intercept": float,
             "accuracy": float, "sample_size": int}
            또는 None — 데이터 부족(< MIN_ROWS_FOR_LR) / 단일 클래스.

        사용자별 `MLModel.train(user_id)` 와는 독립적인 코호트 단위 학습 —
        메모리·디스크 캐시 공유 없음. recency 가중치 미적용(모든 표본 동등).
        """
        df = self._load_history_df()
        if len(df) < MIN_ROWS_FOR_LR or df["selected"].nunique() < 2:
            return None
        X = df[list(FEATURE_COLUMNS)].to_numpy()
        y = df["selected"].to_numpy()
        model = LogisticRegression(max_iter=1000)
        model.fit(X, y)
        coef = dict(zip(FEATURE_LABELS, model.coef_.ravel().tolist(), strict=True))
        return {
            "coef": coef,
            "intercept": float(model.intercept_.ravel()[0]),
            "accuracy": float(model.score(X, y)),
            "sample_size": int(len(df)),
        }
