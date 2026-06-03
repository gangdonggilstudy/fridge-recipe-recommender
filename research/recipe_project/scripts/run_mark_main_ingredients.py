from collections import defaultdict

from db.repository import (
    find_recipes_for_main_ingredient_marking,
    reset_main_ingredient_flags,
    update_main_ingredient_flag,
)
from pipeline.main_ingredient_extractor import calculate_main_ingredient_scores


def main():
    rows = find_recipes_for_main_ingredient_marking()

    recipe_map = defaultdict(lambda: {
        "title": "",
        "tags": "",
        "ingredients": []
    })

    for row in rows:
        recipe_id = row["recipe_id"]

        recipe_map[recipe_id]["title"] = row.get("title") or ""
        recipe_map[recipe_id]["tags"] = row.get("tags") or ""
        recipe_map[recipe_id]["ingredients"].append(row["ingredient_name"])

    print(f"target recipe count={len(recipe_map)}")

    # 기존 메인 재료 정보 초기화
    reset_main_ingredient_flags()

    updated_count = 0
    main_count = 0

    for recipe_id, recipe in recipe_map.items():
        results = calculate_main_ingredient_scores(
            title=recipe["title"],
            tags=recipe["tags"],
            ingredients=recipe["ingredients"]
        )

        for result in results:
            update_main_ingredient_flag(
                recipe_id=recipe_id,
                ingredient_name=result["ingredient_name"],
                is_main=result["is_main"],
                main_score=result["score"],
                main_match_type=result["match_type"]
            )

            updated_count += 1

            if result["is_main"] == "Y":
                main_count += 1

        main_ingredients = [
            result["ingredient_name"]
            for result in results
            if result["is_main"] == "Y"
        ]

        print(
            f"recipe_id={recipe_id}, "
            f"title={recipe['title']}, "
            f"main_ingredients={main_ingredients}"
        )

    print(f"done. updated_count={updated_count}, main_count={main_count}")


if __name__ == "__main__":
    main()