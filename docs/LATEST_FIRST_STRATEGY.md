# Latest-First Data Strategy

**Effective date:** 2026-09-27  
**Pilot area:** Ram Inthra — Prasert-Manukitch — Pradit Manutham — Nuan Chan

## Product principle

BKK Mobility Intelligence is a **current-mobility intelligence product first**.

The first questions are:

1. What is happening in the pilot network now?
2. What changed over the last hours / days?
3. Which road or segment is abnormal relative to its normal condition?
4. Is there a current/recent incident that plausibly explains the change?
5. Are nearby roads showing spillover or diversion effects?

Historical analysis remains important, but mainly as the comparison baseline.

## Source priority

### Tier 1 — LIVE / NEAR-REAL-TIME

Use first whenever accessible and terms permit:

- iTIC / Longdo latest Events JSON
- iTIC / Longdo Free-Longdo traffic status from mobile probes
- current traffic cameras where useful for validation
- current water/rain sources when integrated later

The official iTIC feed page describes:

- Free-Longdo as traffic status from mobile probes in Longdo and iTIC applications;
- Events JSON/RSS as the latest incidents/events collected at iTIC.

### Tier 2 — RECENT

Use to explain short-term trend:

- current-year 2026 incident records;
- recent status/probe records when archives are available;
- recent 24 h / 7 d / 30 d / 90 d windows;
- recent rainfall/flood/roadworks context.

The Longdo Traffic download page exposes 2026 historical event/index resources, so the system should prefer current-year material before older archives.

### Tier 3 — BASELINE

Use older historical archives for:

- typical speed by road × direction × day-of-week × time-of-day;
- variability / reliability bands;
- seasonal patterns;
- normal-vs-abnormal comparison;
- reproducible validation.

Do not make an old replay the default user experience.

## Freshness contract

Every ingested dataset must carry:

- `provider`
- `source_url`
- `retrieved_at_utc`
- `source_timestamp_start` when available
- `source_timestamp_end` when available
- `freshness_class`
- `freshness_note`

Allowed `freshness_class` values:

- `LIVE` — current feed intended to describe present conditions
- `RECENT` — current-year / recent-window information
- `BASELINE` — historical reference used for comparison
- `STALE` — expected-current source whose retrieved content is demonstrably outdated
- `UNKNOWN` — freshness cannot be established safely

## UI rule

The future UI must always show:

- data timestamp;
- retrieval timestamp;
- freshness badge;
- source/provider;
- clear warning when a source is stale or unknown.

A chart or map must never visually imply “now” solely because it came from a live URL.

## Currentness validation

For every live ingestion:

1. record retrieval time before parsing;
2. extract source timestamps where present;
3. calculate observed source age where meaningful;
4. log redirect/failure/schema anomalies;
5. preserve the raw response hash;
6. fall back to the newest recent archive only with a visible downgrade from LIVE to RECENT.

For event feeds, the newest event timestamp alone is **not sufficient proof that the feed is stale**, because there may simply be no newer event. Freshness should be assessed using endpoint behavior, response metadata where available, and continuity across repeated retrievals.

## Analysis windows

Default product windows:

- **Now:** latest available feed
- **Recent:** last 24 h
- **Short trend:** last 7 d
- **Context:** last 30 d
- **Seasonal context:** last 90 d
- **Baseline:** longer historical period selected by data quality

## Pilot success criteria

The latest-first pipeline passes Phase 0 if it can:

1. retrieve current/recent source data reliably;
2. assign freshness without misrepresenting old data as current;
3. match observations/events to the four-road network;
4. show at least road/segment-level current or recent condition;
5. compare the condition against a baseline;
6. preserve source attribution and uncertainty.

## Official references

- iTIC Traffic Data Feeds: https://traffic.longdo.com/feed/
- iTIC / Longdo latest Events JSON: https://event.longdo.com/feed/json
- Longdo Traffic downloads: https://traffic.longdo.com/download
- iTIC Open Data Archives: https://itic.longdo.com/data/
