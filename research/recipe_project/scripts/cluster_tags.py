from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "outputs" / "tag_frequency.csv"
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_TAGS = OUTPUT_DIR / "tag_clusters.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "tag_cluster_summary.csv"


STOPWORDS = {
    "레시피",
    "재료",
    "만드는법",
    "만들기",
    "끓이는법",
    "요리법",
    "황금레시피",
    "양념",
    "방법",
}


def normalize_tag(value: str) -> str:
    return (
        str(value)
        .replace("#", "")
        .replace(" ", "")
        .strip()
    )


def main() -> None:
    df = pd.read_csv(INPUT_PATH)

    df["tag"] = df["tag"].map(normalize_tag)
    df["count"] = df["count"].fillna(1).astype(int)

    df = df[
        (df["tag"] != "")
        & (~df["tag"].isin(STOPWORDS))
        & (df["count"] >= 2)
    ].copy()

    tags = df["tag"].tolist()

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        min_df=1,
    )

    x = vectorizer.fit_transform(tags)

    # 너무 6개로 바로 나누면 뭉개지므로, 먼저 20개 정도로 세분화
    kmeans = KMeans(
        n_clusters=20,
        random_state=42,
        n_init="auto",
    )

    df["cluster"] = kmeans.fit_predict(x, sample_weight=df["count"])

    df = df.sort_values(["cluster", "count"], ascending=[True, False])
    df.to_csv(OUTPUT_TAGS, index=False, encoding="utf-8-sig")

    summary_rows = []

    for cluster_no, group in df.groupby("cluster"):
        top_tags = group.sort_values("count", ascending=False).head(20)

        summary_rows.append(
            {
                "cluster": cluster_no,
                "tag_count": len(group),
                "total_frequency": int(group["count"].sum()),
                "top_tags": ", ".join(top_tags["tag"].tolist()),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values("total_frequency", ascending=False)
    summary_df.to_csv(OUTPUT_SUMMARY, index=False, encoding="utf-8-sig")

    print(f"saved: {OUTPUT_TAGS}")
    print(f"saved: {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()