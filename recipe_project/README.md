# 냉장고 속 재료 기반 개인 선호도 맞춤 레시피 추천 시스템

만개의레시피 데이터를 수집하여 레시피의 **재료, 맛, 계절성, 후기 반응도, 날씨 정보, 레시피 간 유사도, K-means 클러스터링**을 분석하는 프로젝트입니다.

본 프로젝트의 목적은 사용자가 보유한 재료 또는 선택한 레시피를 기준으로, 비슷한 레시피를 추천하고 계절/날씨/후기 반응도를 보조 지표로 활용하는 것입니다.

---

## 1. 프로젝트 개요

### 1.1 분석 목표

이 프로젝트에서는 다음 질문을 중심으로 데이터를 수집하고 분석합니다.

| 분석 주제 | 설명 |
|---|---|
| 레시피 원천 수집 | 만개의레시피의 카테고리별 레시피 상세 정보 수집 |
| 재료 정제 | 레시피의 재료명과 수량을 분리하고, 재료 마스터와 레시피-재료 매핑 생성 |
| 메인 재료 판정 | 제목/태그/제외재료 기준으로 레시피별 핵심 재료 표시 |
| 맛 점수 계산 | 재료 키워드 기반으로 매콤함/고소함/달콤함/새콤함/짭짤함/담백함 점수 산출 |
| 계절 점수 계산 | 제철요리 테마의 계절별 메인 재료를 기준으로 전체 레시피에 계절 점수 부여 |
| 레시피 유사도 계산 | 재료 유사도, 맛 유사도, 카테고리 유사도를 조합하여 레시피 간 유사도 계산 |
| K-means 클러스터링 | 맛 점수, 메인 재료, 카테고리를 기반으로 유사 레시피 그룹화 |
| 후기/날씨 반응도 분석 | 후기 작성일과 서울 기준 날씨 데이터를 결합하여 날씨별 레시피 반응 분석 |
| 시각화 | K-means PCA 산점도, 날씨별 후기 반응 그래프 등 생성 |

---

## 2. 프로젝트 디렉터리 구조

```text
recipe_project/
├─ README.md
├─ requirements.txt
├─ config.py
├─ db_schema.sql
├─ .env
│
├─ crawler/
│  ├─ __init__.py
│  ├─ crawl_list.py
│  ├─ crawl_detail.py
│  ├─ crawl_theme.py
│  └─ crawl_review.py
│
├─ db/
│  ├─ __init__.py
│  ├─ connection.py
│  └─ repository.py
│
├─ pipeline/
│  ├─ __init__.py
│  ├─ ingredient_parser.py
│  ├─ main_ingredient_extractor.py
│  ├─ taste_score_calculator.py
│  ├─ season_score_calculator.py
│  ├─ similarity_calculator.py
│  └─ kmeans_feature_filter.py
│
├─ scripts/
│  ├─ __init__.py
│  ├─ run_crawler_by_type.py
│  ├─ run_crawler_season_theme.py
│  ├─ run_extract_ingredients.py
│  ├─ run_mark_main_ingredients.py
│  ├─ run_calculate_taste_scores.py
│  ├─ run_calculate_season_scores.py
│  ├─ run_calculate_recipe_similarity.py
│  ├─ run_kmeans_clustering.py
│  ├─ plot_kmeans_pca.py
│  ├─ run_crawler_reviews.py
│  ├─ run_collect_weather_daily.py
│  ├─ run_build_recipe_daily_reaction.py
│  └─ plot_weather_reaction_analysis.py
│
└─ outputs/
   ├─ kmeans_pca_scatter.png
   └─ weather/
      ├─ rain_review_count.png
      ├─ temp_group_review_count.png
      ├─ temp_group_category_review.png
      ├─ season_taste_heatmap.png
      └─ weather_corr_heatmap.png
```

---

## 3. 주요 디렉터리 역할

### 3.1 `crawler/`

만개의레시피 웹페이지에서 데이터를 수집하는 모듈입니다.

| 파일 | 역할 |
|---|---|
| `crawl_list.py` | 카테고리 목록 페이지에서 `recipe_id` 수집 |
| `crawl_detail.py` | 레시피 상세 페이지에서 제목, 요약, 재료, 조리순서, 태그, 조회수, 스크랩수, 후기수 수집 |
| `crawl_theme.py` | 봄/여름/가을/겨울 제철요리 테마 페이지에서 `recipe_id` 수집 |
| `crawl_review.py` | 레시피 상세 페이지의 후기 내용, 후기 작성일, 닉네임, 평점 수집 |

---

### 3.2 `pipeline/`

수집된 데이터를 분석 가능한 형태로 가공하는 로직입니다.

