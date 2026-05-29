from sqlalchemy import text
from db.connection import engine


def upsert_raw_recipe(recipe: dict) -> None:
    sql = text("""
        INSERT INTO raw_recipe (
              recipe_id
            , title
            , category_type
            , summary
            , ingredients
            , steps
            , tags
            , view_count
            , scrap_count
            , review_count
            , source_url
        )
        VALUES (
              :recipe_id
            , :title
            , :category_type
            , :summary
            , :ingredients
            , :steps
            , :tags
            , :view_count
            , :scrap_count
            , :review_count
            , :source_url
        )
        ON DUPLICATE KEY UPDATE
              title         = COALESCE(NULLIF(VALUES(title), ''), title)
            , category_type = COALESCE(NULLIF(VALUES(category_type), ''), category_type)
            , summary       = COALESCE(NULLIF(VALUES(summary), ''), summary)
            , ingredients   = COALESCE(NULLIF(VALUES(ingredients), ''), ingredients)
            , steps         = COALESCE(NULLIF(VALUES(steps), ''), steps)
            , tags          = COALESCE(NULLIF(VALUES(tags), ''), tags)
            , view_count    = COALESCE(VALUES(view_count), view_count)
            , scrap_count   = COALESCE(VALUES(scrap_count), scrap_count)
            , review_count  = COALESCE(VALUES(review_count), review_count)
            , source_url    = COALESCE(NULLIF(VALUES(source_url), ''), source_url)
            , crawled_at    = CURRENT_TIMESTAMP
    """)

    recipe.setdefault("category_type", None)
    recipe.setdefault("view_count", None)
    recipe.setdefault("scrap_count", None)
    recipe.setdefault("review_count", None)

    with engine.begin() as conn:
        conn.execute(sql, recipe)


def count_raw_recipes_by_category(category_type: str) -> int:
    sql = text("""
        SELECT COUNT(*) AS recipe_count
          FROM raw_recipe
         WHERE category_type = :category_type
    """)

    with engine.begin() as conn:
        row = conn.execute(sql, {
            "category_type": category_type
        }).mappings().one()

    return int(row["recipe_count"])


def exists_raw_recipe(recipe_id: str) -> bool:
    sql = text("""
        SELECT COUNT(*) AS recipe_count
          FROM raw_recipe
         WHERE recipe_id = :recipe_id
    """)

    with engine.begin() as conn:
        row = conn.execute(sql, {
            "recipe_id": recipe_id
        }).mappings().one()

    return int(row["recipe_count"]) > 0


def find_raw_recipes_for_ingredient_extract() -> list[dict]:
    sql = text("""
        SELECT recipe_id
             , ingredients
          FROM raw_recipe
         WHERE ingredients IS NOT NULL
           AND TRIM(ingredients) <> ''
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]


def upsert_raw_ingredient(ingredient_name: str) -> None:
    sql = text("""
        INSERT INTO raw_ingredients (
              ingredient_name
        )
        VALUES (
              :ingredient_name
        )
        ON DUPLICATE KEY UPDATE
              ingredient_name = VALUES(ingredient_name)
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "ingredient_name": ingredient_name
        })


def upsert_raw_recipe_ingredient(
        recipe_id: str,
        ingredient_name: str,
        raw_text: str
) -> None:
    sql = text("""
        INSERT INTO raw_recipe_ingredient (
              recipe_id
            , ingredient_name
            , raw_text
        )
        VALUES (
              :recipe_id
            , :ingredient_name
            , :raw_text
        )
        ON DUPLICATE KEY UPDATE
              raw_text   = VALUES(raw_text)
            , created_at = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "recipe_id": recipe_id,
            "ingredient_name": ingredient_name,
            "raw_text": raw_text
        })


def find_recipe_ingredients_for_taste_score() -> list[dict]:
    sql = text("""
        SELECT recipe_id
             , ingredient_name
          FROM raw_recipe_ingredient
         WHERE ingredient_name IS NOT NULL
           AND TRIM(ingredient_name) <> ''
         ORDER BY recipe_id
                , ingredient_name
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]


