import math
from typing import Dict, Set


TASTE_COLUMNS = [
    "taste_spicy_score",
    "taste_savory_score",
    "taste_sweet_score",
    "taste_sour_score",
    "taste_salty_score",
    "taste_light_score",
]


def calculate_ingredient_similarity(
        source_ingredients: Set[str],
        target_ingredients: Set[str]
) -> tuple[float, list[str]]:
    """
    재료 유사도 계산.
    Jaccard Similarity 사용.

    공통 재료 개수 / 전체 고유 재료 개수
    """

    if not source_ingredients or not target_ingredients:
        return 0.0, []

    common = source_ingredients.intersection(target_ingredients)
    union = source_ingredients.union(target_ingredients)

    if not union:
        return 0.0, []

    score = len(common) / len(union)

    return round(score, 4), sorted(common)


def calculate_taste_similarity(
        source_recipe: Dict,
        target_recipe: Dict
) -> float:
    """
    맛 유사도 계산.
    코사인 유사도 사용.

    맛 점수 벡터:
    [매콤함, 고소함, 달콤함, 새콤함, 짭짤함, 담백함]
    """

    source_vector = [
        float(source_recipe.get(col) or 0)
        for col in TASTE_COLUMNS
    ]

    target_vector = [
        float(target_recipe.get(col) or 0)
        for col in TASTE_COLUMNS
    ]

    dot = sum(a * b for a, b in zip(source_vector, target_vector))
    source_norm = math.sqrt(sum(a * a for a in source_vector))
    target_norm = math.sqrt(sum(b * b for b in target_vector))

    if source_norm == 0 or target_norm == 0:
        return 0.0

    score = dot / (source_norm * target_norm)

    return round(score, 4)


def calculate_category_similarity(
        source_recipe: Dict,
        target_recipe: Dict
) -> float:
    """
    같은 종류별 카테고리면 1, 아니면 0
    """

    source_category = source_recipe.get("category_type")
    target_category = target_recipe.get("category_type")

    if not source_category or not target_category:
        return 0.0

    return 1.0 if source_category == target_category else 0.0


def calculate_total_similarity(
        ingredient_similarity: float,
        taste_similarity: float,
        category_similarity: float
) -> float:
    """
    최종 유사도 가중합.
    초기 버전 가중치:
    - 재료 50%
    - 맛 30%
    - 카테고리 20%
    """

    total = (
        ingredient_similarity * 0.5
        + taste_similarity * 0.3
        + category_similarity * 0.2
    )

    return round(total, 4)


def build_relation_reason(
        ingredient_similarity: float,
        taste_similarity: float,
        category_similarity: float,
        common_ingredients: list[str],
        source_recipe: Dict,
        target_recipe: Dict
) -> str:
    reasons = []

    if common_ingredients:
        reasons.append(f"공통 재료: {', '.join(common_ingredients[:5])}")

    if source_recipe.get("main_taste") and target_recipe.get("main_taste"):
        if source_recipe.get("main_taste") == target_recipe.get("main_taste"):
            reasons.append(f"대표 맛 동일: {source_recipe.get('main_taste')}")
        else:
            reasons.append(
                f"대표 맛: {source_recipe.get('main_taste')} / {target_recipe.get('main_taste')}"
            )

    if category_similarity == 1.0:
        reasons.append(f"같은 카테고리: {source_recipe.get('category_type')}")

    reasons.append(
        f"재료유사도={ingredient_similarity}, 맛유사도={taste_similarity}, 카테고리유사도={category_similarity}"
    )

    return " | ".join(reasons)