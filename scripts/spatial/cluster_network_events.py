#!/usr/bin/env python3
"""Cluster confirmed current feed records into distinct core-road incidents."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--events", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--coord-decimals", type=int, default=5)
    return p.parse_args()


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def is_route_segment_event(event: dict[str, Any]) -> bool:
    title = normalize_text(event.get("title"))
    refs = event.get("event_route_refs") or []
    return bool(refs) and "ช่วง" in title


def cluster_key(event: dict[str, Any], coord_decimals: int) -> str:
    base = [
        str(event.get("confirmed_road_id") or ""),
        str(event.get("type") or ""),
        normalize_text(event.get("title")),
    ]
    if is_route_segment_event(event):
        # Route feeds can publish several point records for the same named
        # highway segment/status. Treat the segment title as the incident unit.
        return "|".join(base + ["route-segment"])

    lat = round(float(event["latitude"]), coord_decimals)
    lon = round(float(event["longitude"]), coord_decimals)
    return "|".join(
        base
        + [
            f"{lat:.{coord_decimals}f}",
            f"{lon:.{coord_decimals}f}",
        ]
    )


def build_clusters(
    events: list[dict[str, Any]], coord_decimals: int
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if not event.get("network_confirmed"):
            continue
        groups.setdefault(cluster_key(event, coord_decimals), []).append(event)

    clusters: list[dict[str, Any]] = []
    road_counts: dict[str, int] = {}

    for key, rows in groups.items():
        representative = max(
            rows,
            key=lambda x: (
                str(x.get("start") or ""),
                int(x.get("eid") or 0)
                if str(x.get("eid") or "").isdigit()
                else 0,
            ),
        )
        road_id = representative["confirmed_road_id"]
        road_counts[road_id] = road_counts.get(road_id, 0) + 1
        starts = sorted(str(r.get("start")) for r in rows if r.get("start"))
        stops = sorted(str(r.get("stop")) for r in rows if r.get("stop"))
        eids = sorted({str(r.get("eid")) for r in rows if r.get("eid") is not None})

        clusters.append(
            {
                "cluster_id": hashlib.sha1(
                    key.encode("utf-8")
                ).hexdigest()[:12],
                "road_id": road_id,
                "title": representative.get("title"),
                "event_type": representative.get("type"),
                "latitude": float(representative["latitude"]),
                "longitude": float(representative["longitude"]),
                "first_start": starts[0] if starts else None,
                "latest_start": starts[-1] if starts else None,
                "latest_stop": stops[-1] if stops else None,
                "record_count": len(rows),
                "eids": eids,
                "match_classes": sorted(
                    {str(r.get("network_match_class")) for r in rows}
                ),
                "event_route_refs": sorted(
                    {
                        ref
                        for r in rows
                        for ref in (r.get("event_route_refs") or [])
                    }
                ),
                "cluster_scope": (
                    "ROUTE_SEGMENT"
                    if any(is_route_segment_event(r) for r in rows)
                    else "POINT_OR_LOCAL"
                ),
                "location_count": len(
                    {
                        (
                            round(float(r["latitude"]), coord_decimals),
                            round(float(r["longitude"]), coord_decimals),
                        )
                        for r in rows
                    }
                ),
            }
        )

    clusters.sort(
        key=lambda x: (
            str(x.get("latest_start") or ""),
            str(x.get("road_id") or ""),
        ),
        reverse=True,
    )

    return {
        "summary": {
            "confirmed_record_count": sum(len(v) for v in groups.values()),
            "confirmed_cluster_count": len(clusters),
            "clusters_by_road": road_counts,
            "clustering_rule": (
                "route segment: confirmed road + type + normalized segment title; "
                "point/local: confirmed road + type + title + rounded coordinate"
            ),
            "coordinate_decimals": coord_decimals,
        },
        "clusters": clusters,
    }


def main() -> int:
    args = parse_args()
    events = json.loads(args.events.read_text(encoding="utf-8"))
    result = build_clusters(events, args.coord_decimals)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
