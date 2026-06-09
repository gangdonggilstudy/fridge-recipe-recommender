import argparse
from collections import defaultdict

from db.repository import (
    find_season_main_ingredients,
    find_all_recipe_ingredients_for_season_score,
    clear_recipe_season_score,
    upsert_recipe_season_score,
)
from pipeline.season_score_calculator import calculate_recipe_season_score


MODEL_VERSION = "season_v1"


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="계절별 대표 메인 재료 Top N. 기본값 10"
    )

    return parser.parse_args()

from collections import defaultdict

SEASON_TYPES = ["봄", "여름", "가을", "겨울"]


def build_season_ingredient_map(top_n: int) -> dict[str, set[str]]:
    season_ingredient_map = defaultdict(set)

    for season_type in SEASON_TYPES:
        rows = find_season_main_ingredients(
            season_type=season_type,
            top_n=top_n,
        )

        print(f"[DEBUG] {season_type} 대표 재료 수: {len(rows)}")

        for row in rows:
            ingredient_name = row.get("ingredient_name")

            if ingredient_name:
                season_ingredient_map[season_type].add(ingredient_name)

    return dict(season_ingredient_map)
# def build_season_ingredient_map(top_n: int) -> dict[str, set[str]]:
#     rows = find_season_main_ingredients(top_n=top_n)

#     season_ingredient_map = defaultdict(set)

#     for row in rows:
#         season_type = row["season_type"]
#         ingredient_name = row["ingredient_name"]

#         if season_type and ingredient_name:
#             season_ingredient_map[season_type].add(ingredient_name)

#     return dict(season_ingredient_map)


def build_recipe_ingredient_map() -> dict[str, set[str]]:
    rows = find_all_recipe_ingredients_for_season_score()

    recipe_ingredient_map = defaultdict(set)

    for row in rows:
        recipe_id = row["recipe_id"]
        ingredient_name = row["ingredient_name"]

        if recipe_id and ingredient_name:
            recipe_ingredient_map[recipe_id].add(ingredient_name)

    return dict(recipe_ingredient_map)


def main():
    args = parse_args()

    season_ingredient_map = build_season_ingredient_map(
        top_n=args.top_n
    )

    print("season ingredient map")
    for season_type, ingredients in season_ingredient_map.items():
        print(f"{season_type}: {sorted(ingredients)}")

    recipe_ingredient_map = build_recipe_ingredient_map()

    print(f"target recipe count={len(recipe_ingredient_map)}")

    clear_recipe_season_score(MODEL_VERSION)

    saved_count = 0

    for recipe_id, ingredients in recipe_ingredient_map.items():
        score = calculate_recipe_season_score(
            recipe_ingredients=ingredients,
            season_ingredient_map=season_ingredient_map
        )

        upsert_recipe_season_score({
            "recipe_id": recipe_id,
            "spring_score": score["spring_score"],
            "summer_score": score["summer_score"],
            "autumn_score": score["autumn_score"],
            "winter_score": score["winter_score"],
            "main_season": score["main_season"],
            "matched_ingredients": score["matched_ingredients"],
            "model_version": MODEL_VERSION,
        })

        saved_count += 1

        print(
            f"recipe_id={recipe_id}, "
            f"main_season={score['main_season']}, "
            f"spring={score['spring_score']}, "
            f"summer={score['summer_score']}, "
            f"autumn={score['autumn_score']}, "
            f"winter={score['winter_score']}"
        )

    print(f"done. saved_count={saved_count}")


if __name__ == "__main__":
    main()