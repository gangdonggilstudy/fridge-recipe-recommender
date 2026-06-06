from __future__ import annotations

from typing import Any

from sqlalchemy import text

from db.connection import engine


COLLECT_COLUMN_MAP = {
    "category": "category_types",
    "ingredient": "ingredient_types",
    "method": "method_types",
    "situation": "situation_types",
}


def _append_unique(current_value: str | None, new_value: str | None) -> str | None:
    if not new_value:
        return current_value

    values: list[str] = []

    if current_value:
        values = [
            value.strip()
            for value in str(current_value).split(",")
            if value.strip()
        ]

    if new_value not in values:
        values.append(new_value)

    return ",".join(values)


def _csv_contains_expr(column_name: str) -> str:
    return f"((',' || IFNULL({column_name}, '') || ',') LIKE :collect_pattern)"


def _get_collect_column(collect_kind: str) -> str:
    column_name = COLLECT_COLUMN_MAP.get(collect_kind)

    if not column_name:
        raise ValueError(f"Unknown collect_kind: {collect_kind}")

    return column_name


def _normalize_raw_recipe_params(recipe: dict[str, Any]) -> dict[str, Any]:
    params = dict(recipe)

    params.setdefault("recipe_id", "")
    params.setdefault("title", "")
    params.setdefault("category_type", "")
    params.setdefault("category_types", "")
    params.setdefault("ingredient_types", "")
    params.setdefault("method_types", "")
    params.setdefault("situation_types", "")
    params.setdefault("summary", "")
    params.setdefault("ingredients", "")
    params.setdefault("steps", "")
    params.setdefault("tags", "")
    params.setdefault("cook_time", None)
    params.setdefault("difficulty", "")
    params.setdefault("avg_rating", None)
    params.setdefault("view_count", 0)
    params.setdefault("scrap_count", 0)
    params.setdefault("review_count", 0)
    params.setdefault("source_url", "")

    return params


def exists_raw_recipe(recipe_id: str) -> bool:
    sql = text("""
        SELECT COUNT(*) AS cnt
          FROM raw_recipe
         WHERE recipe_id = :recipe_id
    """)

    with engine.begin() as conn:
        row = conn.execute(sql, {"recipe_id": recipe_id}).mappings().one()

    return int(row["cnt"]) > 0


def upsert_raw_recipe(recipe: dict[str, Any]) -> None:
    sql = text("""
        INSERT INTO raw_recipe (
              recipe_id
            , title
            , category_type
            , category_types
            , ingredient_types
            , method_types
            , situation_types
            , summary
            , ingredients
            , steps
            , tags
            , cook_time
            , difficulty
            , avg_rating
            , view_count
            , scrap_count
            , review_count
            , source_url
        )
        VALUES (
              :recipe_id
            , :title
            , :category_type
            , :category_types
            , :ingredient_types
            , :method_types
            , :situation_types
            , :summary
            , :ingredients
            , :steps
            , :tags
            , :cook_time
            , :difficulty
            , :avg_rating
            , :view_count
            , :scrap_count
            , :review_count
            , :source_url
        )
        ON CONFLICT(recipe_id) DO UPDATE SET
              title            = COALESCE(NULLIF(excluded.title, ''), raw_recipe.title)
            , category_type    = COALESCE(NULLIF(excluded.category_type, ''), raw_recipe.category_type)
            , category_types   = COALESCE(NULLIF(excluded.category_types, ''), raw_recipe.category_types)
            , ingredient_types = COALESCE(NULLIF(excluded.ingredient_types, ''), raw_recipe.ingredient_types)
            , method_types     = COALESCE(NULLIF(excluded.method_types, ''), raw_recipe.method_types)
            , situation_types  = COALESCE(NULLIF(excluded.situation_types, ''), raw_recipe.situation_types)
            , summary          = COALESCE(NULLIF(excluded.summary, ''), raw_recipe.summary)
            , ingredients      = COALESCE(NULLIF(excluded.ingredients, ''), raw_recipe.ingredients)
            , steps            = COALESCE(NULLIF(excluded.steps, ''), raw_recipe.steps)
            , tags             = COALESCE(NULLIF(excluded.tags, ''), raw_recipe.tags)
            , cook_time        = COALESCE(excluded.cook_time, raw_recipe.cook_time)
            , difficulty       = COALESCE(NULLIF(excluded.difficulty, ''), raw_recipe.difficulty)
            , avg_rating       = COALESCE(excluded.avg_rating, raw_recipe.avg_rating)
            , view_count       = COALESCE(excluded.view_count, raw_recipe.view_count)
            , scrap_count      = COALESCE(excluded.scrap_count, raw_recipe.scrap_count)
            , review_count     = COALESCE(excluded.review_count, raw_recipe.review_count)
            , source_url       = COALESCE(NULLIF(excluded.source_url, ''), raw_recipe.source_url)
            , crawled_at       = CURRENT_TIMESTAMP
    """)

    params = _normalize_raw_recipe_params(recipe)

    with engine.begin() as conn:
        conn.execute(sql, params)


