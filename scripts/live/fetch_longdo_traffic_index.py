#!/usr/bin/env python3
"""Fetch Longdo Traffic Index as current Bangkok metropolitan context.

Official documentation states the index is 0-10 and recalculated every five
minutes. This metric is city/metropolitan context, NOT road-segment speed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import urllib.request
from typing import Any

DEFAULT_URL = "https://traffic.longdo.com/api/json/traffic/index?callback=bkkmi"
USER_AGENT = "bkk-mobility-intelligence-phase0/0.5"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/current_context/traffic_index.json"),
    )
    p.add_argument("--timeout", type=float, default=30.0)
    return p.parse_args()


def unwrap_jsonp(text: str) -> Any:
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    match = re.match(
        r"^[A-Za-z_$][A-Za-z0-9_$\.]*\s*\((.*)\)\s*;?\s*$",
        stripped,
        re.DOTALL,
    )
    if not match:
        raise ValueError("response is neither JSON nor JSONP")
    return json.loads(match.group(1))


def fetch(url: str, timeout: float) -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        headers = {
            "final_url": resp.geturl(),
            "content_type": resp.headers.get("Content-Type"),
            "date": resp.headers.get("Date"),
            "last_modified": resp.headers.get("Last-Modified"),
        }
    return body, headers


def normalize(payload: Any, retrieved_at: dt.datetime) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("traffic index payload must be an object")
    index = float(payload["index"])
    if not 0 <= index <= 10:
        raise ValueError(f"traffic index outside expected 0-10 range: {index}")
    source_unix = int(payload["time"])
    source_time = dt.datetime.fromtimestamp(source_unix, tz=dt.timezone.utc)
    age_min = (retrieved_at - source_time).total_seconds() / 60
    return {
        "index": index,
        "source_unix_time": source_unix,
        "source_time_utc": source_time.isoformat(),
        "retrieved_at_utc": retrieved_at.isoformat(),
        "age_minutes_at_retrieval": round(age_min, 2),
        "freshness_class": "LIVE" if -2 <= age_min <= 20 else "STALE_OR_CLOCK_SKEW",
        "scope": "Bangkok and vicinity aggregate context",
        "interpretation": "0=free flow context, 10=very congested overall context",
        "not_segment_speed": True,
    }


def main() -> int:
    args = parse_args()
    retrieved_at = dt.datetime.now(dt.timezone.utc)
    body, headers = fetch(args.url, args.timeout)
    parsed = unwrap_jsonp(body.decode("utf-8-sig"))
    result = {
        "provider": "Longdo Traffic / iTIC ecosystem",
        "requested_url": args.url,
        "retrieval_headers": headers,
        "data": normalize(parsed, retrieved_at),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["data"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
