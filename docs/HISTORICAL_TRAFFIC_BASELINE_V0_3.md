# Historical Traffic Baseline v0.3

## Objective

Build a defensible road/time historical baseline for the Bangkok-wide network so
a later phase can compare current sampled speed with the normal distribution for
the same road and time period.

## Source

Primary historical source:

- iTIC / Longdo Historical Raw Vehicle & Mobile Probe Data
- archive index: https://traffic.longdo.com/data/probe-data/
- published format: https://traffic.longdo.com/docs/probedata-format
- license is listed by iTIC Open Data Archives as CC-BY 4.0

The published CSV format contains:

`VehicleID,gpsvalid,lat,lon,timestamp,speed,passenger_lamp,engine_acc`

Timestamp is GMT+7 and speed is km/h.

### Direction limitation

The published archive format does **not** contain heading/direction. Historical
Baseline v0.3 is therefore direction-neutral. Direction must not be inferred
silently.

A future direction-aware baseline may reconstruct heading from consecutive
vehicle points, but only after track-ordering and quality rules are validated.

## Why this is offline-first

Monthly 2025 archives are roughly 1.0–1.5 GB each. They are intentionally not
downloaded in normal GitHub Actions.

The workflow is:

1. keep the original `.tar.bz2` archive local;
2. stream it without extracting the whole month;
3. filter probes to Bangkok district polygons;
4. map-match to the Bangkok OSM road network;
5. reject ambiguous/intersection matches;
6. aggregate each vehicle to one median speed per road/time bin;
7. write small daily `.json.gz` profiles;
8. combine daily profiles into one compact road/time baseline artifact.

Large raw and processed files are already excluded by `.gitignore`.

## Commands

Process one month locally:

```bash
python scripts/history/process_probe_archive.py \
  --archive D:/data/PROBE-202501.tar.bz2
```

Trial only the first archive member:

```bash
python scripts/history/process_probe_archive.py \
  --archive D:/data/PROBE-202501.tar.bz2 \
  --limit-members 1
```

Build the compact 2025 baseline:

```bash
python scripts/history/build_historical_road_baseline.py \
  --daily-dir data/processed/historical_probe/daily \
  --reference-year 2025
```

Default output:

`data/processed/history/road_time_baseline_v0_3.json`

## Map matching

Default project-side QA rules:

- nearest OSM road segment must be within 45 m;
- if another road is within 10 m of the best-match distance, reject as
  ambiguous;
- invalid GPS rows and speeds outside 0–160 km/h are rejected.

These are project QA thresholds, not iTIC standards.

## Aggregation

### Daily profile

Within each road × 30-minute bin:

1. take the median speed for each vehicle;
2. build the daily distribution from those per-vehicle medians.

This reduces repeated-message bias from vehicles reporting more frequently.

### Historical baseline

For each road × weekday × 30-minute bin:

- equal-weight each daily median;
- calculate median, P10, P25, P75, P90;
- retain day count, vehicle count and probe count.

Default baseline-ready threshold:

- at least 8 comparable weekdays;
- at least 40 vehicles total;
- a road is considered baseline-ready for coverage reporting after at least
  24 ready time bins.

These thresholds are explicit project rules and can be revised after the first
real data audit.

## Output schema

`bkk-mobility-road-time-baseline-v0.3`

The artifact includes:

- methodology and quality thresholds;
- source date coverage;
- network and district coverage;
- road readiness;
- baseline distributions for each ready/limited/insufficient time bin.

## Current-vs-normal

v0.3 does **not** label current traffic abnormal.

That is v0.4. The next stage will join a current road speed sample to the
matching weekday/time-bin baseline and classify deviation only when that
baseline bin passes its readiness threshold.
