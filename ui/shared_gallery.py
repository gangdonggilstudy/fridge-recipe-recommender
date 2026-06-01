"""공유 레시피 갤러리 — 검색·정렬 + 본인 냉장고 매칭."""

import streamlit as st

from modules.custom_recipe_repo import CustomRecipeRepo
from modules.fridge_repo import FridgeRepo
from modules.ingredient_matcher import ingredient_score, missing_ingredients
from modules.normalize import STYLE_KEYS
from modules.restriction_repo import RestrictionRepo


def render(
    user_id: str,
    repo: CustomRecipeRepo,
    fridge: FridgeRepo,
    restriction_repo: RestrictionRepo | None = None,
) -> None:
    """공유 커스텀 레시피 갤러리. 검색·스타일 필터 + 알레르기 hard filter +
    내 냉장고 매칭률 정렬. restriction_repo=None 이면 알레르기 필터 생략.
    """
    st.header("🌐 공유 레시피 갤러리")
    st.caption("다른 사용자가 등록한 레시피를 탐색하세요. 내 재료 매칭률도 표시됩니다.")

    shared = repo.list_shared()
    if not shared:
        st.info("아직 공유된 레시피가 없습니다. 사이드바에서 직접 등록할 수 있어요.")
        return

    # ── 검색·필터 ──
    col1, col2 = st.columns([3, 2])
    query = col1.text_input("검색", placeholder="요리 이름 / 재료").strip().lower()
    # STYLE_KEYS 단일출처 사용 — 새 스타일 추가 시 자동 따라옴 (drift 차단).
    # set 인 ALLOWED_ENUMS["style"] 가 아니라 tuple 직접 import → 정의 순서 보장.
    style_filter = col2.selectbox(
        "스타일 필터",
        options=["전체", *STYLE_KEYS],
    )

    owned_names = {i["name"] for i in fridge.load(user_id)}
    restricted = (
        restriction_repo.list_ingredients(user_id)
        if restriction_repo is not None
        else set()
    )

    # 필터 적용
    filtered = []
    for r in shared:
        if query:
            blob = (r["name"] + " " + " ".join(r["ingredients"])).lower()
            if query not in blob:
                continue
        if style_filter != "전체" and r["style"] != style_filter:
            continue
        if restricted & set(r.get("ingredients", [])):
            continue  # 알레르기·기피 재료 포함 레시피 제외
        filtered.append(r)

    if not filtered:
        st.warning("조건에 맞는 레시피가 없습니다.")
        return

    # 매칭률 기준 정렬
    for r in filtered:
        r["_match"] = ingredient_score(owned_names, r["ingredients"], category_weight=0.3)
    filtered.sort(key=lambda x: x["_match"], reverse=True)

    st.caption(f"{len(filtered)}개 결과")

    for r in filtered:
        with st.container(border=True):
            head_col, score_col = st.columns([3, 1])
            head_col.subheader(f"🌐 {r['name']}")
            head_col.caption(
                f"by {r['author_id']} · {r['style']} · "
                f"{', '.join(r['taste']) if r['taste'] else '맛 미지정'} · "
                f"{r['cook_time']}분"
            )
            match_pct = int(r["_match"] * 100)
            score_col.metric("매칭률", f"{match_pct}%")

            st.write("**재료**: " + ", ".join(r["ingredients"]))

            missing = missing_ingredients(owned_names, r["ingredients"])
            if missing:
                st.warning(f"⚠ 추가 필요: {', '.join(missing)}")
            else:
                st.success("✅ 보유한 재료로 만들 수 있어요!")
