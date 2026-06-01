"""운영자 페이지 — `ADMIN_USER_IDS` 화이트리스트."""

import streamlit as st
from dotenv import load_dotenv

# 사용자가 페이지 URL 직접 진입 시 app.py 의 load_dotenv 보장 깨짐. 멱등 호출.
load_dotenv()

from modules.app_services import (  # noqa: E402
    get_feature_analyzer,
    get_history_repo,
    get_like_repo,
    get_metrics,
    get_ml_model,
    get_recommend_evaluator,
)
from ui import monitoring as monitoring_ui  # noqa: E402
from ui._admin_guard import require_admin  # noqa: E402

st.set_page_config(
    page_title="관리자 — 냉장고 요리 추천",
    page_icon="🛡",
    layout="wide",
)

user_id = require_admin()
if user_id is None:
    st.stop()

monitoring_ui.render(
    get_metrics(),
    get_history_repo(),
    get_ml_model(),
    get_like_repo(),
    evaluator=get_recommend_evaluator(),
    feature_analyzer=get_feature_analyzer(),
)
