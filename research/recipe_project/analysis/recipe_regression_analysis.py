import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs" / "charts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")
DB_URL = os.getenv("DB_URL")


def get_engine():
    if not DB_URL:
        raise ValueError(".env 파일에 DB_URL이 없습니다.")
    return create_engine(DB_URL)


def load_recipe_data():
    query = """
        SELECT recipe_id
             , title
             , cook_time
             , difficulty
             , avg_rating
             , review_count
             , scrap_count
             , view_count
             , category_types
             , ingredient_types
             , method_types
          FROM raw_recipe
    """

    engine = get_engine()
    return pd.read_sql(query, engine)


def add_difficulty_score(df):
    difficulty_map = {
        "아무나": 1,
        "초급": 2,
        "중급": 3,
        "고급": 4,
        "신의경지": 5,
    }

    df["difficulty_score"] = df["difficulty"].map(difficulty_map)
    return df


def draw_linear_regression(
        df,
        x_col,
        y_col,
        x_label,
        y_label,
        title,
        file_name,
        x_ticks=None,
        x_tick_labels=None
):
    data = df[[x_col, y_col]].dropna()

    if data.empty:
        print(f"[SKIP] no data: {title}")
        return

    X = data[[x_col]]
    y = data[y_col]

    model = LinearRegression()
    model.fit(X, y)

    y_pred = model.predict(X)
    r2 = r2_score(y, y_pred)

    sorted_data = data.sort_values(x_col)
    sorted_pred = model.predict(sorted_data[[x_col]])

    print(f"\n=== {title} ===")
    print("coef:", model.coef_[0])
    print("intercept:", model.intercept_)
    print("r2:", r2)

    plt.figure(figsize=(8, 4))
    plt.scatter(data[x_col], y, alpha=0.3)
    plt.plot(sorted_data[x_col], sorted_pred)

    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(f"{title} / R2={r2:.3f}")

    if x_ticks is not None and x_tick_labels is not None:
        plt.xticks(x_ticks, x_tick_labels)

    plt.tight_layout()

    save_path = OUTPUT_DIR / file_name
    plt.savefig(save_path, dpi=150)
    plt.close()

    print(f"Saved: {save_path}")

def main():
    df = load_recipe_data()
    df = add_difficulty_score(df)

    # 숫자 컬럼 정리
    numeric_columns = [
        "cook_time",
        "avg_rating",
        "review_count",
        "scrap_count",
        "view_count",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 후기수, 스크랩수는 편차가 크므로 로그 변환
    df["log_review_count"] = np.log1p(df["review_count"].fillna(0).astype(float))
    df["log_scrap_count"] = np.log1p(df["scrap_count"].fillna(0).astype(float))
    df["log_view_count"] = np.log1p(df["view_count"].fillna(0).astype(float))

    # 1. 요리시간 vs 후기수
    draw_linear_regression(
        df=df[df["cook_time"].notna() & (df["cook_time"] > 0)],
        x_col="cook_time",
        y_col="review_count", #"log_review_count",
        x_label="Cooking Time",
        y_label="Review count", #"log(Review Count + 1)",
        title="Cooking Time vs Review Count",
        file_name="reg_cook_time_review_count.png"
    )

    # 1-1. 요리시간 vs 조회수
    draw_linear_regression(
        df=df[df["cook_time"].notna() & (df["cook_time"] > 0) & df["view_count"].notna()],
        x_col="cook_time",
        y_col="log_view_count",
        x_label="Cooking Time",
        y_label="log(View Count + 1)",
        title="Cooking Time vs View Count",
        file_name="reg_cook_time_view_count.png"
    )

    # 2. 난이도 vs 후기수
    draw_linear_regression(
        df=df[df["difficulty_score"].notna()],
        x_col="difficulty_score",
        y_col="review_count", #"log_review_count",
        x_label="Difficulty",
        y_label="Review Count",#"log(Review Count + 1)",
        title="Difficulty vs Review Count",
        file_name="reg_difficulty_review_count.png",
        # x_ticks=[1, 2, 3, 4, 5],
        x_ticks=[1, 2, 3],
        # x_tick_labels=["아무나", "초급", "중급", "고급", "신의경지"]
        x_tick_labels=["아무나", "초급", "중급"]
    )

    # 2-1. 난이도 vs 조회수
    draw_linear_regression(
        df=df[df["difficulty_score"].notna() & df["view_count"].notna()],
        x_col="difficulty_score",
        y_col="log_view_count",
        x_label="Difficulty",
        y_label="log(View Count + 1)",
        title="Difficulty vs View Count",
        file_name="reg_difficulty_view_count.png",
        x_ticks=[1, 2, 3, 4, 5],
        x_tick_labels=["아무나", "초급", "중급", "고급", "신의경지"]
    )

    # 3. 요리시간 vs 평균평점
    draw_linear_regression(
        df=df[df["cook_time"].notna() & (df["cook_time"] > 0) & df["avg_rating"].notna()],
        x_col="cook_time",
        y_col="avg_rating",
        x_label="Cooking Time",
        y_label="Average Rating",
        title="Cooking Time vs Average Rating",
        file_name="reg_cook_time_avg_rating.png"
    )

    # 4. 스크랩수 vs 후기수
    draw_linear_regression(
        df=df[df["scrap_count"].notna() & df["review_count"].notna()],
        x_col="log_scrap_count",
        y_col="log_review_count",
        x_label="log(Scrap Count + 1)",
        y_label="log(Review Count + 1)",
        title="Scrap Count vs Review Count",
        file_name="reg_scrap_review_count.png"
    )

if __name__ == "__main__":
    main()