| 파일 | 역할 |
|---|---|
| `ingredient_parser.py` | `재료명,수량` 문자열에서 재료명 정제 |
| `main_ingredient_extractor.py` | 제목/태그/제외재료 기준으로 메인 재료 점수 계산 |
| `taste_score_calculator.py` | 재료 키워드 기반 맛 점수 계산 |
| `season_score_calculator.py` | 계절 대표 재료와 레시피 재료를 비교하여 계절 점수 계산 |
| `similarity_calculator.py` | 재료/맛/카테고리 유사도 및 최종 유사도 계산 |
| `kmeans_feature_filter.py` | K-means 피처에서 제외할 도구/수량/기본양념 필터링 |

---

### 3.3 `scripts/`

실제 데이터 수집, 분석, 시각화를 실행하는 스크립트입니다.

| 파일 | 역할 |
|---|---|
| `run_crawler_by_type.py` | 음식 종류별 카테고리 레시피 수집 |
| `run_crawler_season_theme.py` | 제철요리 테마 레시피 수집 |
| `run_extract_ingredients.py` | `raw_recipe.ingredients`에서 재료명/수량을 분리하여 저장 |
| `run_mark_main_ingredients.py` | 레시피별 메인 재료 여부 업데이트 |
| `run_calculate_taste_scores.py` | 레시피별 맛 점수 계산 |
| `run_calculate_season_scores.py` | 레시피별 계절 점수 계산 |
| `run_calculate_recipe_similarity.py` | 레시피 간 유사도 계산 |
| `run_kmeans_clustering.py` | K-means 클러스터링 실행 |
| `plot_kmeans_pca.py` | K-means 결과를 PCA 산점도로 시각화 |
| `run_crawler_reviews.py` | 레시피별 후기 수집 |
| `run_collect_weather_daily.py` | Open-Meteo 과거 날씨 데이터 수집 |
| `run_build_recipe_daily_reaction.py` | 레시피-날짜 단위 후기 반응 집계 |
| `plot_weather_reaction_analysis.py` | 날씨별 후기 반응 분석 그래프 생성 |

---

### 3.4 `db/`

DB 연결과 CRUD/조회 함수를 관리합니다.

| 파일 | 역할 |
|---|---|
| `connection.py` | SQLAlchemy DB 엔진 생성 |
| `repository.py` | 데이터 저장/조회/삭제 함수 모음 |

---

## 4. 실행 환경 설정

### 4.1 Python 가상환경 생성 및 활성화

Mac 기준:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows 기준:

```bash
python -m venv .venv
.venv\Scripts\activate
```

가상환경이 정상 활성화되면 터미널 앞에 아래처럼 표시됩니다.

```bash
(.venv)
```

---

### 4.2 패키지 설치

```bash
pip install -r requirements.txt
```

`requirements.txt`에 포함된 주요 패키지:

```text
requests
beautifulsoup4
lxml
pandas
numpy
sqlalchemy
pymysql
python-dotenv
scikit-learn
matplotlib
jupyter
```

---

### 4.3 `.env` 설정

프로젝트 루트에 `.env` 파일을 생성하고 MySQL 접속 정보를 설정합니다.

```env
DB_URL=mysql+pymysql://계정:비밀번호@localhost:3306/DB명?charset=utf8mb4
```

예시:

```env
DB_URL=mysql+pymysql://recipe_user:password@localhost:3306/recipe_db?charset=utf8mb4
```

`config.py`는 `.env`에서 `DB_URL`을 읽어 DB 연결에 사용합니다.

---

### 4.4 DB 테이블 생성

MySQL Workbench 또는 터미널에서 `db_schema.sql`을 실행합니다.

```bash
mysql -u recipe_user -p recipe_db < db_schema.sql
```

또는 MySQL Workbench에서 `db_schema.sql` 내용을 실행합니다.

---

## 5. 데이터베이스 테이블 구성

### 5.1 원천 데이터 테이블

| 테이블 | 설명 |
|---|---|
| `raw_recipe` | 레시피 상세 원천 데이터 |
| `raw_ingredients` | 재료 마스터 |
| `raw_recipe_ingredient` | 레시피별 재료 매핑 및 메인 재료 정보 |
| `raw_recipe_review` | 레시피별 후기 원천 데이터 |

---

### 5.2 분석 결과 테이블

| 테이블 | 설명 |
|---|---|
| `recipe_taste_score` | 재료 기반 맛 점수 |
| `recipe_season_theme` | 봄/여름/가을/겨울 제철요리 테마 매핑 |
| `recipe_season_score` | 계절 대표 재료 기반 계절 점수 |
| `recipe_similarity` | 레시피 간 유사도 |
| `recipe_cluster_result` | K-means 클러스터링 결과 |
| `recipe_season_reaction_score` | 후기 작성일 기반 계절별 반응도 점수 |

---

### 5.3 날씨/반응도 테이블

| 테이블 | 설명 |
|---|---|
| `weather_daily` | 일자별 서울 기준 날씨 데이터 |
| `recipe_daily_reaction` | 레시피-날짜 단위 후기 수와 날씨 결합 데이터 |

---

### 5.4 정제 규칙 테이블

| 테이블 | 설명 |
|---|---|
| `ingredient_exclude_rule` | 계절 대표 재료 분석에서 제외할 기본 양념/도구/수량값 관리 |

