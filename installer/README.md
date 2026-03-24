# BSIE — Installation Guide

## macOS

1. Open `BSIE-vX.X.X-macos.dmg`
2. Drag **BSIE** to your **Applications** folder
3. First launch: right-click BSIE → **Open** (bypasses Gatekeeper for unsigned apps)
4. BSIE opens in your browser automatically at `http://127.0.0.1:5001`
5. A tray icon appears in your menu bar — click it to **Quit BSIE**

**Data location:** `~/Documents/BSIE/`
**Logs:** `~/Documents/BSIE/bsie.log`

---

## Windows

1. Run `BSIE-Setup-vX.X.X-windows.exe`
2. Click **Next** → **Install** → **Finish**
3. BSIE launches automatically and opens in your browser
4. A tray icon appears in the system tray — right-click → **Quit BSIE**

**Data location:** `C:\Users\<you>\Documents\BSIE\`
**Logs:** `C:\Users\<you>\Documents\BSIE\bsie.log`

---

## What's included

Everything is bundled — no additional software needed:
- Python runtime
- Web server (FastAPI + uvicorn)
- React web interface
- Database (SQLite)
- All processing libraries (pandas, openpyxl, etc.)

---

## Supported Banks

SCB · KBANK · BBL · KTB · BAY · TTB · GSB · BAAC

To add a new bank: open BSIE → click **Bank Manager** in the sidebar.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| App won't open on macOS | Right-click → Open, then click "Open" in the dialog |
| Port 5001 already in use | Quit any other BSIE instance, or change `PORT` in app.py |
| Data not showing | Check `~/Documents/BSIE/bsie.log` for errors |
| Lost data after update | Data is in `~/Documents/BSIE/` — safe across updates |
