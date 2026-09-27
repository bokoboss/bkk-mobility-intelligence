# Recent Incident Intelligence — 7D / 30D

## Source

The primary recent-history source is the same public JSON endpoint used by
Longdo Traffic's **Search for Events** interface:

`https://traffic.longdo.com/event.json`

The site JavaScript submits `page`, Unix `from` / `to`, `ordered`,
`eventtype`, and `pagger` parameters. The POC requests up to 1,000 records
per page, paginates until the date-range result is exhausted, and persists only
records inside Expanded V1.

The annual `https://event.longdo.com/feed/2026` CSV remains useful as an
archive/fallback, but is not used for live 7D/30D metrics because its event
coverage was observed to lag the live search database.

## Time semantics

- anchor: the retrieval time of the live current-event feed;
- 7D: event episodes whose first start is in the latest 7-day window;
- prior 7D: immediately preceding 7-day window;
- 30D: event episodes whose first start is in the latest 30-day window.

These are reported-event episodes, not exposure-normalized rates.

## Episode deduplication

Historical rows often contain update records such as
`คืบหน้าอุบัติเหตุ...`. The history engine:

1. canonicalizes common update prefixes;
2. requires the same confirmed road, event type and canonical title/location
   or route segment;
3. groups overlapping or near-continuous records into one episode;
4. starts a new episode when the prior episode has ended and the next record is
   separated by more than six hours.

## Dashboard

The map now supports:

- Now;
- 7 Days;
- 30 Days.

Historical modes use the same confirmed-road matching rules as Now and are
visually separated from current incidents. The history panel shows:

- 7-day incident episodes;
- comparison with the prior 7 days;
- 30-day incident episodes;
- top roads;
- top event types.

## Interpretation caution

A rise in reported incidents does not by itself mean the road became less safe
or more congested. Reporting intensity, event mix and exposure are not yet
normalized.


## Freshness gate

The ingestion manifest compares the newest `createtime` returned by
`/event.json` with the live-feed retrieval anchor. 7D/30D analytics are built
only when the recent-search source is within three hours of the anchor.
Otherwise the pipeline fails closed instead of rendering misleading zero counts.


## Live validation — 2026-09-27

Validated against the live Longdo event search database at approximately
15:25 ICT:

- source coverage lag: **1.13 minutes**;
- pages fetched: **7** at up to 1,000 records/page;
- unique events returned for the 30-day query: **6,825**;
- Expanded V1 rows before road confirmation: **943**;
- confirmed episode clusters in latest 7 days: **209**;
- confirmed episode clusters in prior 7 days: **74**;
- confirmed episode clusters in latest 30 days: **401**;
- roads represented in latest 7 days: **36**;
- roads represented in latest 30 days: **43**.

Thirty-day leading event types in this validation run were flood (150),
accident (108), rain (59), breakdown (34), and traffic jam (30).

The latest 7-day count is substantially above the prior 7-day count and is
dominated by flood reports. This is presented descriptively; it is not a claim
that traffic performance or safety risk increased by the same percentage.
