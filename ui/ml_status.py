"""본인 ML 모델 상태 + 재학습 위젯 — 사이드바 ⚙️ 설정 expander 용."""
from __future__ import annotations

import streamlit as st

from modules.history_repo import HistoryRepo
from modules.ml_model import ACTIVATION_THRESHOLD, MLModel


def render_my_model(
    user_id: str, ml_model: MLModel, history_repo: HistoryRepo,
) -> None:
    """본인 ML 모델 상태 + 재학습. expander 안에서 호출되는 게 일반적."""
    history_n = history_repo.history_count(user_id)
    col_a, col_b = st.columns(2)
    col_a.metric("내 기록 수", history_n)
    col_b.metric("활성화 임계값", ACTIVATION_THRESHOLD)

    if ml_model.is_ready(user_id):
        last_size = ml_model.store.last_trained_size(user_id)
        new_since = history_n - (last_size or 0)
        if new_since > 0:
            if last_size is None:
                st.success(f"✅ 모델 학습 가능 (기록 {history_n}건)")
            else:
                st.success(f"✅ 재학습 가능 (마지막 학습 이후 {new_since}건 새 기록)")
            if st.button("내 모델 재학습", type="primary", key=f"ml_retrain_{user_id}"):
                with st.spinner("학습 중..."):
                    ok = ml_model.train(user_id)
                if ok:
                    st.success("학습 완료 — 다음 추천부터 ML 가중치 적용")
                else:
                    st.warning("선택/미선택 두 클래스가 모두 필요합니다")
        else:
            st.info(f"마지막 학습 이후 새 기록이 없습니다 (학습 표본 {last_size}건)")
    else:
        remaining = ACTIVATION_THRESHOLD - history_n
        st.info(f"💡 모델 활성화까지 {remaining}건의 추천 기록이 더 필요합니다")
