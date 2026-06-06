import argparse
import time
from collections import OrderedDict
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from crawler.crawl_detail import parse_recipe_detail
from crawler.crawl_list import collect_recipe_ids_from_category_page
from db.repository import (
    upsert_raw_recipe,
    count_raw_recipes_by_category,
    exists_raw_recipe,
    append_raw_recipe_collect_type,
    count_raw_recipes_by_collect_type,
)

TYPE_CATEGORY_URLS = OrderedDict({
    "메인반찬": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=56&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "국/탕": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=54&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "찌개": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=55&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "면/만두": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=53&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "밥/죽/떡": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=52&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "양식": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=65&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
})

INGREDIENT_CATEGORY_URLS = OrderedDict({
    "소고기": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=70&cat4=&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "돼지고기": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=71&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "닭고기": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=72&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "채소류": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=28&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "해물류": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=24&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "달걀/유제품": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=50&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "쌀": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=47&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "밀가루": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=32&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "건어물류": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=25&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "버섯류": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=31&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "과일류": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=48&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "콩/견과류": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=27&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "곡류": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=26&cat4=&fct=&order=reco&lastcate=cat3&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
})

METHOD_CATEGORY_URLS = OrderedDict({
    "볶음": "여기에_볶음_URL",
    "끓이기": "여기에_끓이기_URL",
    "부침": "여기에_부침_URL",
    "조림": "여기에_조림_URL",
    "무침": "여기에_무침_URL",
    "비빔": "여기에_비빔_URL",
    "찜": "여기에_찜_URL",
    "절임": "여기에_절임_URL",
    "튀김": "여기에_튀김_URL",
    "삶기": "여기에_삶기_URL",
    "굽기": "여기에_굽기_URL",
    "데치기": "여기에_데치기_URL",
    "회": "여기에_회_URL",
})


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="카테고리별 목표 저장 개수. 기본값 30"
    )

    parser.add_argument(
        "--categories",
        type=str,
        default=None,
        help='수집할 카테고리 목록. 콤마로 구분. 예: --categories "찌개,면/만두"'
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="요청 간 대기 시간. 기본값 1초"
    )

    parser.add_argument(
        "--max-page",
        type=int,
        default=50,
        help="카테고리별 최대 조회 페이지. 기본값 50"
    )

    parser.add_argument(
        "--collect-kind",
        type=str,
        default="category",
        choices=["category", "ingredient", "method", "all"],
        help="수집 기준. category, ingredient, method, all 중 선택"
    )

    parser.add_argument(
        "--target-year",
        type=int,
        default=None,
        help="해당 연도에 등록된 레시피만 수집. 예: --target-year 2025"
    )

    return parser.parse_args()

def to_date_order_url(url: str) -> str:
    """
    만개의레시피 목록 URL을 최신순 URL로 변경한다.

    기존:
    order=reco
    lastcate=cat4

    변경:
    order=date
    lastcate=order
    """

    parsed_url = urlparse(url)
    query_dict = dict(parse_qsl(parsed_url.query, keep_blank_values=True))

    query_dict["order"] = "date"
    query_dict["lastcate"] = "order"

    new_query = urlencode(query_dict)

    return urlunparse(
        parsed_url._replace(query=new_query)
    )

def get_recipe_year(recipe: dict) -> int | None:
    """
    parse_recipe_detail() 결과에서 등록연도 추출.
    실제 key명이 다를 수 있으므로 후보 key를 여러 개 둔다.
    """

    date_key_candidates = [
        "reg_date",
        "created_date",
        "created_at",
        "write_date",
        "registered_at",
        "date",
    ]

    for key in date_key_candidates:
        value = recipe.get(key)

        if not value:
            continue

        value = str(value).strip()

        # 예: 2025-01-03, 2025.01.03, 2025년 1월 3일 모두 대응
        if len(value) >= 4 and value[:4].isdigit():
            return int(value[:4])

    return None

def get_first_valid_recipe_year_from_page(
        collect_url: str,
        page: int,
        from_end: bool = False
) -> tuple[int | None, str | None, str | None]:
    """
    특정 목록 페이지에서 첫 번째 또는 마지막 레시피의 등록연도를 가져온다.

    from_end=False: 페이지 앞쪽 레시피부터 확인
    from_end=True : 페이지 뒤쪽 레시피부터 확인

    return:
    (recipe_year, reg_date, recipe_id)
    """

    recipe_ids = collect_recipe_ids_from_category_page(
        category_url=collect_url,
        page=page
    )

    if not recipe_ids:
        return None, None, None

    target_ids = list(reversed(recipe_ids)) if from_end else recipe_ids

    # 혹시 일부 상세 파싱이 실패할 수 있으므로 앞/뒤에서 최대 5개까지 확인
    for recipe_id in target_ids[:5]:
        try:
            recipe = parse_recipe_detail(recipe_id)
            recipe_year = get_recipe_year(recipe)

            if recipe_year is not None:
                return recipe_year, recipe.get("reg_date"), recipe_id

        except Exception as e:
            print(
                f"[WARN] page year check failed. "
                f"page={page}, recipe_id={recipe_id}, error={e}"
            )
            continue

    return None, None, None


