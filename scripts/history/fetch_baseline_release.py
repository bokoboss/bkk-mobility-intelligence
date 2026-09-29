#!/usr/bin/env python3
"""Fetch the compact historical baseline Release asset, if published.

This adapter is fail-soft by default so the current dashboard remains buildable
before the historical cloud batch has produced a baseline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request

DEFAULT_URL = (
    "https://github.com/bokoboss/bkk-mobility-intelligence/releases/download/"
    "historical-baseline-v0.3/road_time_baseline_v0_3.json"
)
USER_AGENT = "bkk-mobility-intelligence-federated/0.1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/history/road_time_baseline_v0_3.json"),
    )
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--strict", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    req = urllib.request.Request(args.url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            payload = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        print(json.dumps({
            "status": "COMPACT_BASELINE_NOT_AVAILABLE",
            "url": args.url,
            "error": f"{type(exc).__name__}: {exc}",
        }, ensure_ascii=False, indent=2))
        return 1 if args.strict else 0

    try:
        doc = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "INVALID_COMPACT_BASELINE",
            "url": args.url,
            "error": f"{type(exc).__name__}: {exc}",
        }, ensure_ascii=False, indent=2))
        return 1 if args.strict else 0

    if doc.get("schema") != "bkk-mobility-road-time-baseline-v0.3":
        print(json.dumps({
            "status": "UNEXPECTED_BASELINE_SCHEMA",
            "schema": doc.get("schema"),
            "url": args.url,
        }, ensure_ascii=False, indent=2))
        return 1 if args.strict else 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "COMPACT_BASELINE_READY",
        "url": args.url,
        "output": str(args.output),
        "reference_year": doc.get("reference_year"),
        "ready_road_count": (doc.get("summary") or {}).get("ready_road_count", 0),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
