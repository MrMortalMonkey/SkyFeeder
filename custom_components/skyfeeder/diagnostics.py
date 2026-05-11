"""Diagnostics support for SkyFeeder."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SkyFeederCoordinator

TO_REDACT = {
    "latitude",
    "longitude",
    "registration",
    "flight",
    "squawk",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: SkyFeederCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    info = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "host": coordinator.host,
            "port": coordinator.port,
            "use_tls": coordinator.use_tls,
            "home_lat": coordinator.home_lat,
            "home_lon": coordinator.home_lon,
            "radius_km": coordinator.radius_km,
            "min_altitude": coordinator.min_altitude,
            "max_altitude": coordinator.max_altitude,
            "airport_code": coordinator.airport_code,
            "airport_name": coordinator.airport_name,
            "airport_elevation_ft": coordinator.airport_elevation_ft,
            "scan_interval": coordinator.update_interval.total_seconds(),
            "num_filters_categories": len(coordinator.filter_categories),
            "num_filters_types": len(coordinator.filter_types),
            "num_exclude_categories": len(coordinator.exclude_categories),
            "num_exclude_types": len(coordinator.exclude_types),
            "tracked_count": len(coordinator.tracked),
            "path_history_max": coordinator.path_history_max,
            "last_update_success": coordinator.last_update_success,
        },
    }

    if data:
        info["data"] = {
            "total_aircraft": data.total,
            "in_area": len(data.in_area),
            "with_position": len(data.with_position),
            "mlat_count": len(data.mlat_aircraft),
            "messages": data.messages,
            "messages_per_second": data.messages_per_second,
            "feeder_online": data.feeder_online,
            "closest_distance": (
                round(data.closest.distance_km, 2)
                if data.closest and data.closest.distance_km is not None
                else None
            ),
            "entered_recent": len(data.entered_recent),
            "exited_recent": len(data.exited_recent),
            "path_history_entries": sum(len(v) for v in data.path_history.values()),
            "receiver": async_redact_data(dict(data.receiver), TO_REDACT),
        }

    return info