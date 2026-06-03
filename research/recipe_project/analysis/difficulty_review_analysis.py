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
# 한글 폰트 설정
# =========================
plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False

# =========================
# 경로 / DB 설정
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs" / "charts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")
DB_URL = os.getenv("DB_URL")


DIFFICULTY_MAP = {
    "아무나": 1,
    "초급": 2,
    "중급": 3,
    "고급": 4,
    "신의경지": 5,
}


def get_engine():
    if not DB_URL:
        raise ValueError(".env 파일에 DB_URL이 없습니다.")

    return create_engine(DB_URL)


def load_recipe_data():
    """
    난이도와 리뷰수를 raw_recipe 테이블에서 조회한다.
    """

    query = """
        SELECT recipe_id
             , title
             , difficulty
             , review_count
          FROM raw_recipe
         WHERE difficulty IS NOT NULL
           AND difficulty <> ''
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


def prepare_data(df):
    data = df.copy()

    data["difficulty"] = data["difficulty"].astype(str).str.strip()
    data["difficulty_score"] = data["difficulty"].map(DIFFICULTY_MAP)
    data["review_count_num"] = to_numeric_series(data["review_count"])

    data = data.dropna(subset=["difficulty_score", "review_count_num"])

    data = data[
        (data["difficulty_score"] > 0)
        & (data["review_count_num"] >= 0)
    ]

    # 리뷰수는 일부 인기 레시피에 크게 몰릴 수 있으므로 로그 변환
    data["log_review_count"] = numpy.log1p(data["review_count_num"])

    return data


def draw_difficulty_review_regression(data):
    """
    난이도에 따른 리뷰수 선형회귀 그래프 생성.

    X축: 난이도 점수
    Y축: log(리뷰수 + 1)
    """

    if data.empty:
        print("분석할 데이터가 없습니다.")
        return

    X = data[["difficulty_score"]]
    y = data["log_review_count"]

    model = LinearRegression()
    model.fit(X, y)

    y_pred = model.predict(X)

    r2 = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)

    print("=== Difficulty vs Review Count Regression ===")
    print(f"data count: {len(data)}")
    print(f"coef: {model.coef_[0]}")
    print(f"intercept: {model.intercept_}")
    print(f"R2: {r2}")
    print(f"MAE: {mae}")

    # scatter가 겹치지 않도록 x축에 아주 작은 jitter 적용
    plot_data = data.copy()
    plot_data["difficulty_score_jitter"] = (
        plot_data["difficulty_score"]
        + numpy.random.default_rng(42).normal(0, 0.04, len(plot_data))
    )

    # 데이터가 너무 많으면 그래프 표시용 점만 샘플링
    if len(plot_data) > 5000:
        plot_data = plot_data.sample(n=5000, random_state=42)

    x_line = pd.DataFrame({
        "difficulty_score": [1, 2, 3, 4, 5]
    })
    y_line = model.predict(x_line)

    plt.figure(figsize=(8, 4))

    plt.scatter(
        plot_data["difficulty_score_jitter"],
        plot_data["log_review_count"],
        alpha=0.3
    )

    plt.plot(
        x_line["difficulty_score"],
        y_line
    )

    plt.xticks(
        [1, 2, 3, 4, 5],
        ["아무나", "초급", "중급", "고급", "신의경지"]
    )

    plt.xlabel("Difficulty")
    plt.ylabel("log(Review Count + 1)")
    plt.title(f"Difficulty vs Review Count / R2={r2:.3f}")

    plt.tight_layout()

    save_path = OUTPUT_DIR / "difficulty_review_regression.png"
    plt.savefig(save_path, dpi=150)
    plt.close()

    print(f"Saved: {save_path}")


def draw_difficulty_review_bar(data):
    """
    난이도별 평균 리뷰수 비교 그래프 생성.
    선형회귀보다 발표자료에서 보기 쉬운 보조 그래프.
    """

    if data.empty:
        print("분석할 데이터가 없습니다.")
        return

    summary = (
        data
        .groupby(["difficulty", "difficulty_score"], as_index=False)
        .agg(
            recipe_count=("recipe_id", "count"),
            avg_review_count=("review_count_num", "mean"),
            avg_log_review_count=("log_review_count", "mean"),
            median_review_count=("review_count_num", "median")
        )
        .sort_values("difficulty_score")
    )

    print("\n=== Difficulty Summary ===")
    print(summary)

    plt.figure(figsize=(8, 4))

    plt.bar(
        summary["difficulty"],
        summary["avg_log_review_count"]
    )

    plt.xlabel("Difficulty")
    plt.ylabel("Average log(Review Count + 1)")
    plt.title("Average Review Count by Difficulty")

    plt.tight_layout()

    save_path = OUTPUT_DIR / "difficulty_review_bar.png"
    plt.savefig(save_path, dpi=150)
    plt.close()

    print(f"Saved: {save_path}")


def main():
    print("[1] DB 조회 시작")
    df = load_recipe_data()
    print("[2] DB 조회 완료:", len(df))

    print("[3] 데이터 전처리 시작")
    data = prepare_data(df)
    print("[4] 분석 대상 데이터 수:", len(data))

    print("[5] 선형회귀 그래프 생성")
    draw_difficulty_review_regression(data)

    print("[6] 난이도별 평균 리뷰수 그래프 생성")
    draw_difficulty_review_bar(data)

    print("[7] 완료")


if __name__ == "__main__":
    main()