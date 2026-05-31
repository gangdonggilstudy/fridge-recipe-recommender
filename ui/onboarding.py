"""온보딩 — 음식 카드 좋아요/싫어요 → 선호 벡터 + 알레르기·기피 입력."""

import streamlit as st

from modules.demographics_repo import DemographicsRepo
from modules.preference import PreferenceManager
from modules.recipe_repo import RecipeRepo
from modules.restriction_repo import RestrictionRepo


# 음식 카드 — 스타일(4) × 맛(6) 조합을 고르게 표현.
# 사용자에게는 '음식'만 보이고, 내부에서 (style·taste) 차원으로 선호 벡터를 유도한다.
FOOD_CARDS = [
    {"name": "김치찌개",         "style": "한식", "taste": "매운맛"},
    {"name": "된장찌개",         "style": "한식", "taste": "담백함"},
    {"name": "불고기",           "style": "한식", "taste": "단맛"},
    {"name": "간장 닭조림",       "style": "한식", "taste": "짭짤함"},
    {"name": "참깨 비빔국수",     "style": "한식", "taste": "고소함"},
    {"name": "사골국",           "style": "한식", "taste": "감칠맛"},
    {"name": "아라비아타 파스타", "style": "양식", "taste": "매운맛"},
    {"name": "샐러드",           "style": "양식", "taste": "담백함"},
    {"name": "함박스테이크",      "style": "양식", "taste": "단맛"},
    {"name": "올리브 파스타",     "style": "양식", "taste": "짭짤함"},
    {"name": "까르보나라",        "style": "양식", "taste": "고소함"},
    {"name": "버섯 크림 파스타",  "style": "양식", "taste": "감칠맛"},
    {"name": "마라탕",           "style": "중식", "taste": "매운맛"},
    {"name": "계란볶음밥",        "style": "중식", "taste": "담백함"},
    {"name": "탕수육",           "style": "중식", "taste": "단맛"},
    {"name": "굴소스 볶음밥",     "style": "중식", "taste": "짭짤함"},
    {"name": "깨소금 냉채",       "style": "중식", "taste": "고소함"},
    {"name": "짬뽕",             "style": "중식", "taste": "감칠맛"},
    {"name": "매운 라멘",        "style": "일식", "taste": "매운맛"},
    {"name": "초밥",             "style": "일식", "taste": "담백함"},
    {"name": "데리야키 치킨",     "style": "일식", "taste": "단맛"},
    {"name": "쯔유 소바",        "style": "일식", "taste": "짭짤함"},
    {"name": "참깨 냉모밀",       "style": "일식", "taste": "고소함"},
    {"name": "샤부샤부",         "style": "일식", "taste": "감칠맛"},
]


def render(
    user_id: str,
    preference_manager: PreferenceManager,
    demographics_repo: DemographicsRepo,
    recipe_repo: RecipeRepo | None = None,
    restriction_repo: RestrictionRepo | None = None,
) -> None:
    """온보딩 화면 — 음식 취향(좋아요/싫어요) + 안전성 필터(알레르기·기피 재료).

    `recipe_repo`·`restriction_repo` 가 None 이면 안전성 섹션 생략.
    """
    st.header("🍳 시작 전 입맛 설정")
    st.caption(f"환영합니다, {user_id}님! 좋아하는 음식만 알려주시면 추천이 맞춰집니다.")

    GENDER_OPTIONS = ["선택 안 함", "남성", "여성"]
    GENDER_CODE = {"남성": "M", "여성": "F"}
    AGE_OPTIONS = ["선택 안 함", "10대", "20대", "30대", "40대", "50대 이상"]
    AGE_CODE = {"10대": "10s", "20대": "20s", "30대": "30s", "40대": "40s", "50대 이상": "50s+"}

    food_names = [c["name"] for c in FOOD_CARDS]

    with st.form("onboarding"):
        # 인구통계 (선택) — cold-start 보강용
        st.subheader("선택 정보 (건너뛸 수 있습니다)")
        st.caption("입력하시면 초기 추천 정확도가 높아집니다. 추천 점수 계산에만 사용됩니다.")
        col_g, col_a = st.columns(2)
        gender_label = col_g.radio("성별", options=GENDER_OPTIONS)
        age_label = col_a.radio("나이대", options=AGE_OPTIONS)

        st.divider()

        # 1. 음식 취향 — 음식만 평가 (스타일·맛 직접 입력 없음)
        st.subheader("1. 좋아하는 음식을 골라주세요")
        st.caption("고른 음식의 스타일·맛을 분석해 추천에 반영합니다. (하나 이상 필수)")
        liked = st.multiselect(
            "좋아하는 음식 (하나 이상)",
            options=food_names,
            placeholder="예: 김치찌개, 초밥...",
        )
        disliked = st.multiselect(
            "싫어하는 음식 (선택)",
            options=food_names,
            placeholder="평소 잘 안 먹는 음식이 있다면",
        )

        # 2. 알레르기·기피 재료 (안전성 필터)
        restrictions: list[str] = []
        if recipe_repo is not None and restriction_repo is not None:
            st.subheader("2. 알레르기·절대 안 먹는 재료가 있나요? (선택)")
            st.caption(
                "선택 재료가 포함된 레시피는 추천에서 제외됩니다. "
                "⚠ 심한 알레르기는 의료 전문가와 상담하세요."
            )
            all_ingredients = recipe_repo.get_all_ingredients()
            restrictions = st.multiselect(
                "재료 선택 (여러 개 가능)",
                options=all_ingredients,
                placeholder="예: 우유, 견과류, 새우...",
            )

        submitted = st.form_submit_button(
            "완료하고 추천 받기",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    if not liked:
        st.warning("좋아하는 음식을 최소 1개 선택해주세요.")
        return

    # 음식 카드 → (style·taste) 응답으로 변환.
    # 같은 음식이 좋아요·싫어요 양쪽에 들어가면 좋아요 우선.
    card_responses = []
    for c in FOOD_CARDS:
        if c["name"] in liked:
            card_responses.append({"style": c["style"], "taste": c["taste"], "liked": True})
        elif c["name"] in disliked:
            card_responses.append({"style": c["style"], "taste": c["taste"], "liked": False})

    vector = preference_manager.init_cold_start({"cards": card_responses})
    preference_manager.save(user_id, vector)
    # 인구통계 저장 (선택 안 함 → None)
    demographics_repo.save_demographics(
        user_id,
        gender=GENDER_CODE.get(gender_label),
        age_group=AGE_CODE.get(age_label),
    )
    if restriction_repo is not None:
        restriction_repo.replace_all(user_id, restrictions, reason="avoid")
    st.success("저장되었습니다! 추천 화면으로 이동합니다.")
    st.rerun()


def needs_onboarding(user_id: str, preference_manager: PreferenceManager) -> bool:
    """사용자가 온보딩을 거쳐야 하는지 판단. 빈 벡터 = 신규."""
    vector = preference_manager.load(user_id)
    return not vector or not any(abs(float(value)) > 1e-12 for value in vector.values())
