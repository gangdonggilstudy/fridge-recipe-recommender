from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "outputs" / "tag_frequency.csv"

OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_SCATTER_PNG = OUTPUT_DIR / "tag_seed_dimension_scatter.png"
OUTPUT_SUMMARY_PNG = OUTPUT_DIR / "tag_seed_dimension_summary.png"
OUTPUT_POINTS_CSV = OUTPUT_DIR / "tag_seed_dimension_points.csv"
OUTPUT_MAPPING_CSV = OUTPUT_DIR / "tag_keyword_mapping_by_seed_visual.csv"


MIN_COUNT = 2
MIN_SIMILARITY = 0.12
LABEL_TOP_N_PER_KEYWORD = 12


REVIEW_KEYWORD_SEEDS: dict[str, list[str]] = {
    "가벼움": [
        "다이어트",
        "저칼로리",
        "담백",
        "건강식",
        "가벼운",
        "브런치",
        "아침메뉴",
    ],
    "신선함": [
        "샐러드",
        "야채",
        "채소",
        "제철",
        "상큼",
        "오이",
        "토마토",
        "쑥갓",
        "달래",
    ],
    "든든함": [
        "한끼",
        "한그릇",
        "집밥",
        "반찬",
        "밥반찬",
        "국밥",
        "볶음밥",
        "덮밥",
        "찌개",
        "국",
        "탕",
        "라면",
        "잡채",
    ],
    "푸짐함": [
        "고기",
        "소고기",
        "돼지고기",
        "닭고기",
        "닭",
        "메인반찬",
        "손님초대",
        "홈파티",
        "파티",
        "스테이크",
        "갈비",
        "닭볶음탕",
    ],
    "자극적": [
        "매운",
        "매콤",
        "얼큰",
        "칼칼",
        "고추장",
        "김치찌개",
        "떡볶이",
        "마라",
        "쯔란",
        "술안주",
        "야식",
        "해장",
    ],
    "부드러움": [
        "아이반찬",
        "아이간식",
        "아기반찬",
        "유아식",
        "죽",
        "계란찜",
        "달걀",
        "두부",
        "순두부",
        "크림",
        "치즈",
        "부드러운",
    ],
}


NOISE_SUFFIXES = [
    "황금레시피",
    "만드는방법",
    "만드는법",
    "만들기",
    "끓이는법",
    "요리법",
    "조리법",
    "레시피",
    "요리",
]


STOPWORDS_EXACT = {
    "",
    "요리",
    "레시피",
    "재료",
    "방법",
    "양념",
    "만드는법",
    "만들기",
    "끓이는법",
    "요리법",
    "황금레시피",
}


DROP_PATTERNS = [
    "시어머니",
    "엄마",
    "아빠",
    "할머니",
    "백종원",
    "편스토랑",
    "알토란",
    "수미네",
    "추억",
    "누구나좋아하는",
]


