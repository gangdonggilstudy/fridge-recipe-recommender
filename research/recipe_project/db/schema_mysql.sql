CREATE TABLE IF NOT EXISTS raw_ingredients (
      ingredient_id   BIGINT NOT NULL AUTO_INCREMENT
    , ingredient_name VARCHAR(200) NOT NULL
    , created_at      TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
    , PRIMARY KEY (ingredient_id)
    , UNIQUE KEY uk_raw_ingredients_name (ingredient_name)
);

CREATE TABLE IF NOT EXISTS raw_recipe_ingredients (
      recipe_id       VARCHAR(50) NOT NULL
    , ingredient_name VARCHAR(200) NOT NULL
    , raw_text        VARCHAR(500)
    , is_main         TINYINT DEFAULT 0
    , created_at      TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
    , PRIMARY KEY (recipe_id, ingredient_name)
    , KEY idx_raw_recipe_ingredients_name (ingredient_name)
);

CREATE TABLE IF NOT EXISTS recipe_season_theme (
      recipe_id    VARCHAR(50) NOT NULL
    , season_type  VARCHAR(20) NOT NULL
    , title        VARCHAR(500)
    , source_url   VARCHAR(1000)
    , created_at   TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
    , PRIMARY KEY (recipe_id, season_type)
    , KEY idx_recipe_season_theme_season (season_type)
);