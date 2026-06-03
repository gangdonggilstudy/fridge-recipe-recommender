"""추천 성능 메트릭 — 선택률 = SUM(selected) / COUNT (`recommendation_impressions`)."""

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

    @staticmethod
    def _finalize_ctr_df(df: pd.DataFrame, *, round_ctr: bool = True) -> pd.DataFrame:
        """selected fillna(0)+int 캐스팅 + ctr 컬럼 계산.

        `round_ctr=False` 는 daily_metrics(시계열 차트 정밀도 보존) 전용.
        """
        if df.empty:
            return df
        df["selected"] = df["selected"].fillna(0).astype(int)
        ctr = df["selected"] / df["shown"]
        df["ctr"] = ctr.round(3) if round_ctr else ctr
        return df

    # ── 전체 ──

    def total_recommendations(self) -> int:
        return self._safe_count(f"SELECT COUNT(*) FROM {_IMPRESSIONS}")

    def total_selections(self) -> int:
        return self._safe_count(
            f"SELECT COUNT(*) FROM {_IMPRESSIONS} WHERE selected = 1",
        )

    def overall_ctr(self) -> float:
        shown = self.total_recommendations()
        return self.total_selections() / shown if shown > 0 else 0.0

    # ── 시계열 ──

    def daily_metrics(self, days_back: int = 30) -> pd.DataFrame:
        """일별 노출 / 선택 / 선택률.

        반환: columns=[date, shown, selected, ctr]
        """
        start_date = (date.today() - timedelta(days=days_back)).isoformat()
        with self._connect() as con:
            df = pd.read_sql(
                f"""SELECT date(timestamp) AS date,
                          COUNT(*) AS shown,
                          SUM(selected) AS selected
                   FROM {_IMPRESSIONS}
                   WHERE date(timestamp) >= ?
                   GROUP BY date(timestamp)
                   ORDER BY date""",
                con,
                params=[start_date],
            )
        # 차트 정밀도 보존 — 라인 차트가 비반올림 값을 그대로 렌더
        return self._finalize_ctr_df(df, round_ctr=False)

    # ── 집계 ──

    def per_user_summary(self) -> pd.DataFrame:
        with self._connect() as con:
            df = pd.read_sql(
                f"""SELECT user_id,
                          COUNT(*) AS shown,
                          SUM(selected) AS selected
                   FROM {_IMPRESSIONS}
                   GROUP BY user_id
                   ORDER BY shown DESC""",
                con,
            )
        return self._finalize_ctr_df(df)

    def per_recipe_summary(self, top_n: int = 20) -> pd.DataFrame:
        with self._connect() as con:
            df = pd.read_sql(
                f"""SELECT recipe_id,
                          COUNT(*) AS shown,
                          SUM(selected) AS selected
                   FROM {_IMPRESSIONS}
                   GROUP BY recipe_id
                   ORDER BY selected DESC, shown DESC
                   LIMIT ?""",
                con,
                params=[int(top_n)],
            )
        return self._finalize_ctr_df(df)

    def per_style_breakdown(self, recipes_db_path: str | Path = "data/recipes.db") -> pd.DataFrame:
        """레시피 스타일별 선택률 (시스템 레시피만, ATTACH 활용)."""
        recipes_path = Path(recipes_db_path)
        if not recipes_path.exists():
            return pd.DataFrame()
        with self._connect() as con:
            # 경로는 운영자 설정값(기본 data/recipes.db)이라 사용자 입력 아님 →
            # f-string ATTACH 안전. as_posix() 로 Windows 역슬래시가 SQL 에서
            # 깨지는 것 방지. JOIN(INNER) 이라 style 없는 커스텀 레시피는
            # 자연히 제외됨 — 스타일별 집계는 시스템 레시피만 의미 있으므로 의도된 동작.
            con.execute(f"ATTACH DATABASE '{recipes_path.as_posix()}' AS r")
            df = pd.read_sql(
                f"""SELECT r.recipes.style,
                          COUNT(*) AS shown,
                          SUM(src.selected) AS selected
                   FROM {_IMPRESSIONS} src
                   JOIN r.recipes ON src.recipe_id = r.recipes.id
                   GROUP BY r.recipes.style
                   ORDER BY shown DESC""",
                con,
            )
        return self._finalize_ctr_df(df)

    # ── 모델 비교 ──

    def per_group_summary(self, group_col: str = "model_group") -> pd.DataFrame:
        """추천 모드(rule/blender) 별 선택률.

        recommendation_impressions.model_group 컬럼 기준 — user_id 해시 기반 A/B 가 아니라 사용자의
        ML 활성화 임계 통과 여부로 자연 분기된 모드별 CTR. (`ABTestManager` 는
        보존된 미사용 모듈.)
        """
        with self._connect() as con:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({_IMPRESSIONS})").fetchall()]
            if group_col not in cols:
                return pd.DataFrame()
            df = pd.read_sql(
                f"""SELECT {group_col} AS grp,
                           COUNT(*) AS shown,
                           SUM(selected) AS selected
                    FROM {_IMPRESSIONS}
                    WHERE {group_col} IS NOT NULL
                    GROUP BY {group_col}""",
                con,
            )
        return self._finalize_ctr_df(df)

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
            top = group.nlargest(top_n, "ctr")
            row: dict = {"구간": dim_val}
            for i, (_, r) in enumerate(top.iterrows(), start=1):
                row[f"{i}위"] = f"{r['name']} ({r['ctr']:.1%})"
            row["노출 수"] = int(group["shown"].sum())
            rows.append(row)
        return pd.DataFrame(rows)
