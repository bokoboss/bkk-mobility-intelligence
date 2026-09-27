#!/usr/bin/env python3
"""Stream the documented 2026 Longdo event-history CSV and retain recent study-area rows."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
from pathlib import Path
import urllib.request
from typing import Any

DEFAULT_URL = "https://event.longdo.com/feed/2026"
USER_AGENT = "bkk-mobility-intelligence-history/0.1"
ICT = dt.timezone(dt.timedelta(hours=7))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument("--latest-pointer", type=Path, default=Path("data/raw/current/latest.json"))
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/history/recent_30d.study_area.json"),
    )
    p.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/raw/history/recent_30d.manifest.json"),
    )
    return p.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_local(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(text, fmt).replace(tzinfo=ICT)
        except ValueError:
            pass
    return None


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def in_bbox(lat: float | None, lon: float | None, config: dict[str, Any]) -> bool:
    if lat is None or lon is None:
        return False
    b = config["bbox_wgs84"]
    return (
        b["min_lat"] <= lat <= b["max_lat"]
        and b["min_lon"] <= lon <= b["max_lon"]
    )


def anchor_from_latest(pointer: Path) -> dt.datetime:
    latest = load(pointer)
    manifest = load(Path(latest["manifest"]))
    raw = manifest["sources"]["events"].get("retrieved_at_utc")
    if raw:
        return dt.datetime.fromisoformat(raw).astimezone(ICT)
    return dt.datetime.now(dt.timezone.utc).astimezone(ICT)


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "eid": row.get("eid"),
        "title": row.get("title"),
        "title_en": row.get("title_en"),
        "description": row.get("description"),
        "description_en": row.get("description_en"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "type": row.get("type"),
        "start": row.get("start"),
        "stop": row.get("stop"),
        "contributor": row.get("contributor"),
        "history_source": "Longdo Traffic event history 2026",
        "study_area_match": True,
    }


def main() -> int:
    args = parse_args()
    config = load(args.config)
    anchor = anchor_from_latest(args.latest_pointer)
    cutoff = anchor - dt.timedelta(days=args.days)

    req = urllib.request.Request(
        args.url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "identity",
        },
    )

    rows_scanned = 0
    parsed_start_rows = 0
    recent_rows = 0
    study_rows: list[dict[str, Any]] = []
    min_start: dt.datetime | None = None
    max_start: dt.datetime | None = None

    with urllib.request.urlopen(req, timeout=args.timeout) as resp:
        final_url = resp.geturl()
        content_type = resp.headers.get("Content-Type")
        last_modified = resp.headers.get("Last-Modified")
        wrapped = io.TextIOWrapper(resp, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(wrapped)
        expected = {
            "eid", "title", "title_en", "description", "description_en",
            "latitude", "longitude", "type", "start", "stop", "contributor",
        }
        fields = set(reader.fieldnames or [])
        missing = sorted(expected - fields)
        if missing:
            raise ValueError(f"event history CSV missing expected columns: {missing}")

        for row in reader:
            rows_scanned += 1
            started = parse_local(row.get("start"))
            if started is None:
                continue
            parsed_start_rows += 1
            if started < cutoff or started > anchor + dt.timedelta(minutes=10):
                continue
            recent_rows += 1
            lat = to_float(row.get("latitude"))
            lon = to_float(row.get("longitude"))
            if not in_bbox(lat, lon, config):
                continue
            study_rows.append(normalize_row(row))
            min_start = started if min_start is None or started < min_start else min_start
            max_start = started if max_start is None or started > max_start else max_start

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(study_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "pipeline": "recent-event-history-v1",
        "provider": "iTIC Foundation / Longdo Traffic",
        "source_url": args.url,
        "final_url": final_url,
        "content_type": content_type,
        "last_modified": last_modified,
        "anchor_time_ict": anchor.isoformat(),
        "cutoff_time_ict": cutoff.isoformat(),
        "window_days": args.days,
        "rows_scanned": rows_scanned,
        "rows_with_parseable_start": parsed_start_rows,
        "rows_in_recent_window_all_locations": recent_rows,
        "rows_in_recent_window_study_area": len(study_rows),
        "study_area_id": config.get("id"),
        "study_area_min_start": min_start.isoformat() if min_start else None,
        "study_area_max_start": max_start.isoformat() if max_start else None,
        "raw_full_year_persisted": False,
        "window_semantics": "event start timestamp in ICT",
    }
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
