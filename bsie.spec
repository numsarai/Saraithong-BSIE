# bsie.spec
# PyInstaller spec for BSIE desktop application.
# Build: pyinstaller bsie.spec
# Output: dist/BSIE (one-dir) or dist/BSIE.exe (Windows), dist/BSIE.app (macOS)

import sys
from pathlib import Path

from project_meta import APP_CONTACT_PHONE, APP_DEVELOPER_NAME, APP_OWNER_NAME, APP_VERSION

_ico  = str(Path("installer/bsie.ico"))
_icns = str(Path("installer/bsie.icns"))
_icon = _icns if sys.platform == "darwin" else _ico
_version = APP_VERSION
_bundle_contact = f"Owner/Developer: {APP_OWNER_NAME or APP_DEVELOPER_NAME} | Contact: {APP_CONTACT_PHONE}"

block_cipher = None

a = Analysis(
    ["main_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("templates",           "templates"),
        ("static",              "static"),       # includes static/dist/ React build
        ("config",              "config"),
        ("installer/bsie.png",  "installer"),
        ("installer/bsie.ico",  "installer"),
        # New modules that need to be findable at runtime
        ("database.py",         "."),
        ("paths.py",            "."),
        ("migrate_to_db.py",    "."),
        ("tasks.py",            "."),
    ],
    hiddenimports=[
        # ── application modules ──────────────────────────────────────────────
        # app.py is now imported directly (not via string "app:app"), so
        # PyInstaller resolves it statically.  These entries are belt-and-
        # suspenders for any dynamic imports that static analysis may miss.
        "app",
        "paths",
        "pipeline.process_account",
        "core.loader",
        "core.bank_detector",
        "core.column_detector",
        "core.mapping_memory",
        "core.override_manager",
        "core.account_parser",
        "core.autodetect",
        "core.classifier",
        "core.entity",
        "core.exporter",
        "core.link_builder",
        "core.nlp_engine",
        "core.normalizer",
        "utils.date_utils",
        "utils.text_utils",
        # ── uvicorn internals ────────────────────────────────────────────────
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
        # ── web framework ────────────────────────────────────────────────────
        "fastapi",
        "starlette",
        "starlette.routing",
        "starlette.middleware",
        "starlette.middleware.base",
        "starlette.staticfiles",
        "starlette.templating",
        # ── UI / tray ────────────────────────────────────────────────────────
        "pystray",
        "pystray._win32",
        "pystray._darwin",
        "pystray._xorg",
        "PIL",
        "PIL.Image",
        # ── data / ML ────────────────────────────────────────────────────────
        "openpyxl",
        "xlrd",
        "pandas",
        "jinja2",
        "jinja2.ext",
        "aiofiles",
        "rapidfuzz",
        "rapidfuzz.distance",
        "dateutil",
        "dateutil.parser",
        "multipart",
        "python_multipart",
        # ── persistence / task runtime ──────────────────────────────────────
        "sqlmodel",
        "sqlalchemy",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.orm",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "unittest",
        "IPython",
        "jupyter",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == "darwin":
    # macOS: build an onedir app bundle instead of a onefile bundle-in-app.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
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
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="BSIE",
    )
    app = BUNDLE(
        coll,
        name="BSIE.app",
        icon=_icns,
        bundle_identifier="com.bsie.app",
        info_plist={
            "CFBundleShortVersionString": _version,
            "CFBundleGetInfoString": _bundle_contact,
            "NSHumanReadableCopyright": APP_OWNER_NAME or APP_DEVELOPER_NAME,
        },
    )
else:
    # Windows: one-dir layout — COLLECT produces dist/BSIE/ (setup.iss Source path)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        [],
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
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="BSIE",
    )
