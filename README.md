# SkyFeeder — Home Assistant Integration

A HACS-installable Home Assistant integration that connects to a local
[tar1090](https://github.com/wiedehopf/tar1090)-based ADS-B feeder (Ultrafeeder,
readsb, dump1090-fa, graphs1090, …) and exposes everything it sees as native HA
entities — plus optional sidebar panels for the map and station stats.

> Not affiliated with the SDR-Enthusiasts Ultrafeeder project. SkyFeeder is an
> independent HA integration that speaks the standard tar1090 JSON API.

---

**Everything in one HACS install:**

* Live aircraft sensors — in-area, total, MLAT, closest, highest, fastest,
  messages/sec, RSSI, receiver gain, manually-tracked
* Per-aircraft `device_tracker` entities with full GPS attributes
* HA bus events for zone entry/exit, takeoff/landing, MLAT acquisition, and
  new aircraft
* `skyfeeder.track_aircraft` / `untrack_aircraft` / `clear_tracked` services
* Aircraft type filtering — include/exclude by ICAO emitter category
  (A1, A3, B1, B6, …) and/or ICAO type designator (A320, B738, R44, …)
* Sidebar panels — iframe panels pointing at your feeder's tar1090 map and
  graphs1090 stats

---

## Install via HACS

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**.
2. Repository: `https://github.com/mrmortalmonkey/skyfeeder`
   Category: **Integration** → **Add**.
3. Find **SkyFeeder** → **Download**.
4. Restart Home Assistant.
5. **Settings → Devices & Services → Add Integration → SkyFeeder**.
6. Enter the feeder host/port, tune radius and filters.

The sidebar will then show your sensors, device trackers, and (if enabled) two
new panels pointing at the upstream tar1090 and graphs1090 UIs.

---

## Requirements

* Home Assistant 2024.1 or later
* A local ADS-B feeder reachable over HTTP, exposing:
  * `/data/aircraft.json` (tar1090 / readsb)
  * `/data/receiver.json` (optional, for gain sensor)
* Tested against [Ultrafeeder](https://github.com/sdr-enthusiasts/skyfeeder)
  and readsb; should work with any tar1090-compatible frontend.

---

## Aircraft type filtering

Two include lists + two exclude lists, all comma-separated, all
case-insensitive, all empty-by-default.

| Field | Effect |
|---|---|
| `filter_categories` | Only include aircraft whose ICAO emitter category is listed |
| `filter_types` | Only include aircraft whose ICAO type designator is listed |
| `exclude_categories` | Drop aircraft whose category is listed |
| `exclude_types` | Drop aircraft whose type is listed |

Filters apply to the *area* sensors (`aircraft_in_area`, `closest_aircraft`,
device_trackers, zone-entry/exit events). The `aircraft_total` sensor still
counts everything in the feed.

**Common ICAO emitter categories:**

| Code | Class |
|------|-------|
| A1 | Light (< 15,500 lb) |
| A2 | Small |
| A3 | Large (75,000 – 300,000 lb) |
| A4 | High vortex large |
| A5 | Heavy (> 300,000 lb) |
| A6 | High performance |
| A7 | Rotorcraft |
| B1 | Glider |
| B2 | Lighter than air |
| B4 | Ultralight |
| B6 | UAV |
| B7 | Space vehicle |
| C1 | Emergency vehicle |
| C2 | Surface service vehicle |

Examples:

```yaml
# Only commercial airliners (large + heavy):
filter_categories: A3,A5

# Everything except gliders, ultralights, and drones:
exclude_categories: B1,B4,B6

# Only specific aircraft types of interest:
filter_types: A320,A321,B738,B77W

# Drop everything reporting type "GLID" or "PA28":
exclude_types: GLID,PA28
```

---

## Mixed-content note (sidebar panels)

If Home Assistant is served over HTTPS but your feeder is only HTTP, browsers
will refuse to load the iframe panels. Either serve the feeder over HTTPS
(e.g. behind a reverse proxy) or disable **Enable panels** in the integration
options — the sensors, events, services, and device trackers all keep working.

---

## Layout

```
.
├── hacs.json                             # HACS integration manifest
├── README.md
└── custom_components/skyfeeder/          # The integration
    ├── __init__.py
    ├── manifest.json
    ├── config_flow.py
    ├── coordinator.py
    ├── const.py
    ├── sensor.py
    ├── device_tracker.py
    ├── services.yaml
    ├── strings.json
    ├── translations/en.json
    ├── CHANGELOG.md
    └── README.md
```

See [`custom_components/skyfeeder/README.md`](./custom_components/skyfeeder/README.md)
for the full entity / event / service reference.

## License

MIT
