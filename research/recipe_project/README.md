# 냉장고 속 재료 기반 레시피 수집·분석 프로젝트

만개의레시피 데이터를 수집하여 레시피의 **재료, 맛, 계절성, 후기 반응도, 날씨 정보, 레시피 간 유사도, K-means 클러스터링**을 분석하는 프로젝트입니다.

본 프로젝트는 `fridge-recipe-recommender` 추천 앱에서 사용할 레시피 데이터를 만들기 위한 수집·분석 파이프라인입니다.

전체 흐름은 아래와 같습니다.

```text
레시피 수집
→ 재료 추출
→ 메인 재료 판정
→ 맛 점수 계산
→ 계절 점수 계산
→ 유사도/클러스터링 분석
→ 후기/날씨 반응 분석
→ 앱용 CSV 생성
→ 추천 앱 DB 빌드
```

---

## 1. 프로젝트 개요

### 1.1 분석 목표

| 분석 주제         | 설명                                     |
| ------------- | -------------------------------------- |
| 레시피 원천 수집     | 만개의레시피에서 종류별, 재료별, 조리방법별 레시피를 수집합니다.   |
| 재료 정제         | 레시피 재료 문자열에서 재료명과 수량을 분리합니다.           |
| 메인 재료 판정      | 제목, 태그, 재료 목록을 기준으로 핵심 재료를 표시합니다.      |
| 맛 점수 계산       | 재료 키워드를 기준으로 6가지 맛 점수를 계산합니다.          |
| 계절 점수 계산      | 계절별 레시피의 대표 재료를 기준으로 계절 점수를 계산합니다.     |
| 레시피 유사도 계산    | 재료, 맛, 카테고리를 기준으로 레시피 간 유사도를 계산합니다.    |
| K-means 클러스터링 | 비슷한 특성을 가진 레시피를 그룹화합니다.                |
| 후기/날씨 반응 분석   | 후기 작성일과 날씨 데이터를 결합하여 반응도를 분석합니다.       |
| 시각화           | 회귀 그래프, 분포 그래프, PCA 산점도, 히트맵 등을 생성합니다. |

---

## 2. 프로젝트 디렉터리 구조

```text
recipe_project/
├── README.md
├── requirements.txt
├── config.py
│
├── analysis/
│   ├── cook_time_review_regression.py
│   ├── difficulty_review_analysis.py
│   ├── recipe_regression_analysis.py
│   └── review_count_distribution.py
│
├── crawler/
│   ├── crawl_list.py
│   ├── crawl_detail.py
│   ├── crawl_theme.py
│   ├── crawl_review.py
│   └── run_full_crawl.py
│
├── data/
│   └── recipe_project.db
│
├── db/
│   ├── connection.py
│   ├── repository.py
│   ├── repository_mysql.py
│   ├── repository_sqlite.py
│   ├── schema_mysql.sql
│   └── schema_sqlite.sql
│
├── pipeline/
│   ├── ingredient_parser.py
│   ├── main_ingredient_extractor.py
│   ├── taste_score_calculator.py
│   ├── season_score_calculator.py
│   ├── similarity_calculator.py
│   └── kmeans_feature_filter.py
│
├── scripts/
│   ├── init_db.py
│   ├── run_crawler_by_type.py
│   ├── run_crawler_season_theme.py
│   ├── run_extract_ingredients.py
│   ├── run_mark_main_ingredients.py
│   ├── run_calculate_taste_scores.py
│   ├── run_calculate_season_scores.py
│   ├── run_calculate_recipe_similarity.py
│   ├── run_kmeans_clustering.py
│   ├── plot_kmeans_pca.py
│   ├── run_crawler_reviews.py
│   ├── run_collect_weather_daily.py
│   ├── run_build_recipe_daily_reaction.py
│   └── plot_weather_reaction_analysis.py
│
└── outputs/
    ├── charts/
    ├── kmeans_pca_scatter.png
    └── weather/
```

---

## 3. 주요 디렉터리 역할

### 3.1 `crawler/`

만개의레시피 웹페이지에서 데이터를 수집하는 모듈입니다.

