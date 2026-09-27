"""Config flow: auto-discovery on the LAN or manual IP."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import callback

from .api import DeviceInfo, RevogiError, async_discover, async_get_status, async_identify
from .const import (CONF_EVENT_WINDOW, CONF_MAC, CONF_SCAN_INTERVAL, CONF_SN, DEFAULT_EVENT_WINDOW,
                    DEFAULT_SCAN_INTERVAL, DOMAIN)

MANUAL = "manual"


class RevogiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._found: dict[str, DeviceInfo] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        try:
            devices = await async_discover()
        except OSError:
            devices = []
        configured = self._async_current_ids()
        self._found = {d.sn: d for d in devices if d.sn not in configured}
        if not self._found:
            return await self.async_step_manual()
        return await self.async_step_pick()

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if user_input["device"] == MANUAL:
                return await self.async_step_manual()
            return await self._async_create(self._found[user_input["device"]])
        options = {sn: f"{d.name} — {d.host} ({sn})" for sn, d in self._found.items()}
        options[MANUAL] = "Enter IP address manually / Ingresar IP manualmente"
        return self.async_show_form(step_id="pick", data_schema=vol.Schema({vol.Required("device"): vol.In(options)}))

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                dev = await async_identify(user_input[CONF_HOST].strip())
            except (RevogiError, OSError):
                errors["base"] = "cannot_connect"
            else:
                return await self._async_create(dev)
        return self.async_show_form(step_id="manual", data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
                                    errors=errors)

    async def _async_create(self, dev: DeviceInfo) -> ConfigFlowResult:
        await self.async_set_unique_id(dev.sn)
        self._abort_if_unique_id_configured(updates={CONF_HOST: dev.host})
        try:
            await async_get_status(dev.host, dev.sn)
        except RevogiError:
            return self.async_abort(reason="not_supported")
        return self.async_create_entry(
            title=f"Revogi {dev.name}",
            data={CONF_HOST: dev.host, CONF_SN: dev.sn, CONF_MAC: dev.mac, "version": dev.version})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RevogiOptionsFlow()


class RevogiOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        o = self.config_entry.options
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=o.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
                vol.All(vol.Coerce(int), vol.Range(min=3, max=300)),
            vol.Required(CONF_EVENT_WINDOW, default=o.get(CONF_EVENT_WINDOW, DEFAULT_EVENT_WINDOW)):
                vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
        }))
