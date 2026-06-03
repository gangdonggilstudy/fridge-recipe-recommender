"""원클릭 환경 구축 + 앱 실행 진입점.

사용:
    python run.py

흐름:
1. `.venv` 가 없으면 `scripts/setup.py` 실행 (Python 검증·venv 생성·의존성 설치·recipes.db 빌드·테스트)
2. `.venv/Scripts/python.exe -m streamlit run 🍽_사용자.py --server.headless true` 로 앱 기동

직접 호출되는 setup.py 도 동일 가정으로 작성됨 — 추가 환경 변수 없이 동작.
"""

import os
import subprocess
import sys
from pathlib import Path

# Windows 콘솔 CP949 → UTF-8 강제 (한글·em-dash 출력 깨짐 방지)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def main() -> int:
    venv_py = venv_python()
    if not venv_py.exists():
        print("[run.py] .venv 가 없습니다 — scripts/setup.py 로 환경 구축")
        rc = subprocess.call(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "setup.py"), "--no-test"],
            cwd=PROJECT_ROOT,
        )
        if rc != 0:
            print("[run.py] setup 실패 — 위 로그 확인", file=sys.stderr)
            return rc
        if not venv_py.exists():
            print("[run.py] setup 완료했지만 .venv python 을 못 찾음", file=sys.stderr)
            return 1

    print("[run.py] Streamlit 앱 실행 — http://localhost:8501")
    # --server.headless: Streamlit 첫 실행 시 email onboarding 프롬프트 + 브라우저
    # 자동 오픈을 끈다. 비대화식 호출(run.py)에서 stdin 폐쇄로 즉시 종료되는 문제 회피.
    # 메인 스크립트 파일명이 사이드바 라벨로 그대로 표시되므로 '🍽_사용자.py' 사용.
    return subprocess.call(
        [str(venv_py), "-m", "streamlit", "run", "🍽_사용자.py", "--server.headless", "true"],
        cwd=PROJECT_ROOT,
    )


if __name__ == "__main__":
    sys.exit(main())
