"""DataUpdateCoordinator for the SkyFeeder integration."""
from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AIRCRAFT_ENDPOINT,
    AIRPORT_EVENT_RADIUS_KM,
    CONF_AIRPORT_CODE,
    CONF_AIRPORT_ELEVATION_FT,
    CONF_AIRPORT_LATITUDE,
    CONF_AIRPORT_LONGITUDE,
    CONF_AIRPORT_NAME,
    CONF_EXCLUDE_CATEGORIES,
    CONF_EXCLUDE_TYPES,
    CONF_FILTER_CATEGORIES,
    CONF_FILTER_TYPES,
    CONF_HOST,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MAX_ALTITUDE,
    CONF_MIN_ALTITUDE,
    CONF_PORT,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    DEFAULT_MAX_ALTITUDE,
    DEFAULT_MIN_ALTITUDE,
    DEFAULT_PORT,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL,
    EVENT_ENTRY,
    EVENT_EXIT,
    EVENT_LANDED,
    EVENT_MLAT,
    EVENT_NEW,
    EVENT_TOOK_OFF,
    HTTP_TIMEOUT,
    LANDED_AGL_FT,
    RECEIVER_ENDPOINT,
    STATS_ENDPOINT,
    TAKEOFF_AGL_FT,
)


def _parse_csv(raw: str | list | None) -> set[str]:
    """Normalise a comma-separated string (or list) to a lowercase set."""
    if raw is None:
        return set()
    if isinstance(raw, str):
        items = [s.strip() for s in raw.split(",")]
    else:
        items = [str(s).strip() for s in raw]
    return {s.lower() for s in items if s}

_LOGGER = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass
class Aircraft:
    """Normalised view of one aircraft record from aircraft.json."""

    hex: str
    flight: str | None = None
    registration: str | None = None
    squawk: str | None = None
    category: str | None = None              # ICAO emitter category (A1..C7)
    aircraft_type: str | None = None         # ICAO type designator (A320, B738, ...)
    altitude: int | None = None              # barometric altitude, ft
    ground_speed: float | None = None        # knots
    track: float | None = None               # deg
    latitude: float | None = None
    longitude: float | None = None
    vertical_rate: int | None = None         # ft/min
    rssi: float | None = None                # dBFS
    messages: int | None = None
    seen: float | None = None
    seen_pos: float | None = None
    mlat: bool = False
    tisb: bool = False
    distance_km: float | None = None
    on_ground: bool = False
    agl_ft: int | None = None              # altitude relative to configured airport elevation
    distance_to_airport_km: float | None = None

    def as_attr_dict(self) -> dict[str, Any]:
        d = {
            "hex": self.hex,
            "flight": self.flight,
            "registration": self.registration,
            "squawk": self.squawk,
            "category": self.category,
            "aircraft_type": self.aircraft_type,
            "altitude": self.altitude,
            "ground_speed": self.ground_speed,
            "track": self.track,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "vertical_rate": self.vertical_rate,
            "rssi": self.rssi,
            "messages": self.messages,
            "seen": self.seen,
            "seen_pos": self.seen_pos,
            "mlat": self.mlat,
            "tisb": self.tisb,
            "distance_km": (round(self.distance_km, 2) if self.distance_km is not None else None),
            "on_ground": self.on_ground,
            "agl_ft": self.agl_ft,
            "distance_to_airport_km": (
                round(self.distance_to_airport_km, 2)
                if self.distance_to_airport_km is not None
                else None
            ),
        }
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class SkyFeederData:
    """Snapshot of the current feeder state."""

    aircraft: list[Aircraft] = field(default_factory=list)
    in_area: list[Aircraft] = field(default_factory=list)
    messages: int | None = None
    messages_per_second: float | None = None
    receiver: dict[str, Any] = field(default_factory=dict)
    now: float = 0.0

    @property
    def total(self) -> int:
        return len(self.aircraft)

    @property
    def with_position(self) -> list[Aircraft]:
        return [a for a in self.aircraft if a.latitude is not None and a.longitude is not None]

    @property
    def mlat_aircraft(self) -> list[Aircraft]:
        return [a for a in self.aircraft if a.mlat]

    @property
    def closest(self) -> Aircraft | None:
        ranked = [a for a in self.in_area if a.distance_km is not None]
        return min(ranked, key=lambda a: a.distance_km) if ranked else None

    @property
    def highest(self) -> Aircraft | None:
        ranked = [a for a in self.aircraft if a.altitude is not None]
        return max(ranked, key=lambda a: a.altitude) if ranked else None

    @property
    def fastest(self) -> Aircraft | None:
        ranked = [a for a in self.aircraft if a.ground_speed is not None]
        return max(ranked, key=lambda a: a.ground_speed) if ranked else None

    @property
    def strongest_rssi(self) -> float | None:
        rssis = [a.rssi for a in self.aircraft if a.rssi is not None]
        return max(rssis) if rssis else None


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> int | None:
    f = _to_float(v)
    return int(f) if f is not None else None


