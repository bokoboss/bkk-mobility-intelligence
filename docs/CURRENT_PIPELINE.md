# Current Data Pipeline — Bangkok-wide Phase 0

## Purpose

Create an auditable **latest-source bundle** and analytical snapshot for all 50
Bangkok districts. The original Ram Inthra / Prasert-Manukitch /
Pradit Manutham / Nuan Chan roads retain stable IDs for continuity only; they
no longer define the spatial extent or receive special Bangkok-wide priority.

## Current source stack

1. Latest traffic incidents — `https://event.longdo.com/feed/json`
2. Free-Longdo traffic status contract — documented by iTIC/Longdo, currently
   redirecting to `https://live.iticfoundation.org/feed/free`
3. Longdo Traffic Index — Bangkok-and-vicinity aggregate congestion context
4. Optional Longdo Map `traffic/speed` adapter — credential-gated road-speed
   evidence
5. OpenStreetMap — Bangkok road geometry
6. TMD / HII context — rain and flood intelligence

## Runtime status verified on 2026-09-27

The successful Bangkok-wide GitHub Actions run confirmed:

- iTIC/Longdo event feed: HTTP 200 and live;
- Free-Longdo traffic status: redirect succeeds but the final endpoint returns
  **HTTP 401**, so it is not treated as available traffic data;
- Longdo Traffic Index: live and usable as city-level context;
- segment/road speed: blocked until an authorized provider credential is
  available.

A transport failure or authorization failure is never interpreted as zero
traffic or free flow.

## Current traffic-state contract

The pipeline always creates:

`data/processed/current_speed/traffic_state.json`

The contract records:

- provider/access state;
- number of roads in the network;
- number and ratio of roads with usable speed samples;
- normalized speed observations in km/h;
- per-road median / p10 / p90 sampled speed;
- source and direction counts;
- explicit baseline and abnormality readiness.

If `LONGDO_MAP_API_KEY` is absent, the Longdo adapter still writes a small
artifact with `BLOCKED_MISSING_API_KEY`, allowing the dashboard pipeline to
complete without pretending that speed data exist.

The absolute movement bands in this contract are descriptive only. They are
**not LOS**, and they are **not evidence that a road is abnormal**. Abnormality
requires a road- and time-specific historical baseline.

## Run

```bash
python scripts/live/fetch_current_bundle.py
python scripts/live/fetch_longdo_traffic_index.py
python scripts/live/fetch_longdo_traffic_speed.py \
  --network data/processed/osm/core_roads.geojson \
  --output data/processed/current_speed/longdo_speed.json
python scripts/analysis/build_traffic_state.py
python scripts/build/build_now_snapshot.py
```

## Freshness and provenance

Every live-source artifact preserves retrieval time and source metadata where
available. Source transport success, observation recency, spatial coverage, and
authorization state are reported separately.

## Spatial processing

Events are first filtered by the Bangkok extraction envelope, then clipped to
the 50 district polygons, assigned to a district, matched to the Bangkok OSM
road network, and clustered into confirmed incident records.

The road network covers named motorway, trunk, primary, secondary and selected
tertiary roads. The four original focus roads keep stable IDs.

## Current analytical readiness

Ready now:

- current incidents;
- 7/30-day incident context;
- city-level Traffic Index context;
- Bangkok-wide district and road navigation;
- rain/flood context;
- explicit traffic-speed access/coverage reporting.

Still gated:

- broad Bangkok current road-speed coverage;
- current-vs-normal road abnormality;
- robust direction-specific travel-time reliability.

## Tests

```bash
python -m unittest discover -s tests -v
node --check web/app.js
```

The GitHub Actions workflow runs these gates before publishing the validated
static dashboard.


## Traffic Coverage v0.2

The Bangkok-wide pipeline now builds a deterministic rotating sampling plan
before the provider adapter runs.

Artifacts:

- `traffic_sampling_plan.json`: planned road-district probe points under the
  internal request budget;
- `traffic_coverage.json`: planned vs observed coverage by network tier and
  district.

Default internal request budget is 30 probe points/run with a 70% Strategic
target share and daily UTC rotation. This cap is an internal safety control, not
a claimed Longdo/iTIC provider quota.

Observed Coverage counts only usable speed observations. Planned probes are
never presented as measured traffic.


## Historical Traffic Baseline v0.3

Historical processing now follows the DB-free federated architecture.

Normal CI does **not** download monthly raw probe archives. Historical data are
processed only through the manual workflow:

`.github/workflows/historical-baseline-batch.yml`

The workflow accepts year, month, and mode:

- `trial-first-day` — process only the first daily archive member for QA;
- `full-month` — process the complete monthly archive.

For each batch run:

1. the runner restores or rebuilds the validated Bangkok OSM network;
2. downloads `PROBE-YYYYMM.tar.bz2` directly from the provider;
3. verifies the provider MD5 when the checksum is available;
4. streams the archive without committing or permanently storing raw rows;
5. filters to Bangkok, map-matches, rejects ambiguous matches and aggregates;
6. packages only compact daily profiles;
7. uploads `probe-profile-YYYYMM.tar.gz` to GitHub Release
   `historical-baseline-v0.3`;
8. deletes the raw archive at job end.

After one or more full-month assets exist, run:

`.github/workflows/historical-baseline-assemble.yml`

It downloads only compact monthly profile assets, builds
`road_time_baseline_v0_3.json`, publishes that compact baseline to the same
Release, and can dispatch Current Source Smoke to refresh GitHub Pages.

Current Source Smoke calls `scripts/history/fetch_baseline_release.py`.
Before the compact Release asset exists this is fail-soft and the dashboard
shows `CLOUD_BATCH_REQUIRED`. Once the baseline asset exists, the same
frontend-neutral snapshot contract consumes it automatically.

The 2025 archive index currently exposes all 12 monthly probe archives. The
published raw format has no heading field, so v0.3 remains explicitly
direction-neutral.

## Persistence policy

No application database is required at this stage.

- live public data: fetched from source and normalized;
- raw historical archive: temporary cloud-batch input only;
- monthly historical profile: compact GitHub Release asset;
- road/time baseline: compact GitHub Release asset;
- current dashboard snapshot: GitHub Pages build artifact.

See `docs/FEDERATED_ARCHITECTURE.md` and
`config/federated_sources.json`.
