"""
recipes_source.csv → data/recipes.db 빌드 스크립트

실행:
    python recipes/tools/build_recipes.py

산출물:
    data/recipes.db (recipes, recipe_ingredients, meta 테이블)

검증:
    python -c "import sqlite3; con=sqlite3.connect('data/recipes.db'); \
        print('레시피 수:', con.execute('SELECT COUNT(*) FROM recipes').fetchone()[0])"
"""

import csv
import sqlite3
import sys
from datetime import date
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

VERSION = "1.1.0"

# 프로젝트 루트는 본 스크립트의 두 단계 상위 (recipes/tools/ → recipes/ → 프로젝트 루트)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = PROJECT_ROOT / "recipes" / "recipes_source.csv"
DB_PATH = PROJECT_ROOT / "data" / "recipes.db"

# modules 디렉토리를 import path에 추가 (스크립트 직접 실행 대응)
sys.path.insert(0, str(PROJECT_ROOT))

from modules.normalize import (  # noqa: E402
    infer_taste,
    normalize_ingredient,
    split_multi,
    validate_enum,
)


# ─────────────────────────────────────────────
# DB 스키마 생성
# ─────────────────────────────────────────────

SCHEMA_SQL = """
DROP TABLE IF EXISTS recipes;
DROP TABLE IF EXISTS recipe_ingredients;
DROP TABLE IF EXISTS meta;

CREATE TABLE recipes (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    style            TEXT,
    taste            TEXT,
    cook_time        INTEGER,
    difficulty       TEXT,
    suitable_time    TEXT,
    suitable_weather TEXT,
    suitable_month   TEXT,                       -- '1월,9월' 형식 (계절 4 → 월 12 해상도 확장)
    review_keywords  TEXT,                       -- Phase C: 리뷰 키워드 (콤마 구분, 빌드 후 별도 채움)
    instructions     TEXT DEFAULT '',            -- 조리법 (시스템 레시피는 빈 값, 후속 SQL UPDATE 로 외부 링크/텍스트 채움)
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE recipe_ingredients (
    recipe_id  TEXT,
    ingredient TEXT,
    PRIMARY KEY (recipe_id, ingredient)
);

CREATE INDEX idx_ri_ingredient ON recipe_ingredients(ingredient);

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


# 계절 → 월 자동 확장 (CSV 의 suitable_season 입력을 빌드 타임에 풀어냄)
# 명절·제철 키워드가 매칭되면 더 좁은 월로 한정 (infer_months 참조).
SEASON_TO_MONTHS: dict[str, list[int]] = {
    "봄":   [3, 4, 5],
    "여름": [6, 7, 8],
    "가을": [9, 10, 11],
    "겨울": [12, 1, 2],
}

# 레시피명에 키워드가 있으면 해당 월로 강제 한정 (계절 변환 결과 덮어쓰기)
EVENT_MONTH_OVERRIDES: dict[str, list[int]] = {
    "떡국":   [1],
    "송편":   [9],
    "잡채":   [9, 1, 2],     # 명절 음식
    "갈비찜": [1, 2, 9, 10], # 설·추석
    "삼계탕": [7, 8],        # 복날
    "콩국수": [6, 7, 8],
    "냉면":   [6, 7, 8],
    "팥빙수": [6, 7, 8],
}

# 재료 키워드 → 제철 월 한정 (이름 매칭이 없을 때만 적용)
INGREDIENT_MONTH_OVERRIDES: dict[str, list[int]] = {
    "굴":   [11, 12, 1, 2],
    "전어": [9, 10],
}


def infer_months(name: str, ingredients: list[str], seasons: list[str]) -> list[int]:
    """1순위 명절명, 2순위 제철 재료, 3순위 계절 자동 확장."""
    for keyword, months in EVENT_MONTH_OVERRIDES.items():
        if keyword in name:
            return sorted(months)
    for ing, months in INGREDIENT_MONTH_OVERRIDES.items():
        if ing in ingredients:
            return sorted(months)
    return sorted({m for s in seasons for m in SEASON_TO_MONTHS[s]})


def build():
    """recipes.csv → recipes.db 재생성 (스키마 생성 + 전체 적재). 멱등."""
    if not CSV_PATH.exists():
        print(f"[ERROR] CSV not found: {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(SCHEMA_SQL)

    inserted = 0
    skipped = 0
    errors = []

    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=2):  # 헤더 다음부터
            try:
                recipe_id = f"r{row_idx - 1:03d}"  # r001, r002 ...
                name = row["name"].strip()
                style = validate_enum("style", row["style"])
                difficulty = validate_enum("difficulty", row["difficulty"])

                # 재료 목록 먼저 확정 → 맛 자동 추론
                raw_ings = [normalize_ingredient(i) for i in split_multi(row["ingredients"])]
                tastes = infer_taste(raw_ings)
                times = [validate_enum("time", t) for t in split_multi(row["suitable_time"])]
                weathers = [validate_enum("weather", w) for w in split_multi(row["suitable_weather"])]

                # CSV suitable_season → 자동 month 변환 (계절 키 자체는 build 도구가 직접 검증)
                seasons = [s.strip() for s in split_multi(row["suitable_season"])]
                for s in seasons:
                    if s not in SEASON_TO_MONTHS:
                        raise ValueError(f"Invalid season: '{s}'. Allowed: {sorted(SEASON_TO_MONTHS)}")
                months = infer_months(name, raw_ings, seasons)
                month_labels = [f"{m}월" for m in months]

                cur.execute(
                    """INSERT INTO recipes
                       (id, name, style, taste, cook_time, difficulty,
                        suitable_time, suitable_weather, suitable_month)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        recipe_id, name, style,
                        ",".join(tastes),
                        int(row["cook_time"]),
                        difficulty,
                        ",".join(times),
                        ",".join(weathers),
                        ",".join(month_labels),
                    ),
                )

                # 재료 삽입 (이미 정규화된 raw_ings 재사용)
                for ing in raw_ings:
                    cur.execute(
                        "INSERT OR IGNORE INTO recipe_ingredients VALUES (?, ?)",
                        (recipe_id, ing),
                    )

                inserted += 1

            except (ValueError, KeyError) as e:
                skipped += 1
                errors.append(f"  row {row_idx} ({row.get('name', '?')}): {e}")

    # 메타 정보
    cur.execute("INSERT INTO meta VALUES ('version', ?)", (VERSION,))
    cur.execute("INSERT INTO meta VALUES ('updated_at', ?)", (date.today().isoformat(),))
    cur.execute("INSERT INTO meta VALUES ('recipe_count', ?)", (str(inserted),))

    con.commit()
    con.close()

    # 결과 출력
    print(f"[OK] {DB_PATH.relative_to(PROJECT_ROOT)} 생성 완료")
    print(f"     레시피 {inserted}개 삽입, {skipped}개 스킵")
    print(f"     버전: {VERSION}")

    if errors:
        print("\n[경고] 스킵된 행:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)


if __name__ == "__main__":
    build()
