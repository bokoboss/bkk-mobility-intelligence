#!/usr/bin/env python3
"""Fetch recent events through Longdo Traffic's public event-search JSON endpoint.

The browser search UI calls /event.json with Unix from/to timestamps. This
client follows that documented-by-implementation contract, paginates in blocks
of 1,000, filters to the configured study-area bbox, and stores only the recent
window needed by the POC.
"""

from __future__ import annotations

import argparse
import datetime as dt
from html import unescape
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
from typing import Any

ENDPOINT = "https://traffic.longdo.com/event.json"
USER_AGENT = "bkk-mobility-intelligence-history/0.2"
ICT = dt.timezone(dt.timedelta(hours=7))
TAG_RE = re.compile(r"<[^>]+>")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", default=ENDPOINT)
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument("--latest-pointer", type=Path, default=Path("data/raw/current/latest.json"))
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--page-size", type=int, default=1000)
    p.add_argument("--max-pages", type=int, default=100)
    p.add_argument("--timeout", type=float, default=45.0)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/history/recent_30d.study_area.json"),
    )
    p.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/raw/history/recent_30d.manifest.json"),
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


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def in_bbox(lat: float | None, lon: float | None, config: dict[str, Any]) -> bool:
    if lat is None or lon is None:
        return False
    b = config["bbox_wgs84"]
    return (
        b["min_lat"] <= lat <= b["max_lat"]
        and b["min_lon"] <= lon <= b["max_lon"]
    )


def anchor_from_latest(pointer: Path) -> dt.datetime:
    latest = load(pointer)
    manifest = load(Path(latest["manifest"]))
    raw = manifest["sources"]["events"].get("retrieved_at_utc")
    if raw:
        return dt.datetime.fromisoformat(raw).astimezone(ICT)
    return dt.datetime.now(dt.timezone.utc).astimezone(ICT)


def clean_html(value: Any) -> str:
    text = TAG_RE.sub(" ", str(value or ""))
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def direct_route_refs(item: dict[str, Any]) -> list[str]:
    value = item.get("routeno")
    if value in (None, ""):
        return []
    return sorted({
        part.strip()
        for part in re.split(r"[;,/ ]+", str(value))
        if part.strip().isdigit()
    })


def contributor_text(value: Any) -> str | None:
    if isinstance(value, list):
        vals = [str(x).strip() for x in value if str(x).strip()]
        return ", ".join(vals) or None
    text = str(value or "").strip()
    return text or None


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "eid": item.get("eid"),
        "title": item.get("title"),
        "title_en": item.get("title_en"),
        "description": clean_html(item.get("comment")),
        "description_en": clean_html(item.get("comment_en")),
        "latitude": item.get("latitude"),
        "longitude": item.get("longitude"),
        # In /event.json the field named severity is the event-type/tag ID.
        "type": str(item.get("severity") or ""),
        "severity_level": item.get("severity_level"),
        "start": item.get("start_time"),
        "stop": item.get("stop_time"),
        "reported_at": item.get("createtime"),
        "updated_at": item.get("updatedtime"),
        "contributor": contributor_text(item.get("contributor")),
        "route_refs": direct_route_refs(item),
        "routename": item.get("routename"),
        "direction": item.get("direction"),
        "km": item.get("km"),
        "kmstop": item.get("kmstop"),
        "source_status": item.get("status"),
        "history_source": "Longdo Traffic event search JSON",
        "study_area_match": True,
    }


def fetch_page(
    endpoint: str,
    page: int,
    page_size: int,
    start: dt.datetime,
    end: dt.datetime,
    timeout: float,
) -> dict[str, Any]:
    params = {
        "page": page,
        "name": "",
        "creator": "",
        "from": int(start.timestamp()),
        "to": int(end.timestamp()),
        "ordered": "DESC",
        "eventtype": 0,
        "pagger": page_size,
        "now": int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000),
    }
    url = endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("item"), list):
        raise ValueError("unexpected /event.json response schema")
    return payload


