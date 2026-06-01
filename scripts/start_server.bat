@echo off
REM PC 서버 시작 스크립트 — Windows 시작프로그램 등록 가능
REM 등록 방법: Win+R → shell:startup → 본 파일 바로가기 복사

cd /d "%~dp0\.."

REM venv 인터프리터 우선 사용
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

REM 외부 접속 허용 (Tailscale 내 다른 PC에서 접근)
%PYTHON% -m streamlit run app.py ^
    --server.port 8501 ^
    --server.address 0.0.0.0 ^
    --server.headless true ^
    --browser.gatherUsageStats false

pause
