#!/usr/bin/env python3
"""Benchmark local LLM mapping assist against synthetic bank-statement fixtures.

This harness is intentionally local-only and uses synthetic column/sample data.
It does not read uploaded evidence, parser runs, or the BSIE database.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.mapping_assist_service import suggest_mapping_with_llm, suggest_mapping_with_vision_llm

DEFAULT_MODELS = ("gemma4:26b", "gemma4:e4b", "gemma4:e2b")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "llm_mapping_benchmarks"
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Thonburi.ttf"),
)

FIXTURES: list[dict[str, Any]] = [
    {
        "id": "thai_debit_credit",
        "bank": "scb",
        "detected_bank": {"key": "scb", "confidence": 0.92},
        "columns": ["วันที่", "เวลา", "รายละเอียด", "ถอน", "ฝาก", "ยอดคงเหลือ", "ช่องทาง", "บัญชีคู่โอน"],
        "sample_rows": [
            {
                "วันที่": "2026-01-02",
                "เวลา": "09:14",
                "รายละเอียด": "TRF TO 1234567890 SOMCHAI",
                "ถอน": "1,250.00",
                "ฝาก": "",
                "ยอดคงเหลือ": "48,750.00",
                "ช่องทาง": "MOBILE",
                "บัญชีคู่โอน": "1234567890",
            },
            {
                "วันที่": "2026-01-03",
                "เวลา": "12:44",
                "รายละเอียด": "รับโอน PROMPTPAY",
                "ถอน": "",
                "ฝาก": "900.00",
                "ยอดคงเหลือ": "49,650.00",
                "ช่องทาง": "PROMPTPAY",
                "บัญชีคู่โอน": "0987654321",
            },
        ],
        "current_mapping": {"date": "วันที่", "description": "รายละเอียด"},
        "expected": {
            "date": "วันที่",
            "time": "เวลา",
            "description": "รายละเอียด",
            "debit": "ถอน",
            "credit": "ฝาก",
            "balance": "ยอดคงเหลือ",
            "channel": "ช่องทาง",
            "counterparty_account": "บัญชีคู่โอน",
        },
        "sheet_name": "Statement",
        "header_row": 3,
    },
    {
        "id": "english_signed_amount",
        "bank": "kbank",
        "detected_bank": {"key": "kbank", "confidence": 0.87},
        "columns": ["Transaction Date", "Time", "Details", "Amount", "Balance", "Channel", "From/To Account"],
        "sample_rows": [
            {
                "Transaction Date": "02/01/2026",
                "Time": "10:01",
                "Details": "FAST TRANSFER TO 1112223334",
                "Amount": "-2,000.00",
                "Balance": "80,000.00",
                "Channel": "K PLUS",
                "From/To Account": "1112223334",
            },
            {
                "Transaction Date": "03/01/2026",
                "Time": "14:21",
                "Details": "TRANSFER FROM 5556667778",
                "Amount": "5,500.00",
                "Balance": "85,500.00",
                "Channel": "ATM",
                "From/To Account": "5556667778",
            },
        ],
        "current_mapping": {"date": "Transaction Date"},
        "expected": {
            "date": "Transaction Date",
            "time": "Time",
            "description": "Details",
            "amount": "Amount",
            "balance": "Balance",
            "channel": "Channel",
            "counterparty_account": "From/To Account",
        },
        "sheet_name": "Transactions",
        "header_row": 1,
    },
    {
        "id": "ocr_noisy_signed_amount",
        "bank": "ktb",
        "detected_bank": {"key": "ktb", "confidence": 0.71},
        "columns": ["ว/ด/ป", "รายการธุรกรรม", "ยอดเงิน (+/-)", "ยอดเงินคงเหลือ", "หมายเลขบัญชีคู่รายการ", "รหัสช่องทาง"],
        "sample_rows": [
            {
                "ว/ด/ป": "04-01-2026",
                "รายการธุรกรรม": "โอนเงินออกไป 2223334445",
                "ยอดเงิน (+/-)": "-750.00",
                "ยอดเงินคงเหลือ": "30,250.00",
                "หมายเลขบัญชีคู่รายการ": "2223334445",
                "รหัสช่องทาง": "APP",
            },
            {
                "ว/ด/ป": "05-01-2026",
                "รายการธุรกรรม": "รับโอนจาก 8889990001",
                "ยอดเงิน (+/-)": "1,200.00",
                "ยอดเงินคงเหลือ": "31,450.00",
                "หมายเลขบัญชีคู่รายการ": "8889990001",
                "รหัสช่องทาง": "APP",
            },
        ],
        "current_mapping": {},
        "expected": {
            "date": "ว/ด/ป",
            "description": "รายการธุรกรรม",
            "amount": "ยอดเงิน (+/-)",
            "balance": "ยอดเงินคงเหลือ",
            "channel": "รหัสช่องทาง",
            "counterparty_account": "หมายเลขบัญชีคู่รายการ",
        },
        "sheet_name": "OCR_PAGE_1",
        "header_row": 0,
    },
]


def parse_models(value: str) -> list[str]:
    models = [item.strip() for item in value.split(",") if item.strip()]
    if not models:
        raise ValueError("At least one model is required")
    return models


def score_mapping(actual: dict[str, Any], expected: dict[str, str]) -> dict[str, Any]:
    checks = []
    for field, expected_column in expected.items():
        actual_column = actual.get(field)
        checks.append({
            "field": field,
            "expected": expected_column,
            "actual": actual_column,
            "ok": actual_column == expected_column,
        })
    correct = sum(1 for item in checks if item["ok"])
    total = len(checks)
    return {
        "correct": correct,
        "total": total,
        "score": round(correct / total, 4) if total else 0.0,
        "misses": [item for item in checks if not item["ok"]],
    }


def summarize_runs(items: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    relevant = [item[mode] for item in items if mode in item]
    correct = sum(int(item.get("correct", 0)) for item in relevant)
    total = sum(int(item.get("total", 0)) for item in relevant)
    durations = [float(item.get("duration_ms", 0)) for item in relevant]
    return {
        "score": round(correct / total, 4) if total else 0.0,
        "correct": correct,
        "total": total,
        "average_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0.0,
    }


def _font_path() -> Path | None:
    return next((path for path in FONT_CANDIDATES if path.exists()), None)


def make_fixture_image(fixture: dict[str, Any], directory: Path) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Vision benchmark requires Pillow (PIL)") from exc

    columns = fixture["columns"]
    rows = fixture["sample_rows"][:2]
    cell_width = 230
    cell_height = 68
    margin = 32
    width = margin * 2 + cell_width * len(columns)
    height = margin * 2 + cell_height * (len(rows) + 2)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font_path = _font_path()
    if font_path:
        title_font = ImageFont.truetype(str(font_path), 28)
        cell_font = ImageFont.truetype(str(font_path), 20)
        small_font = ImageFont.truetype(str(font_path), 17)
    else:
        title_font = ImageFont.load_default()
        cell_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.text(
        (margin, 8),
        f"Synthetic {fixture['bank'].upper()} statement fixture: {fixture['id']}",
        fill=(25, 25, 25),
        font=title_font,
    )
    header_y = margin + 35
    for index, column in enumerate(columns):
        x = margin + index * cell_width
        draw.rectangle(
            (x, header_y, x + cell_width, header_y + cell_height),
            outline=(80, 80, 80),
            fill=(232, 238, 247),
        )
        draw.text((x + 8, header_y + 12), str(column)[:24], fill=(0, 0, 0), font=cell_font)

    for row_index, row in enumerate(rows):
        y = header_y + cell_height * (row_index + 1)
        for column_index, column in enumerate(columns):
            x = margin + column_index * cell_width
            draw.rectangle((x, y, x + cell_width, y + cell_height), outline=(120, 120, 120), fill="white")
            draw.text((x + 8, y + 12), str(row.get(column, ""))[:28], fill=(20, 20, 20), font=small_font)

    path = directory / f"{fixture['id']}.png"
    image.save(path)
    return path


async def run_text_fixture(model: str, fixture: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await suggest_mapping_with_llm(
            model=model,
            bank=fixture["bank"],
            detected_bank=fixture["detected_bank"],
            columns=fixture["columns"],
            sample_rows=fixture["sample_rows"],
            current_mapping=fixture["current_mapping"],
            sheet_name=fixture["sheet_name"],
            header_row=fixture["header_row"],
        )
        scoring = score_mapping(result["mapping"], fixture["expected"])
        return {
            "status": "ok",
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            **scoring,
            "validation_ok": result["validation"]["ok"],
            "confidence": result["confidence"],
            "mapping": result["mapping"],
            "warnings": result.get("warnings", []),
        }
    except Exception as exc:
        return {
            "status": type(exc).__name__,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "score": 0.0,
            "correct": 0,
            "total": len(fixture["expected"]),
            "misses": [],
            "error": str(exc),
        }


async def run_vision_fixture(model: str, fixture: dict[str, Any], image_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await suggest_mapping_with_vision_llm(
            model=model,
            file_path=image_path,
            bank=fixture["bank"],
            detected_bank=fixture["detected_bank"],
            columns=fixture["columns"],
            sample_rows=fixture["sample_rows"],
            current_mapping=fixture["current_mapping"],
            sheet_name=fixture["sheet_name"],
            header_row=fixture["header_row"],
        )
        scoring = score_mapping(result["mapping"], fixture["expected"])
        return {
            "status": "ok",
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            **scoring,
            "validation_ok": result["validation"]["ok"],
            "confidence": result["confidence"],
            "mapping": result["mapping"],
            "warnings": result.get("warnings", []),
        }
    except Exception as exc:
        return {
            "status": type(exc).__name__,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "score": 0.0,
            "correct": 0,
            "total": len(fixture["expected"]),
            "misses": [],
            "error": str(exc),
        }


async def run_model(
    *,
    model: str,
    fixtures: list[dict[str, Any]],
    mode: str,
    image_paths: dict[str, Path],
) -> dict[str, Any]:
    result: dict[str, Any] = {"model": model, "fixtures": []}
    for fixture in fixtures:
        item: dict[str, Any] = {"fixture": fixture["id"]}
        if mode in {"text", "both"}:
            item["text"] = await run_text_fixture(model, fixture)
        if mode in {"vision", "both"}:
            item["vision"] = await run_vision_fixture(model, fixture, image_paths[fixture["id"]])
        result["fixtures"].append(item)
    if mode in {"text", "both"}:
        result["text_summary"] = summarize_runs(result["fixtures"], "text")
    if mode in {"vision", "both"}:
        result["vision_summary"] = summarize_runs(result["fixtures"], "vision")
    return result


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mapping Model Benchmark",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Local only: `{payload['local_only']}`",
        f"- Mode: `{payload['mode']}`",
        f"- Models: `{', '.join(payload['models'])}`",
        f"- Fixtures: `{', '.join(item['id'] for item in payload['fixtures'])}`",
        "",
        "## Summary",
        "",
        "| Model | Text score | Text avg | Vision score | Vision avg |",
        "|---|---:|---:|---:|---:|",
    ]
    for model_result in payload["results"]:
        text = model_result.get("text_summary", {})
        vision = model_result.get("vision_summary", {})
        text_score = _format_score(text)
        vision_score = _format_score(vision)
        text_avg = _format_duration(text)
        vision_avg = _format_duration(vision)
        lines.append(f"| `{model_result['model']}` | {text_score} | {text_avg} | {vision_score} | {vision_avg} |")

    lines.extend(["", "## Fixture Details", ""])
    for model_result in payload["results"]:
        lines.extend([f"### `{model_result['model']}`", ""])
        for fixture_result in model_result["fixtures"]:
            lines.append(f"- `{fixture_result['fixture']}`")
            for mode in ("text", "vision"):
                if mode not in fixture_result:
                    continue
                item = fixture_result[mode]
                status = item.get("status", "unknown")
                score = f"{item.get('correct', 0)}/{item.get('total', 0)}"
                duration = f"{item.get('duration_ms', 0):,.2f} ms"
                validation = item.get("validation_ok")
                lines.append(f"  - {mode}: `{status}`, score `{score}`, duration `{duration}`, validation `{validation}`")
                for miss in item.get("misses", [])[:6]:
                    lines.append(
                        f"    - miss `{miss['field']}`: expected `{miss['expected']}`, actual `{miss.get('actual')}`"
                    )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_score(summary: dict[str, Any]) -> str:
    if not summary:
        return "-"
    return f"{summary.get('correct', 0)}/{summary.get('total', 0)} ({summary.get('score', 0):.2%})"


def _format_duration(summary: dict[str, Any]) -> str:
    if not summary:
        return "-"
    return f"{float(summary.get('average_duration_ms', 0)):,.2f} ms"


async def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    models = parse_models(args.models)
    selected_fixture_ids = set(args.fixtures or [])
    fixtures = [fixture for fixture in FIXTURES if not selected_fixture_ids or fixture["id"] in selected_fixture_ids]
    if selected_fixture_ids and len(fixtures) != len(selected_fixture_ids):
        known = {fixture["id"] for fixture in FIXTURES}
        unknown = sorted(selected_fixture_ids - known)
        raise ValueError(f"Unknown fixture id(s): {', '.join(unknown)}")

    output_dir = Path(args.output_dir).expanduser().resolve()
    fixture_dir_context: tempfile.TemporaryDirectory[str] | None = None
    if args.keep_fixtures:
        fixture_dir = output_dir / "fixtures" / args.run_id
        fixture_dir.mkdir(parents=True, exist_ok=True)
    else:
        fixture_dir_context = tempfile.TemporaryDirectory(prefix="bsie-llm-fixtures-")
        fixture_dir = Path(fixture_dir_context.name)

    try:
        image_paths = {fixture["id"]: make_fixture_image(fixture, fixture_dir) for fixture in fixtures}
        results = []
        for model in models:
            print(f"benchmark start: {model}", flush=True)
            results.append(await run_model(model=model, fixtures=fixtures, mode=args.mode, image_paths=image_paths))
            print(f"benchmark done: {model}", flush=True)
        return {
            "source": "bsie_mapping_model_benchmark",
            "local_only": True,
            "synthetic_only": True,
            "generated_at": datetime.now(UTC).isoformat(),
            "run_id": args.run_id,
            "mode": args.mode,
            "models": models,
            "fixtures": [
                {
                    "id": fixture["id"],
                    "bank": fixture["bank"],
                    "expected_fields": sorted(fixture["expected"]),
                }
                for fixture in fixtures
            ],
            "results": results,
            "fixture_images": {key: str(path) for key, path in image_paths.items()} if args.keep_fixtures else {},
        }
    finally:
        if fixture_dir_context is not None:
            fixture_dir_context.cleanup()


def write_outputs(payload: dict[str, Any], args: argparse.Namespace) -> dict[str, str]:
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"mapping_model_benchmark_{args.run_id}.json"
    md_path = output_dir / f"mapping_model_benchmark_{args.run_id}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outputs = {"json": str(json_path)}
    if not args.no_markdown:
        md_path.write_text(build_markdown(payload), encoding="utf-8")
        outputs["markdown"] = str(md_path)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark BSIE local mapping-assist models with synthetic fixtures")
    parser.add_argument(
        "--models",
        default=os.getenv("BSIE_MAPPING_BENCH_MODELS", ",".join(DEFAULT_MODELS)),
        help="Comma-separated Ollama model tags",
    )
    parser.add_argument("--mode", choices=("text", "vision", "both"), default="both", help="Benchmark mode")
    parser.add_argument(
        "--fixture",
        action="append",
        dest="fixtures",
        choices=[fixture["id"] for fixture in FIXTURES],
        help="Fixture id to run; may be provided more than once",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for JSON/Markdown reports")
    parser.add_argument("--run-id", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"), help="Stable run id")
    parser.add_argument("--keep-fixtures", action="store_true", help="Keep generated synthetic PNG fixtures")
    parser.add_argument("--no-markdown", action="store_true", help="Only write JSON output")
    parser.add_argument("--print-json", action="store_true", help="Print full JSON payload to stdout")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = asyncio.run(run_benchmark(args))
    outputs = write_outputs(payload, args)
    print(json.dumps({"outputs": outputs, "run_id": payload["run_id"]}, ensure_ascii=False, indent=2))
    if args.print_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
