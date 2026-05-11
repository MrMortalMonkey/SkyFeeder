"""SkyFeeder device_tracker platform."""
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

    watchlist_regs: set[str] = watchlist

    known: dict[str, SkyFeederTrackerEntity] = {}

    @callback
    def _handle_update() -> None:
        data = coordinator.data
        if not data:
            return

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

        for hex_, entity in known.items():
            if hex_ in by_hex:
                entity.update_aircraft(by_hex[hex_])
            else:
                entity.mark_not_home()

    coordinator.async_add_listener(_handle_update)
    if coordinator.data:
        _handle_update()


class SkyFeederTrackerEntity(CoordinatorEntity[SkyFeederCoordinator], TrackerEntity):
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

    @property
    def latitude(self) -> float | None:
        return self._aircraft.latitude

    @property
    def longitude(self) -> float | None:
        return self._aircraft.longitude

    @property
    def location_accuracy(self) -> int:
        return self._aircraft.position_accuracy

    @property
    def battery_level(self) -> int | None:
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._aircraft.as_attr_dict()

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        if data:
            by_hex = {a.hex: a for a in data.aircraft}
            if self._aircraft.hex in by_hex:
                self._aircraft = by_hex[self._aircraft.hex]
        self.async_write_ha_state()


class SkyFeederWatchlistTrackerEntity(CoordinatorEntity[SkyFeederCoordinator], TrackerEntity):
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
        ac = self._find_in_area()
        return ac.position_accuracy if ac else 50

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