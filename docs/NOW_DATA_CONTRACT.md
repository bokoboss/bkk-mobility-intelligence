# Now Data Contract

The first frontend-neutral `Now` contract is generated at:

`data/processed/now/latest_status.json`

It intentionally distinguishes what is known from what is unavailable.

## Ready

- live incident feed and freshness;
- exact four-road OSM network;
- confirmed incident clustering by road;
- live Bangkok/vicinity Traffic Index;
- same-weekday/time 2026 Traffic Index baseline;
- camera coverage diagnostics.

## Not yet ready

- quantitative current speed by road segment;
- current-vs-normal segment speed;
- measured spillover/diversion effects.

The contract uses `UNAVAILABLE` / `BLOCKED_ON_PROVIDER_ACCESS` rather than
inventing a congestion status when segment speed is absent.

## Road-level semantic rule

A road with no confirmed current incident is reported as:

`No confirmed incident in current feed`

not:

`Road clear`

because the event feed is not assumed to be a complete incident census.

## City context

Longdo Traffic Index is a 0-10 Bangkok/vicinity aggregate metric and is kept
separate from road-level state. The baseline compares the live value with all
prior 2026 observations having the same weekday and exact five-minute local
time slot.

This enables statements such as:

- citywide congestion context is typical/high/low for this time;

without claiming that any specific pilot road has the same condition.
