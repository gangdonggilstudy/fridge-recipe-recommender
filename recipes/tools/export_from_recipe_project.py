"""
recipe_project MySQL 원천 데이터 → fridge-recipe-recommender recipes_source.csv 변환 스크립트

실행 위치:
    fridge-recipe-recommender 프로젝트 루트

실행:
    python recipes/tools/export_from_recipe_project.py

이후:
    python recipes/tools/build_recipes.py
"""

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect


# recipes/tools/ → recipes/ → 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "recipes" / "recipes_source.csv"

# 앱 모듈 import 가능하도록 루트 경로 추가
sys.path.insert(0, str(PROJECT_ROOT))

from modules.normalize import normalize_ingredient  # noqa: E402


DIFFICULTY_ALLOWED = {"쉬움", "보통", "어려움"}
SEASON_ALLOWED = {"봄", "여름", "가을", "겨울"}


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_PATH),
        help="생성할 recipes_source.csv 경로"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="내보낼 레시피 수. 0이면 전체"
    )

    parser.add_argument(
        "--min-review-count",
        type=int,
        default=0,
        help="최소 후기수 필터"
    )

    parser.add_argument(
        "--season-version",
        type=str,
        default="season_v1",
        help="recipe_season_score.model_version 필터"
    )

    parser.add_argument(
        "--taste-version",
        type=str,
        default="taste_v1",
        help="recipe_taste_score.model_version 필터. 테이블에 model_version이 없으면 코드에서 자동 무시"
    )

    return parser.parse_args()


def get_engine():
    """
    DB 접속 정보는 .env에서 읽는다.

    우선순위:
      1. RECIPE_PROJECT_DB_URL
      2. DB_URL

    예:
      RECIPE_PROJECT_DB_URL=mysql+pymysql://recipe_user:recipe_pass@localhost:3306/recipe_db?charset=utf8mb4
    """

    load_dotenv(PROJECT_ROOT / ".env")

    db_url = os.getenv("RECIPE_PROJECT_DB_URL") or os.getenv("DB_URL")

    if not db_url:
        raise ValueError(
            ".env에 RECIPE_PROJECT_DB_URL 또는 DB_URL이 없습니다.\n"
            "예: RECIPE_PROJECT_DB_URL=mysql+pymysql://recipe_user:recipe_pass@localhost:3306/recipe_db?charset=utf8mb4"
        )

    return create_engine(db_url)

def table_has_column(engine, table_name: str, column_name: str) -> bool:
    """
    DB 종류와 무관하게 컬럼 존재 여부를 확인한다.
    SQLite / MySQL 모두 대응.
    """

    inspector = inspect(engine)

    if table_name not in inspector.get_table_names():
        return False

    columns = inspector.get_columns(table_name)
    column_names = [column["name"] for column in columns]

    return column_name in column_names
# def table_has_column(engine, table_name: str, column_name: str) -> bool:
#     sql = text("""
#         SELECT COUNT(*) AS cnt
#           FROM INFORMATION_SCHEMA.COLUMNS
#          WHERE TABLE_SCHEMA = DATABASE()
#            AND TABLE_NAME = :table_name
#            AND COLUMN_NAME = :column_name
#     """)

#     with engine.begin() as conn:
#         row = conn.execute(sql, {
#             "table_name": table_name,
#             "column_name": column_name,
#         }).mappings().one()

#     return int(row["cnt"]) > 0

def table_exists(engine, table_name: str) -> bool:
    """
    DB 종류와 무관하게 테이블 존재 여부를 확인한다.
    SQLite / MySQL 모두 대응.
    """

    inspector = inspect(engine)
    return table_name in inspector.get_table_names()
# def table_exists(engine, table_name: str) -> bool:
#     sql = text("""
#         SELECT COUNT(*) AS cnt
#           FROM INFORMATION_SCHEMA.TABLES
#          WHERE TABLE_SCHEMA = DATABASE()
#            AND TABLE_NAME = :table_name
#     """)

