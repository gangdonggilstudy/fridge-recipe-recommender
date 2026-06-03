import argparse
import time

from crawler.crawl_review import parse_recipe_reviews
from db.repository import (
    find_recipe_ids_for_review_crawling,
    delete_raw_recipe_reviews,
    upsert_raw_recipe_review,
    count_raw_recipe_reviews,
)


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="후기 수집 대상 레시피 개수. 없으면 전체"
    )

    parser.add_argument(
        "--recipe-id",
        type=str,
        default=None,
        help="특정 recipe_id만 수집"
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="요청 간 대기 시간. 기본값 1초"
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help="기존 해당 레시피 후기 삭제 후 재수집"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.recipe_id:
        recipe_ids = [args.recipe_id]
    else:
        recipe_ids = find_recipe_ids_for_review_crawling(limit=args.limit)

    print(f"target recipe count={len(recipe_ids)}")

    total_saved_count = 0
    failed_count = 0

    for idx, recipe_id in enumerate(recipe_ids, start=1):
        try:
            if args.replace:
                delete_raw_recipe_reviews(recipe_id)

            reviews = parse_recipe_reviews(recipe_id)

            saved_count = 0

            for review in reviews:
                # 날짜가 없는 후기는 날씨 분석에 못 쓰므로 저장은 하되 나중에 제외 가능
                upsert_raw_recipe_review(review)
                saved_count += 1

            total_saved_count += saved_count

            current_count = count_raw_recipe_reviews(recipe_id)

            print(
                f"[{idx}/{len(recipe_ids)}] "
                f"recipe_id={recipe_id}, parsed={len(reviews)}, "
                f"saved={saved_count}, db_count={current_count}"
            )

            time.sleep(args.sleep)

        except Exception as e:
            failed_count += 1
            print(f"[WARN] failed recipe_id={recipe_id}, error={e}")
            time.sleep(args.sleep)

    print(f"done. total_saved_count={total_saved_count}, failed_count={failed_count}")


if __name__ == "__main__":
    main()