#!/usr/bin/env python3
"""Small stdlib-only administrative geometry helpers for Bangkok-wide v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_geojson(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def geometry_rings(geometry: dict[str, Any]):
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "Polygon":
        yield coords
    elif gtype == "MultiPolygon":
        for polygon in coords:
            yield polygon


def ring_bbox(ring: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in ring]
    ys = [float(p[1]) for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def geometry_bbox(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    boxes = []
    for polygon in geometry_rings(geometry):
        if polygon and polygon[0]:
            boxes.append(ring_bbox(polygon[0]))
    if not boxes:
        return None
    return (
        min(x[0] for x in boxes),
        min(x[1] for x in boxes),
        max(x[2] for x in boxes),
        max(x[3] for x in boxes),
    )


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        if ((yi > lat) != (yj > lat)):
            denom = yj - yi
            xcross = (xj - xi) * (lat - yi) / denom + xi if denom else xi
            if lon < xcross:
                inside = not inside
        j = i
    return inside


def point_in_geometry(lon: float, lat: float, geometry: dict[str, Any]) -> bool:
    for polygon in geometry_rings(geometry):
        if not polygon:
            continue
        outer = polygon[0]
        if not point_in_ring(lon, lat, outer):
            continue
        if any(point_in_ring(lon, lat, hole) for hole in polygon[1:]):
            continue
        return True
    return False


def district_props(feature: dict[str, Any]) -> dict[str, Any]:
    p = feature.get("properties") or {}
    raw_th = str(p.get("dname") or p.get("district_name_th") or "").strip()
    return {
        "district_id": str(p.get("dcode") or p.get("district_id") or "").strip(),
        "district_name_th": raw_th.removeprefix("เขต").strip() or raw_th,
        "district_name_en": str(p.get("dname_e") or p.get("district_name_en") or "").strip(),
    }


def prepare_districts(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for feature in doc.get("features") or []:
        geom = feature.get("geometry") or {}
        bbox = geometry_bbox(geom)
        props = district_props(feature)
        if not bbox or not props["district_id"]:
            continue
        out.append({
            **props,
            "bbox": bbox,
            "geometry": geom,
        })
    out.sort(key=lambda x: x["district_id"])
    return out


def district_for_point(
    lon: float, lat: float, districts: list[dict[str, Any]]
) -> dict[str, Any] | None:
    for district in districts:
        min_lon, min_lat, max_lon, max_lat = district["bbox"]
        if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
            continue
        if point_in_geometry(lon, lat, district["geometry"]):
            return district
    return None


def sample_line_points(coords: list[list[float]], max_points: int = 24) -> list[list[float]]:
    if len(coords) <= max_points:
        points = list(coords)
    else:
        step = (len(coords) - 1) / (max_points - 1)
        points = [coords[round(i * step)] for i in range(max_points)]
    mids = []
    for a, b in zip(points, points[1:]):
        mids.append([(float(a[0]) + float(b[0])) / 2, (float(a[1]) + float(b[1])) / 2])
    return points + mids


def districts_for_line(
    coords: list[list[float]], districts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for point in sample_line_points(coords):
        if len(point) < 2:
            continue
        district = district_for_point(float(point[0]), float(point[1]), districts)
        if not district:
            continue
        did = district["district_id"]
        row = counts.setdefault(did, {**district, "sample_hits": 0})
        row["sample_hits"] += 1
    return sorted(counts.values(), key=lambda x: (-x["sample_hits"], x["district_id"]))


def normalized_district_geojson(doc: dict[str, Any], decimals: int = 5) -> dict[str, Any]:
    def rounded(value):
        if isinstance(value, list):
            return [rounded(x) for x in value]
        if isinstance(value, float):
            return round(value, decimals)
        return value

    features = []
    for feature in doc.get("features") or []:
        props = district_props(feature)
        if not props["district_id"]:
            continue
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {
                **(feature.get("geometry") or {}),
                "coordinates": rounded((feature.get("geometry") or {}).get("coordinates") or []),
            },
        })
    return {
        "type": "FeatureCollection",
        "bbox": doc.get("bbox"),
        "properties": {
            "district_count": len(features),
            "geometry_role": "Bangkok district staging geometry",
        },
        "features": features,
    }
