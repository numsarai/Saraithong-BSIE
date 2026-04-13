#!/usr/bin/env bash
# ============================================================================
#  BSIE — Mac Mini M4 Production Setup Script
#  Run on a fresh macOS machine to set up BSIE as a local server.
#
#  Usage:
#    chmod +x deploy/setup-mac-mini.sh
#    ./deploy/setup-mac-mini.sh
# ============================================================================

set -euo pipefail

BSIE_DIR="$HOME/bsie"
LOG_DIR="$BSIE_DIR/logs"
BACKUP_DIR="$BSIE_DIR/data/backups"
PYTHON_VERSION="3.12"
NODE_VERSION="22"
PORT="${BSIE_PORT:-8757}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[BSIE]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── 1. Prerequisites ───────────────────────────────────────────────────────

log "=== BSIE Mac Mini Production Setup ==="
echo ""

# Check macOS
if [[ "$(uname)" != "Darwin" ]]; then
    err "This script is for macOS only."
    exit 1
fi

# ── 2. Homebrew ────────────────────────────────────────────────────────────

if ! command -v brew &>/dev/null; then
    log "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add to PATH for Apple Silicon
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    log "Homebrew already installed: $(brew --version | head -1)"
fi

# ── 3. Python ──────────────────────────────────────────────────────────────

if ! command -v python${PYTHON_VERSION} &>/dev/null; then
    log "Installing Python ${PYTHON_VERSION}..."
    brew install python@${PYTHON_VERSION}
else
    log "Python already installed: $(python${PYTHON_VERSION} --version)"
fi

# ── 4. Node.js ─────────────────────────────────────────────────────────────

if ! command -v node &>/dev/null; then
    log "Installing Node.js ${NODE_VERSION}..."
    brew install node@${NODE_VERSION}
else
    log "Node.js already installed: $(node --version)"
fi

# ── 5. Project directory ───────────────────────────────────────────────────

if [[ ! -d "$BSIE_DIR" ]]; then
    warn "Project directory not found at $BSIE_DIR"
    echo ""
    echo "  Please copy the BSIE project to: $BSIE_DIR"
    echo ""
    echo "  Options:"
    echo "    1. AirDrop/USB: Copy the entire bsie folder"
    echo "    2. Git:         git clone <your-repo-url> $BSIE_DIR"
    echo "    3. SCP:         scp -r user@old-mac:~/Documents/bsie $BSIE_DIR"
    echo ""
    echo "  Then run this script again."
    exit 1
fi

cd "$BSIE_DIR"
log "Working in: $BSIE_DIR"

# ── 6. Create directories ─────────────────────────────────────────────────

mkdir -p "$LOG_DIR" "$BACKUP_DIR"
mkdir -p data/input data/output data/evidence data/exports

# ── 7. Python venv + dependencies ─────────────────────────────────────────

if [[ ! -d ".venv" ]]; then
    log "Creating Python virtual environment..."
    python${PYTHON_VERSION} -m venv .venv
fi

log "Installing Python dependencies..."
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt --quiet
log "Python dependencies installed."

# ── 8. Frontend build ──────────────────────────────────────────────────────

if [[ -d "frontend" ]]; then
    log "Building frontend for production..."
    cd frontend
    npm install --silent
    npm run build
    cd ..
    log "Frontend built to static/dist/"
else
    warn "frontend/ directory not found — skipping frontend build."
fi

# ── 9. Production .env ─────────────────────────────────────────────────────

if [[ ! -f ".env" ]]; then
    log "Creating production .env..."
    JWT_SECRET=$(.venv/bin/python -c "import secrets; print(secrets.token_hex(32))")
    ADMIN_PW=$(.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(16))")

    cat > .env << ENVEOF
# === BSIE Production Config (Mac Mini M4) ===
# Generated: $(date '+%Y-%m-%d %H:%M:%S')

# Security
BSIE_JWT_SECRET=${JWT_SECRET}
BSIE_AUTH_REQUIRED=false
BSIE_ADMIN_USERNAME=admin
BSIE_ADMIN_INITIAL_PASSWORD=${ADMIN_PW}

# Server
PORT=${PORT}

# Backup
BSIE_ENABLE_AUTO_BACKUP=1
BSIE_BACKUP_INTERVAL_HOURS=24
BSIE_AUTO_BACKUP_FORMAT=json
BSIE_BACKUP_POLL_SECONDS=60

# Optional: Neo4j (disabled by default)
BSIE_ENABLE_NEO4J_EXPORT=0

# Optional: LLM (disabled by default)
BSIE_ENABLE_LLM_CLASSIFICATION=0
ENVEOF

    echo ""
    echo "  ======================================"
    echo "  Admin Password: ${ADMIN_PW}"
    echo "  ======================================"
    echo "  (Save this! It won't be shown again)"
    echo ""
else
    log ".env already exists — skipping."
fi

# ── 10. Production run script ──────────────────────────────────────────────

