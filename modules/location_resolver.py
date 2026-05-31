"""위치 해결 폴백: DB → IP(ipapi.co, 공인 IP만) → `WEATHER_CITY` (서울 기본)."""

import ipaddress
import os
from typing import Literal

import requests

from .location_repo import LocationRepo
from .logging_setup import get_logger

_logger = get_logger(__name__)

# 기본값 (서울시청 좌표)
DEFAULT_CITY = "Seoul"
DEFAULT_LAT = 37.5665
DEFAULT_LON = 126.9780

# IP 지오로케이션 서비스
IPAPI_URL = "https://ipapi.co/{ip}/json/"
IPAPI_TIMEOUT_SEC = 3


Source = Literal["db", "ip", "default"]


def resolve(
    user_id: str,
    repo: LocationRepo,
    *,
    client_ip: str | None = None,
) -> tuple[float, float, str, Source]:
    """위치 결정. 반환: (lat, lon, city, source).

    source:
        - 'db': repo 에 저장된 위치 (1순위, 가장 안정적)
        - 'ip': client_ip → ipapi.co 추정 결과 (저장도 함께 수행)
        - 'default': WEATHER_CITY 환경변수 기본값 (서울)
    """
    # 1순위: DB
    loc = repo.get(user_id)
    if loc and loc.get("lat") is not None and loc.get("lon") is not None:
        return loc["lat"], loc["lon"], loc.get("city") or "?", "db"

    # 2순위: IP 추정 (공인 IP 만)
    if client_ip:
        ip_loc = _fetch_ip_location(client_ip)
        if ip_loc:
            repo.save(
                user_id,
                source="ip",
                city=ip_loc["city"],
                lat=ip_loc["lat"],
                lon=ip_loc["lon"],
            )
            return ip_loc["lat"], ip_loc["lon"], ip_loc["city"], "ip"

    # 3순위: 환경변수 기본값
    default_city = os.getenv("WEATHER_CITY", DEFAULT_CITY)
    return DEFAULT_LAT, DEFAULT_LON, default_city, "default"


def _fetch_ip_location(ip: str) -> dict | None:
    """ipapi.co 호출. 사설망·실패 시 None."""
    if _is_private_ip(ip):
        return None
    try:
        resp = requests.get(IPAPI_URL.format(ip=ip), timeout=IPAPI_TIMEOUT_SEC)
        if resp.status_code != 200:
            return None
        data = resp.json()
        # ipapi.co 는 실패 시 'error': True 또는 latitude 누락
        if data.get("error") or data.get("latitude") is None or data.get("longitude") is None:
            return None
        return {
            "lat": float(data["latitude"]),
            "lon": float(data["longitude"]),
            "city": data.get("city") or "?",
        }
    except (requests.RequestException, ValueError, KeyError) as e:
        _logger.warning("IP 지오로케이션 실패 (%s): %s", ip, e)
        return None


def _is_private_ip(ip: str) -> bool:
    """RFC1918 사설망 + loopback + link-local. 파싱 실패도 외부 호출 회피."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return True
