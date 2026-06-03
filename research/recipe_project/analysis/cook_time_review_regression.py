import os
from pathlib import Path

import numpy
import pandas as pd
import matplotlib

# 터미널 환경에서 이미지 저장 가능하게 설정
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error


# =========================
# 경로 / DB 설정
# =========================
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
    """
    조리시간과 리뷰수를 raw_recipe 테이블에서 조회한다.
    """

    query = """
        SELECT recipe_id
             , title
             , cook_time
             , review_count
          FROM raw_recipe
         WHERE cook_time IS NOT NULL
           AND review_count IS NOT NULL
    """

    engine = get_engine()
    return pd.read_sql(query, engine)


def to_numeric_series(series):
    """
    숫자 컬럼에 콤마나 문자열이 섞여 있어도 숫자로 변환한다.
    예: '1,234' -> 1234
    """

    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False),
        errors="coerce"
    )


def draw_cook_time_review_regression(df):
    """
    조리시간에 따른 리뷰수 선형회귀 그래프를 생성한다.

    X축: 조리시간
    Y축: log(리뷰수 + 1)

    리뷰수는 일부 인기 레시피에 크게 몰릴 수 있으므로
    발표용 그래프에서는 log 변환을 적용한다.
    """

    data = df.copy()

    data["cook_time_num"] = to_numeric_series(data["cook_time"])
    data["review_count_num"] = to_numeric_series(data["review_count"])

    # 이상치/결측 제거
    data = data.dropna(subset=["cook_time_num", "review_count_num"])

    # 조리시간 0 이하 제거
    # 조리시간이 너무 큰 값은 크롤링/파싱 오류일 가능성이 있어 240분 이하만 사용
    data = data[
        (data["cook_time_num"] > 0)
        & (data["cook_time_num"] <= 240)
        & (data["review_count_num"] >= 0)
    ]

    if data.empty:
        print("분석할 데이터가 없습니다.")
        return

    # 리뷰수는 편차가 크므로 log(리뷰수 + 1) 사용
    data["log_review_count"] = numpy.log1p(data["review_count_num"])

    X = data[["cook_time_num"]]
    y = data["log_review_count"]

    model = LinearRegression()
    model.fit(X, y)

    y_pred = model.predict(X)

    r2 = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)

    print("=== Cooking Time vs Review Count Regression ===")
    print(f"data count: {len(data)}")
    print(f"coef: {model.coef_[0]}")
    print(f"intercept: {model.intercept_}")
    print(f"R2: {r2}")
    print(f"MAE: {mae}")

    # 회귀선이 x축 순서대로 그려지도록 정렬
    sorted_data = data.sort_values("cook_time_num")
    sorted_X = sorted_data[["cook_time_num"]]
    sorted_y_pred = model.predict(sorted_X)

    plt.figure(figsize=(8, 4))

    plt.scatter(
        data["cook_time_num"],
        data["log_review_count"],
        alpha=0.3
    )

    plt.plot(
        sorted_data["cook_time_num"],
        sorted_y_pred
    )

    plt.xlabel("Cooking Time (minutes)")
    plt.ylabel("log(Review Count + 1)")
    plt.title(f"Cooking Time vs Review Count / R2={r2:.3f}")

    plt.tight_layout()

    save_path = OUTPUT_DIR / "cook_time_review_regression.png"
    plt.savefig(save_path, dpi=150)
    plt.close()

    print(f"Saved: {save_path}")


def draw_cook_time_review_raw_regression(df):
    """
    로그 변환 없이 원본 리뷰수 기준 그래프도 생성한다.
    단, 리뷰수가 큰 레시피가 있으면 그래프가 한쪽으로 치우칠 수 있다.
    """

    data = df.copy()

    data["cook_time_num"] = to_numeric_series(data["cook_time"])
    data["review_count_num"] = to_numeric_series(data["review_count"])

    data = data.dropna(subset=["cook_time_num", "review_count_num"])

    data = data[
        (data["cook_time_num"] > 0)
        & (data["cook_time_num"] <= 240)
        & (data["review_count_num"] >= 0)
    ]

    if data.empty:
        print("분석할 데이터가 없습니다.")
        return

    X = data[["cook_time_num"]]
    y = data["review_count_num"]

    model = LinearRegression()
    model.fit(X, y)

    y_pred = model.predict(X)

    r2 = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)

    print("\n=== Cooking Time vs Raw Review Count Regression ===")
    print(f"data count: {len(data)}")
    print(f"coef: {model.coef_[0]}")
    print(f"intercept: {model.intercept_}")
    print(f"R2: {r2}")
    print(f"MAE: {mae}")

    sorted_data = data.sort_values("cook_time_num")
    sorted_X = sorted_data[["cook_time_num"]]
    sorted_y_pred = model.predict(sorted_X)

    plt.figure(figsize=(8, 4))

    plt.scatter(
        data["cook_time_num"],
        data["review_count_num"],
        alpha=0.3
    )

    plt.plot(
        sorted_data["cook_time_num"],
        sorted_y_pred
    )

    plt.xlabel("Cooking Time (minutes)")
    plt.ylabel("Review Count")
    plt.title(f"Cooking Time vs Review Count / R2={r2:.3f}")

    plt.tight_layout()

    save_path = OUTPUT_DIR / "cook_time_review_raw_regression.png"
    plt.savefig(save_path, dpi=150)
    plt.close()

    print(f"Saved: {save_path}")


def main():
    df = load_recipe_data()

    print("loaded rows:", len(df))

    # 발표용 추천 그래프: log(리뷰수 + 1)
    draw_cook_time_review_regression(df)

    # 참고용 원본 리뷰수 그래프
    draw_cook_time_review_raw_regression(df)


if __name__ == "__main__":
    main()