#!/usr/bin/env bash
# ============================================================================
#  BSIE — Remote Access Setup (Tailscale + Cloudflare Tunnel)
#  Run on the Mac Mini server.
#
#  Usage:
#    chmod +x deploy/remote-access.sh
#    ./deploy/remote-access.sh tailscale     # Setup Tailscale only
#    ./deploy/remote-access.sh cloudflare    # Setup Cloudflare Tunnel only
#    ./deploy/remote-access.sh all           # Setup both
# ============================================================================

set -euo pipefail

PORT="${PORT:-8757}"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[BSIE]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
info() { echo -e "${BLUE}[INFO]${NC} $*"; }

# ═══════════════════════════════════════════════════════════════════════════
# Tailscale — Private VPN mesh for your team
# ═══════════════════════════════════════════════════════════════════════════

setup_tailscale() {
    log "=== Setting up Tailscale ==="
    echo ""

    # Install
    if ! command -v tailscale &>/dev/null; then
        log "Installing Tailscale..."
        brew install --cask tailscale
        echo ""
        info "Tailscale installed. Opening the app..."
        open -a Tailscale
        echo ""
        echo "  ┌────────────────────────────────────────────────────┐"
        echo "  │  1. Tailscale icon will appear in the menu bar     │"
        echo "  │  2. Click it → Sign in (Google/Microsoft/GitHub)   │"
        echo "  │  3. Approve the device                             │"
        echo "  └────────────────────────────────────────────────────┘"
        echo ""
        read -p "  Press Enter after you've signed in to Tailscale..."
    else
        log "Tailscale already installed."
    fi

    # Check status
    if tailscale status &>/dev/null; then
        TS_IP=$(tailscale ip -4 2>/dev/null || echo "N/A")
        log "Tailscale is connected!"
        echo ""
        echo "  ┌─────────────────────────────────────────────────────────┐"
        echo "  │  Tailscale IP: ${TS_IP}                                │"
        echo "  │  BSIE URL:    http://${TS_IP}:${PORT}                  │"
        echo "  │                                                         │"
        echo "  │  Anyone on your Tailscale network can access this URL.  │"
        echo "  └─────────────────────────────────────────────────────────┘"
        echo ""
    else
        warn "Tailscale is installed but not connected."
        echo "  Open the Tailscale app and sign in."
    fi

    # Client instructions
    echo ""
    log "=== How team members connect ==="
    echo ""
    echo "  Each team member needs to:"
    echo "    1. Install Tailscale:"
    echo "       macOS:   brew install --cask tailscale"
    echo "       Windows: https://tailscale.com/download/windows"
    echo "       iOS:     App Store → 'Tailscale'"
    echo "       Android: Play Store → 'Tailscale'"
    echo ""
    echo "    2. Sign in with the SAME account (or be invited to your tailnet)"
    echo ""
    echo "    3. Open browser:"
    echo "       http://${TS_IP:-<tailscale-ip>}:${PORT}"
    echo ""
}


# ═══════════════════════════════════════════════════════════════════════════
# Cloudflare Tunnel — Public URL with access control
# ═══════════════════════════════════════════════════════════════════════════

setup_cloudflare() {
    log "=== Setting up Cloudflare Tunnel ==="
    echo ""

    # Install cloudflared
    if ! command -v cloudflared &>/dev/null; then
        log "Installing cloudflared..."
        brew install cloudflared
    else
        log "cloudflared already installed."
    fi

    echo ""
    echo "  ┌────────────────────────────────────────────────────────────┐"
    echo "  │  Cloudflare Tunnel has 2 modes:                           │"
    echo "  │                                                            │"
    echo "  │  A) Quick Tunnel (no domain needed, temporary URL)         │"
    echo "  │     Good for: demo, testing, temporary sharing             │"
    echo "  │                                                            │"
    echo "  │  B) Named Tunnel (needs Cloudflare account + domain)       │"
    echo "  │     Good for: permanent URL like bsie.yourdomain.com       │"
    echo "  └────────────────────────────────────────────────────────────┘"
    echo ""

    read -p "  Which mode? [A/B]: " mode
    mode="${mode:-A}"

    if [[ "${mode^^}" == "A" ]]; then
        setup_cloudflare_quick
    else
        setup_cloudflare_named
    fi
}


