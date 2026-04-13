# BSIE — Mac Mini M4 Deployment Guide

## Quick Setup (5 minutes)

### Step 1: Copy project to Mac Mini

```bash
# Option A: AirDrop / USB drive
# Copy the bsie folder to ~/bsie on the Mac Mini

# Option B: SCP from old machine
scp -r ~/Documents/bsie user@mac-mini-ip:~/bsie

# Option C: Git
git clone <your-repo-url> ~/bsie
```

### Step 2: Run setup script

```bash
cd ~/bsie
chmod +x deploy/setup-mac-mini.sh
./deploy/setup-mac-mini.sh
```

The script will:
- Install Homebrew, Python 3.12, Node.js
- Create Python venv + install dependencies
- Build frontend for production
- Generate secure `.env` with random secrets
- Create launchd service (auto-start on boot)
- Create `bsie-ctl.sh` control script

### Step 3: Start the server

```bash
./bsie-ctl.sh start
./bsie-ctl.sh status    # Shows IP + URL
```

---

## Daily Operations

| Command | What it does |
|---------|-------------|
| `./bsie-ctl.sh start` | Start BSIE server |
| `./bsie-ctl.sh stop` | Stop BSIE server |
| `./bsie-ctl.sh restart` | Restart server |
| `./bsie-ctl.sh status` | Show status, PID, memory, URL |
| `./bsie-ctl.sh logs` | View recent logs |
| `./bsie-ctl.sh ip` | Show access URL |

## Accessing from other devices

Devices on the same WiFi/LAN network can access BSIE at:

```
http://<mac-mini-ip>:8757
```

Find the IP with: `./bsie-ctl.sh ip`

### macOS Firewall

When first starting, macOS may ask to allow incoming connections.
Click **"Allow"** for Python/uvicorn.

If blocked manually:
- System Settings > Network > Firewall > Options
- Add Python or set to "Allow all incoming"

---

## Auto-start on Boot

The setup script installs a launchd service that starts BSIE automatically
when the Mac Mini boots up. No login required.

```bash
# Disable auto-start
launchctl unload ~/Library/LaunchAgents/com.bsie.server.plist

# Re-enable
launchctl load ~/Library/LaunchAgents/com.bsie.server.plist
```

---

## Performance Tuning (M4 16GB)

Default config (4 workers) handles 20-50 concurrent users easily.

### Adjust workers

Edit `~/Library/LaunchAgents/com.bsie.server.plist` or run manually:

```bash
# 4 workers (default, good for 10-30 users)
uvicorn app:app --host 0.0.0.0 --port 8757 --workers 4

# 6 workers (for 30-50 users)
uvicorn app:app --host 0.0.0.0 --port 8757 --workers 6
```

### Expected resource usage (M4 16GB)

| Workers | Idle RAM | Peak RAM (20 users) | CPU |
|---------|----------|---------------------|-----|
| 4 | ~600 MB | ~1.5 GB | 5-15% |
| 6 | ~900 MB | ~2.0 GB | 8-20% |

---

## Logs

```
~/bsie/logs/
  bsie-stdout.log    # Application output
  bsie-stderr.log    # Errors + startup messages
  bsie-YYYYMMDD.log  # Daily log (manual run mode)
```

## Backups

Auto-backup runs every 24 hours (configurable in `.env`).

```
~/bsie/data/backups/
```

Manual backup:
```bash
curl -X POST http://localhost:8757/api/admin/backup \
  -H "Content-Type: application/json" \
  -d '{"operator":"admin","note":"pre-presentation backup"}'
```

---

## Troubleshooting

### Server won't start
```bash
./bsie-ctl.sh logs                           # Check error logs
.venv/bin/python -c "import app"             # Test imports
.venv/bin/pip install -r requirements.txt    # Reinstall deps
```

### Can't access from other devices
```bash
# Check IP
ipconfig getifaddr en0

# Check port is listening
lsof -i :8757

# Test locally first
curl http://localhost:8757/
```

### High memory usage
```bash
# Check per-process memory
ps aux | grep uvicorn | grep -v grep

# Restart to free memory
./bsie-ctl.sh restart
```
