"""
routers/banks.py
----------------
Bank management API routes: list, detail, create, delete, and learn.
"""

import json
import logging

from services.auth_service import require_auth
from fastapi import Depends, APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from core.bank_logo_registry import find_bank_logo_record
from paths import BUILTIN_CONFIG_DIR, CONFIG_DIR
from utils.app_helpers import builtin_bank_keys, collect_bank_configs, get_bank_logo_catalog, get_banks

logger = logging.getLogger("bsie.api")

router = APIRouter(prefix="/api", tags=["banks"], dependencies=[Depends(require_auth)])


@router.get("/banks")
async def api_banks():
    return JSONResponse(get_banks())


@router.get("/bank-logo-catalog")
async def api_bank_logo_catalog():
    return JSONResponse(get_bank_logo_catalog())


@router.get("/banks/{key}")
async def api_bank_get(key: str):
    """Return full config for a specific bank (user override takes priority)."""
    f = CONFIG_DIR / f"{key}.json"
    template_source = "custom"
    if not f.exists():
        f = BUILTIN_CONFIG_DIR / f"{key}.json"
        template_source = "builtin"
    if not f.exists():
        raise HTTPException(404, f"Bank '{key}' not found")
    cfg = json.loads(f.read_text(encoding="utf-8"))
    brand = find_bank_logo_record(
        key,
        display_name=str(cfg.get("bank_name", key.upper()) or key.upper()),
        has_template=True,
        template_source=template_source,
    )
    brand["is_builtin"] = template_source == "builtin"
    return JSONResponse({**brand, "key": key, **cfg})


@router.post("/banks")
async def api_bank_create(request: Request):
    """Create or update a bank config file from JSON body."""
    body = await request.json()
    key  = body.get("key", "").strip().lower().replace(" ", "_")
    if not key:
        raise HTTPException(400, "Bank key is required")
    # Protect built-in banks from overwrite unless flagged
    builtin = builtin_bank_keys()
    if key in builtin and not body.get("overwrite_builtin"):
        raise HTTPException(400, f"'{key}' is a built-in bank. Set overwrite_builtin=true to overwrite.")
    cfg = {
        "bank_name":       body.get("bank_name", key.upper()),
        "sheet_index":     int(body.get("sheet_index", 0)),
        "header_row":      int(body.get("header_row", 0)),
        "format_type":     body.get("format_type", "standard"),
        "currency":        body.get("currency", "THB"),
        "amount_mode":     body.get("amount_mode", "signed"),
        "column_mapping":  body.get("column_mapping", {}),
    }
    dest = CONFIG_DIR / f"{key}.json"
    dest.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Bank config saved: %s", dest)
    return JSONResponse({
        "status": "ok",
        "key": key,
        "name": cfg["bank_name"],
        "logo": find_bank_logo_record(key, display_name=cfg["bank_name"], has_template=True, template_source="custom"),
    })


@router.delete("/banks/{key}")
async def api_bank_delete(key: str):
    """Delete a bank config. Built-in banks are protected."""
    builtin = builtin_bank_keys()
    if key in builtin:
        raise HTTPException(400, f"Cannot delete built-in bank '{key}'")
    f = CONFIG_DIR / f"{key}.json"
    if not f.exists():
        raise HTTPException(404, f"Bank '{key}' not found")
    f.unlink()
    return JSONResponse({"status": "deleted", "key": key})


@router.post("/banks/learn")
async def api_bank_learn(request: Request):
    """
    Learn a new bank template from a confirmed column mapping.
    Accepts: { key, bank_name, format_type, amount_mode, confirmed_mapping, all_columns }
    Generates a bank config with the actual column names as aliases.
    """
    body = await request.json()
    key  = body.get("key", "").strip().lower().replace(" ", "_")
    if not key:
        raise HTTPException(400, "Bank key is required")

    confirmed_mapping: dict = body.get("confirmed_mapping", {})
    # Build column_mapping: each logical field -> [the actual column name used]
    col_mapping = {}
    for field, col in confirmed_mapping.items():
        if col:
            col_mapping[field] = [col]

    cfg = {
        "bank_name":      body.get("bank_name", key.upper()),
        "sheet_index":    int(body.get("sheet_index", 0)),
        "header_row":     int(body.get("header_row", 0)),
        "format_type":    body.get("format_type", "standard"),
        "currency":       "THB",
        "amount_mode":    body.get("amount_mode", "signed"),
        "column_mapping": col_mapping,
    }
    dest = CONFIG_DIR / f"{key}.json"
    dest.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Learned new bank config: %s (%s)", key, cfg["bank_name"])
    return JSONResponse({"status": "learned", "key": key, "name": cfg["bank_name"]})
