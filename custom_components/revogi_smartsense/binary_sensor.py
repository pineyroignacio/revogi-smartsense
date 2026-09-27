"""Binary sensors: recent activity of event sensors and alarm triggered."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time

from . import RevogiConfigEntry
from .const import CONF_EVENT_WINDOW, DEFAULT_EVENT_WINDOW
from .coordinator import RevogiCoordinator
from .entity import RevogiEntity

EVENT_CLASSES = {
    "motion": BinarySensorDeviceClass.MOTION,
    "door": BinarySensorDeviceClass.OPENING,
    "smoke": BinarySensorDeviceClass.SMOKE,
    "flood": BinarySensorDeviceClass.MOISTURE,
}


async def async_setup_entry(hass: HomeAssistant, entry: RevogiConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    window = entry.options.get(CONF_EVENT_WINDOW, DEFAULT_EVENT_WINDOW)
    known: set[str] = set()
    async_add_entities([AlarmTriggered(coordinator)])

    @callback
    def _add_new() -> None:
        new = []
        for sid, s in (coordinator.data.sensors if coordinator.data else {}).items():
            if sid not in known and s.key in EVENT_CLASSES:
                known.add(sid)
                new.append(RecentEvent(coordinator, sid, EVENT_CLASSES[s.key], window))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class RecentEvent(RevogiEntity, BinarySensorEntity):
    """On for `window` seconds after the sensor reports an event."""

    def __init__(self, coordinator: RevogiCoordinator, sid: str, device_class, window: int) -> None:
        super().__init__(coordinator, f"{sid}_recent", sid)
        self._attr_device_class = device_class
        self._attr_name = None  # use the device name (e.g. "Motion sensor 1406EB97")
        self._window = timedelta(seconds=window)
        self._unsub = None

    @property
    def is_on(self) -> bool | None:
        s = self.sensor
        if s is None:
            return None
        last = s.value
        return bool(last and datetime.now(timezone.utc) - last < self._window)

    @callback
    def _handle_coordinator_update(self) -> None:
        # schedule a refresh exactly when the window expires
        if self._unsub:
            self._unsub(); self._unsub = None
        s = self.sensor
        if s and s.value:
            off_at = s.value + self._window
            if off_at > datetime.now(timezone.utc):
                self._unsub = async_track_point_in_utc_time(self.hass, self._expire, off_at)
        super()._handle_coordinator_update()

    @callback
    def _expire(self, _now) -> None:
        self._unsub = None
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()


class AlarmTriggered(RevogiEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_translation_key = "alarm"

    def __init__(self, coordinator: RevogiCoordinator) -> None:
        super().__init__(coordinator, "alarm")

    @property
    def is_on(self) -> bool | None:
        d = self.coordinator.data
        return None if d is None or d.alarm is None else d.alarm != 0