def get_page_year_range(
        collect_url: str,
        page: int
) -> tuple[int | None, int | None]:
    """
    최신순 목록 페이지의 연도 범위를 확인한다.

    newest_year: 페이지 앞쪽 레시피 연도
    oldest_year: 페이지 뒤쪽 레시피 연도
    """

    newest_year, newest_reg_date, newest_recipe_id = get_first_valid_recipe_year_from_page(
        collect_url=collect_url,
        page=page,
        from_end=False
    )

    oldest_year, oldest_reg_date, oldest_recipe_id = get_first_valid_recipe_year_from_page(
        collect_url=collect_url,
        page=page,
        from_end=True
    )

    print(
        f"[PAGE CHECK] page={page}, "
        f"newest_year={newest_year}, newest_reg_date={newest_reg_date}, newest_recipe_id={newest_recipe_id}, "
        f"oldest_year={oldest_year}, oldest_reg_date={oldest_reg_date}, oldest_recipe_id={oldest_recipe_id}"
    )

    return newest_year, oldest_year


def find_target_year_start_page(
        collect_url: str,
        target_year: int,
        max_page: int,
        sleep_seconds: float
) -> int | None:
    """
    최신순 order=date 기준으로 target_year가 처음 등장하는 페이지를 이진 탐색한다.

    예:
    target_year=2025일 때,
    2026 페이지들은 건너뛰고
    2025가 처음 나오는 페이지를 찾는다.
    """

    left = 1
    right = max_page
    candidate_page = None

    while left <= right:
        mid = (left + right) // 2

        try:
            newest_year, oldest_year = get_page_year_range(
                collect_url=collect_url,
                page=mid
            )

            time.sleep(sleep_seconds)

        except Exception as e:
            print(f"[WARN] target year page check failed. page={mid}, error={e}")
            right = mid - 1
            continue

        if newest_year is None or oldest_year is None:
            print(f"[WARN] cannot detect year at page={mid}")
            right = mid - 1
            continue

        # 최신순 기준:
        # 페이지 전체가 target_year보다 최신이면 더 뒤 페이지로 이동
        # 예: target=2025, page 전체가 2026
        if oldest_year > target_year:
            left = mid + 1
            continue

        # 페이지 전체가 target_year보다 과거이면 더 앞 페이지로 이동
        # 예: target=2025, page 전체가 2024
        if newest_year < target_year:
            right = mid - 1
            continue

        # 이 페이지 안에 target_year가 포함되어 있음
        candidate_page = mid

        # 더 앞쪽 페이지에도 target_year가 있을 수 있으므로 앞쪽을 계속 탐색
        right = mid - 1

    return candidate_page

def is_target_year_recipe(recipe: dict, target_year: int | None) -> bool:
    if target_year is None:
        return True

    recipe_year = get_recipe_year(recipe)

    if recipe_year is None:
        return False

    return recipe_year == target_year

def parse_target_categories(categories_arg: str | None) -> OrderedDict:
    if not categories_arg:
        return TYPE_CATEGORY_URLS

    requested_categories = [
        category.strip()
        for category in categories_arg.split(",")
        if category.strip()
    ]

    if not requested_categories:
        return TYPE_CATEGORY_URLS

    invalid_categories = [
        category
        for category in requested_categories
        if category not in TYPE_CATEGORY_URLS
    ]

    if invalid_categories:
        raise ValueError(
            f"Unknown categories: {invalid_categories}. "
            f"Available categories: {list(TYPE_CATEGORY_URLS.keys())}"
        )

    return OrderedDict(
        (category, TYPE_CATEGORY_URLS[category])
        for category in requested_categories
    )

def get_collect_targets(collect_kind: str) -> OrderedDict:
    if collect_kind == "category":
        return TYPE_CATEGORY_URLS

    if collect_kind == "ingredient":
        return INGREDIENT_CATEGORY_URLS

    if collect_kind == "method":
        return METHOD_CATEGORY_URLS

    if collect_kind == "all":
        targets = OrderedDict()

        for name, url in TYPE_CATEGORY_URLS.items():
            targets[f"category::{name}"] = url

        for name, url in INGREDIENT_CATEGORY_URLS.items():
            targets[f"ingredient::{name}"] = url

        for name, url in METHOD_CATEGORY_URLS.items():
            targets[f"method::{name}"] = url

        return targets

    raise ValueError(f"Unknown collect_kind: {collect_kind}")

