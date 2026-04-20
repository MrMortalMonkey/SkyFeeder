"""Constants for the SkyFeeder integration."""
from __future__ import annotations

DOMAIN = "skyfeeder"
MANUFACTURER = "SkyFeeder"
MODEL = "ADS-B Feeder"

# --- Config flow / options keys -------------------------------------------------
CONF_HOST = "host"
CONF_PORT = "port"
CONF_NAME = "name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_RADIUS = "radius"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MIN_ALTITUDE = "min_altitude"
CONF_MAX_ALTITUDE = "max_altitude"
CONF_ENABLE_TRACKERS = "enable_device_trackers"
CONF_MAX_TRACKERS = "max_device_trackers"

# Opt-in watchlist of specific registrations (tail numbers). One device_tracker
# per entry; shown only when the airframe is inside the configured watch area.
CONF_WATCHED_REGISTRATIONS = "watched_registrations"

# Local airport. User enters an ICAO (KPIR) or IATA (PIR) code; during the
# config flow we resolve it against OurAirports and cache the field elevation +
# position so takeoff/landing events can be fired in AGL terms at that airport.
CONF_AIRPORT_CODE = "airport_code"
CONF_AIRPORT_NAME = "airport_name"
CONF_AIRPORT_ELEVATION_FT = "airport_elevation_ft"
CONF_AIRPORT_LATITUDE = "airport_latitude"
CONF_AIRPORT_LONGITUDE = "airport_longitude"

# Aircraft type filtering (all comma-separated, case-insensitive, empty = no filter).
CONF_FILTER_CATEGORIES = "filter_categories"  # ICAO emitter categories (A1, A3, B6...)
CONF_FILTER_TYPES = "filter_types"            # ICAO type designators (A320, B738, R44...)
CONF_EXCLUDE_CATEGORIES = "exclude_categories"
CONF_EXCLUDE_TYPES = "exclude_types"

# Sidebar panels - register iframe panels for the upstream tar1090 / graphs1090
# UIs so a HACS-only install still gets a map + stats UI in the sidebar.
CONF_ENABLE_PANELS = "enable_panels"
CONF_GRAPHS1090_PORT = "graphs1090_port"
CONF_GRAPHS1090_PATH = "graphs1090_path"
CONF_TAR1090_PATH = "tar1090_path"

# --- Defaults -------------------------------------------------------------------
DEFAULT_NAME = "SkyFeeder"
DEFAULT_PORT = 8080
DEFAULT_RADIUS_KM = 50
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_MIN_ALTITUDE = 0
DEFAULT_MAX_ALTITUDE = 60000
DEFAULT_ENABLE_TRACKERS = False
DEFAULT_MAX_TRACKERS = 25
DEFAULT_WATCHED_REGISTRATIONS = ""
DEFAULT_FILTER = ""

# Rolling window for the entered_area / exited_area recent-activity sensors.
AREA_HISTORY_WINDOW_SEC = 3600
# Hard cap on how many historical entries we keep per log, to bound memory on
# busy feeders (an hour's worth of entries at a very busy urban site).
AREA_HISTORY_MAX_ENTRIES = 500

DEFAULT_ENABLE_PANELS = True
DEFAULT_GRAPHS1090_PORT = 8080
DEFAULT_GRAPHS1090_PATH = "/graphs1090"
DEFAULT_TAR1090_PATH = "/"

# --- HTTP -----------------------------------------------------------------------
AIRCRAFT_ENDPOINT = "/data/aircraft.json"
RECEIVER_ENDPOINT = "/data/receiver.json"
STATS_ENDPOINT = "/data/stats.json"
HTTP_TIMEOUT = 10

# OurAirports public-domain dataset. Used at config time only to resolve a user-
# supplied airport code to its field elevation and coordinates; never polled
# from the running integration. CSV is ~10 MB and indexed in-process per HA run.
OURAIRPORTS_CSV_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OURAIRPORTS_FETCH_TIMEOUT = 60

# Aircraft must be within this many km of the configured airport to be eligible
# for takeoff / landed events. Avoids false positives from descents / climbs at
# unrelated airfields that happen to fall inside the watch radius.
AIRPORT_EVENT_RADIUS_KM = 5.0

# --- Events ---------------------------------------------------------------------
EVENT_ENTRY = "skyfeeder_aircraft_entered"
EVENT_EXIT = "skyfeeder_aircraft_exited"
EVENT_NEW = "skyfeeder_new_aircraft"
EVENT_MLAT = "skyfeeder_mlat_detected"
EVENT_TOOK_OFF = "skyfeeder_aircraft_took_off"
EVENT_LANDED = "skyfeeder_aircraft_landed"

# --- Services -------------------------------------------------------------------
SERVICE_TRACK = "track_aircraft"
SERVICE_UNTRACK = "untrack_aircraft"
SERVICE_CLEAR_TRACKED = "clear_tracked"

# Takeoff / landing heuristic thresholds (feet).
TAKEOFF_AGL_FT = 500
LANDED_AGL_FT = 200
