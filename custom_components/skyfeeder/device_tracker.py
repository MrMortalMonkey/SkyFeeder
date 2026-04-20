"""SkyFeeder device_tracker platform.

Creates one device_tracker entity per aircraft currently inside the configured
radius.  Entities are added dynamically when an aircraft enters the area and
set to ``not_home`` (rather than removed) when they leave, so automations can
trigger on zone-exit events without the entity disappearing.

Each tracker's state reflects HA zone membership (``home``, a named zone, or
``not_home``) and carries the full aircraft attribute dict for use in templates
and automations.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLE_TRACKERS,
    CONF_MAX_TRACKERS,
    CONF_WATCHED_REGISTRATIONS,
    DEFAULT_ENABLE_TRACKERS,
    DEFAULT_MAX_TRACKERS,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .coordinator import Aircraft, SkyFeederCoordinator, _parse_csv

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device_tracker entities.

    Two independent mechanisms:
      * Opt-in registration watchlist - one fixed entity per tail number the
        user listed in CONF_WATCHED_REGISTRATIONS. Entity shows position while
        the airframe is inside the watch area and `not_home` otherwise.
      * Legacy auto-trackers - one entity per aircraft inside the watch area,
        opt-in via CONF_ENABLE_TRACKERS (default False as of 1.2.0).
    """
    merged = {**entry.data, **entry.options}
    coordinator: SkyFeederCoordinator = hass.data[DOMAIN][entry.entry_id]

    watchlist = _parse_csv(merged.get(CONF_WATCHED_REGISTRATIONS))
    auto_enabled = bool(merged.get(CONF_ENABLE_TRACKERS, DEFAULT_ENABLE_TRACKERS))

    if watchlist:
        async_add_entities(
            SkyFeederWatchlistTrackerEntity(coordinator, entry, reg) for reg in sorted(watchlist)
        )

    if not auto_enabled:
        return

    max_trackers: int = int(merged.get(CONF_MAX_TRACKERS, DEFAULT_MAX_TRACKERS))

    # Registration-keyed set of tails we've already covered via the watchlist;
    # skip them in auto-tracking to avoid a duplicate entity per aircraft.
    watchlist_regs: set[str] = watchlist

    # Keep a registry of auto-created trackers we've seen (hex -> entity).
    known: dict[str, SkyFeederTrackerEntity] = {}

    @callback
    def _handle_update() -> None:
        data = coordinator.data
        if not data:
            return

        # Build the set of hex codes we want auto-trackers for:
        # aircraft in area + any manually tracked ones visible anywhere.
        wanted_hexes: set[str] = set()
        for ac in data.in_area:
            if (ac.registration or "").lower() in watchlist_regs:
                continue
            wanted_hexes.add(ac.hex)
        for ac in data.aircraft:
            ident_lower = set([ac.hex, (ac.flight or "").lower(), (ac.registration or "").lower()])
            if ident_lower & coordinator.tracked:
                if (ac.registration or "").lower() in watchlist_regs:
                    continue
                wanted_hexes.add(ac.hex)

        # Respect the cap (closest first).
        if max_trackers and len(wanted_hexes) > max_trackers:
            by_hex = {a.hex: a for a in data.aircraft}
            ranked = sorted(
                wanted_hexes,
                key=lambda h: (by_hex[h].distance_km if (h in by_hex and by_hex[h].distance_km is not None) else 9999),
            )
            wanted_hexes = set(ranked[:max_trackers])

        by_hex = {a.hex: a for a in data.aircraft}
        new_entities: list[SkyFeederTrackerEntity] = []

        for hex_ in wanted_hexes:
            if hex_ not in known:
                ac = by_hex.get(hex_)
                if ac is None:
                    continue
                entity = SkyFeederTrackerEntity(coordinator, entry, ac)
                known[hex_] = entity
                new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

        # Mark aircraft no longer seen as not_home.
        for hex_, entity in known.items():
            if hex_ in by_hex:
                entity.update_aircraft(by_hex[hex_])
            else:
                entity.mark_not_home()

    coordinator.async_add_listener(_handle_update)
    # Run once immediately if data already available.
    if coordinator.data:
        _handle_update()


