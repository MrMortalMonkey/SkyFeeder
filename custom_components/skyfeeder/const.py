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
DEFAULT_ENABLE_TRACKERS = True
DEFAULT_MAX_TRACKERS = 25
DEFAULT_FILTER = ""

DEFAULT_ENABLE_PANELS = True
DEFAULT_GRAPHS1090_PORT = 8080
DEFAULT_GRAPHS1090_PATH = "/graphs1090"
DEFAULT_TAR1090_PATH = "/"

# --- HTTP -----------------------------------------------------------------------
AIRCRAFT_ENDPOINT = "/data/aircraft.json"
RECEIVER_ENDPOINT = "/data/receiver.json"
STATS_ENDPOINT = "/data/stats.json"
HTTP_TIMEOUT = 10

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
