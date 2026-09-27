# Current Data Pipeline — Phase 0

## Purpose

Create a small, auditable **latest-source bundle** for the Ram Inthra / Prasert-Manukitch / Pradit Manutham / Nuan Chan pilot network before building the UI.

The pipeline currently targets two official iTIC/Longdo sources:

1. Latest traffic incidents: `https://event.longdo.com/feed/json`
2. Free traffic status: `https://traffic.longdo.com/api/feed/free`

The official iTIC feed page describes the latter as **Free-Longdo — mobile probes from Longdo and iTIC applications, offset in meters**. The official link currently redirects to `http://live.iticfoundation.org/feed/free`; the ingestion manifest records both requested and final URL so redirects are visible rather than hidden.

## Run

```bash
python scripts/live/fetch_current_bundle.py
python scripts/live/summarize_latest.py data/raw/current/<RUN_ID>/manifest.json
```

No third-party Python packages are required for the first live-source audit.

## Outputs

Each run creates a local directory such as:

```text
data/raw/current/20260927T061500Z/
  manifest.json
  events.raw.json
  events.study_area.json
  traffic_free.raw.xml
  traffic_free.study_area.json
```

`data/raw/` is ignored by Git and must not be committed.

## Freshness

Every source manifest records:

- requested URL;
- final URL after redirect;
- HTTP status;
- response content type;
- retrieval timestamp (UTC);
- Date / Last-Modified headers when supplied;
- payload size;
- SHA-256;
- freshness class;
- schema/audit results.

Important: **a successful request is not sufficient proof that the underlying observations are current**. The pipeline separates transport success from source-data recency.

For the event feed, the newest event start time is recorded as a diagnostic, but an old newest event is not sufficient by itself to classify the feed as stale because there may simply have been no newer report.

## Study-area filtering

### Incidents

The event JSON includes coordinates. Phase 0 therefore filters incidents by the configured WGS84 extraction envelope and adds road-name text matches when possible.

The bbox is only a **first extraction step**. It is not final road attribution.

### Free traffic status

The current public feed link is documented, but the exact live payload schema must be verified from a successful real fetch. The parser therefore:

- detects JSON / XML / unknown payload;
- inventories status/speed/link/road/direction-like fields;
- extracts coordinates if the payload exposes them;
- detects configured road aliases if they are present;
- refuses to interpret zero extracted records as zero traffic in the study area.

If the free feed is link-ID based without self-contained geometry, the next step is to build/obtain the corresponding link geometry before segment-level filtering.

## Current limitation

The execution environment used while creating this pipeline could inspect the official web documentation but could not make arbitrary outbound HTTP requests from the code runtime. Therefore the parser is unit-tested against representative JSON/XML payloads, while **real live payload qualification remains the first runtime gate** when this script is run in an internet-enabled environment.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Next gate

A real run passes the current-source gate when:

1. latest events are retrieved and parsed;
2. Free-Longdo feed is retrieved and its real schema is captured;
3. freshness metadata are present;
4. study-area incidents can be extracted;
5. traffic data can either be filtered to the pilot network or the exact missing link-geometry dependency is identified.

Only after this gate should the project add 24 h / 7 d storage and the first “Now” dashboard.
