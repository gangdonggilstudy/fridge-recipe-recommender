"""운영자 대시보드 — 핵심지표 / 사용자·레시피 / ML 운영 / 피처 분석 4탭."""

import pandas as pd
import streamlit as st

from modules.feature_analyzer import FeatureAnalyzer
from modules.history_repo import HistoryRepo
from modules.like_repo import LikeRepo
from modules.metrics import MetricsCalculator
from modules.ml_model import FEATURE_LABELS, MLModel
from modules.ml_ops_stats import (
    accuracy_distribution,
    count_active_users,
    like_count_distribution,
    model_coefficients,
    model_disk_stats,
    recent_training_activity,
    users_with_models,
)
from modules.recommend_eval import RecommendEvaluator

# ── 차트 도움말 콘텐츠 ──────────────────────────────────────────────────────
# key → (dialog 제목, 마크다운 설명). _chart_header()가 ❓ 버튼을 생성하고
# _show_chart_help()가 session_state["_chart_help_key"]를 읽어 표시.
_CHART_HELP: dict[str, tuple[str, str]] = {
    "ctr_trend": (
        "일별 추천 전환율 추이 읽는 법",
        """\
**추천 전환율** = 추천 한 번(세션)에 사용자가 **1개 이상 선택한** 비율 (세션 단위).
카드 1장당 클릭률(CTR)이 아니라 "추천이 결국 선택으로 이어졌나"를 봅니다.

| 수치 | 해석 |
|---|---|
| 상승 추세 | 추천이 점점 잘 맞는 중 |
| 하락 추세 | 취향 변화·콘텐츠 신선도 저하 — 레시피 추가 검토 |
| 높을수록 | 추천 한 번이 선택으로 이어지는 비율↑ |

> 한 세션에 5장을 보여줘도 1장만 골라도 그 세션은 '전환'으로 칩니다(천장 100%).
> 카드당 CTR(5장 중 1장 = 천장 20%)과 다른 지표입니다.
> 소규모 데이터는 날마다 변동이 크니 절댓값보다 **추세(방향)**를 보세요.""",
    ),
    "ml_accuracy": (
        "모델 정확도 분포 읽는 법",
        """\
**train_accuracy** = 학습 데이터로 측정한 in-sample 정확도.

> ⚠ 같은 데이터로 테스트한 낙관적 수치입니다.

| 범위 | 해석 |
|---|---|
| 80~90% | 적정 |
| 90~95% | 주의 — 소표본 과적합 징후 가능 |
| 95% 이상 | 과적합 또는 데이터 부족 |
| 60% 미만 | 선택/미선택 데이터 불균형 확인 |

분포가 좁게 모여있을수록 사용자 전반의 모델 품질이 일관됩니다.""",
    ),
    "like_dist": (
        "좋아요 카운트 분포 읽는 법",
        """\
좋아요를 받은 레시피들의 카운트 분포 + 가산 정책 튜닝 지표.

| 지표 | 의미 |
|---|---|
| **좋아요 받은 레시피** | 좋아요 1+ 받은 레시피 수 |
| **Saturation 도달률** | 좋아요 ≥ `LIKE_SATURATION_COUNT`(=10) 비율. 30% 초과면 상수 상향 검토 |
| **권장 SATURATION (P90)** | 좋아요 분포 P90 카운트. 현재 상수와 차이가 양수로 지속되면 상향 권고 |
| **좋아요 신선도** | 시간 가중 / 절대 카운트 비율. 100% 가까우면 최근 좋아요 비중, 50% 미만이면 오래된 좋아요 비중 ↑ |

가산 식: `bonus = LIKE_BONUS_WEIGHT × log(1+W) / log(1+SATURATION)`, `W = Σ 0.5^(Δdays/180)`. 결과 `0 ≤ bonus ≤ 0.05`.

> 도달률 < 10% → 정상 (차등 신호 살아있음) / > 30% → 상수 상향 검토 / 신선도 < 50% → `LIKE_HALFLIFE_DAYS` 단축 검토.
>
> **시드 데이터(시연 환경)** 에선 좋아요가 모두 `CURRENT_TIMESTAMP` 로 생성돼 신선도 ≈ 100% 가 정상입니다.""",
    ),
    "eval_metrics": (
        "추천 품질 메트릭 읽는 법",
        """\
추천 세션 단위로 측정한 순위 품질 지표.

| 지표 | 의미 | 좋은 값 |
|---|---|---|
| **NDCG@5** | 좋은 레시피가 상위에 오는 순위 품질 | 1에 가까울수록 좋음 |
| **Recall@5** | 선호 레시피가 상위 5개 안에 포함된 비율 | 높을수록 좋음 |
| **Hit Rate@5** | 세션 중 1개 이상 선호 레시피가 상위 5개 안에 든 비율 | 높을수록 좋음 |

NDCG = 1위 선택 > 3위 선택 > 5위 선택 (로그 감쇠 가중치 적용 후 정규화).

> 소규모 데모에서는 절댓값보다 **개선 방향**이 중요합니다.""",
    ),
    "feat_corr": (
        "피처 상관계수 읽는 법",
        """\
각 ML 피처와 사용자 선택 간 **Pearson 상관계수**.

| 범위 | 해석 |
|---|---|
| 0.7 이상 | 강한 양의 상관 — 이 피처↑ → 선택 확률↑ |
| 0.3 ~ 0.7 | 보통 상관 |
| -0.3 ~ 0.3 | 약한 상관 — 선택에 큰 영향 없음 |
| 음수 | 이 피처↑ → 선택 확률↓ |

막대가 길고 양수인 피처가 추천 정확도에 가장 기여합니다.

> Pearson 0.7 기준은 통계학 경험적 분류(Evans 1996). 소표본에서는 기준을 낮게 잡아야 합니다.""",
    ),
    "global_coef": (
        "글로벌 LR 가중치 읽는 법",
        """\
전체 사용자 history를 합쳐 학습한 **Logistic Regression의 피처 가중치**.

개인 모델(사용자별)과 달리 코호트 전체 기반 — 시스템 설계 가설 검증 용도.

| 가중치 | 의미 |
|---|---|
| 양수(+) | 이 피처↑ → 선택 확률↑ |
| 음수(-) | 이 피처↑ → 선택 확률↓ |
| 절댓값 큼 | 추천에 강하게 영향 |
| 0에 가까움 | 선택에 영향 미미 |

> LR = sigmoid를 쓰는 뉴런 1개. 계수 × 피처값이 예측 기여도에 exact하게 대응됩니다.""",
    ),
}


