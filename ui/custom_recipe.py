"""커스텀 레시피 UI — 사이드바 등록 + 목록 + 공유 토글."""

import streamlit as st

from llm.review_analyzer import ReviewAnalyzer
from modules.context import SEASON_TO_MONTHS
from modules.custom_recipe_repo import CustomRecipeRepo
from modules.normalize import ALLOWED_ENUMS, infer_taste, normalize_ingredient
from ui._defaults import COOK_TIME_DEFAULT, COOK_TIME_MAX, COOK_TIME_MIN

_analyzer = ReviewAnalyzer(provider=None)


def render_sidebar(user_id: str, repo: CustomRecipeRepo) -> None:
    """사이드바에 등록 폼 + 내 레시피 목록 표시."""
    with (
        st.sidebar.expander("📝 내 레시피 추가"),
        st.form("custom_recipe_form", clear_on_submit=True),
    ):
        name = st.text_input("요리 이름", placeholder="예: 우리집 김치찌개")
        style = st.selectbox("스타일", sorted(ALLOWED_ENUMS["style"]))
        ingredients_raw = st.text_area(
            "재료 (쉼표 구분)",
            placeholder="김치, 돼지고기, 두부, 대파",
        )
        cook_time = st.number_input(
            "조리시간(분)",
            min_value=COOK_TIME_MIN,
            max_value=COOK_TIME_MAX,
            value=COOK_TIME_DEFAULT,
        )
        difficulty = st.selectbox("난이도", ["쉬움", "보통", "어려움"])
        suitable_time = st.multiselect("적합 시간대", sorted(ALLOWED_ENUMS["time"]))
        suitable_weather = st.multiselect("적합 날씨", sorted(ALLOWED_ENUMS["weather"]))
        season_input = st.multiselect("적합 계절", ["봄", "여름", "가을", "겨울"])
        suitable_month = sorted(
            {f"{m}월" for s in season_input for m in SEASON_TO_MONTHS[s]},
            key=lambda x: int(x.rstrip("월")),
        )
        instructions = st.text_area(
            "조리법",
            placeholder="1. 김치를 한입 크기로 썬다.\n2. 돼지고기는 ...",
            help="자유 텍스트 또는 외부 레시피 링크",
        )
        is_shared = st.checkbox(
            "🌐 다른 사용자에게 공유",
            value=False,
            help="공유하면 다른 사용자의 추천 후보에도 포함됩니다",
        )

        if st.form_submit_button("저장", type="primary", use_container_width=True):
            if not name or not ingredients_raw:
                st.warning("이름과 재료는 필수입니다")
                return
            ingredients = [i.strip() for i in ingredients_raw.split(",") if i.strip()]
            inferred_taste = infer_taste([normalize_ingredient(i) for i in ingredients])
            keywords = _analyzer.generate_keywords(name, style, inferred_taste)
            recipe_id = repo.add(
                author_id=user_id,
                name=name,
                style=style,
                ingredients=ingredients,
                cook_time=int(cook_time),
                difficulty=difficulty,
                suitable_time=suitable_time,
                suitable_weather=suitable_weather,
                suitable_month=suitable_month,
                is_shared=is_shared,
                review_keywords=keywords,
                instructions=instructions.strip(),
            )
            st.success(f"등록 완료 ({recipe_id})")
            st.rerun()

    # 내 레시피 목록 — 공유 토글 포함
    my_recipes = repo.list_by_author(user_id)
    if my_recipes:
        with st.sidebar.expander(f"내 레시피 ({len(my_recipes)}개)"):
            for recipe in my_recipes:
                col1, col2, col3 = st.columns([4, 1, 1])
                shared_badge = "🌐" if recipe["is_shared"] else "🔒"
                col1.write(f"{shared_badge} **{recipe['name']}**")
                col1.caption(f"{recipe['style']} · {recipe['cook_time']}분")
                toggle_label = "비공개로" if recipe["is_shared"] else "공유하기"
                if col2.button("🔄", key=f"share_{recipe['id']}", help=toggle_label):
                    repo.update_sharing(recipe["id"], not recipe["is_shared"], author_id=user_id)
                    st.rerun()
                if col3.button("🗑️", key=f"del_custom_{recipe['id']}", help="삭제"):
                    repo.delete(recipe["id"], author_id=user_id)
                    st.rerun()
