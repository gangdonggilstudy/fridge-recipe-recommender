"""Streamlit 진입점. 실행: `streamlit run app.py` (사전: `recipes/tools/build_recipes.py`)."""

import os
import sys
from pathlib import Path

import streamlit as st

# 프로젝트 루트를 import path에 추가 (streamlit run 대응)
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()  # app_services 임포트 전 실행 — _APP_DB/_RECIPES_DB 모듈 상수에 .env 반영

from modules.logging_setup import setup_logging  # noqa: E402

setup_logging()  # 프로젝트 로거 초기화 (멱등)

from modules.app_services import (  # noqa: E402
    get_custom_recipe_repo,
    get_demographics_repo,
    get_fridge_repo,
    get_history_repo,
    get_ingredient_parser,
    get_like_repo,
    get_location_repo,
    get_ml_model,
    get_narrator,
    get_preference_manager,
    get_receipt_parser,
    get_recommendation_impressions,
    get_recommender,
    get_recipe_repo,
    get_restriction_repo,
    get_stt_engine,
)
from modules.auth import is_valid_user_id  # noqa: E402
from modules.context import ContextAnalyzer  # noqa: E402
from modules import location_resolver  # noqa: E402
from modules.weather_api import StaticWeatherProvider, WeatherAPI  # noqa: E402
from ui import consent as consent_ui  # noqa: E402
from ui import custom_recipe as custom_recipe_ui  # noqa: E402
from ui import fridge as fridge_ui  # noqa: E402
from ui import ml_status as ml_status_ui  # noqa: E402
from ui import onboarding as onboarding_ui  # noqa: E402
from ui import result as result_ui  # noqa: E402
from ui import shared_gallery as shared_gallery_ui  # noqa: E402
from ui import location as location_ui  # noqa: E402
from ui.session_keys import SessionKeys  # noqa: E402


# ── 페이지 설정 ──
st.set_page_config(
    page_title="냉장고 요리 추천",
    page_icon="🍳",
    layout="wide",
)


# ── 컨텍스트 분석기 (사용자별 세션 캐시) ──

def _get_client_ip() -> str | None:
    """Streamlit 요청 헤더에서 클라이언트 IP 추출 (X-Forwarded-For 우선)."""
    try:
        headers = st.context.headers
        xff = headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
        return headers.get("X-Real-Ip")
    except Exception:  # noqa: BLE001 — Streamlit context 미구현·헤더 누락 등 모든 경우 IP 미상 처리
        return None


def make_context_analyzer_for(user_id: str) -> ContextAnalyzer:
    """사용자 위치 해결 → WeatherAPI(lat/lon) 또는 StaticProvider 주입."""
    repo = get_location_repo()
    lat, lon, city, source = location_resolver.resolve(
        user_id, repo, client_ip=_get_client_ip()
    )
    api_key = os.getenv("WEATHER_API_KEY", "")
    if api_key and not api_key.startswith("your_"):
        if source == "default":
            provider = WeatherAPI(api_key, city=city)
        else:
            provider = WeatherAPI(api_key, lat=lat, lon=lon)
    else:
        provider = StaticWeatherProvider("맑음")
    return ContextAnalyzer(weather_provider=provider)


def get_context_analyzer_cached(user_id: str) -> ContextAnalyzer:
    """사용자별 ContextAnalyzer 를 session_state 에 1회 캐시."""
    cached_user = st.session_state.get(SessionKeys.CONTEXT_ANALYZER_USER)
    if cached_user != user_id or SessionKeys.CONTEXT_ANALYZER not in st.session_state:
        st.session_state[SessionKeys.CONTEXT_ANALYZER] = make_context_analyzer_for(user_id)
        st.session_state[SessionKeys.CONTEXT_ANALYZER_USER] = user_id
    return st.session_state[SessionKeys.CONTEXT_ANALYZER]


# ── 사이드바 ──

def _render_user_selector() -> str:
    """사용자 ID 입력·검증. 유효한 ID 반환, 오류 시 빈 문자열."""
    st.sidebar.title("🍳 냉장고 추천")
    st.sidebar.caption(f"레시피 DB v{get_recipe_repo().get_version()}")
    user_id = st.sidebar.text_input(
        "사용자 ID",
        value=st.session_state.get(SessionKeys.USER_ID, "demo"),
        help="원하는 이름·별명을 입력하세요",
    )
    st.session_state[SessionKeys.USER_ID] = user_id
    if user_id and not is_valid_user_id(user_id):
        st.sidebar.error(
            "사용자 ID는 한글·영문·숫자·`-`·`_`·공백, 1~64자만 가능합니다. "
            "(`/ \\ . :` 등은 사용할 수 없습니다)"
        )
        return ""
    return user_id