def parse_collect_key(raw_key: str, default_collect_kind: str) -> tuple[str, str]:
    if "::" not in raw_key:
        return default_collect_kind, raw_key

    collect_kind, collect_name = raw_key.split("::", 1)
    return collect_kind, collect_name

def crawl_category_until_limit(
        category_name: str,
        category_url: str,
        limit: int,
        sleep_seconds: float,
        max_page: int
):
    current_count = count_raw_recipes_by_category(category_name)

    print(f"\n=== Start category: {category_name} ===")
    print(f"[{category_name}] current db count={current_count}, target={limit}")

    if current_count >= limit:
        print(f"[{category_name}] already reached target. skip.")
        return

    seen_recipe_ids = set()
    page = 1
    stop_group = False

    while current_count < limit and page <= max_page and not stop_group:
        try:
            recipe_ids = collect_recipe_ids_from_category_page(
                category_url=category_url,
                page=page
            )

        except Exception as e:
            print(f"[ERROR] list page failed. category={category_name}, page={page}, error={e}")
            page += 1
            time.sleep(sleep_seconds)
            continue

        if not recipe_ids:
            print(f"[{category_name}] no recipe ids. stop. page={page}")
            break

        for recipe_id in recipe_ids:
            if current_count >= limit:
                break

            if recipe_id in seen_recipe_ids:
                continue

            seen_recipe_ids.add(recipe_id)

            # raw_recipe는 recipe_id가 PK이므로 전체 기준 중복이면 skip
            if exists_raw_recipe(recipe_id):
                print(f"[{category_name}] skip already exists recipe_id={recipe_id}")
                continue

            try:
                recipe = parse_recipe_detail(recipe_id)

                if not is_target_year_recipe(recipe, 2025):
                    print("2025년 데이터 아님. skip")
                    continue

                recipe["category_type"] = category_name

                upsert_raw_recipe(recipe)

                current_count += 1

                print(
                    f"[{category_name}] saved "
                    f"{current_count}/{limit}, "
                    f"recipe_id={recipe_id}, title={recipe['title']}"
                )

                time.sleep(sleep_seconds)

            except Exception as e:
                print(f"[WARN] recipe failed. category={category_name}, recipe_id={recipe_id}, error={e}")
                time.sleep(sleep_seconds)
                continue

        page += 1

    final_count = count_raw_recipes_by_category(category_name)

    print(f"[{category_name}] finished. final db count={final_count}, target={limit}")

    if final_count < limit:
        print(f"[WARN] {category_name} did not reach target. final={final_count}, target={limit}")

