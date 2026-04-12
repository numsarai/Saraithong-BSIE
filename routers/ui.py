"""
routers/ui.py
-------------
UI routes: SPA index, favicons, bank logos, health check.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from paths import STATIC_DIR, TEMPLATES_DIR
from core.bank_logo_registry import render_bank_logo_svg

_BASE = Path(__file__).parent.parent
_REACT_DIST = STATIC_DIR / "dist"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["ui"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Serve the React SPA if built, fallback to legacy Jinja2 template
    react_index = _REACT_DIST / "index.html"
    if react_index.exists():
        return FileResponse(str(react_index))
    return templates.TemplateResponse(request, "index.html")


@router.get("/favicon.svg")
async def favicon():
    """Serve the built frontend favicon from the path requested by browsers."""
    for candidate in (_REACT_DIST / "favicon.svg", STATIC_DIR / "favicon.svg"):
        if candidate.exists():
            return FileResponse(str(candidate), media_type="image/svg+xml")
    raise HTTPException(404, "favicon.svg not found")


@router.get("/favicon.png")
async def favicon_png():
    """Serve the program icon as PNG for browsers and in-app branding."""
    for candidate in (_REACT_DIST / "favicon.png", STATIC_DIR / "favicon.png", STATIC_DIR / "bsie-app-icon.png"):
        if candidate.exists():
            return FileResponse(str(candidate), media_type="image/png")
    raise HTTPException(404, "favicon.png not found")


@router.get("/favicon.ico")
async def favicon_ico():
    """Serve the program icon in ICO format for compatibility-oriented clients."""
    for candidate in (_REACT_DIST / "favicon.ico", STATIC_DIR / "favicon.ico", _BASE / "installer" / "bsie.ico"):
        if candidate.exists():
            return FileResponse(str(candidate), media_type="image/x-icon")
    raise HTTPException(404, "favicon.ico not found")


@router.get("/api/bank-logos/{key}.svg")
async def bank_logo_svg(key: str):
    """Serve deterministic bank logo badges from the central registry."""
    svg = render_bank_logo_svg(key, size=96)
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/app", response_class=HTMLResponse)
@router.get("/bank-manager", response_class=HTMLResponse)
async def react_spa():
    """Serve React SPA for all frontend routes."""
    react_index = _REACT_DIST / "index.html"
    if react_index.exists():
        return FileResponse(str(react_index))
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/")


@router.get("/health")
def health():
    return JSONResponse({"status": "ok"})
