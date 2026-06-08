"""추천 성능 메트릭 (`recommendation_impressions` 기반).

- **세션 전환율**(헤드라인·추이) = 1개 이상 선택한 세션 / 전체 세션. "추천 한 번이
  선택으로 이어졌나"(천장 1.0) — 사용자 직관에 가깝다.
- **카드 단위 선택률(CTR)**은 별도 집계 함수 없이 `top_recipes_by_dimension`에서만
  레시피별로 계산 — 표시는 CTR, 정렬은 Wilson 하한(소표본 보정).
- 그 외: `total_recommendations`/`total_selections`(원시 카운트).
"""

import math
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from ._base_repo import BaseRepository
from .context import get_time_label

_IMPRESSIONS = "recommendation_impressions"

# 자연 정렬 (사전 순으로 어색한 경우용).
_MONTH_ORDER: list[str] = [f"{i}월" for i in range(1, 13)]
_WEATHER_ORDER: list[str] = ["맑음", "비", "눈", "더위", "추위"]
_TIME_ORDER: list[str] = ["아침", "점심", "저녁", "야식"]
_DIMENSION_ORDER: dict[str, list[str]] = {
    "month":   _MONTH_ORDER,
    "weather": _WEATHER_ORDER,
    "time":    _TIME_ORDER,
}


def _wilson_lower(k: int, n: int, z: float = 1.96) -> float:
    """Wilson score 구간의 하한(95%). 소표본 고CTR을 보수적으로 강등.

    예: 1/1→≈0.21, 5/5→≈0.57, 20/25→≈0.61. raw CTR(1/1=100%) 정렬이
    소표본 레시피를 과대노출하는 문제를 표본수 반영으로 보정한다.
    """
    if n <= 0:
        return 0.0
    phat = k / n
    denom = 1.0 + z * z / n
    centre = phat + z * z / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return (centre - margin) / denom


