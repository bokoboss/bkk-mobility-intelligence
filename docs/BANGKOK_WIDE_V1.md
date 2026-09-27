# Bangkok-wide v1

## Scope

The POC now operates across the 50 Bangkok districts.

### Administrative geometry

The working district geometry is a pinned public staging GeoJSON containing
exactly 50 district codes with Bangkok province code 10. Automated access to the
BMA official KML/CKAN resource was unstable from GitHub Actions on 2026-09-27,
so the dashboard labels this as staging geometry and keeps the BMA resource as
the intended replacement source.

### Road network

- OpenStreetMap named roads;
- motorway / trunk / primary / secondary / tertiary;
- 4 × 4 Overpass tiles with per-tile cache;
- OSM way deduplication across tiles;
- polygon clip to Bangkok districts;
- strategic tier: motorway/trunk/primary/secondary;
- urban tier: sufficiently long named tertiary roads;
- no arbitrary global road-count cap.

### Event flow

Current and 30-day events are first bbox-filtered, then polygon-clipped and
assigned to one of the 50 districts before road matching.

### Dashboard hierarchy

Bangkok → District → Road → Hotspot.

The MapLibre dashboard includes:
- 50 district boundaries;
- district selector;
- district-filtered incidents / roads / flood hotspots / TMD grid;
- 30-day top districts;
- district flood recurrence;
- district relative Flood Watch.

Relative watch scores are within-Bangkok prioritization only and are not flood
probabilities.
