"""사이드바 위치 위젯 — IP/브라우저/기본값 + GPS 권한 + 강제 재추정."""

import streamlit as st

try:
    from streamlit_geolocation import streamlit_geolocation as _streamlit_geolocation
    _GEO_AVAILABLE = True
except ImportError:
    _streamlit_geolocation = None
    _GEO_AVAILABLE = False

from modules.location_repo import LocationRepo
from ui.session_keys import SessionKeys


_SOURCE_LABELS = {
    "browser": "📱 브라우저",
    "ip":      "🌐 IP 추정",
    "default": "기본값",
}


def _invalidate_context_cache() -> None:
    """위치 변경 시 ContextAnalyzer 캐시 폐기 → 다음 호출에서 재해결."""
    st.session_state.pop(SessionKeys.CONTEXT_ANALYZER, None)
    st.session_state.pop(SessionKeys.CONTEXT_ANALYZER_USER, None)


def render_sidebar(user_id: str, repo: LocationRepo) -> None:
    """현재 위치 표시 + 정확도 향상(브라우저 권한) + 재추정."""
    loc = repo.get(user_id)
    if loc:
        city = loc.get("city") or "좌표만"
        src = _SOURCE_LABELS.get(loc["source"], loc["source"])
        st.caption(f"현재: **{city}** ({src})")
    else:
        st.caption("미설정 — 추천 시 IP 자동 추정 또는 기본값")

    if _GEO_AVAILABLE:
        st.caption("정확도 향상: 위치 권한 허용 시 GPS/WiFi 기반으로 갱신됩니다.")
    browser_loc = _streamlit_geolocation() if _GEO_AVAILABLE else None
    if (
        browser_loc
        and browser_loc.get("latitude") is not None
        and browser_loc.get("longitude") is not None
    ):
        repo.save(
            user_id,
            source="browser",
            lat=float(browser_loc["latitude"]),
            lon=float(browser_loc["longitude"]),
            city=loc.get("city") if loc else None,
        )
        _invalidate_context_cache()
        st.toast("📍 위치 갱신됨")
        st.rerun()

    if st.button(
        "🔄 위치 재추정",
        key=f"loc_reset_{user_id}",
        help="저장된 위치를 폐기하고 다음 추천 시 IP 기반으로 다시 추정",
    ):
        repo.clear(user_id)
        _invalidate_context_cache()
        st.toast("위치 초기화됨 — 다음 추천 시 자동 재추정")
        st.rerun()