def upsert_recipe_taste_score(recipe_id: str, taste_score: dict) -> None:
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
        )
        ON DUPLICATE KEY UPDATE
              taste_spicy_score  = VALUES(taste_spicy_score)
            , taste_savory_score = VALUES(taste_savory_score)
            , taste_sweet_score  = VALUES(taste_sweet_score)
            , taste_sour_score   = VALUES(taste_sour_score)
            , taste_salty_score  = VALUES(taste_salty_score)
            , taste_light_score  = VALUES(taste_light_score)
            , main_taste         = VALUES(main_taste)
            , matched_keywords   = VALUES(matched_keywords)
            , updated_at         = CURRENT_TIMESTAMP
    """)

    params = {
        "recipe_id": recipe_id,
        **taste_score
    }

    with engine.begin() as conn:
        conn.execute(sql, params)

def find_recipes_for_similarity() -> list[dict]:
    sql = text("""
        SELECT R.recipe_id
             , R.title
             , R.category_type
             , T.taste_spicy_score
             , T.taste_savory_score
             , T.taste_sweet_score
             , T.taste_sour_score
             , T.taste_salty_score
             , T.taste_light_score
             , T.main_taste
          FROM raw_recipe R
          LEFT JOIN recipe_taste_score T
            ON T.recipe_id = R.recipe_id
         WHERE R.recipe_id IS NOT NULL
         ORDER BY R.recipe_id
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]


def find_all_recipe_ingredients() -> list[dict]:
    sql = text("""
        SELECT recipe_id
             , ingredient_name
          FROM raw_recipe_ingredient
         WHERE ingredient_name IS NOT NULL
           AND TRIM(ingredient_name) <> ''
         ORDER BY recipe_id
                , ingredient_name
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]


def clear_recipe_similarity(model_version: str = "v1") -> None:
    sql = text("""
        DELETE
          FROM recipe_similarity
         WHERE model_version = :model_version
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "model_version": model_version
        })


def upsert_recipe_similarity(similarity: dict) -> None:
    sql = text("""
        INSERT INTO recipe_similarity (
              source_recipe_id
            , target_recipe_id
            , source_title
            , target_title
            , total_similarity
            , ingredient_similarity
            , taste_similarity
            , category_similarity
            , common_ingredients
            , source_main_taste
            , target_main_taste
            , relation_reason
            , model_version
        )
        VALUES (
              :source_recipe_id
            , :target_recipe_id
            , :source_title
            , :target_title
            , :total_similarity
            , :ingredient_similarity
            , :taste_similarity
            , :category_similarity
            , :common_ingredients
            , :source_main_taste
            , :target_main_taste
            , :relation_reason
            , :model_version
        )
        ON DUPLICATE KEY UPDATE
              source_title          = VALUES(source_title)
            , target_title          = VALUES(target_title)
            , total_similarity      = VALUES(total_similarity)
            , ingredient_similarity = VALUES(ingredient_similarity)
            , taste_similarity      = VALUES(taste_similarity)
            , category_similarity   = VALUES(category_similarity)
            , common_ingredients    = VALUES(common_ingredients)
            , source_main_taste     = VALUES(source_main_taste)
            , target_main_taste     = VALUES(target_main_taste)
            , relation_reason       = VALUES(relation_reason)
            , created_at            = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, similarity)


def find_recipes_for_clustering() -> list[dict]:
    sql = text("""
        SELECT R.recipe_id
             , R.title
             , R.category_type
             , T.main_taste
             , T.taste_spicy_score
             , T.taste_savory_score
             , T.taste_sweet_score
             , T.taste_sour_score
             , T.taste_salty_score
             , T.taste_light_score
          FROM raw_recipe R
          LEFT JOIN recipe_taste_score T
            ON T.recipe_id = R.recipe_id
         WHERE R.recipe_id IS NOT NULL
         ORDER BY R.recipe_id
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]


