"""음성 입력 — 녹음 → STT → 파싱 → 미리보기 다이얼로그 → fridge 일괄 upsert."""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from llm.ingredient_parser import IngredientParser, ParsedItem
from modules.fridge_repo import FridgeRepo
from modules.logging_setup import get_logger
from modules.stt_engine import STTEngine
from ui._item_confirm import (
    cleanup_preview_state,
    render_confirm_body,
    store_preview_and_rerun,
)
from ui.session_keys import SessionKeys

_logger = get_logger(__name__)


def render(
    user_id: str,
    fridge: FridgeRepo,
    parser: IngredientParser,
    stt: STTEngine,
) -> None:
    """냉장고 탭 안에 음성 입력 expander 렌더링.

    호출자가 stt/parser None 체크 후 호출하므로 여기선 신뢰함.
    """
    with st.expander("🎤 음성으로 추가 (베타)", expanded=False):
        st.caption('예: "양파, 계란, 두부" — 재료 이름만 추출합니다. 녹음 후 확인하고 추가하세요.')

        audio = st.audio_input(
            "마이크 녹음",
            key="voice_audio_recorder",
            label_visibility="collapsed",
        )

        if audio is not None and st.button(
            "🔍 인식 시작", type="primary", use_container_width=True,
            key="voice_recognize",
        ):
            _process_audio(audio, parser, stt)

    # 다이얼로그 트리거 — 처리 결과가 세션에 있으면 표시.
    # parser.canonical_names 를 전달해 다이얼로그가 미등록 재료를 저장 시 차단.
    if st.session_state.get(SessionKeys.VOICE_PREVIEW_OPEN):
        _preview_dialog(user_id, fridge, set(parser.canonical_names))


def _process_audio(audio, parser: IngredientParser, stt: STTEngine) -> None:
    """audio_input 결과를 STT + parse 처리하여 세션에 저장."""
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False
        ) as tmp:
            tmp.write(audio.getvalue())
            tmp_path = Path(tmp.name)

        with st.spinner("음성 인식 중..."):
            transcript = stt.transcribe(tmp_path)

        if not transcript:
            st.toast("인식된 내용이 없습니다 — 다시 녹음해주세요", icon="⚠️")
            return

        items = parser.parse(transcript)
        if not items:
            st.toast(f'인식: "{transcript}" — 재료를 추출하지 못했습니다', icon="⚠️")
            return

        # 세션에 결과 저장 → 다이얼로그 트리거 (voice/receipt 공통 흐름).
        # transcript 는 voice 전용이라 extras 로 함께 저장.
        store_preview_and_rerun(
            items,
            key_prefix="voice",
            items_key=SessionKeys.VOICE_PARSED_ITEMS,
            nonce_key=SessionKeys.VOICE_PREVIEW_NONCE,
            open_key=SessionKeys.VOICE_PREVIEW_OPEN,
            extras={SessionKeys.VOICE_TRANSCRIPT: transcript},
        )
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError as e:
                _logger.warning("임시 파일 삭제 실패: %s", e)


@st.dialog("🎤 음성 인식 결과 확인")
def _preview_dialog(user_id: str, fridge: FridgeRepo, allowed_names: set[str]) -> None:
    """파싱 결과 미리보기 + 사용자 확정 (공유 본문 — 영수증과 동일 UX).

    allowed_names: canonical 재료 풀. 저장 시점에 미등록 재료를 자동 제외한다.
    """
    transcript = st.session_state.get(SessionKeys.VOICE_TRANSCRIPT, "")
    items: list[ParsedItem] = st.session_state.get(
        SessionKeys.VOICE_PARSED_ITEMS, []
    )
    nonce = st.session_state.get(SessionKeys.VOICE_PREVIEW_NONCE, "")
    render_confirm_body(
        items=items,
        source_caption=f'인식 결과: "{transcript}"',
        key_prefix=f"voice_{nonce}",
        user_id=user_id,
        fridge=fridge,
        on_done=_clear_voice_state,
        allowed_names=allowed_names,
    )


def _clear_voice_state() -> None:
    cleanup_preview_state(
        key_prefix="voice",
        nonce_key=SessionKeys.VOICE_PREVIEW_NONCE,
        keys_to_pop=(
            SessionKeys.VOICE_TRANSCRIPT,
            SessionKeys.VOICE_PARSED_ITEMS,
            SessionKeys.VOICE_PREVIEW_OPEN,
            SessionKeys.VOICE_PREVIEW_NONCE,
        ),
    )