| 파일                | 역할                                                        |
| ----------------- | --------------------------------------------------------- |
| `crawl_list.py`   | 카테고리/목록 페이지에서 레시피 ID를 수집합니다.                              |
| `crawl_theme.py`  | 테마 URL 기준으로 여러 페이지를 돌며 레시피 ID를 수집합니다.                     |
| `crawl_detail.py` | 레시피 상세 페이지에서 제목, 요약, 재료, 조리순서, 태그, 조회수, 스크랩수, 후기수를 수집합니다. |
| `crawl_review.py` | 레시피 상세 페이지에서 후기 목록을 파싱합니다.                                |

---

### 3.2 `db/`

DB 연결과 저장/조회 함수를 관리합니다.

| 파일                     | 역할                                           |
| ---------------------- | -------------------------------------------- |
| `connection.py`        | DB 연결 엔진을 생성합니다.                             |
| `repository.py`        | DB 종류에 따라 MySQL 또는 SQLite repository를 선택합니다. |
| `repository_sqlite.py` | SQLite용 저장/조회 쿼리를 관리합니다.                     |
| `repository_mysql.py`  | MySQL용 저장/조회 쿼리를 관리합니다.                      |
| `schema_sqlite.sql`    | SQLite 테이블 생성 스크립트입니다.                       |
| `schema_mysql.sql`     | MySQL 테이블 생성 스크립트입니다.                        |

현재 기본 실행은 SQLite 기준입니다.

---

### 3.3 `pipeline/`

수집된 데이터를 분석 가능한 형태로 가공합니다.

| 파일                             | 역할                                   |
| ------------------------------ | ------------------------------------ |
| `ingredient_parser.py`         | 재료 문자열에서 재료명을 정제합니다.                 |
| `main_ingredient_extractor.py` | 제목/태그/제외재료 기준으로 메인 재료를 판정합니다.        |
| `taste_score_calculator.py`    | 재료 키워드 기반으로 맛 점수를 계산합니다.             |
| `season_score_calculator.py`   | 계절 대표 재료와 레시피 재료를 비교하여 계절 점수를 계산합니다. |
| `similarity_calculator.py`     | 재료/맛/카테고리 유사도를 계산합니다.                |
| `kmeans_feature_filter.py`     | K-means 분석에서 제외할 재료/도구/수량값을 필터링합니다.  |

---

### 3.4 `scripts/`

실제 수집, 분석, 시각화를 실행하는 파일입니다.

| 파일                                   | 역할                            |
| ------------------------------------ | ----------------------------- |
| `init_db.py`                         | SQLite DB를 초기화합니다.            |
| `run_crawler_by_type.py`             | 종류별, 재료별, 방법별 레시피를 수집합니다.     |
| `run_crawler_season_theme.py`        | 봄/여름/가을/겨울 계절 테마 레시피를 수집합니다.  |
| `run_extract_ingredients.py`         | 레시피 재료 문자열을 재료 테이블로 분리 저장합니다. |
| `run_mark_main_ingredients.py`       | 레시피별 메인 재료를 표시합니다.            |
| `run_calculate_taste_scores.py`      | 레시피별 맛 점수를 계산합니다.             |
| `run_calculate_season_scores.py`     | 레시피별 계절 점수를 계산합니다.            |
| `run_calculate_recipe_similarity.py` | 레시피 간 유사도를 계산합니다.             |
| `run_kmeans_clustering.py`           | K-means 클러스터링을 실행합니다.         |
| `plot_kmeans_pca.py`                 | K-means 결과를 PCA 산점도로 시각화합니다.  |
| `run_crawler_reviews.py`             | 레시피별 후기를 수집합니다.               |
| `run_collect_weather_daily.py`       | 일자별 날씨 데이터를 수집합니다.            |
| `run_build_recipe_daily_reaction.py` | 레시피-날짜 단위 후기 반응 데이터를 생성합니다.   |
| `plot_weather_reaction_analysis.py`  | 날씨/계절/맛 기반 반응 그래프를 생성합니다.     |

---

## 4. 실행환경 설정 및 실행 방법

### 4.1 실행 위치

수집과 분석은 `recipe_project` 폴더에서 실행합니다.

```bash
cd fridge-recipe-recommender/research/recipe_project
```

---

### 4.2 가상환경 생성