def clear_recipe_cluster_result(model_version: str = "kmeans_v1") -> None:
    sql = text("""
        DELETE
          FROM recipe_cluster_result
         WHERE model_version = :model_version
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "model_version": model_version
        })


def upsert_recipe_cluster_result(row: dict) -> None:
    sql = text("""
        INSERT INTO recipe_cluster_result (
              recipe_id
            , title
            , category_type
            , main_taste
            , cluster_id
            , cluster_label
            , taste_spicy_score
            , taste_savory_score
            , taste_sweet_score
            , taste_sour_score
            , taste_salty_score
            , taste_light_score
            , model_version
        )
        VALUES (
              :recipe_id
            , :title
            , :category_type
            , :main_taste
            , :cluster_id
            , :cluster_label
            , :taste_spicy_score
            , :taste_savory_score
            , :taste_sweet_score
            , :taste_sour_score
            , :taste_salty_score
            , :taste_light_score
            , :model_version
        )
        ON DUPLICATE KEY UPDATE
              title              = VALUES(title)
            , category_type      = VALUES(category_type)
            , main_taste         = VALUES(main_taste)
            , cluster_id         = VALUES(cluster_id)
            , cluster_label      = VALUES(cluster_label)
            , taste_spicy_score  = VALUES(taste_spicy_score)
            , taste_savory_score = VALUES(taste_savory_score)
            , taste_sweet_score  = VALUES(taste_sweet_score)
            , taste_sour_score   = VALUES(taste_sour_score)
            , taste_salty_score  = VALUES(taste_salty_score)
            , taste_light_score  = VALUES(taste_light_score)
            , model_version      = VALUES(model_version)
            , updated_at         = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, row)

def upsert_recipe_season_theme(
        recipe_id: str,
        season_type: str,
        theme_url: str
) -> None:
    sql = text("""
        INSERT INTO recipe_season_theme (
              recipe_id
            , season_type
            , theme_url
        )
        VALUES (
              :recipe_id
            , :season_type
            , :theme_url
        )
        ON DUPLICATE KEY UPDATE
              theme_url  = VALUES(theme_url)
            , created_at = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "recipe_id": recipe_id,
            "season_type": season_type,
            "theme_url": theme_url
        })


def count_recipe_season_theme(season_type: str | None = None) -> int:
    if season_type:
        sql = text("""
            SELECT COUNT(*) AS recipe_count
              FROM recipe_season_theme
             WHERE season_type = :season_type
        """)

        params = {
            "season_type": season_type
        }

    else:
        sql = text("""
            SELECT COUNT(*) AS recipe_count
              FROM recipe_season_theme
        """)

        params = {}

    with engine.begin() as conn:
        row = conn.execute(sql, params).mappings().one()

    return int(row["recipe_count"])

def find_recipes_for_main_ingredient_marking() -> list[dict]:
    sql = text("""
        SELECT R.recipe_id
             , R.title
             , R.tags
             , I.ingredient_name
          FROM raw_recipe R
         INNER JOIN raw_recipe_ingredient I
            ON I.recipe_id = R.recipe_id
         WHERE I.ingredient_name IS NOT NULL
           AND TRIM(I.ingredient_name) <> ''
         ORDER BY R.recipe_id
                , I.created_at
                , I.ingredient_name
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]


def reset_main_ingredient_flags() -> None:
    sql = text("""
        UPDATE raw_recipe_ingredient
           SET is_main = 'N'
             , main_score = 0
             , main_match_type = NULL
    """)

    with engine.begin() as conn:
        conn.execute(sql)