def count_raw_recipes_by_category(category_name: str) -> int:
    return count_raw_recipes_by_collect_type("category", category_name)


def count_raw_recipes_by_collect_type(
        collect_kind: str,
        collect_value: str
) -> int:
    column_name = _get_collect_column(collect_kind)
    where_expr = _csv_contains_expr(column_name)

    if collect_kind == "category":
        sql = text(f"""
            SELECT COUNT(*) AS recipe_count
              FROM raw_recipe
             WHERE {where_expr}
                OR category_type = :collect_value
        """)
    else:
        sql = text(f"""
            SELECT COUNT(*) AS recipe_count
              FROM raw_recipe
             WHERE {where_expr}
        """)

    with engine.begin() as conn:
        row = conn.execute(sql, {
            "collect_value": collect_value,
            "collect_pattern": f"%,{collect_value},%",
        }).mappings().one()

    return int(row["recipe_count"])


def has_raw_recipe_collect_type(
        recipe_id: str,
        collect_kind: str,
        collect_value: str
) -> bool:
    column_name = _get_collect_column(collect_kind)
    where_expr = _csv_contains_expr(column_name)

    if collect_kind == "category":
        sql = text(f"""
            SELECT COUNT(*) AS recipe_count
              FROM raw_recipe
             WHERE recipe_id = :recipe_id
               AND (
                    {where_expr}
                 OR category_type = :collect_value
               )
        """)
    else:
        sql = text(f"""
            SELECT COUNT(*) AS recipe_count
              FROM raw_recipe
             WHERE recipe_id = :recipe_id
               AND {where_expr}
        """)

    with engine.begin() as conn:
        row = conn.execute(sql, {
            "recipe_id": recipe_id,
            "collect_value": collect_value,
            "collect_pattern": f"%,{collect_value},%",
        }).mappings().one()

    return int(row["recipe_count"]) > 0


def append_raw_recipe_collect_type(
        recipe_id: str,
        category_type: str | None = None,
        ingredient_type: str | None = None,
        method_type: str | None = None,
        situation_type: str | None = None
) -> None:
    select_sql = text("""
        SELECT category_type
             , category_types
             , ingredient_types
             , method_types
             , situation_types
          FROM raw_recipe
         WHERE recipe_id = :recipe_id
    """)

    update_sql = text("""
        UPDATE raw_recipe
           SET category_type    = COALESCE(NULLIF(:category_type, ''), category_type)
             , category_types   = :category_types
             , ingredient_types = :ingredient_types
             , method_types     = :method_types
             , situation_types  = :situation_types
             , crawled_at       = CURRENT_TIMESTAMP
         WHERE recipe_id = :recipe_id
    """)

    with engine.begin() as conn:
        row = conn.execute(select_sql, {
            "recipe_id": recipe_id,
        }).mappings().one_or_none()

        if not row:
            return

        conn.execute(update_sql, {
            "recipe_id": recipe_id,
            "category_type": category_type or row["category_type"] or "",
            "category_types": _append_unique(row["category_types"], category_type),
            "ingredient_types": _append_unique(row["ingredient_types"], ingredient_type),
            "method_types": _append_unique(row["method_types"], method_type),
            "situation_types": _append_unique(row["situation_types"], situation_type),
        })


