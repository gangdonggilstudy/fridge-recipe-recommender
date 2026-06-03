from collections import defaultdict

from db.repository import (
    find_recipes_for_similarity,
    find_all_recipe_ingredients,
    clear_recipe_similarity,
    upsert_recipe_similarity,
)
from pipeline.similarity_calculator import (
    calculate_ingredient_similarity,
    calculate_taste_similarity,
    calculate_category_similarity,
    calculate_total_similarity,
    build_relation_reason,
)


MODEL_VERSION = "v1"


def build_ingredient_map() -> dict[str, set[str]]:
    rows = find_all_recipe_ingredients()

    ingredient_map = defaultdict(set)

    for row in rows:
        recipe_id = row["recipe_id"]
        ingredient_name = row["ingredient_name"]

        if ingredient_name:
            ingredient_map[recipe_id].add(ingredient_name)

    return dict(ingredient_map)


def main():
    recipes = find_recipes_for_similarity()
    ingredient_map = build_ingredient_map()

    print(f"target recipe count={len(recipes)}")

    # 같은 model_version 결과는 다시 계산하기 위해 삭제
    clear_recipe_similarity(MODEL_VERSION)

    saved_count = 0

    for i, source_recipe in enumerate(recipes):
        source_recipe_id = source_recipe["recipe_id"]
        source_ingredients = ingredient_map.get(source_recipe_id, set())

        # 핵심 변경:
        # j를 i + 1부터 시작해서 A-B만 저장하고 B-A는 저장하지 않음
        for j in range(i + 1, len(recipes)):
            target_recipe = recipes[j]
            target_recipe_id = target_recipe["recipe_id"]
            target_ingredients = ingredient_map.get(target_recipe_id, set())

            ingredient_similarity, common_ingredients = calculate_ingredient_similarity(
                source_ingredients=source_ingredients,
                target_ingredients=target_ingredients
            )

            taste_similarity = calculate_taste_similarity(
                source_recipe=source_recipe,
                target_recipe=target_recipe
            )

            category_similarity = calculate_category_similarity(
                source_recipe=source_recipe,
                target_recipe=target_recipe
            )

            total_similarity = calculate_total_similarity(
                ingredient_similarity=ingredient_similarity,
                taste_similarity=taste_similarity,
                category_similarity=category_similarity
            )

            # 너무 낮은 유사도는 저장하지 않음
            if total_similarity <= 0:
                continue

            relation_reason = build_relation_reason(
                ingredient_similarity=ingredient_similarity,
                taste_similarity=taste_similarity,
                category_similarity=category_similarity,
                common_ingredients=common_ingredients,
                source_recipe=source_recipe,
                target_recipe=target_recipe
            )

            upsert_recipe_similarity({
                "source_recipe_id": source_recipe_id,
                "target_recipe_id": target_recipe_id,
                "source_title": source_recipe.get("title"),
                "target_title": target_recipe.get("title"),
                "total_similarity": total_similarity,
                "ingredient_similarity": ingredient_similarity,
                "taste_similarity": taste_similarity,
                "category_similarity": category_similarity,
                "common_ingredients": ",".join(common_ingredients),
                "source_main_taste": source_recipe.get("main_taste"),
                "target_main_taste": target_recipe.get("main_taste"),
                "relation_reason": relation_reason,
                "model_version": MODEL_VERSION,
            })

            saved_count += 1

        print(f"processed {i + 1}/{len(recipes)}, recipe_id={source_recipe_id}")

    print(f"done. saved_count={saved_count}")


if __name__ == "__main__":
    main()