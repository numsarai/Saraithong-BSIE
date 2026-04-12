# ADR-004: Thai-First i18n Architecture

**Status:** Accepted  
**Date:** 2026-04-11  
**Author:** ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง

## Context
BSIE is built for Thai police investigators. The UI must default to Thai language but allow switching to English for international collaboration or English-language documentation.

## Decision
- **Frontend**: react-i18next with `fallbackLng: 'th'` (Thai is default)
- **Backend**: Locale module with `get_locale(request)` reading `X-BSIE-Locale` or `Accept-Language` header
- **Exports**: TH Sarabun New font for all Excel/PDF outputs, column headers translatable via locale parameter
- **Detection**: `localStorage('bsie.language')` → browser language → fallback to Thai

## Rationale
- Primary users are Thai — Thai must be the default without configuration
- English needed for: international cooperation, English-language court documents
- TH Sarabun New is the standard Thai government font (widely available)
- react-i18next is the de facto standard for React i18n (lightweight, well-maintained)

## Consequences
- All new UI strings must be added to both `en.json` and `th.json`
- Export column headers may differ between Thai/English reports
- Font must be bundled with the application (included in `static/fonts/`)