---

## 6. 전체 데이터 수집 및 분석 파이프라인

전체 흐름은 아래 순서로 진행합니다.

```text
1. 음식 종류별 레시피 수집
2. 제철요리 테마 레시피 수집
3. 재료 파싱
4. 메인 재료 판정
5. 맛 점수 계산
6. 계절 점수 계산
7. 레시피 간 유사도 계산
8. K-means 클러스터링
9. K-means PCA 시각화
10. 후기 수집
11. 날씨 데이터 수집
12. 레시피-날짜 단위 반응 집계
13. 날씨별 후기 반응 시각화
```

---

## 7. Step 1. 음식 종류별 레시피 수집

### 7.1 목적

만개의레시피의 종류별 카테고리에서 레시피 목록을 가져오고, 각 레시피 상세 정보를 `raw_recipe`에 저장합니다.

수집 대상 카테고리:

```text
메인반찬
국/탕
찌개
면/만두
밥/죽/떡
양식
```

### 7.2 실행 명령어

카테고리별 기본 30개씩 수집:

```bash
python -m scripts.run_crawler_by_type
```

카테고리별 20개씩 수집:

```bash
python -m scripts.run_crawler_by_type --limit 20
```

특정 카테고리만 수집:

```bash
python -m scripts.run_crawler_by_type --categories "찌개,면/만두" --limit 30
```

### 7.3 저장 테이블

| 테이블 | 저장 내용 |
|---|---|
| `raw_recipe` | 레시피 제목, 카테고리, 요약, 재료, 조리순서, 태그, 조회수, 스크랩수, 후기수 |
| `raw_recipe_ingredient` | 이 단계에서는 아직 저장하지 않음 |

---

## 8. Step 2. 제철요리 테마 레시피 수집

### 8.1 목적

만개의레시피의 제철요리 테마 페이지에서 봄/여름/가을/겨울 레시피를 수집합니다.

| 계절 | 테마 URL |
|---|---|
| 봄 | `https://www.10000recipe.com/theme/view.html?theme=101010001` |
| 여름 | `https://www.10000recipe.com/theme/view.html?theme=101010002` |
| 가을 | `https://www.10000recipe.com/theme/view.html?theme=101010003` |
| 겨울 | `https://www.10000recipe.com/theme/view.html?theme=101010004` |

### 8.2 실행 명령어

전체 계절 수집:

```bash
python -m scripts.run_crawler_season_theme
```

특정 계절만 수집:

```bash
python -m scripts.run_crawler_season_theme --seasons "봄,여름"
```

계절별 20개만 테스트:

```bash
python -m scripts.run_crawler_season_theme --limit 20
```

테마 매핑만 저장하고 상세 수집은 생략:

```bash
python -m scripts.run_crawler_season_theme --skip-detail
```

### 8.3 저장 테이블

| 테이블 | 저장 내용 |
|---|---|
| `recipe_season_theme` | `recipe_id`, `season_type`, `theme_url` |
| `raw_recipe` | 상세가 없는 레시피는 상세 수집 후 저장 |

---

## 9. Step 3. 재료 파싱

### 9.1 목적

`raw_recipe.ingredients`에 저장된 문자열을 분리하여, 재료 마스터와 레시피별 재료 매핑을 생성합니다.

예:

```text
raw_recipe.ingredients =
대파,1/2개/국수,2인분/간장,2큰술
```

파싱 결과:

| recipe_id | ingredient_name | raw_text |
|---|---|---|
| 12345 | 대파 | 대파,1/2개 |
| 12345 | 국수 | 국수,2인분 |
| 12345 | 간장 | 간장,2큰술 |

### 9.2 실행 명령어

```bash
python -m scripts.run_extract_ingredients
```

### 9.3 저장 테이블

| 테이블 | 저장 내용 |
|---|---|
| `raw_ingredients` | 중복 없는 재료명 |
| `raw_recipe_ingredient` | 레시피별 재료명, 원문 |

---

## 10. Step 4. 메인 재료 판정

### 10.1 목적

레시피별 재료 중 실제 음식의 핵심이 되는 재료를 판정합니다.

단순히 재료 순서만으로 메인 재료를 판단하지 않습니다. 예를 들어 `낙지연포탕`의 재료 목록에서 `낙지`가 마지막에 있어도, 제목에 `낙지`가 포함되어 있으므로 메인 재료로 판단할 수 있습니다.

### 10.2 판정 기준

| 기준 | 설명 |
|---|---|
| 제외 재료 | 소금, 설탕, 물, 간장, 도구, 수량값 등은 메인 재료 후보에서 제외 |
| 제목 매칭 | 재료명이 제목에 포함되면 높은 점수 부여 |
| 태그 매칭 | 재료명이 태그에 포함되면 높은 점수 부여 |
| fallback | 제목/태그 매칭이 없으면 제외 후 남은 재료 중 일부를 후보로 처리 |

### 10.3 실행 명령어

