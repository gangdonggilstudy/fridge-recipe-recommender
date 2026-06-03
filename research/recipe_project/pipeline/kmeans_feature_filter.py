import re


EXCLUDE_KMEANS_INGREDIENTS = {
    # 기본 재료
    "물",

    # 기본 양념/조미료
    "소금", "설탕", "간장", "국간장", "진간장", "집간장",
    "참기름", "들기름", "식용유", "올리브유", "올리브오일",
    "고춧가루", "고추가루", "고추장", "된장",
    "후추", "후춧가루", "맛술", "올리고당", "물엿", "식초",
    "굴소스", "참치액", "액젓", "통깨", "깨", "깨소금",

    # 향신/부재료
    "다진마늘", "다진 마늘", "마늘", "대파", "다진파",
    "양파", "청양고추", "홍고추",

    # 도구
    "도마", "조리용나이프", "냄비", "프라이팬", "볼", "접시",
    "국자", "채반", "요리스푼", "요리젓가락", "뒤집개",
    "믹싱볼", "완성그릇", "소스볼", "계량스푼", "면기",
    "요리집게", "완성접시", "플레이팅접시", "숟가락",
    "조리용스푼", "대접", "키친타올",

    # 베이킹/가공 보조재료는 필요에 따라 제외
    "박력분", "튀김가루", "베이킹파우더",
}


def is_valid_kmeans_ingredient(ingredient_name: str) -> bool:
    if not ingredient_name:
        return False

    name = ingredient_name.strip()

    if name in EXCLUDE_KMEANS_INGREDIENTS:
        return False

    # 숫자가 포함된 값 제외: 2개, 2T, 1/2개 등
    if re.search(r"\d", name):
        return False

    # 너무 짧은 값은 제외
    if len(name) <= 1:
        return False

    return True