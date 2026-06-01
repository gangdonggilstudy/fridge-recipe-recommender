"""레시피 키워드 투표 — LLM 라벨 agree/disagree 누적. (보존된 미사용 모듈)"""

from pathlib import Path

from llm.review_analyzer import REVIEW_KEYWORD_DIMS

from ._base_repo import BaseRepository


class KeywordVoteRepo(BaseRepository):
    """recipe_keyword_votes 전담 Repository."""

    def __init__(self, db_path: str | Path | None = None):
        super().__init__(db_path)

    def record_feedback(self, recipe_id: str, checked: list[str]) -> None:
        """사용자가 선택한 키워드를 투표로 기록.

        checked 목록이 비어 있으면 저장하지 않는다 — 미응답과 전체 미선택을 구분.
        checked → agree++, 나머지 REVIEW_KEYWORD_DIMS → disagree++.
        """
        if not checked:
            return
        checked_set = set(checked)
        with self._connect() as con:
            for keyword in REVIEW_KEYWORD_DIMS:
                con.execute(
                    "INSERT OR IGNORE INTO recipe_keyword_votes (recipe_id, keyword) VALUES (?, ?)",
                    (recipe_id, keyword),
                )
                if keyword in checked_set:
                    con.execute(
                        "UPDATE recipe_keyword_votes SET agree = agree + 1 "
                        "WHERE recipe_id = ? AND keyword = ?",
                        (recipe_id, keyword),
                    )
                else:
                    con.execute(
                        "UPDATE recipe_keyword_votes SET disagree = disagree + 1 "
                        "WHERE recipe_id = ? AND keyword = ?",
                        (recipe_id, keyword),
                    )
            con.commit()

    def get_votes(self, recipe_id: str) -> dict[str, dict]:
        """keyword → {agree, disagree, confidence} 반환.

        투표 데이터가 없는 키워드는 결과에 포함되지 않는다.
        confidence = agree / (agree + disagree), 투표 없으면 None.
        """
        with self._connect() as con:
            rows = con.execute(
                "SELECT keyword, agree, disagree FROM recipe_keyword_votes WHERE recipe_id = ?",
                (recipe_id,),
            ).fetchall()
        result = {}
        for r in rows:
            total = r["agree"] + r["disagree"]
            result[r["keyword"]] = {
                "agree": r["agree"],
                "disagree": r["disagree"],
                "confidence": r["agree"] / total if total > 0 else None,
            }
        return result
