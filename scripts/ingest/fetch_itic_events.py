#!/usr/bin/env python3
"""Fetch a snapshot of the public iTIC/Longdo traffic incident JSON feed.

The script intentionally uses only the Python standard library so Phase 0 can
validate connectivity and schema before the GIS/data stack is installed.

Source attribution:
    Intelligent Traffic Information Center Foundation (iTIC Foundation)
    https://traffic.longdo.com/feed/

Important: the published historical archive is explicitly CC BY 4.0. This
script does not assume that the same license automatically applies to every
live endpoint; endpoint-specific terms should be recorded separately.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://event.longdo.com/feed/json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--output-dir",
        default="data/raw/itic_events",
        help="Directory for raw snapshots (ignored by Git).",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def fetch_json(url: str, timeout: float) -> tuple[bytes, object]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "bkk-mobility-intelligence-phase0/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    return payload, json.loads(payload.decode("utf-8"))


def basic_schema(records: list[dict]) -> dict:
    keys = sorted({key for row in records for key in row})
    missing_eid = sum(not row.get("eid") for row in records)
    duplicate_eid = len(records) - len({row.get("eid") for row in records})
    invalid_coordinates = 0
    for row in records:
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                invalid_coordinates += 1
        except (KeyError, TypeError, ValueError):
            invalid_coordinates += 1
    return {
        "record_count": len(records),
        "keys": keys,
        "missing_eid": missing_eid,
        "duplicate_eid_within_snapshot": duplicate_eid,
        "invalid_or_missing_coordinates": invalid_coordinates,
    }


def main() -> int:
    args = parse_args()
    fetched_at = dt.datetime.now(dt.timezone.utc)
    try:
        payload, parsed = fetch_json(args.url, args.timeout)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: unable to fetch/parse {args.url}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(parsed, list) or any(not isinstance(row, dict) for row in parsed):
        print("ERROR: expected a JSON array of objects", file=sys.stderr)
        return 3

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = fetched_at.strftime("%Y%m%dT%H%M%SZ")
    data_path = output_dir / f"itic-events-{stamp}.json"
    meta_path = output_dir / f"itic-events-{stamp}.meta.json"

    data_path.write_bytes(payload)
    metadata = {
        "provider": "Intelligent Traffic Information Center Foundation (iTIC Foundation)",
        "source_url": args.url,
        "fetched_at_utc": fetched_at.isoformat(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "license_note": (
            "Historical iTIC archives are published under CC BY 4.0; "
            "verify the live endpoint terms separately."
        ),
        "schema_audit": basic_schema(parsed),
    }
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(data_path)
    print(meta_path)
    print(json.dumps(metadata["schema_audit"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
