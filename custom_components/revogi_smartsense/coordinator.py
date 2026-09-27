"""Polling coordinator for Revogi Smart Sense."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RevogiError, Status, async_discover, async_get_status
from .const import CONF_SCAN_INTERVAL, CONF_SN, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class RevogiCoordinator(DataUpdateCoordinator[Status]):
    """Reads the gateway every few seconds."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=interval),
                         config_entry=entry)
        self.sn: str = entry.data[CONF_SN]
        self._failures = 0

    @property
    def host(self) -> str:
        return self.config_entry.data[CONF_HOST]

    async def _async_update_data(self) -> Status:
        try:
            status = await async_get_status(self.host, self.sn)
        except RevogiError as err:
            self._failures += 1
            if self._failures % 3 == 0:
                await self._async_rediscover()
            raise UpdateFailed(f"Gateway {self.host} not responding: {err}") from err
        self._failures = 0
        return status

    async def _async_rediscover(self) -> None:
        """The gateway may have a new IP (DHCP): look for its serial number."""
        try:
            devices = await async_discover()
        except OSError:
            return
        for dev in devices:
            if dev.sn == self.sn and dev.host != self.host:
                _LOGGER.info("Revogi %s moved from %s to %s", self.sn, self.host, dev.host)
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data, CONF_HOST: dev.host})
