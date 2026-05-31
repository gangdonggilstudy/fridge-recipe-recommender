"""UI 레벨 표현 상수 — `modules/` 비즈니스 상수와 분리."""

COMMON_INGREDIENTS: list[str] = [
    "계란", "대파", "마늘", "양파", "두부", "김치", "밥", "면",
]

DEFAULT_EXPIRY_DAYS_AHEAD: int = 7
# 'D-X 이내' 빨간색 강조 (그 외 회색).
EXPIRY_WARNING_DAYS: int = 3

# OVERFETCH → 세션 패스 필터 → DISPLAY 노출.
DISPLAY_N: int = 5
OVERFETCH_N: int = 10

COOK_TIME_MIN: int = 5
COOK_TIME_MAX: int = 180
COOK_TIME_DEFAULT: int = 20

# 장변 N px 다운스케일 후 JPEG 인코딩 — 토큰 비용 상한.
RECEIPT_MAX_PX: int = 1600
RECEIPT_JPEG_QUALITY: int = 85
