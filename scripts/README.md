# Scripts

Phase 0 scripts will be organized by purpose:

- `ingest/` — retrieve or load source data
- `clean/` — schema normalization, timestamp cleanup, deduplication
- `spatial/` — CRS handling, corridor buffers, road/event matching
- `analytics/` — baseline profiles, disruption comparison, reliability indicators

No production pipeline is committed yet. The first implementation should follow the findings of the Data Feasibility Audit.
