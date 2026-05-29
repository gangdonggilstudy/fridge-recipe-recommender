import argparse
import time
from collections import OrderedDict

from crawler.crawl_detail import parse_recipe_detail
from crawler.crawl_list import collect_recipe_ids_from_category_page
from db.repository import (
    upsert_raw_recipe,
    count_raw_recipes_by_category,
    exists_raw_recipe,
)


TYPE_CATEGORY_URLS = OrderedDict({
    "메인반찬": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=56&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "국/탕": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=54&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "찌개": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=55&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "면/만두": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=53&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "밥/죽/떡": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=52&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
    "양식": "https://www.10000recipe.com/recipe/list.html?q=&query=&cat1=&cat2=&cat3=&cat4=65&fct=&order=reco&lastcate=cat4&dsearch=&copyshot=&scrap=&degree=&portion=&time=&niresource=",
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


def main():
    args = parse_args()

    target_categories = parse_target_categories(args.categories)

    print("target categories:", list(target_categories.keys()))
    print("limit per category:", args.limit)
    print("sleep seconds:", args.sleep)
    print("max page:", args.max_page)

    for category_name, category_url in target_categories.items():
        crawl_category_until_limit(
            category_name=category_name,
            category_url=category_url,
            limit=args.limit,
            sleep_seconds=args.sleep,
            max_page=args.max_page
        )


if __name__ == "__main__":
    main()