def insert_raw_ingredient(ingredient_name: str) -> None:
    sql = text("""
        INSERT OR IGNORE INTO raw_ingredients (
              ingredient_name
        )
        VALUES (
              :ingredient_name
        )
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "ingredient_name": ingredient_name,
        })


def insert_raw_recipe_review(review: dict[str, Any]) -> None:
    sql = text("""
        INSERT INTO raw_recipe_review (
              recipe_id
            , rating
            , content
            , review_date
        )
        VALUES (
              :recipe_id
            , :rating
            , :content
            , :review_date
        )
    """)

    params = dict(review)
    params.setdefault("rating", None)
    params.setdefault("content", "")
    params.setdefault("review_date", "")

    with engine.begin() as conn:
        conn.execute(sql, params)

def upsert_raw_recipe_review(row: dict) -> None:
    sql = text("""
        INSERT INTO raw_recipe_review (
              recipe_id
            , review_seq
            , review_date
            , nickname
            , review_content
            , rating
        )
        VALUES (
              :recipe_id
            , :review_seq
            , :review_date
            , :nickname
            , :review_content
            , :rating
        )
        ON CONFLICT(recipe_id, review_seq) DO UPDATE SET
              review_date    = excluded.review_date
            , nickname       = excluded.nickname
            , review_content = excluded.review_content
            , rating         = excluded.rating
            , crawled_at     = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, row)

def delete_raw_recipe_reviews(recipe_id: str) -> None:
    sql = text("""
        DELETE FROM raw_recipe_review
         WHERE recipe_id = :recipe_id
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "recipe_id": recipe_id,
        })


def count_raw_recipe_reviews(recipe_id: str) -> int:
    sql = text("""
        SELECT COUNT(*) AS cnt
          FROM raw_recipe_review
         WHERE recipe_id = :recipe_id
    """)

    with engine.begin() as conn:
        row = conn.execute(sql, {
            "recipe_id": recipe_id,
        }).mappings().one()

    return int(row["cnt"])


def upsert_recipe_taste_score(score: dict | None = None, **kwargs) -> None:
    """
    레시피 맛 점수 저장.

    호출 방식 둘 다 지원:
    1) upsert_recipe_taste_score(score_dict)
    2) upsert_recipe_taste_score(recipe_id=..., taste_spicy_score=..., ...)
    """

    params = {}

    if score:
        params.update(score)

    params.update(kwargs)

    if not params.get("recipe_id"):
        return

    params.setdefault("taste_spicy_score", 0)
    params.setdefault("taste_savory_score", 0)
    params.setdefault("taste_sweet_score", 0)
    params.setdefault("taste_sour_score", 0)
    params.setdefault("taste_salty_score", 0)
    params.setdefault("taste_light_score", 0)
    params.setdefault("main_taste", "")
    params.setdefault("matched_keywords", "")
    params.setdefault("model_version", "taste_v1")

    if isinstance(params["matched_keywords"], list):
        params["matched_keywords"] = ",".join(params["matched_keywords"])

    sql = text("""
        INSERT INTO recipe_taste_score (
              recipe_id
            , taste_spicy_score
            , taste_savory_score
            , taste_sweet_score
            , taste_sour_score
            , taste_salty_score
            , taste_light_score
            , main_taste
            , matched_keywords
            , model_version
        )
        VALUES (
              :recipe_id
            , :taste_spicy_score
            , :taste_savory_score
            , :taste_sweet_score
            , :taste_sour_score
            , :taste_salty_score
            , :taste_light_score
            , :main_taste
            , :matched_keywords
            , :model_version
        )
        ON CONFLICT(recipe_id) DO UPDATE SET
              taste_spicy_score  = excluded.taste_spicy_score
            , taste_savory_score = excluded.taste_savory_score
            , taste_sweet_score  = excluded.taste_sweet_score
            , taste_sour_score   = excluded.taste_sour_score
            , taste_salty_score  = excluded.taste_salty_score
            , taste_light_score  = excluded.taste_light_score
            , main_taste         = excluded.main_taste
            , matched_keywords   = excluded.matched_keywords
            , model_version      = excluded.model_version
            , created_at         = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, params)