```bash
python -m scripts.run_mark_main_ingredients
```

### 10.4 저장 컬럼

`raw_recipe_ingredient`에 아래 컬럼이 업데이트됩니다.

| 컬럼 | 설명 |
|---|---|
| `is_main` | 메인 재료 여부. `Y` 또는 `N` |
| `main_score` | 메인 재료 판단 점수 |
| `main_match_type` | `TITLE_MATCH`, `TAG_MATCH`, `EXCLUDED`, `FALLBACK_TOP_INGREDIENT` 등 |

---

## 11. Step 5. 맛 점수 계산

### 11.1 목적

재료 키워드를 기준으로 각 레시피의 맛 특성을 점수화합니다.

### 11.2 맛 분류

| 맛 | 예시 키워드 |
|---|---|
| 매콤함 | 고춧가루, 고추장, 청양고추 |
| 고소함 | 참기름, 들기름, 깨, 버터, 치즈 |
| 달콤함 | 설탕, 올리고당, 물엿, 꿀 |
| 새콤함 | 식초, 매실액, 케찹 |
| 짭짤함 | 간장, 소금, 굴소스, 된장, 액젓 |
| 담백함 | 두부, 순두부, 닭가슴살, 콩나물, 감자 |

### 11.3 실행 명령어

```bash
python -m scripts.run_calculate_taste_scores
```

### 11.4 저장 테이블

| 테이블 | 저장 내용 |
|---|---|
| `recipe_taste_score` | 6개 맛 점수, 대표 맛, 매칭 키워드 |

---

## 12. Step 6. 계절 점수 계산

### 12.1 목적

제철요리 테마에서 계절별 메인 재료 Top N을 뽑고, 전체 레시피의 재료와 비교하여 계절 점수를 계산합니다.

### 12.2 계산 방식

계절별 대표 메인 재료 Top N을 생성합니다.

예:

```text
봄   = 달래, 돌나물, 딸기, 부추, 쑥
여름 = 가지, 깻잎, 오이, 옥수수, 토마토
가을 = 광어, 도토리묵, 사과, 연근, 포도
겨울 = 굴, 꼬막, 대구, 브로콜리, 황태
```

각 레시피의 재료와 계절 대표 재료가 겹치는 비율로 점수를 계산합니다.

```text
계절 점수 = 해당 계절 대표 재료와 겹친 개수 / 해당 계절 대표 재료 개수
```

### 12.3 실행 명령어

기본 Top 10:

```bash
python -m scripts.run_calculate_season_scores
```

Top 15 기준:

```bash
python -m scripts.run_calculate_season_scores --top-n 15
```

Top 20 기준:

```bash
python -m scripts.run_calculate_season_scores --top-n 20
```

### 12.4 저장 테이블

| 테이블 | 저장 내용 |
|---|---|
| `recipe_season_score` | 봄/여름/가을/겨울 점수, 대표 계절, 매칭 재료 |

---

## 13. Step 7. 레시피 간 유사도 계산

### 13.1 목적

레시피 간 유사도를 계산하여 추천 후보를 만들기 위한 기반 데이터를 생성합니다.

### 13.2 유사도 구성

| 유사도 | 계산 방식 | 가중치 |
|---|---|---:|
| 재료 유사도 | Jaccard Similarity | 0.5 |
| 맛 유사도 | 맛 점수 벡터의 Cosine Similarity | 0.3 |
| 카테고리 유사도 | 같은 카테고리면 1, 아니면 0 | 0.2 |

최종 유사도:

```text
total_similarity =
  ingredient_similarity * 0.5
+ taste_similarity      * 0.3
+ category_similarity   * 0.2
```

### 13.3 중복 저장 방지

`A-B`, `B-A`가 중복 저장되지 않도록 `i + 1` 조합만 계산합니다.

예:

```text
저장함: 김치찌개 - 된장찌개
저장 안 함: 된장찌개 - 김치찌개
```

### 13.4 실행 명령어

```bash
python -m scripts.run_calculate_recipe_similarity
```

### 13.5 저장 테이블

| 테이블 | 저장 내용 |
|---|---|
| `recipe_similarity` | 레시피 쌍별 유사도, 공통 재료, 대표 맛, 추천 이유 |

---

## 14. Step 8. K-means 클러스터링

### 14.1 목적

레시피를 비슷한 특성끼리 자동으로 그룹화합니다.

### 14.2 사용 피처

현재 K-means는 아래 피처를 사용합니다.

| 피처 그룹 | 설명 |
|---|---|
| 맛 점수 6개 | 매콤함, 고소함, 달콤함, 새콤함, 짭짤함, 담백함 |
| 메인 재료 Top N | `is_main = 'Y'`인 재료 중 주요 재료 Top N |
| 카테고리 원-핫 | `category_type`을 0/1 컬럼으로 변환 |

K-means 입력에서 도구, 수량, 기본 양념은 `kmeans_feature_filter.py`에서 제외합니다.

예외 처리 대상:

