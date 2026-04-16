# SkyFeeder — Home Assistant Integration

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

The integration is configured entirely through the UI config flow.

| Field | Default | Description |
|---|---|---|
| Name | `SkyFeeder` | Friendly name for this instance |
| Host | — | Hostname / IP of the feeder machine |
| Port | `8080` | tar1090 HTTP port |
| Latitude | HA location | Centre of the monitoring area |
| Longitude | HA location | Centre of the monitoring area |
| Radius (km) | `50` | Aircraft within this distance trigger zone events |
| Scan interval (s) | `15` | How often to poll `aircraft.json` |
| Min altitude (ft) | `0` | Ignore aircraft below this altitude |
| Max altitude (ft) | `60000` | Ignore aircraft above this altitude |
| Filter categories | _empty_ | ICAO emitter categories to **include** (e.g. `A1,A3,A5,A7`). Empty = all. |
| Filter types | _empty_ | ICAO type designators to **include** (e.g. `A320,B738`). Empty = all. |
| Exclude categories | _empty_ | ICAO emitter categories to **exclude** (e.g. `B1,B6`). |
| Exclude types | _empty_ | ICAO type designators to **exclude** (e.g. `GLID,PA28`). |
| Enable device trackers | `true` | Create a `device_tracker` per in-area aircraft |
| Max device trackers | `25` | Cap on tracker entities (0 = unlimited) |
| Enable panels | `true` | Add iframe sidebar panels for tar1090 + graphs1090 |
| tar1090 path | `/` | Subpath where tar1090 is served on the host |
| graphs1090 port | `8080` | Port hosting graphs1090 (usually same as tar1090) |
| graphs1090 path | `/graphs1090` | Subpath where graphs1090 is served |

All fields are editable after setup via **Settings → Devices & Services →
SkyFeeder → Configure**.

### Aircraft type filtering

Filters apply to the *area* sensors (`aircraft_in_area`, `closest_aircraft`,
device trackers, zone-entry/exit events). The `aircraft_total` sensor still
counts everything in the feed.

Common ICAO emitter category codes:

| Code | Class | Code | Class |
|------|-------|------|-------|
| A1 | Light (< 15,500 lb) | B1 | Glider |
| A2 | Small | B2 | Lighter than air |
| A3 | Large (75–300 k lb) | B4 | Ultralight |
| A4 | High vortex large | B6 | UAV / drone |
| A5 | Heavy (> 300 k lb) | B7 | Space vehicle |
| A6 | High performance | C1 | Emergency vehicle |
| A7 | Rotorcraft | C2 | Surface service vehicle |

```yaml
# Only show airliners larger than commuters:
filter_categories: A3,A5

# Hide drones and gliders:
exclude_categories: B1,B6

# Only the planes you actually care about:
filter_types: A320,A321,B738,B77W
```

### Sidebar panels

When *Enable panels* is on, the integration registers two iframe panels in
the HA sidebar pointing directly at the upstream feeder host:

* **`<name> Map`** — tar1090 ADS-B map
* **`<name> Stats`** — graphs1090 station statistics

> ⚠ **Mixed content:** if your Home Assistant is HTTPS but the feeder is HTTP,
> browsers will refuse to load the iframes. Either serve the feeder over HTTPS
> (e.g. behind a reverse proxy) or turn off *Enable panels* — all other
> entities continue to work.

---

## Entities

### Sensors

