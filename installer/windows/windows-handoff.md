# BSIE Windows Handoff

Use this on the Windows PC where you want to continue development or produce
the Windows installer.

## 1. Pull the current branch

From the repo root:

```powershell
git checkout Smarter-BSIE
git pull origin Smarter-BSIE
```

## 2. Prepare the machine

Install these if the PC does not already have them:

- Git
- Python 3.12
- Node.js LTS
- Inno Setup 6 if you plan to build the Windows installer

Then run:

```powershell
installer\windows\prepare_windows_pc.cmd
```

That script:

- checks Python and Node
- creates `.venv` if needed
- installs Python dependencies
- installs frontend dependencies
- tells you the exact next commands for dev and release

If you only want a quick prerequisite check:

```powershell
powershell -ExecutionPolicy Bypass -File installer/windows/prepare_windows_pc.ps1 -CheckOnly
```

## 3. Run in development mode

Open terminal 1:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open terminal 2:

```powershell
cd frontend
npm run dev
```

Dev URLs:

- App: `http://localhost:6776`
- API: `http://localhost:8757/api`
- Health: `http://localhost:8757/health`

## 4. Build the Windows release

From the repo root:

```powershell
installer\windows\build_release.cmd
```

Or directly:

```powershell
powershell -ExecutionPolicy Bypass -File installer/windows/build_release.ps1
```

Expected outputs:

- `dist\BSIE\BSIE.exe`
- `dist\installer\BSIE-Setup-<version>-windows.exe`

## 5. Manual checks before leaving the PC

After the release build:

1. Run `dist\installer\BSIE-Setup-<version>-windows.exe`
2. Install with default options
3. Launch BSIE and confirm the browser opens
4. Confirm the tray icon appears
5. Quit BSIE from the tray
6. Uninstall BSIE and confirm shortcuts are removed

## 6. Current release context

The repo is already prepared for version-synced packaging:

- release version is read from `VERSION`
- frontend version display is wired to the same source
- Windows installer version is injected from `build_release.ps1`
- macOS release artifact for version `3.0.1` has already been built and smoke-tested
