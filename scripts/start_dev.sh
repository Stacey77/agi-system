#!/usr/bin/env bash
# Start the AGI System API server in development mode.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# ── .env handling ───────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        cp .env.example .env
        echo "[info] Created .env from .env.example"
    fi
fi

if [[ -f .env ]]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

# ── API key warnings (mock mode notice) ────────────────────────────────────
if [[ -z "${OPENAI_API_KEY:-}" && -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "[warn] No LLM API keys found — agents will run in mock/fallback mode"
    echo "       Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env to enable real LLM calls"
elif [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "[info] OPENAI_API_KEY not set — OpenAI provider unavailable"
elif [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "[info] ANTHROPIC_API_KEY not set — Anthropic provider unavailable"
fi

# ── Dependency check ────────────────────────────────────────────────────────
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "[info] Installing dependencies..."
    pip install -r requirements.txt
fi

# ── Start server ────────────────────────────────────────────────────────────
PORT="${PORT:-8000}"
echo "[info] Starting AGI System API on http://0.0.0.0:${PORT} (reload enabled)"
exec uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT}" --reload