#     with engine.begin() as conn:
#         row = conn.execute(sql, {
#             "table_name": table_name,
#         }).mappings().one()

#     return int(row["cnt"]) > 0


def load_recipe_project_data(
        engine,
        limit: int,
        min_review_count: int,
        season_version: str,
        taste_version: str
) -> pd.DataFrame:
    """
    recipe_project의 raw_recipe를 중심으로 계절/맛 점수 테이블을 조인한다.

    taste_score 테이블은 프로젝트 상황에 따라 없거나 model_version 컬럼이 없을 수 있으므로
    존재 여부를 확인해서 안전하게 조인한다.
    """

    has_season_score = table_exists(engine, "recipe_season_score")
    has_taste_score = table_exists(engine, "recipe_taste_score")
    taste_has_model_version = (
        has_taste_score
        and table_has_column(engine, "recipe_taste_score", "model_version")
    )

    season_join = ""
    taste_join = ""

    if has_season_score:
        season_join = """
            LEFT JOIN recipe_season_score S
                   ON S.recipe_id = R.recipe_id
                  AND S.model_version = :season_version
        """

    if has_taste_score and taste_has_model_version:
        taste_join = """
            LEFT JOIN recipe_taste_score T
                   ON T.recipe_id = R.recipe_id
                  AND T.model_version = :taste_version
        """
    elif has_taste_score:
        taste_join = """
            LEFT JOIN recipe_taste_score T
                   ON T.recipe_id = R.recipe_id
        """

    season_columns = """
         , S.main_season
         , S.spring_score
         , S.summer_score
         , S.autumn_score
         , S.winter_score
    """ if has_season_score else """
         , NULL AS main_season
         , NULL AS spring_score
         , NULL AS summer_score
         , NULL AS autumn_score
         , NULL AS winter_score
    """

    taste_columns = """
         , T.main_taste
    """ if has_taste_score else """
         , NULL AS main_taste
    """

    limit_clause = ""
    if limit and limit > 0:
        limit_clause = " LIMIT :limit"

    query = f"""
        SELECT R.recipe_id
             , R.title
             , R.ingredients
             , R.cook_time
             , R.difficulty
             , R.category_type
             , R.category_types
             , R.ingredient_types
             , R.method_types
             , R.avg_rating
             , R.review_count
             , R.scrap_count
             , R.source_url
             {season_columns}
             {taste_columns}
          FROM raw_recipe R
          {season_join}
          {taste_join}
         WHERE R.title IS NOT NULL
           AND TRIM(R.title) <> ''
           AND R.ingredients IS NOT NULL
           AND TRIM(R.ingredients) <> ''
           AND (
                :min_review_count = 0
             OR IFNULL(R.review_count, 0) >= :min_review_count
           )
         ORDER BY IFNULL(R.review_count, 0) DESC
                , R.recipe_id
         {limit_clause}
    """

    params = {
        "season_version": season_version,
        "taste_version": taste_version,
        "min_review_count": min_review_count,
    }

    if limit and limit > 0:
        params["limit"] = limit

    return pd.read_sql(text(query), engine, params=params)


def normalize_text(value) -> str:
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip()