def upsert_recipe_season_score(score: dict[str, Any]) -> None:
    sql = text("""
        INSERT INTO recipe_season_score (
              recipe_id
            , spring_score
            , summer_score
            , autumn_score
            , winter_score
            , main_season
            , matched_ingredients
            , model_version
        )
        VALUES (
              :recipe_id
            , :spring_score
            , :summer_score
            , :autumn_score
            , :winter_score
            , :main_season
            , :matched_ingredients
            , :model_version
        )
        ON CONFLICT(recipe_id) DO UPDATE SET
              spring_score        = excluded.spring_score
            , summer_score        = excluded.summer_score
            , autumn_score        = excluded.autumn_score
            , winter_score        = excluded.winter_score
            , main_season         = excluded.main_season
            , matched_ingredients = excluded.matched_ingredients
            , model_version       = excluded.model_version
            , created_at          = CURRENT_TIMESTAMP
    """)

    params = dict(score)
    params.setdefault("spring_score", 0)
    params.setdefault("summer_score", 0)
    params.setdefault("autumn_score", 0)
    params.setdefault("winter_score", 0)
    params.setdefault("main_season", "")
    params.setdefault("matched_ingredients", "")
    params.setdefault("model_version", "season_v1")

    with engine.begin() as conn:
        conn.execute(sql, params)


def select_raw_recipe_all() -> list[dict[str, Any]]:
    sql = text("""
        SELECT *
          FROM raw_recipe
         ORDER BY recipe_id
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]


def select_raw_recipe_for_analysis() -> list[dict[str, Any]]:
    sql = text("""
        SELECT recipe_id
             , title
             , ingredients
             , category_type
             , category_types
             , ingredient_types
             , method_types
             , situation_types
             , cook_time
             , difficulty
             , avg_rating
             , review_count
             , scrap_count
             , view_count
             , source_url
          FROM raw_recipe
         ORDER BY recipe_id
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]

def find_recipe_ids_for_review_crawling(
        limit: int = 100,
        only_not_crawled: bool = True,
        **kwargs
) -> list[str]:
    """
    리뷰 크롤링 대상 recipe_id 조회.

    - review_count가 1 이상인 레시피 대상
    - only_not_crawled=True이면 raw_recipe_review에 아직 리뷰가 없는 레시피만 조회
    """

    if "max_count" in kwargs:
        limit = kwargs["max_count"]

    if "only_missing" in kwargs:
        only_not_crawled = kwargs["only_missing"]

    not_crawled_condition = ""

    if only_not_crawled:
        not_crawled_condition = """
           AND NOT EXISTS (
                SELECT 1
                  FROM raw_recipe_review RR
                 WHERE RR.recipe_id = R.recipe_id
           )
        """

    sql = text(f"""
        SELECT R.recipe_id
          FROM raw_recipe R
         WHERE IFNULL(R.review_count, 0) > 0
           {not_crawled_condition}
         ORDER BY IFNULL(R.review_count, 0) DESC
                , R.recipe_id
         LIMIT :limit
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql, {
            "limit": int(limit),
        }).mappings().all()

    return [str(row["recipe_id"]) for row in rows]

def find_raw_recipes_for_ingredient_extract(
        limit: int | None = None
) -> list[dict]:
    """
    재료 추출 대상 레시피 조회.

    raw_recipe.ingredients가 있는 레시피를 조회해서
    ingredient_parser에서 재료명을 추출할 수 있게 넘긴다.
    """

    limit_clause = ""

    if limit is not None and limit > 0:
        limit_clause = " LIMIT :limit"

    sql = text(f"""
        SELECT recipe_id
             , title
             , ingredients
          FROM raw_recipe
         WHERE ingredients IS NOT NULL
           AND TRIM(ingredients) <> ''
         ORDER BY recipe_id
         {limit_clause}
    """)

    params = {}

    if limit is not None and limit > 0:
        params["limit"] = int(limit)

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return [dict(row) for row in rows]

def upsert_raw_ingredient(ingredient_name: str) -> None:
    """
    정제된 재료명을 raw_ingredients 테이블에 중복 없이 저장한다.
    SQLite에서는 ingredient_name UNIQUE 기준으로 중복을 무시한다.
    """

    if not ingredient_name:
        return

    ingredient_name = str(ingredient_name).strip()

    if not ingredient_name:
        return

    sql = text("""
        INSERT INTO raw_ingredients (
              ingredient_name
        )
        VALUES (
              :ingredient_name
        )
        ON CONFLICT(ingredient_name) DO UPDATE SET
              ingredient_name = excluded.ingredient_name
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "ingredient_name": ingredient_name,
        })