class MetricsCalculator(BaseRepository):
    """추천 노출 테이블 기반 성능 집계."""

    def __init__(self, db_path: str | Path | None = None):
        # 읽기 전용 소비자 — 생성 시 init_db 부작용 없이 _connect() 만 위임
        super().__init__(db_path, init_app_db=False)

    # ── 내부 공통 헬퍼 ──

    def _safe_count(self, sql: str, params: tuple = ()) -> int:
        """COUNT(*) 쿼리 → int 정규화 (row 가 None 인 엣지 케이스 안전 처리)."""
        with self._connect() as con:
            row = con.execute(sql, params).fetchone()
        return int(row[0]) if row else 0

    # ── 전체 ──

    def total_recommendations(self) -> int:
        return self._safe_count(f"SELECT COUNT(*) FROM {_IMPRESSIONS}")

    def total_selections(self) -> int:
        return self._safe_count(
            f"SELECT COUNT(*) FROM {_IMPRESSIONS} WHERE selected = 1",
        )

    # ── 세션 단위 전환율 ──
    # CTR(카드 1장당)과 달리, '추천 한 번(세션)에 1개 이상 선택했나'를 본다.
    # 한 세션에 5장을 보여줘도 세션은 1회 → 천장이 0.2 가 아니라 1.0.

    def session_conversion(self) -> float:
        """전환율 = 1개 이상 선택한 세션 / 전체 세션."""
        with self._connect() as con:
            row = con.execute(
                f"""WITH sess AS (
                       SELECT session_id, MAX(selected) AS picked
                       FROM {_IMPRESSIONS} GROUP BY session_id)
                    SELECT COUNT(*) AS sessions, COALESCE(SUM(picked), 0) AS converted
                    FROM sess""",
            ).fetchone()
        sessions = int(row[0]) if row else 0
        converted = int(row[1]) if row else 0
        return converted / sessions if sessions > 0 else 0.0

    def daily_session_conversion(self, days_back: int = 30) -> pd.DataFrame:
        """일별 세션 전환율. columns=[date, sessions, converted, rate]."""
        start_date = (date.today() - timedelta(days=days_back)).isoformat()
        with self._connect() as con:
            df = pd.read_sql(
                f"""WITH sess AS (
                       SELECT session_id,
                              MIN(date(timestamp)) AS date,
                              MAX(selected) AS picked
                       FROM {_IMPRESSIONS}
                       WHERE date(timestamp) >= ?
                       GROUP BY session_id)
                    SELECT date, COUNT(*) AS sessions, SUM(picked) AS converted
                    FROM sess GROUP BY date ORDER BY date""",
                con,
                params=[start_date],
            )
        if df.empty:
            return df
        df["converted"] = df["converted"].fillna(0).astype(int)
        df["rate"] = df["converted"] / df["sessions"]
        return df

    # ── 집계 ──

    # ── 차원별 인기 레시피 (월·날씨·시간대 × recipe) ──

    def top_recipes_by_dimension(
        self,
        dimension: str,
        top_n: int = 3,
        recipes_db_path: str | Path = "data/recipes.db",
    ) -> pd.DataFrame:
        """`dimension` 별 카테고리 row × top_n 레시피 (이름·선택률) 컬럼.

        dimension ∈ {"month", "weather", "time"}. 시간대는 hour 컬럼을 `get_time_label`
        로 라벨링 후 그룹. 자연 정렬 순서(`_DIMENSION_ORDER`)대로 행 배치.
        시스템 레시피는 recipes.db JOIN 으로 이름 표시, 커스텀 또는 미존재는 ID 그대로.
        빈 결과(노출 0)면 빈 DataFrame.
        """
        if dimension not in _DIMENSION_ORDER:
            raise ValueError(
                f"dimension must be one of {list(_DIMENSION_ORDER)}, got {dimension!r}",
            )

        # 1) 차원 × recipe 별 노출·선택 집계
        if dimension == "time":
            with self._connect() as con:
                raw = pd.read_sql(
                    f"""SELECT hour, recipe_id,
                              COUNT(*) AS shown,
                              SUM(selected) AS selected
                       FROM {_IMPRESSIONS}
                       WHERE hour IS NOT NULL
                       GROUP BY hour, recipe_id""",
                    con,
                )
            if raw.empty:
                return pd.DataFrame()
            raw["dim"] = raw["hour"].astype(int).apply(get_time_label)
            agg = raw.groupby(["dim", "recipe_id"], as_index=False).agg(
                shown=("shown", "sum"), selected=("selected", "sum"),
            )
        else:
            col = dimension  # "month" or "weather"
            with self._connect() as con:
                agg = pd.read_sql(
                    f"""SELECT {col} AS dim, recipe_id,
                              COUNT(*) AS shown,
                              SUM(selected) AS selected
                       FROM {_IMPRESSIONS}
                       WHERE {col} IS NOT NULL
                       GROUP BY {col}, recipe_id""",
                    con,
                )
            if agg.empty:
                return pd.DataFrame()

        agg["selected"] = agg["selected"].fillna(0).astype(int)
        agg["ctr"] = agg["selected"] / agg["shown"]
        # 표본 보정: Wilson 하한으로 정렬해 소표본 100%(1/1) 과대노출 방지.
        agg["wilson"] = [
            _wilson_lower(int(k), int(s))
            for k, s in zip(agg["selected"], agg["shown"], strict=True)
        ]

        # 2) 레시피 이름 매핑 (시스템 레시피만 — 커스텀은 ID 유지)
        recipes_path = Path(recipes_db_path)
        if recipes_path.exists():
            import sqlite3  # noqa: PLC0415 — recipes.db 는 별도 연결만 필요
            with sqlite3.connect(recipes_path) as r_con:
                names = pd.read_sql("SELECT id, name FROM recipes", r_con)
            agg = agg.merge(names, left_on="recipe_id", right_on="id", how="left")
            agg["name"] = agg["name"].fillna(agg["recipe_id"])
        else:
            agg["name"] = agg["recipe_id"]

        # 3) 차원 카테고리별 top_n 추출 → 한 행으로 펼침
        order = _DIMENSION_ORDER[dimension]
        rows: list[dict] = []
        for dim_val in order:
            group = agg[agg["dim"] == dim_val]
            if group.empty:
                continue
            top = group.nlargest(top_n, "wilson")
            row: dict = {"구간": dim_val}
            for i, (_, r) in enumerate(top.iterrows(), start=1):
                row[f"{i}위"] = f"{r['name']} ({r['ctr']:.0%}, n={int(r['shown'])})"
            row["노출 수"] = int(group["shown"].sum())
            rows.append(row)
        return pd.DataFrame(rows)
