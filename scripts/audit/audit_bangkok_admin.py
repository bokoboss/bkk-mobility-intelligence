#!/usr/bin/env python3
"""Audit official BMA 50-district dataset resources.

This avoids relying on a single large Overpass administrative query. It reads
CKAN package metadata and probes only lightweight JSON/KML/GML-style resources.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

USER_AGENT = "bkk-mobility-intelligence-bangkok-audit/0.2"
CKAN_ROOTS = [
    "https://data.bangkok.go.th",
    "https://data.go.th",
]
PACKAGE_IDS = [
    "bae2ce5a-5990-413b-ba86-9fcf28bdebcc",
    "e537025b-1cf6-4c5b-8e46-c2e976f13283",
    "district",
]


def fetch_json(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8-sig", errors="replace"))


def fetch_prefix(url: str, limit: int = 2000, timeout: float = 25.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Range": f"bytes=0-{limit-1}",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(limit)
        return {
            "status": getattr(resp, "status", None),
            "final_url": resp.geturl(),
            "content_type": resp.headers.get("Content-Type"),
            "content_length": resp.headers.get("Content-Length"),
            "sample_prefix": raw.decode("utf-8", errors="replace")[:limit],
        }


def compact_resource(resource: dict) -> dict:
    keys = (
        "id", "name", "format", "mimetype", "url", "url_type",
        "resource_type", "last_modified", "created",
    )
    return {k: resource.get(k) for k in keys if k in resource}


def discover_package() -> tuple[dict, str, str]:
    errors = []
    for root in CKAN_ROOTS:
        for package_id in PACKAGE_IDS:
            url = (
                root.rstrip("/")
                + "/api/3/action/package_show?"
                + urllib.parse.urlencode({"id": package_id})
            )
            try:
                payload = fetch_json(url)
                if payload.get("success") and isinstance(payload.get("result"), dict):
                    return payload["result"], root, package_id
            except Exception as exc:
                errors.append(
                    f"{url}: {type(exc).__name__}: {exc}"
                )
    raise RuntimeError("; ".join(errors))


def main() -> int:
    package, root, package_id = discover_package()
    resources = [
        compact_resource(x)
        for x in package.get("resources") or []
        if isinstance(x, dict)
    ]

    probes = []
    for resource in package.get("resources") or []:
        if not isinstance(resource, dict):
            continue
        fmt = str(resource.get("format") or resource.get("mimetype") or "").casefold()
        url = resource.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        if not any(token in fmt for token in ("json", "geojson", "kml", "gml", "xml")):
            continue
        try:
            probe = fetch_prefix(url)
            probes.append({
                "resource": compact_resource(resource),
                "probe": probe,
            })
        except Exception as exc:
            probes.append({
                "resource": compact_resource(resource),
                "error": f"{type(exc).__name__}: {exc}",
            })

    result = {
        "source": "BMA Open Data CKAN",
        "ckan_root": root,
        "package_id_used": package_id,
        "dataset_id": package.get("id"),
        "name": package.get("name"),
        "title": package.get("title"),
        "metadata_modified": package.get("metadata_modified"),
        "license_title": package.get("license_title"),
        "resource_count": len(resources),
        "resources": resources,
        "lightweight_resource_probes": probes,
        "expected_district_count": 50,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
