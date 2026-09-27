#!/usr/bin/env python3
"""Sample TMD Domain-2 24-hour precipitation forecast over the study area.

The 3-km CSV is cached per model cycle, streamed row-by-row, spatially filtered
to the pilot envelope, and aggregated to OSM roads via nearest retained grid
cells. No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
import shutil
import sys
import urllib.request
from typing import Any

UTC = dt.timezone.utc
USER_AGENT = "bkk-mobility-intelligence-tmd-grid/0.1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--context",
        type=Path,
        default=Path("data/raw/current_context/tmd_precip_context.json"),
    )
    p.add_argument(
        "--config",
        type=Path,
        default=Path("config/study_area.json"),
    )
    p.add_argument(
        "--network",
        type=Path,
        default=Path("data/processed/osm/core_roads.geojson"),
    )
    p.add_argument(
        "--admin",
        type=Path,
        default=Path("data/reference/bangkok_districts.geojson"),
    )
    p.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/cache/tmd"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/flood/tmd_precip_grid_sample.json"),
    )
    p.add_argument("--padding-deg", type=float, default=0.05)
    p.add_argument("--timeout", type=float, default=90.0)
    return p.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_init(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y%m%d%H").replace(tzinfo=UTC)


def parse_valid_header(value: str) -> dt.datetime | None:
    text = str(value or "").strip()
    for fmt in ("%H:%MZ %Y-%m-%d", "%Y-%m-%d_%H:%MZ"):
        try:
            return dt.datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    return None


def choose_next_24h_column(headers: list[str], init_time: dt.datetime) -> tuple[int, dt.datetime]:
    candidates: list[tuple[dt.datetime, int]] = []
    for idx, value in enumerate(headers[2:], start=2):
        parsed = parse_valid_header(value)
        if parsed and parsed > init_time:
            candidates.append((parsed, idx))
    if not candidates:
        raise ValueError("no p24h forecast column is later than the model initialization time")
    candidates.sort()
    valid, idx = candidates[0]
    return idx, valid


def to_float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def download(url: str, output: Path, timeout: float) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as f:
        shutil.copyfileobj(resp, f, length=1024 * 1024)
    tmp.replace(output)


def buffered_bbox(config: dict[str, Any], padding: float) -> dict[str, float]:
    bbox = config["bbox_wgs84"]
    return {
        "min_lon": float(bbox["min_lon"]) - padding,
        "min_lat": float(bbox["min_lat"]) - padding,
        "max_lon": float(bbox["max_lon"]) + padding,
        "max_lat": float(bbox["max_lat"]) + padding,
    }


def inside(lat: float, lon: float, bbox: dict[str, float]) -> bool:
    return (
        bbox["min_lat"] <= lat <= bbox["max_lat"]
        and bbox["min_lon"] <= lon <= bbox["max_lon"]
    )


def read_grid(
    csv_path: Path,
    bbox: dict[str, float],
    init_time: dt.datetime,
) -> tuple[list[dict[str, Any]], str]:
    points: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or len(header) < 3:
            raise ValueError("TMD p24h CSV does not contain expected lat/lon/forecast columns")
        idx, valid_time = choose_next_24h_column(header, init_time)
        for row in reader:
            if len(row) <= idx:
                continue
            lat = to_float(row[0])
            lon = to_float(row[1])
            mm = to_float(row[idx])
            if lat is None or lon is None or mm is None:
                continue
            if not inside(lat, lon, bbox):
                continue
            points.append(
                {
                    "grid_id": f"{lat:.6f},{lon:.6f}",
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "next_24h_mm": round(mm, 3),
                }
            )
    return points, valid_time.isoformat()


def iter_line_coords(feature: dict[str, Any]):
    geom = feature.get("geometry") or {}
    if geom.get("type") == "LineString":
        for coord in geom.get("coordinates") or []:
            if len(coord) >= 2:
                yield float(coord[0]), float(coord[1])
    elif geom.get("type") == "MultiLineString":
        for line in geom.get("coordinates") or []:
            for coord in line:
                if len(coord) >= 2:
                    yield float(coord[0]), float(coord[1])


def nearest_point_index(lon: float, lat: float, points: list[dict[str, Any]]) -> int:
    # Small-envelope approximation is sufficient for nearest 3-km grid cells.
    cos_lat = math.cos(math.radians(lat))
    best_idx = 0
    best = float("inf")
    for idx, point in enumerate(points):
        dx = (float(point["longitude"]) - lon) * cos_lat
        dy = float(point["latitude"]) - lat
        dist2 = dx * dx + dy * dy
        if dist2 < best:
            best = dist2
            best_idx = idx
    return best_idx


def road_aggregates(network: dict[str, Any], points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not points:
        return []
    groups: dict[str, dict[str, Any]] = {}
    for feature in network.get("features") or []:
        props = feature.get("properties") or {}
        road_id = props.get("road_id")
        if not road_id:
            continue
        group = groups.setdefault(
            str(road_id),
            {
                "road_id": str(road_id),
                "road_name": props.get("display_name") or str(road_id),
                "priority": bool(props.get("priority")),
                "network_tier": props.get("network_tier"),
                "district_ids": set(),
                "district_names": set(),
                "cell_indexes": set(),
            },
        )
        group["district_ids"].update(props.get("district_ids") or [])
        group["district_names"].update(props.get("district_names") or [])
        for lon, lat in iter_line_coords(feature):
            group["cell_indexes"].add(nearest_point_index(lon, lat, points))

    rows = []
    for group in groups.values():
        values = [
            float(points[idx]["next_24h_mm"])
            for idx in sorted(group["cell_indexes"])
        ]
        if not values:
            continue
        rows.append(
            {
                "road_id": group["road_id"],
                "road_name": group["road_name"],
                "priority": group["priority"],
                "network_tier": group.get("network_tier"),
                "district_ids": sorted(group.get("district_ids") or []),
                "district_names": sorted(group.get("district_names") or []),
                "grid_cell_count": len(values),
                "next_24h_mean_mm": round(sum(values) / len(values), 2),
                "next_24h_p90_mm": round(percentile(values, 0.9) or 0.0, 2),
                "next_24h_max_mm": round(max(values), 2),
            }
        )
    rows.sort(key=lambda x: (-x["next_24h_max_mm"], x["road_name"]))
    return rows


def assign_grid_districts(
    points: list[dict[str, Any]],
    districts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out = []
    for point in points:
        row = dict(point)
        district = None
        for candidate in districts:
            min_lon, min_lat, max_lon, max_lat = candidate["bbox"]
            lon = float(row["longitude"])
            lat = float(row["latitude"])
            if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                continue
            if geo_admin.point_in_geometry(lon, lat, candidate["geometry"]):
                district = candidate
                break
        row["district_id"] = district["district_id"] if district else None
        row["district_name_th"] = district["district_name_th"] if district else None
        row["district_name_en"] = district["district_name_en"] if district else None
        out.append(row)
    return out


def district_aggregates(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for point in points:
        did = str(point.get("district_id") or "")
        if not did:
            continue
        row = groups.setdefault(
            did,
            {
                "district_id": did,
                "district_name_th": point.get("district_name_th") or did,
                "district_name_en": point.get("district_name_en") or "",
                "values": [],
            },
        )
        row["values"].append(float(point["next_24h_mm"]))
    result = []
    for row in groups.values():
        values = row.pop("values")
        result.append(
            {
                **row,
                "grid_cell_count": len(values),
                "next_24h_mean_mm": round(sum(values) / len(values), 2),
                "next_24h_p90_mm": round(percentile(values, 0.9) or 0.0, 2),
                "next_24h_max_mm": round(max(values), 2),
            }
        )
    result.sort(key=lambda x: (-x["next_24h_max_mm"], x["district_name_th"]))
    return result


def unavailable_result(context: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "schema": "tmd-precip-grid-sample-v0.1",
        "status": "UNAVAILABLE",
        "reason": reason,
        "model_init_time_utc": context.get("initial_time"),
        "source_is_forecast": True,
        "not_observed_rainfall": True,
        "grid_points": [],
        "road_forecast": [],
        "district_forecast": [],
    }


def main() -> int:
    args = parse_args()
    context = load(args.context)
    config = load(args.config)
    sys.path.insert(0, str(Path("scripts/spatial").resolve()))
    global geo_admin
    import geo_admin

    product = (context.get("precip_products") or {}).get("p24h_d02_csv") or {}
    url = product.get("download_url")
    init_raw = str(context.get("initial_time") or "")
    if not url or not init_raw:
        result = unavailable_result(context, "TMD p24h Domain-2 CSV product is not available")
    else:
        try:
            init_time = parse_init(init_raw)
            cache_path = args.cache_dir / f"p24h.d02.{init_raw}.csv"
            if not cache_path.exists() or cache_path.stat().st_size == 0:
                download(str(url), cache_path, args.timeout)

            bbox = buffered_bbox(config, args.padding_deg)
            points, valid_time = read_grid(cache_path, bbox, init_time)
            network = load(args.network)
            road_rows = road_aggregates(network, points)

            admin_doc = load(args.admin)
            districts = geo_admin.prepare_districts(admin_doc)
            if len(districts) != int((config.get("admin_geometry") or {}).get("district_count", 50)):
                raise RuntimeError(f"district geometry count mismatch: {len(districts)}")
            assigned_points = assign_grid_districts(points, districts)
            bangkok_points = [x for x in assigned_points if x.get("district_id")]
            district_rows = district_aggregates(bangkok_points)
            values = [float(x["next_24h_mm"]) for x in bangkok_points]

            result = {
                "schema": "tmd-precip-grid-sample-v0.1",
                "status": "READY",
                "provider": "Thai Meteorological Department NWP",
                "model_init_time_utc": init_time.isoformat(),
                "forecast_valid_time_utc": valid_time,
                "forecast_measure": "24-hour accumulated precipitation",
                "domain": "Domain 2 (Thailand 3km)",
                "source_url": url,
                "source_is_forecast": True,
                "not_observed_rainfall": True,
                "study_area_id": config.get("id"),
                "bbox_padding_deg": args.padding_deg,
                "grid_summary": {
                    "point_count": len(points),
                    "min_mm": round(min(values), 2) if values else None,
                    "median_mm": round(percentile(values, 0.5) or 0.0, 2) if values else None,
                    "p90_mm": round(percentile(values, 0.9) or 0.0, 2) if values else None,
                    "max_mm": round(max(values), 2) if values else None,
                },
                "grid_points": bangkok_points,
                "road_forecast": road_rows,
                "district_forecast": district_rows,
            }
        except Exception as exc:
            result = unavailable_result(
                context,
                f"{type(exc).__name__}: {exc}",
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result.get("status"),
                "model_init_time_utc": result.get("model_init_time_utc"),
                "forecast_valid_time_utc": result.get("forecast_valid_time_utc"),
                "grid_summary": result.get("grid_summary"),
                "top_road_forecast": (result.get("road_forecast") or [])[:5],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
