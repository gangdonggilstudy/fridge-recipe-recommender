# 07. 사용 라이브러리 — 무엇이고, 우리 프로젝트 어디서 쓰나

> [requirements.txt](../requirements.txt)의 각 라이브러리가 **무엇인지** + **이 프로젝트의 어디서 어떻게 쓰이는지** 정리합니다.
> 앱 사이드바 "📦 사용 라이브러리"는 requirements.txt를 그대로 보여주고, 이 문서는 그 *해설판*입니다.

---

## 한눈에 보기

| 라이브러리 | 분류 | 한 줄 역할 | 우리 프로젝트 사용처 |
|---|---|---|---|
| **streamlit** | 핵심 | 파이썬으로 웹 UI | 앱 전체 (`app.py`, `ui/`, `pages/`) |
| **pandas** | 핵심 | 표 데이터 처리 | 운영자 지표·ML 분석 |
| **numpy** | 핵심 | 수치 배열 연산 | 점수 벡터·ML 피처 |
| **scikit-learn** | 핵심 | 머신러닝 | 추천 개인화 (로지스틱 회귀) |
| **requests** | 핵심 | HTTP 호출 | 날씨·LLM·IP 위치 API |
| **python-dotenv** | 핵심 | `.env` 로딩 | 환경변수·API 키 |
| **streamlit-geolocation** | 핵심(선택동작) | 브라우저 위치 | 위치 위젯 |
| **faster-whisper** | 선택 | 음성→텍스트(STT) | 음성 재료 입력 |
| **beautifulsoup4·lxml** | 데이터(서브) | HTML 파싱 | 레시피 크롤러 (`research/recipe_project/crawler/`) |
| **SQLAlchemy·pymysql** | 데이터(서브) | DB ORM·MySQL 드라이버 | 크롤링 DB·앱용 CSV 생성 (`research/`, `recipes/tools/`) |
| **matplotlib·jupyter** | 분석(서브) | 시각화·노트북 | 회귀/분포 분석 (`research/recipe_project/analysis/`) |
| **markdown·Pygments·pypdf** | 빌드 | 문서→PDF | `scripts/build_pdf.py` |
| **pytest·pytest-cov·ruff** | 개발 | 테스트·린트 | 개발 시 |
| (번들) **joblib** | — | 모델 직렬화 | 학습 모델 저장 |
| (번들) **altair** | — | 차트 | 운영자 대시보드 |
| (번들) **Pillow** | 선택 | 이미지 처리 | 영수증 사진 축소 |

> "번들"은 requirements.txt에 직접 없지만 scikit-learn/streamlit이 함께 설치하는 의존성입니다.

---

## 핵심 의존성 (없으면 앱이 안 뜸)

### streamlit `>=1.31`
**무엇**: 파이썬 스크립트를 그대로 웹앱으로 만들어 주는 프레임워크. HTML/JS 없이 버튼·탭·폼을 파이썬으로 작성.

**우리 프로젝트**:
- 진입점 [`app.py`](../app.py) / [`🍽_사용자.py`](../🍽_사용자.py) — 탭·사이드바 구성
- [`ui/`](../ui/) 전체 — `st.tabs`, `st.button`, `st.multiselect`, `st.audio_input` 등
- [`pages/`](../pages/) — 멀티페이지 기능으로 운영자 페이지 분리
- **`@st.cache_resource`** ([`app_services.py`](../modules/app_services.py)) — 서비스 객체를 앱 전체에서 1개만 생성하는 **싱글톤 핵심 장치**
- **`st.session_state`** — 사용자별 임시 상태 저장 (선택한 레시피, 추천 결과 캐시 등)

> 💡 Streamlit은 사용자가 뭔가 누를 때마다 **스크립트를 처음부터 다시 실행**(rerun)합니다. 그래서 `cache_resource`로 DB 연결을 재사용하고, `session_state`로 상태를 유지하는 패턴이 곳곳에 있습니다.

### pandas `>=2.0`
**무엇**: 표(DataFrame) 형태 데이터를 다루는 표준 도구.

**우리 프로젝트**:
- [`metrics.py`](../modules/metrics.py) — 추천 노출/클릭 기록을 집계해 CTR·일별 추이 표 생성
- [`ml_ops_stats.py`](../modules/ml_ops_stats.py) — 사용자/모델 분포 통계
- [`feature_analyzer.py`](../modules/feature_analyzer.py) — 피처 상관관계 행렬
- [`ui/monitoring.py`](../ui/monitoring.py) — 위 표들을 운영자 대시보드 차트로

### numpy `>=1.24`
**무엇**: 빠른 수치 배열 연산 라이브러리.

**우리 프로젝트**:
- [`scorer.py`](../modules/scorer.py) — 선호 벡터를 배열로 만들어 코사인 유사도 계산
- [`ml_trainer.py`](../modules/ml_trainer.py) — `0.95 ** np.arange(...)`로 최신성 가중치 배열 생성, 피처 벡터 변환
- 곳곳의 점수 벡터 연산

### scikit-learn `>=1.3` ⭐
**무엇**: 파이썬 대표 머신러닝 라이브러리.

