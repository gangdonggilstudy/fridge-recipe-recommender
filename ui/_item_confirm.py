"""인식 결과 확정 다이얼로그 본문 — 음성/영수증 공유. `key_prefix` 로 충돌 회피."""
from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from llm.ingredient_parser import CONFIDENCE_EXACT, CONFIDENCE_FUZZY, ParsedItem
from modules.fridge_repo import FridgeRepo


def cleanup_preview_state(
    *,
    key_prefix: str,
    nonce_key: str,
    keys_to_pop: tuple[str, ...],
) -> None:
    """다이얼로그 닫기 시 nonce widget 잔재 + 세션 키 정리.

    `store_preview_and_rerun` 의 거울 — 인식 다이얼로그 흐름이 완료(저장/취소)
    되거나 X 닫기 후 호출되어 다음 회차가 깨끗한 상태에서 시작되도록 한다.

    voice/receipt 양쪽이 공유하는 공통 정리 흐름.
    """
    old_nonce = st.session_state.get(nonce_key, "")
    if old_nonce:
        cleanup_widget_state_by_prefix(f"{key_prefix}_{old_nonce}_")
    for key in keys_to_pop:
        st.session_state.pop(key, None)


def cleanup_widget_state_by_prefix(prefix: str) -> None:
    """`prefix` 로 시작하는 session_state 키 전부 삭제.

    음성·영수증 다이얼로그가 회차마다 nonce 를 갱신해 widget 정체성을 새로 만들 때,
    이전 회차의 잔재 키(`{voice|receipt}_{nonce}_chk_0` 등)를 정리한다.
    사용자가 다이얼로그를 X 로 닫아 on_done 미호출 경로에서도 누적이 없도록.
    """
    for key in [k for k in st.session_state if isinstance(k, str) and k.startswith(prefix)]:
        del st.session_state[key]


def store_preview_and_rerun(
    items: list[ParsedItem],
    *,
    key_prefix: str,
    items_key: str,
    nonce_key: str,
    open_key: str,
    extras: dict | None = None,
) -> None:
    """인식 결과 미리보기 세션 저장 + rerun 공통 흐름 (voice/receipt 공유).

    - 이전 nonce 가 있으면 widget 상태 cleanup (이전 회차 잔재 차단)
    - items + extras 세션 저장 → 새 nonce 발급 → open=True → rerun

    voice 의 transcript 처럼 모듈별 추가 키는 `extras` 로 함께 저장한다.
    """
    import uuid  # noqa: PLC0415 — lazy (호출 빈도 낮음, 모듈 import 부담 회피)

    old_nonce = st.session_state.get(nonce_key, "")
    if old_nonce:
        cleanup_widget_state_by_prefix(f"{key_prefix}_{old_nonce}_")
    st.session_state[items_key] = items
    for k, v in (extras or {}).items():
        st.session_state[k] = v
    st.session_state[nonce_key] = uuid.uuid4().hex[:8]
    st.session_state[open_key] = True
    st.rerun()


def render_confirm_body(
    *,
    items: list[ParsedItem],
    source_caption: str,
    key_prefix: str,
    user_id: str,
    fridge: FridgeRepo,
    on_done: Callable[[], None],
    allowed_names: set[str] | None = None,
) -> None:
    """확정 다이얼로그 본문. 저장/취소/빈결과 모두 on_done() 후 rerun.

    `allowed_names` 전달 시 — 저장 시점에 각 항목 이름이 해당 집합에 있는지 검증.
    미등록 재료는 skip + toast 안내. 사용자가 text_input 으로 이름을 수정했을 때
    canonical 풀을 벗어난 임의 텍스트가 fridge 에 들어가지 않도록 차단.
    None 이면 검증 없음 (테스트·하위호환 경로).
    """
    st.caption(source_caption)

    if not items:
        st.warning("재료를 추출하지 못했습니다.")
        if st.button("닫기", use_container_width=True, key=f"{key_prefix}_close"):
            on_done()
            st.rerun()
        return

    st.write("**저장할 항목을 선택하고 필요 시 이름을 수정하세요:**")

    edited: list[tuple[bool, str]] = []
    for i, item in enumerate(items):
        with st.container(border=True):
            col_chk, col_name = st.columns([1, 7])

            checked = col_chk.checkbox(
                "포함", value=True, key=f"{key_prefix}_chk_{i}",
                label_visibility="collapsed",
            )
            name = col_name.text_input(
                "재료", value=item.name, key=f"{key_prefix}_name_{i}",
                label_visibility="collapsed",
            )

            if item.confidence < CONFIDENCE_EXACT:
                badge = "표준 외 재료" if item.confidence < CONFIDENCE_FUZZY else "유사 매칭"
                st.caption(f"⚠ {badge} (confidence {item.confidence:.1f})")

            edited.append((checked, name))

    st.divider()
    st.caption("유통기한은 냉장고 화면에서 별도로 설정할 수 있습니다.")
    if allowed_names is not None:
        st.caption("⚠ 시스템에 등록된 재료만 추가됩니다. 미등록 재료는 자동 제외.")

    col_save, col_cancel = st.columns(2)
    if col_save.button(
        "선택 항목 추가", type="primary", use_container_width=True,
        key=f"{key_prefix}_save",
    ):
        saved = 0
        skipped: list[str] = []
        for checked, name in edited:
            clean = name.strip()
            if not checked or not clean:
                continue
            if allowed_names is not None and clean not in allowed_names:
                skipped.append(clean)
                continue
            fridge.upsert(user_id, clean)
            saved += 1
        if saved:
            st.toast(f"{saved}개 재료 추가됨 ✅")
        if skipped:
            preview = ", ".join(skipped[:3]) + (" 등" if len(skipped) > 3 else "")
            st.toast(f"⚠ 미등록 재료 {len(skipped)}개 제외: {preview}", icon="⚠️")
        on_done()
        st.rerun()

    if col_cancel.button(
        "취소", use_container_width=True, key=f"{key_prefix}_cancel"
    ):
        on_done()
        st.rerun()
