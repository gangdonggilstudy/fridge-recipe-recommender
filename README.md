# 냉장고 요리 추천 시스템 — 실행 가이드

> 📚 **이 프로젝트를 처음 이해하려면?** [docs/](docs/README.md) 의 초보자 문서부터 읽으세요
> (개요 → 아키텍처 → 용어 사전 → 추천 로직). 아래는 실행 가이드입니다.

## 빠른 시작 (원클릭)

```bash
python run.py
```

`.venv` 가 없으면 **자동으로** 가상환경 생성 → 의존성 설치 → `recipes.db` 빌드까지 한 뒤 앱을 띄웁니다 (아래 §1·§2 생략 가능). `app.db`(사용자·기록)는 첫 실행 시 새 스키마로 **자동 생성**됩니다.

> 아래 §1~§4는 단계별로 직접 제어하고 싶을 때의 **수동 설정**입니다.

## 1. 의존성 설치

```bash
pip install -r requirements.txt
```

권장: 가상환경 안에서 설치.

## 2. 레시피 DB 빌드 (최초 1회)

`data/recipes.db` 생성:

```bash
python recipes/tools/build_recipes.py
```

만개의 크롤링한 데이터를 사용하려면:
mysql 수집 데이터 -> csv 파일로 export 후 recipes.db 생성
```bash
python recipes/tools/export_from_recipe_project.py
python recipes/tools/build_recipes.py
```

## 3. 환경 변수 (선택)

`.env.example` 을 `.env` 로 복사 후 필요한 키 입력:

| 키 | 용도 |
|---|---|
| `WEATHER_API_KEY` | OpenWeatherMap — 날씨 추천 활성화 |
| `LLM_PROVIDER` | `gemini` 또는 `openai` — AI 설명·영수증 OCR |
| `LLM_API_KEY` | 위 공급자 API 키 |
| `STT_ENABLED` | `true` 시 음성 입력 활성화 (faster-whisper는 requirements.txt에 포함돼 기본 설치 — 미설치 환경이면 자동 비활성화) |
| `RECEIPT_OCR_ENABLED` | `true` + `LLM_*` 가용 시 영수증 OCR 입력 노출 |
| `ADMIN_USER_IDS` | 운영자 페이지 접근 user_id 콤마 구분 |

모두 미설정이어도 추천·UI 는 동작합니다 (LLM/날씨는 fallback).

## 4. 실행

원클릭:

```bash
python run.py
```

직접 실행:

```bash
streamlit run 🍽_사용자.py
```

브라우저에서 `http://localhost:8501` 접속.

## 5. 코드 업데이트 후 DB가 안 맞을 때 (기존 개발자)

> 📢 **DB 정책 (릴리스 단계)**: 이 프로젝트는 이제 **DB 마이그레이션을 운영**합니다.
> 스키마 단일 출처는 `modules/db_init.py` 이며,
> - **추가형 변경(컬럼 추가)** — `init_db` 가 매 기동 시 **자동 보강**(`_reconcile_columns`,
>   `_ADDITIVE_COLUMNS` 원장). 그냥 pull 후 실행하면 데이터 보존한 채 반영됩니다.
> - **구조적 변경(드롭·리네임·타입변경)** — SQLite 제약상 자동화 불가. 해당 변경을 내는
>   PR 은 **명시적 마이그레이션 스크립트**(`scripts/migrate_*.py`)를 함께 제공하는 것을
>   원칙으로 합니다. "app.db 삭제"는 마이그레이션이 없을 때의 **최후 수단**입니다.

구조적 변경을 pull 했는데 마이그레이션 스크립트가 없다면 기존 `data/app.db` 가 옛 구조 그대로라 `no such column ...` 같은 충돌이 날 수 있습니다 (예: ML 피처 변경으로 `month_match`/`season_match` → `temporal_fit`). 그때는 아래로 재생성하세요.

- **app.db (사용자·기록)** — (마이그레이션 없는 구조적 변경 시 최후 수단) 삭제 후 재생성. 앱을 다시 실행하면 새 스키마로 자동 생성됩니다.
  ```bash
  # Windows
  del data\app.db data\app.db-wal data\app.db-shm
  ```
  > 📌 **추가형 컬럼은 자동 마이그레이션**: 예로 `recommendation_impressions` 에 ML
  > '약한 미선택' 학습용 5피처(`ingredient_score`·`consumption_score`·`preference_score`·
  > `context_score`·`temporal_fit`)가 추가됐는데, **앱을 다시 실행하면 `init_db` 가
  > 누락 컬럼만 ALTER 로 자동 보강**합니다(데이터 보존, 옛 노출 행은 피처 NULL →
  > 학습에서 자동 제외). 앱 없이 수동 적용만 하려면: `python scripts/migrate_impression_features.py`
- **학습 모델 (`models/`)** — 피처 차원이 바뀌어도 옛 모델은 `feature_dim` 가드로 **자동 무효화·재학습**되어 보통 손댈 필요 없음. 깔끔히 비우려면 `models/` 폴더 삭제.
- **recipes.db (레시피 카탈로그)** — CSV·빌드 로직이 바뀌었으면 재빌드: `python recipes/tools/build_recipes.py` (또는 `python scripts/setup.py --rebuild`).

> 💡 **새로 clone 하는 사람은 해당 없음** — 처음부터 최신 스키마로 생성됩니다. 이 안내는 **예전 DB를 들고 있던** 경우에만 필요합니다.

## 폴더 구조

| 디렉토리 | 책임 |
|---|---|
| `app.py` / `🍽_사용자.py` | Streamlit 진입점 |
| `modules/` | 추천·점수·저장소·ML |
| `ui/` | Streamlit UI 컴포넌트 |
| `llm/` | LLM 호출 (narrator·parser) |
| `pages/` | 운영자 페이지 |
| `recipes/` | 레시피 카탈로그 빌드 |
| `research` / `recipe_project`| 만개의 레시피 크롤링 및 분석 |
| `scripts/` | 재학습 등 보조 스크립트 |
