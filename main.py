"""
main.py
-------
Bank Statement Intelligence Engine (BSIE)
Entry point — processes a single bank statement Excel file.

Usage:
    python main.py --file data/input/example_scb.xlsx \
                   --bank scb \
                   --account 1234567890 \
                   --name "สมชาย ใจดี"
"""

import argparse
import logging
import sys
from pathlib import Path

# Make sure bsie/ is importable regardless of CWD
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.process_account import process_account


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bank Statement Intelligence Engine (BSIE)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --file data/input/example_scb.xlsx --bank scb --account 1234567890
  python main.py --file data/input/example_kbank.xlsx --bank kbank --account 123456789012 --name "นายทดสอบ"
        """,
    )
    parser.add_argument("--file",    required=True,  help="Path to input .xlsx bank statement")
    parser.add_argument("--bank",    required=True,  help="Bank key (e.g. scb, kbank)")
    parser.add_argument("--account", required=True,  help="Subject account number (10 or 12 digits)")
    parser.add_argument("--name",    default="",     help="Account holder name (optional)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger("bsie.main")

    input_path = Path(args.file)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    try:
        output_dir = process_account(
            input_file=input_path,
            bank_key=args.bank,
            subject_account=args.account,
            subject_name=args.name,
        )
        print(f"\n✅ Account Package generated successfully!")
        print(f"   → {output_dir}")
        print(f"\n   Contents:")
        for f in sorted(output_dir.rglob("*")):
            if f.is_file():
                print(f"     {f.relative_to(output_dir)}")
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
