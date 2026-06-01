"""동의 화면 — 신규/버전변경 사용자 진입 게이트. 거부 시 서비스 차단."""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from modules.db_init import (
    CONSENT_VERSION,
    delete_user_complete,
    has_consent,
    record_consent,
)
from ui.session_keys import SessionKeys


# ── 단일 소스 텍스트 — 동의 화면 + 사이드바 보기에서 공유 ──

COLLECTED_DATA: list[tuple[str, str]] = [
    ("별명", "사용자 ID (직접 입력)"),
    ("선호 음식 스타일·맛", "온보딩 답변"),
    ("알레르기·기피 재료", "선택"),
    ("냉장고 재료·유통기한", "직접 입력 또는 음성 입력"),
    ("추천 선택·평점 기록", "ML 학습 및 통계용"),
    ("작성한 커스텀 레시피", "본인이 만든 경우"),
    ("성별·나이대 (선택, 미입력 가능)",
     "cold-start 추천 보강용 — 그룹 통계 편향은 다양성 보정 + 운영자 모니터링으로 통제"),
]

EXTERNAL_DATA: list[tuple[str, str]] = [
    ("Google Gemini / OpenAI", "추천 이유 자연어 설명 생성 (레시피 메타 + 추천 사유 라벨만 전송, 본인 식별 정보 없음)"),
    ("음성 입력", "로컬 처리 (faster-whisper) — 외부 전송 0"),
]

NOT_COLLECTED: list[str] = [
    "이름·이메일·전화번호",
    "건강 상태·의료 정보",
]


# ── 게이트 함수 ──

def needs_consent(user_id: str, db_path: str | Path) -> bool:
    """현재 버전으로 동의 안 한 사용자는 True 반환."""
    return not has_consent(db_path, user_id)


# ── 렌더링 ──

def render(user_id: str, db_path: str | Path) -> None:
    """동의 화면 렌더링. 동의 시 record_consent + rerun."""
    st.header("🍳 서비스 시작 전 안내")
    st.caption(f"환영합니다, **{user_id}**님. 첫 이용 전 데이터 수집에 대해 안내드립니다.")

    _render_collected_section()
    _render_external_section()
    _render_not_collected_section()
    _render_disclaimer_section()
    _render_withdrawal_section(key_prefix="main")

    st.divider()

    agreed = st.checkbox(
        "위 내용을 확인했고 동의합니다 (필수)",
        key="consent_checkbox",
    )

    col_no, col_yes = st.columns(2)
    if col_no.button("동의하지 않음", use_container_width=True):
        st.info(
            "동의 없이는 서비스를 이용할 수 없습니다. "
            "이용을 원하시면 위 체크박스를 선택 후 **동의하고 시작** 버튼을 눌러주세요."
        )

    if col_yes.button(
        "동의하고 시작",
        type="primary",
        use_container_width=True,
        disabled=not agreed,
    ):
        record_consent(db_path, user_id)
        st.success("동의가 기록되었습니다. 다음 단계로 이동합니다.")
        st.rerun()


def render_summary() -> None:
    """사이드바 ⚙️ 설정 expander 내부에서 호출되는 읽기 전용 요약."""
    _render_collected_section()
    _render_external_section()
    _render_not_collected_section()
    _render_withdrawal_section(key_prefix="sidebar")
    st.caption(f"동의 버전: `{CONSENT_VERSION}`")


# ── 내부 헬퍼 ──

def _render_collected_section() -> None:
    st.subheader("📦 저장되는 정보")
    st.caption("모두 본인 기기/서버에만 보관됩니다.")
    for label, desc in COLLECTED_DATA:
        st.markdown(f"- **{label}** — {desc}")


def _render_external_section() -> None:
    st.subheader("🌐 외부로 전송되는 정보 (LLM 사용 시)")
    for label, desc in EXTERNAL_DATA:
        st.markdown(f"- **{label}** — {desc}")


def _render_not_collected_section() -> None:
    st.subheader("🚫 수집하지 않는 정보")
    for item in NOT_COLLECTED:
        st.markdown(f"- {item}")


def _render_disclaimer_section() -> None:
    st.subheader("⚠ 의료 면책")
    st.markdown(
        "알레르기 필터는 단순 텍스트 매칭이며, **의학적 진단·영양 처방이 아닙니다**. "
        "심한 알레르기·중증 식이 제한·만성 질환은 반드시 의료 전문가와 상담하세요."
    )


def _render_withdrawal_section(key_prefix: str) -> None:
    # 같은 페이지 렌더 중에 동의 화면(메인) + 사이드바 expander 양쪽에서 호출되므로
    # widget key 충돌을 막기 위해 prefix 를 받는다. session_state(WITHDRAW_CONFIRM)는
    # 사용자 단위라 공유 — 한 쪽에서 토글하면 다른 쪽도 같은 상태로 보임 (의도).
    st.subheader("✋ 데이터 철회·삭제")
    st.caption(
        "데이터 다운로드(JSON export)·OAuth·제3자 동의 분리는 사업화 단계 도입 예정입니다."
    )

    user_id: str | None = st.session_state.get(SessionKeys.USER_ID)
    db_path = os.getenv("APP_DB_PATH", "data/app.db")

    if not user_id:
        st.info("사용자 ID를 입력한 후 삭제 요청이 가능합니다.")
        return

    if not st.session_state.get(SessionKeys.WITHDRAW_CONFIRM):
        if st.button("🗑️ 데이터 삭제 요청", key=f"{key_prefix}_withdraw_req"):
            st.session_state[SessionKeys.WITHDRAW_CONFIRM] = True
            st.rerun()
    else:
        st.warning(
            "⚠ **이 작업은 되돌릴 수 없습니다.** "
            "냉장고·기록·선호·커스텀 레시피·평점 등 모든 데이터가 영구 삭제됩니다."
        )
        confirmed = st.checkbox(
            "위 내용을 이해하고 모든 데이터 삭제에 동의합니다",
            key=f"{key_prefix}_withdraw_confirmed",
        )
        col_cancel, col_delete = st.columns(2)
        if col_cancel.button("취소", key=f"{key_prefix}_withdraw_cancel"):
            st.session_state.pop(SessionKeys.WITHDRAW_CONFIRM, None)
            st.rerun()
        if col_delete.button(
            "영구 삭제",
            type="primary",
            disabled=not confirmed,
            key=f"{key_prefix}_withdraw_delete",
        ):
            delete_user_complete(db_path, user_id)
            st.cache_resource.clear()
            st.session_state.clear()
            st.rerun()
