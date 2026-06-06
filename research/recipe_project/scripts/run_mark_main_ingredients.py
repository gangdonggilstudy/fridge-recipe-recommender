from collections import defaultdict

from db.repository import (
    find_recipes_for_main_ingredient_marking,
    reset_main_ingredient_flags,
    update_main_ingredient_flag,
)
from pipeline.main_ingredient_extractor import calculate_main_ingredient_scores


def to_is_main_value(is_main: str) -> int:
    """
    calculate_main_ingredient_scores() 결과의 Y/N 값을
    DB 저장용 1/0 값으로 명확히 변환한다.
    """
    return 1 if is_main == "Y" else 0


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
            is_main_value = to_is_main_value(result["is_main"])

            # 채반 디버그용
            if "채반" in result["ingredient_name"]:
                print(
                    "[DEBUG 채반]",
                    f"recipe_id={recipe_id}",
                    f"ingredient_name={repr(result['ingredient_name'])}",
                    f"normalized_name={repr(result.get('normalized_name'))}",
                    f"result_is_main={repr(result['is_main'])}",
                    f"is_main_value={is_main_value}",
                    f"score={result['score']}",
                    f"match_type={result['match_type']}",
                )

            update_main_ingredient_flag(
                recipe_id=recipe_id,
                ingredient_name=result["ingredient_name"],
                is_main=is_main_value,
                main_score=result["score"],
                main_match_type=result["match_type"]
            )

            updated_count += 1

            if is_main_value == 1:
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