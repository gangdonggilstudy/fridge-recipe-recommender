"""환경변수 불리언 파싱 단일 출처."""

import os

_TRUE = {"1", "true", "yes", "on", "y", "t"}
_FALSE = {"0", "false", "no", "off", "n", "f"}


def env_flag(name: str, *, default: bool) -> bool:
    """환경변수를 불리언으로 해석. 미설정/빈값/미인식이면 default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return default
