import re


REMOVE_WORDS = [
    "구매",
    "필수",
    "선택",
]


def clean_ingredient_name(raw_text: str) -> str:
    """
    raw_text 형식:
    - 국수,2인분
    - 대파,1/2개
    - 간장,2큰술

    결과:
    - 국수
    - 대파
    - 간장
    """

    if not raw_text:
        return ""

    ingredient_name = raw_text.split(",", 1)[0].strip()

    ingredient_name = re.sub(r"\([^)]*\)", "", ingredient_name)

    for word in REMOVE_WORDS:
        ingredient_name = ingredient_name.replace(word, "")

    ingredient_name = re.sub(r"\s+", " ", ingredient_name).strip()
    ingredient_name = re.sub(r"[,/]+$", "", ingredient_name).strip()

    return ingredient_name


def get_ingredient_amount(raw_text: str) -> str:
    if not raw_text:
        return ""

    if "," not in raw_text:
        return ""

    return raw_text.split(",", 1)[1].strip()