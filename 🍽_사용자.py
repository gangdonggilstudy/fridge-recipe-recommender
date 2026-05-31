"""Streamlit 메인 진입점 — 사이드바 표시 라벨 '🍽 사용자' 용 얇은 래퍼.

Streamlit MPA 는 메인 스크립트 파일명을 사이드바 라벨로 그대로 표시한다.
실제 진입 로직은 `app.py` 에 그대로 두고(테스트의 `import app` 호환 보존),
이 파일은 main() 만 호출. set_page_config 등 모듈 부수효과는 `import app` 시점에 실행됨.
"""
import app

app.main()
