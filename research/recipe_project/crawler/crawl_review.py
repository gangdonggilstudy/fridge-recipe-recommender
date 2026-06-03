import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException


def fetch_html(url: str, max_retries: int = 3, timeout: int = 20) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.10000recipe.com/",
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
                f"[WARN] review fetch failed. "
                f"attempt={attempt}/{max_retries}, "
                f"wait={wait_seconds}s, url={url}, error={e}"
            )
            time.sleep(wait_seconds)

    raise last_error


def parse_korean_date(text: str) -> Optional[str]:
    """
    다양한 날짜 표현을 YYYY-MM-DD로 변환
    예:
      2024-07-15
      2024.07.15
      2024. 7. 15.
      24.07.15
    """
    if not text:
        return None

    text = text.strip()

    # yyyy-mm-dd or yyyy.mm.dd
    match = re.search(r"(20\d{2}|19\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    # yy.mm.dd
    match = re.search(r"(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
    if match:
        year = int(match.group(1))
        year = 2000 + year
        month = int(match.group(2))
        day = int(match.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    return None


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_rating(text: str) -> Optional[float]:
    if not text:
        return None

    # 5.0, 별점 5, 평점 4.5 같은 값 추출
    match = re.search(r"([0-5](?:\.\d)?)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None

    return None


def parse_reviews_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")

    reviews = []

    # 만개의레시피 페이지 구조가 바뀔 수 있으므로 후보 selector 여러 개 사용
    review_selectors = [
        ".view_reply .media",
        ".view_reply .media-body",
        ".view_reply li",
        ".comment_list li",
        ".reply_list li",
        ".review_list li",
        "[class*='reply'] li",
        "[class*='comment'] li",
        "[class*='review'] li",
    ]

    review_nodes = []

    for selector in review_selectors:
        nodes = soup.select(selector)

        if len(nodes) > len(review_nodes):
            review_nodes = nodes

    seen_texts = set()

    for node in review_nodes:
        full_text = clean_text(node.get_text(" ", strip=True))

        if not full_text:
            continue

        if full_text in seen_texts:
            continue

        seen_texts.add(full_text)

        review_date = parse_korean_date(full_text)

        # 닉네임 후보
        nickname = ""
        nickname_selectors = [
            ".media-heading",
            ".info_name",
            ".name",
            "[class*='name']",
            "[class*='nick']",
        ]

        for selector in nickname_selectors:
            selected = node.select_one(selector)
            if selected:
                nickname = clean_text(selected.get_text(" ", strip=True))
                break

        # 내용 후보
        content = ""
        content_selectors = [
            ".media-body",
            ".reply_cont",
            ".comment",
            ".cont",
            "[class*='cont']",
            "[class*='txt']",
        ]

        for selector in content_selectors:
            selected = node.select_one(selector)
            if selected:
                content = clean_text(selected.get_text(" ", strip=True))
                break

        if not content:
            content = full_text

        rating = extract_rating(full_text)

        reviews.append({
            "review_date": review_date,
            "nickname": nickname,
            "review_content": content,
            "rating": rating,
        })

    return reviews


def parse_recipe_reviews(recipe_id: str) -> list[dict]:
    url = f"https://www.10000recipe.com/recipe/{recipe_id}"

    html = fetch_html(url)
    reviews = parse_reviews_from_html(html)

    # recipe_id, review_seq 부여
    result = []

    for idx, review in enumerate(reviews, start=1):
        result.append({
            "recipe_id": recipe_id,
            "review_seq": idx,
            "review_date": review.get("review_date"),
            "nickname": review.get("nickname"),
            "review_content": review.get("review_content"),
            "rating": review.get("rating"),
        })

    return result