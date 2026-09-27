"""Revogi Smart Sense (local, unofficial) integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import RevogiCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type RevogiConfigEntry = ConfigEntry[RevogiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RevogiConfigEntry) -> bool:
    coordinator = RevogiCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: RevogiConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RevogiConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
