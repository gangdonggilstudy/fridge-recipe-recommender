"""
레시피 리뷰 키워드 일괄 생성.

전 레시피 순회 → ReviewAnalyzer 로 키워드 생성 → recipes.db UPDATE.
이미 채워진 레시피는 skip. 멱등 안전.

실행:
    python scripts/generate_review_keywords.py

LLM 미설정이면 스타일·맛 기반 fallback 사용.
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from llm.narrator import make_provider  # noqa: E402
from llm.review_analyzer import ReviewAnalyzer  # noqa: E402
from modules.normalize import split_multi  # noqa: E402


DB_PATH = PROJECT_ROOT / "data" / "recipes.db"


def main(force: bool = False) -> None:
    """recipes.db 의 빈 review_keywords 를 일괄 채움 (멱등, force 시 기존도 갱신)."""
    if not DB_PATH.exists():
        print(f"[ERROR] {DB_PATH} 없음. 먼저 build_recipes.py 실행 필요.")
        sys.exit(1)

    analyzer = ReviewAnalyzer(provider=make_provider())
    mode = "LLM" if analyzer.provider else "fallback (스타일·맛 기반)"
    print(f"[INFO] 키워드 생성 모드: {mode}")

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    rows = con.execute(
        "SELECT id, name, style, taste, review_keywords FROM recipes"
    ).fetchall()

    updated = 0
    skipped = 0
    for row in rows:
        if not force and row["review_keywords"]:
            skipped += 1
            continue
        taste = split_multi(row["taste"])
        keywords = analyzer.generate_keywords(
            recipe_name=row["name"],
            style=row["style"],
            taste=taste,
        )
        con.execute(
            "UPDATE recipes SET review_keywords = ? WHERE id = ?",
            (",".join(keywords), row["id"]),
        )
        updated += 1

    con.commit()
    con.close()

    print(f"[OK] 갱신 {updated}건, 스킵 {skipped}건 (총 {len(rows)}건)")


if __name__ == "__main__":
    force = "--force" in sys.argv
    main(force=force)
