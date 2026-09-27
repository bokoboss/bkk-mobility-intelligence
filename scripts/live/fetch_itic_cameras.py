#!/usr/bin/env python3
"""Fetch public iTIC/Longdo traffic-camera metadata and filter to pilot bbox.

This stage handles metadata only. Camera imagery is treated as visual
validation/context, not a quantitative traffic-speed source.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import urllib.request
from typing import Any, Iterable

DEFAULT_URL = "https://camera.longdo.com/feed/?command=json"
USER_AGENT = "bkk-mobility-intelligence-phase0/0.5"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/current_context/cameras.study_area.json"),
    )
    p.add_argument("--timeout", type=float, default=30.0)
    return p.parse_args()


def recursive_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from recursive_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from recursive_dicts(child)


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_lat_lon(row: dict[str, Any]) -> tuple[float | None, float | None]:
    lower = {str(k).lower(): v for k, v in row.items()}
    lat = next(
        (
            to_float(lower[k])
            for k in ("latitude", "lat", "y")
            if k in lower
        ),
        None,
    )
    lon = next(
        (
            to_float(lower[k])
            for k in ("longitude", "lon", "lng", "long", "x")
            if k in lower
        ),
        None,
    )
    return lat, lon


def in_bbox(
    lat: float | None, lon: float | None, config: dict[str, Any]
) -> bool:
    if lat is None or lon is None:
        return False
    b = config["bbox_wgs84"]
    return (
        b["min_lat"] <= lat <= b["max_lat"]
        and b["min_lon"] <= lon <= b["max_lon"]
    )


def camera_id(row: dict[str, Any]) -> str | None:
    lower = {str(k).lower(): v for k, v in row.items()}
    for key in ("camid", "camera_id", "camcode", "code", "id"):
        value = lower.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def likely_camera_record(row: dict[str, Any]) -> bool:
    lat, lon = extract_lat_lon(row)
    if lat is None or lon is None:
        return False
    lower_keys = {str(k).lower() for k in row}
    return bool(
        lower_keys
        & {
            "camid",
            "camera_id",
            "camcode",
            "code",
            "id",
            "name",
            "title",
            "description",
        }
    )


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    retrieved_at = dt.datetime.now(dt.timezone.utc)

    req = urllib.request.Request(args.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=args.timeout) as resp:
        body = resp.read()
        final_url = resp.geturl()
        content_type = resp.headers.get("Content-Type")

    parsed = json.loads(body.decode("utf-8-sig"))
    records = [r for r in recursive_dicts(parsed) if likely_camera_record(r)]

    keys = sorted({str(k) for row in records for k in row})
    study: list[dict[str, Any]] = []
    for row in records:
        lat, lon = extract_lat_lon(row)
        if not in_bbox(lat, lon, config):
            continue
        cid = camera_id(row)
        out = dict(row)
        out["_normalized"] = {
            "camera_id": cid,
            "latitude": lat,
            "longitude": lon,
            "jpeg_url": (
                "https://cameras.iticfoundation.org/api/jpeg2.php?camid="
                + urllib.parse.quote(cid, safe="")
                if cid
                else None
            ),
        }
        study.append(out)

    result = {
        "provider": "iTIC Foundation / Longdo Traffic Camera",
        "source_url": args.url,
        "final_url": final_url,
        "content_type": content_type,
        "retrieved_at_utc": retrieved_at.isoformat(),
        "all_candidate_camera_records": len(records),
        "study_area_camera_records": len(study),
        "observed_keys": keys,
        "records": study,
        "usage_note": (
            "Camera metadata/imagery is visual context only; it is not treated "
            "as quantitative segment speed."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "all_candidate_camera_records": len(records),
                "study_area_camera_records": len(study),
                "observed_keys": keys[:80],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    import urllib.parse
    raise SystemExit(main())
