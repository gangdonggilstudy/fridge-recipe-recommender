import argparse
import time
from collections import OrderedDict

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

    return parser.parse_args()


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

    while current_count < limit and page <= max_page:
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
        max_page: int
):
    current_count = count_raw_recipes_by_collect_type(
        collect_kind=collect_kind,
        collect_value=collect_name
    )

    print(f"\n=== Start {collect_kind}: {collect_name} ===")
    print(f"[{collect_name}] current db count={current_count}, target={limit}")

    if current_count >= limit:
        print(f"[{collect_name}] already reached target. skip.")
        return

    seen_recipe_ids = set()
    page = 1

    while current_count < limit and page <= max_page:
        try:
            recipe_ids = collect_recipe_ids_from_category_page(
                category_url=collect_url,
                page=page
            )

        except Exception as e:
            print(f"[ERROR] list page failed. kind={collect_kind}, name={collect_name}, page={page}, error={e}")
            page += 1
            time.sleep(sleep_seconds)
            continue

        if not recipe_ids:
            print(f"[{collect_name}] no recipe ids. stop. page={page}")
            break

        for recipe_id in recipe_ids:
            if current_count >= limit:
                break

            if recipe_id in seen_recipe_ids:
                continue

            seen_recipe_ids.add(recipe_id)

            try:
                already_exists = exists_raw_recipe(recipe_id)

                if not already_exists:
                    recipe = parse_recipe_detail(recipe_id)

                    if collect_kind == "category":
                        recipe["category_type"] = collect_name

                    upsert_raw_recipe(recipe)

                    print(
                        f"[{collect_name}] saved raw_recipe, "
                        f"recipe_id={recipe_id}, title={recipe['title']}"
                    )

                else:
                    print(f"[{collect_name}] already exists recipe_id={recipe_id}. append type only.")

                append_raw_recipe_collect_type(
                    recipe_id=recipe_id,
                    category_type=collect_name if collect_kind == "category" else None,
                    ingredient_type=collect_name if collect_kind == "ingredient" else None,
                    method_type=collect_name if collect_kind == "method" else None,
                    situation_type=collect_name if collect_kind == "situation" else None,
                )

                current_count += 1

                print(
                    f"[{collect_name}] collected "
                    f"{current_count}/{limit}, "
                    f"recipe_id={recipe_id}"
                )

                time.sleep(sleep_seconds)

            except Exception as e:
                print(f"[WARN] recipe failed. kind={collect_kind}, name={collect_name}, recipe_id={recipe_id}, error={e}")
                time.sleep(sleep_seconds)
                continue

        page += 1

    final_count = count_raw_recipes_by_collect_type(
        collect_kind=collect_kind,
        collect_value=collect_name
    )

    print(f"[{collect_name}] finished. final db count={final_count}, target={limit}")

    if final_count < limit:
        print(f"[WARN] {collect_name} did not reach target. final={final_count}, target={limit}")

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

    print("collect kind:", args.collect_kind)
    print("target groups:", list(target_groups.keys()))
    print("limit per group:", args.limit)
    print("sleep seconds:", args.sleep)
    print("max page:", args.max_page)

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
            max_page=args.max_page
        )

if __name__ == "__main__":
    main()