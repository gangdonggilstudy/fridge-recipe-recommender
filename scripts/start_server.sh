#!/usr/bin/env bash
# PC 서버 시작 스크립트 — macOS/Linux
# systemd/launchd 등록 시 본 스크립트를 ExecStart 로 지정

set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

# 외부 접속 허용 (Tailscale 내 다른 PC 에서 접근)
exec "$PYTHON" -m streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
