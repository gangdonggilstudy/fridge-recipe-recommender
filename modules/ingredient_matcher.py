"""재료 일치도·소모 우선순위 점수 — 순수 함수."""

from collections import Counter
from datetime import date

from .normalize import get_category

# 0=1.0, 1=0.7, 2=0.4, 3+=0. 1~2 살려두는 이유: 탐색성.
MISSING_PENALTY: dict[int, float] = {0: 1.0, 1: 0.7, 2: 0.4}

# 일주일 장보기 주기 가정.
EXPIRY_WINDOW_DAYS = 7


def ingredient_score(
    owned: set[str],
    recipe_ingredients: list[str],
    category_weight: float = 0.0,
) -> float:
    """반환 [0, 1]. `category_weight > 0` 시 부족 재료의 동일 카테고리 부분 점수."""
    if not recipe_ingredients:
        return 0.0

    required = set(recipe_ingredients)
    matched = owned & required

    partial = 0.0
    covered = 0
    if category_weight > 0:
        # 한 보유 재료가 같은 카테고리 여러 슬롯 무제한 대체 못 함.
        owned_categories = Counter(
            c for o in (owned - matched) if (c := get_category(o)) is not None
        )
        for r in (required - matched):
            category = get_category(r)
            if category is not None and owned_categories[category] > 0:
                partial += category_weight
                covered += 1
                owned_categories[category] -= 1

    missing = len(required) - len(matched)
    effective_missing = max(0, missing - covered)
    base = (len(matched) + partial) / len(required)
    penalty = MISSING_PENALTY.get(effective_missing, 0.0)
    return min(1.0, base * penalty)


def missing_ingredients(owned: set[str], recipe_ingredients: list[str]) -> list[str]:
    return [i for i in recipe_ingredients if i not in owned]


def _expiry_score(item: dict) -> float:
    """오늘 만료=1.0, 7일 후=0.0, 만료/7일+=0.0."""
    exp = item.get("expiry_date")
    if exp is None:
        return 0.0
    days = (exp - date.today()).days
    if days < 0 or days > EXPIRY_WINDOW_DAYS:
        return 0.0
    return 1.0 - (days / EXPIRY_WINDOW_DAYS)


def consumption_score(owned_items: list[dict], recipe_ingredients: list[str]) -> float:
    """분모는 레시피 전체 재료 수 — 임박 재료 집중도 반영."""
    if not recipe_ingredients:
        return 0.0
    ingredient_set = set(recipe_ingredients)
    scores = [_expiry_score(i) for i in owned_items if i.get("name") in ingredient_set]
    if not scores:
        return 0.0
    return sum(scores) / len(recipe_ingredients)
