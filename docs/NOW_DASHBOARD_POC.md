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

The same Current Source Smoke workflow now supports **manual-only Pages
deployment**. Normal pushes still build/QA the preview but do not publish it.

One-time repository setup is required in GitHub:

1. `Settings → Pages`
2. Under `Build and deployment`, set `Source` to **GitHub Actions**.

After that, open the `Current Source Smoke` workflow, choose
`Run workflow`, and enable the `deploy_pages` checkbox.

The deploy path uses the official Pages Actions sequence:

- `actions/configure-pages@v5`
- `actions/upload-pages-artifact@v4`
- `actions/deploy-pages@v4`

No schedule is enabled yet. Refresh cadence should be chosen only after the
published POC is reviewed, because live source polling and Pages deployment are
separate concerns.
