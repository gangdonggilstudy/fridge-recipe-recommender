import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

# 서버/터미널 환경에서도 이미지 파일 저장 가능하게 설정
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from dotenv import load_dotenv

# =========================
# 경로 설정
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs" / "charts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# .env 로드
load_dotenv(BASE_DIR / ".env")

# .env에 있는 DB_URL 사용
DB_URL = os.getenv("DB_URL")


def get_engine():
    if not DB_URL:
        raise ValueError(".env 파일에 DB_URL이 설정되어 있지 않습니다.")

    return create_engine(DB_URL)

def load_review_count():
    """
    raw_recipe_review 테이블에서 레시피별 후기 수를 집계한다.

    전제:
    - raw_recipe_review 테이블에 recipe_id 컬럼이 있음
    """

    query = """
        SELECT recipe_id
             , COUNT(*) AS review_count
          FROM raw_recipe_review
         GROUP BY recipe_id
         ORDER BY review_count DESC
    """

    engine = get_engine()
    return pd.read_sql(query, engine)


def draw_review_count_distribution(df):
    """
    원본 후기수 분포 그래프
    """

    plt.figure(figsize=(8, 4))
    plt.hist(df["review_count"], bins=50)

    plt.xlabel("Review Count")
    plt.ylabel("Recipe Count")
    plt.title("Distribution of Review Count per Recipe")

    plt.tight_layout()

    save_path = OUTPUT_DIR / "review_count_distribution.png"
    plt.savefig(save_path, dpi=150)
    plt.close()

    print(f"Saved: {save_path}")


def draw_log_review_count_distribution(df):
    """
    log(후기수 + 1) 분포 그래프

    후기수는 일부 인기 레시피에 몰리는 경우가 많아서
    로그 변환 그래프를 같이 보면 발표자료에서 더 보기 좋음.
    """

    df = df.copy()
    df["log_review_count"] = np.log1p(df["review_count"])

    plt.figure(figsize=(8, 4))
    plt.hist(df["log_review_count"], bins=50)

    plt.xlabel("log(Review Count + 1)")
    plt.ylabel("Recipe Count")
    plt.title("Log Distribution of Review Count per Recipe")

    plt.tight_layout()

    save_path = OUTPUT_DIR / "log_review_count_distribution.png"
    plt.savefig(save_path, dpi=150)
    plt.close()

    print(f"Saved: {save_path}")

def draw_review_count_bar(df):
    """
    후기수별 레시피 개수 막대그래프

    예:
    review_count = 1 인 레시피가 몇 개인지
    review_count = 2 인 레시피가 몇 개인지
    ...
    """

    count_df = (
        df["review_count"]
        .value_counts()
        .sort_index()
        .reset_index()
    )

    count_df.columns = ["review_count", "recipe_count"]

    print("\n=== Recipe Count by Review Count ===")
    print(count_df.head(30))

    plt.figure(figsize=(10, 4))
    plt.bar(count_df["review_count"], count_df["recipe_count"])

    plt.xlabel("Review Count")
    plt.ylabel("Recipe Count")
    plt.title("Recipe Count by Review Count")

    plt.tight_layout()

    save_path = OUTPUT_DIR / "recipe_count_by_review_count.png"
    plt.savefig(save_path, dpi=150)
    plt.close()

    print(f"Saved: {save_path}")

def print_summary(df):
    """
    콘솔에 간단한 요약 통계 출력
    """

    print("\n=== Review Count Summary ===")
    print(df["review_count"].describe())

    print("\n=== Top 10 Recipes by Review Count ===")
    print(df.head(10))


# def main():
#     df = load_review_count()

#     if df.empty:
#         print("raw_recipe_review 테이블에 후기 데이터가 없습니다.")
#         return

#     print_summary(df)
#     draw_review_count_distribution(df)
#     draw_log_review_count_distribution(df)


# if __name__ == "__main__":
#     main()

def main():
    df = load_review_count()

    if df.empty:
        print("raw_recipe_review 테이블에 후기 데이터가 없습니다.")
        return

    print_summary(df)

    draw_review_count_distribution(df)
    draw_review_count_bar(df)
    draw_log_review_count_distribution(df)