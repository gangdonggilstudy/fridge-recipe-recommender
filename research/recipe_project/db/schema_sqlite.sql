CREATE TABLE IF NOT EXISTS raw_recipe (
      recipe_id        TEXT PRIMARY KEY
    , title            TEXT NOT NULL
    , summary          TEXT
    , ingredients      TEXT
    , steps            TEXT
    , tags             TEXT
    , category_type    TEXT
    , category_types   TEXT
    , ingredient_types TEXT
    , method_types     TEXT
    , situation_types  TEXT
    , cook_time        INTEGER
    , difficulty       TEXT
    , avg_rating       REAL
    , review_count     INTEGER DEFAULT 0
    , scrap_count      INTEGER DEFAULT 0
    , view_count       INTEGER DEFAULT 0
    , source_url       TEXT
    , crawled_at       TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_recipe_review (
      review_id    INTEGER PRIMARY KEY AUTOINCREMENT
    , recipe_id    TEXT NOT NULL
    , rating       REAL
    , content      TEXT
    , review_date  TEXT
    , created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_ingredients (
      ingredient_id   INTEGER PRIMARY KEY AUTOINCREMENT
    , ingredient_name TEXT NOT NULL UNIQUE
    , created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recipe_taste_score (
      recipe_id            TEXT PRIMARY KEY
    , taste_spicy_score    REAL DEFAULT 0
    , taste_savory_score   REAL DEFAULT 0
    , taste_sweet_score    REAL DEFAULT 0
    , taste_sour_score     REAL DEFAULT 0
    , taste_salty_score    REAL DEFAULT 0
    , taste_light_score    REAL DEFAULT 0
    , main_taste           TEXT
    , matched_keywords     TEXT
    , model_version        TEXT DEFAULT 'taste_v1'
    , created_at           TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recipe_season_score (
      recipe_id            TEXT PRIMARY KEY
    , spring_score         REAL DEFAULT 0
    , summer_score         REAL DEFAULT 0
    , autumn_score         REAL DEFAULT 0
    , winter_score         REAL DEFAULT 0
    , main_season          TEXT
    , matched_ingredients  TEXT
    , model_version        TEXT DEFAULT 'season_v1'
    , created_at           TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_recipe_review_count
    ON raw_recipe(review_count);

CREATE INDEX IF NOT EXISTS idx_raw_recipe_category_type
    ON raw_recipe(category_type);

CREATE INDEX IF NOT EXISTS idx_raw_recipe_cook_time
    ON raw_recipe(cook_time);

CREATE TABLE IF NOT EXISTS raw_recipe_ingredients (
      recipe_id       TEXT NOT NULL
    , ingredient_name TEXT NOT NULL
    , raw_text        TEXT
    , is_main         INTEGER DEFAULT 0
    , created_at      TEXT DEFAULT CURRENT_TIMESTAMP
    , PRIMARY KEY (recipe_id, ingredient_name)
);

CREATE INDEX IF NOT EXISTS idx_raw_recipe_ingredients_name
    ON raw_recipe_ingredients(ingredient_name);

CREATE TABLE IF NOT EXISTS recipe_season_theme (
      recipe_id    TEXT NOT NULL
    , season_type  TEXT NOT NULL
    , title        TEXT
    , source_url   TEXT
    , created_at   TEXT DEFAULT CURRENT_TIMESTAMP
    , PRIMARY KEY (recipe_id, season_type)
);

CREATE INDEX IF NOT EXISTS idx_recipe_season_theme_season
    ON recipe_season_theme(season_type);