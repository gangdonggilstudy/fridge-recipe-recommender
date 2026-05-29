import argparse
import math
from collections import Counter, defaultdict

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from db.repository import (
    find_recipes_for_clustering,
    find_all_recipe_ingredients,
    find_main_recipe_ingredients_for_clustering,
    clear_recipe_cluster_result,
    upsert_recipe_cluster_result,
)

from pipeline.kmeans_feature_filter import is_valid_kmeans_ingredient

MODEL_VERSION = "kmeans_v1"

TASTE_COLUMNS = [
    "taste_spicy_score",
    "taste_savory_score",
    "taste_sweet_score",
    "taste_sour_score",
    "taste_salty_score",
    "taste_light_score",
]


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--clusters",
        type=int,
        default=5,
        help="K-means 클러스터 개수. 기본값 5"
    )

    parser.add_argument(
        "--top-ingredients",
        type=int,
        default=30,
        help="피처로 사용할 주요 재료 Top N. 기본값 30"
    )

    return parser.parse_args()


def build_ingredient_map() -> dict[str, set[str]]:
    # rows = find_all_recipe_ingredients()
    rows = find_main_recipe_ingredients_for_clustering()

    ingredient_map = defaultdict(set)

    for row in rows:
        recipe_id = row["recipe_id"]
        ingredient_name = row["ingredient_name"]

        if ingredient_name:
            ingredient_map[recipe_id].add(ingredient_name)

    return dict(ingredient_map)


# def get_top_ingredients(
#         ingredient_map: dict[str, set[str]],
#         top_n: int
# ) -> list[str]:
#     counter = Counter()

#     for ingredients in ingredient_map.values():
#         for ingredient in ingredients:
#             counter[ingredient] += 1

#     return [
#         ingredient
#         for ingredient, _ in counter.most_common(top_n)
#     ]

def get_top_ingredients(
        ingredient_map: dict[str, set[str]],
        top_n: int
) -> list[str]:
    counter = Counter()

    for ingredients in ingredient_map.values():
        for ingredient in ingredients:
            if not is_valid_kmeans_ingredient(ingredient):
                continue

            counter[ingredient] += 1

    return [
        ingredient
        for ingredient, _ in counter.most_common(top_n)
    ]

def safe_value(value, default=None):
    if value is None:
        return default

    if isinstance(value, float) and math.isnan(value):
        return default

    if pd.isna(value):
        return default

    return value


def safe_float(value, default=0.0):
    if value is None:
        return default

    if isinstance(value, float) and math.isnan(value):
        return default

    if pd.isna(value):
        return default

    return float(value)
    
def build_feature_dataframe(
        recipes: list[dict],
        ingredient_map: dict[str, set[str]],
        top_ingredients: list[str]
) -> pd.DataFrame:
    rows = []

    for recipe in recipes:
        recipe_id = recipe["recipe_id"]
        ingredients = ingredient_map.get(recipe_id, set())

        row = {
            "recipe_id": recipe_id,
            "title": recipe.get("title"),
            "category_type": recipe.get("category_type"),
            "main_taste": recipe.get("main_taste"),
        }

        for col in TASTE_COLUMNS:
            row[col] = float(recipe.get(col) or 0)

        for ingredient in top_ingredients:
            row[f"ing_{ingredient}"] = 1 if ingredient in ingredients else 0

        rows.append(row)

    df = pd.DataFrame(rows)

    category_dummies = pd.get_dummies(
        df["category_type"].fillna("미분류"),
        prefix="category"
    )

    df = pd.concat([df, category_dummies], axis=1)

    return df


