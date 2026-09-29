#!/usr/bin/env python3
"""Stream iTIC/Longdo historical probe archives into compact daily road profiles.

Designed for cloud batch preprocessing. Large monthly archives are streamed in
a manual batch job, are not committed, and are discarded after processing.
The same CLI remains usable locally for debugging. The published raw probe format is:
VehicleID,gpsvalid,lat,lon,timestamp,speed,passenger_lamp,engine_acc

The archive format has no heading field, so v0.3 is deliberately
direction-neutral.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import io
import json
import math
from collections import defaultdict
from pathlib import Path
import statistics
import sys
import tarfile
from typing import Any, Iterable, TextIO

SPATIAL_DIR = Path(__file__).parents[1] / "spatial"
sys.path.insert(0, str(SPATIAL_DIR.resolve()))
import geo_admin  # noqa: E402

EARTH_M_PER_DEG_LAT = 110_574.0
EARTH_M_PER_DEG_LON_AT_EQUATOR = 111_320.0
WEEKDAY_NAMES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--network", type=Path, default=Path("data/processed/osm/core_roads.geojson"))
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument("--output-dir", type=Path, default=Path("data/processed/historical_probe/daily"))
    p.add_argument("--max-map-match-m", type=float, default=None)
    p.add_argument("--ambiguity-margin-m", type=float, default=None)
    p.add_argument("--time-bin-minutes", type=int, default=None)
    p.add_argument("--max-speed-kmh", type=float, default=None)
    p.add_argument("--limit-members", type=int, default=None)
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(float(x) for x in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def parse_probe_row(row: list[str], max_speed_kmh: float = 160.0) -> dict[str, Any] | None:
    if len(row) < 6:
        return None
    try:
        vehicle_id = str(row[0]).strip()
        gps_valid = int(str(row[1]).strip())
        lat = float(row[2])
        lon = float(row[3])
        timestamp = dt.datetime.strptime(str(row[4]).strip(), "%Y-%m-%d %H:%M:%S")
        speed_kmh = float(row[5])
    except (TypeError, ValueError):
        return None
    if not vehicle_id or gps_valid != 1:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    if not (0.0 <= speed_kmh <= max_speed_kmh):
        return None
    return {
        "vehicle_id": vehicle_id,
        "lat": lat,
        "lon": lon,
        "timestamp": timestamp,
        "speed_kmh": speed_kmh,
    }


def point_segment_distance_m(
    lon: float,
    lat: float,
    a: list[float],
    b: list[float],
) -> float:
    """Approximate local point-to-segment distance in meters."""
    cos_lat = max(0.2, math.cos(math.radians(lat)))
    sx = EARTH_M_PER_DEG_LON_AT_EQUATOR * cos_lat
    sy = EARTH_M_PER_DEG_LAT
    ax = (float(a[0]) - lon) * sx
    ay = (float(a[1]) - lat) * sy
    bx = (float(b[0]) - lon) * sx
    by = (float(b[1]) - lat) * sy
    vx, vy = bx - ax, by - ay
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * vx + ay * vy) / denom))
    px = ax + t * vx
    py = ay + t * vy
    return math.hypot(px, py)


class RoadMatcher:
    """Small stdlib spatial grid for Bangkok road matching."""

    def __init__(
        self,
        network: dict[str, Any],
        max_distance_m: float = 45.0,
        ambiguity_margin_m: float = 10.0,
        cell_deg: float = 0.002,
    ) -> None:
        self.max_distance_m = float(max_distance_m)
        self.ambiguity_margin_m = float(ambiguity_margin_m)
        self.cell_deg = float(cell_deg)
        self.segments: list[dict[str, Any]] = []
        self.grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        expand_deg = self.max_distance_m / 100_000.0

        for feature in network.get("features") or []:
            props = feature.get("properties") or {}
            rid = str(props.get("road_id") or "")
            geom = feature.get("geometry") or {}
            if not rid or geom.get("type") != "LineString":
                continue
            coords = geom.get("coordinates") or []
            for a, b in zip(coords, coords[1:]):
                if len(a) < 2 or len(b) < 2:
                    continue
                seg = {
                    "road_id": rid,
                    "road_name": props.get("display_name") or rid,
                    "network_tier": props.get("network_tier") or "URBAN",
                    "a": a,
                    "b": b,
                }
                idx = len(self.segments)
                self.segments.append(seg)
                min_lon = min(float(a[0]), float(b[0])) - expand_deg
                max_lon = max(float(a[0]), float(b[0])) + expand_deg
                min_lat = min(float(a[1]), float(b[1])) - expand_deg
                max_lat = max(float(a[1]), float(b[1])) + expand_deg
                x0, x1 = self._cell_x(min_lon), self._cell_x(max_lon)
                y0, y1 = self._cell_y(min_lat), self._cell_y(max_lat)
                for x in range(x0, x1 + 1):
                    for y in range(y0, y1 + 1):
                        self.grid[(x, y)].append(idx)

    def _cell_x(self, lon: float) -> int:
        return math.floor(float(lon) / self.cell_deg)

    def _cell_y(self, lat: float) -> int:
        return math.floor(float(lat) / self.cell_deg)

    def match(self, lon: float, lat: float) -> dict[str, Any]:
        cx, cy = self._cell_x(lon), self._cell_y(lat)
        candidates: set[int] = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                candidates.update(self.grid.get((cx + dx, cy + dy), []))

        by_road: dict[str, tuple[float, dict[str, Any]]] = {}
        for idx in candidates:
            seg = self.segments[idx]
            distance = point_segment_distance_m(lon, lat, seg["a"], seg["b"])
            prior = by_road.get(seg["road_id"])
            if prior is None or distance < prior[0]:
                by_road[seg["road_id"]] = (distance, seg)

        ranked = sorted(by_road.values(), key=lambda x: x[0])
        if not ranked or ranked[0][0] > self.max_distance_m:
            return {"status": "UNMATCHED"}

        best_distance, best = ranked[0]
        if len(ranked) > 1:
            second_distance = ranked[1][0]
            if second_distance - best_distance < self.ambiguity_margin_m:
                return {
                    "status": "AMBIGUOUS",
                    "best_road_id": best["road_id"],
                    "best_distance_m": round(best_distance, 1),
                    "second_distance_m": round(second_distance, 1),
                }

        return {
            "status": "MATCHED",
            "road_id": best["road_id"],
            "road_name": best["road_name"],
            "network_tier": best["network_tier"],
            "distance_m": round(best_distance, 1),
        }


def time_bin(timestamp: dt.datetime, minutes: int) -> tuple[int, str]:
    minute_of_day = timestamp.hour * 60 + timestamp.minute
    index = minute_of_day // minutes
    start_minute = index * minutes
    hh, mm = divmod(start_minute, 60)
    return index, f"{hh:02d}:{mm:02d}"


def aggregate_lines(
    lines: Iterable[str],
    matcher: RoadMatcher,
    districts: list[dict[str, Any]],
    time_bin_minutes: int,
    max_speed_kmh: float,
) -> list[dict[str, Any]]:
    """Return one or more daily profile documents from a text stream."""
    vehicle_speeds: dict[tuple[str, str, int, str], list[float]] = defaultdict(list)
    bucket_probe_count: dict[tuple[str, str, int, str], int] = defaultdict(int)
    bucket_meta: dict[tuple[str, str, int, str], dict[str, Any]] = {}

    stats = {
        "input_row_count": 0,
        "valid_probe_count": 0,
        "bangkok_probe_count": 0,
        "matched_probe_count": 0,
        "ambiguous_probe_count": 0,
        "unmatched_probe_count": 0,
    }

    reader = csv.reader(lines)
    for row in reader:
        stats["input_row_count"] += 1
        probe = parse_probe_row(row, max_speed_kmh=max_speed_kmh)
        if probe is None:
            continue
        stats["valid_probe_count"] += 1

        district = geo_admin.district_for_point(probe["lon"], probe["lat"], districts)
        if district is None:
            continue
        stats["bangkok_probe_count"] += 1

        match = matcher.match(probe["lon"], probe["lat"])
        if match["status"] == "AMBIGUOUS":
            stats["ambiguous_probe_count"] += 1
            continue
        if match["status"] != "MATCHED":
            stats["unmatched_probe_count"] += 1
            continue
        stats["matched_probe_count"] += 1

        date_key = probe["timestamp"].date().isoformat()
        bin_index, bin_label = time_bin(probe["timestamp"], time_bin_minutes)
        key = (date_key, match["road_id"], bin_index, probe["vehicle_id"])
        vehicle_speeds[key].append(float(probe["speed_kmh"]))
        bucket_probe_count[key] += 1
        bucket_meta[key] = {
            "date": date_key,
            "weekday": probe["timestamp"].weekday(),
            "weekday_name": WEEKDAY_NAMES[probe["timestamp"].weekday()],
            "time_bin_index": bin_index,
            "time_bin_start": bin_label,
            "road_id": match["road_id"],
            "road_name": match["road_name"],
            "network_tier": match["network_tier"],
            "district_id": str(district.get("district_id") or ""),
            "district_name_th": district.get("district_name_th") or "",
        }

    daily_groups: dict[tuple[str, str, int], dict[str, Any]] = {}
    for key, speeds in vehicle_speeds.items():
        meta = bucket_meta[key]
        group_key = (meta["date"], meta["road_id"], meta["time_bin_index"])
        group = daily_groups.setdefault(
            group_key,
            {
                **meta,
                "vehicle_medians": [],
                "probe_count": 0,
                "district_ids": set(),
                "district_names": set(),
            },
        )
        group["vehicle_medians"].append(float(statistics.median(speeds)))
        group["probe_count"] += bucket_probe_count[key]
        if meta["district_id"]:
            group["district_ids"].add(meta["district_id"])
        if meta["district_name_th"]:
            group["district_names"].add(meta["district_name_th"])

    docs_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in daily_groups.values():
        medians = group.pop("vehicle_medians")
        group["district_ids"] = sorted(group["district_ids"])
        group["district_names"] = sorted(group["district_names"])
        group["vehicle_count"] = len(medians)
        group["daily_median_speed_kmh"] = round(float(statistics.median(medians)), 1)
        group["daily_p25_speed_kmh"] = round(float(percentile(medians, 0.25)), 1)
        group["daily_p75_speed_kmh"] = round(float(percentile(medians, 0.75)), 1)
        docs_by_date[group["date"]].append(group)

    docs = []
    for date_key in sorted(docs_by_date):
        rows = sorted(
            docs_by_date[date_key],
            key=lambda x: (x["road_id"], x["time_bin_index"]),
        )
        docs.append({
            "schema": "bkk-mobility-probe-daily-profile-v0.3",
            "date": date_key,
            "timezone": "Asia/Bangkok",
            "direction_state": "NOT_AVAILABLE_IN_PUBLISHED_RAW_FORMAT",
            "aggregation_unit": "daily road x 30-minute-bin profile from per-vehicle medians",
            "source_stats": dict(stats),
            "row_count": len(rows),
            "rows": rows,
        })
    return docs


def write_daily_doc(output_dir: Path, doc: dict[str, Any], overwrite: bool) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f'{doc["date"]}.json.gz'
    if path.exists() and not overwrite:
        return path
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    return path


def process_text_file(
    path: Path,
    matcher: RoadMatcher,
    districts: list[dict[str, Any]],
    time_bin_minutes: int,
    max_speed_kmh: float,
    output_dir: Path,
    overwrite: bool,
) -> list[Path]:
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as f:
        docs = aggregate_lines(f, matcher, districts, time_bin_minutes, max_speed_kmh)
    return [write_daily_doc(output_dir, doc, overwrite) for doc in docs]


def process_tar(
    path: Path,
    matcher: RoadMatcher,
    districts: list[dict[str, Any]],
    time_bin_minutes: int,
    max_speed_kmh: float,
    output_dir: Path,
    overwrite: bool,
    limit_members: int | None,
) -> list[Path]:
    outputs: list[Path] = []
    processed_members = 0
    with tarfile.open(path, mode="r|*") as tf:
        for member in tf:
            if not member.isfile():
                continue
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            wrapper = io.TextIOWrapper(extracted, encoding="utf-8", errors="replace", newline="")
            docs = aggregate_lines(wrapper, matcher, districts, time_bin_minutes, max_speed_kmh)
            for doc in docs:
                out = write_daily_doc(output_dir, doc, overwrite)
                outputs.append(out)
                print(json.dumps({
                    "member": member.name,
                    "date": doc["date"],
                    "row_count": doc["row_count"],
                    "matched_probe_count": doc["source_stats"]["matched_probe_count"],
                    "output": str(out),
                }, ensure_ascii=False))
            processed_members += 1
            if limit_members is not None and processed_members >= limit_members:
                break
    return outputs


def main() -> int:
    args = parse_args()
    config = load(args.config)
    baseline_cfg = config.get("historical_baseline") or {}
    network = load(args.network)
    districts = geo_admin.prepare_districts(
        geo_admin.load_geojson(Path(config["admin_geometry"]["path"]))
    )
    if len(districts) != int(config["admin_geometry"].get("district_count", 50)):
        raise RuntimeError("Bangkok district geometry incomplete")

    max_match = float(
        args.max_map_match_m
        if args.max_map_match_m is not None
        else baseline_cfg.get("max_map_match_distance_m", 45)
    )
    ambiguity = float(
        args.ambiguity_margin_m
        if args.ambiguity_margin_m is not None
        else baseline_cfg.get("ambiguity_margin_m", 10)
    )
    bin_minutes = int(
        args.time_bin_minutes
        if args.time_bin_minutes is not None
        else baseline_cfg.get("time_bin_minutes", 30)
    )
    max_speed = float(
        args.max_speed_kmh
        if args.max_speed_kmh is not None
        else baseline_cfg.get("max_speed_kmh", 160)
    )

    matcher = RoadMatcher(network, max_distance_m=max_match, ambiguity_margin_m=ambiguity)
    suffixes = "".join(args.archive.suffixes).lower()
    if ".tar" in suffixes or suffixes.endswith(".tgz") or suffixes.endswith(".tbz2"):
        outputs = process_tar(
            args.archive,
            matcher,
            districts,
            bin_minutes,
            max_speed,
            args.output_dir,
            args.overwrite,
            args.limit_members,
        )
    else:
        outputs = process_text_file(
            args.archive,
            matcher,
            districts,
            bin_minutes,
            max_speed,
            args.output_dir,
            args.overwrite,
        )

    print(json.dumps({
        "archive": str(args.archive),
        "daily_profile_count": len(outputs),
        "output_dir": str(args.output_dir),
        "direction_state": "NOT_AVAILABLE_IN_PUBLISHED_RAW_FORMAT",
        "map_match_distance_m": max_match,
        "ambiguity_margin_m": ambiguity,
        "time_bin_minutes": bin_minutes,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