| Entity | Description | Attributes |
|---|---|---|
| `sensor.skyfeeder_aircraft_in_area` | Aircraft within your configured radius | `aircraft` list with full details |
| `sensor.skyfeeder_aircraft_total` | Total aircraft in feed | `aircraft` list |
| `sensor.skyfeeder_aircraft_with_position` | Aircraft reporting lat/lon | — |
| `sensor.skyfeeder_mlat_aircraft` | MLAT-derived positions | `aircraft` list |
| `sensor.skyfeeder_messages` | Cumulative message count | — |
| `sensor.skyfeeder_messages_per_second` | Rolling message rate (msg/s) | — |
| `sensor.skyfeeder_strongest_signal` | Max RSSI in feed (dBFS) | — |
| `sensor.skyfeeder_closest_aircraft` | Distance to nearest in-area aircraft (km) | Full aircraft detail |
| `sensor.skyfeeder_highest_aircraft` | Altitude of highest aircraft (ft) | Full aircraft detail |
| `sensor.skyfeeder_fastest_aircraft` | Ground speed of fastest aircraft (kt) | Full aircraft detail |
| `sensor.skyfeeder_receiver_gain` | SDR receiver gain (dB) | Full `receiver.json` |
| `sensor.skyfeeder_tracked_aircraft` | Count of manually-tracked aircraft | `tracked` set + `aircraft` matches |

Each sensor's `aircraft` attribute contains a list of objects with fields:

`hex`, `flight`, `registration`, `squawk`, `category`, `aircraft_type`,
`altitude`, `ground_speed`, `track`, `latitude`, `longitude`,
`vertical_rate`, `rssi`, `messages`, `seen`, `seen_pos`, `mlat`, `tisb`,
`distance_km`

### Device Trackers

When **Enable device trackers** is on, one `device_tracker.<flight_hex>`
entity is created for each aircraft currently inside the radius (up to the
configured cap). Trackers are also created for any aircraft in the
manually-tracked list regardless of zone.

- **State**: `home`, a named HA zone, or `not_home`
- **Attributes**: full aircraft detail dict (same fields as sensor attributes)
- Trackers persist as `not_home` after an aircraft leaves the feed so zone-exit
  automations can still trigger.

---

## Events

All events fire on the Home Assistant event bus. Each event payload is the
full aircraft detail dict.

| Event | When |
|---|---|
| `skyfeeder_aircraft_entered` | Aircraft moves inside the configured radius |
| `skyfeeder_aircraft_exited` | Aircraft moves outside the configured radius |
| `skyfeeder_new_aircraft` | New ICAO hex appears in the feed |
| `skyfeeder_mlat_detected` | Aircraft acquires a MLAT-derived position |
| `skyfeeder_aircraft_took_off` | In-area aircraft climbs above 500 ft AGL |
| `skyfeeder_aircraft_landed` | In-area aircraft descends below 200 ft AGL |

### Example automation — notify on zone entry

```yaml
automation:
  - alias: "Aircraft entered my area"
    trigger:
      - platform: event
        event_type: skyfeeder_aircraft_entered
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Aircraft entering area"
          message: >-
            {{ trigger.event.data.flight | default(trigger.event.data.hex) }}
            at {{ trigger.event.data.altitude | default('?') }} ft,
            {{ trigger.event.data.distance_km | round(1) }} km away.
```

---

## Services

### `skyfeeder.track_aircraft`

Add an aircraft to the manually-tracked list. It will appear in
`sensor.skyfeeder_tracked_aircraft` and a `device_tracker` will be created for
it even outside the zone.

```yaml
service: skyfeeder.track_aircraft
data:
  aircraft: "BAW123"   # callsign, ICAO hex, or registration
```

### `skyfeeder.untrack_aircraft`

```yaml
service: skyfeeder.untrack_aircraft
data:
  aircraft: "BAW123"
```

### `skyfeeder.clear_tracked`

Remove all manually-tracked aircraft.

```yaml
service: skyfeeder.clear_tracked
```

---

## Troubleshooting

**"Cannot connect" during setup**
Verify that `http://<host>:<port>/data/aircraft.json` is reachable from
your Home Assistant host's network.

**No aircraft appearing in area sensor**
Check that the monitoring latitude/longitude and radius in the integration
options actually cover the sky above you. The radius defaults to 50 km.

**Device trackers not created**
Confirm *Enable device trackers* is on in the options, and that aircraft are
inside your configured radius. Entities only appear after the first poll that
finds in-range aircraft.
