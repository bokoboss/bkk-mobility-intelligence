# Bangkok 50-District Staging Geometry

Bangkok-wide v1 needs a stable local district polygon source because the BMA
Open Data host reset automated connections from the GitHub Actions runner during
validation on 2026-09-27, while large Overpass administrative queries returned
504 from two mirrors.

## Ground truth

Bangkok Metropolitan Administration publicly identifies Bangkok as 50
administrative districts and publishes the dataset:

- Dataset: `พื้นที่เขตปกครอง 50 เขตของกรุงเทพมหานคร`
- Official KML resource:
  `https://data.bangkok.go.th/dataset/e537025b-1cf6-4c5b-8e46-c2e976f13283/resource/0f40f9b4-617b-46a9-8806-f590da610954/download/district.kml`

The direct BMA geometry remains the intended authoritative replacement once
automated access is stable.

## Staging geometry

To avoid blocking the POC, v1 vendors the public GitHub file:

- repository: `pcrete/gsvloader-demo`
- path: `geojson/Bangkok-districts.geojson`
- blob SHA: `a268fe2f4e400f5b1e630aa2182cada10ea531ec`
- repository license: MIT

Validation before vendoring:

- FeatureCollection features: **50**
- bbox: `100.3261885862, 13.4942754210, 100.9396540371, 13.9519855760`
- properties include district code (`dcode`), Thai name (`dname`), and English
  name (`dname_e`).

This file is a staging geometry dependency, not a claim that the GitHub copy is
more authoritative than BMA.