def insert_raw_ingredient(ingredient_name: str) -> None:
    """
    기존 코드 호환용 alias.
    """
    upsert_raw_ingredient(ingredient_name)

def upsert_raw_recipe_ingredient(
        recipe_id: str,
        ingredient_name: str,
        raw_text: str | None = None,
        is_main: bool | int = False,
        **kwargs
) -> None:
    """
    레시피와 재료의 매핑 정보를 저장한다.

    recipe_id + ingredient_name 기준으로 중복 저장을 막고,
    raw_text에는 원본 재료 문자열을 보관한다.
    """

    if not recipe_id or not ingredient_name:
        return

    recipe_id = str(recipe_id).strip()
    ingredient_name = str(ingredient_name).strip()
    raw_text = "" if raw_text is None else str(raw_text).strip()

    if not recipe_id or not ingredient_name:
        return

    sql = text("""
        INSERT INTO raw_recipe_ingredients (
              recipe_id
            , ingredient_name
            , raw_text
            , is_main
        )
        VALUES (
              :recipe_id
            , :ingredient_name
            , :raw_text
            , :is_main
        )
        ON CONFLICT(recipe_id, ingredient_name) DO UPDATE SET
              raw_text   = COALESCE(NULLIF(excluded.raw_text, ''), raw_recipe_ingredients.raw_text)
            , is_main    = CASE
                               WHEN excluded.is_main = 1 THEN 1
                               ELSE raw_recipe_ingredients.is_main
                           END
            , created_at = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "recipe_id": recipe_id,
            "ingredient_name": ingredient_name,
            "raw_text": raw_text,
            "is_main": 1 if is_main else 0,
        })


def insert_raw_recipe_ingredient(
        recipe_id: str,
        ingredient_name: str,
        raw_text: str | None = None,
        is_main: bool | int = False,
        **kwargs
) -> None:
    upsert_raw_recipe_ingredient(
        recipe_id=recipe_id,
        ingredient_name=ingredient_name,
        raw_text=raw_text,
        is_main=is_main,
        **kwargs
    )

def find_recipes_for_main_ingredient_marking(
        limit: int | None = None,
        only_unmarked: bool = False,
        **kwargs
) -> list[dict]:
    """
    메인 재료 표시 대상 조회.

    run_mark_main_ingredients.py는 row["ingredient_name"]을 사용하므로,
    레시피별로 GROUP_CONCAT 하지 않고 재료 1개당 1 row로 반환한다.
    """

    if "max_count" in kwargs:
        limit = kwargs["max_count"]

    if "only_missing" in kwargs:
        only_unmarked = kwargs["only_missing"]

    limit_clause = ""

    if limit is not None and int(limit) > 0:
        limit_clause = " LIMIT :limit"

    only_unmarked_condition = ""

    if only_unmarked:
        only_unmarked_condition = """
           AND NOT EXISTS (
                SELECT 1
                  FROM raw_recipe_ingredients MRI
                 WHERE MRI.recipe_id = R.recipe_id
                   AND IFNULL(MRI.is_main, 0) = 1
           )
        """

    sql = text(f"""
        SELECT R.recipe_id
             , R.title
             , RI.ingredient_name
             , RI.raw_text
             , IFNULL(RI.is_main, 0) AS is_main
          FROM raw_recipe R
         INNER JOIN raw_recipe_ingredients RI
            ON RI.recipe_id = R.recipe_id
         WHERE R.recipe_id IS NOT NULL
           AND R.title IS NOT NULL
           AND TRIM(R.title) <> ''
           AND RI.ingredient_name IS NOT NULL
           AND TRIM(RI.ingredient_name) <> ''
           {only_unmarked_condition}
         ORDER BY R.recipe_id
                , RI.ingredient_name
         {limit_clause}
    """)

    params = {}

    if limit is not None and int(limit) > 0:
        params["limit"] = int(limit)

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return [dict(row) for row in rows]

def update_raw_recipe_ingredient_is_main(
        recipe_id: str,
        ingredient_name: str,
        is_main: bool | int = True
) -> None:
    sql = text("""
        UPDATE raw_recipe_ingredients
           SET is_main = :is_main
         WHERE recipe_id = :recipe_id
           AND ingredient_name = :ingredient_name
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "recipe_id": recipe_id,
            "ingredient_name": ingredient_name,
            "is_main": 1 if is_main else 0,
        })

