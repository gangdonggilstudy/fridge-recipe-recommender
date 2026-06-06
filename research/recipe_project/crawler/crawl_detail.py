import re
import time
import argparse
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

from db.repository import (
    upsert_raw_recipe, find_recipe_ids_for_review_crawling
)

BASE_URL = "https://www.10000recipe.com"


def fetch_html(url: str, max_retries: int = 3, timeout: int = 20) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text

        except RequestException as e:
            last_error = e
            wait_seconds = attempt * 3
            print(
                f"[WARN] detail fetch failed. "
                f"attempt={attempt}/{max_retries}, "
                f"wait={wait_seconds}s, url={url}, error={e}"
            )
            time.sleep(wait_seconds)

    raise last_error


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def parse_int(value: str | None) -> int | None:
    if not value:
        return None

    value = value.replace(",", "")
    match = re.search(r"\d+", value)

    if not match:
        return None

    return int(match.group(0))

def parse_float(value: str | None) -> float | None:
    if not value:
        return None

    match = re.search(r"([0-5](?:\.\d+)?)", value)

    if not match:
        return None

    return float(match.group(1))


def parse_cook_time_minutes(soup: BeautifulSoup, body_text: str) -> int | None:
    """
    요리시간을 분 단위 숫자로 변환한다.

    예:
    - 10분 이내  -> 10
    - 30분 이내  -> 30
    - 1시간 이내 -> 60
    - 1시간 30분 -> 90
    """

    candidate_texts: list[str] = []

    # 만개의레시피 상세 상단 정보 영역 후보
    for selector in [
        ".view2_summary_info span",
        ".view2_summary_info",
        ".view2_summary",
    ]:
        for el in soup.select(selector):
            text = clean_text(el.get_text(" ", strip=True))
            if text:
                candidate_texts.append(text)

    candidate_texts.append(body_text)

    for text in candidate_texts:
        # 1시간 30분
        match = re.search(r"(\d+)\s*시간\s*(\d+)\s*분", text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            return hour * 60 + minute

        # 1시간 이내 / 2시간 이상
        match = re.search(r"(\d+)\s*시간", text)
        if match:
            hour = int(match.group(1))
            return hour * 60

        # 10분 이내 / 30분
        match = re.search(r"(\d+)\s*분", text)
        if match:
            return int(match.group(1))

    return None


def parse_difficulty(soup: BeautifulSoup, body_text: str) -> str:
    """
    난이도 텍스트를 추출한다.

    만개의레시피에서 자주 보이는 값:
    - 아무나
    - 초급
    - 중급
    - 고급
    - 신의경지
    """

    difficulty_values = ["아무나", "초급", "중급", "고급", "신의경지"]

    candidate_texts: list[str] = []

    for selector in [
        ".view2_summary_info span",
        ".view2_summary_info",
        ".view2_summary",
    ]:
        for el in soup.select(selector):
            text = clean_text(el.get_text(" ", strip=True))
            if text:
                candidate_texts.append(text)

    candidate_texts.append(body_text)

    for text in candidate_texts:
        for difficulty in difficulty_values:
            if difficulty in text:
                return difficulty

    return ""


def parse_avg_rating(soup: BeautifulSoup, body_text: str) -> float | None:
    """
    평균평점을 추출한다.

    페이지 구조가 바뀔 수 있으므로 별점/평점 관련 selector를 우선 보고,
    없으면 본문 텍스트에서 fallback으로 찾는다.
    """

    rating_selectors = [
        ".view2_summary .score_star",
        ".view2_summary .star_score",
        ".view2_summary .view_score",
        ".view2_summary [class*='star']",
        ".view2_summary [class*='score']",
        ".view2_review [class*='star']",
        ".view2_review [class*='score']",
        "[class*='rating']",
    ]

    for selector in rating_selectors:
        for el in soup.select(selector):
            text = clean_text(el.get_text(" ", strip=True))
            rating = parse_float(text)

            if rating is not None:
                return rating

    # fallback: 평점 4.8 / 별점 5.0 / 평균평점 4.7 같은 표현
    patterns = [
        r"평점\s*([0-5](?:\.\d+)?)",
        r"별점\s*([0-5](?:\.\d+)?)",
        r"평균\s*평점\s*([0-5](?:\.\d+)?)",
        r"평균\s*별점\s*([0-5](?:\.\d+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, body_text)

        if match:
            return float(match.group(1))

    return None

def parse_ingredients(soup: BeautifulSoup) -> List[str]:
    """
    raw_recipe.ingredients 저장 형식:
    재료명,단위/재료명2,단위2

    예:
    두부,1모/대파,1/2개/간장,2큰술
    """

    ingredients: List[str] = []

    name_elements = soup.select(".ingre_list_name")

    for name_el in name_elements:
        a_el = name_el.select_one("a")
        ingredient_name = clean_text(a_el.get_text(" ")) if a_el else clean_text(name_el.get_text(" "))

        if not ingredient_name:
            continue

        parent_el = name_el.find_parent()
        amount_el = parent_el.select_one(".ingre_list_ea") if parent_el else None
        amount_text = clean_text(amount_el.get_text(" ")) if amount_el else ""

        amount_text = amount_text.replace("구매", "").strip()

        ingredients.append(f"{ingredient_name},{amount_text}")

    # fallback
    if not ingredients:
        for el in soup.select(".ready_ingre3 li"):
            text = clean_text(el.get_text(" "))
            text = text.replace("구매", "").strip()

            if text:
                ingredients.append(f"{text},")

    return ingredients

def extract_recipe_dates(soup):
    text = soup.get_text(" ", strip=True)

    reg_date = None
    update_date = None

    reg_match = re.search(r"등록일\s*:\s*(\d{4}-\d{2}-\d{2})", text)
    update_match = re.search(r"수정일\s*:\s*(\d{4}-\d{2}-\d{2})", text)

    if reg_match:
        reg_date = reg_match.group(1)

    if update_match:
        update_date = update_match.group(1)

    return reg_date, update_date

def parse_recipe_detail(recipe_id: str) -> Dict:
    url = f"{BASE_URL}/recipe/{recipe_id}"
    html = fetch_html(url)

    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one("div.view2_summary h3")
    title = clean_text(title_el.get_text()) if title_el else ""

    summary_el = soup.select_one("div.view2_summary_in")
    summary = clean_text(summary_el.get_text()) if summary_el else ""

    ingredients = parse_ingredients(soup)

    steps: List[str] = []
    for el in soup.select(".view_step_cont"):
        text = clean_text(el.get_text(" "))
        if text:
            steps.append(text)

    tags: List[str] = []
    for el in soup.select(".view_tag a"):
        tag = clean_text(el.get_text()).replace("#", "")
        if tag:
            tags.append(tag)

    body_text = soup.get_text("\n", strip=True)

    cook_time = parse_cook_time_minutes(soup, body_text)
    difficulty = parse_difficulty(soup, body_text)
    avg_rating = parse_avg_rating(soup, body_text)

    view_count = None

    for selector in [
        ".view_cate_num",
        ".view2_summary_info .view_num",
        ".view2_summary_info span",
        ".view2_summary .view_num"
    ]:
        el = soup.select_one(selector)
        if el:
            candidate = parse_int(el.get_text(strip=True))
            if candidate:
                view_count = candidate
                break

    if view_count is None:
        numbers = re.findall(r"\d{1,3}(?:,\d{3})+", body_text)
        if numbers:
            view_count = parse_int(numbers[0])

    review_count = None
    review_match = re.search(r"요리\s*후기\s*([\d,]+)", body_text)
    if review_match:
        review_count = parse_int(review_match.group(1))

    scrap_count = None
    scrap_match = re.search(r"스크랩\s*([\d,]+)", body_text)
    if scrap_match:
        scrap_count = parse_int(scrap_match.group(1))

    reg_date, update_date = extract_recipe_dates(soup)

    return {
        "recipe_id": recipe_id,
        "title": title,
        "summary": summary,
        "ingredients": "/".join(ingredients),
        "steps": "\n".join(steps),
        "tags": ",".join(tags),
        "cook_time": cook_time,
        "difficulty": difficulty,
        "avg_rating": avg_rating,
        "view_count": view_count,
        "scrap_count": scrap_count,
        "review_count": review_count,
        "reg_date": reg_date,
        "update_date": update_date,
        "source_url": url
    }


# def main():
#     recipe = parse_recipe_detail("6897498")
#     print(recipe)

def run_detail_crawl(limit: int | None = 1000, sleep_seconds: float = 0.5) -> None:
    recipe_ids = find_recipe_ids_for_review_crawling(limit=limit)

    print(f"target recipe count = {len(recipe_ids)}")

    success_count = 0
    fail_count = 0

    for idx, recipe_id in enumerate(recipe_ids, start=1):
        try:
            recipe = parse_recipe_detail(str(recipe_id))
            upsert_raw_recipe(recipe)

            success_count += 1
            print(f"[OK] {idx}/{len(recipe_ids)} recipe_id={recipe_id}")

        except Exception as e:
            fail_count += 1
            print(f"[ERROR] {idx}/{len(recipe_ids)} recipe_id={recipe_id}, error={e}")

        time.sleep(sleep_seconds)

    print("done")
    print(f"success_count={success_count}")
    print(f"fail_count={fail_count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args()

    run_detail_crawl(
        limit=args.limit,
        sleep_seconds=args.sleep
    )

if __name__ == "__main__":
    main()