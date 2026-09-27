# Interactive Online Map

## Decision

The dashboard map uses **MapLibre GL JS + OpenFreeMap** as the interactive
basemap. The analytical road network and confirmed iTIC/Longdo incidents remain
our own GeoJSON overlays.

## Why this architecture

- pan / wheel zoom / pinch zoom are native map interactions;
- the expanded network is easier to interpret against real streets, place
  labels, waterways and urban context;
- future flood, roadworks, cameras, speed and historical incident layers can be
  added without changing the data engine;
- no Longdo/Google basemap key is required for the default map.

## Basemap

Default style:

`https://tiles.openfreemap.org/styles/liberty`

OpenFreeMap public tiles use OpenStreetMap data. MapLibre renders provider /
OpenStreetMap attribution in the map UI.

## POC overlays

### Road network

`data/core_roads.geojson`

- four original priority roads retain distinct colors;
- other analytical roads are muted;
- clicking a road synchronizes the map, incident filter and road cards.

### Confirmed incidents

Built in the browser from `data/latest_status.json`.

- red circles;
- click for road / title / latest timestamp popup;
- selected-road filtering dims incidents on other roads.

## Controls

- mouse/touch pan;
- wheel/pinch zoom;
- MapLibre navigation control;
- fullscreen control;
- metric scale bar;
- `Fit Study Area` control.

## Failure behavior

If the external MapLibre/OpenFreeMap assets are unavailable, the dashboard data
cards and incident list still load. Only the map panel reports basemap
unavailability.

## Current limitation

Segment speed remains unavailable until a qualified speed provider is connected.
The map therefore shows road identity and incident overlays, not inferred
congestion colors.