def reset_main_ingredient_flags(
        recipe_id: str | None = None,
        **kwargs
) -> None:
    """
    메인 재료 표시 초기화.

    recipe_id가 있으면 해당 레시피만 초기화하고,
    recipe_id가 없으면 전체 레시피의 is_main 값을 초기화한다.
    """

    if "target_recipe_id" in kwargs:
        recipe_id = kwargs["target_recipe_id"]

    if recipe_id:
        sql = text("""
            UPDATE raw_recipe_ingredients
               SET is_main = 0
             WHERE recipe_id = :recipe_id
        """)

        params = {
            "recipe_id": str(recipe_id).strip()
        }
    else:
        sql = text("""
            UPDATE raw_recipe_ingredients
               SET is_main = 0
        """)

        params = {}

    with engine.begin() as conn:
        conn.execute(sql, params)

def update_main_ingredient_flag(
        recipe_id: str,
        ingredient_name: str,
        is_main: bool | int | str = True,
        **kwargs
) -> None:
    """
    특정 레시피의 특정 재료를 메인 재료로 표시하거나 해제한다.
    """

    if not recipe_id or not ingredient_name:
        return

    recipe_id = str(recipe_id).strip()
    ingredient_name = str(ingredient_name).strip()

    if not recipe_id or not ingredient_name:
        return

    if isinstance(is_main, str):
        is_main_value = 1 if is_main.upper() in ("Y", "1", "TRUE") else 0
    else:
        is_main_value = 1 if is_main in (True, 1) else 0

    sql = text("""
        UPDATE raw_recipe_ingredients
           SET is_main = :is_main
         WHERE recipe_id = :recipe_id
           AND ingredient_name = :ingredient_name
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "recipe_id": recipe_id,
            "ingredient_name": ingredient_name,
            "is_main": is_main_value,
        })

def update_raw_recipe_ingredient_is_main(
        recipe_id: str,
        ingredient_name: str,
        is_main: bool | int = True,
        **kwargs
) -> None:
    """
    기존 코드 호환용 alias.
    """
    update_main_ingredient_flag(
        recipe_id=recipe_id,
        ingredient_name=ingredient_name,
        is_main=is_main,
        **kwargs
    )

def find_recipe_ingredients_for_taste_score(
        limit: int | None = None,
        only_main: bool = False,
        **kwargs
) -> list[dict]:
    """
    맛 점수 계산 대상 재료 조회.

    recipe_taste_score 계산을 위해 레시피별 추출 재료를 조회한다.
    기본은 전체 재료를 사용하고, only_main=True이면 메인 재료만 조회한다.
    """

    if "max_count" in kwargs:
        limit = kwargs["max_count"]

    if "main_only" in kwargs:
        only_main = kwargs["main_only"]

    limit_clause = ""

    if limit is not None and int(limit) > 0:
        limit_clause = " LIMIT :limit"

    main_condition = ""

    if only_main:
        main_condition = """
           AND IFNULL(RI.is_main, 0) = 1
        """

    sql = text(f"""
        SELECT R.recipe_id
             , R.title
             , RI.ingredient_name
             , RI.raw_text
             , IFNULL(RI.is_main, 0) AS is_main
          FROM raw_recipe R
         INNER JOIN raw_recipe_ingredients RI
            ON RI.recipe_id = R.recipe_id
         WHERE R.recipe_id IS NOT NULL
           AND RI.ingredient_name IS NOT NULL
           AND TRIM(RI.ingredient_name) <> ''
           {main_condition}
         ORDER BY R.recipe_id
                , RI.ingredient_name
         {limit_clause}
    """)

    params = {}

    if limit is not None and int(limit) > 0:
        params["limit"] = int(limit)

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return [dict(row) for row in rows]

def upsert_recipe_season_theme(
        recipe_id: str | None = None,
        season_type: str | None = None,
        title: str | None = None,
        source_url: str | None = None,
        **kwargs
) -> None:
    """
    계절별 테마 수집 결과를 저장한다.

    같은 recipe_id + season_type 조합이 이미 있으면
    title/source_url만 갱신한다.
    """

    if recipe_id is None:
        recipe_id = kwargs.get("recipe_id")

    if season_type is None:
        season_type = (
            kwargs.get("season_type")
            or kwargs.get("season")
            or kwargs.get("theme")
            or kwargs.get("theme_name")
        )

    if title is None:
        title = kwargs.get("title")

    if source_url is None:
        source_url = kwargs.get("source_url")

    if not recipe_id or not season_type:
        return

    recipe_id = str(recipe_id).strip()
    season_type = str(season_type).strip()
    title = "" if title is None else str(title).strip()
    source_url = "" if source_url is None else str(source_url).strip()

    if not recipe_id or not season_type:
        return

    sql = text("""
        INSERT INTO recipe_season_theme (
              recipe_id
            , season_type
            , title
            , source_url
        )
        VALUES (
              :recipe_id
            , :season_type
            , :title
            , :source_url
        )
        ON CONFLICT(recipe_id, season_type) DO UPDATE SET
              title      = COALESCE(NULLIF(excluded.title, ''), recipe_season_theme.title)
            , source_url = COALESCE(NULLIF(excluded.source_url, ''), recipe_season_theme.source_url)
            , created_at = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "recipe_id": recipe_id,
            "season_type": season_type,
            "title": title,
            "source_url": source_url,
        })

