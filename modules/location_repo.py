"""사용자 위치 (users 테이블 city/lat/lon/source/updated_at)."""

from pathlib import Path

from ._base_repo import BaseRepository
from .db_init import ensure_user


# 유효한 source 값 (location_resolver 와 UI 양쪽에서 검증용)
VALID_SOURCES = {"browser", "ip", "manual", "default"}


class LocationRepo(BaseRepository):
    """사용자 위치 저장·조회."""

    def __init__(self, db_path: str | Path | None = None, init_app_db: bool = True):
        super().__init__(db_path, init_app_db=init_app_db)

    def save(
        self,
        user_id: str,
        *,
        source: str,
        city: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
    ) -> None:
        """위치 저장. source 는 추정 경로 라벨 (browser/ip/manual/default).

        lat/lon 둘 다 None 이면 도시명만 저장 (지오코딩은 호출자 책임).
        """
        if source not in VALID_SOURCES:
            raise ValueError(f"source must be one of {VALID_SOURCES}, got {source!r}")
        ensure_user(self.db_path, user_id)
        with self._connect() as con:
            con.execute(
                """UPDATE users
                   SET city = ?, lat = ?, lon = ?, location_source = ?,
                       location_updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ?""",
                (city, lat, lon, source, user_id),
            )
            con.commit()

    def get(self, user_id: str) -> dict | None:
        """저장된 위치. 없거나 source 가 NULL 이면 None."""
        with self._connect() as con:
            row = con.execute(
                """SELECT city, lat, lon, location_source, location_updated_at
                   FROM users WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
        if not row or row["location_source"] is None:
            return None
        return {
            "city": row["city"],
            "lat": row["lat"],
            "lon": row["lon"],
            "source": row["location_source"],
            "updated_at": row["location_updated_at"],
        }

    def clear(self, user_id: str) -> None:
        """위치 정보만 초기화 (사용자 자체는 유지)."""
        with self._connect() as con:
            con.execute(
                """UPDATE users
                   SET city = NULL, lat = NULL, lon = NULL,
                       location_source = NULL, location_updated_at = NULL
                   WHERE user_id = ?""",
                (user_id,),
            )
            con.commit()
