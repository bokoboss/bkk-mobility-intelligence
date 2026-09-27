#!/usr/bin/env python3
"""Audit the official BMA 50-district KML resource directly."""

from __future__ import annotations

import io
import json
import math
import re
import urllib.request
import xml.etree.ElementTree as ET

URL = "https://data.bangkok.go.th/dataset/e537025b-1cf6-4c5b-8e46-c2e976f13283/resource/0f40f9b4-617b-46a9-8806-f590da610954/download/district.kml"
USER_AGENT = "bkk-mobility-intelligence-bangkok-audit/0.3"
NS = {"kml": "http://www.opengis.net/kml/2.2"}


def fetch() -> bytes:
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.google-earth.kml+xml,application/xml,text/xml,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def parse_coord_text(text: str | None) -> list[list[float]]:
    out = []
    for token in re.split(r"\s+", (text or "").strip()):
        if not token:
            continue
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            continue
        if math.isfinite(lon) and math.isfinite(lat):
            out.append([lon, lat])
    return out


def field_map(pm: ET.Element) -> dict[str, str]:
    fields = {}
    for data in pm.findall(".//kml:ExtendedData/kml:Data", NS):
        name = data.get("name")
        value = data.findtext("kml:value", default="", namespaces=NS)
        if name:
            fields[name] = value
    for sd in pm.findall(".//kml:ExtendedData/kml:SchemaData/kml:SimpleData", NS):
        name = sd.get("name")
        if name:
            fields[name] = sd.text or ""
    return fields


def main() -> int:
    raw = fetch()
    root = ET.fromstring(raw)
    placemarks = root.findall(".//kml:Placemark", NS)
    rows = []
    all_coords = []

    for pm in placemarks:
        name = pm.findtext("kml:name", default="", namespaces=NS).strip()
        fields = field_map(pm)
        rings = []
        for node in pm.findall(".//kml:Polygon//kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", NS):
            coords = parse_coord_text(node.text)
            if len(coords) >= 4:
                rings.append(coords)
                all_coords.extend(coords)
        rows.append({
            "name": name,
            "fields": fields,
            "polygon_count": len(rings),
            "coordinate_count": sum(len(x) for x in rings),
        })

    if not all_coords:
        raise RuntimeError("KML contained no polygon coordinates")
    lons = [x[0] for x in all_coords]
    lats = [x[1] for x in all_coords]
    result = {
        "source_url": URL,
        "byte_count": len(raw),
        "placemark_count": len(placemarks),
        "polygon_placemark_count": sum(1 for x in rows if x["polygon_count"]),
        "bbox_wgs84": {
            "min_lon": min(lons),
            "min_lat": min(lats),
            "max_lon": max(lons),
            "max_lat": max(lats),
        },
        "sample": rows[:8],
        "names": [x["name"] for x in rows],
        "field_names": sorted({
            key for row in rows for key in row["fields"].keys()
        }),
        "validation": {
            "expected_district_count": 50,
            "district_count_ok": len([x for x in rows if x["polygon_count"]]) == 50,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["validation"]["district_count_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
