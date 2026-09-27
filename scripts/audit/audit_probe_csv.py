#!/usr/bin/env python3
"""Audit a corridor-filtered iTIC probe CSV."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("csv_file", type=Path)
    return p.parse_args()


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    frac = pos - lo
    return values[lo] * (1 - frac) + values[hi] * frac


def main() -> int:
    args = parse_args()
    speeds: list[float] = []
    headings: list[float] = []
    lats: list[float] = []
    lons: list[float] = []
    vehicles: set[str] = set()
    dates = Counter()
    schemas = Counter()
    gpsvalid = Counter()
    invalid_numeric = 0
    rows = 0

    with args.csv_file.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rows += 1
            vehicles.add(row.get("vehicle_id", ""))
            schemas[row.get("source_schema", "unknown")] += 1
            gpsvalid[row.get("gpsvalid", "")] += 1
            ts = row.get("timestamp", "")
            if len(ts) >= 10:
                dates[ts[:10]] += 1
            try:
                speed = float(row["speed_kmh"])
                lat = float(row["lat"])
                lon = float(row["lon"])
                speeds.append(speed)
                lats.append(lat)
                lons.append(lon)
                if row.get("heading_deg") not in (None, ""):
                    headings.append(float(row["heading_deg"]))
            except (KeyError, TypeError, ValueError):
                invalid_numeric += 1

    report = {
        "rows": rows,
        "unique_vehicles": len(vehicles - {""}),
        "dates": dict(sorted(dates.items())),
        "source_schemas": dict(schemas),
        "gpsvalid": dict(gpsvalid),
        "invalid_numeric_rows": invalid_numeric,
        "heading_available_rows": len(headings),
        "heading_coverage_pct": round(100 * len(headings) / rows, 2) if rows else None,
        "speed_kmh": {
            "min": min(speeds) if speeds else None,
            "p05": percentile(speeds, 0.05),
            "p50": percentile(speeds, 0.50),
            "p95": percentile(speeds, 0.95),
            "max": max(speeds) if speeds else None,
        },
        "coordinate_bbox": (
            {
                "min_lat": min(lats),
                "max_lat": max(lats),
                "min_lon": min(lons),
                "max_lon": max(lons),
            }
            if lats and lons
            else None
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
