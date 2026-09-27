# Data Sources

This file is the source-of-truth for provenance, access method, coverage, licensing, and intended analytical use of each dataset.

## 1. iTIC / Longdo Traffic Incidents

### Live feed

- Endpoint: https://event.longdo.com/feed/json
- Data type: traffic incidents / events
- Typical contents: event ID, event type, title/description, latitude/longitude, timestamps, severity/source metadata where available
- Intended POC use:
  - incident mapping
  - event classification
  - corridor proximity analysis
  - disruption timeline
  - incident vs traffic-performance comparison

### Attribution

Primary source attribution:

**Intelligent Traffic Information Center Foundation (iTIC Foundation)**

Official references:

- https://iticfoundation.org/en/open-data-sharing/
- https://itic.longdo.com/data/
- https://traffic.longdo.com/feed/
- https://event.longdo.com/feed/json

The iTIC / Longdo Traffic Data Feeds page identifies the Events RSS/JSON feed as the latest incidents/events collected at iTIC via events.longdo.com.

### Licensing

The iTIC Open Data Archive explicitly identifies the following historical datasets under **CC-BY 4.0**:

- Historical Traffic Incidents
- Historical Traffic Information Status
- Historical Raw Vehicle & Mobile Probe Data

The live endpoint is tracked separately. Do not assume that every live feed automatically inherits the archive license.

---

## 2. Candidate supporting datasets

The following are candidates for Phase 0 validation. Availability, exact endpoints, licensing, and schema must be verified before implementation.

| Dataset | Candidate use | Phase 0 checks |
|---|---|---|
| iTIC historical traffic incidents | disruption history | coverage, schema, duplicates, license |
| iTIC traffic status | speed / congestion profile | temporal resolution, network matching |
| iTIC raw probe data | speed / travel time derivation | size, sampling rate, privacy/terms |
| Road network / OSM | corridor geometry | segment IDs, direction, topology |
| DOH / DRR traffic volume / AADT | exposure / demand context | station coverage, date, road matching |
| BMA flood / water-level data | disruption context | station locations, timestamps |
| TMD rain data | weather correlation | rainfall resolution and access |
| Accident datasets | safety context | spatial precision, severity, coverage |
| BMA roadworks / closures | planned disruption | timing, geometry, completeness |

## Data-source rules

1. Preserve provenance for every derived dataset.
2. Record original URL / provider / retrieval date.
3. Do not commit large raw datasets to GitHub.
4. Keep only small reproducible samples in `data/sample/`.
5. Document transformations from raw -> cleaned -> analytical outputs.
6. Keep live-feed terms separate from historical archive terms.
7. Do not present open-data records as complete ground truth; report known coverage limitations.

## Phase 0 source matrix fields

Each dataset should eventually be scored on:

- Provider
- URL / endpoint
- Data type
- Spatial coverage
- Temporal coverage
- Temporal resolution
- Spatial resolution
- Coordinate reference system
- Update frequency
- Historical depth
- File/API format
- Estimated size
- Missing data risk
- Duplicate risk
- Road matching difficulty
- Directionality
- License
- Required attribution
- POC usefulness
- Production suitability
