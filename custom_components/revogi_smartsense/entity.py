"""Base entities for Revogi Smart Sense."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Sensor
from .const import CONF_MAC, DOMAIN, MANUFACTURER
from .coordinator import RevogiCoordinator

WIRELESS_MODELS = {
    "motion": "Motion sensor", "door": "Door/window sensor", "smoke": "Smoke detector",
    "flood": "Flood sensor", "button": "Smart button", "remote": "Key fob",
    "bulb": "Smart bulb", "siren": "Strobe siren",
}


def gateway_device(coordinator: RevogiCoordinator) -> DeviceInfo:
    entry = coordinator.config_entry
    info = DeviceInfo(identifiers={(DOMAIN, coordinator.sn)}, manufacturer=MANUFACTURER,
                      model="Smart Sense gateway", name=entry.title, serial_number=coordinator.sn)
    if mac := entry.data.get(CONF_MAC):
        info["connections"] = {("mac", mac.lower())}
    return info


class RevogiEntity(CoordinatorEntity[RevogiCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: RevogiCoordinator, unique_suffix: str, sensor_id: str | None = None) -> None:
        super().__init__(coordinator)
        self.sensor_id = sensor_id
        self._attr_unique_id = f"{coordinator.sn}_{unique_suffix}"
        sensor = self.sensor
        if sensor is not None and sensor.kind != "internal":
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{coordinator.sn}_{sensor.id}")},
                manufacturer=MANUFACTURER,
                model=WIRELESS_MODELS.get(sensor.key, f"Sensor type 0x{sensor.type:02X}"),
                name=f"{WIRELESS_MODELS.get(sensor.key, 'Sensor')} {sensor.id}",
                via_device=(DOMAIN, coordinator.sn),
            )
        else:
            self._attr_device_info = gateway_device(coordinator)

    @property
    def sensor(self) -> Sensor | None:
        if self.sensor_id is None or self.coordinator.data is None:
            return None
        return self.coordinator.data.sensors.get(self.sensor_id)

    @property
    def available(self) -> bool:
        return super().available and (self.sensor_id is None or self.sensor is not None)
