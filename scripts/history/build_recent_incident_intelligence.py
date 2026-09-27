#!/usr/bin/env python3
"""Build 7-day / 30-day incident intelligence from matched historical event rows."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from typing import Any

ICT = dt.timezone(dt.timedelta(hours=7))

EVENT_TYPES = {
    "1": {"th": "รถเสีย", "en": "Car Break Down", "severity": 1},
    "2": {"th": "ก่อสร้าง", "en": "Construction", "severity": 1},
    "3": {"th": "อุบัติเหตุ", "en": "Accident", "severity": 3},
    "5": {"th": "ฝนตก", "en": "Rain", "severity": 3},
    "6": {"th": "น้ำท่วม", "en": "Flood", "severity": 3},
    "7": {"th": "การชุมนุม", "en": "Crowd", "severity": 3},
    "8": {"th": "ประกาศ", "en": "Information", "severity": 3},
    "9": {"th": "ด่านตรวจ", "en": "Check Point", "severity": 1},
    "10": {"th": "รถติด", "en": "Trafficjam", "severity": 1},
    "11": {"th": "จิปาถะ", "en": "MISC", "severity": 1},
    "12": {"th": "ระวัง", "en": "Warning", "severity": 3},
    "13": {"th": "การจัดงาน", "en": "Event", "severity": 3},
    "14": {"th": "ลดราคา", "en": "Sale", "severity": 1},
    "15": {"th": "เพลิงไหม้", "en": "Fire", "severity": 3},
    "16": {"th": "ร้องเรียน", "en": "Complaint", "severity": 1},
    "18": {"th": "เบี่ยงจราจร", "en": "Diversion", "severity": 1},
    "19": {"th": "ถนนปิด", "en": "Road Closed", "severity": 3},
    "20": {"th": "แผ่นดินไหว", "en": "Earthquake", "severity": 3},
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--events", type=Path, required=True)
    p.add_argument(
        "--history-manifest",
        type=Path,
        default=Path("data/raw/history/recent_30d.manifest.json"),
    )
    p.add_argument("--network", type=Path, default=Path("data/processed/osm/core_roads.geojson"))
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/history/recent_incident_intelligence.json"),
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


def canonical_title(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    prefixes = (
        "คืบหน้าเหตุ",
        "คืบหน้า",
        "อัปเดต",
        "update:",
        "update ",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip(" :-")
                changed = True
    return text


def is_route_segment_event(event: dict[str, Any]) -> bool:
    return bool(event.get("event_route_refs")) and "ช่วง" in canonical_title(event.get("title"))


def base_key(event: dict[str, Any], coord_decimals: int = 5) -> str:
    key = [
        str(event.get("confirmed_road_id") or ""),
        str(event.get("type") or ""),
        canonical_title(event.get("title")),
    ]
    if is_route_segment_event(event):
        return "|".join(key + ["route-segment"])
    lat = round(float(event["latitude"]), coord_decimals)
    lon = round(float(event["longitude"]), coord_decimals)
    return "|".join(key + [f"{lat:.{coord_decimals}f}", f"{lon:.{coord_decimals}f}"])


def end_time(event: dict[str, Any]) -> dt.datetime:
    return parse_local(event.get("stop")) or parse_local(event.get("start")) or dt.datetime.min.replace(tzinfo=ICT)


def split_episodes(rows: list[dict[str, Any]], gap_hours: float = 6.0) -> list[list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda x: parse_local(x.get("start")) or dt.datetime.min.replace(tzinfo=ICT))
    episodes: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_end: dt.datetime | None = None
    gap = dt.timedelta(hours=gap_hours)

    for row in ordered:
        started = parse_local(row.get("start"))
        if started is None:
            continue
        row_end = end_time(row)
        if current and current_end is not None and started > current_end + gap:
            episodes.append(current)
            current = []
            current_end = None
        current.append(row)
        current_end = row_end if current_end is None or row_end > current_end else current_end

    if current:
        episodes.append(current)
    return episodes


def build_episode_clusters(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if event.get("network_confirmed"):
            groups.setdefault(base_key(event), []).append(event)

    clusters: list[dict[str, Any]] = []
    for key, rows in groups.items():
        for episode in split_episodes(rows):
            rep = max(
                episode,
                key=lambda x: (
                    parse_local(x.get("start")) or dt.datetime.min.replace(tzinfo=ICT),
                    int(x.get("eid") or 0) if str(x.get("eid") or "").isdigit() else 0,
                ),
            )
            starts = [parse_local(x.get("start")) for x in episode]
            starts = [x for x in starts if x]
            stops = [parse_local(x.get("stop")) for x in episode]
            stops = [x for x in stops if x]
            episode_seed = key + "|" + (min(starts).isoformat() if starts else "")
            clusters.append(
                {
                    "cluster_id": hashlib.sha1(episode_seed.encode("utf-8")).hexdigest()[:12],
                    "road_id": rep.get("confirmed_road_id"),
                    "road_name": rep.get("confirmed_road_name"),
                    "title": rep.get("title"),
                    "event_type": str(rep.get("type") or ""),
                    "event_type_name": EVENT_TYPES.get(str(rep.get("type") or ""), {}).get("th"),
                    "event_severity": EVENT_TYPES.get(str(rep.get("type") or ""), {}).get("severity"),
                    "latitude": float(rep["latitude"]),
                    "longitude": float(rep["longitude"]),
                    "first_start": min(starts).isoformat() if starts else None,
                    "latest_start": max(starts).isoformat() if starts else None,
                    "latest_stop": max(stops).isoformat() if stops else None,
                    "record_count": len(episode),
                    "eids": sorted({str(x.get("eid")) for x in episode if x.get("eid") is not None}),
                    "cluster_scope": "ROUTE_SEGMENT" if any(is_route_segment_event(x) for x in episode) else "POINT_OR_LOCAL",
                    "location_count": len({
                        (round(float(x["latitude"]), 5), round(float(x["longitude"]), 5))
                        for x in episode
                    }),
                }
            )
    clusters.sort(key=lambda x: str(x.get("latest_start") or ""), reverse=True)
    return clusters


def road_catalog(network: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in (network.get("properties") or {}).get("road_catalog") or []:
        out[item["road_id"]] = item.get("display_name") or item["road_id"]
    return out


def cluster_time(cluster: dict[str, Any]) -> dt.datetime | None:
    raw = cluster.get("first_start")
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(str(raw))
    except ValueError:
        return parse_local(raw)


def select_window(
    clusters: list[dict[str, Any]], anchor: dt.datetime, days: int, offset_days: int = 0
) -> list[dict[str, Any]]:
    end = anchor - dt.timedelta(days=offset_days)
    start = end - dt.timedelta(days=days)
    return [
        x for x in clusters
        if (t := cluster_time(x)) is not None and start <= t < end
    ]


def ranked_counts(items: list[dict[str, Any]], key: str, labels: dict[str, str] | None = None) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "")
        if value:
            counts[value] = counts.get(value, 0) + 1
    rows = [
        {
            "id": k,
            "label": (labels or {}).get(k) or k,
            "count": v,
        }
        for k, v in counts.items()
    ]
    rows.sort(key=lambda x: (-x["count"], x["label"]))
    return rows


def daily_counts(items: list[dict[str, Any]], anchor: dt.datetime, days: int) -> list[dict[str, Any]]:
    start_date = (anchor - dt.timedelta(days=days)).date()
    counts: dict[str, int] = {}
    for i in range(days):
        d = start_date + dt.timedelta(days=i)
        counts[d.isoformat()] = 0
    for item in items:
        t = cluster_time(item)
        if t:
            key = t.date().isoformat()
            if key in counts:
                counts[key] += 1
    return [{"date": k, "count": v} for k, v in counts.items()]


def delta_pct(current: int, prior: int) -> float | None:
    if prior == 0:
        return None if current == 0 else 100.0
    return round((current - prior) * 100.0 / prior, 1)


def window_summary(
    items: list[dict[str, Any]],
    road_labels: dict[str, str],
    anchor: dt.datetime,
    days: int,
) -> dict[str, Any]:
    roads = ranked_counts(items, "road_id", road_labels)
    types = ranked_counts(
        items,
        "event_type",
        {k: v["th"] for k, v in EVENT_TYPES.items()},
    )
    return {
        "incident_count": len(items),
        "road_count": len(roads),
        "top_roads": roads[:10],
        "top_event_types": types[:10],
        "daily_counts": daily_counts(items, anchor, days),
        "clusters": items,
    }


def main() -> int:
    args = parse_args()
    events = load(args.events)
    manifest = load(args.history_manifest)
    network = load(args.network)
    anchor = dt.datetime.fromisoformat(manifest["anchor_time_ict"])
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=ICT)

    clusters = build_episode_clusters(events)
    seven = select_window(clusters, anchor, 7)
    prior_seven = select_window(clusters, anchor, 7, offset_days=7)
    thirty = select_window(clusters, anchor, 30)
    labels = road_catalog(network)

    result = {
        "schema": "bkk-mobility-history-v0.1",
        "provider": "iTIC Foundation / Longdo Traffic event history",
        "source_url": manifest.get("source_url"),
        "anchor_time_ict": anchor.isoformat(),
        "window_semantics": "event first-start time; confirmed road episodes only",
        "event_types": EVENT_TYPES,
        "windows": {
            "7d": window_summary(seven, labels, anchor, 7),
            "prior_7d": window_summary(prior_seven, labels, anchor - dt.timedelta(days=7), 7),
            "30d": window_summary(thirty, labels, anchor, 30),
        },
        "trend": {
            "latest_7d_count": len(seven),
            "prior_7d_count": len(prior_seven),
            "absolute_change": len(seven) - len(prior_seven),
            "percent_change": delta_pct(len(seven), len(prior_seven)),
            "interpretation_note": (
                "This is a descriptive comparison of reported confirmed-road event episodes, "
                "not an exposure-normalized safety or traffic-performance rate."
            ),
        },
        "quality": {
            "matched_event_rows_input": len(events),
            "episode_clusters_30d_source": len(clusters),
            "update_dedup_rule": (
                "same road/type/canonical title/location or route segment; "
                "overlapping/near-continuous records grouped into one episode"
            ),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "anchor_time_ict": result["anchor_time_ict"],
                "latest_7d": len(seven),
                "prior_7d": len(prior_seven),
                "latest_30d": len(thirty),
                "roads_7d": result["windows"]["7d"]["road_count"],
                "roads_30d": result["windows"]["30d"]["road_count"],
                "top_roads_30d": result["windows"]["30d"]["top_roads"][:5],
                "top_types_30d": result["windows"]["30d"]["top_event_types"][:5],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