@st.dialog("차트 도움말")
def _show_chart_help() -> None:
    """session_state의 _chart_help_key 를 읽어 해당 차트 설명을 팝업으로 표시."""
    key = st.session_state.get("_chart_help_key", "")
    title, body = _CHART_HELP.get(key, ("", "내용을 찾을 수 없습니다."))
    st.subheader(title)
    st.markdown(body)


def _chart_header(title: str, help_key: str) -> None:
    """차트 제목 + ❓ 도움말 버튼을 한 행에 렌더."""
    col_title, col_btn = st.columns([11, 1])
    col_title.subheader(title)
    if col_btn.button("❓", key=f"help_{help_key}", help="차트 설명 보기"):
        st.session_state["_chart_help_key"] = help_key
        _show_chart_help()


def _render_summary(metrics: MetricsCalculator) -> int:
    """전체 요약 3지표 렌더. 노출 건수(shown) 반환 — 0이면 호출자가 early-return.

    '추천 전환율'은 세션 단위(추천 한 번에 1개 이상 선택). 카드당 CTR 이 아니다.
    """
    shown = metrics.total_recommendations()
    selected = metrics.total_selections()
    conversion = metrics.session_conversion()

    col1, col2, col3 = st.columns(3)
    col1.metric("총 추천 노출(카드)", f"{shown:,}")
    col2.metric("선택된 카드", f"{selected:,}")
    col3.metric(
        "추천 전환율", f"{conversion:.1%}",
        help="추천 한 번(세션)에 1개 이상 선택한 비율 — 세션 단위(카드당 CTR 아님)",
    )
    return shown


