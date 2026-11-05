<img src="https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/10/7e/8d/107e8dc6-d3d0-b886-5539-d5475a8258d5/AppIcon-1x_U007ephone-0-1-85-220-0.png/512x512bb.png" alt="Sport Clips" width="96" height="96">

# Sport Clips for Home Assistant

[![CI workflows](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/ColeMundus/ha-sportclips/actions/workflows/ci.yml)
[![Home Assistant tested: 2026.10.0](https://img.shields.io/badge/Home_Assistant-tested_2026.10.0-18BCF2?logo=homeassistant&logoColor=white)](https://github.com/ColeMundus/ha-sportclips/actions/workflows/ci.yml)
[![Code license: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![HACS: private preview](https://img.shields.io/badge/HACS-private_preview-orange)](#hacs)

Account-free estimated waits and store status for selected Sport Clips salons.
Independent and unofficial; not affiliated with or endorsed by Sport Clips.

## Install

Requires **Home Assistant Core 2026.10.0 or later**. Automated tests use Core
2026.10.0 and Python 3.14.7; installation and setup have also been verified on Core
2026.10.0 with Python 3.14.6. Later Core versions have not been verified. No account,
API key, cookies, additional runtime packages or separate server are needed.

### Manual installation

1. Back up your Home Assistant configuration and any existing `sportclips` folder.
2. Copy `custom_components/sportclips` into your configuration directory's
   `custom_components` folder. Alternatively, extract the manual-install ZIP built
   with [the package command](CONTRIBUTING.md) into the configuration directory.
3. Restart Home Assistant.

### HACS

**Unavailable while this repository is private. It is not listed in the HACS catalog.**
If public distribution is approved later, add
`https://github.com/ColeMundus/ha-sportclips` under **HACS → Custom repositories**,
choose **Integration**, download Sport Clips and restart Home Assistant. HACS uses
repository source; the manual-install ZIP is not a HACS release asset.

## Set up

Open **Settings → Devices & services → Add integration → Sport Clips**. Enter a
**city or ZIP code**, choose the geographic suggestion, then select a salon and
its **polling interval** (whole minutes, **1–60**, default **2**). Change it later
from the entry's **Configure** button in **Settings → Devices & services**.
Existing entries keep the two-minute default until changed.
Repeat setup to monitor more salons; duplicate salons are rejected.

To remove it, delete its integration entries, remove the component folder and
restart. To roll back an update, restore the backed-up folder and restart.

## Sensors

Each salon has two sensors sharing one read at its configured polling interval.
New entity IDs start with `sensor.sports_clips_`, followed by the salon and sensor
name. Existing registry IDs and user customizations are not automatically renamed.

| Sensor | Value |
| --- | --- |
| Estimated wait | Provider estimate in minutes, including genuine zero. Missing, invalid or non-open waits are **unknown**, not zero. |
| Store status | Open, lineup opens soon, opens soon, closed until next day, closed or offline. Unrecognized states are **unknown**. |

Failed reads make both sensors **unavailable** until a successful read. Manual
refreshes and entry reloads cannot bypass the polling interval. Changing the
interval does not shorten an existing polling or provider cooldown. Errors use
exponential backoff up to one hour, or longer when required by `Retry-After`.
Provider error cooldowns are shared across salons and setup flows until Core
restarts. `fetched_at` is the local fetch time; `response_generated_at` is the
provider response time. Neither proves when the wait estimate was last calculated.

## Limitations and privacy

- Estimates are not appointments or guarantees. Store status does not establish
  online check-in availability. No booking, check-in, account or stylist actions
  are provided; the metadata POST is a read-only query.
- The undocumented provider endpoint may change or reject automation. No provider
  quota, availability guarantee or permission to automate is implied. Access
  errors do not trigger authentication or challenge bypass.
- Search covers a bounded area, not a guaranteed nearest-salon search. Try a more
  specific ZIP code if needed. A missing selected salon is a failed read, not proof
  it was deleted. Dates use the selected salon's time zone.
- Searches and salon coordinates are sent to the provider. Selected salon identity,
  coordinates and time zone are stored in HA configuration and backups; search
  queries are not saved. History may reveal salon preferences. Do not share
  unredacted configuration or logs. No raw responses or diagnostics are exported.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for checks and release preparation, and
[SECURITY.md](SECURITY.md) for safe reporting. Code is [MIT licensed](LICENSE).
Sport Clips artwork and trademarks belong to their respective owners; see the
[artwork notice](custom_components/sportclips/brand/NOTICE.md). The code license
does not grant trademark rights or permission to access the service.
