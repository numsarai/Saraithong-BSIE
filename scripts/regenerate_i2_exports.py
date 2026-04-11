#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.export_anx import export_anx_from_graph
from core.export_i2_import import write_i2_import_package


DEFAULT_ROOTS = (
    REPO_ROOT / "data" / "output",
    REPO_ROOT / "data" / "exports",
)


def _is_graph_bundle_dir(path: Path) -> bool:
    return (path / "nodes.csv").exists() and (path / "edges.csv").exists()


def _discover_bundle_dirs(roots: list[Path]) -> list[Path]:
    bundle_dirs: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        root = root.resolve()
        if not root.exists():
            continue
        if _is_graph_bundle_dir(root):
            if root not in seen:
                seen.add(root)
                bundle_dirs.append(root)
            continue
        for path in sorted(root.rglob("nodes.csv")):
            bundle_dir = path.parent.resolve()
            if bundle_dir in seen or not _is_graph_bundle_dir(bundle_dir):
                continue
            seen.add(bundle_dir)
            bundle_dirs.append(bundle_dir)
    return sorted(bundle_dirs)


def _subject_for_bundle(bundle_dir: Path, meta: dict[str, object] | None) -> str:
    if meta:
        account = str(meta.get("account_number") or bundle_dir.parent.name or bundle_dir.name).strip()
        bank = str(meta.get("bank") or "").strip()
        if bank and account:
            return f"BSIE import for {bank} {account}"
        if account:
            return f"BSIE import for {account}"
    return f"BSIE import for {bundle_dir.name}"


def _comments_for_bundle(bundle_dir: Path, meta: dict[str, object] | None) -> str:
    if meta:
        account = str(meta.get("account_number") or "").strip()
        bank = str(meta.get("bank") or "").strip()
        parts = [part for part in [bank, account] if part]
        if parts:
            return (
                f"Generated from the BSIE graph bundle for {' '.join(parts)}. "
                "Import this specification inside i2 Analyst's Notebook with the companion CSV in the same folder."
            )
    return (
        f"Generated from the BSIE graph bundle at {bundle_dir}. "
        "Import this specification inside i2 Analyst's Notebook with the companion CSV in the same folder."
    )


def _update_meta(meta_path: Path) -> bool:
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    category_files = payload.setdefault("category_files", {})
    updated = False
    for key, value in {
        "anx": "i2_chart.anx",
        "i2_import_csv": "i2_import_transactions.csv",
        "i2_import_spec": "i2_import_spec.ximp",
    }.items():
        if category_files.get(key) != value:
            category_files[key] = value
            updated = True
    if updated:
        meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return updated


def regenerate_bundle(bundle_dir: Path, *, update_meta: bool = True) -> dict[str, object]:
    nodes = pd.read_csv(bundle_dir / "nodes.csv", dtype=str, keep_default_na=False).fillna("")
    edges = pd.read_csv(bundle_dir / "edges.csv", dtype=str, keep_default_na=False).fillna("")

    export_anx_from_graph(nodes, edges, bundle_dir / "i2_chart.anx")

    meta_path: Path | None = None
    meta_changed = False
    meta_payload: dict[str, object] | None = None
    if bundle_dir.name == "processed":
        candidate = bundle_dir.parent / "meta.json"
        if candidate.exists():
            meta_path = candidate
            meta_payload = json.loads(candidate.read_text(encoding="utf-8"))

    i2_paths = write_i2_import_package(
        nodes,
        edges,
        bundle_dir,
        subject=_subject_for_bundle(bundle_dir, meta_payload),
        comments=_comments_for_bundle(bundle_dir, meta_payload),
        author="BSIE",
    )

    if update_meta and meta_path is not None:
        meta_changed = _update_meta(meta_path)

    return {
        "bundle_dir": bundle_dir,
        "anx_path": bundle_dir / "i2_chart.anx",
        "csv_path": i2_paths["csv_path"],
        "spec_path": i2_paths["spec_path"],
        "meta_path": meta_path,
        "meta_changed": meta_changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate BSIE i2 artifacts (.anx and .ximp + .csv) from existing graph bundle directories."
    )
    parser.add_argument(
        "roots",
        nargs="*",
        type=Path,
        default=list(DEFAULT_ROOTS),
        help="Bundle directory or parent directory to scan. Defaults to data/output and data/exports.",
    )
    parser.add_argument(
        "--skip-meta",
        action="store_true",
        help="Do not update category_files keys inside per-account meta.json files.",
    )
    args = parser.parse_args()

    bundle_dirs = _discover_bundle_dirs([path.resolve() for path in args.roots])
    if not bundle_dirs:
        print("No graph bundle directories found.")
        return 0

    meta_updates = 0
    for bundle_dir in bundle_dirs:
        result = regenerate_bundle(bundle_dir, update_meta=not args.skip_meta)
        if result["meta_changed"]:
            meta_updates += 1
        print(
            f"[ok] {bundle_dir} -> "
            f"{result['anx_path'].name}, {result['csv_path'].name}, {result['spec_path'].name}"
        )

    print(
        f"Regenerated i2 artifacts for {len(bundle_dirs)} bundle(s). "
        f"Updated meta.json in {meta_updates} account package(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
