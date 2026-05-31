"""영수증 OCR — 별도 동의 필수, 이미지 비저장. RECEIPT_OCR_ENABLED 게이팅."""
from __future__ import annotations

from io import BytesIO

import streamlit as st

from llm.receipt_parser import ReceiptParser
from modules.fridge_repo import FridgeRepo
from ui._defaults import RECEIPT_JPEG_QUALITY, RECEIPT_MAX_PX
from ui._item_confirm import (
    cleanup_preview_state,
    render_confirm_body,
    store_preview_and_rerun,
)
from ui.session_keys import SessionKeys


def _maybe_downscale(
    data: bytes, mime: str, max_px: int = RECEIPT_MAX_PX
) -> tuple[bytes, str]:
    """Pillow 가용 시 장변 max_px 로 축소(JPEG). 없거나 실패 시 원본 그대로.

    토큰·비용 상한 목적의 best-effort — 하드 의존성 아님(graceful).
    """
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError:
        return data, mime
    try:
        img = Image.open(BytesIO(data))
        w, h = img.size
        if max(w, h) <= max_px:
            # 축소 불필요 → 원본 그대로(불필요한 재인코딩·품질손실 회피)
            return data, mime
        scale = max_px / max(w, h)
        img = img.convert("RGB").resize((int(w * scale), int(h * scale)))
        out = BytesIO()
        img.save(out, format="JPEG", quality=RECEIPT_JPEG_QUALITY)
        return out.getvalue(), "image/jpeg"
    except Exception:  # noqa: BLE001 — 축소 실패는 원본 전송으로 폴백
        return data, mime


def render(user_id: str, fridge: FridgeRepo, receipt_parser: ReceiptParser) -> None:
    """냉장고 탭 안에 영수증 입력 expander 렌더링."""
    with st.expander("🧾 영수증으로 추가 (베타)", expanded=False):
        st.caption(
            "영수증 사진을 올리면 품목을 추출합니다. 미리보기에서 확인·수정 후 추가됩니다."
        )

        # 별도 옵트인 동의 — 이미지가 외부 AI(Gemini)로 전송되는 민감 입력
        consent = st.checkbox(
            "영수증 이미지가 외부 AI(Gemini)로 전송되어 품목 인식에 사용됨에 "
            "동의합니다. 이미지는 저장되지 않습니다.",
            value=st.session_state.get(SessionKeys.RECEIPT_CONSENT, False),
            key="receipt_consent_chk",
        )
        st.session_state[SessionKeys.RECEIPT_CONSENT] = consent

        if not consent:
            st.info("동의 후 영수증 업로드가 활성화됩니다.")
        else:
            tab_up, tab_cam = st.tabs(["📁 파일 업로드", "📷 촬영"])
            with tab_up:
                up = st.file_uploader(
                    "영수증 이미지", type=["jpg", "jpeg", "png"],
                    key="receipt_file", label_visibility="collapsed",
                )
            with tab_cam:
                cam = st.camera_input(
                    "영수증 촬영", key="receipt_cam",
                    label_visibility="collapsed",
                )

            src = up or cam
            if src is not None and st.button(
                "🔍 인식 시작", type="primary",
                use_container_width=True, key="receipt_recognize",
            ):
                _process_image(src, receipt_parser)

    # 다이얼로그가 미등록 재료를 저장 시 차단하도록 canonical 풀 전달
    # (ReceiptParser 가 IngredientParser 를 재사용 → canonical_names 공유).
    if st.session_state.get(SessionKeys.RECEIPT_PREVIEW_OPEN):
        _preview_dialog(user_id, fridge, set(receipt_parser._ip.canonical_names))


def _process_image(src, receipt_parser: ReceiptParser) -> None:
    """업로드/촬영 이미지를 OCR 처리하여 세션에 저장 (이미지 비저장)."""
    data = src.getvalue()
    mime = getattr(src, "type", None) or "image/jpeg"
    data, mime = _maybe_downscale(data, mime)

    with st.spinner("영수증 인식 중..."):
        items = receipt_parser.parse(data, mime)

    if not items:
        st.toast(
            "영수증에서 품목을 추출하지 못했습니다 — 다시 시도하세요", icon="⚠️"
        )
        return

    # 세션 저장 + nonce 갱신 + rerun (voice/receipt 공통 흐름).
    store_preview_and_rerun(
        items,
        key_prefix="receipt",
        items_key=SessionKeys.RECEIPT_PARSED_ITEMS,
        nonce_key=SessionKeys.RECEIPT_PREVIEW_NONCE,
        open_key=SessionKeys.RECEIPT_PREVIEW_OPEN,
    )


@st.dialog("🧾 영수증 인식 결과 확인")
def _preview_dialog(user_id: str, fridge: FridgeRepo, allowed_names: set[str]) -> None:
    """인식 결과 미리보기 + 확정 (음성과 동일 공유 본문).

    allowed_names: canonical 재료 풀. 저장 시점에 미등록 재료를 자동 제외한다 —
    LLM 영수증 응답이 임의 품목명을 만들어도 fridge 에 들어가지 않도록.
    """
    items = st.session_state.get(SessionKeys.RECEIPT_PARSED_ITEMS, [])
    nonce = st.session_state.get(SessionKeys.RECEIPT_PREVIEW_NONCE, "")
    render_confirm_body(
        items=items,
        source_caption="영수증에서 추출한 품목입니다. 확인·수정 후 추가하세요.",
        key_prefix=f"receipt_{nonce}",
        user_id=user_id,
        fridge=fridge,
        on_done=_clear_receipt_state,
        allowed_names=allowed_names,
    )


def _clear_receipt_state() -> None:
    """파싱·다이얼로그 상태만 정리. 동의(RECEIPT_CONSENT)는 세션 유지."""
    cleanup_preview_state(
        key_prefix="receipt",
        nonce_key=SessionKeys.RECEIPT_PREVIEW_NONCE,
        keys_to_pop=(
            SessionKeys.RECEIPT_PARSED_ITEMS,
            SessionKeys.RECEIPT_PREVIEW_OPEN,
            SessionKeys.RECEIPT_PREVIEW_NONCE,
        ),
    )
