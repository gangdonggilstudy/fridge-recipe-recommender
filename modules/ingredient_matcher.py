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

    # ① 정확 매치: 레시피 필요 재료 중 내가 그대로 가진 것.
    required = set(recipe_ingredients)
    matched = owned & required

    # ② 카테고리 부분 점수: 정확히는 없어도 같은 종류(예: 소고기↔돼지고기=육류)를
    #    가졌으면 category_weight 만큼 부분 인정. category_weight=0 이면 이 단계 건너뜀.
    partial = 0.0
    covered = 0
    if category_weight > 0:
        # 아직 안 쓴 보유 재료들을 카테고리별 개수로 집계.
        # 한 보유 재료가 같은 카테고리 여러 슬롯 무제한 대체 못 함.
        owned_categories = Counter(
            c for o in (owned - matched) if (c := get_category(o)) is not None
        )
        # 아직 못 채운 필요 재료를 돌며, 같은 카테고리 보유분이 남았으면 1개 소진.
        for r in (required - matched):
            category = get_category(r)
            if category is not None and owned_categories[category] > 0:
                partial += category_weight
                covered += 1
                owned_categories[category] -= 1  # 소진 → 다음 슬롯엔 재사용 불가

    # ③ 결측 페널티: 카테고리로 메운 수(covered)를 뺀 '진짜 부족분'으로 페널티 결정.
    missing = len(required) - len(matched)
    effective_missing = max(0, missing - covered)
    # base = 채운 비율(정확 + 부분) / 필요 재료 수.  ex) (2 + 0.3) / 4 = 0.575
    base = (len(matched) + partial) / len(required)
    penalty = MISSING_PENALTY.get(effective_missing, 0.0)  # 3개 이상 부족 → 0
    # ④ 최종: base × penalty, 1.0 초과는 잘라냄.  ex) 0.575 × 0.7 = 0.403
    return min(1.0, base * penalty)


def missing_ingredients(owned: set[str], recipe_ingredients: list[str]) -> list[str]:
    return [i for i in recipe_ingredients if i not in owned]


def _expiry_score(item: dict) -> float:
    """오늘 만료=1.0, 7일 후=0.0, 만료/7일+=0.0."""
    exp = item.get("expiry_date")
    if exp is None:
        return 0.0
    days = (exp - date.today()).days
    # 이미 상했거나(음수) 아직 여유 있으면(7일 초과) 소모 우선순위 없음 → 0.
    if days < 0 or days > EXPIRY_WINDOW_DAYS:
        return 0.0
    # 남은 일수가 적을수록 1.0 에 가깝게 선형 증가.  ex) 5일 남음 → 1-5/7 = 0.286
    return 1.0 - (days / EXPIRY_WINDOW_DAYS)


def consumption_score(owned_items: list[dict], recipe_ingredients: list[str]) -> float:
    """분모는 레시피 전체 재료 수 — 임박 재료 집중도 반영."""
    if not recipe_ingredients:
        return 0.0
    # 레시피에 실제로 쓰이는 내 재료만 골라 임박도를 매김.
    ingredient_set = set(recipe_ingredients)
    scores = [_expiry_score(i) for i in owned_items if i.get("name") in ingredient_set]
    if not scores:
        return 0.0
    # 분모를 '매치된 재료 수'가 아닌 '레시피 전체 재료 수'로 나눠, 임박 재료를
    # 쓰면서도 재료 수가 적은(집중도 높은) 레시피가 더 유리하도록 설계.
    return sum(scores) / len(recipe_ingredients)
