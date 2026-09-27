# Expanded Study Area v1

## Why expand now

The initial four-road pilot proved the live incident pipeline, road geometry
matching, freshness handling and dashboard flow. The next useful step is to
expand geography before adding 7/30-day trend analytics, so the product can
observe network effects beyond the original four roads.

## Analytical envelope

Expanded Northeast Bangkok pilot:

- west/east: approximately longitude 100.53–100.79
- south/north: approximately latitude 13.735–13.93

This is an **analytical extraction envelope**, not an administrative boundary.

It covers the original Ram Inthra / Prasert-Manukitch / Pradit Manutham /
Nuan Chan area and extends toward the surrounding Lat Phrao–Nawamin–Seri Thai–
Ramkhamhaeng–Min Buri–Bang Khen/Lak Si network context.

## Network discovery

The OSM engine now selects:

- named `trunk`
- named `primary`
- named `secondary`
- named `tertiary`

within the expanded envelope.

To avoid turning the dashboard into a local-street map:

- the four original roads are always retained as **priority roads**;
- other road-name groups must exceed a configured total in-area length;
- only the longest non-priority road groups are retained.

## Stable vs dynamic road IDs

Priority roads retain stable IDs:

- `ram_inthra`
- `prasert_manukitch`
- `pradit_manutham`
- `nuan_chan`

Other roads receive deterministic OSM-name hash IDs. The display name and OSM
aliases remain in the data contract.

## Incident confirmation

An expanded-network incident is confirmed only when:

1. the event point is spatially close to a discovered road; and
2. the event title matches a road alias **or** its route number matches the
   OSM/config route reference.

Geometry-only proximity remains a candidate, not a confirmed incident.

## Dashboard behavior

- all retained major-road geometry is drawn;
- the four original roads remain visually emphasized;
- roads with confirmed current incidents are elevated into filters/cards;
- the UI does not create dozens of permanent road cards for quiet roads;
- segment speed remains explicitly unavailable until a qualified provider is
  connected.

## Expansion gate

The expanded area is accepted only if the live smoke run shows:

- all four priority roads present;
- a manageable dynamic road count;
- no obvious local-street explosion;
- incident confirmation remains selective rather than turning every nearby
  event into a road-level incident.
