import re
import time
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

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

    return {
        "recipe_id": recipe_id,
        "title": title,
        "summary": summary,
        "ingredients": "/".join(ingredients),
        "steps": "\n".join(steps),
        "tags": ",".join(tags),
        "view_count": view_count,
        "scrap_count": scrap_count,
        "review_count": review_count,
        "source_url": url
    }


def main():
    recipe = parse_recipe_detail("6897498")
    print(recipe)


if __name__ == "__main__":
    main()