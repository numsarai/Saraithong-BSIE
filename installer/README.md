# BSIE — Installation Guide

## Program Owner

- Owner: ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง
- Developer: ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง
- Contact: ๐๙๖๗๗๖๘๗๕๗

## macOS

1. Open `BSIE-<version>-macos.dmg`
2. Drag **BSIE** to your **Applications** folder
3. First launch: right-click BSIE → **Open** (bypasses Gatekeeper for unsigned apps)
4. BSIE opens in your browser automatically at `http://127.0.0.1:8757`
5. A tray icon appears in your menu bar — click it to **Quit BSIE**

**Data location:** `~/Library/Application Support/BSIE/`
**Logs:** `~/Library/Application Support/BSIE/bsie.log`

---

## Windows

1. Run `dist/installer/BSIE-Setup-<version>-windows.exe`
2. Click **Next** → **Install** → **Finish**
3. BSIE launches automatically and opens in your browser
4. A tray icon appears in the system tray — right-click → **Quit BSIE**

**Data location:** `%LOCALAPPDATA%\BSIE\`
**Logs:** `%LOCALAPPDATA%\BSIE\bsie.log`

---

## What's included

Everything is bundled — no additional software needed:
- Python runtime
- Web server (FastAPI + uvicorn)
- React web interface
- Database (SQLite)
- All processing libraries (pandas, openpyxl, etc.)

Existing installs that already use the legacy `Documents/BSIE` folder keep using
that location automatically so upgrades do not strand old case data.

## Maintainer Verification

After building a desktop bundle, you can smoke-test it without opening a tray
icon or browser:

```bash
./.venv/bin/python scripts/smoke_bundle.py \
  --target dist/BSIE.app \
  --port 8761 \
  --user-data-dir /tmp/bsie-smoke
```

On Windows, point `--target` at `dist\BSIE\BSIE.exe` instead.

For a release-oriented checklist across macOS and Windows, use
`installer/release-checklist.md`.

For a one-command Windows release build from a Windows machine, use:

```powershell
powershell -ExecutionPolicy Bypass -File installer/windows/build_release.ps1
```

The smoke test verifies more than `/health`:
- the embedded FastAPI server responds
- root UI assets load
- the bundled writable runtime folders are created
- the packaged bank logo catalog is available
- at least one real packaged bank logo asset (`scb`) is served successfully

---

## Supported Banks

SCB · KBANK · BBL · KTB · BAY · TTB · GSB · BAAC

To add a new bank: open BSIE → click **Bank Manager** in the sidebar.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| App won't open on macOS | Right-click → Open, then click "Open" in the dialog |
| Port 8757 already in use | Quit any other BSIE instance, or change `PORT` in `.env` |
| Data not showing | Check the `bsie.log` file in the app data folder for your platform |
| Lost data after update | Existing installs keep using their original BSIE data folder automatically |