def build_cluster_labels(
        df: pd.DataFrame,
        ingredient_map: dict[str, set[str]]
) -> dict[int, str]:
    cluster_labels = {}

    for cluster_id in sorted(df["cluster_id"].unique()):
        cluster_df = df[df["cluster_id"] == cluster_id]

        category_label = "카테고리혼합"

        valid_categories = cluster_df["category_type"].dropna()
        valid_categories = valid_categories[valid_categories != "미분류"]

        if not valid_categories.empty:
            category_label = valid_categories.mode().iloc[0]

        taste_label = "맛혼합"

        valid_tastes = cluster_df["main_taste"].dropna()
        valid_tastes = valid_tastes[valid_tastes != "미분류"]

        if not valid_tastes.empty:
            taste_label = valid_tastes.mode().iloc[0]

        ingredient_counter = Counter()

        for recipe_id in cluster_df["recipe_id"]:
            for ingredient in ingredient_map.get(recipe_id, set()):
                if not is_valid_kmeans_ingredient(ingredient):
                    continue

                ingredient_counter[ingredient] += 1

        top_ingredients = [
            ingredient
            for ingredient, _ in ingredient_counter.most_common(3)
        ]

        if top_ingredients:
            ingredient_text = "/".join(top_ingredients)
            label = f"{category_label}-{taste_label}-{ingredient_text}"
        else:
            label = f"{category_label}-{taste_label}"

        cluster_labels[int(cluster_id)] = label

    return cluster_labels

def main():
    args = parse_args()

    recipes = find_recipes_for_clustering()
    ingredient_map = build_ingredient_map()

    if len(recipes) < args.clusters:
        raise ValueError(
            f"recipe count({len(recipes)}) must be greater than clusters({args.clusters})"
        )

    top_ingredients = get_top_ingredients(
        ingredient_map=ingredient_map,
        top_n=args.top_ingredients
    )

    print(f"recipe count={len(recipes)}")
    print(f"clusters={args.clusters}")
    print(f"top ingredients={top_ingredients}")

    df = build_feature_dataframe(
        recipes=recipes,
        ingredient_map=ingredient_map,
        top_ingredients=top_ingredients
    )

    df["category_type"] = df["category_type"].fillna("미분류")
    df["main_taste"] = df["main_taste"].fillna("미분류")
    df["title"] = df["title"].fillna("")

    meta_cols = [
        "recipe_id",
        "title",
        "category_type",
        "main_taste",
    ]

    feature_cols = [
        col
        for col in df.columns
        if col not in meta_cols
    ]

    X = df[feature_cols].fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(
        n_clusters=args.clusters,
        random_state=42,
        n_init=10
    )

    df["cluster_id"] = kmeans.fit_predict(X_scaled)

    if args.clusters > 1 and len(df) > args.clusters:
        score = silhouette_score(X_scaled, df["cluster_id"])
        print(f"silhouette_score={round(score, 4)}")

    cluster_labels = build_cluster_labels(
        df=df,
        ingredient_map=ingredient_map
    )

    df["cluster_label"] = df["cluster_id"].apply(
        lambda cluster_id: cluster_labels[int(cluster_id)]
    )

    clear_recipe_cluster_result(MODEL_VERSION)

    saved_count = 0

    for _, row in df.iterrows():
        upsert_recipe_cluster_result({
            "recipe_id": safe_value(row["recipe_id"]),
            "title": safe_value(row["title"], ""),
            "category_type": safe_value(row["category_type"], "미분류"),
            "main_taste": safe_value(row["main_taste"], "미분류"),
            "cluster_id": int(row["cluster_id"]),
            "cluster_label": safe_value(row["cluster_label"], ""),
            "taste_spicy_score": safe_float(row["taste_spicy_score"]),
            "taste_savory_score": safe_float(row["taste_savory_score"]),
            "taste_sweet_score": safe_float(row["taste_sweet_score"]),
            "taste_sour_score": safe_float(row["taste_sour_score"]),
            "taste_salty_score": safe_float(row["taste_salty_score"]),
            "taste_light_score": safe_float(row["taste_light_score"]),
            "model_version": MODEL_VERSION,
        })

        saved_count += 1

    print("cluster summary")
    print(
        df.groupby(["cluster_id", "cluster_label"])
          .size()
          .reset_index(name="recipe_count")
          .sort_values("cluster_id")
    )

    print(f"done. saved_count={saved_count}")


if __name__ == "__main__":
    main()