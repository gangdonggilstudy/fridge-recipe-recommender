"""
개발 편의 명령 모음 (venv python 자동 사용).

실행:
    python scripts/dev.py <command>

명령:
    run       — Streamlit 앱 실행
    test      — pytest 전체 실행
    rebuild   — recipes.db 재빌드
    lint      — ruff check
    format    — ruff format
    pdf       — 문서/코드 PDF 빌드
"""

import os
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"


def venv_python() -> Path:
    """venv 내부 python — 없으면 현재 인터프리터로 폴백."""
    if os.name == "nt":
        path = VENV_DIR / "Scripts" / "python.exe"
    else:
        path = VENV_DIR / "bin" / "python"
    return path if path.exists() else Path(sys.executable)


def run(*cmd: str) -> int:
    py = str(venv_python())
    return subprocess.call([py, *cmd], cwd=PROJECT_ROOT)


COMMANDS = {
    "run":     ("-m", "streamlit", "run", "🍽_사용자.py"),
    "test":    ("-m", "pytest", "tests", "-v"),
    "rebuild": ("recipes/tools/build_recipes.py",),
    "lint":    ("-m", "ruff", "check", "."),
    "format":  ("-m", "ruff", "format", "."),
    "pdf":     ("scripts/build_pdf.py",),
}


def main() -> None:
    """CLI 디스패처: `python scripts/dev.py <run|test|rebuild|lint|format|pdf>`."""
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    extra = sys.argv[2:]
    sys.exit(run(*COMMANDS[cmd], *extra))


if __name__ == "__main__":
    main()
