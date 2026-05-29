CREATE TABLE `raw_recipe` (
  `recipe_id` varchar(30) NOT NULL,
  `title` varchar(500) DEFAULT NULL,
  `category_type` varchar(100) DEFAULT NULL,
  `summary` text,
  `ingredients` text,
  `steps` text,
  `tags` text,
  `view_count` int DEFAULT NULL,
  `scrap_count` int DEFAULT NULL,
  `review_count` int DEFAULT NULL,
  `source_url` varchar(1000) DEFAULT NULL,
  `crawled_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`recipe_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `raw_ingredients` (
  `ingredient_id` bigint NOT NULL AUTO_INCREMENT,
  `ingredient_name` varchar(200) NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ingredient_id`),
  UNIQUE KEY `ingredient_name` (`ingredient_name`)
) ENGINE=InnoDB AUTO_INCREMENT=5381 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `raw_recipe_ingredient` (
  `recipe_id` varchar(30) NOT NULL,
  `ingredient_name` varchar(200) NOT NULL,
  `raw_text` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `is_main` char(1) DEFAULT 'N',
  `main_score` decimal(8,4) DEFAULT '0.0000',
  `main_match_type` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`recipe_id`,`ingredient_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `recipe_taste_score` (
  `recipe_id` varchar(30) NOT NULL,
  `taste_spicy_score` decimal(8,2) DEFAULT '0.00',
  `taste_savory_score` decimal(8,2) DEFAULT '0.00',
  `taste_sweet_score` decimal(8,2) DEFAULT '0.00',
  `taste_sour_score` decimal(8,2) DEFAULT '0.00',
  `taste_salty_score` decimal(8,2) DEFAULT '0.00',
  `taste_light_score` decimal(8,2) DEFAULT '0.00',
  `main_taste` varchar(50) DEFAULT NULL,
  `matched_keywords` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`recipe_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `recipe_similarity` (
  `source_recipe_id` varchar(30) NOT NULL,
  `target_recipe_id` varchar(30) NOT NULL,
  `source_title` varchar(500) DEFAULT NULL,
  `target_title` varchar(500) DEFAULT NULL,
  `total_similarity` decimal(8,4) DEFAULT '0.0000',
  `ingredient_similarity` decimal(8,4) DEFAULT '0.0000',
  `taste_similarity` decimal(8,4) DEFAULT '0.0000',
  `category_similarity` decimal(8,4) DEFAULT '0.0000',
  `common_ingredients` text,
  `source_main_taste` varchar(50) DEFAULT NULL,
  `target_main_taste` varchar(50) DEFAULT NULL,
  `relation_reason` text,
  `model_version` varchar(50) NOT NULL DEFAULT 'v1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`source_recipe_id`,`target_recipe_id`,`model_version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `recipe_cluster_result` (
  `recipe_id` varchar(30) NOT NULL,
  `title` varchar(500) DEFAULT NULL,
  `category_type` varchar(100) DEFAULT NULL,
  `main_taste` varchar(50) DEFAULT NULL,
  `cluster_id` int DEFAULT NULL,
  `cluster_label` varchar(200) DEFAULT NULL,
  `taste_spicy_score` decimal(8,2) DEFAULT '0.00',
  `taste_savory_score` decimal(8,2) DEFAULT '0.00',
  `taste_sweet_score` decimal(8,2) DEFAULT '0.00',
  `taste_sour_score` decimal(8,2) DEFAULT '0.00',
  `taste_salty_score` decimal(8,2) DEFAULT '0.00',
  `taste_light_score` decimal(8,2) DEFAULT '0.00',
  `model_version` varchar(50) DEFAULT 'kmeans_v1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`recipe_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `recipe_season_theme` (
  `recipe_id` varchar(30) NOT NULL,
  `season_type` varchar(20) NOT NULL,
  `theme_url` varchar(1000) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`recipe_id`,`season_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `ingredient_exclude_rule` (
  `ingredient_name` varchar(200) NOT NULL,
  `exclude_type` varchar(50) DEFAULT NULL,
  `reason` varchar(500) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ingredient_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `recipe_season_score` (
  `recipe_id` varchar(30) NOT NULL,
  `spring_score` decimal(8,4) DEFAULT '0.0000',
  `summer_score` decimal(8,4) DEFAULT '0.0000',
  `autumn_score` decimal(8,4) DEFAULT '0.0000',
  `winter_score` decimal(8,4) DEFAULT '0.0000',
  `main_season` varchar(20) DEFAULT NULL,
  `matched_ingredients` text,
  `model_version` varchar(50) DEFAULT 'season_v1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `score_reason` text,
  PRIMARY KEY (`recipe_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- review
CREATE TABLE `raw_recipe_review` (
  `recipe_id` varchar(30) NOT NULL,
  `review_seq` int NOT NULL,
  `review_date` date DEFAULT NULL,
  `nickname` varchar(200) DEFAULT NULL,
  `review_content` text,
  `rating` decimal(3,1) DEFAULT NULL,
  `crawled_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`recipe_id`,`review_seq`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `recipe_season_reaction_score` (
  `recipe_id` varchar(30) NOT NULL,
  `spring_review_count` int DEFAULT '0',
  `summer_review_count` int DEFAULT '0',
  `autumn_review_count` int DEFAULT '0',
  `winter_review_count` int DEFAULT '0',
  `spring_reaction_score` decimal(8,4) DEFAULT '0.0000',
  `summer_reaction_score` decimal(8,4) DEFAULT '0.0000',
  `autumn_reaction_score` decimal(8,4) DEFAULT '0.0000',
  `winter_reaction_score` decimal(8,4) DEFAULT '0.0000',
  `main_reaction_season` varchar(20) DEFAULT NULL,
  `total_review_count` int DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`recipe_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- weather
CREATE TABLE `weather_daily` (
  `weather_date` date NOT NULL,
  `avg_temp` decimal(6,2) DEFAULT NULL,
  `min_temp` decimal(6,2) DEFAULT NULL,
  `max_temp` decimal(6,2) DEFAULT NULL,
  `avg_humidity` decimal(6,2) DEFAULT NULL,
  `rainfall` decimal(8,2) DEFAULT NULL,
  `rain_yn` char(1) DEFAULT NULL,
  `source` varchar(50) DEFAULT 'OPEN_METEO',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`weather_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `recipe_daily_reaction` (
  `recipe_id` varchar(30) NOT NULL,
  `reaction_date` date NOT NULL,
  `review_count` int DEFAULT '0',
  `avg_temp` decimal(6,2) DEFAULT NULL,
  `min_temp` decimal(6,2) DEFAULT NULL,
  `max_temp` decimal(6,2) DEFAULT NULL,
  `avg_humidity` decimal(6,2) DEFAULT NULL,
  `rainfall` decimal(8,2) DEFAULT NULL,
  `rain_yn` char(1) DEFAULT NULL,
  `season_type` varchar(20) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`recipe_id`,`reaction_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