**우리 프로젝트** — 이 앱 개인화의 심장:
- [`ml_trainer.py`](../modules/ml_trainer.py) — **`LogisticRegression`** 으로 사용자별 "선택 확률" 모델 학습/예측
- [`scorer.py`](../modules/scorer.py) — **`cosine_similarity`** 로 선호도 점수 계산
- [`feature_analyzer.py`](../modules/feature_analyzer.py) — 전역 LR로 피처 영향 분석

→ 어떻게 쓰이는지 자세히는 [06. ML 풀어쓰기](06_ml_explained.md)

### requests `>=2.31`
**무엇**: HTTP 요청을 보내는 가장 흔한 라이브러리.

**우리 프로젝트** — 모든 외부 API 호출:
- [`weather_api.py`](../modules/weather_api.py) — OpenWeatherMap 날씨 조회
- [`llm/narrator.py`](../llm/narrator.py) — Gemini/OpenAI REST API 호출 (텍스트·비전)
- [`location_resolver.py`](../modules/location_resolver.py) — ipapi.co로 IP 기반 위치 추정

> 💡 모두 **fallback**이 있어 네트워크/키가 없어도 앱은 동작합니다.

### python-dotenv `>=1.0`
**무엇**: `.env` 파일의 키=값을 환경변수로 읽어들임.

**우리 프로젝트**:
- [`app.py`](../app.py), [`pages/`](../pages/) 시작 시 `load_dotenv()` — `WEATHER_API_KEY`, `LLM_*`, `ADMIN_USER_IDS` 등을 로드
- 임포트 순서가 중요: app_services가 DB 경로 상수를 읽기 *전에* 로드해야 함

### streamlit-geolocation `>=0.0.10`
**무엇**: 브라우저의 위치 권한을 요청해 GPS/WiFi 좌표를 받는 Streamlit 컴포넌트.

**우리 프로젝트**:
- [`ui/location.py`](../ui/location.py) — 사용자가 허용하면 정확한 위치로 날씨 추천. 없으면 IP 추정 → 기본값(서울)로 폴백

---

## 선택 의존성 (없으면 해당 기능만 비활성)

### faster-whisper `>=1.0`
**무엇**: OpenAI Whisper 음성인식 모델의 빠른 구현 (로컬 실행, 외부 전송 없음).

**우리 프로젝트**:
- [`stt_engine.py`](../modules/stt_engine.py) — 녹음한 음성을 텍스트로 변환
- [`ui/voice_input.py`](../ui/voice_input.py) — "말로 재료 넣기" 기능
- `STT_ENABLED=true`일 때만 활성, 미설치 시 음성 입력 버튼만 사라짐

---

## 빌드용 (PDF 생성)

### markdown · Pygments · pypdf
**무엇**: 마크다운→HTML 변환(markdown), 코드 하이라이팅(Pygments), PDF 병합(pypdf).

**우리 프로젝트**:
- [`scripts/build_pdf.py`](../scripts/build_pdf.py) — 문서/코드를 PDF로 묶음 (제출·보관용). Chrome/Edge headless 추가 필요

---

## 개발용 (앱 실행엔 불필요)

| 라이브러리 | 역할 |
|---|---|
| **pytest** `>=7.4` | 테스트 실행 |
| **pytest-cov** `>=4.1` | 테스트 커버리지 측정 |
| **ruff** `>=0.1` | 빠른 린터·포매터 (코드 스타일 검사) |

---

## 직접 명시 안 했지만 쓰이는 것 (번들 의존성)

### joblib
scikit-learn이 함께 설치. [`model_registry.py`](../modules/model_registry.py)에서 **학습된 모델을 `.pkl` 파일로 저장/로드**할 때 사용.

### altair
streamlit이 함께 설치. [`ui/monitoring.py`](../ui/monitoring.py) 피처 분석 탭에서 상관계수 **히트맵**을 그릴 때 사용.

### Pillow (PIL)
**선택적 best-effort**. [`ui/receipt_input.py`](../ui/receipt_input.py)에서 **영수증 사진을 OCR 전에 축소**(API 비용·속도 절감). 미설치면 원본 그대로 전송 (graceful).

---

## 의존성 철학

**실행 중인 앱** 기준으로는 **핵심 5개(streamlit·pandas·numpy·scikit-learn·requests)만 필수**이고, 음성·위치·OCR 등은 모두 **선택**입니다. AI 키, 음성, 위치, OCR이 전부 없어도 추천·UI는 완전히 동작합니다 — 모든 외부 의존성에 fallback이 있기 때문입니다.

단, requirements.txt에는 앱 런타임이 아닌 **데이터 파이프라인용 의존성**(beautifulsoup4·lxml·SQLAlchemy·pymysql·matplotlib·jupyter)도 포함됩니다. 이들은 레시피 크롤링·DB 적재·오프라인 분석(`research/recipe_project/`, `recipes/tools/`)에서만 쓰이고 앱 실행에는 필요 없습니다. → [03. 용어 사전](03_glossary.md)의 "fallback" 참고

---

## 다음에 읽을 문서

- 라이브러리가 코드에서 조립되는 방식 → [02. 아키텍처](02_architecture.md)
- scikit-learn이 쓰이는 ML 상세 → [06. ML 풀어쓰기](06_ml_explained.md)