class SkyFeederTrackerEntity(CoordinatorEntity[SkyFeederCoordinator], TrackerEntity):
    """A device tracker for one aircraft (identified by ICAO 24-bit hex)."""

    _attr_has_entity_name = True
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator: SkyFeederCoordinator,
        entry: ConfigEntry,
        aircraft: Aircraft,
    ) -> None:
        super().__init__(coordinator)
        self._aircraft = aircraft
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tracker_{aircraft.hex}"
        self._attr_name = self._display_name(aircraft)
        self._attr_icon = "mdi:airplane"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or "SkyFeeder",
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=f"http://{coordinator.host}:{coordinator.port}/",
        )

    # ---- Helpers -----------------------------------------------------------

    @staticmethod
    def _display_name(aircraft: Aircraft) -> str:
        flight = (aircraft.flight or "").strip()
        if flight:
            return f"{flight} ({aircraft.hex.upper()})"
        return aircraft.hex.upper()

    def update_aircraft(self, aircraft: Aircraft) -> None:
        self._aircraft = aircraft
        self.async_write_ha_state()

    def mark_not_home(self) -> None:
        self._aircraft = Aircraft(hex=self._aircraft.hex)
        self.async_write_ha_state()

    # ---- TrackerEntity required properties ---------------------------------

    @property
    def latitude(self) -> float | None:
        return self._aircraft.latitude

    @property
    def longitude(self) -> float | None:
        return self._aircraft.longitude

    @property
    def location_accuracy(self) -> int:
        # ADS-B position accuracy is typically ~10 m; use 50 m as conservative estimate.
        return 50

    @property
    def battery_level(self) -> int | None:
        return None

    # ---- State / attributes ------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._aircraft.as_attr_dict()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Coordinator pushes updates; find our aircraft in the new data."""
        data = self.coordinator.data
        if data:
            by_hex = {a.hex: a for a in data.aircraft}
            if self._aircraft.hex in by_hex:
                self._aircraft = by_hex[self._aircraft.hex]
        self.async_write_ha_state()


class SkyFeederWatchlistTrackerEntity(CoordinatorEntity[SkyFeederCoordinator], TrackerEntity):
    """A fixed device tracker keyed on a single registration (tail number).

    Shows position only while the airframe is inside the configured watch
    area; otherwise reports ``not_home``. The entity exists across restarts
    regardless of whether the aircraft is currently visible, so automations
    can reference it reliably.
    """

    _attr_has_entity_name = True
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator: SkyFeederCoordinator,
        entry: ConfigEntry,
        registration: str,
    ) -> None:
        super().__init__(coordinator)
        self._registration = registration.strip().lower()
        pretty = self._registration.upper()
        self._attr_unique_id = f"{entry.entry_id}_watch_{self._registration}"
        self._attr_name = pretty
        self._attr_icon = "mdi:airplane-marker"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or "SkyFeeder",
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=f"http://{coordinator.host}:{coordinator.port}/",
        )

    def _find_in_area(self) -> Aircraft | None:
        data = self.coordinator.data
        if not data:
            return None
        target = self._registration
        for ac in data.in_area:
            if (ac.registration or "").lower() == target:
                return ac
        return None

    @property
    def latitude(self) -> float | None:
        ac = self._find_in_area()
        return ac.latitude if ac else None

    @property
    def longitude(self) -> float | None:
        ac = self._find_in_area()
        return ac.longitude if ac else None

    @property
    def location_accuracy(self) -> int:
        return 50

    @property
    def battery_level(self) -> int | None:
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ac = self._find_in_area()
        if ac is not None:
            return ac.as_attr_dict()
        return {"registration": self._registration.upper(), "in_area": False}

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
