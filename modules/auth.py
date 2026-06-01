"""운영자 권한 — `ADMIN_USER_IDS` 콤마 구분 환경변수 화이트리스트."""

import os
import re

ENV_KEY = "ADMIN_USER_IDS"

# 유니코드 단어문자·숫자·`_`·`-`·공백 (1~64자). `.` `/` `\` `:` 자동 거부.
_USER_ID_RE = re.compile(r"[\w \-]{1,64}", re.UNICODE)


def is_valid_user_id(user_id: str) -> bool:
    """경로 traversal·주입 차단 — `..` / 양끝 공백 / 빈 값 거부."""
    if not user_id or user_id != user_id.strip():
        return False
    if ".." in user_id:
        return False
    return _USER_ID_RE.fullmatch(user_id) is not None


def get_admin_ids() -> set[str]:
    raw = os.getenv(ENV_KEY, "")
    return {part.strip() for part in raw.split(",") if part.strip()}


def is_admin(user_id: str) -> bool:
    if not user_id:
        return False
    return user_id in get_admin_ids()