def main() -> int:
    args = parse_args()
    config = load(args.config)
    anchor = anchor_from_latest(args.latest_pointer)
    cutoff = anchor - dt.timedelta(days=args.days)
    # Small forward allowance covers clock/retrieval skew without adding a day.
    query_end = anchor + dt.timedelta(minutes=10)

    study_rows: list[dict[str, Any]] = []
    seen_eids: set[str] = set()
    page_fingerprints: set[tuple[str | None, str | None]] = set()
    total_items = 0
    pages_fetched = 0
    max_reported: dt.datetime | None = None
    min_reported: dt.datetime | None = None
    max_start: dt.datetime | None = None
    min_start: dt.datetime | None = None

    for page in range(1, args.max_pages + 1):
        payload = fetch_page(
            args.endpoint, page, args.page_size, cutoff, query_end, args.timeout
        )
        items = payload["item"]
        pages_fetched += 1
        if not items:
            break

        fingerprint = (
            str(items[0].get("eid")) if items else None,
            str(items[-1].get("eid")) if items else None,
        )
        if fingerprint in page_fingerprints:
            raise RuntimeError(f"pagination repeated page fingerprint at page {page}: {fingerprint}")
        page_fingerprints.add(fingerprint)

        total_items += len(items)
        for item in items:
            eid = str(item.get("eid") or "")
            if not eid or eid in seen_eids:
                continue
            seen_eids.add(eid)

            reported = parse_local(item.get("createtime"))
            started = parse_local(item.get("start_time"))
            if reported:
                min_reported = reported if min_reported is None or reported < min_reported else min_reported
                max_reported = reported if max_reported is None or reported > max_reported else max_reported
            if started:
                min_start = started if min_start is None or started < min_start else min_start
                max_start = started if max_start is None or started > max_start else max_start

            lat = to_float(item.get("latitude"))
            lon = to_float(item.get("longitude"))
            if in_bbox(lat, lon, config):
                study_rows.append(normalize_item(item))

        if len(items) < args.page_size:
            break
    else:
        raise RuntimeError(f"event search exceeded max pages ({args.max_pages})")

    # The source is considered current only if the newest report is reasonably
    # close to our live-feed retrieval anchor.
    coverage_lag_min = (
        (anchor - max_reported).total_seconds() / 60 if max_reported else None
    )
    coverage_status = (
        "CURRENT"
        if coverage_lag_min is not None and -10 <= coverage_lag_min <= 180
        else "STALE_OR_UNKNOWN"
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(study_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "pipeline": "recent-event-search-v2",
        "provider": "iTIC Foundation / Longdo Traffic",
        "source_url": args.endpoint,
        "query_contract": "/event.json page/from/to/ordered/eventtype/pagger",
        "anchor_time_ict": anchor.isoformat(),
        "cutoff_time_ict": cutoff.isoformat(),
        "window_days": args.days,
        "page_size": args.page_size,
        "pages_fetched": pages_fetched,
        "unique_events_in_query": len(seen_eids),
        "response_items_scanned": total_items,
        "rows_in_study_area": len(study_rows),
        "study_area_id": config.get("id"),
        "source_min_reported_at": min_reported.isoformat() if min_reported else None,
        "source_max_reported_at": max_reported.isoformat() if max_reported else None,
        "source_min_start": min_start.isoformat() if min_start else None,
        "source_max_start": max_start.isoformat() if max_start else None,
        "coverage_lag_minutes": round(coverage_lag_min, 2) if coverage_lag_min is not None else None,
        "coverage_status": coverage_status,
        "raw_full_window_all_locations_persisted": False,
        "window_semantics": "server search by reported date; analytics by event episode start",
    }
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    if coverage_status != "CURRENT":
        print(json.dumps({
            "warning": "recent event search coverage is not current enough for 7D/30D UI",
            "coverage_lag_minutes": manifest["coverage_lag_minutes"],
        }, ensure_ascii=False))
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
