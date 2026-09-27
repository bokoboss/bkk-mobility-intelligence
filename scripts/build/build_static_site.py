#!/usr/bin/env python3
"""Build the zero-dependency static Now dashboard from validated data outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--web-dir", type=Path, default=Path("web"))
    p.add_argument("--output-dir", type=Path, default=Path("dist"))
    p.add_argument(
        "--status",
        type=Path,
        default=Path("data/processed/now/latest_status.json"),
    )
    p.add_argument(
        "--network",
        type=Path,
        default=Path("data/processed/osm/core_roads.geojson"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    required = [
        args.web_dir / "index.html",
        args.web_dir / "styles.css",
        args.web_dir / "app.js",
        args.status,
        args.network,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing dashboard inputs: " + ", ".join(missing))

    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    data_dir = args.output_dir / "data"
    data_dir.mkdir(parents=True)

    for name in ("index.html", "styles.css", "app.js"):
        shutil.copy2(args.web_dir / name, args.output_dir / name)

    shutil.copy2(args.status, data_dir / "latest_status.json")
    shutil.copy2(args.network, data_dir / "core_roads.geojson")

    status = json.loads(args.status.read_text(encoding="utf-8"))
    build_info = {
        "schema": "bkk-mobility-static-build-v0.1",
        "generated_from_run": status.get("generated_from_run"),
        "study_area_id": status.get("study_area_id"),
        "files": [
            "index.html",
            "styles.css",
            "app.js",
            "data/latest_status.json",
            "data/core_roads.geojson",
        ],
    }
    (data_dir / "build_info.json").write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "generated_from_run": status.get("generated_from_run"),
                "readiness": status.get("readiness"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
