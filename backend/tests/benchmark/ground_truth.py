"""
Ground-truth loading for the benchmark harness.

Expects a JSON file mapping receipt filenames to their correct fields:

{
  "receipt_001.jpg": {"vendor": "Tesco", "date": "2024-03-15", "amount": 23.47},
  "receipt_002.pdf": {"vendor": "Aldi",  "date": "2024-03-18", "amount": 9.99}
}
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


@dataclass
class GroundTruth:
    vendor: Optional[str]
    date: Optional[datetime]
    amount: Optional[float]


def load_ground_truth(path: str) -> Dict[str, GroundTruth]:
    raw = pd.read_csv(Path(path))
    out = {}
    for _, row in raw.iterrows():
        filename = row["receipt"]
        date = row.get("transaction_date")
        out[filename] = GroundTruth(
            vendor=row.get("party"),
            date=pd.to_datetime(date, errors="coerce", format="%d/%m/%Y") if date else None,
            amount=row.get("amount", 0)*-1,
        )
    return out

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", type=str, required=True)
    args = ap.parse_args()

    gt = load_ground_truth(args.truth)
    for filename, fields in gt.items():
        print(f"{filename}: {fields}")