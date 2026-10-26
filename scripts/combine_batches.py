"""Prepare a joint sample manifest without copying raw files or changing source sheets.

Example: python scripts/combine_batches.py --root /data --output manifest.json \
    --batch 20261022 /data/20261022/sample_groups.xlsx /data/20261022 \
    --batch 20261026 /data/20261026/sample_groups.xlsx /data/20261026/raw

Emits JSON for spreadsheet export; existing fit columns are deliberately omitted so
the combined analysis can recompute all samples with the same settings.
"""
import argparse
import json
import os
from pathlib import Path

import pandas as pd


def combine_batches(root, batches):
    root = Path(root).resolve()
    rows = []
    seen = set()
    labels = set()
    required = ["file_name", "sample_id", "treatment", "test_type", "Group"]
    for label, sheet, raw_dir in batches:
        if label in labels:
            raise ValueError(f"Duplicate batch label: {label}")
        labels.add(label)
        sheet = Path(sheet).resolve()
        frame = pd.read_excel(sheet)
        if not set(required).issubset(frame.columns):
            raise ValueError(f"Missing required columns in {sheet}")
        for record in frame[required].to_dict("records"):
            path = (Path(raw_dir) / str(record["file_name"]).strip()).resolve()
            if not path.is_file():
                raise FileNotFoundError(path)
            if path in seen:
                raise ValueError(f"Raw file listed twice: {path}")
            seen.add(path)
            rows.append({"file_name": os.path.relpath(path, root),
                         "sample_id": len(rows) + 1,
                         "treatment": str(record["treatment"]).strip(),
                         "test_type": str(record["test_type"]).strip(),
                         "Group": f"{label} {str(record['treatment']).strip()} {str(record['test_type']).strip()}",
                         "batch": label, "original_sample_id": int(record["sample_id"]),
                         "original_group": str(record["Group"]),
                         "source_sheet": os.path.relpath(sheet, root)})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True, help="New JSON manifest (will not overwrite)")
    parser.add_argument("--batch", nargs=3, action="append", required=True,
                        metavar=("LABEL", "SHEET", "RAW_DIR"))
    args = parser.parse_args()
    rows = combine_batches(args.root, args.batch)
    with open(args.output, "x") as stream:
        json.dump(rows, stream, indent=2)
    print(f"Validated {len(rows)} samples across {len(args.batch)} batches")


if __name__ == "__main__":
    main()
