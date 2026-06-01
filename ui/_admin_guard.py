"""관리자 페이지 가드 — `pages/` 진입 시 호출, 비관리자 차단.

사용 예:
    from ui._admin_guard import require_admin
    user_id = require_admin()
    if user_id is None:
        st.stop()
    # ... 관리자 기능 ...
"""

import streamlit as st

from modules.auth import ENV_KEY, is_admin, is_valid_user_id
from modules.logging_setup import get_logger
from ui.session_keys import SessionKeys

_logger = get_logger(__name__)


def require_admin() -> str | None:
    """사이드바에서 사용자 ID 받고 권한 확인.

    반환:
        str  — 관리자 user_id (페이지 진입 허용)
        None — 비관리자·미입력 (호출자가 st.stop() 등으로 차단)
    """
    st.sidebar.title("🛡️ 관리자")
    user_id = st.sidebar.text_input(
        "사용자 ID",
        value=st.session_state.get(SessionKeys.USER_ID, ""),
        help="ADMIN_USER_IDS 환경변수에 등록된 ID 만 진입 가능",
    )
    st.session_state[SessionKeys.USER_ID] = user_id

    if not user_id:
        st.warning("사이드바에서 사용자 ID 를 입력해주세요.")
        return None

    if not is_valid_user_id(user_id):
        st.error("사용자 ID 형식이 올바르지 않습니다 (한글·영문·숫자·-·_·공백 1~64자).")
        _logger.info("admin page access denied: invalid user_id format")
        return None

    if not is_admin(user_id):
        st.error(
            f"🚫 '{user_id}' 는 운영자가 아닙니다.\n\n"
            f"운영자 등록은 `.env` 의 `{ENV_KEY}` 환경변수에서 관리됩니다."
        )
        st.info("사용자 페이지로 돌아가려면 사이드바의 메인 페이지를 선택하세요.")
        _logger.info("admin page access denied: user_id=%s", user_id)
        return None

    st.sidebar.success(f"✅ 운영자 인증: {user_id}")
    return user_id
