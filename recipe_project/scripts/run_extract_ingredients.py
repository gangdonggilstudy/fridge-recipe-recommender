import re

from db.repository import (
    find_raw_recipes_for_ingredient_extract,
    upsert_raw_ingredient,
    upsert_raw_recipe_ingredient,
)
from pipeline.ingredient_parser import clean_ingredient_name


def split_ingredients(ingredients_text: str) -> list[str]:
    if not ingredients_text:
        return []

    # raw_recipe.ingredients 형식:
    # 재료명,단위/재료명2,단위2
    parts = re.split(r"[/\n]+", ingredients_text)

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def main():
    recipes = find_raw_recipes_for_ingredient_extract()

    print(f"target recipe count={len(recipes)}")

    total_count = 0
    saved_count = 0

    for recipe in recipes:
        recipe_id = recipe["recipe_id"]
        ingredients_text = recipe["ingredients"]

        raw_ingredient_lines = split_ingredients(ingredients_text)
        recipe_saved_count = 0

        for raw_text in raw_ingredient_lines:
            total_count += 1

            # raw_text 예:
            # 간장,2큰술
            # 대파,1/2개
            # 두부,1모
            #
            # clean_ingredient_name 결과:
            # 간장
            # 대파
            # 두부
            ingredient_name = clean_ingredient_name(raw_text)

            if not ingredient_name:
                continue

            upsert_raw_ingredient(ingredient_name)

            upsert_raw_recipe_ingredient(
                recipe_id=recipe_id,
                ingredient_name=ingredient_name,
                raw_text=raw_text
            )

            saved_count += 1
            recipe_saved_count += 1

        print(
            f"recipe_id={recipe_id}, "
            f"raw_ingredient_count={len(raw_ingredient_lines)}, "
            f"saved_ingredient_count={recipe_saved_count}"
        )

    print(f"done. total_raw={total_count}, saved={saved_count}")


if __name__ == "__main__":
    main()