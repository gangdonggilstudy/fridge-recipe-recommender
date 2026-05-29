from typing import Dict, List


INGREDIENT_ALIAS_MAP = {
    "다진 마늘": "다진마늘",
    "고추가루": "고춧가루",
    "후춧가루": "후추",
    "달걀": "계란",
    "모짜렐라 치즈": "모짜렐라치즈",
    "올리브오일": "올리브유",
}


EXCLUDE_INGREDIENTS = {
    "2개", "3개", "4개", "2대", "2T", "3T", "2스푼", "2큰술", "2모", "스푼",
    "도마", "조리용나이프", "프라이팬", "냄비", "요리스푼", "볼", "채반", "접시",
    "요리젓가락", "국자", "믹싱볼", "뒤집개", "완성그릇", "소스볼", "계량스푼",
    "면기", "요리집게", "완성접시", "플레이팅접시", "숟가락", "조리용스푼",
    "대접", "키친타올",
}


TASTE_INGREDIENT_RULES = {
    "매콤함": {
        "column": "taste_spicy_score",
        "keywords": {
            "고춧가루": 2.0,
            "고추장": 2.0,
            "청양고추": 2.0,
            "홍고추": 1.2,
        },
    },
    "고소함": {
        "column": "taste_savory_score",
        "keywords": {
            "참기름": 2.0,
            "들기름": 2.0,
            "깨": 1.3,
            "통깨": 1.5,
            "깨소금": 1.5,
            "버터": 1.5,
            "모짜렐라치즈": 1.5,
            "우유": 1.0,
        },
    },
    "달콤함": {
        "column": "taste_sweet_score",
        "keywords": {
            "설탕": 2.0,
            "올리고당": 1.8,
            "물엿": 1.8,
            "꿀": 2.0,
            "매실액": 1.2,
            "케찹": 1.0,
        },
    },
    "새콤함": {
        "column": "taste_sour_score",
        "keywords": {
            "식초": 2.0,
            "매실액": 1.3,
            "케찹": 1.2,
        },
    },
    "짭짤함": {
        "column": "taste_salty_score",
        "keywords": {
            "간장": 2.0,
            "국간장": 2.0,
            "진간장": 2.0,
            "소금": 2.0,
            "굴소스": 1.8,
            "고추장": 1.2,
            "참치액": 1.5,
            "된장": 1.8,
            "액젓": 1.8,
            "참치액젓": 1.8,
            "스팸": 1.2,
            "베이컨": 1.2,
            "어묵": 1.0,
        },
    },
    "담백함": {
        "column": "taste_light_score",
        "keywords": {
            "계란": 1.2,
            "두부": 2.0,
            "순두부": 2.0,
            "닭가슴살": 2.0,
            "콩나물": 1.3,
            "팽이버섯": 1.2,
            "감자": 1.0,
            "애호박": 1.0,
            "양배추": 1.0,
            "시금치": 1.0,
            "무": 1.0,
            "오이": 1.0,
            "당근": 1.0,
            "새우": 1.2,
            "밥": 1.0,
        },
    },
}


def normalize_ingredient_name(ingredient_name: str) -> str:
    if not ingredient_name:
        return ""

    name = ingredient_name.strip()
    return INGREDIENT_ALIAS_MAP.get(name, name)


def is_valid_ingredient(ingredient_name: str) -> bool:
    if not ingredient_name:
        return False

    if ingredient_name in EXCLUDE_INGREDIENTS:
        return False

    return True


def calculate_taste_score(ingredients: List[str]) -> Dict:
    result = {
        "taste_spicy_score": 0.0,
        "taste_savory_score": 0.0,
        "taste_sweet_score": 0.0,
        "taste_sour_score": 0.0,
        "taste_salty_score": 0.0,
        "taste_light_score": 0.0,
    }

    matched_by_taste = {}
    normalized_ingredients = []

    for ingredient in ingredients:
        normalized_name = normalize_ingredient_name(ingredient)

        if not is_valid_ingredient(normalized_name):
            continue

        normalized_ingredients.append(normalized_name)

    for taste_name, rule in TASTE_INGREDIENT_RULES.items():
        column = rule["column"]
        matched_keywords = []

        for ingredient in normalized_ingredients:
            keyword_weight = rule["keywords"].get(ingredient)

            if keyword_weight is None:
                continue

            result[column] += keyword_weight
            matched_keywords.append(ingredient)

        if matched_keywords:
            matched_by_taste[taste_name] = matched_keywords

    for key in result.keys():
        result[key] = round(result[key], 2)

    score_to_taste = {
        "매콤함": result["taste_spicy_score"],
        "고소함": result["taste_savory_score"],
        "달콤함": result["taste_sweet_score"],
        "새콤함": result["taste_sour_score"],
        "짭짤함": result["taste_salty_score"],
        "담백함": result["taste_light_score"],
    }

    main_taste = max(score_to_taste.items(), key=lambda x: x[1])

    if main_taste[1] <= 0:
        result["main_taste"] = "미분류"
    else:
        result["main_taste"] = main_taste[0]

    matched_texts = []

    for taste_name, keywords in matched_by_taste.items():
        matched_texts.append(f"{taste_name}={','.join(sorted(set(keywords)))}")

    result["matched_keywords"] = " | ".join(matched_texts)

    return result