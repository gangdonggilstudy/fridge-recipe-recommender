"""
개발환경 원샷 설정 스크립트.

실행:
    python scripts/setup.py

자동 처리:
1. Python 버전 확인 (>= 3.10)
2. .venv 가상환경 생성 (없을 때만)
3. requirements.txt 설치
4. .env 파일 생성 (.env.example 복사, 없을 때만)
5. data/recipes.db 빌드 (없을 때만, --rebuild 옵션으로 강제)
6. pytest 단위 테스트 실행하여 환경 검증

옵션:
    --rebuild   recipes.db 강제 재빌드
    --no-test   테스트 스킵
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from _cli_utils import die, info, ok, section, warn

# Windows 콘솔 CP949 → UTF-8 강제 (한글·특수문자 출력 깨짐 방지)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
ENV_FILE = PROJECT_ROOT / ".env"
RECIPES_DB = PROJECT_ROOT / "data" / "recipes.db"

MIN_PYTHON = (3, 10)


# ─── 단계별 함수 ───

def check_python_version() -> None:
    section("Python 버전 확인")
    info(f"현재: {sys.version.split()[0]}")
    if sys.version_info < MIN_PYTHON:
        die(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ 필요")
    ok(f"요구사항 충족 (>= {MIN_PYTHON[0]}.{MIN_PYTHON[1]})")


def venv_python() -> Path:
    """venv 내부 python 인터프리터 경로."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_venv() -> Path:
    section("가상환경 (.venv)")
    if VENV_DIR.exists():
        ok("이미 존재 — 재사용")
    else:
        info("생성 중...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
        ok(".venv 생성 완료")
    py = venv_python()
    if not py.exists():
        die(f"venv python 인터프리터 못 찾음: {py}")
    return py


def install_requirements(py: Path) -> None:
    section("의존성 설치 (pip)")
    req = PROJECT_ROOT / "requirements.txt"
    if not req.exists():
        die(f"requirements.txt 없음: {req}")
    subprocess.check_call(
        [str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"]
    )
    subprocess.check_call(
        [str(py), "-m", "pip", "install", "-q", "-r", str(req)]
    )
    ok("requirements.txt 설치 완료")


def setup_env_file() -> None:
    section(".env 파일")
    if ENV_FILE.exists():
        ok("이미 존재 — 유지")
        return
    if not ENV_EXAMPLE.exists():
        warn(".env.example 도 없음 — 스킵")
        return
    shutil.copy(ENV_EXAMPLE, ENV_FILE)
    ok(".env.example → .env 복사 완료")
    info("API 키 발급 후 .env 의 WEATHER_API_KEY / LLM_API_KEY 수정 필요")


def build_recipes_db(py: Path, force: bool = False) -> None:
    section("레시피 DB 빌드")
    if RECIPES_DB.exists() and not force:
        ok(f"이미 존재 — 재사용 ({RECIPES_DB.relative_to(PROJECT_ROOT)})")
        info("강제 재빌드는: python scripts/setup.py --rebuild")
        return
    build_script = PROJECT_ROOT / "recipes" / "tools" / "build_recipes.py"
    if not build_script.exists():
        die(f"빌드 스크립트 없음: {build_script}")
    subprocess.check_call([str(py), str(build_script)])
    ok("recipes.db 빌드 완료")


def run_tests(py: Path) -> None:
    section("단위 테스트 실행")
    tests_dir = PROJECT_ROOT / "tests"
    if not tests_dir.exists():
        warn("tests/ 디렉토리 없음 — 스킵")
        return
    result = subprocess.run(
        [str(py), "-m", "pytest", "-q", str(tests_dir)],
        capture_output=True,
        text=True,
    )
    print(result.stdout.strip().split("\n")[-1] if result.stdout else "")
    if result.returncode != 0:
        warn("테스트 실패 — 출력 확인 필요")
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return
    ok("테스트 통과")


def print_next_steps(py: Path) -> None:
    print("\n" + "=" * 50)
    print("개발환경 설정 완료!")
    print("=" * 50)
    print("\n다음 명령으로 앱 실행:")
    if os.name == "nt":
        print("  .venv\\Scripts\\activate")
    else:
        print("  source .venv/bin/activate")
    print("  streamlit run app.py")
    print("\n또는 venv 활성화 없이:")
    print(f"  {py} -m streamlit run app.py")
    print()


# ─── main ───

def main() -> None:
    """개발환경 부트스트랩: venv·의존성·.env·recipes.db·테스트 순차 설정."""
    parser = argparse.ArgumentParser(description="개발환경 자동 설정")
    parser.add_argument("--rebuild", action="store_true",
                        help="recipes.db 강제 재빌드")
    parser.add_argument("--no-test", action="store_true",
                        help="단위 테스트 스킵")
    args = parser.parse_args()

    check_python_version()
    py = ensure_venv()
    install_requirements(py)
    setup_env_file()
    build_recipes_db(py, force=args.rebuild)
    if not args.no_test:
        run_tests(py)
    print_next_steps(py)


if __name__ == "__main__":
    main()
