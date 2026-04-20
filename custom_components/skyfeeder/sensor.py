"""SkyFeeder sensor platform."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import Aircraft, SkyFeederCoordinator, SkyFeederData


@dataclass(frozen=True)
class SkyFeederSensorSpec:
    """A single sensor's behaviour."""

    key: str
    name: str
    icon: str
    unit: str | None = None
    state_class: SensorStateClass | None = None
    value_fn: Callable[[SkyFeederData], Any] = lambda d: None
    attrs_fn: Callable[[SkyFeederData], dict[str, Any]] = lambda d: {}


def _aircraft_list_attr(selector: Callable[[SkyFeederData], list[Aircraft]]) -> Callable[[SkyFeederData], dict[str, Any]]:
    def _fn(d: SkyFeederData) -> dict[str, Any]:
        return {"aircraft": [a.as_attr_dict() for a in selector(d)]}
    return _fn


def _single_aircraft_attrs(selector: Callable[[SkyFeederData], Aircraft | None]) -> Callable[[SkyFeederData], dict[str, Any]]:
    def _fn(d: SkyFeederData) -> dict[str, Any]:
        ac = selector(d)
        return ac.as_attr_dict() if ac else {}
    return _fn


SENSOR_SPECS: tuple[SkyFeederSensorSpec, ...] = (
    SkyFeederSensorSpec(
        key="aircraft_in_area",
        name="Aircraft in area",
        icon="mdi:airplane",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.in_area),
        attrs_fn=_aircraft_list_attr(lambda d: d.in_area),
    ),
    SkyFeederSensorSpec(
        key="aircraft_total",
        name="Aircraft total",
        icon="mdi:airplane-search",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.total,
        attrs_fn=_aircraft_list_attr(lambda d: d.aircraft),
    ),
    SkyFeederSensorSpec(
        key="aircraft_with_position",
        name="Aircraft with position",
        icon="mdi:crosshairs-gps",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.with_position),
    ),
    SkyFeederSensorSpec(
        key="mlat_aircraft",
        name="MLAT aircraft",
        icon="mdi:broadcast",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.mlat_aircraft),
        attrs_fn=_aircraft_list_attr(lambda d: d.mlat_aircraft),
    ),
    SkyFeederSensorSpec(
        key="messages",
        name="Messages received",
        icon="mdi:message-processing",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.messages,
    ),
    SkyFeederSensorSpec(
        key="messages_per_second",
        name="Messages per second",
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
        unit="msg/s",
        value_fn=lambda d: d.messages_per_second,
    ),
    SkyFeederSensorSpec(
        key="strongest_signal",
        name="Strongest signal",
        icon="mdi:signal",
        unit="dBFS",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.strongest_rssi,
    ),
    SkyFeederSensorSpec(
        key="closest_aircraft",
        name="Closest aircraft",
        icon="mdi:airplane-marker",
        unit=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (round(d.closest.distance_km, 2) if (d.closest and d.closest.distance_km is not None) else None),
        attrs_fn=_single_aircraft_attrs(lambda d: d.closest),
    ),
    SkyFeederSensorSpec(
        key="highest_aircraft",
        name="Highest aircraft",
        icon="mdi:arrow-up-bold",
        unit="ft",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (d.highest.altitude if d.highest else None),
        attrs_fn=_single_aircraft_attrs(lambda d: d.highest),
    ),
    SkyFeederSensorSpec(
        key="fastest_aircraft",
        name="Fastest aircraft",
        icon="mdi:speedometer",
        unit=UnitOfSpeed.KNOTS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (round(d.fastest.ground_speed, 1) if (d.fastest and d.fastest.ground_speed is not None) else None),
        attrs_fn=_single_aircraft_attrs(lambda d: d.fastest),
    ),
    SkyFeederSensorSpec(
        key="receiver_gain",
        name="Receiver gain",
        icon="mdi:antenna",
        unit="dB",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.receiver.get("gain") if isinstance(d.receiver, dict) else None,
        attrs_fn=lambda d: d.receiver if isinstance(d.receiver, dict) else {},
    ),
    SkyFeederSensorSpec(
        key="tracked_aircraft",
        name="Tracked aircraft",
        icon="mdi:eye",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: 0,  # overridden by SkyFeederTrackedSensor
    ),
    SkyFeederSensorSpec(
        key="entered_area_recent",
        name="Aircraft entered area (last hour)",
        icon="mdi:airplane-landing",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.entered_recent),
        attrs_fn=lambda d: {
            "events": d.entered_recent,
            "aircraft": [e["aircraft"] for e in d.entered_recent],
        },
    ),
    SkyFeederSensorSpec(
        key="exited_area_recent",
        name="Aircraft exited area (last hour)",
        icon="mdi:airplane-takeoff",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.exited_recent),
        attrs_fn=lambda d: {
            "events": d.exited_recent,
            "aircraft": [e["aircraft"] for e in d.exited_recent],
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: SkyFeederCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for spec in SENSOR_SPECS:
        if spec.key == "tracked_aircraft":
            entities.append(SkyFeederTrackedSensor(coordinator, entry, spec))
        else:
            entities.append(SkyFeederSensor(coordinator, entry, spec))

    async_add_entities(entities)


class SkyFeederSensor(CoordinatorEntity[SkyFeederCoordinator], SensorEntity):
    """Base sensor driven by a :class:`SkyFeederSensorSpec`."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SkyFeederCoordinator,
        entry: ConfigEntry,
        spec: SkyFeederSensorSpec,
    ) -> None:
        super().__init__(coordinator)
        self._spec = spec
        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_state_class = spec.state_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or "SkyFeeder",
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=f"http://{coordinator.host}:{coordinator.port}/",
        )

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data
        return self._spec.value_fn(data) if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return self._spec.attrs_fn(data) if data else {}


class SkyFeederTrackedSensor(SkyFeederSensor):
    """A sensor that lists manually-tracked aircraft (by ICAO or callsign)."""

    @property
    def native_value(self) -> int:
        return len(self.coordinator.tracked)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        matches: list[dict[str, Any]] = []
        if data:
            wanted = self.coordinator.tracked
            for ac in data.aircraft:
                flight = (ac.flight or "").lower()
                reg = (ac.registration or "").lower()
                if ac.hex in wanted or flight in wanted or reg in wanted:
                    matches.append(ac.as_attr_dict())
        return {"tracked": sorted(self.coordinator.tracked), "aircraft": matches}
