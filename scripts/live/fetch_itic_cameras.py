#!/usr/bin/env python3
"""Fetch public iTIC/Longdo traffic-camera metadata and assess pilot coverage."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request
from typing import Any, Iterable

DEFAULT_URL = "https://camera.longdo.com/feed/?command=json"
USER_AGENT = "bkk-mobility-intelligence-phase0/0.6"
EARTH_M = 6371008.8


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
    p.add_argument("--nearest", type=int, default=10)
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
        (to_float(lower[k]) for k in ("latitude", "lat", "y") if k in lower),
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
    return "camid" in {str(k).lower() for k in row} or "imgurl" in {
        str(k).lower() for k in row
    }


def distance_to_bbox_m(
    lat: float, lon: float, config: dict[str, Any]
) -> float:
    b = config["bbox_wgs84"]
    clamped_lat = min(max(lat, b["min_lat"]), b["max_lat"])
    clamped_lon = min(max(lon, b["min_lon"]), b["max_lon"])
    lat0 = math.radians((lat + clamped_lat) / 2)
    dy = math.radians(lat - clamped_lat) * EARTH_M
    dx = (
        math.radians(lon - clamped_lon)
        * EARTH_M
        * math.cos(lat0)
    )
    return math.hypot(dx, dy)


def normalized_camera(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    lat, lon = extract_lat_lon(row)
    cid = camera_id(row)
    return {
        "camera_id": cid,
        "title": row.get("title"),
        "organization": row.get("organization"),
        "latitude": lat,
        "longitude": lon,
        "lastupdate": row.get("lastupdate"),
        "imgurl": row.get("imgurl"),
        "imgurl_specific": row.get("imgurl_specific"),
        "hls_url": row.get("hls_url"),
        "distance_to_study_bbox_m": (
            round(distance_to_bbox_m(lat, lon, config), 1)
            if lat is not None and lon is not None
            else None
        ),
        "official_jpeg_template": (
            "https://cameras.iticfoundation.org/api/jpeg2.php?camid="
            + urllib.parse.quote(cid, safe="")
            if cid
            else None
        ),
    }


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

    normalized = [normalized_camera(row, config) for row in records]
    study = [
        row
        for row in normalized
        if in_bbox(row["latitude"], row["longitude"], config)
    ]
    nearest = sorted(
        normalized,
        key=lambda x: (
            x["distance_to_study_bbox_m"]
            if x["distance_to_study_bbox_m"] is not None
            else float("inf")
        ),
    )[: args.nearest]

    within_1km = sum(
        1
        for row in normalized
        if row["distance_to_study_bbox_m"] is not None
        and row["distance_to_study_bbox_m"] <= 1000
    )
    within_3km = sum(
        1
        for row in normalized
        if row["distance_to_study_bbox_m"] is not None
        and row["distance_to_study_bbox_m"] <= 3000
    )

    result = {
        "provider": "iTIC Foundation / Longdo Traffic Camera",
        "source_url": args.url,
        "final_url": final_url,
        "content_type": content_type,
        "retrieved_at_utc": retrieved_at.isoformat(),
        "all_candidate_camera_records": len(records),
        "study_area_camera_records": len(study),
        "within_1km_of_bbox": within_1km,
        "within_3km_of_bbox": within_3km,
        "observed_keys": keys,
        "study_area_records": study,
        "nearest_cameras": nearest,
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
                "within_1km_of_bbox": within_1km,
                "within_3km_of_bbox": within_3km,
                "nearest_cameras": nearest[:5],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
