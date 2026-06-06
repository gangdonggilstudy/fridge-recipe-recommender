import re
from typing import List, Dict


EXCLUDE_MAIN_INGREDIENTS = {
    # 기본 양념/조미료
    "소금", "굵은소금", "고운소금 마지막 간 보며 넣기", "설탕", "물", "간장", "국간장", "진간장", "집간장",
    "참기름", "들기름", "식용유", "올리브유", "올리브오일",
    "후추", "후춧가루", "고춧가루", "고추가루", "고추장", "된장",
    "맛술", "올리고당", "물엿", "식초", "굴소스", "참치액", "액젓",

    # 향신/부재료
    "다진마늘", "다진 마늘", "마늘", "대파", "다진파", "양파",
    "청양고추", "홍고추",

    # 고명/기본 재료
    "통깨", "깨", "깨소금",

    # 도구/수량/단위가 잘못 들어온 경우
    "도마", "냄비", "프라이팬", "볼", "접시", "국자", "채반", "국그릇", "계량컵",
    "조리용나이프", "요리스푼", "요리젓가락", "뒤집개",
    "2개", "3개", "4개", "2T", "3T", "2큰술", "2스푼"
}


INGREDIENT_ALIAS_MAP = {
    "다진 마늘": "다진마늘",
    "고추가루": "고춧가루",
    "후춧가루": "후추",
    "달걀": "계란",
    "모짜렐라 치즈": "모짜렐라치즈",
    "올리브오일": "올리브유",
    "애느타리버섯": "애느타리",
}


def normalize_text(text: str | None) -> str:
    if not text:
        return ""

    text = re.sub(r"\s+", "", text)
    return text.strip()


def normalize_ingredient_name(ingredient_name: str | None) -> str:
    if not ingredient_name:
        return ""

    name = ingredient_name.strip()
    return INGREDIENT_ALIAS_MAP.get(name, name)


def is_excluded_main_ingredient(ingredient_name: str) -> bool:
    if not ingredient_name:
        return True

    normalized_name = normalize_text(ingredient_name)

    normalized_excludes = {
        normalize_text(item)
        for item in EXCLUDE_MAIN_INGREDIENTS
    }

    if normalized_name in normalized_excludes:
        return True

    # 포함형 도구 제외
    non_food_keywords = [
        "채반",
        "도마",
        "냄비",
        "프라이팬",
        "후라이팬",
        "볼",
        "접시",
        "국그릇",
        "계량컵",
        "국자",
        "체망",
        "체",
        "면보",
        "키친타월",
        "종이호일",
        "랩",
        "위생봉투",
    ]

    if any(keyword in normalized_name for keyword in non_food_keywords):
        return True

    # 숫자가 들어간 값은 재료가 아니라 수량/단위로 보고 제외
    if re.search(r"\d", normalized_name):
        return True

    return False


def calculate_main_ingredient_scores(
        title: str,
        tags: str | None,
        ingredients: List[str]
) -> List[Dict]:
    """
    레시피별 재료에 대해 메인 재료 점수를 계산한다.

    기준:
    1. 기본 양념/도구/수량값은 제외
    2. 제목에 재료명이 포함되면 강한 메인 후보
    3. 태그에 재료명이 포함되면 메인 후보
    4. 제목/태그 매칭이 없으면 제외 후 남은 재료 중 앞쪽 1~2개를 fallback 후보로 사용
    """

    normalized_title = normalize_text(title)
    normalized_tags = normalize_text(tags)

    results = []

    valid_candidates = []

    for index, ingredient in enumerate(ingredients):
        normalized_name = normalize_ingredient_name(ingredient)

        score = 0.0
        match_type = "CANDIDATE"
        is_excluded = is_excluded_main_ingredient(normalized_name)

        if is_excluded:
            results.append({
                "ingredient_name": ingredient,
                "normalized_name": normalized_name,
                "score": 0.0,
                "match_type": "EXCLUDED",
                "is_main": "N",
                "index": index,
            })
            continue

        # 후보 기본 점수
        score += 1.0

        # 재료 순서 보조 점수: 앞쪽 재료일수록 약간 가산
        if index == 0:
            score += 0.5
        elif index == 1:
            score += 0.3

        normalized_ingredient_text = normalize_text(normalized_name)

        # 1순위: 제목 매칭
        if normalized_ingredient_text and normalized_ingredient_text in normalized_title:
            score += 5.0
            match_type = "TITLE_MATCH"

        # 2순위: 태그 매칭
        elif normalized_ingredient_text and normalized_ingredient_text in normalized_tags:
            score += 4.0
            match_type = "TAG_MATCH"

        valid_candidates.append({
            "ingredient_name": ingredient,
            "normalized_name": normalized_name,
            "score": score,
            "match_type": match_type,
            "is_main": "N",
            "index": index,
        })

    # 제목/태그 매칭 후보가 있으면 그 후보만 Y
    strong_candidates = [
        item for item in valid_candidates
        if item["match_type"] in ("TITLE_MATCH", "TAG_MATCH")
    ]

    if strong_candidates:
        max_score = max(item["score"] for item in strong_candidates)

        for item in valid_candidates:
            if item["score"] == max_score and item["match_type"] in ("TITLE_MATCH", "TAG_MATCH"):
                item["is_main"] = "Y"

    else:
        # 제목/태그 매칭이 없으면 fallback:
        # 제외 후 남은 재료 중 점수 높은 상위 1개만 메인 처리
        if valid_candidates:
            sorted_candidates = sorted(
                valid_candidates,
                key=lambda x: (x["score"], -x["index"]),
                reverse=True
            )

            sorted_candidates[0]["is_main"] = "Y"
            sorted_candidates[0]["match_type"] = "FALLBACK_TOP_INGREDIENT"

    results.extend(valid_candidates)

    return results