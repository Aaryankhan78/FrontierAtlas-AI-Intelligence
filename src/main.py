
import argparse
import asyncio
import json
from pathlib import Path

from src.pipeline import run_pipeline
from src.exporters.sheets import export_google_sheets


def main():
    parser = argparse.ArgumentParser(
        description="FrontierAtlas AI Intelligence Pipeline"
    )

    parser.add_argument(
        "--papers",
        type=int,
        default=100,
        help="Number of arXiv papers (maximum 2000)"
    )

    parser.add_argument(
        "--startups",
        type=int,
        default=1000,
        help="Number of AI startups to collect"
    )

    parser.add_argument(
        "--products",
        type=int,
        default=1000,
        help="Number of AI products to collect"
    )

    parser.add_argument(
        "--export-sheets",
        action="store_true",
        help="Export records to configured Google Sheet"
    )

    args = parser.parse_args()

    if not 1 <= args.papers <= 2000:
        parser.error("--papers must be between 1 and 2000")

    if args.startups < 1 or args.products < 1:
        parser.error("--startups and --products must be at least 1")

    records, mapping_log = asyncio.run(
        run_pipeline(
            paper_limit=args.papers,
            startup_limit=args.startups,
            product_limit=args.products
        )
    )

    Path("data").mkdir(exist_ok=True)

    Path("data/entity_mapping_log.json").write_text(
        json.dumps(mapping_log, indent=2),
        encoding="utf-8"
    )

    if args.export_sheets:
        export_google_sheets(records, mapping_log)

    counts = {}

    for record in records:
        record_type = record.get("recordType", "UNKNOWN")
        counts[record_type] = counts.get(record_type, 0) + 1

    print("\n========== PIPELINE SUMMARY ==========")

    for record_type, count in sorted(counts.items()):
        print(f"{record_type}: {count}")

    print(f"Total stored records: {len(records)}")
    print("Pipeline complete.")


if __name__ == "__main__":
    main()
