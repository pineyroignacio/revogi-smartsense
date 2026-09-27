"""Diagnostics (sensitive fields redacted)."""
from __future__ import annotations

from dataclasses import asdict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import RevogiConfigEntry

TO_REDACT = {"mac", "sn", "host"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: RevogiConfigEntry) -> dict:
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "status": asdict(data) if data else None,
    }
