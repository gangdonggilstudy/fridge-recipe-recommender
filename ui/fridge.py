"""냉장고 화면 — 이름 + 유통기한. 음성/영수증은 parser 주입 시만 활성."""

from datetime import date, timedelta

import streamlit as st

from llm.ingredient_parser import IngredientParser
from llm.receipt_parser import ReceiptParser
from modules.fridge_repo import FridgeRepo
from modules.recipe_repo import RecipeRepo
from modules.stt_engine import STTEngine
from ui import receipt_input as receipt_input_ui
from ui import voice_input as voice_input_ui
from ui._defaults import (
    COMMON_INGREDIENTS,
    DEFAULT_EXPIRY_DAYS_AHEAD,
    EXPIRY_WARNING_DAYS,
)


def render(
    user_id: str,
    fridge: FridgeRepo,
    recipe_repo: RecipeRepo,
    parser: IngredientParser | None = None,
    stt: STTEngine | None = None,
    receipt_parser: ReceiptParser | None = None,
) -> None:
    """냉장고 화면 렌더링."""
    st.header("🥬 내 냉장고")

    items = fridge.load(user_id)

    # ── 보유 재료 목록 ──
    if items:
        st.subheader(f"보유 재료 ({len(items)}개)")
        for item in items:
            col1, col2, col3 = st.columns([5, 3, 1])
            col1.write(f"**{item['name']}**")
            if item["expiry_date"]:
                days = (item["expiry_date"] - date.today()).days
                expiry_label = f"D-{days}" if days >= 0 else "❌ 지남"
                color = "red" if days <= EXPIRY_WARNING_DAYS else "gray"
                col2.markdown(f":{color}[{expiry_label}]")
            else:
                col2.caption("기한 미설정")
            if col3.button("🗑️", key=f"del_{item['name']}", help="삭제"):
                fridge.delete(user_id, item["name"])
                st.rerun()
    else:
        st.info("냉장고가 비어 있습니다. 아래에서 재료를 추가하세요.")

    st.divider()

    # ── 자주 쓰는 재료 빠른 추가 ──
    st.subheader("자주 쓰는 재료")
    cols = st.columns(len(COMMON_INGREDIENTS))
    for col, name in zip(cols, COMMON_INGREDIENTS, strict=True):
        if col.button(name, key=f"quick_{name}"):
            fridge.upsert(user_id, name)
            st.rerun()

    st.divider()

    # ── 재료 추가 ──
    st.subheader("재료 추가")

    # 음성 입력 (선택) — STT 엔진·파서가 모두 가용일 때만 표시
    if stt is not None and parser is not None:
        voice_input_ui.render(user_id, fridge, parser, stt)

    # 영수증 OCR (선택) — RECEIPT_OCR_ENABLED + LLM 키 가용 시에만 주입됨
    if receipt_parser is not None:
        receipt_input_ui.render(user_id, fridge, receipt_parser)

    all_ingredients = recipe_repo.get_all_ingredients()

    # st.form 을 쓰지 않는다 — form 안 위젯은 submit 누르기 전엔 갱신 안 되어
    # 체크박스를 눌러도 날짜 입력이 즉시 안 뜨던 문제 회피.
    col1, col2 = st.columns([4, 2])
    name = col1.selectbox(
        "재료", options=all_ingredients, index=None, placeholder="검색...",
        key="add_ingredient_name",
    )
    use_expiry = col2.checkbox("유통기한", key="add_ingredient_use_expiry")

    expiry_date = None
    if use_expiry:
        expiry_date = st.date_input(
            "유통기한",
            value=date.today() + timedelta(days=DEFAULT_EXPIRY_DAYS_AHEAD),
            min_value=date.today(),
            key="add_ingredient_expiry",
        )

    if st.button("추가", key="add_ingredient_submit", type="primary"):
        if name:
            fridge.upsert(user_id, name, expiry_date)
            st.success(f"{name} 추가됨")
            st.rerun()
        else:
            st.warning("재료를 선택해주세요")