def set_korean_font() -> None:
    plt.rcParams["font.family"] = [
        "Malgun Gothic",
        "AppleGothic",
        "NanumGothic",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def normalize_raw_tag(value) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if not text or text.lower() == "nan":
        return ""

    return (
        text
        .replace("#", "")
        .replace(" ", "")
        .replace("_", "")
        .strip()
    )


def clean_tag(value) -> str:
    tag = normalize_raw_tag(value)

    if not tag:
        return ""

    if any(pattern in tag for pattern in DROP_PATTERNS):
        return ""

    changed = True

    while changed:
        changed = False

        for suffix in NOISE_SUFFIXES:
            if tag.endswith(suffix) and len(tag) > len(suffix):
                tag = tag[: -len(suffix)]
                changed = True

    tag = tag.strip()

    if tag in STOPWORDS_EXACT:
        return ""

    if len(tag) <= 1:
        return ""

    return tag


def find_direct_keywords(tag: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for keyword, seeds in REVIEW_KEYWORD_SEEDS.items():
        for seed in seeds:
            seed_text = clean_tag(seed)

            if not seed_text:
                continue

            if seed_text in tag:
                if keyword not in seen:
                    result.append(keyword)
                    seen.add(keyword)

    return result


def build_seed_vectors(vectorizer: TfidfVectorizer):
    seed_labels: list[str] = []
    seed_texts: list[str] = []

    for keyword, seeds in REVIEW_KEYWORD_SEEDS.items():
        for seed in seeds:
            cleaned = clean_tag(seed)
            if cleaned:
                seed_labels.append(keyword)
                seed_texts.append(cleaned)

    return seed_labels, seed_texts


def save_summary_png(summary_df: pd.DataFrame) -> None:
    show_df = summary_df.copy()

    fig, ax = plt.subplots(figsize=(15, 6))
    ax.axis("off")

    table = ax.table(
        cellText=show_df.values,
        colLabels=show_df.columns,
        loc="center",
        cellLoc="left",
        colLoc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.6)

    plt.title("6개 리뷰 인상 차원별 대표 태그", fontsize=18, pad=20)
    plt.tight_layout()
    plt.savefig(OUTPUT_SUMMARY_PNG, dpi=200)
    plt.close()


def main() -> None:
    set_korean_font()

    df = pd.read_csv(INPUT_PATH)

    df["original_tag"] = df["tag"].map(normalize_raw_tag)
    df["clean_tag"] = df["tag"].map(clean_tag)
    df["count"] = df["count"].fillna(1).astype(int)

    df = df[
        (df["clean_tag"] != "")
        & (df["count"] >= MIN_COUNT)
    ].copy()

    grouped_df = (
        df.groupby("clean_tag", as_index=False)
        .agg(
            count=("count", "sum"),
            original_tags=("original_tag", lambda x: ", ".join(sorted(set(x))[:10])),
        )
    )

    grouped_df = grouped_df.sort_values("count", ascending=False).reset_index(drop=True)

    tags = grouped_df["clean_tag"].tolist()

    seed_labels, seed_texts = build_seed_vectors(None)

    all_texts = tags + seed_texts

    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 5),
        min_df=1,
    )

    vectors = vectorizer.fit_transform(all_texts)

    tag_vectors = vectors[: len(tags)]
    seed_vectors = vectors[len(tags):]

    keyword_names = list(REVIEW_KEYWORD_SEEDS.keys())

    # 2차원 축소: 시각화용
    reducer = TruncatedSVD(
        n_components=2,
        random_state=42,
    )

    points = reducer.fit_transform(tag_vectors)

    grouped_df["x"] = points[:, 0]
    grouped_df["y"] = points[:, 1]

    # seed 유사도 계산
    for keyword in keyword_names:
        indexes = [
            idx
            for idx, label in enumerate(seed_labels)
            if label == keyword
        ]

        seed_group_vectors = seed_vectors[indexes]

        # 해당 차원의 seed 중 가장 가까운 값 사용
        sim = cosine_similarity(tag_vectors, seed_group_vectors).max(axis=1)

        grouped_df[f"sim_{keyword}"] = sim

    result_keywords: list[str] = []
    result_scores: list[float] = []
    result_reasons: list[str] = []

    for _, row in grouped_df.iterrows():
        tag = row["clean_tag"]

        direct_keywords = find_direct_keywords(tag)

        if direct_keywords:
            keyword = direct_keywords[0]
            result_keywords.append(keyword)
            result_scores.append(1.0)
            result_reasons.append("seed 직접 포함")
            continue

        scores = {
            keyword: float(row[f"sim_{keyword}"])
            for keyword in keyword_names
        }

        best_keyword = max(scores, key=scores.get)
        best_score = scores[best_keyword]

        if best_score < MIN_SIMILARITY:
            result_keywords.append("미분류")
            result_scores.append(best_score)
            result_reasons.append("유사도 낮음")
            continue

        result_keywords.append(best_keyword)
        result_scores.append(best_score)
        result_reasons.append("TF-IDF seed 유사도")

    grouped_df["review_keyword"] = result_keywords
    grouped_df["similarity"] = result_scores
    grouped_df["reason"] = result_reasons

    grouped_df.to_csv(
        OUTPUT_POINTS_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    mapping_df = grouped_df[grouped_df["review_keyword"] != "미분류"].copy()

    mapping_df[[
        "clean_tag",
        "review_keyword",
        "similarity",
        "count",
        "reason",
        "original_tags",
    ]].rename(
        columns={
            "clean_tag": "tag_pattern",
        }
    ).to_csv(
        OUTPUT_MAPPING_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    # 요약 표 생성
    summary_rows: list[dict] = []

    for keyword in keyword_names:
        part = grouped_df[grouped_df["review_keyword"] == keyword].copy()
        part = part.sort_values(["count", "similarity"], ascending=[False, False])

        summary_rows.append(
            {
                "리뷰 인상 차원": keyword,
                "태그 수": len(part),
                "등장 횟수": int(part["count"].sum()),
                "대표 태그": ", ".join(part["clean_tag"].head(12).tolist()),
            }
        )

    unmapped = grouped_df[grouped_df["review_keyword"] == "미분류"].copy()

    summary_rows.append(
        {
            "리뷰 인상 차원": "미분류",
            "태그 수": len(unmapped),
            "등장 횟수": int(unmapped["count"].sum()),
            "대표 태그": ", ".join(
                unmapped.sort_values("count", ascending=False)["clean_tag"].head(12).tolist()
            ),
        }
    )

    summary_df = pd.DataFrame(summary_rows)
    save_summary_png(summary_df)

    # 산점도 시각화
    plt.figure(figsize=(16, 10))

    color_map = {
        "가벼움": "#4C78A8",
        "신선함": "#54A24B",
        "든든함": "#F58518",
        "푸짐함": "#B279A2",
        "자극적": "#E45756",
        "부드러움": "#72B7B2",
        "미분류": "#BDBDBD",
    }

    for keyword in keyword_names + ["미분류"]:
        part = grouped_df[grouped_df["review_keyword"] == keyword]

        if part.empty:
            continue

        plt.scatter(
            part["x"],
            part["y"],
            s=part["count"].clip(upper=20) * 25,
            alpha=0.65,
            label=keyword,
            color=color_map[keyword],
        )

    # 각 키워드별 빈도 상위 태그만 라벨 표시
    label_parts = []

    for keyword in keyword_names:
        part = grouped_df[grouped_df["review_keyword"] == keyword]
        label_parts.append(
            part.sort_values("count", ascending=False).head(LABEL_TOP_N_PER_KEYWORD)
        )

    label_df = pd.concat(label_parts, ignore_index=True)

    for _, row in label_df.iterrows():
        plt.text(
            row["x"],
            row["y"],
            row["clean_tag"],
            fontsize=9,
            alpha=0.9,
        )

    plt.title("해시태그 seed 유사도 기반 6개 리뷰 인상 차원 시각화", fontsize=18)
    plt.xlabel("TF-IDF 문자 n-gram 축소 차원 1")
    plt.ylabel("TF-IDF 문자 n-gram 축소 차원 2")
    plt.grid(True, alpha=0.25)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(OUTPUT_SCATTER_PNG, dpi=200)
    plt.close()

    print(f"정제 후 태그 수: {len(grouped_df)}")
    print(f"매핑 태그 수: {len(mapping_df)}")
    print(f"미분류 태그 수: {len(unmapped)}")
    print(f"저장 완료: {OUTPUT_SCATTER_PNG}")
    print(f"저장 완료: {OUTPUT_SUMMARY_PNG}")
    print(f"저장 완료: {OUTPUT_POINTS_CSV}")
    print(f"저장 완료: {OUTPUT_MAPPING_CSV}")


if __name__ == "__main__":
    main()