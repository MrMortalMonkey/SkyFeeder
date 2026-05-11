"""SkyFeeder binary_sensor platform."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import SkyFeederCoordinator, SkyFeederData


@dataclass(frozen=True)
class SkyFeederBinarySensorSpec:
    key: str
    name: str
    icon_on: str
    icon_off: str
    device_class: BinarySensorDeviceClass | None = None
    value_fn: Callable[[SkyFeederData], bool] = lambda d: False
    attrs_fn: Callable[[SkyFeederData], dict[str, Any]] = lambda d: {}


BINARY_SENSOR_SPECS: tuple[SkyFeederBinarySensorSpec, ...] = (
    SkyFeederBinarySensorSpec(
        key="feeder_online",
        name="Feeder online",
        icon_on="mdi:server-network",
        icon_off="mdi:server-network-off",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: d.feeder_online,
    ),
    SkyFeederBinarySensorSpec(
        key="has_mlat",
        name="MLAT active",
        icon_on="mdi:broadcast",
        icon_off="mdi:broadcast-off",
        value_fn=lambda d: len(d.mlat_aircraft) > 0,
        attrs_fn=lambda d: {"mlat_count": len(d.mlat_aircraft)},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SkyFeederCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        SkyFeederBinarySensor(coordinator, entry, spec)
        for spec in BINARY_SENSOR_SPECS
    ]
    async_add_entities(entities)


class SkyFeederBinarySensor(CoordinatorEntity[SkyFeederCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SkyFeederCoordinator,
        entry: ConfigEntry,
        spec: SkyFeederBinarySensorSpec,
    ) -> None:
        super().__init__(coordinator)
        self._spec = spec
        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"
        self._attr_name = spec.name
        self._attr_device_class = spec.device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or "SkyFeeder",
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=f"http://{coordinator.host}:{coordinator.port}/",
        )

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        return self._spec.value_fn(data) if data else False

    @property
    def icon(self) -> str:
        return self._spec.icon_on if self.is_on else self._spec.icon_off

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return self._spec.attrs_fn(data) if data else {}