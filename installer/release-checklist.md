# BSIE Release Checklist

Use this checklist for a release-candidate or public installer build. It keeps
the version, packaged assets, and smoke-test expectations aligned across macOS
and Windows.

## 1. Preflight

- Confirm the release version in `VERSION`.
- Confirm the app reports the same version in the UI after `frontend` build.
- Make sure `.venv` exists and has project dependencies installed.
- Decide whether any existing dirty working-tree files are intentional before
  building release artifacts.
- Keep `create-dmg` available on macOS and Inno Setup 6 (`iscc`) available on
  Windows.

## 2. macOS Final Build

From the repo root:

```bash
bash build.sh --dmg
```

Expected outputs:

- `dist/BSIE.app`
- `dist/BSIE-<version>-macos.dmg`

Smoke-test the packaged app bundle:

```bash
./.venv/bin/python scripts/smoke_bundle.py \
  --target dist/BSIE.app \
  --port 8761 \
  --user-data-dir /tmp/bsie-smoke-release
```

Manual install check:

1. Open `dist/BSIE-<version>-macos.dmg`
2. Drag `BSIE.app` to `Applications`
3. Launch it from `Applications`
4. Verify the browser opens and the tray/menu-bar icon appears
5. Process one sample statement and verify output export succeeds

## 3. Windows Final Build

Run this on a Windows machine from the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File installer/windows/build_release.ps1
```

Expected outputs:

- `dist\BSIE\BSIE.exe`
- `dist\installer\BSIE-Setup-<version>-windows.exe`

What the helper script does:

- reads `VERSION`
- builds the frontend unless `-SkipFrontend` is passed
- reinstalls Python requirements into `.venv`
- runs `PyInstaller`
- smoke-tests `dist\BSIE\BSIE.exe`
- builds the Inno Setup installer with the same version string

Manual install check:

1. Run `dist\installer\BSIE-Setup-<version>-windows.exe`
2. Complete install with default options
3. Launch BSIE and verify the browser opens automatically
4. Verify the tray icon appears
5. Quit BSIE from the tray
6. Uninstall BSIE and confirm the shortcut entries are removed

## 4. Release Sign-Off

Do not publish until all of the following are true:

- macOS bundle smoke test passed
- macOS DMG install test passed
- Windows bundle smoke test passed
- Windows installer install/uninstall test passed
- `VERSION`, installer filenames, and in-app UI version all match
- bank logos, favicon, and static assets render in the packaged app
- one end-to-end sample workflow succeeds from upload to export

## 5. Artifact Record

Record these exact paths for the release notes:

- macOS app bundle: `dist/BSIE.app`
- macOS DMG: `dist/BSIE-<version>-macos.dmg`
- Windows app folder: `dist\BSIE\`
- Windows installer: `dist\installer\BSIE-Setup-<version>-windows.exe`
