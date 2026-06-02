# 냉장고 요리 추천 시스템 — 실행 가이드

> 📚 **이 프로젝트를 처음 이해하려면?** [docs/](docs/README.md) 의 초보자 문서부터 읽으세요
> (개요 → 아키텍처 → 용어 사전 → 추천 로직). 아래는 실행 가이드입니다.

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

## 3. 환경 변수 (선택)

`.env.example` 을 `.env` 로 복사 후 필요한 키 입력:

| 키 | 용도 |
|---|---|
| `WEATHER_API_KEY` | OpenWeatherMap — 날씨 추천 활성화 |
| `LLM_PROVIDER` | `gemini` 또는 `openai` — AI 설명·영수증 OCR |
| `LLM_API_KEY` | 위 공급자 API 키 |
| `STT_ENABLED` | `true` 시 음성 입력 활성화 (faster-whisper 자동 설치) |
| `RECEIPT_OCR_ENABLED` | `true` + `LLM_*` 가용 시 영수증 OCR 입력 노출 |
| `ADMIN_USER_IDS` | 운영자 페이지 접근 user_id 콤마 구분 |

모두 미설정이어도 추천·UI 는 동작합니다 (LLM/날씨는 fallback).

## 4. (선택) 시드 데이터

시연용 데모 사용자 + history 생성:

```bash
python scripts/seed_demo.py --with-history
```

전체 시드 (lots of history + likes + impressions):

```bash
python scripts/seed_full.py
```

## 5. 실행

원클릭:

```bash
python run.py
```

직접 실행:

```bash
streamlit run 🍽_사용자.py
```

브라우저에서 `http://localhost:8501` 접속.

## 폴더 구조

| 디렉토리 | 책임 |
|---|---|
| `app.py` / `🍽_사용자.py` | Streamlit 진입점 |
| `modules/` | 추천·점수·저장소·ML |
| `ui/` | Streamlit UI 컴포넌트 |
| `llm/` | LLM 호출 (narrator·parser) |
| `pages/` | 운영자 페이지 |
| `recipes/` | 레시피 카탈로그 빌드 |
| `scripts/` | 시드·재학습 등 보조 스크립트 |
