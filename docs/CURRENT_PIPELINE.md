# Current Data Pipeline — Bangkok-wide Phase 0

## Purpose

Create an auditable **latest-source bundle** and analytical snapshot for all 50
Bangkok districts. The original Ram Inthra / Prasert-Manukitch /
Pradit Manutham / Nuan Chan roads remain focus roads, but they no longer define
the spatial extent of the pipeline.

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
