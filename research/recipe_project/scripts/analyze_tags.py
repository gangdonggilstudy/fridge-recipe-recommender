from __future__ import annotations

import re
import sqlite3
from collections import Counter
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "recipe_project.db"
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TAG_SPLIT_PATTERN = re.compile(r"[,/|;\n]+")

STOPWORDS = {
    "레시피",
    "재료",
    "만드는법",
    "만들기",
    "끓이는법",
    "요리법",
    "황금레시피",
    "양념",
    "방법",
}


def normalize_tag(value: str) -> str:
    return (
        str(value)
        .replace("#", "")
        .replace(" ", "")
        .strip()
    )


def split_tags(raw_tags: str | None) -> list[str]:
    if raw_tags is None:
        return []

    raw = str(raw_tags).strip()
    if not raw or raw.lower() == "nan":
        return []

    tags: list[str] = []

    for value in TAG_SPLIT_PATTERN.split(raw):
        tag = normalize_tag(value)
        if not tag:
            continue
        tags.append(tag)

    return tags


def main() -> None:
    con = sqlite3.connect(DB_PATH)

    df = pd.read_sql(
        """
        SELECT recipe_id
             , title
             , tags
          FROM raw_recipe
         WHERE tags IS NOT NULL
           AND TRIM(tags) <> ''
        """,
        con,
    )

    tag_counter: Counter[str] = Counter()
    recipe_tag_rows: list[dict] = []

    for _, row in df.iterrows():
        tags = split_tags(row["tags"])
        unique_tags = sorted(set(tags))

        for tag in unique_tags:
            tag_counter[tag] += 1

            recipe_tag_rows.append(
                {
                    "recipe_id": row["recipe_id"],
                    "title": row["title"],
                    "tag": tag,
                    "is_stopword": tag in STOPWORDS,
                }
            )

    freq_df = pd.DataFrame(
        [
            {
                "tag": tag,
                "count": count,
                "is_stopword": tag in STOPWORDS,
            }
            for tag, count in tag_counter.most_common()
        ]
    )

    freq_df.to_csv(OUTPUT_DIR / "tag_frequency.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame(recipe_tag_rows).to_csv(
        OUTPUT_DIR / "recipe_tags_long.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"raw recipes with tags: {len(df)}")
    print(f"unique tags: {len(freq_df)}")
    print(f"saved: {OUTPUT_DIR / 'tag_frequency.csv'}")
    print(f"saved: {OUTPUT_DIR / 'recipe_tags_long.csv'}")


if __name__ == "__main__":
    main()