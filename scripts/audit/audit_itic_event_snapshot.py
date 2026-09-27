#!/usr/bin/env python3
"""Audit an iTIC event JSON snapshot without external dependencies."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = json.loads(args.snapshot.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise SystemExit("Expected a JSON list")

    icons = Counter()
    contributors = Counter()
    starts: list[str] = []
    stops: list[str] = []
    coords: list[tuple[float, float]] = []
    ids: list[str] = []

    for row in records:
        if row.get("icon"):
            icons[str(row["icon"])] += 1
        if row.get("contributor"):
            contributors[str(row["contributor"])] += 1
        if row.get("start"):
            starts.append(str(row["start"]))
        if row.get("stop"):
            stops.append(str(row["stop"]))
        if row.get("eid") is not None:
            ids.append(str(row["eid"]))
        try:
            coords.append((float(row["latitude"]), float(row["longitude"])))
        except (KeyError, TypeError, ValueError):
            pass

    report = {
        "records": len(records),
        "unique_eids": len(set(ids)),
        "duplicate_rows_by_eid": len(ids) - len(set(ids)),
        "start_min": min(starts) if starts else None,
        "start_max": max(starts) if starts else None,
        "stop_min": min(stops) if stops else None,
        "stop_max": max(stops) if stops else None,
        "coordinate_bbox": (
            {
                "min_lat": min(lat for lat, _ in coords),
                "max_lat": max(lat for lat, _ in coords),
                "min_lon": min(lon for _, lon in coords),
                "max_lon": max(lon for _, lon in coords),
            }
            if coords
            else None
        ),
        "top_event_icons": icons.most_common(20),
        "top_contributors": contributors.most_common(20),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