def update_main_ingredient_flag(
        recipe_id: str,
        ingredient_name: str,
        is_main: str,
        main_score: float,
        main_match_type: str
) -> None:
    sql = text("""
        UPDATE raw_recipe_ingredient
           SET is_main = :is_main
             , main_score = :main_score
             , main_match_type = :main_match_type
         WHERE recipe_id = :recipe_id
           AND ingredient_name = :ingredient_name
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "recipe_id": recipe_id,
            "ingredient_name": ingredient_name,
            "is_main": is_main,
            "main_score": main_score,
            "main_match_type": main_match_type,
        })

def find_season_main_ingredients(top_n: int = 10) -> list[dict]:
    sql = text("""
        WITH MAIN_ING AS (
            SELECT S.season_type
                 , I.ingredient_name
                 , COUNT(*) AS recipe_count
              FROM recipe_season_theme S
             INNER JOIN raw_recipe_ingredient I
                ON I.recipe_id = S.recipe_id
             WHERE I.is_main = 'Y'
             GROUP BY S.season_type
                    , I.ingredient_name
        ),
        RANKED AS (
            SELECT season_type
                 , ingredient_name
                 , recipe_count
                 , ROW_NUMBER() OVER (
                       PARTITION BY season_type
                       ORDER BY recipe_count DESC
                   ) AS rn
              FROM MAIN_ING
        )
        SELECT season_type
             , ingredient_name
             , recipe_count
          FROM RANKED
         WHERE rn <= :top_n
         ORDER BY CASE season_type
                      WHEN '봄'   THEN 1
                      WHEN '여름' THEN 2
                      WHEN '가을' THEN 3
                      WHEN '겨울' THEN 4
                      ELSE 99
                  END
                , rn
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql, {
            "top_n": top_n
        }).mappings().all()

    return [dict(row) for row in rows]


def find_all_recipe_ingredients_for_season_score() -> list[dict]:
    sql = text("""
        SELECT R.recipe_id
             , R.title
             , I.ingredient_name
          FROM raw_recipe R
         INNER JOIN raw_recipe_ingredient I
            ON I.recipe_id = R.recipe_id
         WHERE I.ingredient_name IS NOT NULL
           AND TRIM(I.ingredient_name) <> ''
         ORDER BY R.recipe_id
                , I.ingredient_name
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]


def clear_recipe_season_score(model_version: str = "season_v1") -> None:
    sql = text("""
        DELETE
          FROM recipe_season_score
         WHERE model_version = :model_version
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "model_version": model_version
        })


def upsert_recipe_season_score(row: dict) -> None:
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
        ON DUPLICATE KEY UPDATE
              spring_score        = VALUES(spring_score)
            , summer_score        = VALUES(summer_score)
            , autumn_score        = VALUES(autumn_score)
            , winter_score        = VALUES(winter_score)
            , main_season         = VALUES(main_season)
            , matched_ingredients = VALUES(matched_ingredients)
            , model_version       = VALUES(model_version)
            , updated_at          = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, row)

def find_recipe_cluster_results(model_version: str = "kmeans_v1") -> list[dict]:
    sql = text("""
        SELECT recipe_id
             , cluster_id
             , cluster_label
          FROM recipe_cluster_result
         WHERE model_version = :model_version
         ORDER BY recipe_id
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql, {
            "model_version": model_version
        }).mappings().all()

    return [dict(row) for row in rows]

def find_main_recipe_ingredients_for_clustering() -> list[dict]:
    sql = text("""
        SELECT recipe_id
             , ingredient_name
          FROM raw_recipe_ingredient
         WHERE is_main = 'Y'
           AND ingredient_name IS NOT NULL
           AND TRIM(ingredient_name) <> ''
         ORDER BY recipe_id
                , ingredient_name
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]

def find_recipe_ids_for_review_crawling(limit: int | None = None) -> list[str]:
    if limit:
        sql = text("""
            SELECT recipe_id
              FROM raw_recipe
             ORDER BY recipe_id
             LIMIT :limit
        """)

        params = {
            "limit": limit
        }

    else:
        sql = text("""
            SELECT recipe_id
              FROM raw_recipe
             ORDER BY recipe_id
        """)

        params = {}

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return [row["recipe_id"] for row in rows]