def _parse_aircraft(raw: dict[str, Any], home_lat: float | None, home_lon: float | None) -> Aircraft:
    """Map a raw aircraft.json entry to an :class:`Aircraft`."""
    hex_code = (raw.get("hex") or "").strip().lower()
    alt_raw = raw.get("alt_baro")
    on_ground = alt_raw == "ground" or bool(raw.get("ground"))
    if alt_raw == "ground":
        altitude = None  # MSL is unknown when the airframe just reports "ground"
    else:
        altitude = _to_int(alt_raw) if alt_raw is not None else _to_int(raw.get("altitude"))

    lat = _to_float(raw.get("lat"))
    lon = _to_float(raw.get("lon"))
    distance = (
        haversine_km(home_lat, home_lon, lat, lon)
        if lat is not None and lon is not None and home_lat is not None and home_lon is not None
        else None
    )

    mlat_field = raw.get("mlat")
    is_mlat = bool(mlat_field) if isinstance(mlat_field, list) else bool(mlat_field)

    cat = raw.get("category")
    type_designator = (raw.get("t") or raw.get("type") or "").strip() or None

    return Aircraft(
        hex=hex_code,
        flight=(raw.get("flight") or "").strip() or None,
        registration=raw.get("r") or raw.get("registration"),
        squawk=raw.get("squawk"),
        category=(cat.upper() if isinstance(cat, str) else None),
        aircraft_type=(type_designator.upper() if type_designator else None),
        altitude=altitude,
        ground_speed=_to_float(raw.get("gs")),
        track=_to_float(raw.get("track")),
        latitude=lat,
        longitude=lon,
        vertical_rate=_to_int(raw.get("baro_rate") or raw.get("geom_rate")),
        rssi=_to_float(raw.get("rssi")),
        messages=_to_int(raw.get("messages")),
        seen=_to_float(raw.get("seen")),
        seen_pos=_to_float(raw.get("seen_pos")),
        mlat=is_mlat,
        tisb=bool(raw.get("tisb")),
        distance_km=distance,
        on_ground=on_ground,
    )


