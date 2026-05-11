# SkyFeeder — Home Assistant Integration (v1.3.0)

A HACS-installable custom integration that connects Home Assistant to a local
[tar1090](https://github.com/wiedehopf/tar1090)-based ADS-B feeder (Ultrafeeder,
readsb, dump1090-fa, …) and exposes live aircraft data as native HA entities.

> Not affiliated with the SDR-Enthusiasts Ultrafeeder project. SkyFeeder is an
> independent HA integration that speaks the standard tar1090 JSON API.

---

## Installation via HACS

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**.
2. Repository: `https://github.com/mrmortalmonkey/skyfeeder`
   Category: **Integration** → **Add**.
3. Find **SkyFeeder** in the integration list → **Download**.
4. Restart Home Assistant.
5. **Settings → Devices & Services → Add Integration → SkyFeeder**.

---

## Configuration

| Field | Default | Description |
|---|---|---|
| Name | `SkyFeeder` | Friendly name for this instance |
| Host | — | Hostname / IP of the feeder machine |
| Port | `8080` | tar1090 HTTP port |
| Use TLS | `false` | Enable HTTPS for remote feeder connections |
| Latitude | HA location | Centre of the monitoring area |
| Longitude | HA location | Centre of the monitoring area |
| Radius (km) | `50` | Aircraft within this distance trigger zone events |
| Scan interval (s) | `15` | How often to poll `aircraft.json` |
| Min altitude (ft) | `0` | Ignore aircraft below this altitude |
| Max altitude (ft) | `60000` | Ignore aircraft above this altitude |
| Filter categories | _empty_ | ICAO emitter categories to **include** |
| Filter types | _empty_ | ICAO type designators to **include** |
| Exclude categories | _empty_ | ICAO emitter categories to **exclude** |
| Exclude types | _empty_ | ICAO type designators to **exclude** |
| Enable device trackers | `false` | Create a `device_tracker` per in-area aircraft |
| Max device trackers | `25` | Cap on tracker entities (0 = unlimited) |
| Path history | `0` | Position history length per aircraft (0=disabled, max 200) |
| Watched registrations | _empty_ | Comma-separated tail numbers for dedicated trackers |
| Enable panels | `true` | Add iframe sidebar panels for tar1090 + graphs1090 |
| tar1090 path | `/` | Subpath where tar1090 is served on the host |
| graphs1090 port | `8080` | Port hosting graphs1090 |
| graphs1090 path | `/graphs1090` | Subpath where graphs1090 is served |

All fields editable after setup via **Configure**.

---

## Entities

### Sensors (14)

| Entity | Description |
|---|---|
| `sensor.skyfeeder_aircraft_in_area` | Count of aircraft within radius (full aircraft list in attributes) |
| `sensor.skyfeeder_aircraft_total` | Total aircraft in the feed |
| `sensor.skyfeeder_aircraft_with_position` | Aircraft reporting lat/lon |
| `sensor.skyfeeder_mlat_aircraft` | MLAT-derived positions |
| `sensor.skyfeeder_messages` | Cumulative message count |
| `sensor.skyfeeder_messages_per_second` | Rolling msg/s rate |
| `sensor.skyfeeder_strongest_signal` | Max RSSI in feed (dBFS) |
| `sensor.skyfeeder_closest_aircraft` | Distance to nearest in-area aircraft (km) |
| `sensor.skyfeeder_highest_aircraft` | Altitude of highest aircraft (ft) |
| `sensor.skyfeeder_fastest_aircraft` | Ground speed of fastest aircraft (kt) |
| `sensor.skyfeeder_receiver_gain` | SDR receiver gain (dB) |
| `sensor.skyfeeder_tracked_aircraft` | Count of manually-tracked aircraft |
| `sensor.skyfeeder_entered_area_recent` | Aircraft that entered area (last hour) |
| `sensor.skyfeeder_exited_area_recent` | Aircraft that exited area (last hour) |

### Binary Sensors (2)

| Entity | Description |
|---|---|
| `binary_sensor.skyfeeder_feeder_online` | Feeder connectivity status |
| `binary_sensor.skyfeeder_has_mlat` | Whether any MLAT aircraft are present |

### Device Trackers

- **Watchlist trackers**: One permanent `device_tracker` per watched tail number
- **Auto-trackers** (opt-in): One per in-area aircraft, capped by max setting
- Location accuracy is dynamically estimated from RSSI + MLAT status
- Attributes include full aircraft detail (hex, flight, registration, altitude, speed, etc.)

---

## Events

| Event | When |
|---|---|
| `skyfeeder_aircraft_entered` | Aircraft moves inside the configured radius |
| `skyfeeder_aircraft_exited` | Aircraft moves outside the configured radius |
| `skyfeeder_new_aircraft` | New ICAO hex appears in the feed |
| `skyfeeder_mlat_detected` | Aircraft acquires a MLAT-derived position |
| `skyfeeder_aircraft_took_off` | In-area aircraft climbs above 500 ft AGL |
| `skyfeeder_aircraft_landed` | In-area aircraft descends below 200 ft AGL |

---

## Services

- `skyfeeder.track_aircraft` — Add aircraft to tracked list (persisted across restarts)
- `skyfeeder.untrack_aircraft` — Remove aircraft from tracked list
- `skyfeeder.clear_tracked` — Remove all tracked aircraft

---

## What's New in 1.3.0

- **HTTPS/TLS support** — Connect to remote feeders over HTTPS (`use_tls` option)
- **Persistent tracked aircraft** — Tracked list survives HA restarts via Store API
- **Flight path history** — Track last N positions per aircraft (configurable, up to 200)
- **Stats endpoint integration** — Fetches `/data/stats.json` for richer telemetry
- **Binary sensors** — `feeder_online` connectivity + `has_mlat` indicators
- **Dynamic location accuracy** — Accuracy varies by RSSI strength and MLAT source
- **Diagnostics support** — Full diagnostics page in HA for easier troubleshooting
- **Feeder reconnection detection** — Logs when feeder goes offline/comes back online
- **Path history pruning** — Stale entries automatically cleaned each poll cycle