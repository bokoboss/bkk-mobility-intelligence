#!/usr/bin/env python3
"""Print a compact latest-source summary from a current bundle manifest."""

from __future__ import annotations
import argparse
import json
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("manifest", type=Path)
    args = p.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    out = {
        "study_area_id": data.get("study_area_id"),
        "run_id": data.get("run_id"),
        "pipeline_status": data.get("pipeline_status"),
        "sources": {},
    }
    for key, src in data.get("sources", {}).items():
        audit = src.get("audit") or {}
        out["sources"][key] = {
            "freshness_class": src.get("freshness_class"),
            "retrieved_at_utc": src.get("retrieved_at_utc"),
            "final_url": src.get("final_url"),
            "http_status": src.get("http_status"),
            "byte_count": src.get("byte_count"),
            "study_area_count": audit.get(
                "study_area_event_count", audit.get("study_area_record_count")
            ),
            "latest_event_start": audit.get("latest_event_start"),
            "parse_error": audit.get("parse_error"),
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