cat > run_production.sh << 'RUNEOF'
#!/usr/bin/env bash
# Run BSIE in production mode
set -euo pipefail

BSIE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BSIE_DIR"

export PATH="$BSIE_DIR/.venv/bin:$PATH"

WORKERS="${BSIE_WORKERS:-4}"
PORT="${PORT:-8757}"
LOG_DIR="$BSIE_DIR/logs"
mkdir -p "$LOG_DIR"

echo "[$(date)] Starting BSIE v$(cat VERSION) on port $PORT with $WORKERS workers"

exec "$BSIE_DIR/.venv/bin/uvicorn" app:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level info \
    --access-log \
    2>&1 | tee -a "$LOG_DIR/bsie-$(date +%Y%m%d).log"
RUNEOF
chmod +x run_production.sh

# ── 11. launchd service (auto-start on boot) ──────────────────────────────

PLIST_NAME="com.bsie.server"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

cat > "$PLIST_PATH" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${BSIE_DIR}/.venv/bin/uvicorn</string>
        <string>app:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>${PORT}</string>
        <string>--workers</string>
        <string>4</string>
        <string>--log-level</string>
        <string>info</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${BSIE_DIR}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${BSIE_DIR}/.venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/bsie-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/bsie-stderr.log</string>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>SoftResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>4096</integer>
    </dict>
</dict>
</plist>
PLISTEOF

log "launchd service created: $PLIST_PATH"

# ── 12. Control scripts ───────────────────────────────────────────────────

cat > bsie-ctl.sh << 'CTLEOF'
#!/usr/bin/env bash
# BSIE Server Control
# Usage: ./bsie-ctl.sh {start|stop|restart|status|logs}

SERVICE="com.bsie.server"
BSIE_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$BSIE_DIR/logs"

case "${1:-help}" in
    start)
        echo "Starting BSIE server..."
        launchctl load "$HOME/Library/LaunchAgents/${SERVICE}.plist" 2>/dev/null
        launchctl start "$SERVICE" 2>/dev/null
        sleep 2
        if curl -s -o /dev/null -w '' http://localhost:${PORT:-8757}/ 2>/dev/null; then
            echo "BSIE is running on http://$(ipconfig getifaddr en0):${PORT:-8757}"
        else
            echo "Starting... check: ./bsie-ctl.sh status"
        fi
        ;;
    stop)
        echo "Stopping BSIE server..."
        launchctl stop "$SERVICE" 2>/dev/null
        launchctl unload "$HOME/Library/LaunchAgents/${SERVICE}.plist" 2>/dev/null
        echo "Stopped."
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    status)
        echo "=== BSIE Server Status ==="
        if launchctl list | grep -q "$SERVICE"; then
            echo "Service: RUNNING"
            PID=$(launchctl list | grep "$SERVICE" | awk '{print $1}')
            echo "PID: $PID"
            IP=$(ipconfig getifaddr en0 2>/dev/null || echo "N/A")
            echo "URL: http://${IP}:${PORT:-8757}"
            HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${PORT:-8757}/ 2>/dev/null || echo "N/A")
            echo "HTTP: $HTTP"
            if [[ "$PID" != "-" && "$PID" != "" ]]; then
                RSS=$(ps -o rss= -p "$PID" 2>/dev/null | awk '{printf "%.0f", $1/1024}')
                echo "Memory: ${RSS:-?} MB"
            fi
        else
            echo "Service: STOPPED"
        fi
        ;;
    logs)
        echo "=== Recent logs ==="
        tail -50 "$LOG_DIR/bsie-stderr.log" 2>/dev/null || echo "No logs yet."
        ;;
    ip)
        IP=$(ipconfig getifaddr en0 2>/dev/null || echo "N/A")
        echo "http://${IP}:${PORT:-8757}"
        ;;
    help|*)
        echo "Usage: $0 {start|stop|restart|status|logs|ip}"
        ;;
esac
CTLEOF
chmod +x bsie-ctl.sh

# ── 13. Firewall hint ─────────────────────────────────────────────────────

log ""
log "=== Setup Complete! ==="
echo ""
echo "  Quick start:"
echo "    ./bsie-ctl.sh start        # Start the server"
echo "    ./bsie-ctl.sh status       # Check status + URL"
echo "    ./bsie-ctl.sh logs         # View logs"
echo "    ./bsie-ctl.sh stop         # Stop the server"
echo ""
echo "  Auto-start on boot: ENABLED (launchd)"
echo "    Disable: launchctl unload ~/Library/LaunchAgents/com.bsie.server.plist"
echo ""
echo "  Network access (for other devices on same WiFi/LAN):"
echo "    1. System Settings > General > Sharing > check 'Remote Login' (optional)"
echo "    2. When macOS firewall asks — click 'Allow' for Python"
echo "    3. Other devices access: http://$(ipconfig getifaddr en0 2>/dev/null || echo '<mac-mini-ip>'):${PORT}"
echo ""
echo "  Logs: $LOG_DIR/"
echo ""
