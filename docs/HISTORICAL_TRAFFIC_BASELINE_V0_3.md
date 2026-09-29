# Historical Traffic Baseline v0.3

## Objective

Build a defensible road/time historical baseline for the Bangkok-wide network
without maintaining a mobility database or a permanent copy of provider raw
archives.

## Source

Primary historical source:

- iTIC / Longdo Historical Raw Vehicle & Mobile Probe Data
- archive index: https://traffic.longdo.com/data/probe-data/
- published format: https://traffic.longdo.com/docs/probedata-format
- archive license listed by iTIC Open Data Archives: CC-BY 4.0

The published CSV format is:

`VehicleID,gpsvalid,lat,lon,timestamp,speed,passenger_lamp,engine_acc`

Timestamp is GMT+7 and speed is km/h.

The 2025 archive index exposes monthly files
`PROBE-202501.tar.bz2` through `PROBE-202512.tar.bz2`.

## Direction limitation

The published archive format has no heading/direction field. Baseline v0.3 is
therefore direction-neutral. Direction must not be inferred silently.

A future direction-aware baseline may reconstruct heading from consecutive
vehicle observations only after track ordering and QA rules are validated.

## Cloud-batch design

Local preprocessing is no longer required for the normal project workflow.

Use **GitHub Actions → Historical Baseline Batch → Run workflow**.

Inputs:

- year;
- month;
- `trial-first-day` or `full-month`.

### Trial first

The default mode processes only the first daily member in the archive. This is
the safe gate for measuring:

- Bangkok probe count;
- matched / ambiguous / unmatched rates;
- processing time;
- compact output size.

### Full month

After trial QA is acceptable, rerun that month in `full-month` mode.

The job:

1. downloads the provider archive directly to the GitHub runner;
2. validates the published MD5 when available;
3. streams the archive;
4. filters to Bangkok district polygons;
5. map-matches to the OSM road network;
6. rejects ambiguous/intersection matches;
7. aggregates each vehicle to one median speed per road/time bin;
8. publishes only compact daily profiles;
9. deletes the raw archive.

The persistent monthly asset is:

`probe-profile-YYYYMM.tar.gz`

under GitHub Release:

`historical-baseline-v0.3`

Trial assets use a `-trial` suffix and are intentionally excluded from
baseline assembly.

## Baseline assembly

After full-month assets are available, use:

**GitHub Actions → Historical Baseline Assemble → Run workflow**

The workflow downloads only full-month compact profiles and builds:

`road_time_baseline_v0_3.json`

The final baseline is uploaded to the same GitHub Release. It can then trigger a
normal dashboard refresh.

## Map matching QA

Default project-side rules:

- nearest OSM road segment within 45 m;
- reject when another road is within 10 m of the best-match distance;
- reject invalid GPS rows;
- reject speeds outside 0–160 km/h.

These are project QA thresholds, not provider standards.

## Aggregation

### Daily profile

Within each road × 30-minute bin:

1. median speed is calculated per vehicle;
2. the daily distribution uses those vehicle medians.

This reduces bias from vehicles that report more frequently.

### Historical baseline

For each road × weekday × 30-minute bin:

- equal weight per daily median;
- median, P10, P25, P75, P90;
- day count, vehicle count and probe count retained.

Default baseline-ready threshold:

- at least 8 comparable weekdays;
- at least 40 vehicles total;
- road coverage marked ready after at least 24 ready time bins.

## Persistence and database policy

Raw archives are **not** persisted by this project after a batch job.

Persistent project data are limited to compact derived Release assets. No
PostgreSQL/PostGIS database is required for v0.3.

This storage layer is replaceable. If GitHub Release assets later become
inconvenient, the same monthly and baseline contracts can move to S3/R2 without
changing the frontend.

## Dashboard consumption

Normal Current Source Smoke runs
`scripts/history/fetch_baseline_release.py`.

- if the Release baseline does not exist: build continues and reports
  `CLOUD_BATCH_REQUIRED`;
- if it exists and has the expected schema: it is consumed automatically;
- a transport failure never becomes a fake zero/normal traffic state.

## Current-vs-normal

v0.3 still does not label current traffic abnormal.

v0.4 will compare a current road speed observation with the matching
weekday/time-bin baseline only when the baseline quality threshold is satisfied.