def _render_sidebar_metrics(user_id: str) -> None:
    """보유 재료 수·선택 기록 건수 메트릭."""
    items = get_fridge_repo().load(user_id)
    history_n = get_history_repo().history_count(user_id)
    st.sidebar.metric("보유 재료", f"{len(items)}개")
    st.sidebar.metric("선택 기록", f"{history_n}건")


def _render_sidebar_settings(user_id: str) -> None:
    """위치·설정·알레르기 expander."""
    with st.sidebar.expander("📍 위치 (날씨 추천)"):
        location_ui.render_sidebar(user_id, get_location_repo())

    with st.sidebar.expander("⚙️ 설정"):
        if st.button("온보딩 다시 하기", key=f"onboarding_reset_{user_id}"):
            get_preference_manager().save(user_id, {})
            st.rerun()

        st.divider()
        st.caption("🚫 알레르기·기피 재료")
        restriction_repo = get_restriction_repo()
        current = sorted(restriction_repo.list_ingredients(user_id))
        all_ings = get_recipe_repo().get_all_ingredients()
        key = SessionKeys.restriction_edit_for(user_id)

        def _on_restriction_change() -> None:
            new_value = st.session_state.get(key, [])
            cur = sorted(restriction_repo.list_ingredients(user_id))
            if set(new_value) != set(cur):
                restriction_repo.replace_all(user_id, new_value, reason="avoid")
                st.toast(f"{len(new_value)}개 재료 저장됨 🚫")

        st.multiselect(
            "변경하면 자동 저장됩니다",
            options=all_ings,
            default=current,
            key=key,
            on_change=_on_restriction_change,
            label_visibility="collapsed",
        )

        st.divider()
        with st.expander("🤖 내 추천 모델"):
            ml_status_ui.render_my_model(
                user_id, get_ml_model(), get_history_repo(),
            )

        st.divider()
        with st.expander("📋 수집 정보 보기"):
            consent_ui.render_summary()

        st.divider()
        with st.expander("📦 사용 라이브러리"):
            # requirements.txt 를 단일출처로 그대로 노출 — 갱신 시 자동 따라옴.
            # 카테고리 주석(# 핵심 의존성 / # 음성 입력 (선택) 등)이 그대로 보여
            # 별도 매핑 없이 구분 직관성 확보.
            req_path = Path(__file__).parent / "requirements.txt"
            st.code(req_path.read_text(encoding="utf-8"), language="text")


def sidebar() -> str:
    """사이드바 렌더 + 사용자 ID 반환."""
    user_id = _render_user_selector()
    if not user_id:
        return ""
    st.sidebar.divider()
    _render_sidebar_metrics(user_id)
    _render_sidebar_settings(user_id)
    custom_recipe_ui.render_sidebar(user_id, get_custom_recipe_repo())
    return user_id


# ── 메인 ──

def main() -> None:
    """앱 진입 흐름: 사이드바 → 동의 게이트 → 온보딩 게이트 → 탭(냉장고·추천·갤러리).

    동의·온보딩은 미완료 시 early return 으로 다음 단계 진입을 차단한다.
    """
    user_id = sidebar()
    if not user_id:
        st.warning("사이드바에서 사용자 ID를 입력해주세요.")
        return

    app_db_path = get_preference_manager().db_path
    if consent_ui.needs_consent(user_id, app_db_path):
        consent_ui.render(user_id, app_db_path)
        return

    preference_manager = get_preference_manager()
    if onboarding_ui.needs_onboarding(user_id, preference_manager):
        onboarding_ui.render(
            user_id, preference_manager,
            demographics_repo=get_demographics_repo(),
            recipe_repo=get_recipe_repo(),
            restriction_repo=get_restriction_repo(),
        )
        return

    tabs = st.tabs(["🥬 냉장고", "🍽️ 추천 받기", "🌐 공유 갤러리"])

    with tabs[0]:
        fridge_ui.render(
            user_id,
            get_fridge_repo(),
            get_recipe_repo(),
            parser=get_ingredient_parser(),
            stt=get_stt_engine(),
            receipt_parser=get_receipt_parser(),
        )

    with tabs[1]:
        context = get_context_analyzer_cached(user_id).get_context()
        result_ui.render(
            user_id,
            get_recommender(),
            context,
            narrator=get_narrator(),
            like_repo=get_like_repo(),
            impression_repo=get_recommendation_impressions(),
        )

    with tabs[2]:
        shared_gallery_ui.render(
            user_id,
            get_custom_recipe_repo(),
            get_fridge_repo(),
            restriction_repo=get_restriction_repo(),
        )


if __name__ == "__main__":
    main()
