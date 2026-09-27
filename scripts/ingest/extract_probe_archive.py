#!/usr/bin/env python3
"""Stream-filter an iTIC monthly probe archive into a corridor-sized CSV.

The archive is expected to be a local .tar.bz2 downloaded from the iTIC
Open Data Archive. The script never loads the full monthly archive into memory.

Two public iTIC documentation variants are accommodated:
  9 fields: VehicleID,gpsvalid,lat,lon,timestamp,speed,heading,for_hire_light,engine_acc
  8 fields: VehicleID,gpsvalid,lat,lon,timestamp,speed,passenger_lamp,engine_acc

Source attribution:
  Intelligent Traffic Information Center Foundation (iTIC Foundation)
  Historical raw vehicle/mobile probe data: CC BY 4.0
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path
import sys
import tarfile
from typing import Iterable, Iterator

OUTPUT_FIELDS = [
    "vehicle_id",
    "gpsvalid",
    "lat",
    "lon",
    "timestamp",
    "speed_kmh",
    "heading_deg",
    "taxi_lamp",
    "engine_acc",
    "source_schema",
    "source_member",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("archive", type=Path, help="Local iTIC monthly .tar.bz2 archive")
    p.add_argument("--output", type=Path, required=True, help="Filtered CSV output")
    p.add_argument(
        "--bbox",
        required=True,
        help="min_lon,min_lat,max_lon,max_lat; use a defensible corridor envelope",
    )
    p.add_argument(
        "--date",
        action="append",
        default=[],
        help="Keep local GMT+7 date YYYY-MM-DD; repeat for multiple dates",
    )
    p.add_argument(
        "--gps-valid-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep gpsvalid=1 only (default true)",
    )
    return p.parse_args()


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        min_lon, min_lat, max_lon, max_lat = (float(x) for x in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bbox must have four comma-separated numbers") from exc
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise argparse.ArgumentTypeError("invalid bbox bounds")
    return min_lon, min_lat, max_lon, max_lat


def normalize_date(value: str) -> str:
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}; expected YYYY-MM-DD") from exc


def looks_like_header(row: list[str]) -> bool:
    lowered = {cell.strip().lower() for cell in row}
    return bool({"vehicleid", "vehicle_id", "gpsvalid", "timestamp"} & lowered)


def canonicalize(row: list[str], member: str) -> dict[str, str] | None:
    row = [cell.strip() for cell in row]
    if len(row) == 9:
        vehicle_id, gpsvalid, lat, lon, timestamp, speed, heading, lamp, engine = row
        schema = "itic-probe-9-field"
    elif len(row) == 8:
        vehicle_id, gpsvalid, lat, lon, timestamp, speed, lamp, engine = row
        heading = ""
        schema = "itic-probe-8-field"
    else:
        return None
    return {
        "vehicle_id": vehicle_id,
        "gpsvalid": gpsvalid,
        "lat": lat,
        "lon": lon,
        "timestamp": timestamp,
        "speed_kmh": speed,
        "heading_deg": heading,
        "taxi_lamp": lamp,
        "engine_acc": engine,
        "source_schema": schema,
        "source_member": member,
    }


def date_matches(timestamp: str, wanted_dates: set[str]) -> bool:
    if not wanted_dates:
        return True
    return any(timestamp.startswith(day) for day in wanted_dates)


def row_in_bbox(record: dict[str, str], bbox: tuple[float, float, float, float]) -> bool:
    try:
        lat = float(record["lat"])
        lon = float(record["lon"])
    except ValueError:
        return False
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def iter_member_rows(tf: tarfile.TarFile, member: tarfile.TarInfo) -> Iterator[list[str]]:
    raw = tf.extractfile(member)
    if raw is None:
        return
    import io

    text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
    yield from csv.reader(text)


def candidate_members(tf: tarfile.TarFile) -> Iterable[tarfile.TarInfo]:
    for member in tf:
        if member.isfile() and member.name.lower().endswith((".csv", ".txt")):
            yield member


def main() -> int:
    args = parse_args()
    try:
        bbox = parse_bbox(args.bbox)
        wanted_dates = {normalize_date(d) for d in args.date}
    except argparse.ArgumentTypeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not args.archive.exists():
        print(f"ERROR: archive not found: {args.archive}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)

    seen = 0
    written = 0
    malformed = 0
    schema_counts: dict[str, int] = {}
    member_count = 0

    with tarfile.open(args.archive, mode="r:bz2") as tf, args.output.open(
        "w", encoding="utf-8", newline=""
    ) as out:
        writer = csv.DictWriter(out, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()

        for member in candidate_members(tf):
            member_count += 1
            for row in iter_member_rows(tf, member):
                if not row or looks_like_header(row):
                    continue
                seen += 1
                record = canonicalize(row, member.name)
                if record is None:
                    malformed += 1
                    continue
                schema_counts[record["source_schema"]] = schema_counts.get(record["source_schema"], 0) + 1
                if args.gps_valid_only and record["gpsvalid"] != "1":
                    continue
                if not date_matches(record["timestamp"], wanted_dates):
                    continue
                if not row_in_bbox(record, bbox):
                    continue
                writer.writerow(record)
                written += 1

    print(f"archive={args.archive}")
    print(f"members_scanned={member_count}")
    print(f"rows_seen={seen}")
    print(f"rows_written={written}")
    print(f"malformed_or_unknown_schema={malformed}")
    print(f"schema_counts={schema_counts}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
