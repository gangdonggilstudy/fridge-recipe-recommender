"""`st.session_state` 키 중앙 관리 — 매직 문자열 분산 방지."""


class SessionKeys:
    """전역 session_state 키 모음. 인스턴스화 금지 — 클래스 속성으로만 접근."""

    USER_ID = "user_id"
    LAST_IMPRESSION_SIGNATURE = "last_impression_signature"
    LAST_IMPRESSION_SESSION_ID = "last_impression_session_id"
    WITHDRAW_CONFIRM = "withdraw_confirm"  # 데이터 철회 2단계 확정 플래그

    # ── 음성 입력 (Voice Input) ──
    VOICE_TRANSCRIPT = "voice_transcript"          # STT 원본 텍스트
    VOICE_PARSED_ITEMS = "voice_parsed_items"      # ParsedItem 리스트
    VOICE_PREVIEW_OPEN = "voice_preview_open"      # 다이얼로그 트리거
    VOICE_PREVIEW_NONCE = "voice_preview_nonce"    # 인식 회차마다 갱신 — 다이얼로그 widget 키 prefix 에 포함되어 이전 회차 상태 잔재 차단

    # ── 영수증 입력 (Receipt OCR) ──
    RECEIPT_PARSED_ITEMS = "receipt_parsed_items"  # ParsedItem 리스트
    RECEIPT_PREVIEW_OPEN = "receipt_preview_open"  # 다이얼로그 트리거
    RECEIPT_PREVIEW_NONCE = "receipt_preview_nonce"  # 음성과 동일 — 인식 회차마다 갱신
    RECEIPT_CONSENT = "receipt_consent"            # 세션 옵트인 동의(이미지 외부전송)

    # ── 사용자별 컨텍스트 분석기 (위치 해결 결과 캐시) ──
    CONTEXT_ANALYZER = "context_analyzer"
    CONTEXT_ANALYZER_USER = "context_analyzer_user"  # 캐시 무효화 키

    AI_DESC_PREFIX = "ai_desc_"
    RESTRICTION_EDIT_PREFIX = "restr_edit_"
    LAST_RESULTS_PREFIX = "last_results_"
    LAST_CTX_PREFIX = "last_ctx_"
    DETAIL_OPEN_PREFIX = "detail_open_"  # 사용자별 현재 펼쳐진 상세 카드 recipe_id
    PICKED_IN_SESSION_PREFIX = "picked_in_session_"  # 사용자별 (impression_session_id, picked recipe_id set)
    DISLIKED_IN_SESSION_PREFIX = "disliked_in_session_"  # 사용자별 (impression_session_id, disliked recipe_id set)

    @staticmethod
    def ai_desc_for(recipe_id: str) -> str:
        """추천 카드별 LLM 설명 캐시 키."""
        return f"{SessionKeys.AI_DESC_PREFIX}{recipe_id}"

    @staticmethod
    def restriction_edit_for(user_id: str) -> str:
        """사용자별 제한 재료 multiselect 위젯 키."""
        return f"{SessionKeys.RESTRICTION_EDIT_PREFIX}{user_id}"

    @staticmethod
    def last_results_for(user_id: str) -> str:
        """사용자별 마지막 추천 결과 세션 키."""
        return f"{SessionKeys.LAST_RESULTS_PREFIX}{user_id}"

    @staticmethod
    def last_ctx_for(user_id: str) -> str:
        """사용자별 마지막 컨텍스트 세션 키."""
        return f"{SessionKeys.LAST_CTX_PREFIX}{user_id}"

    @staticmethod
    def detail_open_for(user_id: str) -> str:
        """리스트→상세 흐름에서 현재 펼쳐진 recipe_id (없으면 닫힘)."""
        return f"{SessionKeys.DETAIL_OPEN_PREFIX}{user_id}"

    @staticmethod
    def picked_in_session_for(user_id: str) -> str:
        """현재 추천 세션 내에서 이미 선택 학습 신호를 기록한 recipe_id 집합 키.

        새 추천 세션(impression_session_id 변경)에서는 자동 초기화 — 같은 리스트
        안에서 같은 음식을 여러 번 눌러도 history 학습 신호는 1회만 들어간다.
        """
        return f"{SessionKeys.PICKED_IN_SESSION_PREFIX}{user_id}"

    @staticmethod
    def disliked_in_session_for(user_id: str) -> str:
        """현재 추천 세션 내에서 '별로에요' 누른 recipe_id 집합 키.

        picked_in_session 과 동일 구조 `(impression_session_id, set[recipe_id])`.
        같은 추천 화면에서 별로에요는 메뉴당 1회만 — 클릭↔별로에요 사이클로
        -1.5 학습 신호가 무한 누적되는 것을 막는다. 새 추천 시 자동 초기화.
        """
        return f"{SessionKeys.DISLIKED_IN_SESSION_PREFIX}{user_id}"
