import argparse
import os
from collections import Counter, defaultdict

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from db.repository import (
    find_recipes_for_clustering,
    find_all_recipe_ingredients,
    find_recipe_cluster_results,
)

from pipeline.kmeans_feature_filter import is_valid_kmeans_ingredient


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
        "--top-ingredients",
        type=int,
        default=30,
        help="K-means 때 사용한 주요 재료 Top N. 기본값 30"
    )

    parser.add_argument(
        "--model-version",
        type=str,
        default="kmeans_v1",
        help="recipe_cluster_result의 model_version. 기본값 kmeans_v1"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="outputs/kmeans_pca_scatter.png",
        help="저장할 이미지 경로"
    )

    return parser.parse_args()


def build_ingredient_map() -> dict[str, set[str]]:
    rows = find_all_recipe_ingredients()

    ingredient_map = defaultdict(set)

    for row in rows:
        recipe_id = row["recipe_id"]
        ingredient_name = row["ingredient_name"]

        if recipe_id and ingredient_name:
            ingredient_map[recipe_id].add(ingredient_name)

    return dict(ingredient_map)


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
            "title": recipe.get("title") or "",
            "category_type": recipe.get("category_type") or "미분류",
            "main_taste": recipe.get("main_taste") or "미분류",
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


def build_cluster_dataframe(model_version: str) -> pd.DataFrame:
    rows = find_recipe_cluster_results(model_version=model_version)
    return pd.DataFrame(rows)


def main():
    args = parse_args()

    recipes = find_recipes_for_clustering()
    ingredient_map = build_ingredient_map()

    top_ingredients = get_top_ingredients(
        ingredient_map=ingredient_map,
        top_n=args.top_ingredients
    )

    print(f"recipe count={len(recipes)}")
    print(f"top ingredient count={len(top_ingredients)}")
    print(f"top ingredients={top_ingredients}")

    feature_df = build_feature_dataframe(
        recipes=recipes,
        ingredient_map=ingredient_map,
        top_ingredients=top_ingredients
    )

    cluster_df = build_cluster_dataframe(
        model_version=args.model_version
    )

    if cluster_df.empty:
        raise ValueError("recipe_cluster_result 데이터가 없습니다. 먼저 K-means를 실행하세요.")

    df = feature_df.merge(
        cluster_df,
        on="recipe_id",
        how="inner"
    )

    if df.empty:
        raise ValueError("feature 데이터와 cluster 데이터가 매칭되지 않습니다.")

    meta_cols = [
        "recipe_id",
        "title",
        "category_type",
        "main_taste",
        "cluster_id",
        "cluster_label",
    ]

    feature_cols = [
        col
        for col in df.columns
        if col not in meta_cols
    ]

    print(f"feature count={len(feature_cols)}")

    X = df[feature_cols].fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    pca = PCA(n_components=2, random_state=42)
    pca_result = pca.fit_transform(X_scaled)

    df["pca_1"] = pca_result[:, 0]
    df["pca_2"] = pca_result[:, 1]

    explained_ratio = pca.explained_variance_ratio_
    print(f"PCA explained variance ratio={explained_ratio}")
    print(f"PCA total explained={round(explained_ratio.sum(), 4)}")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # Mac 한글 폰트 설정
    plt.rcParams["font.family"] = "AppleGothic"
    plt.rcParams["axes.unicode_minus"] = False

    plt.figure(figsize=(12, 8))

    scatter = plt.scatter(
        df["pca_1"],
        df["pca_2"],
        c=df["cluster_id"],
        alpha=0.75,
        s=60
    )

    plt.title("K-means Recipe Clusters visualized with PCA")
    plt.xlabel(f"PCA 1 ({explained_ratio[0] * 100:.1f}%)")
    plt.ylabel(f"PCA 2 ({explained_ratio[1] * 100:.1f}%)")

    legend = plt.legend(
        *scatter.legend_elements(),
        title="cluster_id",
        loc="best"
    )
    plt.gca().add_artist(legend)

    # 클러스터 중심 위치에 라벨 표시
    cluster_centers = (
        df.groupby("cluster_id")[["pca_1", "pca_2"]]
          .mean()
          .reset_index()
    )

    for _, row in cluster_centers.iterrows():
        cluster_id = int(row["cluster_id"])

        label_values = df[df["cluster_id"] == cluster_id]["cluster_label"].dropna().unique()
        cluster_label = label_values[0] if len(label_values) > 0 else f"Cluster {cluster_id}"

        plt.text(
            row["pca_1"],
            row["pca_2"],
            f"{cluster_id}\n{cluster_label}",
            fontsize=9,
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.3", alpha=0.2)
        )

    plt.tight_layout()
    plt.savefig(args.output, dpi=200)
    plt.close()

    print(f"saved plot: {args.output}")


if __name__ == "__main__":
    main()