def _render_conversion_trend(metrics: MetricsCalculator) -> None:
    """일별 추천 전환율 추이 (최근 30일, 세션 단위)."""
    _chart_header("일별 추천 전환율 추이 (최근 30일)", "ctr_trend")
    daily = metrics.daily_session_conversion(30)
    if daily.empty:
        st.caption("기록이 충분히 쌓이면 그래프가 표시됩니다.")
    else:
        st.line_chart(daily.set_index("date")[["rate"]])
        with st.expander("일별 상세 (rate = 전환 세션 ÷ 전체 세션)"):
            st.dataframe(daily, use_container_width=True, hide_index=True)


def _render_top_by_context(metrics: MetricsCalculator) -> None:
    """🌡 월·날씨·시간대 차원별 카테고리 row × top 3 인기 레시피."""
    st.divider()
    st.subheader("🌡 상황별 인기 레시피")
    st.caption(
        "월·날씨·시간대 각 카테고리에서 어떤 레시피가 가장 잘 선택됐는지 top 3. "
        "선택률 = selected ÷ shown (그 카테고리 안 노출 기준)."
    )
    label_to_dim = {"월": "month", "날씨": "weather", "시간대": "time"}
    choice = st.radio(
        "차원", options=list(label_to_dim),
        horizontal=True, key="ctx_top_dim",
    )
    df = metrics.top_recipes_by_dimension(label_to_dim[choice], top_n=3)
    if df.empty:
        st.info("기록이 쌓이면 표시됩니다.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def _render_ml_ops(
    history_repo: HistoryRepo, ml_model: MLModel, like_repo: LikeRepo,
) -> None:
    """시스템 차원 ML 운영 통계 — 활성화 사용자·모델 상태·디스크·좋아요 분포."""
    active = count_active_users(history_repo)
    disk = model_disk_stats(ml_model.registry)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("활성화 사용자", f"{active}명")
    col_b.metric("학습된 모델", f"{disk['n_users']}명 / {disk['n_files']}개 파일")
    mb = disk["total_bytes"] / (1024 * 1024)
    col_c.metric("모델 디스크", f"{mb:.2f} MB")
    st.caption(
        f"활성화 사용자 = history ≥ {ml_model.threshold}건 누적. "
        "학습된 모델 ≠ 활성화 사용자 — 임계값 통과 후 아직 학습 트리거 안 된 경우 차이."
    )

    st.divider()
    st.subheader("사용자별 모델 상태")
    df = users_with_models(ml_model.registry, history_repo, ml_model.store)
    if df.empty:
        st.info("기록·모델 데이터가 쌓이면 표시됩니다.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

    _render_ml_drilldown(ml_model)
    _render_recent_training(ml_model)
    _render_accuracy_dist(ml_model)
    _render_like_distribution(like_repo)

    st.caption(f"모델 저장 경로: `{disk['base_dir']}`")


def _render_ml_drilldown(ml_model: MLModel) -> None:
    """🔍 사용자 모델 드릴다운 — 버전 이력 + 최신 모델 피처 가중치."""
    st.divider()
    st.subheader("🔍 사용자 모델 드릴다운")
    st.caption(
        "특정 사용자를 선택하면 모델 버전 이력과 최신 LR 계수를 표시. "
        "운영자가 '왜 이 사용자에게 이런 추천이 가나' 즉답하는 용도."
    )

    base_dir = ml_model.registry.base_dir
    candidates = (
        sorted(p.name for p in base_dir.iterdir() if p.is_dir())
        if base_dir.exists()
        else []
    )
    if not candidates:
        st.info("학습된 모델이 있어야 표시됩니다.")
        return

    selected = st.selectbox("사용자 선택", options=candidates, key="ml_drilldown_user")
    if not selected:
        return

    versions = ml_model.registry.list_versions(selected)
    if versions:
        v_df = pd.DataFrame([
            {
                "version":         v.get("version", ""),
                "created_at":      v.get("created_at", ""),
                "training_size":   v.get("training_size", 0),
                "train_accuracy":  v.get("train_accuracy", 0.0),
            }
            for v in versions
        ])
        st.write(f"**{selected} 버전 이력 ({len(versions)}건)**")
        st.dataframe(v_df, use_container_width=True, hide_index=True)

    coef_info = model_coefficients(ml_model.store, selected, FEATURE_LABELS)
    if coef_info is not None:
        st.write(f"**최신 모델 가중치** · 절편 `{coef_info['intercept']:+.3f}`")
        coef_df = pd.DataFrame(
            [{"피처": label, "가중치": w} for label, w in coef_info["coef"].items()],
        )
        st.bar_chart(coef_df.set_index("피처"))
    else:
        st.caption("선형 모델(LR)이 아니거나 차원 불일치로 가중치 표시 불가.")


def _render_recent_training(ml_model: MLModel) -> None:
    """⏱ 최근 학습 활동 — 모든 사용자 가로지른 최근 학습 10개."""
    st.divider()
    st.subheader("⏱ 최근 학습 활동")
    st.caption(
        "모든 사용자에 걸쳐 가장 최근 학습된 모델 10개. "
        "운영 중 '언제 누가 학습됐나' 시계열 가시화."
    )
    df = recent_training_activity(ml_model.registry, limit=10)
    if df.empty:
        st.info("학습된 모델이 없습니다.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def _render_accuracy_dist(ml_model: MLModel) -> None:
    """🎯 모델 정확도 분포 — 평균·중위 + bin 카운트 (사용자 수 무관)."""
    st.divider()
    _chart_header("🎯 모델 정확도 분포", "ml_accuracy")
    st.caption(
        "활성화 사용자 최신 모델의 train_accuracy 분포 — 코호트 모델 품질 일관성 점검."
    )
    stats = accuracy_distribution(ml_model.registry)
    if stats["count"] == 0:
        st.info("학습된 모델이 없습니다.")
        return

    col_n, col_m, col_med = st.columns(3)
    col_n.metric("모델 수", f"{stats['count']}")
    col_m.metric("평균 정확도", f"{stats['mean']:.1%}")
    col_med.metric("중위 정확도", f"{stats['median']:.1%}")
    st.bar_chart(stats["bins"])


def _render_like_distribution(like_repo: LikeRepo) -> None:
    """❤️ 좋아요 카운트 분포 — saturation 도달률 + 신선도 + 운영자 튜닝 권고값.

    `LIKE_SATURATION_COUNT` 상수는 시드 데이터 추정치이므로, 좋아요가 누적되면
    P90 카운트 기반 권장값을 보고 상수를 재조정한다.
    """
    st.divider()
    _chart_header("❤️ 좋아요 카운트 분포", "like_dist")
    st.caption(
        "레시피별 좋아요 카운트 분포 + 가산 정책의 saturation 도달률. "
        "도달률 30% 초과면 SATURATION 상향, 권장값과 격차 지속 시 재조정. "
        "시드 환경에선 신선도 ≈ 100% 가 정상."
    )
    stats = like_count_distribution(like_repo)
    if stats["total_recipes_liked"] == 0:
        st.info("아직 좋아요 데이터가 없습니다.")
        return

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("좋아요 받은 레시피", stats["total_recipes_liked"])
    col_b.metric(
        "Saturation 도달률",
        f"{stats['saturation_rate']:.0%}",
        help=f"좋아요 ≥ {stats['saturation_count']}명 비율. "
             "30% 초과면 LIKE_SATURATION_COUNT 상향 검토.",
    )
    col_c.metric(
        "권장 SATURATION (P90)",
        stats["recommended_saturation"],
        delta=stats["recommended_saturation"] - stats["saturation_count"],
        help="현재 상수와 차이. 양수 격차가 지속되면 상수 상향 권고.",
    )
    col_d.metric(
        "좋아요 신선도",
        f"{stats['weighted_total_ratio']:.0%}",
        help="시간 가중 / 절대 카운트 비율. 100% 가까우면 최근 좋아요, "
             "50% 미만이면 오래된 좋아요 비중 큼 — LIKE_HALFLIFE_DAYS 검토.",
    )
    st.bar_chart(stats["bins"])
    p = stats["percentiles"]
    st.caption(
        f"P50={p['p50']} / P75={p['p75']} / P90={p['p90']} / max={p['max']}"
    )


def _render_eval_metrics(evaluator: RecommendEvaluator | None) -> None:
    """추천 품질 메트릭 (NDCG/Recall/HitRate) — 노출 로그 기반 세션 단위."""
    if evaluator is not None:
        st.divider()
        _chart_header("📐 추천 품질 메트릭", "eval_metrics")
        st.caption(
            "추천 세션 단위로 평가한 순위 품질 지표. "
            "노출 로그(session_id/rec_rank) 기준으로 계산합니다."
        )
        with st.expander("전체 평가 (모든 사용자)", expanded=False):
            result = evaluator.evaluate(k=5)
            if not result:
                st.info("기록이 충분히 쌓이면 표시됩니다.")
            else:
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("NDCG@5", f"{result['ndcg']:.3f}")
                col_b.metric("Recall@5", f"{result['recall']:.3f}")
                col_c.metric("Hit Rate@5", f"{result['hit_rate']:.1%}")
                col_d.metric("세션 수", f"{int(result['session_count']):,}")


def _render_feature_correlation(analyzer: FeatureAnalyzer) -> None:
    """피처 × selected Pearson 상관계수 — selected 행을 막대 차트로 노출.

    매트릭스 전체보다 'selected 와의 상관' 만 한 줄로 추출하는 게 의사결정에
    가장 직관적 (어느 피처가 선택과 가장 강하게 연동되는가).
    """
    _chart_header("🔬 피처 × 선택 Pearson 상관계수", "feat_corr")
    st.caption(
        "각 피처가 사용자 선택과 얼마나 상관 있는지. "
        "값이 1 에 가까울수록 강한 양의 상관, -1 에 가까우면 음의 상관."
    )
    corr = analyzer.feature_correlation()
    if corr.empty:
        st.info("기록이 10건 이상 쌓이고 선택/미선택이 모두 있어야 표시됩니다.")
        return

    sel_corr = corr["selected"].drop(labels="selected", errors="ignore")
    sel_df = (
        pd.DataFrame({"피처": sel_corr.index, "selected 상관계수": sel_corr.values})
        .sort_values(
            "selected 상관계수",
            key=lambda s: s.abs(),
            ascending=False,
        )
    )
    st.bar_chart(sel_df.set_index("피처"))
    with st.expander("전체 상관계수 매트릭스 (히트맵)"):
        import altair as alt  # noqa: PLC0415 — lazy (streamlit transitive)

        # 7×7 매트릭스 → long-format (피처1, 피처2, corr) 49 행
        long_corr = (
            corr.round(3)
                .stack()
                .reset_index()
                .rename(columns={"level_0": "피처1", "level_1": "피처2", 0: "corr"})
        )
        axis_order = list(corr.columns)
        base = alt.Chart(long_corr).encode(
            x=alt.X("피처1:N", title=None, sort=axis_order),
            y=alt.Y("피처2:N", title=None, sort=axis_order),
        )
        heat = base.mark_rect().encode(
            color=alt.Color(
                "corr:Q",
                scale=alt.Scale(scheme="redblue", domain=[-1, 1]),
                title="상관계수",
            ),
            tooltip=["피처1", "피처2", "corr"],
        )
        # 셀 안 숫자 overlay — 짙은 색 셀은 흰 글씨, 연한 색은 검정으로 대비.
        text = base.mark_text(baseline="middle").encode(
            text="corr:Q",
            color=alt.condition(
                "abs(datum.corr) > 0.5", alt.value("white"), alt.value("black"),
            ),
        )
        st.altair_chart(heat + text, use_container_width=True)


def _render_global_lr_coef(analyzer: FeatureAnalyzer) -> None:
    """전체 사용자 LR 학습 가중치 (코호트 단위 가설 가중치 검증)."""
    _chart_header("🌐 글로벌 LR 가중치 (전체 사용자 코호트)", "global_coef")
    st.caption(
        "전체 사용자 history 를 합쳐 학습한 Logistic Regression 의 피처 가중치. "
        "개인 모델(블렌더)과 달리 코호트 단위 — 가설 가중치 검증·다음 피처 결정 근거."
    )
    result = analyzer.global_lr_coefficients()
    if result is None:
        st.info("기록이 20건 이상 쌓이고 선택/미선택이 모두 있어야 학습됩니다.")
        return

    col_acc, col_n, col_b = st.columns(3)
    col_acc.metric("학습 정확도", f"{result['accuracy']:.1%}")
    col_n.metric("학습 표본", f"{result['sample_size']:,}건")
    col_b.metric("절편", f"{result['intercept']:+.3f}")

    coef_df = (
        pd.DataFrame(
            [{"피처": k, "가중치": v} for k, v in result["coef"].items()],
        )
        .sort_values("가중치", key=lambda s: s.abs(), ascending=False)
    )
    st.bar_chart(coef_df.set_index("피처"))


def render(
    metrics: MetricsCalculator,
    history_repo: HistoryRepo,
    ml_model: MLModel,
    like_repo: LikeRepo,
    evaluator: RecommendEvaluator | None = None,
    feature_analyzer: FeatureAnalyzer | None = None,
) -> None:
    """운영자 대시보드 렌더 — 4개 탭(핵심·사용자/레시피·ML 운영·피처분석).

    데이터가 없으면 각 섹션은 안내 문구로 graceful 처리(빈 화면 방지).
    상단 요약 메트릭은 탭 밖 — 모든 탭에서 공통 KPI 가 보이도록.
    개인 ML 모델 강제 재학습은 사용자 사이드바(`ui/ml_status`); 이 탭은
    시스템 차원 운영 통계만 (활성화 사용자 수·모델 상태 표·디스크).
    """
    st.header("📊 모니터링 대시보드")
    st.caption("🛡️ 운영자 전용 — 전체 사용자 데이터·운영 지표 노출.")

    shown = _render_summary(metrics)
    if shown == 0:
        st.info("아직 추천 기록이 없습니다. 추천 결과 화면에서 카드를 선택하면 데이터가 쌓입니다.")
        return

    tab_core, tab_user, tab_ml, tab_feat = st.tabs(
        ["📈 핵심 지표", "👥 사용자·레시피", "🤖 ML 운영", "🔬 피처 분석"],
    )

    with tab_core:
        _render_conversion_trend(metrics)
        _render_eval_metrics(evaluator)

    with tab_user:
        _render_top_by_context(metrics)

    with tab_ml:
        _render_ml_ops(history_repo, ml_model, like_repo)

    with tab_feat:
        if feature_analyzer is None:
            st.info("FeatureAnalyzer 가 주입되지 않았습니다 (관리자 페이지 호출부 확인).")
        else:
            _render_feature_correlation(feature_analyzer)
            st.divider()
            _render_global_lr_coef(feature_analyzer)
