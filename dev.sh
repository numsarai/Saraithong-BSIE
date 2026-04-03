#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# BSIE Development Server Launcher
# Usage:  ./dev.sh          (start both backend + frontend)
#         ./dev.sh --stop   (kill both servers)
# ─────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BACKEND_PORT=8757
FRONTEND_PORT=5173
BACKEND_LOG="/tmp/bsie_backend.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# ── Stop mode ────────────────────────────────────────────
if [[ "$1" == "--stop" ]]; then
    echo -e "${RED}Stopping BSIE servers...${NC}"
    lsof -ti:$BACKEND_PORT  | xargs kill 2>/dev/null && echo "  Backend  (port $BACKEND_PORT) stopped" || echo "  Backend  not running"
    lsof -ti:$FRONTEND_PORT | xargs kill 2>/dev/null && echo "  Frontend (port $FRONTEND_PORT) stopped" || echo "  Frontend not running"
    exit 0
fi

echo -e "${BOLD}${BLUE}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   BSIE – Development Server Launcher    ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ── Kill stale processes on our ports ─────────────────────
for port in $BACKEND_PORT $FRONTEND_PORT; do
    pid=$(lsof -ti:$port 2>/dev/null || true)
    if [[ -n "$pid" ]]; then
        echo -e "  ${RED}Killing stale process on port $port (PID $pid)${NC}"
        kill $pid 2>/dev/null || true
        sleep 1
    fi
done

# ── Activate venv ────────────────────────────────────────
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
    echo -e "  ${GREEN}✓${NC} Python venv activated ($(python3 --version))"
else
    echo -e "  ${RED}✗${NC} No .venv found — run: python3 -m venv .venv && .venv/pip install -r requirements.txt"
    exit 1
fi

# ── Start backend ────────────────────────────────────────
echo -e "  ${BLUE}Starting backend on port $BACKEND_PORT...${NC}"
python3 app.py > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Wait for backend health
for i in $(seq 1 20); do
    if curl -sf http://127.0.0.1:$BACKEND_PORT/health > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Backend ready (PID $BACKEND_PID)"
        break
    fi
    if [[ $i -eq 20 ]]; then
        echo -e "  ${RED}✗${NC} Backend failed to start — check $BACKEND_LOG"
        cat "$BACKEND_LOG"
        exit 1
    fi
    sleep 0.5
done

# ── Start frontend ───────────────────────────────────────
if [[ -d frontend/node_modules ]]; then
    echo -e "  ${BLUE}Starting frontend on port $FRONTEND_PORT...${NC}"
    cd frontend
    npm run dev > /dev/null 2>&1 &
    FRONTEND_PID=$!
    cd "$SCRIPT_DIR"
    sleep 2
    echo -e "  ${GREEN}✓${NC} Frontend ready (PID $FRONTEND_PID)"
else
    echo -e "  ${RED}✗${NC} frontend/node_modules missing — run: cd frontend && npm install"
    echo -e "  ${BLUE}→${NC} Serving built React from backend instead"
    FRONTEND_PID=""
fi

# ── Summary ──────────────────────────────────────────────
echo ""
echo -e "  ${BOLD}${GREEN}All servers running!${NC}"
echo ""
APP_PORT=${FRONTEND_PID:+$FRONTEND_PORT}
APP_PORT=${APP_PORT:-$BACKEND_PORT}
echo -e "  ${BOLD}App:${NC}      http://localhost:$APP_PORT"
echo -e "  ${BOLD}API:${NC}      http://localhost:$BACKEND_PORT/api"
echo -e "  ${BOLD}Health:${NC}   http://localhost:$BACKEND_PORT/health"
echo -e "  ${BOLD}Logs:${NC}     $BACKEND_LOG"
echo ""
echo -e "  Press ${BOLD}Ctrl+C${NC} to stop all servers"
echo ""

# ── Trap Ctrl+C to clean up ──────────────────────────────
cleanup() {
    echo ""
    echo -e "  ${RED}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && kill $FRONTEND_PID 2>/dev/null || true
    wait 2>/dev/null
    echo -e "  ${GREEN}Done.${NC}"
    exit 0
}
trap cleanup INT TERM

# Open browser
if command -v open &>/dev/null; then
    open "http://localhost:$APP_PORT"
elif command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:$APP_PORT"
fi

# Wait for either process to exit
wait
