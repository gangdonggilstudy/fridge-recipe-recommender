from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "outputs" / "tag_frequency.csv"
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAPPING_OUTPUT = OUTPUT_DIR / "tag_keyword_mapping.csv"
SIMILARITY_OUTPUT = OUTPUT_DIR / "tag_seed_similarity.csv"
UNMAPPED_OUTPUT = OUTPUT_DIR / "tag_unmapped.csv"


REVIEW_KEYWORD_SEEDS: dict[str, list[str]] = {
    "가벼움": [
        "다이어트",
        "다이어트메뉴",
        "다이어트레시피",
        "저칼로리",
        "간단요리",
        "초간단",
        "전자레인지요리",
        "브런치",
        "간식",
    ],
    "신선함": [
        "샐러드",
        "야채",
        "채소",
        "제철",
        "제철음식",
        "상큼",
        "과일",
        "봄요리",
        "여름요리",
    ],
    "든든함": [
        "한끼",
        "집밥",
        "반찬",
        "밥반찬",
        "밑반찬",
        "국밥",
        "볶음밥",
        "덮밥",
        "찌개",
        "국물요리",
    ],
    "푸짐함": [
        "고기요리",
        "소고기",
        "돼지고기",
        "닭고기",
        "손님초대",
        "홈파티",
        "파티요리",
        "메인반찬",
        "닭볶음탕",
        "스테이크",
    ],
    "자극적": [
        "매운",
        "매콤",
        "얼큰",
        "칼칼",
        "해장",
        "술안주",
        "야식",
        "고추장",
        "김치찌개",
        "떡볶이",
    ],
    "부드러움": [
        "아이반찬",
        "아이간식",
        "아기반찬",
        "죽",
        "계란찜",
        "두부",
        "순두부",
        "크림",
        "치즈",
        "부드러운",
    ],
}


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
    "만드는방법",
}


MIN_SIMILARITY = 0.18


def normalize_tag(value) -> str:
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


def main() -> None:
    df = pd.read_csv(INPUT_PATH)

    df["tag"] = df["tag"].map(normalize_tag)
    df["count"] = df["count"].fillna(1).astype(int)

    df = df[df["tag"] != ""].copy()

    df["is_stopword"] = df["tag"].isin(STOPWORDS)

    target_df = df[~df["is_stopword"]].copy()

    tags = target_df["tag"].tolist()

    seed_labels: list[str] = []
    seed_texts: list[str] = []

    for keyword, seeds in REVIEW_KEYWORD_SEEDS.items():
        for seed in seeds:
            seed_labels.append(keyword)
            seed_texts.append(normalize_tag(seed))

    all_texts = tags + seed_texts

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        min_df=1,
    )

    vectors = vectorizer.fit_transform(all_texts)

    tag_vectors = vectors[: len(tags)]
    seed_vectors = vectors[len(tags):]

    similarities = []

    for keyword in REVIEW_KEYWORD_SEEDS.keys():
        indexes = [
            idx
            for idx, label in enumerate(seed_labels)
            if label == keyword
        ]

        seed_group_vectors = seed_vectors[indexes]

        # 각 태그와 해당 키워드 seed들 간 유사도를 계산한 뒤 평균값 사용
        sim = cosine_similarity(tag_vectors, seed_group_vectors).mean(axis=1)

        similarities.append(sim.reshape(-1))

    keyword_names = list(REVIEW_KEYWORD_SEEDS.keys())

    similarity_df = target_df[["tag", "count"]].copy()

    for idx, keyword in enumerate(keyword_names):
        similarity_df[f"sim_{keyword}"] = similarities[idx]

    result_rows = []

    for _, row in similarity_df.iterrows():
        scores = {
            keyword: float(row[f"sim_{keyword}"])
            for keyword in keyword_names
        }

        best_keyword = max(scores, key=scores.get)
        best_score = scores[best_keyword]

        if best_score < MIN_SIMILARITY:
            continue

        result_rows.append(
            {
                "tag_pattern": row["tag"],
                "review_keyword": best_keyword,
                "similarity": round(best_score, 4),
                "count": int(row["count"]),
                "reason": f"TF-IDF seed 유사도 기준 자동 매핑: {best_keyword}",
            }
        )

    mapping_df = pd.DataFrame(result_rows)
    mapping_df = mapping_df.sort_values(
        ["review_keyword", "count", "similarity"],
        ascending=[True, False, False],
    )

    mapped_tags = set(mapping_df["tag_pattern"].tolist())

    unmapped_df = target_df[~target_df["tag"].isin(mapped_tags)].copy()
    unmapped_df = unmapped_df.sort_values("count", ascending=False)

    similarity_df = similarity_df.sort_values("count", ascending=False)

    mapping_df.to_csv(MAPPING_OUTPUT, index=False, encoding="utf-8-sig")
    similarity_df.to_csv(SIMILARITY_OUTPUT, index=False, encoding="utf-8-sig")
    unmapped_df.to_csv(UNMAPPED_OUTPUT, index=False, encoding="utf-8-sig")

    print(f"전체 태그 수: {len(df)}")
    print(f"분류 대상 태그 수: {len(target_df)}")
    print(f"매핑 태그 수: {len(mapping_df)}")
    print(f"미분류 태그 수: {len(unmapped_df)}")
    print(f"saved: {MAPPING_OUTPUT}")
    print(f"saved: {SIMILARITY_OUTPUT}")
    print(f"saved: {UNMAPPED_OUTPUT}")


if __name__ == "__main__":
    main()