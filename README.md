<img src="https://raw.githubusercontent.com/ColeMundus/ha-sportclips/main/custom_components/sportclips/brand/icon.png" alt="Sport Clips" width="96" height="96">

# Sport Clips for Home Assistant

[![CI workflows](docs/badges/ci.svg)](https://github.com/ColeMundus/ha-sportclips/actions/workflows/ci.yml)
[![Home Assistant tested: 2026.10.0](docs/badges/home-assistant.svg)](https://github.com/ColeMundus/ha-sportclips/actions/workflows/ci.yml)
[![Code license: MIT](docs/badges/license.svg)](LICENSE)
[![HACS: custom repository](docs/badges/hacs.svg)](#hacs)

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

Each salon has an estimated-wait sensor and an Opening binary sensor sharing one
refresh. Default IDs begin with `sensor.sports_clips_` for waits and
`binary_sensor.sports_clips_` for store status.

| Sensor | Value |
| --- | --- |
| Estimated wait | Wait in minutes, including zero. Unknown when no valid estimate is available. |
| Store status | Native **Open/Closed** boolean with door icons. Only provider-confirmed open is on; opens soon and all known closed states are off. Offline/unrecognized status is unknown. Detailed status remains in the `provider_status` attribute. |

### Upgrading from the enum status sensor

Setup replaces the obsolete status enum using Home Assistant's entity-registry
APIs. The object name and unique ID are retained, along with custom name, icon,
area, aliases, labels, categories, device association, and disabled/hidden settings
where applicable. Domain-independent registry options and explicit assistant
exposure choices are preserved; an unset exposure choice stays unexposed rather
than adopting the new binary sensor's broader default. Existing binary-sensor
customizations take precedence on retry;
ID collisions receive Home Assistant's normal suffix. Wait sensor identity and
integration configuration are unchanged.

The status entity necessarily moves from `sensor.<object>` to
`binary_sensor.<object>` (and receives a new registry record). Update dashboard,
automation and script references to the old status ID; automations must use `on`
for Open and `off` for Closed instead of enum strings. Old sensor-specific
options and device-class overrides are not copied to the boolean. Historical
status records are not rewritten. No `.storage` files are edited.

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