def count_recipe_season_theme(
        season_type: str | None = None,
        **kwargs
) -> int:
    """
    계절 테마별 수집된 레시피 수를 조회한다.

    예:
        count_recipe_season_theme("봄")
        count_recipe_season_theme(season_type="여름")
        count_recipe_season_theme(season="가을")
    """

    if season_type is None:
        season_type = (
            kwargs.get("season_type")
            or kwargs.get("season")
            or kwargs.get("theme")
            or kwargs.get("theme_name")
        )

    if not season_type:
        sql = text("""
            SELECT COUNT(*) AS cnt
              FROM recipe_season_theme
        """)

        with engine.begin() as conn:
            row = conn.execute(sql).mappings().one()

        return int(row["cnt"])

    season_type = str(season_type).strip()

    sql = text("""
        SELECT COUNT(*) AS cnt
          FROM recipe_season_theme
         WHERE season_type = :season_type
    """)

    with engine.begin() as conn:
        row = conn.execute(sql, {
            "season_type": season_type,
        }).mappings().one()

    return int(row["cnt"])

def find_season_main_ingredients(
        season_type: str | None = None,
        min_count: int = 1,
        limit: int | None = None,
        **kwargs
) -> list[dict]:
    """
    계절별 대표 메인 재료 집계 조회.

    recipe_season_theme:
        어떤 recipe_id가 어떤 계절 테마에서 수집되었는지 저장

    raw_recipe_ingredients:
        recipe_id별 추출 재료와 is_main 여부 저장

    반환 예:
        [
            {
                "season_type": "봄",
                "ingredient_name": "달래",
                "ingredient_count": 12,
                "cnt": 12
            }
        ]
    """

    if season_type is None:
        season_type = (
            kwargs.get("season_type")
            or kwargs.get("season")
            or kwargs.get("theme")
            or kwargs.get("theme_name")
        )

    if "top_n" in kwargs and limit is None:
        limit = kwargs["top_n"]

    where_season = ""

    if season_type:
        where_season = """
           AND ST.season_type = :season_type
        """

    limit_clause = ""

    if limit is not None and int(limit) > 0:
        limit_clause = " LIMIT :limit"

    sql = text(f"""
        SELECT ST.season_type
             , RI.ingredient_name
             , COUNT(*) AS ingredient_count
             , COUNT(*) AS cnt
          FROM recipe_season_theme ST
         INNER JOIN raw_recipe_ingredients RI
            ON RI.recipe_id = ST.recipe_id
         WHERE RI.ingredient_name IS NOT NULL
           AND TRIM(RI.ingredient_name) <> ''
           AND IFNULL(RI.is_main, 0) = 1
           {where_season}
         GROUP BY ST.season_type
                , RI.ingredient_name
        HAVING COUNT(*) >= :min_count
         ORDER BY ST.season_type
                , COUNT(*) DESC
                , RI.ingredient_name
         {limit_clause}
    """)

    params = {
        "min_count": int(min_count),
    }

    if season_type:
        params["season_type"] = str(season_type).strip()

    if limit is not None and int(limit) > 0:
        params["limit"] = int(limit)

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return [dict(row) for row in rows]

