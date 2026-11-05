# Sport Clips for Home Assistant

Account-free estimated waits and store status for selected Sport Clips salons.
Independent, unofficial integration; not affiliated with or endorsed by Sport Clips.

## Installation (private preview)

Requires **Home Assistant Core 2026.10.0 or later**. Tested with Core 2026.10.0,
Python 3.14.7 and the real Home Assistant test harness. Later versions are not yet
verified. No additional runtime packages, server, account, API key or cookies.

This repository is private: **HACS installation and validation are unavailable**.
No public release or catalog listing is claimed. Authorized repository users can:

1. Back up the Home Assistant configuration and any existing `sportclips` directory.
2. Copy `custom_components/sportclips` into the configuration directory's
   `custom_components` folder (or extract the locally built manual ZIP there).
3. Restart Home Assistant, then open **Settings → Devices & services → Add integration
   → Sport Clips**.
4. Enter a **city or ZIP code**, select the geographic suggestion, then the salon.
   Repeat setup for additional salons. Duplicate salons are rejected.

To remove it, delete its integration entries, remove the component folder and restart.
No production installation has been verified yet. Do not overwrite an existing
component without a backup; restore that folder and restart to roll back an upgrade.

## Entities and refresh behavior

Each salon has two sensors sharing one read every **120 seconds**:

- **Estimated wait**: provider display estimate in minutes, without rounding or
  a fabricated countdown. Genuine `0` is preserved. Missing, negative, malformed,
  closed/offline and unknown-state waits are **unknown**, not zero.
- **Store status**: provider state mapped to open, lineup opens soon, opens soon,
  closed until next day, closed or offline. Unrecognized states are **unknown**.
  Store status does not imply online check-in availability.

A failed read makes both sensors **unavailable**; the last successful wait is not
shown as current. Recovery restores them after a complete successful read.
Automatic reads are shared by both sensors. Manual refreshes, simultaneous refreshes
and entry reloads cannot accelerate salon reads past 120 seconds. Transport/server
errors use exponential backoff up to one hour, honoring a longer `Retry-After`
(delta seconds or HTTP-date). Provider error cooldowns are host-wide and apply to
setup as well as polling; they can temporarily defer other salons. Cooldowns survive
entry reloads and reopened flows in the same HA process, not full Core restarts.

`fetched_at` records the successful local fetch and `response_generated_at` the
provider response time. Neither proves the upstream wait was newly calculated.
Time-only upstream values are not invented into dated timestamps. Dates in selected
salon queries use that salon's IANA time zone. Estimates can change, are not an
appointment or a guarantee, and are not published as long-term measurement statistics.

## Privacy and limitations

Only anonymous geographic search and bounded store metadata reads are used.
The metadata endpoint uses POST for a **read query**, not a check-in. No account,
stylist, booking, check-in creation/modification/cancellation or store-context actions
exist. No authentication or challenge bypass is attempted on access errors.

City/ZIP searches and selected salon coordinates are sent to the provider. The
selected salon's public identity, coordinates and time zone are stored in the HA
config entry (and backups). Search queries are not saved by the integration. Entity
history may reveal salon preferences. Avoid sharing unredacted HA configuration or
logs. No raw provider responses or diagnostics are exported by this integration.

This is an undocumented first-party endpoint and may change or reject automation;
no provider quota, availability guarantee or automation license is asserted. Discovery
covers a bounded 0.8-degree rectangle, not a nationwide or guaranteed nearest-store
search. Polling uses a tiny 0.01-degree rectangle and exact source ID matching;
a missing result is a failed read, not evidence the salon was deleted. Large cities
may require a more specific ZIP code. Optional stylist data is deliberately excluded.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for reproducible checks and manual packaging.
Source and original generic artwork are [MIT licensed](LICENSE). Service names and
trademarks remain their owners' property; the code license does not grant service
access or trademark rights. See [SECURITY.md](SECURITY.md) for reporting guidance.
