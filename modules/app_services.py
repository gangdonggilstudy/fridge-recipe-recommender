"""앱 전역 `@st.cache_resource` 싱글톤 — pages/ 가 app.py 미경유 import."""

import streamlit as st

from modules.custom_recipe_repo import CustomRecipeRepo
from modules.db_init import init_db
from modules.db_paths import get_app_db_path, get_recipes_db_path
from modules.demographics_repo import DemographicsRepo
from modules.feature_analyzer import FeatureAnalyzer
from modules.fridge_repo import FridgeRepo
from modules.history_repo import HistoryRepo
from modules.location_repo import LocationRepo
from modules.metrics import MetricsCalculator
from modules.ml_model import MLModel
from modules.preference import PreferenceManager
from modules.like_repo import LikeRepo
from modules.recipe_repo import RecipeRepo
from modules.recommendation_impression import RecommendationImpressionRepo
from modules.recommend_eval import RecommendEvaluator
from modules.recommender import Recommender
from modules.restriction_repo import RestrictionRepo
from modules.stt_engine import STTEngine, make_stt_engine
from llm.ingredient_parser import IngredientParser
from llm.narrator import Narrator, make_provider
from llm.receipt_parser import ReceiptParser

_APP_DB = get_app_db_path()
_RECIPES_DB = get_recipes_db_path()

# 모듈 import 시점에 schema 보장 (멱등 — CREATE TABLE IF NOT EXISTS).
# Repository 인스턴스가 cache_resource 로 살아있는 동안 외부에서 db 파일이
# 삭제되면 sqlite3.connect() 가 빈 파일을 자동 재생성해 "no such table" 이
# 났던 버그를 차단. 정상 운영에선 1회 실행이라 비용 0.
init_db(_APP_DB)


@st.cache_resource
def get_recipe_repo() -> RecipeRepo:
    return RecipeRepo(_RECIPES_DB)


@st.cache_resource
def get_preference_manager() -> PreferenceManager:
    return PreferenceManager(_APP_DB)


@st.cache_resource
def get_fridge_repo() -> FridgeRepo:
    return FridgeRepo(_APP_DB)


@st.cache_resource
def get_custom_recipe_repo() -> CustomRecipeRepo:
    return CustomRecipeRepo(_APP_DB)


@st.cache_resource
def get_like_repo() -> LikeRepo:
    return LikeRepo(_APP_DB)


@st.cache_resource
def get_restriction_repo() -> RestrictionRepo:
    return RestrictionRepo(_APP_DB)


@st.cache_resource
def get_metrics() -> MetricsCalculator:
    return MetricsCalculator(_APP_DB)


@st.cache_resource
def get_ml_model() -> MLModel:
    return MLModel(_APP_DB)


@st.cache_resource
def get_recommend_evaluator() -> RecommendEvaluator:
    return RecommendEvaluator(_APP_DB)


@st.cache_resource
def get_feature_analyzer() -> FeatureAnalyzer:
    return FeatureAnalyzer(_APP_DB)


@st.cache_resource
def get_recommendation_impressions() -> RecommendationImpressionRepo:
    return RecommendationImpressionRepo(_APP_DB)


@st.cache_resource
def get_location_repo() -> LocationRepo:
    return LocationRepo(_APP_DB)


@st.cache_resource
def get_history_repo() -> HistoryRepo:
    return HistoryRepo(_APP_DB)


@st.cache_resource
def get_demographics_repo() -> DemographicsRepo:
    return DemographicsRepo(_APP_DB)


@st.cache_resource
def get_recommender() -> Recommender:
    return Recommender(
        recipe_repo=get_recipe_repo(),
        preference_manager=get_preference_manager(),
        fridge_repo=get_fridge_repo(),
        history_repo=get_history_repo(),
        demographics_repo=get_demographics_repo(),
        custom_repo=get_custom_recipe_repo(),
        like_repo=get_like_repo(),
        restriction_repo=get_restriction_repo(),
        ml_model=get_ml_model(),
    )


@st.cache_resource
def get_narrator() -> Narrator:
    """LLM 키 있으면 실 호출, 없으면 템플릿 fallback."""
    return Narrator(provider=make_provider())


@st.cache_resource
def get_stt_engine() -> STTEngine | None:
    """faster-whisper 설치·STT_ENABLED 여부에 따라 None 가능."""
    return make_stt_engine()


@st.cache_resource
def get_ingredient_parser() -> IngredientParser:
    """음성 텍스트 → 재료 항목 파서. LLM 키 있으면 폴백 활용, 없으면 정규식만."""
    return IngredientParser(
        provider=make_provider(),
        canonical_names=get_recipe_repo().get_all_ingredients(),
    )


@st.cache_resource
def get_receipt_parser() -> ReceiptParser | None:
    """영수증 OCR(Gemini 비전). RECEIPT_OCR_ENABLED + LLM 키 가용 시에만.

    게이팅 정책은 streamlit 무의존 모듈에 분리(`feature_gates.receipt_ocr_enabled`)
    — 단위 테스트가 app 전체 import 없이 게이트만 검증 가능.
    """
    from .feature_gates import receipt_ocr_enabled  # noqa: PLC0415 — lazy (순환 회피)

    if not receipt_ocr_enabled():
        return None
    return ReceiptParser(provider=make_provider(), ingredient_parser=get_ingredient_parser())
