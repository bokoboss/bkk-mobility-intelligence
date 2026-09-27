# Now Dashboard POC

## Scope

The first UI is intentionally limited to data already validated in Phase 0.

It shows:

- four-road pilot geometry;
- confirmed/deduplicated incidents;
- live Longdo Traffic Index;
- comparison with the 2026 same-weekday/time baseline;
- source freshness;
- explicit segment-speed unavailability.

It does **not** infer road congestion from incident counts or the citywide Traffic Index.

## Build

The Current Source Smoke workflow generates validated data and then runs:

```bash
python scripts/build/build_static_site.py
```

Output:

```text
dist/
  index.html
  styles.css
  app.js
  data/
    latest_status.json
    core_roads.geojson
    build_info.json
```

The workflow uploads `dist/` as the `now-dashboard-preview` artifact.

## Design choices

- zero frontend framework dependencies;
- SVG road-network visualization using the validated OSM geometry;
- road filtering by clicking the map, road cards, or filter chips;
- incident feed with deduplicated confirmed clusters;
- light/dark theme toggle;
- responsive mobile layout;
- visible uncertainty / blocked-source states.

## Deployment

No scheduled Pages deployment is enabled yet.

This is deliberate: first validate the dashboard artifact and data semantics,
then enable GitHub Pages and choose an appropriate refresh cadence without
creating unnecessary Actions usage or repository commits.
