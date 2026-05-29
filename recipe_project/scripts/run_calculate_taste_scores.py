from collections import defaultdict

from db.repository import (
    find_recipe_ingredients_for_taste_score,
    upsert_recipe_taste_score,
)
from pipeline.taste_score_calculator import calculate_taste_score


def main():
    rows = find_recipe_ingredients_for_taste_score()

    recipe_ingredients = defaultdict(list)

    for row in rows:
        recipe_id = row["recipe_id"]
        ingredient_name = row["ingredient_name"]

        recipe_ingredients[recipe_id].append(ingredient_name)

    print(f"target recipe count={len(recipe_ingredients)}")

    saved_count = 0

    for recipe_id, ingredients in recipe_ingredients.items():
        taste_score = calculate_taste_score(ingredients)

        upsert_recipe_taste_score(
            recipe_id=recipe_id,
            taste_score=taste_score
        )

        saved_count += 1

        print(
            f"recipe_id={recipe_id}, "
            f"main_taste={taste_score['main_taste']}, "
            f"spicy={taste_score['taste_spicy_score']}, "
            f"savory={taste_score['taste_savory_score']}, "
            f"sweet={taste_score['taste_sweet_score']}, "
            f"sour={taste_score['taste_sour_score']}, "
            f"salty={taste_score['taste_salty_score']}, "
            f"light={taste_score['taste_light_score']}"
        )

    print(f"done. saved_count={saved_count}")


if __name__ == "__main__":
    main()