class SkyFeederCoordinator(DataUpdateCoordinator[SkyFeederData]):
    """Polls the upstream feeder's tar1090 JSON endpoints and maintains state."""

    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
        self.hass = hass
        self.host: str = entry_data[CONF_HOST]
        self.port: int = int(entry_data.get(CONF_PORT, DEFAULT_PORT))
        self.home_lat: float | None = entry_data.get(CONF_LATITUDE) or hass.config.latitude
        self.home_lon: float | None = entry_data.get(CONF_LONGITUDE) or hass.config.longitude
        self.radius_km: float = float(entry_data.get(CONF_RADIUS, DEFAULT_RADIUS_KM))
        self.min_altitude: int = int(entry_data.get(CONF_MIN_ALTITUDE, DEFAULT_MIN_ALTITUDE))
        self.max_altitude: int = int(entry_data.get(CONF_MAX_ALTITUDE, DEFAULT_MAX_ALTITUDE))

        # Configured local airport (optional). When set, AGL is computed as
        # altitude_msl - airport_elevation_ft and takeoff / landed events are
        # gated to aircraft within AIRPORT_EVENT_RADIUS_KM of the field.
        self.airport_code: str = (entry_data.get(CONF_AIRPORT_CODE) or "").strip().upper()
        self.airport_name: str = entry_data.get(CONF_AIRPORT_NAME) or ""
        elev = entry_data.get(CONF_AIRPORT_ELEVATION_FT)
        self.airport_elevation_ft: int = int(elev) if elev is not None else 0
        self.airport_lat: float | None = _to_float(entry_data.get(CONF_AIRPORT_LATITUDE))
        self.airport_lon: float | None = _to_float(entry_data.get(CONF_AIRPORT_LONGITUDE))

        # Aircraft type filtering. Empty set -> no filter for that dimension.
        self.filter_categories: set[str] = _parse_csv(entry_data.get(CONF_FILTER_CATEGORIES))
        self.filter_types: set[str] = _parse_csv(entry_data.get(CONF_FILTER_TYPES))
        self.exclude_categories: set[str] = _parse_csv(entry_data.get(CONF_EXCLUDE_CATEGORIES))
        self.exclude_types: set[str] = _parse_csv(entry_data.get(CONF_EXCLUDE_TYPES))

        scan = int(entry_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        # State for event detection.
        self._in_area_hexes: set[str] = set()
        self._known_hexes: set[str] = set()
        self._mlat_hexes: set[str] = set()
        self._airborne_hexes: set[str] = set()
        self._ground_hexes: set[str] = set()
        self._last_messages: int | None = None
        self._last_poll_ts: float | None = None

        # Extra manually-tracked aircraft (by ICAO hex or callsign).
        self.tracked: set[str] = set()

        super().__init__(
            hass,
            _LOGGER,
            name=f"skyfeeder:{self.host}",
            update_interval=timedelta(seconds=max(5, scan)),
        )

    # ---- HTTP ---------------------------------------------------------------

    async def _fetch_json(self, path: str) -> dict[str, Any] | None:
        session = async_get_clientsession(self.hass)
        url = f"http://{self.host}:{self.port}{path}"
        try:
            async with asyncio.timeout(HTTP_TIMEOUT):
                resp = await session.get(url)
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug("Fetch failed for %s: %s", url, err)
            return None

    async def async_probe(self) -> bool:
        """Used by the config flow to validate host/port."""
        data = await self._fetch_json(AIRCRAFT_ENDPOINT)
        return isinstance(data, dict) and "aircraft" in data

    # ---- Filtering ---------------------------------------------------------

    def _passes_type_filter(self, ac: Aircraft) -> bool:
        """Apply category / type include + exclude lists.

        - Include lists: empty = match-all; non-empty = aircraft must match
          at least one entry on every non-empty include dimension.
        - Exclude lists: aircraft matching any entry are dropped.
        - Aircraft without a known category/type *pass* include filters
          unless every include dimension is non-empty (we don't want to drop
          unknowns just because they didn't broadcast a category).
        """
        cat = (ac.category or "").lower()
        typ = (ac.aircraft_type or "").lower()

        if self.exclude_categories and cat and cat in self.exclude_categories:
            return False
        if self.exclude_types and typ and typ in self.exclude_types:
            return False

        if self.filter_categories or self.filter_types:
            cat_ok = (not self.filter_categories) or (cat in self.filter_categories)
            type_ok = (not self.filter_types) or (typ in self.filter_types)
            # If the aircraft is missing the field used by an active include
            # filter, treat it as a non-match for that dimension.
            if self.filter_categories and not cat:
                cat_ok = False
            if self.filter_types and not typ:
                type_ok = False
            if not (cat_ok and type_ok):
                return False

        return True

    # ---- Coordinator entry point -------------------------------------------

    async def _async_update_data(self) -> SkyFeederData:
        aircraft_doc, receiver_doc = await asyncio.gather(
            self._fetch_json(AIRCRAFT_ENDPOINT),
            self._fetch_json(RECEIVER_ENDPOINT),
        )
        if not aircraft_doc:
            raise UpdateFailed(f"aircraft.json not available from {self.host}:{self.port}")

        now_ts = time.time()
        aircraft: list[Aircraft] = []
        for raw in aircraft_doc.get("aircraft", []) or []:
            ac = _parse_aircraft(raw, self.home_lat, self.home_lon)
            if not ac.hex:
                continue
            self._enrich_with_airport(ac)
            aircraft.append(ac)

        # Filter aircraft within area + altitude band + type filters
        # for event / closest logic.
        in_area = [
            a
            for a in aircraft
            if a.distance_km is not None
            and a.distance_km <= self.radius_km
            and (a.altitude is None or self.min_altitude <= a.altitude <= self.max_altitude)
            and self._passes_type_filter(a)
        ]

        self._dispatch_events(aircraft, in_area)

        # Rolling messages/sec.
        total_msgs = _to_int(aircraft_doc.get("messages"))
        msgs_per_sec: float | None = None
        if total_msgs is not None and self._last_messages is not None and self._last_poll_ts is not None:
            dt = max(1.0, now_ts - self._last_poll_ts)
            diff = total_msgs - self._last_messages
            if diff >= 0:
                msgs_per_sec = round(diff / dt, 2)
        self._last_messages = total_msgs
        self._last_poll_ts = now_ts

        return SkyFeederData(
            aircraft=aircraft,
            in_area=in_area,
            messages=total_msgs,
            messages_per_second=msgs_per_sec,
            receiver=receiver_doc or {},
            now=_to_float(aircraft_doc.get("now")) or now_ts,
        )

    # ---- Airport enrichment ------------------------------------------------

    def _enrich_with_airport(self, ac: Aircraft) -> None:
        """Populate AGL relative to the configured airport, plus distance to it."""
        if ac.altitude is not None:
            ac.agl_ft = ac.altitude - self.airport_elevation_ft
        if (
            self.airport_lat is not None
            and self.airport_lon is not None
            and ac.latitude is not None
            and ac.longitude is not None
        ):
            ac.distance_to_airport_km = haversine_km(
                self.airport_lat, self.airport_lon, ac.latitude, ac.longitude
            )

    # ---- Event detection ---------------------------------------------------

    def _fire(self, event_type: str, aircraft: Aircraft, **extra: Any) -> None:
        payload = aircraft.as_attr_dict()
        if self.airport_code:
            payload.setdefault("airport_code", self.airport_code)
            payload.setdefault("airport_elevation_ft", self.airport_elevation_ft)
            if self.airport_name:
                payload.setdefault("airport_name", self.airport_name)
        payload.update(extra)
        self.hass.bus.async_fire(event_type, payload)

    def _airport_eligible(self, ac: Aircraft) -> bool:
        """True if this aircraft is close enough to the airport to count for
        takeoff / landing events. With no airport configured, fall back to the
        legacy behaviour of just using the watch radius."""
        if not self.airport_code:
            return True
        if ac.distance_to_airport_km is None:
            return False
        return ac.distance_to_airport_km <= AIRPORT_EVENT_RADIUS_KM

    def _dispatch_events(self, aircraft: list[Aircraft], in_area: list[Aircraft]) -> None:
        current_hexes = {a.hex for a in aircraft}
        current_area_hexes = {a.hex for a in in_area}
        by_hex = {a.hex: a for a in aircraft}

        # New aircraft.
        for new_hex in current_hexes - self._known_hexes:
            self._fire(EVENT_NEW, by_hex[new_hex])

        # Zone entry / exit.
        for hex_ in current_area_hexes - self._in_area_hexes:
            self._fire(EVENT_ENTRY, by_hex[hex_])
        for hex_ in self._in_area_hexes - current_area_hexes:
            if hex_ in by_hex:
                self._fire(EVENT_EXIT, by_hex[hex_])

        # MLAT acquisition.
        current_mlat = {a.hex for a in aircraft if a.mlat}
        for hex_ in current_mlat - self._mlat_hexes:
            self._fire(EVENT_MLAT, by_hex[hex_])

        # Takeoff / landing - AGL relative to the configured airport's runway
        # elevation. With no airport configured, agl_ft == altitude (i.e. MSL).
        airborne_now: set[str] = set()
        ground_now: set[str] = set()
        for a in in_area:
            if not self._airport_eligible(a):
                continue
            if a.on_ground:
                ground_now.add(a.hex)
                continue
            if a.agl_ft is None:
                continue
            if a.agl_ft >= TAKEOFF_AGL_FT:
                airborne_now.add(a.hex)
            elif a.agl_ft <= LANDED_AGL_FT:
                ground_now.add(a.hex)

        # Only fire transitions: a plane that first appears at cruise must not
        # generate a "took off" event.
        for hex_ in airborne_now & self._ground_hexes:
            self._fire(
                EVENT_TOOK_OFF,
                by_hex[hex_],
                agl_ft=by_hex[hex_].agl_ft,
            )
        for hex_ in ground_now & self._airborne_hexes:
            self._fire(
                EVENT_LANDED,
                by_hex[hex_],
                agl_ft=by_hex[hex_].agl_ft,
            )

        self._airborne_hexes = airborne_now
        self._ground_hexes = ground_now
        self._in_area_hexes = current_area_hexes
        self._known_hexes = current_hexes
        self._mlat_hexes = current_mlat

    # ---- Services helpers --------------------------------------------------

    def add_tracked(self, ident: str) -> None:
        self.tracked.add(ident.strip().lower())

    def remove_tracked(self, ident: str) -> None:
        self.tracked.discard(ident.strip().lower())

    def clear_tracked(self) -> None:
        self.tracked.clear()