처음 한 번만 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate #mac
.\.venv\Scripts\activate #windows
```

---

### 4.3 패키지 설치

```bash
python -m pip install -r requirements.txt
```

---

### 4.4 SQLite DB 초기화

```bash
python -m scripts.init_db
```

SQLite는 별도 DB 서버를 실행할 필요가 없습니다.
수집 데이터는 `data/recipe_project.db` 파일에 저장됩니다.

---

### 4.5 처음 수집 예시

처음에는 종류별 레시피를 20개씩 수집합니다.

```bash
python -m scripts.run_crawler_by_type --collect-kind category --limit 20 --sleep 0.5 --max-page 10
```

위 명령어는 전체 20개가 아니라, 종류별로 20개씩 수집합니다.

```text
메인반찬 20개
국/탕 20개
찌개 20개
면/만두 20개
밥/죽/떡 20개
양식 20개
```

`--collect-kind category`에서 `category` 부분을 바꾸면 다른 기준으로 수집할 수 있습니다.

| 값            | 설명       |
| ------------ | -------- |
| `category`   | 종류별 수집   |
| `ingredient` | 재료별 수집   |
| `method`     | 조리방법별 수집 |

예시:

```bash
python -m scripts.run_crawler_by_type --collect-kind ingredient --limit 20 --sleep 0.5 --max-page 10
```

```bash
python -m scripts.run_crawler_by_type --collect-kind method --limit 20 --sleep 0.5 --max-page 10
```

`--limit 20` 값을 `50`, `100`, `400`처럼 바꾸면 그룹별 수집 개수를 늘릴 수 있습니다.

특정 연도 데이터만 수집하려면 `--target-year` 옵션을 추가합니다.
예를 들어 2025년에 등록된 레시피만 종류별로 100개씩 수집하려면 아래처럼 실행합니다.

```bash
python -m scripts.run_crawler_by_type --collect-kind category --target-year 2025 --limit 100 --sleep 0.5 --max-page 300
```

위 명령어는 최신순으로 레시피 목록을 탐색하면서 2025년 데이터가 나오는 지점부터 수집합니다.

| 옵션               | 설명                                                |
| ---------------- | ------------------------------------------------- |
| `--collect-kind` | 수집 기준 선택. `category`, `ingredient`, `method` 중 선택 |
| `--target-year`  | 특정 연도에 등록된 레시피만 수집                                |
| `--limit`        | 그룹별 수집 개수                                         |
| `--sleep`        | 요청 사이 대기 시간                                       |
| `--max-page`     | 그룹별 최대 탐색 페이지 수                                   |

`--target-year`를 생략하면 특정 연도 제한 없이 최신순으로 수집합니다. 2025년처럼 이전 연도 데이터를 찾는 경우에는 최신 데이터가 앞에 많이 있을 수 있으므로 `--max-page` 값을 넉넉하게 지정하는 것이 좋습니다.

---

### 4.6 계절별 레시피 수집

계절 점수를 계산하려면 봄/여름/가을/겨울 계절 테마 레시피를 수집합니다.

```bash
python -m scripts.run_crawler_season_theme --limit 20 --sleep 0.5 --max-page 10
```

---

### 4.7 기본 분석 실행 순서

```bash
python -m scripts.run_extract_ingredients
python -m scripts.run_mark_main_ingredients
python -m scripts.run_calculate_taste_scores
python -m scripts.run_calculate_season_scores
```

---

### 4.8 앱용 CSV 생성 및 앱 DB 빌드

수집·분석한 데이터를 추천 앱에서 사용하려면 앱 루트로 이동합니다.

```bash
deactivate

