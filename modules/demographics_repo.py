"""인구통계 (성별·나이대) — cold-start 그룹 평균 벡터. 식별·건강정보 불수집."""

from pathlib import Path

from ._base_repo import BaseRepository
from .db_init import ensure_user


class DemographicsRepo(BaseRepository):
    """성별·나이대 저장 + 그룹 평균 벡터 (cold-start 한정 활용)."""

    def __init__(self, db_path: str | Path | None = None, init_app_db: bool = True):
        super().__init__(db_path, init_app_db=init_app_db)

    def save_demographics(
        self,
        user_id: str,
        gender: str | None,
        age_group: str | None,
    ) -> None:
        """성별·나이대를 users 테이블에 저장. None 은 '선택 안 함' 으로 처리."""
        ensure_user(self.db_path, user_id)
        with self._connect() as con:
            con.execute(
                "UPDATE users SET gender = ?, age_group = ? WHERE user_id = ?",
                (gender or None, age_group or None, user_id),
            )
            con.commit()

    def get_demographics(self, user_id: str) -> tuple[str | None, str | None]:
        """(gender, age_group) 반환. 미설정이면 (None, None)."""
        with self._connect() as con:
            row = con.execute(
                "SELECT gender, age_group FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return (None, None)
        return (row["gender"], row["age_group"])

    def get_group_vector(
        self,
        gender: str | None,
        age_group: str | None,
    ) -> dict[str, float]:
        """같은 성별·나이대 사용자 선호 벡터 평균. 데이터 없으면 빈 dict.

        gender·age_group 모두 None 이면 빈 dict (보정 불가).
        한쪽만 지정 시 해당 조건만 필터링.
        """
        if not gender and not age_group:
            return {}

        conditions: list[str] = []
        params: list[str] = []
        if gender:
            conditions.append("gender = ?")
            params.append(gender)
        if age_group:
            conditions.append("age_group = ?")
            params.append(age_group)

        where = " AND ".join(conditions)
        with self._connect() as con:
            user_rows = con.execute(
                f"SELECT user_id FROM users WHERE {where}", params
            ).fetchall()
            if not user_rows:
                return {}

            uids = [r["user_id"] for r in user_rows]
            placeholders = ",".join("?" * len(uids))
            vec_rows = con.execute(
                f"SELECT feature, AVG(value) AS avg_val "
                f"FROM preference_vectors "
                f"WHERE user_id IN ({placeholders}) "
                f"GROUP BY feature",
                uids,
            ).fetchall()

        return {r["feature"]: r["avg_val"] for r in vec_rows}