def clean_ingredient_name(value: str) -> str:
    """
    재료명만 정리한다.
    raw_recipe.ingredients의 수량은 split_ingredients에서 먼저 제거한다.
    """

    value = normalize_text(value)

    if not value:
        return ""

    # 괄호 내용 제거
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"\[[^\]]*\]", "", value)

    # 앞에 붙은 계량 문자 제거
    # 예: T고추가루, t소금 같은 경우
    value = re.sub(r"^[Tt]+", "", value)

    # 불필요 표현 제거
    value = re.sub(r"(약간|적당량|취향껏|구매)", "", value)

    # ':' 뒤 설명 제거
    value = re.sub(r"[:：].*$", "", value)

    # 특수문자 제거
    value = re.sub(r"[^가-힣a-zA-Z]", "", value)

    alias_map = {
        "고추가루": "고춧가루",
        "다진마늘": "마늘",
        "다진파": "대파",
        "진간장": "간장",
        "국간장": "간장",
        "양조간장": "간장",
        "맛간장": "간장",
        "조선간장": "간장",
        "집된장": "된장",
        "재래된장": "된장",
        "시판된장": "된장",
        "초고추장": "고추장",
        "비엔나소세지": "소세지",
        "비엔나": "소세지",
    }

    value = alias_map.get(value, value)

    # 계량 단위만 남은 경우 제거
    if value in MEASURE_ONLY_TOKENS:
        return ""

    # 영어만 남은 경우 제거
    if re.fullmatch(r"[a-zA-Z]+", value):
        return ""

    value = normalize_ingredient(value)

    if not is_valid_ingredient_name(value):
        return ""

    return value

EXCLUDE_INGREDIENT_KEYWORDS = [
    "냄비", "팬", "후라이팬", "프라이팬", "볼", "그릇", "접시", "도마", "칼",
    "주방칼", "가위", "젓가락", "요리젓가락", "숟가락", "스푼", "국자",
    "채반", "믹서", "오븐", "전자레인지", "락앤락", "유리락앤락",
    "부르스타", "비닐", "위생팩", "종이컵", "랩",
    "요리", "재료", "양념", "소스", "준비", "용기"
]

MEASURE_ONLY_TOKENS = {
    "T", "t", "Ts", "ts", "TS",
    "tsp", "Tsp", "tbsp", "Tbsp", "TBSP",
    "ml", "ML", "g", "G", "kg", "KG", "L", "l",

    # 한글 수량/단위
    "개", "장", "모", "쪽", "톨", "알", "봉", "팩", "캔",
    "마리", "조각", "줌", "줄", "대", "컵",
    "큰술", "작은술", "스푼", "숟가락",
    "약간", "적당량", "취향껏"
}


def is_valid_ingredient_name(name: str) -> bool:
    if not name:
        return False

    name = name.strip()

    # 단위만 남은 값 제거
    if name in MEASURE_ONLY_TOKENS:
        return False

    # 숫자 포함 값 제거
    if re.search(r"\d", name):
        return False

    # 영어만 남은 값 제거
    if re.fullmatch(r"[a-zA-Z]+", name):
        return False

    # 너무 긴 값은 재료명이 아니라 설명문일 가능성이 큼
    if len(name) > 12:
        return False

    for keyword in EXCLUDE_INGREDIENT_KEYWORDS:
        if keyword in name:
            return False

    return True

def split_ingredients(raw_value) -> list[str]:
    """
    raw_recipe.ingredients 형식:
        재료명,수량/재료명,수량/재료명,수량

    예:
        두부,1모/대파,1/2개/간장,2큰술

    처리 방식:
        1. "/" 기준으로 재료 항목 분리
        2. 각 항목에서 "," 앞부분만 재료명으로 사용
        3. 수량은 버림
    """

    raw = normalize_text(raw_value)

    if not raw:
        return []

    items = []

    # JSON 배열 형태 대응
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            items = [str(v) for v in parsed]
    except Exception:
        items = []

    # recipe_project 원본 형식은 "/" 기준
    if not items:
        if "/" in raw:
            items = raw.split("/")
        else:
            # fallback: 이미 앱용 CSV처럼 콤마로만 된 경우
            items = re.split(r"[,|\n;]+", raw)

    cleaned = []

    for item in items:
        item = normalize_text(item)

        if not item:
            continue

        # 핵심: "재료명,수량"에서 재료명만 사용
        # 예: "간장,2큰술" -> "간장"
        if "," in item:
            ingredient_name = item.split(",", 1)[0]
        else:
            ingredient_name = item

        name = clean_ingredient_name(ingredient_name)

        if not name:
            continue
        
        if not is_valid_ingredient_name(name):
            continue

        cleaned.append(name)

    # 순서 유지 중복 제거
    result = []
    seen = set()

    for item in cleaned:
        if item not in seen:
            result.append(item)
            seen.add(item)

    return result

