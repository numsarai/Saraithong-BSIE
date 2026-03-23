# bsie.spec
# PyInstaller spec for BSIE desktop application.
# Build: pyinstaller bsie.spec
# Output: dist/BSIE (one-dir) or dist/BSIE.exe (Windows), dist/BSIE.app (macOS)

import sys
from pathlib import Path

_ico  = str(Path("installer/bsie.ico"))
_icns = str(Path("installer/bsie.icns"))
_icon = _icns if sys.platform == "darwin" else _ico

block_cipher = None

a = Analysis(
    ["main_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("templates",          "templates"),
        ("static",             "static"),
        ("config",             "config"),
        ("installer/bsie.png", "installer"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "fastapi",
        "starlette",
        "starlette.routing",
        "starlette.middleware",
        "starlette.middleware.base",
        "starlette.staticfiles",
        "starlette.templating",
        "pystray._win32",
        "pystray._darwin",
        "pystray._xorg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BSIE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="BSIE.app",
        icon=_icns,
        bundle_identifier="com.bsie.app",
    )