```text
소금, 물, 간장, 설탕, 도마, 조리용나이프, 2개, 2큰술 등
```

### 14.3 실행 명령어

기본 클러스터 5개:

```bash
python -m scripts.run_kmeans_clustering
```

클러스터 개수 지정:

```bash
python -m scripts.run_kmeans_clustering --clusters 6
```

주요 재료 Top 50 사용:

```bash
python -m scripts.run_kmeans_clustering --clusters 5 --top-ingredients 50
```

### 14.4 저장 테이블

| 테이블 | 저장 내용 |
|---|---|
| `recipe_cluster_result` | 레시피별 클러스터 ID, 클러스터 라벨, 맛 점수 |

### 14.5 클러스터 조회 예시

```sql
SELECT cluster_id
     , cluster_label
     , COUNT(*) AS recipe_count
  FROM recipe_cluster_result
 GROUP BY cluster_id
        , cluster_label
 ORDER BY cluster_id;
```

특정 클러스터의 레시피 목록:

```sql
SELECT recipe_id
     , title
     , category_type
     , main_taste
     , cluster_label
  FROM recipe_cluster_result
 WHERE cluster_id = 0
 ORDER BY title;
```

---

## 15. Step 9. K-means PCA 산점도 생성

### 15.1 목적

K-means는 다차원 피처를 기반으로 수행되기 때문에, 발표자료에서는 PCA를 사용하여 2차원 산점도로 시각화합니다.

### 15.2 PCA 의미

PCA는 여러 개의 숫자 피처를 2개 축으로 압축하여 시각적으로 보기 쉽게 만드는 방법입니다.

```text
K-means = 실제 클러스터링
PCA = 클러스터링 결과 시각화용 2차원 축소
```

### 15.3 실행 명령어

```bash
python -m scripts.plot_kmeans_pca --top-ingredients 30
```

출력 파일:

```text
outputs/kmeans_pca_scatter.png
```

---

## 16. Step 10. 요리 후기 수집

### 16.1 목적

후기 작성일을 기준으로 날씨/계절별 레시피 반응도를 분석하기 위해 레시피별 후기를 수집합니다.

### 16.2 실행 명령어

특정 레시피만 테스트:

```bash
python -m scripts.run_crawler_reviews --recipe-id 6897498 --replace
```

10개 레시피만 테스트:

```bash
python -m scripts.run_crawler_reviews --limit 10 --replace
```

전체 후기 수집:

```bash
python -m scripts.run_crawler_reviews --replace
```

### 16.3 저장 테이블

| 테이블 | 저장 내용 |
|---|---|
| `raw_recipe_review` | `recipe_id`, `review_seq`, `review_date`, `nickname`, `review_content`, `rating` |

### 16.4 주의사항

후기 작성일은 실제 요리한 날짜와 완전히 동일하다고 단정할 수 없습니다. 본 프로젝트에서는 후기 작성일을 **사용자가 해당 레시피에 반응한 시점**으로 해석합니다.

---

## 17. Step 11. 날씨 데이터 수집

### 17.1 목적

후기 작성일과 날씨 데이터를 결합하여 날씨별 레시피 반응도를 분석합니다.

### 17.2 기준 지역

리뷰 작성자의 실제 위치 정보는 수집할 수 없기 때문에, 본 프로젝트에서는 **서울 기준 날씨**를 대표 날씨로 사용합니다.

기본 좌표:

| 항목 | 값 |
|---|---:|
| 위도 | `37.5665` |
| 경도 | `126.9780` |
| 기준 | 서울시청 인근 |

### 17.3 수집 데이터

Open-Meteo 과거 날씨 API에서 시간별 데이터를 수집한 뒤 일별로 집계합니다.

| 컬럼 | 설명 |
|---|---|
| `avg_temp` | 일평균 기온 |
| `min_temp` | 일최저 기온 |
| `max_temp` | 일최고 기온 |
| `avg_humidity` | 일평균 습도 |
| `rainfall` | 일강수량 합계 |
| `rain_yn` | 강수 여부 |

### 17.4 실행 명령어

후기 날짜 범위 기준 자동 수집:

```bash
python -m scripts.run_collect_weather_daily
```

특정 기간 수집:

```bash
python -m scripts.run_collect_weather_daily --start-date 2024-01-01 --end-date 2024-12-31
```

다른 지역 좌표 사용:

```bash
python -m scripts.run_collect_weather_daily \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --latitude 35.1796 \
  --longitude 129.0756
```

### 17.5 저장 테이블

| 테이블 | 저장 내용 |
|---|---|
| `weather_daily` | 일자별 날씨 데이터 |

---

## 18. Step 12. 레시피-날짜 단위 후기 반응 집계

### 18.1 목적

후기 원천 데이터와 날씨 데이터를 결합하여, 레시피별/날짜별 후기 수와 날씨 조건을 하나의 테이블로 생성합니다.

### 18.2 생성 기준

```text
raw_recipe_review.review_date = weather_daily.weather_date
```

