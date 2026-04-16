"""Config flow for the SkyFeeder integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ENABLE_PANELS,
    CONF_ENABLE_TRACKERS,
    CONF_EXCLUDE_CATEGORIES,
    CONF_EXCLUDE_TYPES,
    CONF_FILTER_CATEGORIES,
    CONF_FILTER_TYPES,
    CONF_GRAPHS1090_PATH,
    CONF_GRAPHS1090_PORT,
    CONF_HOST,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MAX_ALTITUDE,
    CONF_MAX_TRACKERS,
    CONF_MIN_ALTITUDE,
    CONF_NAME,
    CONF_PORT,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_TAR1090_PATH,
    DEFAULT_ENABLE_PANELS,
    DEFAULT_ENABLE_TRACKERS,
    DEFAULT_FILTER,
    DEFAULT_GRAPHS1090_PATH,
    DEFAULT_GRAPHS1090_PORT,
    DEFAULT_MAX_ALTITUDE,
    DEFAULT_MAX_TRACKERS,
    DEFAULT_MIN_ALTITUDE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TAR1090_PATH,
    DOMAIN,
)
from .coordinator import SkyFeederCoordinator


def _user_schema(hass_lat: float, hass_lon: float, defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_LATITUDE, default=d.get(CONF_LATITUDE, hass_lat)): vol.Coerce(float),
            vol.Required(CONF_LONGITUDE, default=d.get(CONF_LONGITUDE, hass_lon)): vol.Coerce(float),
            vol.Required(CONF_RADIUS, default=d.get(CONF_RADIUS, DEFAULT_RADIUS_KM)): vol.All(
                vol.Coerce(float), vol.Range(min=1, max=500)
            ),
            vol.Required(
                CONF_SCAN_INTERVAL, default=d.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
            vol.Optional(
                CONF_MIN_ALTITUDE, default=d.get(CONF_MIN_ALTITUDE, DEFAULT_MIN_ALTITUDE)
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60000)),
            vol.Optional(
                CONF_MAX_ALTITUDE, default=d.get(CONF_MAX_ALTITUDE, DEFAULT_MAX_ALTITUDE)
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100000)),
            # ---- Aircraft type filtering -----------------------------------
            vol.Optional(
                CONF_FILTER_CATEGORIES, default=d.get(CONF_FILTER_CATEGORIES, DEFAULT_FILTER)
            ): str,
            vol.Optional(
                CONF_FILTER_TYPES, default=d.get(CONF_FILTER_TYPES, DEFAULT_FILTER)
            ): str,
            vol.Optional(
                CONF_EXCLUDE_CATEGORIES, default=d.get(CONF_EXCLUDE_CATEGORIES, DEFAULT_FILTER)
            ): str,
            vol.Optional(
                CONF_EXCLUDE_TYPES, default=d.get(CONF_EXCLUDE_TYPES, DEFAULT_FILTER)
            ): str,
            # ---- Device trackers -------------------------------------------
            vol.Optional(
                CONF_ENABLE_TRACKERS, default=d.get(CONF_ENABLE_TRACKERS, DEFAULT_ENABLE_TRACKERS)
            ): bool,
            vol.Optional(
                CONF_MAX_TRACKERS, default=d.get(CONF_MAX_TRACKERS, DEFAULT_MAX_TRACKERS)
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=200)),
            # ---- Sidebar panels (replaces the legacy App) ------------------
            vol.Optional(
                CONF_ENABLE_PANELS, default=d.get(CONF_ENABLE_PANELS, DEFAULT_ENABLE_PANELS)
            ): bool,
            vol.Optional(
                CONF_TAR1090_PATH, default=d.get(CONF_TAR1090_PATH, DEFAULT_TAR1090_PATH)
            ): str,
            vol.Optional(
                CONF_GRAPHS1090_PORT, default=d.get(CONF_GRAPHS1090_PORT, DEFAULT_GRAPHS1090_PORT)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(
                CONF_GRAPHS1090_PATH, default=d.get(CONF_GRAPHS1090_PATH, DEFAULT_GRAPHS1090_PATH)
            ): str,
        }
    )


class SkyFeederConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a SkyFeeder config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Single-step user form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()

            coord = SkyFeederCoordinator(self.hass, user_input)
            try:
                ok = await coord.async_probe()
            except Exception:  # noqa: BLE001
                ok = False
            if not ok:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(
                self.hass.config.latitude or 0.0,
                self.hass.config.longitude or 0.0,
                user_input,
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SkyFeederOptionsFlow()


class SkyFeederOptionsFlow(OptionsFlow):
    """Options flow - lets the user retune radius / scan interval / filters."""

    # Note: do NOT define __init__ and do NOT assign self.config_entry.
    # Since Home Assistant Core 2024.12 `config_entry` is a read-only property
    # on OptionsFlow that HA populates itself; assigning it raises and makes
    # the Configure cog return HTTP 500 in the frontend.

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        merged = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_user_schema(
                self.hass.config.latitude or 0.0,
                self.hass.config.longitude or 0.0,
                merged,
            ),
        )