def find_all_recipe_ingredients_for_season_score(
        limit: int | None = None,
        only_main: bool = True,
        **kwargs
) -> list[dict]:
    """
    계절 점수 계산 대상 레시피 재료 조회.

    기본적으로 is_main = 1인 메인 재료만 조회한다.
    season_score_calculator에서 레시피별 재료와 계절 대표 재료를 비교할 때 사용한다.
    """

    if "max_count" in kwargs:
        limit = kwargs["max_count"]

    if "main_only" in kwargs:
        only_main = kwargs["main_only"]

    if "only_main" in kwargs:
        only_main = kwargs["only_main"]

    main_condition = ""

    if only_main:
        main_condition = """
           AND IFNULL(RI.is_main, 0) = 1
        """

    limit_clause = ""

    if limit is not None and int(limit) > 0:
        limit_clause = " LIMIT :limit"

    sql = text(f"""
        SELECT R.recipe_id
             , R.title
             , RI.ingredient_name
             , RI.raw_text
             , IFNULL(RI.is_main, 0) AS is_main
          FROM raw_recipe R
         INNER JOIN raw_recipe_ingredients RI
            ON RI.recipe_id = R.recipe_id
         WHERE R.recipe_id IS NOT NULL
           AND R.title IS NOT NULL
           AND TRIM(R.title) <> ''
           AND RI.ingredient_name IS NOT NULL
           AND TRIM(RI.ingredient_name) <> ''
           {main_condition}
         ORDER BY R.recipe_id
                , RI.ingredient_name
         {limit_clause}
    """)

    params = {}

    if limit is not None and int(limit) > 0:
        params["limit"] = int(limit)

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return [dict(row) for row in rows]

def clear_recipe_season_score(
        model_version: str | None = None,
        **kwargs
) -> None:
    """
    계절 점수 계산 결과를 삭제한다.

    model_version이 있으면 해당 버전만 삭제하고,
    없으면 recipe_season_score 전체를 삭제한다.
    """

    if model_version is None:
        model_version = kwargs.get("version")

    if model_version:
        sql = text("""
            DELETE FROM recipe_season_score
             WHERE model_version = :model_version
        """)

        params = {
            "model_version": model_version
        }
    else:
        sql = text("""
            DELETE FROM recipe_season_score
        """)

        params = {}

    with engine.begin() as conn:
        conn.execute(sql, params)