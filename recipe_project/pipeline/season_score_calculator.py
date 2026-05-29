from typing import Dict, Set


SEASON_SCORE_COLUMNS = {
    "봄": "spring_score",
    "여름": "summer_score",
    "가을": "autumn_score",
    "겨울": "winter_score",
}


def calculate_recipe_season_score(
        recipe_ingredients: Set[str],
        season_ingredient_map: Dict[str, Set[str]]
) -> dict:
    """
    recipe_ingredients:
        특정 레시피에 들어간 재료 set

    season_ingredient_map:
        {
            "봄": {"냉이", "달래", "두릅"},
            "여름": {"오이", "가지", "토마토"},
            ...
        }

    점수 방식:
        해당 계절 대표 재료와 겹친 개수 / 해당 계절 대표 재료 개수
    """

    result = {
        "spring_score": 0.0,
        "summer_score": 0.0,
        "autumn_score": 0.0,
        "winter_score": 0.0,
        "main_season": "미분류",
        "matched_ingredients": "",
    }

    matched_texts = []
    season_scores = {}

    for season_type, season_ingredients in season_ingredient_map.items():
        column_name = SEASON_SCORE_COLUMNS.get(season_type)

        if not column_name:
            continue

        if not season_ingredients:
            score = 0.0
            matched = set()
        else:
            matched = recipe_ingredients.intersection(season_ingredients)
            score = len(matched) / len(season_ingredients)

        score = round(score, 4)

        result[column_name] = score
        season_scores[season_type] = score

        if matched:
            matched_texts.append(
                f"{season_type}={','.join(sorted(matched))}"
            )

    if season_scores:
        main_season, max_score = max(
            season_scores.items(),
            key=lambda x: x[1]
        )

        if max_score > 0:
            result["main_season"] = main_season

    result["matched_ingredients"] = " | ".join(matched_texts)

    return result