def crawl_group_until_limit(
        collect_kind: str,
        collect_name: str,
        collect_url: str,
        limit: int,
        sleep_seconds: float,
        max_page: int,
        target_year: int | None = None
):
    current_count = count_raw_recipes_by_collect_type(
        collect_kind=collect_kind,
        collect_value=collect_name
    )

    print(f"\n=== Start {collect_kind}: {collect_name} ===")
    print(f"[{collect_name}] current db count={current_count}, target={limit}")
    print(f"[{collect_name}] url={collect_url}")

    if current_count >= limit:
        print(f"[{collect_name}] already reached target. skip.")
        return

    seen_recipe_ids = set()

    if target_year is not None:
        start_page = find_target_year_start_page(
            collect_url=collect_url,
            target_year=target_year,
            max_page=max_page,
            sleep_seconds=sleep_seconds
        )

        if start_page is None:
            print(
                f"[{collect_name}] target year page not found. "
                f"target_year={target_year}. skip group."
            )
            return

        page = start_page

        print(
            f"[{collect_name}] target year start page found. "
            f"target_year={target_year}, start_page={start_page}"
        )

    else:
        page = 1

    stop_group = False

    while current_count < limit and page <= max_page and not stop_group:
        try:
            recipe_ids = collect_recipe_ids_from_category_page(
                category_url=collect_url,
                page=page
            )

        except Exception as e:
            print(
                f"[ERROR] list page failed. "
                f"kind={collect_kind}, name={collect_name}, page={page}, error={e}"
            )
            page += 1
            time.sleep(sleep_seconds)
            continue

        if not recipe_ids:
            print(f"[{collect_name}] no recipe ids. stop. page={page}")
            break

        print(
            f"[{collect_name}] page={page}, "
            f"recipe_id_count={len(recipe_ids)}"
        )

        for recipe_id in recipe_ids:
            if current_count >= limit:
                break

            if recipe_id in seen_recipe_ids:
                continue

            seen_recipe_ids.add(recipe_id)

            try:
                recipe = parse_recipe_detail(recipe_id)

                recipe_year = get_recipe_year(recipe)

                if target_year is not None:
                    if recipe_year is None:
                        print(
                            f"[{collect_name}] skip unknown year. "
                            f"target_year={target_year}, "
                            f"reg_date={recipe.get('reg_date')}, "
                            f"recipe_id={recipe_id}"
                        )
                        time.sleep(sleep_seconds)
                        continue

                    if recipe_year > target_year:
                        print(
                            f"[{collect_name}] skip newer recipe. "
                            f"target_year={target_year}, "
                            f"recipe_year={recipe_year}, "
                            f"reg_date={recipe.get('reg_date')}, "
                            f"recipe_id={recipe_id}"
                        )
                        time.sleep(sleep_seconds)
                        continue

                    if recipe_year < target_year:
                        print(
                            f"[{collect_name}] older recipe found. stop this group. "
                            f"target_year={target_year}, "
                            f"recipe_year={recipe_year}, "
                            f"reg_date={recipe.get('reg_date')}, "
                            f"recipe_id={recipe_id}"
                        )
                        stop_group = True
                        break

                already_exists = exists_raw_recipe(recipe_id)

                if not already_exists:
                    if collect_kind == "category":
                        recipe["category_type"] = collect_name

                    upsert_raw_recipe(recipe)

                    print(
                        f"[{collect_name}] saved raw_recipe, "
                        f"recipe_id={recipe_id}, "
                        f"reg_date={recipe.get('reg_date')}, "
                        f"title={recipe.get('title')}"
                    )
                else:
                    print(
                        f"[{collect_name}] already exists recipe_id={recipe_id}. "
                        f"append type only."
                    )

                append_raw_recipe_collect_type(
                    recipe_id=recipe_id,
                    category_type=collect_name if collect_kind == "category" else None,
                    ingredient_type=collect_name if collect_kind == "ingredient" else None,
                    method_type=collect_name if collect_kind == "method" else None,
                    situation_type=collect_name if collect_kind == "situation" else None,
                )

                new_count = count_raw_recipes_by_collect_type(
                    collect_kind=collect_kind,
                    collect_value=collect_name
                )

                if new_count > current_count:
                    current_count = new_count

                    print(
                        f"[{collect_name}] collected "
                        f"{current_count}/{limit}, "
                        f"recipe_id={recipe_id}"
                    )
                else:
                    print(
                        f"[{collect_name}] already mapped. "
                        f"count not increased. "
                        f"current={current_count}, "
                        f"recipe_id={recipe_id}"
                    )

                time.sleep(sleep_seconds)

            except Exception as e:
                print(
                    f"[WARN] recipe failed. "
                    f"kind={collect_kind}, "
                    f"name={collect_name}, "
                    f"recipe_id={recipe_id}, "
                    f"error={e}"
                )
                time.sleep(sleep_seconds)
                continue

        if stop_group:
            break

        page += 1

    final_count = count_raw_recipes_by_collect_type(
        collect_kind=collect_kind,
        collect_value=collect_name
    )

    print(f"[{collect_name}] finished. final db count={final_count}, target={limit}")

    if final_count < limit:
        print(
            f"[WARN] {collect_name} did not reach target. "
            f"final={final_count}, target={limit}"
        )

# def main():
#     args = parse_args()

#     target_categories = parse_target_categories(args.categories)

#     print("target categories:", list(target_categories.keys()))
#     print("limit per category:", args.limit)
#     print("sleep seconds:", args.sleep)
#     print("max page:", args.max_page)

#     for category_name, category_url in target_categories.items():
#         crawl_category_until_limit(
#             category_name=category_name,
#             category_url=category_url,
#             limit=args.limit,
#             sleep_seconds=args.sleep,
#             max_page=args.max_page
#         )


def main():
    args = parse_args()

    target_groups = get_collect_targets(args.collect_kind)

    # target_year가 있으면 최신순 URL로 변경한다.
    # order=reco 대신 order=date로 조회해야 연도 기준으로 빠르게 멈출 수 있다.
    if args.target_year is not None:
        target_groups = OrderedDict(
            (name, to_date_order_url(url))
            for name, url in target_groups.items()
        )

    print("collect kind:", args.collect_kind)
    print("target groups:", list(target_groups.keys()))
    print("limit per group:", args.limit)
    print("sleep seconds:", args.sleep)
    print("max page:", args.max_page)
    print("target year:", args.target_year)

    for raw_key, collect_url in target_groups.items():
        collect_kind, collect_name = parse_collect_key(
            raw_key=raw_key,
            default_collect_kind=args.collect_kind
        )

        crawl_group_until_limit(
            collect_kind=collect_kind,
            collect_name=collect_name,
            collect_url=collect_url,
            limit=args.limit,
            sleep_seconds=args.sleep,
            max_page=args.max_page,
            target_year=args.target_year
        )

if __name__ == "__main__":
    main()