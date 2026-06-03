import argparse
import time
from collections import OrderedDict

from crawler.crawl_detail import parse_recipe_detail
from crawler.crawl_theme import collect_recipe_ids_from_theme
from db.repository import (
    exists_raw_recipe,
    upsert_raw_recipe,
    upsert_recipe_season_theme,
    count_recipe_season_theme,
)


SEASON_THEME_URLS = OrderedDict({
    "봄": "https://www.10000recipe.com/theme/view.html?theme=101010001",
    "여름": "https://www.10000recipe.com/theme/view.html?theme=101010002",
    "가을": "https://www.10000recipe.com/theme/view.html?theme=101010003",
    "겨울": "https://www.10000recipe.com/theme/view.html?theme=101010004",
})


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seasons",
        type=str,
        default=None,
        help='수집할 계절 목록. 콤마로 구분. 예: --seasons "봄,여름"'
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="계절별 수집 제한 개수. 없으면 전체 수집"
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
        default=30,
        help="계절별 최대 조회 페이지. 기본값 30"
    )

    parser.add_argument(
        "--skip-detail",
        action="store_true",
        help="raw_recipe 상세 수집은 하지 않고 recipe_season_theme만 저장"
    )

    return parser.parse_args()


def parse_target_seasons(seasons_arg: str | None) -> OrderedDict:
    if not seasons_arg:
        return SEASON_THEME_URLS

    requested_seasons = [
        season.strip()
        for season in seasons_arg.split(",")
        if season.strip()
    ]

    if not requested_seasons:
        return SEASON_THEME_URLS

    invalid_seasons = [
        season
        for season in requested_seasons
        if season not in SEASON_THEME_URLS
    ]

    if invalid_seasons:
        raise ValueError(
            f"Unknown seasons: {invalid_seasons}. "
            f"Available seasons: {list(SEASON_THEME_URLS.keys())}"
        )

    return OrderedDict(
        (season, SEASON_THEME_URLS[season])
        for season in requested_seasons
    )


def crawl_season_theme(
        season_type: str,
        theme_url: str,
        limit: int | None,
        sleep_seconds: float,
        max_page: int,
        skip_detail: bool
):
    print(f"\n=== Start season theme: {season_type} ===")
    print(f"theme_url={theme_url}")

    before_count = count_recipe_season_theme(season_type)
    print(f"[{season_type}] current theme count={before_count}")

    recipe_ids = collect_recipe_ids_from_theme(
        theme_url=theme_url,
        max_page=max_page,
        sleep_seconds=sleep_seconds,
        limit=limit
    )

    print(f"[{season_type}] collected recipe ids={len(recipe_ids)}")

    saved_theme_count = 0
    saved_raw_count = 0
    skipped_raw_count = 0
    failed_count = 0

    for idx, recipe_id in enumerate(recipe_ids, start=1):
        try:
            # 1. season theme mapping 저장
            upsert_recipe_season_theme(
                recipe_id=recipe_id,
                season_type=season_type,
                theme_url=theme_url
            )

            saved_theme_count += 1

            # 2. raw_recipe에 없으면 상세 수집
            if skip_detail:
                print(f"[{season_type}] {idx}/{len(recipe_ids)} saved theme only recipe_id={recipe_id}")
                continue

            if exists_raw_recipe(recipe_id):
                skipped_raw_count += 1
                print(f"[{season_type}] {idx}/{len(recipe_ids)} raw exists. recipe_id={recipe_id}")
                continue

            recipe = parse_recipe_detail(recipe_id)

            # 제철요리 테마에서 수집된 레시피는 category_type을 억지로 넣지 않음
            # 기존 종류별 카테고리가 있으면 유지하고, 신규면 NULL로 저장됨
            recipe["category_type"] = None

            upsert_raw_recipe(recipe)

            saved_raw_count += 1

            print(
                f"[{season_type}] {idx}/{len(recipe_ids)} "
                f"saved raw recipe_id={recipe_id}, title={recipe.get('title')}"
            )

            time.sleep(sleep_seconds)

        except Exception as e:
            failed_count += 1
            print(f"[WARN] season crawl failed. season={season_type}, recipe_id={recipe_id}, error={e}")
            time.sleep(sleep_seconds)
            continue

    after_count = count_recipe_season_theme(season_type)

    print(f"\n[{season_type}] done")
    print(f"theme before={before_count}, after={after_count}")
    print(f"saved_theme_count={saved_theme_count}")
    print(f"saved_raw_count={saved_raw_count}")
    print(f"skipped_raw_count={skipped_raw_count}")
    print(f"failed_count={failed_count}")


def main():
    args = parse_args()

    target_seasons = parse_target_seasons(args.seasons)

    print("target seasons:", list(target_seasons.keys()))
    print("limit per season:", args.limit)
    print("sleep seconds:", args.sleep)
    print("max page:", args.max_page)
    print("skip detail:", args.skip_detail)

    for season_type, theme_url in target_seasons.items():
        crawl_season_theme(
            season_type=season_type,
            theme_url=theme_url,
            limit=args.limit,
            sleep_seconds=args.sleep,
            max_page=args.max_page,
            skip_detail=args.skip_detail
        )


if __name__ == "__main__":
    main()