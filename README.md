<img src="https://raw.githubusercontent.com/ColeMundus/ha-sportclips/main/custom_components/sportclips/brand/icon.png" alt="Sport Clips" width="96" height="96">

# Sport Clips for Home Assistant

[![CI: workflow](docs/badges/ci.svg)](https://github.com/ColeMundus/ha-sportclips/actions/workflows/ci.yml)
[![HA tested: 2026.10.0 | 2026.11.0](docs/badges/compatibility.svg)](https://github.com/ColeMundus/ha-sportclips/actions/workflows/ci.yml)
[![License: MIT](docs/badges/license.svg)](LICENSE)
[![Distribution: HACS custom](docs/badges/distribution.svg)](#hacs)

Account-free estimated waits and store status for selected Sport Clips salons.
Independent and unofficial; not affiliated with or endorsed by Sport Clips.

## Install

Requires **Home Assistant Core 2026.10.0 or later**. Tested on Core 2026.10.0 and
2026.11.0. No Sport Clips account, API key or separate server required.

### HACS

This integration is **not yet listed in the default HACS catalog**.

1. Open **HACS → Custom repositories**.
2. Add `https://github.com/ColeMundus/ha-sportclips` and choose **Integration**.
3. Download **Sport Clips** and restart Home Assistant.

### Manual installation

1. Copy `custom_components/sportclips` into your Home Assistant configuration's
   `custom_components` folder.
2. Restart Home Assistant.

## Set up

Open **Settings → Devices & services → Add integration → Sport Clips**. Leave the
**city or ZIP code** blank to use your Home Assistant location, or enter a search
and choose a location. Then select a salon and **polling interval**
(whole minutes, **1–60**, default **2**). Change the interval later using the
entry's **Configure** button. Repeat setup to monitor additional salons.

## Sensors

Each salon has two sensors sharing the configured polling interval. Default entity
IDs begin with `sensor.sports_clips_`, followed by the salon and sensor name.

| Sensor | Value |
| --- | --- |
| Estimated wait | Wait in minutes, including zero. Unknown when no valid estimate is available. |
| Store status | Open, lineup opens soon, opens soon, closed until next day, closed or offline. |

Failed reads make sensors **unavailable** until a successful refresh. Automatic
backoff handles provider errors; manual refreshes respect polling and retry limits.

## Limitations and privacy

- Waits are estimates, not appointments. This integration is read-only: no check-ins,
  bookings or stylist selection.
- It uses an undocumented Sport Clips API. Availability, location coverage and
  time-zone accuracy depend on the provider.
- Search text, your Home Assistant coordinates when using the default location,
  and selected salon coordinates are sent to Sport Clips. The selected salon is
  stored in Home Assistant; search queries are not saved by the integration.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and [SECURITY.md](SECURITY.md)
for reporting. Code is [MIT licensed](LICENSE). Sport Clips artwork and trademarks
belong to their owners; see the [artwork notice](custom_components/sportclips/brand/NOTICE.md).
The code license grants no trademark or service-access rights. Use of the service
is subject to [Sport Clips' terms](https://terms.sportclipsinc.com/).
