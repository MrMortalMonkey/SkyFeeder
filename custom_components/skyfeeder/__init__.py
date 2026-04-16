"""The SkyFeeder integration."""
from __future__ import annotations

import logging
import re

import voluptuous as vol
from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ENABLE_PANELS,
    CONF_GRAPHS1090_PATH,
    CONF_GRAPHS1090_PORT,
    CONF_HOST,
    CONF_PORT,
    CONF_TAR1090_PATH,
    DEFAULT_ENABLE_PANELS,
    DEFAULT_GRAPHS1090_PATH,
    DEFAULT_GRAPHS1090_PORT,
    DEFAULT_TAR1090_PATH,
    DOMAIN,
    SERVICE_CLEAR_TRACKED,
    SERVICE_TRACK,
    SERVICE_UNTRACK,
)
from .coordinator import SkyFeederCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.DEVICE_TRACKER]

TRACK_SCHEMA = vol.Schema({vol.Required("aircraft"): cv.string})

# We track which iframe panel paths each entry registered so they can be
# removed cleanly on unload.
_PANELS_BY_ENTRY: dict[str, list[str]] = {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SkyFeeder from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Merge options on top of data so reconfiguration works.
    merged = {**entry.data, **entry.options}

    coordinator = SkyFeederCoordinator(hass, merged)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)
    _register_panels(hass, entry, merged)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _unregister_panels(hass, entry)

    if not hass.data[DOMAIN]:
        for svc in (SERVICE_TRACK, SERVICE_UNTRACK, SERVICE_CLEAR_TRACKED):
            hass.services.async_remove(DOMAIN, svc)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _all_coordinators(hass: HomeAssistant) -> list[SkyFeederCoordinator]:
    return list(hass.data.get(DOMAIN, {}).values())


def _register_services(hass: HomeAssistant) -> None:
    """Register services once; idempotent across multiple config entries."""
    if hass.services.has_service(DOMAIN, SERVICE_TRACK):
        return

    async def _handle_track(call: ServiceCall) -> None:
        ident: str = call.data["aircraft"]
        for coord in _all_coordinators(hass):
            coord.add_tracked(ident)
            await coord.async_request_refresh()

    async def _handle_untrack(call: ServiceCall) -> None:
        ident: str = call.data["aircraft"]
        for coord in _all_coordinators(hass):
            coord.remove_tracked(ident)
            await coord.async_request_refresh()

    async def _handle_clear(_: ServiceCall) -> None:
        for coord in _all_coordinators(hass):
            coord.clear_tracked()
            await coord.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_TRACK, _handle_track, schema=TRACK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_UNTRACK, _handle_untrack, schema=TRACK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_TRACKED, _handle_clear)


# ---- Sidebar iframe panels ----------------------------------------------------
#
# A HACS-only install still gives users the tar1090 map and graphs1090 stats
# in the HA sidebar by registering iframe panels that point straight at the
# upstream ADS-B feeder host.
#
# Caveat: if Home Assistant is served over HTTPS the browser will refuse to
# load an http:// iframe (mixed content). In that case serve the upstream
# feeder over HTTPS (e.g. behind a reverse proxy) or disable panels.

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG_RE.sub("_", value.lower()).strip("_") or "skyfeeder"


def _normalise_path(path: str | None) -> str:
    if not path or path == "/":
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/")


def _register_panels(hass: HomeAssistant, entry: ConfigEntry, merged: dict) -> None:
    if not merged.get(CONF_ENABLE_PANELS, DEFAULT_ENABLE_PANELS):
        return

    host = merged.get(CONF_HOST)
    if not host:
        return

    tar_port = int(merged.get(CONF_PORT))
    tar_path = _normalise_path(merged.get(CONF_TAR1090_PATH, DEFAULT_TAR1090_PATH))
    graphs_port = int(merged.get(CONF_GRAPHS1090_PORT, DEFAULT_GRAPHS1090_PORT))
    graphs_path = _normalise_path(merged.get(CONF_GRAPHS1090_PATH, DEFAULT_GRAPHS1090_PATH))

    suffix = _slug(entry.entry_id[:8])
    paths: list[str] = []

    map_panel = f"skyfeeder_map_{suffix}"
    graphs_panel = f"skyfeeder_graphs_{suffix}"

    title_prefix = entry.title or "SkyFeeder"

    try:
        async_register_built_in_panel(
            hass,
            "iframe",
            sidebar_title=f"{title_prefix} Map",
            sidebar_icon="mdi:airplane",
            frontend_url_path=map_panel,
            config={"url": f"http://{host}:{tar_port}{tar_path}/"},
            require_admin=False,
        )
        paths.append(map_panel)
    except ValueError as err:
        _LOGGER.warning("Could not register tar1090 panel %s: %s", map_panel, err)

    try:
        async_register_built_in_panel(
            hass,
            "iframe",
            sidebar_title=f"{title_prefix} Stats",
            sidebar_icon="mdi:chart-line",
            frontend_url_path=graphs_panel,
            config={"url": f"http://{host}:{graphs_port}{graphs_path}/"},
            require_admin=False,
        )
        paths.append(graphs_panel)
    except ValueError as err:
        _LOGGER.warning("Could not register graphs1090 panel %s: %s", graphs_panel, err)

    _PANELS_BY_ENTRY[entry.entry_id] = paths


def _unregister_panels(hass: HomeAssistant, entry: ConfigEntry) -> None:
    for path in _PANELS_BY_ENTRY.pop(entry.entry_id, []):
        try:
            async_remove_panel(hass, path)
        except (KeyError, ValueError):
            pass