### 18.3 계절 구분

| 계절 | 월 |
|---|---|
| 봄 | 3, 4, 5월 |
| 여름 | 6, 7, 8월 |
| 가을 | 9, 10, 11월 |
| 겨울 | 12, 1, 2월 |

### 18.4 온도 구간

| 온도 구간 | 기준 |
|---|---|
| 추움 | `avg_temp < 5℃` |
| 선선함 | `5℃ <= avg_temp < 15℃` |
| 따뜻함 | `15℃ <= avg_temp < 25℃` |
| 더움 | `25℃ <= avg_temp` |

### 18.5 실행 명령어

```bash
python -m scripts.run_build_recipe_daily_reaction
```

### 18.6 저장 테이블

| 테이블 | 저장 내용 |
|---|---|
| `recipe_daily_reaction` | 레시피-날짜 단위 후기 수, 날씨, 계절 |

---

## 19. Step 13. 날씨별 후기 반응 시각화

### 19.1 목적

날씨 조건과 레시피 후기 반응의 관계를 시각적으로 확인합니다.

### 19.2 실행 명령어

```bash
python -m scripts.plot_weather_reaction_analysis
```

### 19.3 출력 파일

```text
outputs/weather/rain_review_count.png
outputs/weather/temp_group_review_count.png
outputs/weather/temp_group_category_review.png
outputs/weather/season_taste_heatmap.png
outputs/weather/weather_corr_heatmap.png
```

### 19.4 생성 그래프

| 그래프 | 설명 |
|---|---|
| `rain_review_count.png` | 비 오는 날/안 오는 날 총 후기 수 비교 |
| `temp_group_review_count.png` | 온도 구간별 총 후기 수 비교 |
| `temp_group_category_review.png` | 온도 구간별 음식 카테고리 후기 반응 |
| `season_taste_heatmap.png` | 계절별 대표 맛 후기 반응 |
| `weather_corr_heatmap.png` | 날씨 변수와 후기 수 상관관계 |

### 19.5 해석 주의사항

날씨 변수와 후기 수의 전체 상관관계가 낮게 나올 수 있습니다. 이는 날씨가 의미 없다는 뜻이 아니라, 전체 레시피를 한 번에 분석할 경우 레시피 자체의 인기도, 노출도, 작성자 영향 등 다른 요인이 더 크게 작용할 수 있다는 의미입니다.

따라서 날씨 분석은 아래처럼 세부 그룹으로 나누어 해석하는 것이 좋습니다.

```text
카테고리별
맛 유형별
온도 구간별
계절별
특정 레시피별
```

---

## 20. 전체 실행 순서 요약

처음부터 전체 파이프라인을 실행하려면 아래 순서로 진행합니다.

```bash
# 1. 종류별 레시피 수집
python -m scripts.run_crawler_by_type --limit 30

# 2. 제철요리 테마 레시피 수집
python -m scripts.run_crawler_season_theme

# 3. 재료 파싱
python -m scripts.run_extract_ingredients

# 4. 메인 재료 판정
python -m scripts.run_mark_main_ingredients

# 5. 맛 점수 계산
python -m scripts.run_calculate_taste_scores

# 6. 계절 점수 계산
python -m scripts.run_calculate_season_scores --top-n 15

# 7. 레시피 간 유사도 계산
python -m scripts.run_calculate_recipe_similarity

# 8. K-means 클러스터링
python -m scripts.run_kmeans_clustering --clusters 5 --top-ingredients 30

# 9. K-means PCA 산점도 생성
python -m scripts.plot_kmeans_pca --top-ingredients 30

# 10. 후기 수집
python -m scripts.run_crawler_reviews --replace

# 11. 날씨 데이터 수집
python -m scripts.run_collect_weather_daily --start-date 2024-01-01 --end-date 2024-12-31

# 12. 레시피-날짜 단위 후기 반응 집계
python -m scripts.run_build_recipe_daily_reaction

# 13. 날씨별 반응도 시각화
python -m scripts.plot_weather_reaction_analysis
```

---

## 21. 주요 분석 쿼리

### 21.1 카테고리별 레시피 수

```sql
SELECT COALESCE(category_type, '미분류') AS category_type
     , COUNT(*) AS recipe_count
  FROM raw_recipe
 GROUP BY COALESCE(category_type, '미분류')
 ORDER BY recipe_count DESC;
```

---

### 21.2 계절별 제철요리 수

```sql
SELECT season_type
     , COUNT(*) AS recipe_count
  FROM recipe_season_theme
 GROUP BY season_type
 ORDER BY CASE season_type
              WHEN '봄'   THEN 1
              WHEN '여름' THEN 2
              WHEN '가을' THEN 3
              WHEN '겨울' THEN 4
              ELSE 99
          END;
```

---

### 21.3 계절별 메인 재료 Top 5