setup_cloudflare_quick() {
    log "Starting Quick Tunnel (temporary public URL)..."
    echo ""
    echo "  This will give you a URL like: https://xxx-yyy-zzz.trycloudflare.com"
    echo "  The URL changes every time you restart. Good for demos."
    echo ""
    echo "  Starting tunnel to localhost:${PORT}..."
    echo "  Press Ctrl+C to stop."
    echo ""

    cloudflared tunnel --url "http://localhost:${PORT}"
}


setup_cloudflare_named() {
    echo ""
    echo "  ┌────────────────────────────────────────────────────────────┐"
    echo "  │  Prerequisites for Named Tunnel:                           │"
    echo "  │                                                            │"
    echo "  │  1. Cloudflare account (free)                              │"
    echo "  │     https://dash.cloudflare.com/sign-up                    │"
    echo "  │                                                            │"
    echo "  │  2. Domain added to Cloudflare                             │"
    echo "  │     (You can buy a .com for ~$10/year on Cloudflare)       │"
    echo "  └────────────────────────────────────────────────────────────┘"
    echo ""

    # Login
    if [[ ! -f "$HOME/.cloudflared/cert.pem" ]]; then
        log "Authenticating with Cloudflare..."
        cloudflared tunnel login
    fi

    # Create tunnel
    read -p "  Enter a tunnel name (e.g. 'bsie'): " TUNNEL_NAME
    TUNNEL_NAME="${TUNNEL_NAME:-bsie}"

    log "Creating tunnel '${TUNNEL_NAME}'..."
    cloudflared tunnel create "${TUNNEL_NAME}" 2>/dev/null || warn "Tunnel may already exist."

    # Get tunnel ID
    TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "${TUNNEL_NAME}" | awk '{print $1}')

    if [[ -z "$TUNNEL_ID" ]]; then
        warn "Could not find tunnel ID. Check: cloudflared tunnel list"
        return 1
    fi

    read -p "  Enter your domain (e.g. 'bsie.example.com'): " DOMAIN
    DOMAIN="${DOMAIN:-bsie.example.com}"

    # Create DNS route
    log "Setting DNS route: ${DOMAIN} → tunnel..."
    cloudflared tunnel route dns "${TUNNEL_NAME}" "${DOMAIN}" 2>/dev/null || warn "DNS route may already exist."

    # Create config
    CLOUDFLARED_DIR="$HOME/.cloudflared"
    mkdir -p "$CLOUDFLARED_DIR"

    cat > "${CLOUDFLARED_DIR}/config.yml" << CFEOF
tunnel: ${TUNNEL_ID}
credentials-file: ${CLOUDFLARED_DIR}/${TUNNEL_ID}.json

ingress:
  - hostname: ${DOMAIN}
    service: http://localhost:${PORT}
  - service: http_status:404
CFEOF

    log "Config written to ${CLOUDFLARED_DIR}/config.yml"
    echo ""

    # Create launchd service for cloudflared
    PLIST_PATH="$HOME/Library/LaunchAgents/com.cloudflare.tunnel.plist"
    cat > "$PLIST_PATH" << PEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${CLOUDFLARED_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${CLOUDFLARED_DIR}/tunnel-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${CLOUDFLARED_DIR}/tunnel-stderr.log</string>
</dict>
</plist>
PEOF

    log "launchd service created for Cloudflare Tunnel"
    echo ""
    echo "  ┌─────────────────────────────────────────────────────────┐"
    echo "  │  Setup complete!                                        │"
    echo "  │                                                         │"
    echo "  │  Start tunnel:                                          │"
    echo "  │    launchctl load ${PLIST_PATH}                         │"
    echo "  │                                                         │"
    echo "  │  Or manually:                                           │"
    echo "  │    cloudflared tunnel run                                │"
    echo "  │                                                         │"
    echo "  │  Access URL: https://${DOMAIN}                          │"
    echo "  │                                                         │"
    echo "  │  IMPORTANT: Add Cloudflare Access to protect the URL!   │"
    echo "  │    https://one.dash.cloudflare.com → Access → Apps      │"
    echo "  └─────────────────────────────────────────────────────────┘"
    echo ""
}


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

case "${1:-help}" in
    tailscale)
        setup_tailscale
        ;;
    cloudflare)
        setup_cloudflare
        ;;
    all)
        setup_tailscale
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        setup_cloudflare
        ;;
    help|*)
        echo "BSIE Remote Access Setup"
        echo ""
        echo "Usage: $0 {tailscale|cloudflare|all}"
        echo ""
        echo "  tailscale   - Private VPN mesh (for dev team)"
        echo "  cloudflare  - Public tunnel with access control"
        echo "  all         - Setup both"
        ;;
esac
