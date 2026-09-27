#!/usr/bin/env python3
"""Assign Bangkok district IDs/names to point event records and drop bbox-corner outsiders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import geo_admin


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--events", type=Path, required=True)
    p.add_argument("--admin", type=Path, default=Path("data/reference/bangkok_districts.geojson"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--keep-outside", action="store_true")
    return p.parse_args()


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    args = parse_args()
    events = json.loads(args.events.read_text(encoding="utf-8"))
    districts = geo_admin.prepare_districts(geo_admin.load_geojson(args.admin))
    out = []
    outside = 0
    assigned = 0
    for event in events:
        lat = to_float(event.get("latitude"))
        lon = to_float(event.get("longitude"))
        district = geo_admin.district_for_point(lon, lat, districts) if lat is not None and lon is not None else None
        if not district:
            outside += 1
            if not args.keep_outside:
                continue
            row = dict(event)
            row.update({"district_id": None, "district_name_th": None, "district_name_en": None})
            out.append(row)
            continue
        assigned += 1
        row = dict(event)
        row.update({
            "district_id": district["district_id"],
            "district_name_th": district["district_name_th"],
            "district_name_en": district["district_name_en"],
        })
        out.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "input_events": len(events),
        "district_assigned": assigned,
        "outside_bangkok_polygon": outside,
        "output_events": len(out),
        "district_count": len(districts),
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