```sql
WITH MAIN_ING AS (
    SELECT S.season_type
         , I.ingredient_name
         , COUNT(*) AS recipe_count
      FROM recipe_season_theme S
     INNER JOIN raw_recipe_ingredient I
        ON I.recipe_id = S.recipe_id
     WHERE I.is_main = 'Y'
     GROUP BY S.season_type
            , I.ingredient_name
),
RANKED AS (
    SELECT season_type
         , ingredient_name
         , recipe_count
         , ROW_NUMBER() OVER (
               PARTITION BY season_type
               ORDER BY recipe_count DESC
           ) AS rn
      FROM MAIN_ING
)
SELECT season_type
     , ingredient_name
     , recipe_count
  FROM RANKED
 WHERE rn <= 5
 ORDER BY CASE season_type
              WHEN '봄'   THEN 1
              WHEN '여름' THEN 2
              WHEN '가을' THEN 3
              WHEN '겨울' THEN 4
              ELSE 99
          END
        , rn;
```

---

### 21.4 대표 맛 분포

```sql
SELECT main_taste
     , COUNT(*) AS recipe_count
  FROM recipe_taste_score
 GROUP BY main_taste
 ORDER BY recipe_count DESC;
```

---

### 21.5 특정 레시피와 유사한 레시피 Top 10

```sql
SELECT CASE
           WHEN source_recipe_id = '기준레시피ID' THEN target_recipe_id
           ELSE source_recipe_id
       END AS similar_recipe_id
     , CASE
           WHEN source_recipe_id = '기준레시피ID' THEN target_title
           ELSE source_title
       END AS similar_title
     , total_similarity
     , ingredient_similarity
     , taste_similarity
     , category_similarity
     , common_ingredients
     , relation_reason
  FROM recipe_similarity
 WHERE source_recipe_id = '기준레시피ID'
    OR target_recipe_id = '기준레시피ID'
 ORDER BY total_similarity DESC
 LIMIT 10;
```

---

### 21.6 클러스터별 레시피 수

```sql
SELECT cluster_id
     , cluster_label
     , COUNT(*) AS recipe_count
  FROM recipe_cluster_result
 GROUP BY cluster_id
        , cluster_label
 ORDER BY cluster_id;
```

---

### 21.7 비 여부별 후기 반응

```sql
SELECT rain_yn
     , COUNT(*) AS reaction_day_count
     , SUM(review_count) AS total_review_count
     , ROUND(AVG(review_count), 2) AS avg_review_count
  FROM recipe_daily_reaction
 WHERE rain_yn IS NOT NULL
 GROUP BY rain_yn;
```

---

### 21.8 온도 구간별 카테고리 후기 반응

```sql
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
 ORDER BY temp_group
        , total_review_count DESC;
```

---

## 22. 추천 점수 설계 방향

현재 프로젝트에서 추천 점수는 아래 요소를 조합하는 방식으로 확장할 수 있습니다.

```text
final_recommend_score =
  recipe_similarity_score * 0.60
+ cluster_match_score     * 0.15
+ season_score            * 0.10
+ weather_reaction_score  * 0.15
```

각 점수 의미:

| 점수 | 의미 |
|---|---|
| `recipe_similarity_score` | 재료/맛/카테고리 기반 유사도 |
| `cluster_match_score` | 같은 K-means 클러스터 여부 |
| `season_score` | 계절 대표 재료 기반 계절성 |
| `weather_reaction_score` | 현재 날씨 조건과 과거 후기 반응의 유사성 |

---

## 23. 분석 한계

본 프로젝트는 탐색적 데이터 분석 프로젝트이므로 아래 한계를 가집니다.

| 한계 | 설명 |
|---|---|
| 후기 작성일 한계 | 후기 작성일은 실제 요리/섭취일과 다를 수 있음 |
| 위치 정보 한계 | 리뷰 작성자의 실제 위치를 알 수 없어 서울 기준 날씨를 대표값으로 사용 |
| 표본 수 한계 | 카테고리별 수집 레시피 수가 제한적이므로 일반화에 주의 필요 |
| 노출도 통제 불가 | 사이트 노출 순위, 작성자 인지도, 레시피 등록일 영향은 통제하지 못함 |
| 크롤링 의존성 | 사이트 HTML 구조 변경 시 selector 수정 필요 |
| 계절 테마 데이터 한계 | 제철요리 테마 데이터 수가 적어 계절성 학습 데이터가 아닌 보조 라벨로 사용 |

---

## 24. 발표용 핵심 메시지

발표에서는 아래 흐름으로 설명하면 좋습니다.

```text
1. 만개의레시피에서 레시피 원천 데이터와 후기 데이터를 수집하였다.
2. 재료 데이터를 정제하고, 제목/태그 기반으로 메인 재료를 판정하였다.
3. 재료 키워드 기반으로 6개 맛 점수를 계산하였다.
4. 제철요리 테마의 메인 재료를 활용하여 계절 점수를 만들었다.
5. 재료/맛/카테고리 기반으로 레시피 간 유사도를 계산하였다.
6. K-means로 유사한 레시피 그룹을 만들고 PCA로 시각화하였다.
7. 후기 작성일과 서울 기준 날씨를 결합하여 날씨별 후기 반응도를 탐색하였다.
8. 최종적으로 유사도, 클러스터, 계절, 날씨 반응도를 조합한 추천 구조로 확장할 수 있다.
```