cd fridge-recipe-recommender
source .venv/bin/activate
```

앱용 CSV를 생성합니다.

```bash
python recipes/tools/export_from_recipe_project.py
```

추천 앱이 읽는 `recipes.db`를 빌드합니다.

```bash
python recipes/tools/build_recipes.py
```

앱을 실행합니다.

```bash
python run.py
```

---

## 5. 데이터베이스 테이블 구성

현재 기본 DB는 SQLite입니다.

### 5.1 원천 데이터 테이블

| 테이블                      | 설명                                                             |
| ------------------------ | -------------------------------------------------------------- |
| `raw_recipe`             | 레시피 상세 원천 데이터입니다. 제목, 요약, 재료, 조리순서, 태그, 조회수, 스크랩수, 후기수를 저장합니다. |
| `raw_ingredients`        | 정제된 재료명 목록입니다.                                                 |
| `raw_recipe_ingredients` | 레시피별 재료 매핑 정보입니다. 재료명, 원문, 메인 재료 여부를 저장합니다.                    |
| `raw_recipe_review`      | 레시피별 후기 원천 데이터입니다.                                             |

---

### 5.2 분석 결과 테이블

| 테이블                     | 설명                                      |
| ----------------------- | --------------------------------------- |
| `recipe_taste_score`    | 매콤함, 고소함, 달콤함, 새콤함, 짭짤함, 담백함 점수를 저장합니다. |
| `recipe_season_theme`   | 봄/여름/가을/겨울 테마에서 수집된 레시피 매핑 정보를 저장합니다.   |
| `recipe_season_score`   | 봄/여름/가을/겨울 계절 점수와 대표 계절을 저장합니다.         |
| `recipe_similarity`     | 레시피 간 재료/맛/카테고리 유사도를 저장합니다.             |
| `recipe_cluster_result` | K-means 클러스터링 결과를 저장합니다.                |

---

### 5.3 후기/날씨 분석 테이블

| 테이블                     | 설명                                 |
| ----------------------- | ---------------------------------- |
| `weather_daily`         | 일자별 서울 기준 날씨 데이터를 저장합니다.           |
| `recipe_daily_reaction` | 레시피-날짜 단위 후기 수와 날씨 정보를 결합한 데이터입니다. |

---

### 5.4 정제 규칙 테이블

| 테이블                       | 설명                                                  |
| ------------------------- | --------------------------------------------------- |
| `ingredient_exclude_rule` | 메인 재료, 계절 대표 재료, K-means 피처에서 제외할 재료/도구/수량값을 관리합니다. |

---

## 6. 전체 데이터 수집 및 분석 파이프라인

전체 파이프라인은 아래 순서로 진행됩니다.

```text
1. 음식 종류별 레시피 수집
2. 계절별 레시피 수집
3. 재료 파싱
4. 메인 재료 판정
5. 맛 점수 계산
6. 계절 점수 계산
7. 레시피 간 유사도 계산
8. K-means 클러스터링
9. K-means PCA 산점도 생성
10. 요리 후기 수집
11. 날씨 데이터 수집
12. 레시피-날짜 단위 후기 반응 집계
13. 날씨/계절/맛 반응 시각화
14. 앱용 CSV 생성
15. 추천 앱 DB 빌드
```

---

## 7. 주요 실행 단계

### 7.1 음식 종류별 레시피 수집

만개의레시피의 종류별 카테고리에서 레시피를 수집합니다.

```bash
python -m scripts.run_crawler_by_type --collect-kind category --limit 20 --sleep 0.5 --max-page 10
```

수집 대상 예시는 다음과 같습니다.

```text
메인반찬
국/탕
찌개
면/만두
밥/죽/떡
양식
```

---

### 7.2 계절별 레시피 수집

봄/여름/가을/겨울 계절 테마 레시피를 수집합니다.

```bash
python -m scripts.run_crawler_season_theme --limit 20 --sleep 0.5 --max-page 10
```

계절 점수 계산을 위해 사용됩니다.

---

### 7.3 재료 파싱

수집된 레시피의 재료 문자열을 재료 단위로 분리합니다.

```bash
python -m scripts.run_extract_ingredients
```

예시:

```text
순두부,1봉/양파,1/2개/고추장,1큰술
```

위 문자열은 아래처럼 분리됩니다.

```text
순두부
양파
고추장
```

---

### 7.4 메인 재료 판정

레시피의 핵심 재료를 표시합니다.

```bash
python -m scripts.run_mark_main_ingredients
```

제목, 태그, 재료 목록, 제외 재료 규칙을 활용합니다.

---

### 7.5 맛 점수 계산

재료 키워드를 기준으로 6가지 맛 점수를 계산합니다.

```bash
python -m scripts.run_calculate_taste_scores
```

계산되는 맛은 다음과 같습니다.

| 맛   | 예시 키워드             |
| --- | ------------------ |
| 매콤함 | 고춧가루, 고추장, 청양고추    |
| 고소함 | 참기름, 들기름, 깨, 버터    |
| 달콤함 | 설탕, 올리고당, 물엿, 꿀    |
| 새콤함 | 식초, 매실액, 케찹        |
| 짭짤함 | 간장, 소금, 된장, 액젓     |
| 담백함 | 두부, 순두부, 닭가슴살, 콩나물 |

---

### 7.6 계절 점수 계산

계절별 레시피에서 자주 등장한 메인 재료를 대표 재료로 사용하고, 전체 레시피의 메인 재료와 비교하여 계절 점수를 계산합니다.

```bash
python -m scripts.run_calculate_season_scores
```

대표 재료 개수를 조정하려면 `--top-n`을 사용합니다.

```bash
python -m scripts.run_calculate_season_scores --top-n 15
```

---

### 7.7 레시피 간 유사도 계산

레시피 간 유사도를 계산합니다.

```bash
python -m scripts.run_calculate_recipe_similarity
```

유사도는 다음 요소를 조합합니다.

| 요소       | 설명          |
| -------- | ----------- |
| 재료 유사도   | 공통 재료 비율    |
| 맛 유사도    | 맛 점수 벡터 유사도 |
| 카테고리 유사도 | 같은 카테고리 여부  |

---

### 7.8 K-means 클러스터링

레시피를 비슷한 특성끼리 그룹화합니다.

```bash
python -m scripts.run_kmeans_clustering --clusters 5 --top-ingredients 30
```

사용 피처는 다음과 같습니다.

```text
맛 점수
메인 재료
카테고리
```

---

### 7.9 K-means PCA 산점도 생성

K-means 결과를 2차원 산점도로 시각화합니다.

```bash
python -m scripts.plot_kmeans_pca --top-ingredients 30
```

출력 파일:

```text
outputs/kmeans_pca_scatter.png
```

---

### 7.10 요리 후기 수집

레시피별 후기를 수집합니다.

```bash
python -m scripts.run_crawler_reviews --limit 10 --replace
```

더 많이 수집하려면 `--limit` 값을 늘리거나 생략합니다.

---

### 7.11 날씨 데이터 수집

후기 작성일과 결합할 서울 기준 날씨 데이터를 수집합니다.

```bash
python -m scripts.run_collect_weather_daily --start-date 2024-01-01 --end-date 2024-12-31
```

---

### 7.12 레시피-날짜 단위 후기 반응 집계

후기 데이터와 날씨 데이터를 날짜 기준으로 결합합니다.

```bash
python -m scripts.run_build_recipe_daily_reaction
```

---

### 7.13 날씨/계절/맛 반응 시각화

후기 반응과 날씨/계절/맛 정보를 그래프로 생성합니다.

```bash
python -m scripts.plot_weather_reaction_analysis
```

생성되는 주요 그래프는 다음과 같습니다.

| 파일                                               | 설명                    |
| ------------------------------------------------ | --------------------- |
| `outputs/weather/rain_review_count.png`          | 비 여부별 후기 반응 그래프       |
| `outputs/weather/temp_group_review_count.png`    | 온도 구간별 후기 반응 그래프      |
| `outputs/weather/temp_group_category_review.png` | 온도 구간별 카테고리 후기 반응 그래프 |
| `outputs/weather/season_taste_heatmap.png`       | 계절별 대표 맛 후기 반응 히트맵    |
| `outputs/weather/weather_corr_heatmap.png`       | 날씨 변수와 후기 수 상관관계 히트맵  |

---

### 7.14 추가 분석 그래프

`analysis/` 폴더에서는 레시피 반응도 관련 그래프를 생성합니다.

| 파일                               | 설명                 | 출력 예시                                            |
| -------------------------------- | ------------------ | ------------------------------------------------ |
| `review_count_distribution.py`   | 후기 수 분포 그래프        | `outputs/charts/review_count_distribution.png`   |
| `cook_time_review_regression.py` | 조리시간과 후기 수 회귀 분석   | `outputs/charts/cook_time_review_regression.png` |
| `difficulty_review_analysis.py`  | 난이도별 후기 반응 분석      | `outputs/charts/difficulty_review_bar.png`       |
| `recipe_regression_analysis.py`  | 레시피 특성과 후기 수 회귀 분석 | `outputs/charts/`                                |

---

## 8. 전체 실행 순서 요약

처음부터 앱 실행까지의 기본 순서는 다음과 같습니다.

```bash
# recipe_project 폴더에서 실행
cd fridge-recipe-recommender/research/recipe_project

