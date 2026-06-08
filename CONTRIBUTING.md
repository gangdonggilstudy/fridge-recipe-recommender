# 기여 가이드 (CONTRIBUTING)

> 이 프로젝트의 코드를 직접 수정·확장하려는 분을 위한 실전 안내입니다.
> 구조를 먼저 이해하려면 [docs/](docs/README.md)를 읽으세요.

---

## 개발 환경 셋업

```bash
# 1. 가상환경 (권장)
python -m venv .venv
. .venv/Scripts/activate      # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. 의존성
pip install -r requirements.txt

# 3. 레시피 DB 빌드 (최초 1회)
python recipes/tools/build_recipes.py

# 4. 실행
python run.py        # 또는: streamlit run 🍽_사용자.py
```

`.env`는 선택입니다. 키가 없어도 LLM·날씨·음성은 fallback으로 동작합니다([01. 개요](docs/01_overview.md) 참고).

---

## 코드를 관통하는 설계 원칙

이 코드베이스에 기여할 때 **반드시 지켜야 할** 약속들입니다.

### 1. 단일 출처 원칙 (Single Source of Truth)
같은 정보는 한 곳에서만 정의합니다. 새 코드가 이를 깨지 않도록 주의:

| 정보 | 유일한 정의 위치 |
|---|---|
| DB 경로 | `modules/db_paths.py` |
| DB 스키마 | `modules/db_init.py` `SCHEMA_SQL` |
| ML 피처 순서 | `modules/ml_model.py` `FEATURES` |
| 시기 적합 (월·계절 통합) | `modules/context.py` `temporal_fit_score()` |
| 재료 정규화·카테고리 | `modules/normalize.py` |
| 선호 벡터 차원 | `modules/preference.py` `FEATURE_KEYS` |
| 맛 추론 마커 | `modules/normalize.py` `TASTE_MARKERS` |

> ⚠️ 예: ML 피처를 바꿀 땐 `FEATURES` 튜플(라벨·순서·차원의 단일 출처)과 **함께** `build_feature`·history INSERT·`row_to_feature`/SELECT·`db_init` 스키마를 **같은 순서로 맞춰** 고쳐야 합니다(이들은 같은 컬럼명을 리터럴로 참조). **약한 미선택 학습**도 같은 5피처를 쓰므로 `recommendation_impressions` 스키마 컬럼 + `RecommendationImpressionRepo.log_view`(노출 시 피처 기록) + `TrainingDataRepository.load_with_weak`(SELECT) 도 함께 맞춰야 합니다. 한쪽만 바꾸면 train/predict 스큐가 생깁니다.

### 2. 모든 외부 의존성에 fallback
LLM·날씨·STT·OCR은 키가 없거나 실패해도 **앱이 죽으면 안 됩니다.** 새 외부 호출을 추가하면 `try/except` + 대체 경로를 반드시 넣으세요.

### 3. 저장소는 BaseRepository 상속
새 데이터 테이블이 필요하면 `_base_repo.BaseRepository`를 상속해 `_connect()`를 쓰세요. 직접 `sqlite3.connect`를 흩뿌리지 마세요.

### 4. 점수 변경은 멱등하게
`Recommender._apply_diversity`처럼, 점수를 다시 계산해도 누적되지 않도록 `base`를 보존하고 `total`을 재계산하는 패턴을 따르세요.

---

## 자주 하는 작업 (How-to)

### 레시피 추가하기
1. `recipes/recipes_source.csv`에 행 추가
2. `python recipes/tools/build_recipes.py` 재실행 → `recipes.db` 갱신
3. 맛(taste)은 빌드 시 자동 추론됩니다 (리뷰 키워드는 빌드 후 `scripts/generate_review_keywords.py`로 별도 채움)

### 새 점수 요소 추가하기
1. `modules/ingredient_matcher.py` 등에 순수 함수로 점수 계산 추가
2. `modules/scorer.py` `Scorer.score()`의 `components`에 항목 추가
3. `DEFAULT_WEIGHTS`에 가중치 추가
4. ML에도 넣으려면 `ml_model.FEATURES` + history 스키마 컬럼 + `recommendation_impressions` 컬럼(약한 미선택용)·`log_view`·`load_with_weak` 까지 함께 추가 (위 §1 ⚠️ 참고)

### LLM provider 바꾸기/추가하기
1. `llm/narrator.py`의 `LLMProvider` Protocol을 구현
2. `make_provider()`에 분기 추가
3. `.env`의 `LLM_PROVIDER`로 선택

### 새 UI 탭/위젯 추가하기
1. `ui/`에 `render(...)` 함수를 가진 모듈 추가
2. 필요한 객체는 `modules/app_services.py`의 `get_*()`로 주입받기
3. `app.py`에서 호출

---

## 코드 스타일

- **타입 힌트** 적극 사용 (`contracts.py`의 TypedDict 참고)
- **한국어 docstring** — 기존 코드 톤에 맞추세요 (왜 그렇게 했는지 설명 위주)
- `# noqa: BLE001` — 광범위 except는 fallback 의도가 분명할 때만, 주석으로 이유 명시
- 매직 문자열 금지 — session_state 키는 `ui/session_keys.py`에 등록

---

## 테스트 & 확인

```bash
# 스키마 초기화 단독 실행
python -m modules.db_init

# ML 동작 확인 (앱에서 추천을 충분히 선택해 기록을 쌓은 뒤)
python scripts/retrain.py        # 재학습 트리거

# 앱 띄워 수동 확인
python run.py
```

> 변경 후에는 추천이 실제로 동작하는지(룰/블렌더 양쪽), fallback 경로(키 없이)가 깨지지 않는지 확인하세요.

---

## 폴더 빠른 참조

| 폴더 | 책임 |
|---|---|
| `modules/` | 핵심 로직 (추천·점수·ML·저장소) |
| `ui/` | Streamlit 화면 |
| `llm/` | AI 텍스트 (provider 추상화 + fallback) |
| `pages/` | 운영자 페이지 |
| `recipes/` | 레시피 카탈로그 빌드 |
| `scripts/` | 시드·재학습 등 보조 도구 |
| `docs/` | 초보자용 설명 문서 |
