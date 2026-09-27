# Phase 0 Test Area — Ram Inthra / Prasert-Manukitch / Pradit Manutham / Nuan Chan

## Study network

The Phase 0 pilot is a **small urban road network**, not a single corridor.

Core roads:

1. **Ram Inthra Road (ถนนรามอินทรา)**
2. **Prasert-Manukitch Road (ถนนประเสริฐมนูกิจ / เกษตร–นวมินทร์)**
3. **Pradit Manutham Road (ถนนประดิษฐ์มนูธรรม / เลียบทางด่วน)**
4. **Nuan Chan Road (ถนนนวลจันทร์)**

The exact GIS study polygon is intentionally not hand-drawn in this document. It will be generated from OpenStreetMap road geometry and expanded by a controlled context margin so the extraction is reproducible.

## Why this area is better than a single-road POC

This network allows the POC to test two levels of intelligence:

### A. Road / segment performance

For each core road or road segment:

- typical speed profile;
- directional differences where probe heading is available;
- peak-period timing;
- low-speed duration;
- data coverage / sample sufficiency;
- incidents matched to the road;
- before / during / after disruption comparison.

### B. Cross-road effects

For selected incidents or abnormal conditions:

- does speed deteriorate only on the affected road?
- do nearby roads become slower at the same time?
- is there evidence consistent with diversion / spillover?
- how long does the local network take to recover?

This is a more valuable POC question than analyzing one isolated corridor.

## Geographic evidence used for scoping

Bangkok Metropolitan Administration planning documents identify:

- Prasert-Manukitch Road within Bueng Kum between Pradit Manutham Road and Nawamin Road;
- Nuan Chan Road as an approximately 3 km road in the district road inventory, connecting into this same local network.

BMA also has a completed sidewalk-improvement project explicitly described as covering Nuan Chan Road from Prasert-Manukitch Road to Pradit Manutham Road, confirming that these roads form a directly related local study network.

Ram Inthra is included as a major adjacent arterial and as part of the Nuan Chan / Ram Inthra traffic context.

References:

- BMA Bueng Kum annual action plan: https://webportal.bangkok.go.th/public/user_files_editor/80/ITA/2567/O05/66.O08-%E0%B9%81%E0%B8%9C%E0%B8%99%E0%B8%9B%E0%B8%8F%E0%B8%B4%E0%B8%9A%E0%B8%B1%E0%B8%95%E0%B8%B4%E0%B8%A3%E0%B8%B2%E0%B8%8A%E0%B8%81%E0%B8%B2%E0%B8%A3%E0%B8%9B%E0%B8%A3%E0%B8%B0%E0%B8%88%E0%B8%B3%E0%B8%9B%E0%B8%B5%202566-%E0%B8%9A%E0%B8%B6%E0%B8%87%E0%B8%81%E0%B8%B8%E0%B9%88%E0%B8%A1.pdf
- BMA project tracking — Nuan Chan footpath improvement: https://policy.bangkok.go.th/tracking/frontend/web/index.php?ID=3207&r=site%2Fprojectview

## Phase 0 spatial strategy

### Stage 1 — broad extraction envelope

Create a polygon covering all four road corridors plus an outer context margin. This is used only to reduce the national iTIC probe/event archives to a manageable local dataset.

### Stage 2 — road matching

Do not assign data to a road simply because it falls inside the broad study-area polygon.

Probe observations should be matched using:

- nearest plausible road geometry;
- road direction / heading when the source schema includes heading;
- distance from carriageway;
- continuity across sequential observations where possible.

Events should be matched using:

- event coordinates;
- nearest road geometry;
- road / place names in title and description;
- event type;
- contextual confidence.

### Stage 3 — analysis segments

After QA, divide the four roads into stable analytical segments, preferably based on major intersections or approximately 250–500 m units where intersection structure does not provide a better boundary.

Every result must carry at least:

- road ID;
- segment ID;
- direction when defensible;
- time bin;
- observation count;
- data-quality flag.

## Event proximity bands

These are **screening distances only**, not final assignment rules:

- **0–150 m:** strong geometric candidate
- **150–300 m:** contextual candidate
- **300–800 m:** network-context event only
- **>800 m:** excluded by default unless a documented network disruption justifies inclusion

Dense Bangkok roads make large distance-only buffers unsafe for road attribution.

## Temporal strategy — latest first

Start from **now / recent conditions**, then move backward only as needed:

1. current/latest incident feed and current traffic-status feed;
2. recent 24 hours for operational context;
3. recent 7 days for repeatability and weekday context;
4. recent 30/90 days where data access permits;
5. older historical data only to construct normal baselines, seasonality and reproducible validation cases.

The first user-facing result should therefore answer **what is happening in this four-road network now/recently**, not begin with a 2022 replay.

## First Phase 0 outputs

1. OSM-derived study network and extraction envelope;
2. road-segment inventory;
3. **latest network status with source freshness**;
4. latest/recent incident map and timeline;
5. recent traffic-status coverage by road/segment;
6. 24 h / 7 d trend where source history is available;
7. current/recent condition vs normal baseline;
8. before / during / after comparison for selected recent incidents;
9. one cross-road impact case, if the data contain a defensible example;
10. data-quality and data-gap report;
11. go / revise / stop recommendation for P1.

## POC discipline

The four-road network is the **maximum Phase 0 geography**.

Do not expand to all of Bueng Kum / Lat Phrao / Khan Na Yao until:

- probe map matching works;
- incident matching works;
- sample sufficiency is known;
- at least one useful analytical finding has been reproduced.

## Geometry status

Exact OpenStreetMap-derived geometries are not committed yet. They will be generated in the spatial-extraction step with OSM provenance and attribution recorded.
