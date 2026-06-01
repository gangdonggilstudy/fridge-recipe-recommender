"""스크립트 공용 콘솔 출력 헬퍼.

setup.py / build_pdf.py 등 CLI 스크립트에서 일관된 단계·상태 표기를 위해 공유.
"""

import sys


def info(msg: str) -> None:
    print(f"  → {msg}")


def section(title: str) -> None:
    print(f"\n[STEP] {title}")


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def die(msg: str, code: int = 1) -> None:
    print(f"  [ERROR] {msg}", file=sys.stderr)
    sys.exit(code)
