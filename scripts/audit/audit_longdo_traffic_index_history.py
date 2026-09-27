#!/usr/bin/env python3
"""Audit the published 2026 Longdo Traffic Index CSV without assuming schema."""

from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request

DEFAULT_URL = "https://traffic.longdo.com/api/raw/trafficindex/2026"
USER_AGENT = "bkk-mobility-intelligence-phase0/0.5"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--timeout", type=float, default=30.0)
    args = p.parse_args()

    req = urllib.request.Request(args.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=args.timeout) as resp:
        body = resp.read()
        content_type = resp.headers.get("Content-Type")
        final_url = resp.geturl()

    text = body.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    widths: dict[str, int] = {}
    for row in rows[:10000]:
        widths[str(len(row))] = widths.get(str(len(row)), 0) + 1

    report = {
        "final_url": final_url,
        "content_type": content_type,
        "byte_count": len(body),
        "row_count": len(rows),
        "first_rows": rows[:5],
        "column_width_distribution_first_10000": widths,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