def delete_raw_recipe_reviews(recipe_id: str) -> None:
    sql = text("""
        DELETE
          FROM raw_recipe_review
         WHERE recipe_id = :recipe_id
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "recipe_id": recipe_id
        })


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
        ON DUPLICATE KEY UPDATE
              review_date    = VALUES(review_date)
            , nickname       = VALUES(nickname)
            , review_content = VALUES(review_content)
            , rating         = VALUES(rating)
            , crawled_at     = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, row)


def count_raw_recipe_reviews(recipe_id: str | None = None) -> int:
    if recipe_id:
        sql = text("""
            SELECT COUNT(*) AS review_count
              FROM raw_recipe_review
             WHERE recipe_id = :recipe_id
        """)

        params = {
            "recipe_id": recipe_id
        }

    else:
        sql = text("""
            SELECT COUNT(*) AS review_count
              FROM raw_recipe_review
        """)

        params = {}

    with engine.begin() as conn:
        row = conn.execute(sql, params).mappings().one()

    return int(row["review_count"])

def find_review_date_range() -> dict:
    sql = text("""
        SELECT MIN(review_date) AS min_date
             , MAX(review_date) AS max_date
          FROM raw_recipe_review
         WHERE review_date IS NOT NULL
    """)

    with engine.begin() as conn:
        row = conn.execute(sql).mappings().one()

    return {
        "min_date": row["min_date"],
        "max_date": row["max_date"],
    }


def upsert_weather_daily(row: dict) -> None:
    sql = text("""
        INSERT INTO weather_daily (
              weather_date
            , avg_temp
            , min_temp
            , max_temp
            , avg_humidity
            , rainfall
            , rain_yn
            , source
        )
        VALUES (
              :weather_date
            , :avg_temp
            , :min_temp
            , :max_temp
            , :avg_humidity
            , :rainfall
            , :rain_yn
            , :source
        )
        ON DUPLICATE KEY UPDATE
              avg_temp     = VALUES(avg_temp)
            , min_temp     = VALUES(min_temp)
            , max_temp     = VALUES(max_temp)
            , avg_humidity = VALUES(avg_humidity)
            , rainfall     = VALUES(rainfall)
            , rain_yn      = VALUES(rain_yn)
            , source       = VALUES(source)
            , updated_at   = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(sql, row)

def rebuild_recipe_daily_reaction() -> None:
    delete_sql = text("""
        DELETE
          FROM recipe_daily_reaction
    """)

    insert_sql = text("""
        INSERT INTO recipe_daily_reaction (
              recipe_id
            , reaction_date
            , review_count
            , avg_temp
            , min_temp
            , max_temp
            , avg_humidity
            , rainfall
            , rain_yn
            , season_type
        )
        SELECT R.recipe_id
             , R.review_date AS reaction_date
             , COUNT(*) AS review_count
             , W.avg_temp
             , W.min_temp
             , W.max_temp
             , W.avg_humidity
             , W.rainfall
             , W.rain_yn
             , CASE
                   WHEN MONTH(R.review_date) IN (3,4,5) THEN '봄'
                   WHEN MONTH(R.review_date) IN (6,7,8) THEN '여름'
                   WHEN MONTH(R.review_date) IN (9,10,11) THEN '가을'
                   ELSE '겨울'
               END AS season_type
          FROM raw_recipe_review R
          LEFT JOIN weather_daily W
            ON W.weather_date = R.review_date
         WHERE R.review_date IS NOT NULL
         GROUP BY R.recipe_id
                , R.review_date
                , W.avg_temp
                , W.min_temp
                , W.max_temp
                , W.avg_humidity
                , W.rainfall
                , W.rain_yn
    """)

    with engine.begin() as conn:
        conn.execute(delete_sql)
        conn.execute(insert_sql)


def count_recipe_daily_reaction() -> int:
    sql = text("""
        SELECT COUNT(*) AS row_count
          FROM recipe_daily_reaction
    """)

    with engine.begin() as conn:
        row = conn.execute(sql).mappings().one()

    return int(row["row_count"])