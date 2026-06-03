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
                f"[WARN] theme fetch failed. "
                f"attempt={attempt}/{max_retries}, "
                f"wait={wait_seconds}s, url={url}, error={e}"
            )
            time.sleep(wait_seconds)

    raise last_error


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


def extract_recipe_ids_from_theme_html(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")

    recipe_ids = []

    for a in soup.select("a[href*='/recipe/']"):
        href = a.get("href", "")

        match = re.search(r"/recipe/(\d+)", href)

        if match:
            recipe_ids.append(match.group(1))

    # 중복 제거, 순서 유지
    return list(dict.fromkeys(recipe_ids))


def collect_recipe_ids_from_theme_page(
        theme_url: str,
        page: int
) -> list[str]:
    page_url = add_page_param(theme_url, page)

    html = fetch_html(page_url)
    recipe_ids = extract_recipe_ids_from_theme_html(html)

    print(f"theme page={page}, recipe_id_count={len(recipe_ids)}, url={page_url}")

    return recipe_ids


def collect_recipe_ids_from_theme(
        theme_url: str,
        max_page: int = 30,
        sleep_seconds: float = 1.0,
        limit: int | None = None
) -> list[str]:
    collected = []
    seen = set()

    for page in range(1, max_page + 1):
        try:
            recipe_ids = collect_recipe_ids_from_theme_page(
                theme_url=theme_url,
                page=page
            )

        except Exception as e:
            print(f"[ERROR] theme page failed. page={page}, error={e}")
            time.sleep(sleep_seconds)
            continue

        if not recipe_ids:
            print(f"no recipe ids. stop. page={page}")
            break

        added_count = 0

        for recipe_id in recipe_ids:
            if recipe_id in seen:
                continue

            seen.add(recipe_id)
            collected.append(recipe_id)
            added_count += 1

            if limit and len(collected) >= limit:
                return collected

        print(f"page={page}, added={added_count}, total={len(collected)}")

        time.sleep(sleep_seconds)

    return collected