ALLOWED_RECIPE_TYPES = {
    "메인반찬",
    "찌개",
    "국/탕",
    "밥/죽/떡",
    "면/만두",
    "양식",
}

def safe_text(value) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()

def map_style(category_type, category_types, title=None) -> str:
    candidates: list[str] = []

    category_type_text = safe_text(category_type)
    category_types_text = safe_text(category_types)

    if category_type_text:
        candidates.append(category_type_text)

    if category_types_text:
        candidates.extend([
            v.strip()
            for v in category_types_text.split(",")
            if v.strip()
        ])

    for value in candidates:
        if value in ALLOWED_RECIPE_TYPES:
            return value

    # 계절요리처럼 category_type/category_types가 없는 데이터는 비워둔다.
    return ""
    
# def map_style(category_type: str, category_types: str, title: str) -> str:
#     """
#     앱 recipes_source.csv의 style은 한식/양식/중식/일식만 허용된다.
#     recipe_project의 category_type은 메인반찬, 찌개, 국/탕 같은 메뉴 종류라서 그대로 넣으면 build_recipes.py 검증에서 실패한다.
#     """

#     text_value = ",".join([
#         normalize_text(category_type),
#         normalize_text(category_types),
#         normalize_text(title),
#     ])

#     if "양식" in text_value or "파스타" in text_value or "스테이크" in text_value:
#         return "양식"

#     if "중식" in text_value or "짜장" in text_value or "짬뽕" in text_value or "마라" in text_value:
#         return "중식"

#     if "일식" in text_value or "우동" in text_value or "초밥" in text_value or "돈까스" in text_value:
#         return "일식"

#     return "한식"


def map_difficulty(value: str) -> str:
    """
    recipe_project 난이도 → 앱 난이도 enum으로 변환
    앱 허용값: 쉬움, 보통, 어려움
    """

    value = normalize_text(value)

    if value in DIFFICULTY_ALLOWED:
        return value

    if value in {"아무나", "초급", "쉬운"}:
        return "쉬움"

    if value in {"중급", "보통"}:
        return "보통"

    if value in {"고급", "신의경지", "어려운"}:
        return "어려움"

    return "보통"


def map_season(value: str) -> str:
    """
    recipe_season_score.main_season → suitable_season
    없으면 기본값으로 사계절 모두 넣는다.
    build_recipes.py에서 계절을 월로 확장한다.
    """

    value = normalize_text(value)

    if value in SEASON_ALLOWED:
        return value

    if value == "미분류" or not value:
        return "봄,여름,가을,겨울"

    return "봄,여름,가을,겨울"


def map_cook_time(value) -> int:
    try:
        if pd.isna(value):
            return 30

        cook_time = int(float(str(value).replace(",", "").strip()))

        if cook_time <= 0:
            return 30

        # 너무 큰 값은 파싱 오류 가능성이 있으므로 상한 처리
        if cook_time > 240:
            return 240

        return cook_time

    except Exception:
        return 30


def map_suitable_time(cook_time: int) -> str:
    """
    조리시간을 기준으로 추천 시간대를 단순 부여한다.
    앱 허용값: 아침, 점심, 저녁, 야식
    """

    if cook_time <= 15:
        return "아침,점심,야식"

    if cook_time <= 40:
        return "점심,저녁"

    return "저녁"


