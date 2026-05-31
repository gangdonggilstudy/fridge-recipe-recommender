"""추천 카드 정적 렌더 — 상세 시각만 (상태/부수효과는 ResultPageController)."""
from __future__ import annotations

import streamlit as st

from llm.narrator import Narrator
from modules.explainer import Explainer
from modules.like_repo import LikeRepo
from ui.session_keys import SessionKeys


def render_card_instructions(recipe: dict) -> None:
    """조리법 — 상세 카드 상단에 직접 표시 (expander 없이 한 번에 보이도록).

    시스템 레시피는 instructions 가 기본 빈 값. 그 경우엔 미등록 안내를 한 줄
    띄워 사용자가 데이터 누락임을 명시적으로 인지하게 한다(향후 외부 링크 채움).
    """
    st.markdown("**📖 조리법**")
    instructions = (recipe.get("instructions") or "").strip()
    if not instructions:
        st.caption("아직 등록된 조리법이 없습니다.")
        return
    if instructions.startswith(("http://", "https://")):
        st.markdown(f"[외부 레시피 열기]({instructions})")
    else:
        st.markdown(instructions)


def render_card_explanation(recipe: dict, explainer: Explainer) -> None:
    """XAI 점수 비중 — 레짐(rule/blender)별 충실 분해."""
    with st.expander("📊 추천 이유 (점수 비중)"):
        score_breakdown = explainer.breakdown(recipe["scores"])
        contributions = explainer.explain(recipe["scores"])

        if score_breakdown["mode"] == "blender":
            st.caption(
                f"🤖 학습된 추천 (이 카드 기준) · "
                f"로짓 {score_breakdown['total']:.2f} → 선택확률 {score_breakdown['prob']:.2f}"
            )
            st.caption(f"기본 성향(절편) {score_breakdown['intercept']:+.2f}")
            for label, percent in contributions.items():
                pt = score_breakdown["items"].get(label, 0.0)
                sign = "▲" if pt >= 0 else "▼"
                st.write(f"**{label}** {sign} {pt:+.2f}")
                st.progress(int(percent), text=f"{percent}%")
        else:
            parts = " + ".join(
                f"{k} {v:.0f}" for k, v in score_breakdown["items"].items() if v > 0
            )
            st.caption(f"종합(규칙) {score_breakdown['total']:.0f}점 = {parts}")
            for label, percent in contributions.items():
                st.write(f"**{label}**")
                st.progress(int(percent), text=f"{percent}%")


def render_card_ai(recipe: dict, narrator: Narrator, explainer: Explainer) -> None:
    """AI 자연어 설명 (세션 캐시 — 카드당 1회 생성)."""
    with st.expander("🤖 AI 설명 보기"):
        cache_key = SessionKeys.ai_desc_for(recipe["id"])
        if cache_key not in st.session_state:
            with st.spinner("설명 생성 중..."):
                top_reason = explainer.top_reason(recipe["scores"])
                st.session_state[cache_key] = narrator.generate(recipe, top_reason)
        st.write(st.session_state[cache_key])


def render_like(like_repo: LikeRepo, user_id: str, recipe_id: str) -> None:
    """좋아요 토글 + 누적 카운트 표시."""
    liked = like_repo.is_liked(user_id, recipe_id)
    count = like_repo.like_count(recipe_id)

    col_btn, col_stats = st.columns([1, 5])

    btn_label = "❤️ 좋아요 취소" if liked else "🤍 좋아요"
    if col_btn.button(btn_label, key=f"like_{recipe_id}"):
        like_repo.toggle_like(user_id, recipe_id)
        st.rerun()

    if count > 0:
        col_stats.caption(f"❤️ × {count}")