python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python -m scripts.init_db

python -m scripts.run_crawler_by_type --collect-kind category --limit 20 --sleep 0.5 --max-page 10
python -m scripts.run_crawler_season_theme --limit 20 --sleep 0.5 --max-page 10

python -m scripts.run_extract_ingredients
python -m scripts.run_mark_main_ingredients
python -m scripts.run_calculate_taste_scores
python -m scripts.run_calculate_season_scores

python -m scripts.run_calculate_recipe_similarity
python -m scripts.run_kmeans_clustering --clusters 5 --top-ingredients 30
python -m scripts.plot_kmeans_pca --top-ingredients 30

python -m scripts.run_crawler_reviews --limit 10 --replace
python -m scripts.run_collect_weather_daily --start-date 2024-01-01 --end-date 2024-12-31
python -m scripts.run_build_recipe_daily_reaction
python -m scripts.plot_weather_reaction_analysis
```

추천 앱에 반영하려면 앱 루트에서 아래를 실행합니다.

```bash
deactivate

cd fridge-recipe-recommender
source .venv/bin/activate

python recipes/tools/export_from_recipe_project.py
python recipes/tools/build_recipes.py
python run.py
```

---

## 9. 분석 한계

| 한계            | 설명                                                           |
| ------------- | ------------------------------------------------------------ |
| 수집 데이터 한계     | 제한된 수량의 레시피만 수집하므로 전체 레시피를 대표한다고 보기 어렵습니다.                   |
| 사이트 노출 영향     | 후기 수, 조회수, 스크랩수는 레시피 품질뿐 아니라 사이트 노출도와 작성자 인지도 영향을 받을 수 있습니다. |
| 후기 작성일 한계     | 후기 작성일은 실제 요리한 날짜와 다를 수 있습니다.                                |
| 날씨 지역 한계      | 리뷰 작성자의 실제 위치를 알 수 없어 서울 기준 날씨를 대표값으로 사용합니다.                 |
| 계절 테마 한계      | 계절 점수는 학습 모델이 아니라 계절 테마 레시피의 대표 재료를 활용한 보조 지표입니다.            |
| Rule-based 한계 | 맛 점수와 메인 재료 판정은 규칙 기반이므로 모든 레시피에 완벽하게 맞지는 않습니다.              |
| 크롤링 의존성       | 웹사이트 HTML 구조가 바뀌면 크롤러 수정이 필요할 수 있습니다.                        |

---

## 10. 향후 개선 방향

| 개선 방향      | 설명                                                      |
| ---------- | ------------------------------------------------------- |
| 수집 범위 확대   | 종류별, 재료별, 방법별 수집량을 늘려 분석 표본을 확대합니다.                     |
| 레시피 등록일 수집 | 오래된 레시피가 후기 수에서 유리한 문제를 보정할 수 있습니다.                     |
| 인기도 점수 개선  | 조회수, 스크랩수, 후기수, 평점을 조합한 관심도 점수를 만들 수 있습니다.              |
| 맛 분류 고도화   | 재료 키워드 기반 규칙을 보완하거나 학습 모델로 확장할 수 있습니다.                  |
| 계절 점수 개선   | 계절별 대표 재료 사전을 더 정교하게 만들고, 후기 작성월과도 결합할 수 있습니다.          |
| 날씨 분석 개선   | 서울 기준이 아니라 사용자 지역 또는 주요 도시 평균 날씨로 확장할 수 있습니다.           |
| 추천 앱 연동 강화 | recipe_project에서 생성한 맛/계절/인기도 정보를 추천 점수에 직접 반영할 수 있습니다. |
| 대시보드화      | 수집 현황, 맛 분포, 계절 점수, 클러스터 결과를 화면에서 확인할 수 있도록 확장할 수 있습니다. |

---

## 11. 프로젝트 요약

이 프로젝트는 만개의레시피에서 레시피 데이터를 수집하고, 재료·맛·계절·후기·날씨 정보를 분석하여 추천 앱에서 사용할 수 있는 데이터로 변환하는 프로젝트입니다.

최종적으로는 사용자가 가진 재료를 기준으로, 비슷한 레시피를 찾고 계절성이나 반응도 정보를 함께 활용하는 추천 시스템으로 확장할 수 있습니다.
