# ADR-003: Duplicate Prevention — File Reuse Policy

**Status:** Accepted  
**Date:** 2026-04-11  
**Author:** ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง

## Context
Previously, uploading the same file multiple times created duplicate records in every table (files, transactions, raw_import_rows). This caused 574 duplicate files and 47,451 duplicate transactions, inflating the database from ~50MB to 475MB.

## Decision
1. **Upload dedup**: When uploading a file with identical SHA-256 hash, reuse the existing FileRecord instead of creating a new one.
2. **Re-process cleanup**: When re-processing a file (new mapping), delete prior parser run data (transactions, raw rows, batches, alerts, matches) and mark old runs as "superseded".
3. **User choice**: Show dialog letting investigator choose "View Previous Results" or "Re-process (new mapping)".

## Rationale
- Prevents data bloat from repeated testing/experimentation
- Prior results are still accessible via the "superseded" parser run status
- Evidence files on disk are not duplicated (reuse same evidence directory)
- Investigators can re-analyze with corrected mapping without accumulating garbage data

## Consequences
- Old transaction data is permanently deleted on re-process (not soft-deleted)
- Backup should be taken before bulk re-processing
- "Superseded" parser runs remain in history for audit trail
