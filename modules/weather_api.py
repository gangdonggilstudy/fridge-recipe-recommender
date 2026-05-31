"""OpenWeatherMap → 맑음/비/눈/더위/추위 5종 enum (코드 + 기온)."""

import requests

# OpenWeatherMap 코드 분류 (https://openweathermap.org/weather-conditions)
# code // 100 기준
RAIN_CODE_PREFIXES = {3, 5}   # 3xx: drizzle, 5xx: rain
SNOW_CODE_PREFIX = 6           # 6xx: snow

# 기온 임계 (섭씨)
HOT_TEMP_C = 28.0
COLD_TEMP_C = 5.0


class WeatherAPI:
    """OpenWeatherMap 기반 날씨 조회. 도시명 또는 좌표(lat/lon) 지원."""

    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
    TIMEOUT = 5  # seconds

    def __init__(
        self,
        api_key: str,
        city: str | None = None,
        *,
        lat: float | None = None,
        lon: float | None = None,
    ):
        if city is None and (lat is None or lon is None):
            raise ValueError("city 또는 lat+lon 중 하나는 필수")
        self.api_key = api_key
        self.city = city
        self.lat = lat
        self.lon = lon

    def get_weather(self) -> str:
        """현재 날씨를 시스템 enum 값으로 반환. 실패 시 예외 발생.

        좌표(lat/lon)가 주어지면 좌표 기반, 아니면 city 명 기반 조회.
        """
        params: dict[str, str | float] = {"appid": self.api_key, "units": "metric"}
        if self.lat is not None and self.lon is not None:
            params["lat"] = self.lat
            params["lon"] = self.lon
        else:
            params["q"] = self.city  # type: ignore[assignment]
        resp = requests.get(self.BASE_URL, params=params, timeout=self.TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # 빈 리스트/키 누락 시 IndexError·KeyError 가 호출 스택을 오염시키지 않도록
        # ValueError 로 일관화 — provider 레이어 fallback 흐름이 같은 예외만 잡으면 됨.
        weather_list = data.get("weather") or []
        main = data.get("main") or {}
        if not weather_list or "temp" not in main:
            raise ValueError(f"unexpected OpenWeatherMap response shape: {data!r:.200}")
        return self._classify(weather_list[0]["id"], main["temp"])

    @staticmethod
    def _classify(code: int, temp: float) -> str:
        prefix = code // 100
        if prefix in RAIN_CODE_PREFIXES:
            return "비"
        if prefix == SNOW_CODE_PREFIX:
            return "눈"
        if temp >= HOT_TEMP_C:
            return "더위"
        if temp <= COLD_TEMP_C:
            return "추위"
        return "맑음"


class StaticWeatherProvider:
    """모킹·테스트·오프라인용 정적 날씨 제공자."""

    def __init__(self, weather: str = "맑음"):
        self.weather = weather

    def get_weather(self) -> str:
        return self.weather