---

## 25. 자주 발생한 오류와 해결 방법

### 25.1 `Unknown column 'avg_humidity' in 'field list'`

원인:

```text
weather_daily 테이블에 avg_humidity 컬럼이 없는데 코드에서 INSERT 시도
```

해결:

```sql
ALTER TABLE weather_daily
ADD COLUMN avg_humidity DECIMAL(6,2) AFTER max_temp;
```

또는 `weather_daily` 테이블을 `db_schema.sql` 기준으로 재생성합니다.

---

### 25.2 `nan can not be used with MySQL`

원인:

```text
pandas DataFrame에서 category_type 등 NULL 값이 NaN으로 변환된 상태로 MySQL 저장 시도
```

해결:

```text
저장 전 NaN을 None 또는 '미분류'로 변환
```

예:

```python
df["category_type"] = df["category_type"].fillna("미분류")
```

---

### 25.3 K-means 대표 재료에 도구/수량값이 나오는 문제

원인:

```text
전체 재료 빈도 Top N을 그대로 피처로 사용하여 도마, 조리용나이프, 2개 등이 포함됨
```

해결:

```text
kmeans_feature_filter.py에서 도구/수량/기본양념 제외
K-means 피처는 is_main = 'Y'인 메인 재료 중심으로 구성
```

---

## 26. 향후 개선 방향

| 개선 방향 | 설명 |
|---|---|
| 후기 수집 정확도 개선 | 후기 HTML selector 보완 및 날짜 파싱률 개선 |
| 지역 기반 날씨 확장 | 서울 고정 대신 주요 도시 평균 또는 사용자 지역 기반 날씨 결합 |
| 레시피 등록일 수집 | 오래된 레시피가 후기 수에서 유리한 문제 보정 |
| 인기도 점수 추가 | 조회수, 스크랩수, 후기수 기반 관심도 점수 생성 |
| 계절 반응도 점수 강화 | 후기 작성월 기준 계절별 반응 집중도 산출 |
| 추천 API화 | 특정 레시피 기준 추천 Top N 조회 API 개발 |
| 대시보드 구축 | Streamlit, Jupyter, 또는 웹 화면으로 분석 결과 시각화 |

---

## 27. 참고 실행 순서: 빠른 테스트용

처음부터 전체를 돌리기 전에 아래처럼 소량 데이터로 테스트할 수 있습니다.

```bash
python -m scripts.run_crawler_by_type --limit 5 --categories "찌개,면/만두"
python -m scripts.run_crawler_season_theme --limit 5 --seasons "여름,겨울"
python -m scripts.run_extract_ingredients
python -m scripts.run_mark_main_ingredients
python -m scripts.run_calculate_taste_scores
python -m scripts.run_calculate_season_scores --top-n 5
python -m scripts.run_calculate_recipe_similarity
python -m scripts.run_kmeans_clustering --clusters 3 --top-ingredients 10
python -m scripts.plot_kmeans_pca --top-ingredients 10
python -m scripts.run_crawler_reviews --limit 10 --replace
python -m scripts.run_collect_weather_daily --start-date 2024-01-01 --end-date 2024-12-31
python -m scripts.run_build_recipe_daily_reaction
python -m scripts.plot_weather_reaction_analysis
```

---

## 28. 산출물

최종적으로 생성되는 주요 산출물은 다음과 같습니다.

| 산출물 | 위치 |
|---|---|
| K-means PCA 산점도 | `outputs/kmeans_pca_scatter.png` |
| 비 여부별 후기 반응 그래프 | `outputs/weather/rain_review_count.png` |
| 온도 구간별 후기 반응 그래프 | `outputs/weather/temp_group_review_count.png` |
| 온도 구간별 카테고리 반응 그래프 | `outputs/weather/temp_group_category_review.png` |
| 계절별 맛 반응 히트맵 | `outputs/weather/season_taste_heatmap.png` |
| 날씨 변수 상관관계 히트맵 | `outputs/weather/weather_corr_heatmap.png` |

---

## 29. 프로젝트 요약

이 프로젝트는 단순히 레시피를 수집하는 데서 끝나지 않고, 다음과 같은 분석 파이프라인을 구성합니다.

```text
레시피 수집
→ 재료 정제
→ 메인 재료 판정
→ 맛 점수 계산
→ 계절 점수 계산
→ 레시피 간 유사도 계산
→ K-means 클러스터링
→ 후기/날씨 반응도 분석
→ 추천 점수 설계
```

이를 통해 사용자가 가진 재료 또는 선택한 레시피를 기준으로, 비슷한 레시피를 찾고 계절/날씨 반응도를 보조적으로 반영하는 추천 시스템으로 확장할 수 있습니다.
