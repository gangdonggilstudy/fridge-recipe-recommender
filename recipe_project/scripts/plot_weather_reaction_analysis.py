import os

import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import text

from db.connection import engine


OUTPUT_DIR = "outputs/weather"


def setup():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plt.rcParams["font.family"] = "AppleGothic"
    plt.rcParams["axes.unicode_minus"] = False


def save_rain_review_chart():
    sql = text("""
        SELECT rain_yn
             , SUM(review_count) AS total_review_count
          FROM recipe_daily_reaction
         WHERE rain_yn IS NOT NULL
         GROUP BY rain_yn
         ORDER BY rain_yn
    """)

    df = pd.read_sql(sql, engine)
    df["rain_label"] = df["rain_yn"].map({"Y": "비 오는 날", "N": "비 안 오는 날"})

    plt.figure(figsize=(8, 5))
    plt.bar(df["rain_label"], df["total_review_count"])
    plt.title("비 여부에 따른 총 후기 반응")
    plt.xlabel("강수 여부")
    plt.ylabel("총 후기 수")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/rain_review_count.png", dpi=200)
    plt.close()


def save_temp_group_chart():
    sql = text("""
        SELECT CASE
                   WHEN avg_temp < 5 THEN '추움'
                   WHEN avg_temp < 15 THEN '선선함'
                   WHEN avg_temp < 25 THEN '따뜻함'
                   ELSE '더움'
               END AS temp_group
             , SUM(review_count) AS total_review_count
          FROM recipe_daily_reaction
         WHERE avg_temp IS NOT NULL
         GROUP BY CASE
                      WHEN avg_temp < 5 THEN '추움'
                      WHEN avg_temp < 15 THEN '선선함'
                      WHEN avg_temp < 25 THEN '따뜻함'
                      ELSE '더움'
                  END
    """)

    df = pd.read_sql(sql, engine)
    order = ["추움", "선선함", "따뜻함", "더움"]
    df["temp_group"] = pd.Categorical(df["temp_group"], categories=order, ordered=True)
    df = df.sort_values("temp_group")

    plt.figure(figsize=(8, 5))
    plt.bar(df["temp_group"], df["total_review_count"])
    plt.title("온도 구간별 총 후기 반응")
    plt.xlabel("온도 구간")
    plt.ylabel("총 후기 수")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/temp_group_review_count.png", dpi=200)
    plt.close()


def save_temp_category_chart():
    sql = text("""
        SELECT CASE
                   WHEN D.avg_temp < 5 THEN '추움'
                   WHEN D.avg_temp < 15 THEN '선선함'
                   WHEN D.avg_temp < 25 THEN '따뜻함'
                   ELSE '더움'
               END AS temp_group
             , COALESCE(R.category_type, '미분류') AS category_type
             , SUM(D.review_count) AS total_review_count
          FROM recipe_daily_reaction D
         INNER JOIN raw_recipe R
            ON R.recipe_id = D.recipe_id
         WHERE D.avg_temp IS NOT NULL
         GROUP BY CASE
                      WHEN D.avg_temp < 5 THEN '추움'
                      WHEN D.avg_temp < 15 THEN '선선함'
                      WHEN D.avg_temp < 25 THEN '따뜻함'
                      ELSE '더움'
                  END
                , COALESCE(R.category_type, '미분류')
    """)

    df = pd.read_sql(sql, engine)
    order = ["추움", "선선함", "따뜻함", "더움"]
    df["temp_group"] = pd.Categorical(df["temp_group"], categories=order, ordered=True)

    pivot_df = df.pivot_table(
        index="temp_group",
        columns="category_type",
        values="total_review_count",
        aggfunc="sum",
        fill_value=0
    )

    ax = pivot_df.plot(kind="bar", figsize=(12, 6))
    plt.title("온도 구간별 음식 카테고리 후기 반응")
    plt.xlabel("온도 구간")
    plt.ylabel("총 후기 수")
    plt.xticks(rotation=0)
    plt.legend(title="카테고리", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/temp_group_category_review.png", dpi=200)
    plt.close()


def save_season_taste_heatmap():
    sql = text("""
        SELECT D.season_type
             , T.main_taste
             , SUM(D.review_count) AS total_review_count
          FROM recipe_daily_reaction D
         INNER JOIN recipe_taste_score T
            ON T.recipe_id = D.recipe_id
         WHERE D.season_type IS NOT NULL
           AND T.main_taste IS NOT NULL
         GROUP BY D.season_type
                , T.main_taste
    """)

    df = pd.read_sql(sql, engine)

    season_order = ["봄", "여름", "가을", "겨울"]
    taste_order = ["매콤함", "고소함", "달콤함", "새콤함", "짭짤함", "담백함", "미분류"]

    pivot_df = df.pivot_table(
        index="season_type",
        columns="main_taste",
        values="total_review_count",
        aggfunc="sum",
        fill_value=0
    )

    pivot_df = pivot_df.reindex(index=season_order)
    pivot_df = pivot_df.reindex(columns=[col for col in taste_order if col in pivot_df.columns])

    plt.figure(figsize=(10, 5))
    plt.imshow(pivot_df.values, aspect="auto")

    plt.title("계절별 대표 맛 후기 반응")
    plt.xlabel("대표 맛")
    plt.ylabel("계절")
    plt.xticks(range(len(pivot_df.columns)), pivot_df.columns, rotation=45)
    plt.yticks(range(len(pivot_df.index)), pivot_df.index)

    for i in range(len(pivot_df.index)):
        for j in range(len(pivot_df.columns)):
            value = int(pivot_df.iloc[i, j])
            plt.text(j, i, value, ha="center", va="center")

    plt.colorbar(label="총 후기 수")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/season_taste_heatmap.png", dpi=200)
    plt.close()


def save_weather_corr_heatmap():
    sql = text("""
        SELECT review_count
             , avg_temp
             , min_temp
             , max_temp
             , avg_humidity
             , rainfall
          FROM recipe_daily_reaction
         WHERE avg_temp IS NOT NULL
           AND avg_humidity IS NOT NULL
           AND rainfall IS NOT NULL
    """)

    df = pd.read_sql(sql, engine)
    corr_df = df.corr(numeric_only=True)

    plt.figure(figsize=(8, 6))
    plt.imshow(corr_df.values, aspect="auto", vmin=-1, vmax=1)

    plt.title("날씨 변수와 후기 수 상관관계")
    plt.xticks(range(len(corr_df.columns)), corr_df.columns, rotation=45)
    plt.yticks(range(len(corr_df.index)), corr_df.index)

    for i in range(len(corr_df.index)):
        for j in range(len(corr_df.columns)):
            value = corr_df.iloc[i, j]
            plt.text(j, i, f"{value:.2f}", ha="center", va="center")

    plt.colorbar(label="상관계수")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/weather_corr_heatmap.png", dpi=200)
    plt.close()


def main():
    setup()

    save_rain_review_chart()
    save_temp_group_chart()
    save_temp_category_chart()
    save_season_taste_heatmap()
    save_weather_corr_heatmap()

    print(f"done. charts saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()