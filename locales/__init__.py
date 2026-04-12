"""
Backend i18n support for BSIE.

Provides locale detection from HTTP requests and a simple translation lookup.
Default language is Thai ('th') since primary users are Thai police investigators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

from locales.messages import MESSAGES

SUPPORTED_LOCALES = ("th", "en")
DEFAULT_LOCALE = "th"


def get_locale(request: "Request | None" = None) -> str:
    """Extract preferred locale from an HTTP request.

    Checks (in order):
    1. ``X-BSIE-Locale`` custom header (explicit client preference)
    2. ``Accept-Language`` header (browser / frontend preference)
    3. Falls back to *th*.
    """
    if request is None:
        return DEFAULT_LOCALE

    # 1. Explicit header
    explicit = (request.headers.get("x-bsie-locale") or "").strip().lower()
    if explicit in SUPPORTED_LOCALES:
        return explicit

    # 2. Accept-Language (simplified — pick first match)
    accept = (request.headers.get("accept-language") or "").lower()
    for locale in SUPPORTED_LOCALES:
        if locale in accept:
            return locale

    return DEFAULT_LOCALE


def t(key: str, locale: str = DEFAULT_LOCALE) -> str:
    """Look up a translated message by *key* for the given *locale*.

    Falls back to the Thai message, then the raw key itself.
    """
    lang = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    msg = MESSAGES.get(lang, {}).get(key)
    if msg is not None:
        return msg
    # Fallback chain: try Thai, then return key as-is
    msg = MESSAGES.get(DEFAULT_LOCALE, {}).get(key)
    return msg if msg is not None else key
