"""Sensors for Revogi Smart Sense."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass)
from homeassistant.const import (
    LIGHT_LUX, PERCENTAGE, UnitOfPressure, UnitOfSoundPressure, UnitOfTemperature, EntityCategory)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RevogiConfigEntry
from .coordinator import RevogiCoordinator
from .entity import RevogiEntity

MEASUREMENTS: dict[str, SensorEntityDescription] = {
    "temperature": SensorEntityDescription(key="temperature", translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1),
    "temperature_ext": SensorEntityDescription(key="temperature_ext", translation_key="temperature_ext",
        device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1),
    "humidity": SensorEntityDescription(key="humidity", translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY, native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1),
    "humidity_ext": SensorEntityDescription(key="humidity_ext", translation_key="humidity_ext",
        device_class=SensorDeviceClass.HUMIDITY, native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1),
    "illuminance": SensorEntityDescription(key="illuminance", translation_key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE, native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT),
    "noise": SensorEntityDescription(key="noise", translation_key="noise",
        device_class=SensorDeviceClass.SOUND_PRESSURE, native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT),
    "pressure": SensorEntityDescription(key="pressure", translation_key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE, native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1),
    "air_quality": SensorEntityDescription(key="air_quality", translation_key="air_quality",
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:air-filter"),
}


async def async_setup_entry(hass: HomeAssistant, entry: RevogiConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    async_add_entities([AlarmStateSensor(coordinator)])

    @callback
    def _add_new() -> None:
        new: list[SensorEntity] = []
        for sid, s in (coordinator.data.sensors if coordinator.data else {}).items():
            if sid in known:
                continue
            known.add(sid)
            if s.kind == "internal":
                desc = MEASUREMENTS.get(s.key)
                new.append(MeasurementSensor(coordinator, sid, desc) if desc else RawSensor(coordinator, sid))
            elif s.kind == "event":
                new += [LastEventSensor(coordinator, sid), BatterySensor(coordinator, sid)]
            else:
                new += [RawSensor(coordinator, sid), BatterySensor(coordinator, sid)]
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class MeasurementSensor(RevogiEntity, SensorEntity):
    def __init__(self, coordinator: RevogiCoordinator, sid: str, desc: SensorEntityDescription) -> None:
        self.entity_description = desc
        super().__init__(coordinator, desc.key, sid)

    @property
    def native_value(self):
        return self.sensor.value if self.sensor else None


class LastEventSensor(RevogiEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "last_event"

    def __init__(self, coordinator: RevogiCoordinator, sid: str) -> None:
        super().__init__(coordinator, f"{sid}_last_event", sid)

    @property
    def native_value(self):
        return self.sensor.value if self.sensor else None

    @property
    def extra_state_attributes(self):
        s = self.sensor
        return {"sensor_id": s.id, "raw": s.raw, "online": s.online} if s else None


class BatterySensor(RevogiEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: RevogiCoordinator, sid: str) -> None:
        super().__init__(coordinator, f"{sid}_battery", sid)

    @property
    def native_value(self):
        return self.sensor.battery if self.sensor else None


class RawSensor(RevogiEntity, SensorEntity):
    """Unknown sensor type: exposes the raw value so users can report it."""
    _attr_translation_key = "raw"

    def __init__(self, coordinator: RevogiCoordinator, sid: str) -> None:
        super().__init__(coordinator, f"{sid}_raw", sid)
        self._attr_translation_placeholders = {"sensor_id": sid}

    @property
    def native_value(self):
        return self.sensor.raw if self.sensor else None

    @property
    def extra_state_attributes(self):
        s = self.sensor
        return {"type": f"0x{s.type:02X}", "battery": s.battery, "online": s.online} if s else None


class AlarmStateSensor(RevogiEntity, SensorEntity):
    """Raw alarm mode reported by the gateway (meaning of values not confirmed yet)."""
    _attr_translation_key = "alarm_state"
    _attr_icon = "mdi:shield-home"

    def __init__(self, coordinator: RevogiCoordinator) -> None:
        super().__init__(coordinator, "alarm_state")

    @property
    def native_value(self):
        return self.coordinator.data.alarm_state if self.coordinator.data else None

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        return {"alarm": d.alarm, "light": d.light} if d else None
