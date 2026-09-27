#!/usr/bin/env python3
"""Audit Bangkok OSM administrative geometry before citywide expansion."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "bkk-mobility-intelligence-bangkok-audit/0.1"


def fetch(query: str) -> tuple[dict, str]:
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    errors = []
    for endpoint in ENDPOINTS:
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=80) as resp:
                return json.loads(resp.read().decode("utf-8")), endpoint
        except Exception as exc:
            errors.append(f"{endpoint}: {type(exc).__name__}: {exc}")
    raise RuntimeError("; ".join(errors))


def bbox_from_element(el: dict) -> dict | None:
    bounds = el.get("bounds") or {}
    keys = ("minlat", "minlon", "maxlat", "maxlon")
    if not all(k in bounds for k in keys):
        return None
    return {
        "min_lon": float(bounds["minlon"]),
        "min_lat": float(bounds["minlat"]),
        "max_lon": float(bounds["maxlon"]),
        "max_lat": float(bounds["maxlat"]),
    }


def main() -> int:
    province_q = """
[out:json][timeout:60];
relation["boundary"="administrative"]["ISO3166-2"="TH-10"];
out tags bb;
"""
    province_doc, endpoint = fetch(province_q)
    provinces = [x for x in province_doc.get("elements", []) if x.get("type") == "relation"]
    if len(provinces) != 1:
        raise RuntimeError(f"expected one Bangkok relation, got {len(provinces)}")
    province = provinces[0]
    bbox = bbox_from_element(province)
    if not bbox:
        raise RuntimeError("Bangkok relation has no bounds")

    district_q = """
[out:json][timeout:60];
area["boundary"="administrative"]["ISO3166-2"="TH-10"]->.bkk;
relation(area.bkk)["boundary"="administrative"]["admin_level"="6"];
out tags bb;
"""
    districts_doc, district_endpoint = fetch(district_q)
    districts = []
    for el in districts_doc.get("elements", []):
        if el.get("type") != "relation":
            continue
        tags = el.get("tags") or {}
        name_th = tags.get("name:th") or tags.get("name")
        name_en = tags.get("name:en")
        districts.append({
            "relation_id": el.get("id"),
            "name_th": name_th,
            "name_en": name_en,
            "admin_level": tags.get("admin_level"),
            "boundary": tags.get("boundary"),
            "bbox": bbox_from_element(el),
        })
    districts.sort(key=lambda x: str(x.get("name_th") or ""))

    result = {
        "province": {
            "relation_id": province.get("id"),
            "name": (province.get("tags") or {}).get("name"),
            "name_en": (province.get("tags") or {}).get("name:en"),
            "iso3166_2": (province.get("tags") or {}).get("ISO3166-2"),
            "admin_level": (province.get("tags") or {}).get("admin_level"),
            "bbox_wgs84": bbox,
        },
        "district_count": len(districts),
        "districts": districts,
        "validation": {
            "expected_district_count": 50,
            "district_count_ok": len(districts) == 50,
            "province_relation_unique": True,
        },
        "overpass_endpoint": endpoint,
        "district_endpoint": district_endpoint,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if len(districts) != 50:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
