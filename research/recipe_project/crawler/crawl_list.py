import re
import time
from typing import List
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException


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
                f"[WARN] list fetch failed. "
                f"attempt={attempt}/{max_retries}, "
                f"wait={wait_seconds}s, url={url}, error={e}"
            )
            time.sleep(wait_seconds)

    raise last_error


def extract_recipe_ids(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")

    recipe_ids = []

    for a in soup.select("a[href*='/recipe/']"):
        href = a.get("href", "")
        match = re.search(r"/recipe/(\d+)", href)

        if match:
            recipe_ids.append(match.group(1))

    return list(dict.fromkeys(recipe_ids))


def add_page_param(url: str, page: int) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    query["page"] = [str(page)]

    new_query = urlencode(query, doseq=True)

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))


def collect_recipe_ids_from_category_page(
        category_url: str,
        page: int
) -> list[str]:
    page_url = add_page_param(category_url, page)

    html = fetch_html(page_url)
    recipe_ids = extract_recipe_ids(html)

    print(f"page={page}, recipe_id_count={len(recipe_ids)}, url={page_url}")

    return recipe_ids