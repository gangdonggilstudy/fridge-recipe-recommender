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

    # 너무 넓은 selector는 답글/중복을 같이 잡을 수 있으므로
    # 우선순위대로 첫 번째로 잡히는 selector만 사용한다.
    review_selectors = [
        ".view_reply .media",
        ".comment_list > li",
        ".review_list > li",
    ]

    review_nodes = []

    for selector in review_selectors:
        nodes = soup.select(selector)

        if nodes:
            review_nodes = nodes
            print(f"[DEBUG] review selector used: {selector}, count={len(nodes)}")
            break

    seen_texts = set()

    for node in review_nodes:
        # 답글 node 자체면 제외
        if is_reply_review_element(node):
            continue

        # 정상 리뷰 안에 답글 block이 섞여 있으면 제거
        clean_node = remove_reply_blocks(node)

        full_text = clean_text(clean_node.get_text(" ", strip=True))

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
            selected = clean_node.select_one(selector)
            if selected:
                nickname = clean_text(selected.get_text(" ", strip=True))
                break

        # 내용 후보
        content = ""
        content_selectors = [
            ".reply_cont",
            ".comment",
            ".cont",
            "[class*='cont']",
            "[class*='txt']",
        ]

        for selector in content_selectors:
            selected = clean_node.select_one(selector)
            if selected:
                content = clean_text(selected.get_text(" ", strip=True))
                break

        if not content:
            content = full_text

        # 답글 버튼/불필요 문구 제거
        content = content.replace("답글", " ")
        content = content.replace("답글달기", " ")
        content = clean_text(content)

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
    
def is_reply_review_element(el) -> bool:
    """
    리뷰 답글/대댓글 영역이면 True.
    단, 최상위 리뷰 컨테이너인 view_reply는 제외한다.
    """

    reply_class_keywords = [
        "re_reply",
        "comment_reply",
        "review_reply",
        "reply_comment",
        "reply_answer",
        "recomment",
        "answer",
    ]

    class_text = " ".join(el.get("class", []))
    class_text_lower = class_text.lower()

    # 직접 class가 답글성 class인 경우
    if any(keyword in class_text_lower for keyword in reply_class_keywords):
        return True

    # class가 그냥 reply인 경우는 답글일 가능성이 있음
    # 단 view_reply는 전체 리뷰 영역이므로 제외
    class_names = set(el.get("class", []))
    if "reply" in class_names and "view_reply" not in class_names:
        return True

    # 부모를 올라가며 답글 영역인지 확인
    # 단 view_reply를 만나면 정상 리뷰 영역이므로 탐색 중단
    parent = el.find_parent()

    while parent:
        parent_class_names = set(parent.get("class", []))
        parent_class_text = " ".join(parent.get("class", [])).lower()

        if "view_reply" in parent_class_names:
            break

        if any(keyword in parent_class_text for keyword in reply_class_keywords):
            return True

        if "reply" in parent_class_names and "view_reply" not in parent_class_names:
            return True

        parent = parent.find_parent()

    text = el.get_text(" ", strip=True)

    if text.startswith("답글"):
        return True

    if "답글달기" in text:
        return True

    return False

def remove_reply_blocks(node):
    """
    리뷰 node 내부에 답글 영역이 섞여 있으면 제거한 복사본을 반환한다.
    원본 soup는 건드리지 않는다.
    """

    copied_soup = BeautifulSoup(str(node), "lxml")

    reply_selectors = [
        ".re_reply",
        ".comment_reply",
        ".review_reply",
        ".reply_comment",
        ".reply_answer",
        ".recomment",
        ".answer",
        "[class*='re_reply']",
        "[class*='comment_reply']",
        "[class*='review_reply']",
        "[class*='reply_comment']",
        "[class*='reply_answer']",
        "[class*='recomment']",
    ]

    for selector in reply_selectors:
        for reply_el in copied_soup.select(selector):
            reply_el.decompose()

    return copied_soup