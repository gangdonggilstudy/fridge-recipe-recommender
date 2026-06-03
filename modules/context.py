"""상황 분석 (시간대/월/날씨) — 월 해상도가 계절보다 3배 (명절·제철)."""

from datetime import date, datetime

from .contracts import Context
from .logging_setup import get_logger

_logger = get_logger(__name__)


# (start, end) end 미포함. 야식 22~다음날 5시는 hour+24 정규화로 22~30 매칭.
TIME_RANGES: dict[str, tuple[int, int]] = {
    "아침": (6, 11),
    "점심": (11, 15),
    "저녁": (17, 22),
    "야식": (22, 30),
}

# 시간 정규화 — 야식 매칭용 (0~5시 → 24~29시로 시프트)
NIGHT_END_HOUR = 6
HOURS_PER_DAY = 24


# 가설 가중치 (운영 데이터로 재산출 예정). Cramér's V 효과 크기 추정 — 합 1.0.
CONTEXT_WEIGHTS: dict[str, float] = {
    "time":    0.55,
    "weather": 0.29,
    "month":   0.16,
}


# 계절 ↔ 월 매핑 — UI 입력은 계절 4개로 받고 내부에서 자동 확장,
# 추천·표시 측은 month_to_season() 으로 역변환 (라벨링·점수는 월 기반)
SEASON_TO_MONTHS: dict[str, list[int]] = {
    "봄":   [3, 4, 5],
    "여름": [6, 7, 8],
    "가을": [9, 10, 11],
    "겨울": [12, 1, 2],
}

# 역방향 lookup pre-compute — month_to_season 이 narrator/UI 에서 빈번 호출되어
# 매번 4×3 선형 탐색하는 부담을 O(1) dict lookup 으로 교체.
# SEASON_TO_MONTHS(계절→월목록)를 뒤집어 {월: 계절} 사전을 미리 만들어 둔다.
#  ex) {3:"봄", 4:"봄", 5:"봄", 6:"여름", ...}
_MONTH_TO_SEASON: dict[int, str] = {
    m: s for s, ms in SEASON_TO_MONTHS.items() for m in ms
}


def get_time_label(hour: int) -> str:
    """0~23 범위 시각을 시간대 라벨로 변환. 매칭 없으면 '점심' 기본."""
    if hour < 0 or hour >= HOURS_PER_DAY:
        raise ValueError(f"hour out of range: {hour}")
    # 야식 범위는 22~30시로 정의돼 있음. 자정 넘은 0~5시는 +24 해야 이 범위에 들어옴.
    #  ex) 새벽 2시 → 26 → 야식(22~30) 매칭.
    adjusted = hour + HOURS_PER_DAY if hour < NIGHT_END_HOUR else hour
    for label, (start, end) in TIME_RANGES.items():
        if start <= adjusted < end:
            return label
    return "점심"  # 어느 구간에도 안 들면(15~17시) 기본값 점심


def get_month(today: date | None = None) -> str:
    """현재 날짜 기반 월 라벨 자동 인식. 반환: '1월'~'12월'."""
    if today is None:
        today = date.today()
    return f"{today.month}월"


def month_to_season(month: str) -> str | None:
    """월 라벨('9월') → 계절('가을'). UI 표시·자연어 narrator 용도."""
    try:
        month_num = int(month.rstrip("월"))
    except (ValueError, AttributeError):
        return None
    return _MONTH_TO_SEASON.get(month_num)


def _compute_month_season_match(
    context_month: str | None,
    suitable_months: list[str] | None,
) -> tuple[bool, bool]:
    """`temporal_fit_score` 전용 내부 헬퍼 — 외부에서 호출 금지.

    월·계절 매칭을 (month_match, season_match) 튜플로 분리 계산. 외부에는
    `temporal_fit_score` 의 단일 서수만 노출하고, 이 함수는 그 내부 단계로만 존재.

    - month_match: `context_month ∈ suitable_months`
    - season_match: `month_to_season(context_month)` 가 suitable_months 의 어느 월의 계절과 일치
    """
    if not context_month or not suitable_months:
        return False, False
    # month_match: 지금 '월'(예: 6월)이 레시피의 어울리는 월 목록에 정확히 있는가.
    month_match = context_month in suitable_months
    season = month_to_season(context_month)
    if not season:
        return month_match, False
    # season_match: 레시피 어울리는 월들이 속한 '계절' 집합에 지금 계절이 포함되는가.
    #  (월보다 느슨한 신호 — 6월은 안 맞아도 '여름'은 맞을 수 있음)
    recipe_seasons = {s for m in suitable_months if (s := month_to_season(m))}
    season_match = season in recipe_seasons
    return month_match, season_match


def temporal_fit_score(
    context_month: str | None,
    suitable_months: list[str] | None,
) -> float:
    """월·계절 적합을 단일 서수로 — 1.0 월일치 / 0.5 계절만 / 0.0 불일치.

    month_match ⟹ season_match 포함 관계라 두 차원은 공선 중복(계절 확장
    레시피에선 동일 열). 0.5 단계(계절만 일치)만 고유 정보 → 한 서수로 통합.
    history INSERT 와 build_feature 가 공유하는 단일 출처.
    """
    month_match, season_match = _compute_month_season_match(context_month, suitable_months)
    if month_match:
        return 1.0
    if season_match:
        return 0.5
    return 0.0


def get_current_hour(now: datetime | None = None) -> int:
    if now is None:
        now = datetime.now()
    return now.hour


class ContextAnalyzer:
    """시간·날씨·월을 한 번에 조립하는 헬퍼."""

    def __init__(self, weather_provider=None):
        """weather_provider: get_weather() -> str 메서드를 가진 객체. None이면 '맑음' 사용."""
        self.weather_provider = weather_provider

    def get_context(self, now: datetime | None = None) -> Context:
        now = now or datetime.now()
        hour = now.hour
        weather = self._fetch_weather()
        month = get_month(now.date())
        return {
            "hour":    hour,
            "time":    get_time_label(hour),
            "weather": weather,
            "month":   month,
            "season":  month_to_season(month) or "봄",
        }

    def _fetch_weather(self) -> str:
        if self.weather_provider is None:
            return "맑음"
        try:
            return self.weather_provider.get_weather()
        except Exception as e:  # noqa: BLE001 — 외부 API/네트워크 어떤 실패든 안전 폴백
            _logger.warning("날씨 조회 실패, '맑음'으로 폴백: %s", e)
            return "맑음"
