"""
main_launcher.py
----------------
PyInstaller entry point for the BSIE desktop application.

Responsibilities (in order):
  1. Create user data directories if they don't exist (first-run setup)
  2. Redirect stdout/stderr to bsie.log in the user data directory
  3. Start uvicorn (FastAPI server) in a background thread on port 5001
  4. Poll GET /health until the server is ready (max 10 seconds)
  5. Open the user's default browser to http://127.0.0.1:5001
  6. Show a system tray icon with a "Quit BSIE" menu item
  7. On "Quit BSIE": stop uvicorn, remove tray icon, exit process
"""

import sys
import os
import time
import threading
import webbrowser
import urllib.request
import urllib.error
import logging
from pathlib import Path

# Import paths first — works in both bundle and source mode
from paths import (
    INPUT_DIR, OUTPUT_DIR, OVERRIDES_DIR, PROFILES_DIR,
    BUNDLE_DIR, USER_DATA_DIR,
)

PORT = 5001
BASE_URL = f"http://127.0.0.1:{PORT}"
HEALTH_URL = f"{BASE_URL}/health"
MAX_WAIT_SECONDS = 10


def _setup_user_dirs() -> None:
    """Create user data directories on first launch (idempotent).

    USER_DATA_DIR is created implicitly as a parent of INPUT_DIR, but we create
    it explicitly first so _redirect_output_to_log can safely open bsie.log.
    """
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for directory in [INPUT_DIR, OUTPUT_DIR, OVERRIDES_DIR, PROFILES_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def _redirect_output_to_log() -> None:
    """Redirect stdout/stderr to bsie.log (PyInstaller suppresses the console).

    Must be called after _setup_user_dirs() so USER_DATA_DIR exists.
    The log file handle is intentionally never closed — it must stay open for
    the lifetime of the process; os._exit(0) in _quit_app lets the OS close it.
    """
    log_path = USER_DATA_DIR / "bsie.log"
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file
    logging.basicConfig(
        stream=log_file,
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def _start_server() -> None:
    """Start the uvicorn server in a daemon thread. Stores server ref for shutdown.

    The server reference is stored as a function attribute before server.run()
    blocks.  _quit_app uses hasattr() to guard against reading it before it is
    set — but in practice _quit_app is only reachable after the tray icon runs,
    which only starts after _wait_for_server() succeeds, by which point this
    thread has already stored the reference.

    IMPORTANT: We import and pass the FastAPI app *object* directly rather than
    using the string form "app:app".  In a PyInstaller frozen bundle, uvicorn's
    string-based importer cannot resolve module names — it raises
    "Could not import module 'app'".  Passing the live object bypasses that
    entirely and also ensures PyInstaller's static analysis picks up app.py and
    all its transitive imports at build time.
    """
    import uvicorn
    from app import app as fastapi_app  # noqa: PLC0415 — deferred to keep startup fast
    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    _start_server.server = server
    server.run()


def _wait_for_server() -> bool:
    """Poll /health until the server responds or MAX_WAIT_SECONDS is reached."""
    deadline = time.time() + MAX_WAIT_SECONDS
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def _load_tray_icon():
    """Load the tray icon PNG. Falls back to a coloured square if not found."""
    from PIL import Image
    icon_path = BUNDLE_DIR / "installer" / "bsie.png"
    if not icon_path.exists():
        return Image.new("RGB", (64, 64), color=(30, 100, 200))
    return Image.open(icon_path)


def _quit_app(icon, item) -> None:
    """Called when user selects 'Quit BSIE' from the tray menu."""
    icon.stop()
    if hasattr(_start_server, "server"):
        _start_server.server.should_exit = True
    time.sleep(1)
    os._exit(0)


def main() -> None:
    _setup_user_dirs()
    _redirect_output_to_log()

    logger = logging.getLogger("bsie.launcher")
    logger.info("BSIE launcher starting — user data: %s", USER_DATA_DIR)

    # Start uvicorn in a background daemon thread
    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    if not _wait_for_server():
        import tkinter.messagebox as mb
        mb.showerror(
            "BSIE",
            f"Server failed to start on port {PORT}.\n"
            "Check bsie.log for details."
        )
        sys.exit(1)

    logger.info("Server ready — opening browser")
    webbrowser.open(BASE_URL)

    # System tray icon (blocks until icon.stop() is called)
    import pystray
    tray_image = _load_tray_icon()
    menu = pystray.Menu(
        pystray.MenuItem("Quit BSIE", _quit_app),
    )
    icon = pystray.Icon("BSIE", tray_image, "BSIE", menu)
    logger.info("Tray icon running")
    icon.run()


if __name__ == "__main__":
    main()