def map_suitable_weather(season: str, category_types: str, title: str) -> str:
    """
    날씨 적합도는 상세 데이터가 없으므로 휴리스틱으로 부여한다.
    앱 허용값: 맑음, 비, 눈, 더위, 추위
    """

    text_value = ",".join([
        normalize_text(season),
        normalize_text(category_types),
        normalize_text(title),
    ])

    values = {"맑음"}

    if "여름" in text_value or "냉" in text_value or "콩국수" in text_value:
        values.add("더위")

    if "겨울" in text_value or "국/탕" in text_value or "찌개" in text_value or "전골" in text_value:
        values.add("추위")
        values.add("비")
        values.add("눈")

    order = ["맑음", "비", "눈", "더위", "추위"]
    return ",".join([v for v in order if v in values])


def make_recipe_row(row) -> dict | None:
    ingredients = split_ingredients(row.get("ingredients"))

    # 재료가 너무 적으면 추천 품질이 떨어지므로 제외
    if len(ingredients) < 2:
        return None

    title = normalize_text(row.get("title"))

    if not title:
        return None

    cook_time = map_cook_time(row.get("cook_time"))
    season = map_season(row.get("main_season"))
    style = map_style(
        category_type=row.get("category_type"),
        category_types=row.get("category_types"),
        title=title
    )
    difficulty = map_difficulty(row.get("difficulty"))
    suitable_time = map_suitable_time(cook_time)
    suitable_weather = map_suitable_weather(
        season=season,
        category_types=row.get("category_types"),
        title=title
    )

    return {
        # build_recipes.py가 실제로 사용하는 컬럼
        "name": title,
        "style": style,
        "ingredients": ",".join(ingredients),
        "cook_time": cook_time,
        "difficulty": difficulty,
        "suitable_time": suitable_time,
        "suitable_weather": suitable_weather,
        "suitable_season": season,

        # 아래는 보존용 메타 컬럼.
        # 현재 build_recipes.py는 사용하지 않지만 CSV에 있어도 문제 없음.
        "source_recipe_id": normalize_text(row.get("recipe_id")),
        "source_url": normalize_text(row.get("source_url")),
        "source_category": normalize_text(row.get("category_types") or row.get("category_type")),
        "source_main_taste": normalize_text(row.get("main_taste")),
        "source_main_season": normalize_text(row.get("main_season")),
        "source_review_count": normalize_text(row.get("review_count")),
        "source_avg_rating": normalize_text(row.get("avg_rating")),
        "source_scrap_count": normalize_text(row.get("scrap_count")),
    }


def export_csv(df: pd.DataFrame, output_path: Path) -> tuple[int, int]:
    fieldnames = [
        "name",
        "style",
        "ingredients",
        "cook_time",
        "difficulty",
        "suitable_time",
        "suitable_weather",
        "suitable_season",
        "source_recipe_id",
        "source_url",
        "source_category",
        "source_main_taste",
        "source_main_season",
        "source_review_count",
        "source_avg_rating",
        "source_scrap_count",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    inserted = 0
    skipped = 0
    seen_names = set()

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for _, row in df.iterrows():
            recipe_row = make_recipe_row(row)

            if recipe_row is None:
                skipped += 1
                continue

            # 같은 제목 중복 방지
            name = recipe_row["name"]

            if name in seen_names:
                skipped += 1
                continue

            seen_names.add(name)
            writer.writerow(recipe_row)
            inserted += 1

    return inserted, skipped


def main():
    args = parse_args()

    engine = get_engine()

    print("[1] recipe_project 데이터 조회 시작")

    df = load_recipe_project_data(
        engine=engine,
        limit=args.limit,
        min_review_count=args.min_review_count,
        season_version=args.season_version,
        taste_version=args.taste_version,
    )

    print(f"[2] 조회 완료: {len(df)} rows")

    output_path = Path(args.output)

    print(f"[3] CSV 생성 시작: {output_path}")

    inserted, skipped = export_csv(df, output_path)

    print("[OK] recipes_source.csv 생성 완료")
    print(f" - output : {output_path}")
    print(f" - inserted: {inserted}")
    print(f" - skipped : {skipped}")
    print()
    print("다음 명령어를 실행하세요:")
    print("python recipes/tools/build_recipes.py")


if __name__ == "__main__":
    main()