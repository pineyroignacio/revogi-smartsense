"""Local UDP protocol for Revogi Smart Sense gateways (read-only).

Protocol notes (from the RevogiHome app, local mode):
  * Discovery: ``00dv=all,<YYYY-MM-DD>,<HH:MM:SS>,<zone>;`` sent to UDP 8888
    (broadcast or unicast). ``zone`` = UTC offset in hours + 12.
    Reply: ``{"response":0,"data":{"sn":..,"name":..,"mac":..,"ver":..}}``
  * Sensor status: ``V3{"sn":"<SN>","cmd":88}`` to UDP 8888.
    Reply: ``V3{"response":517,"code":200,"data":{"alarm":..,"alarmstate":..,
    "light":..,"sensor":[{"id":"01000000","data":1235,"batt":1,"online":1},..]}}``
  * Sensor type = first byte (hex) of the sensor id.

This module has no Home Assistant dependencies so it can be tested standalone.
"""
from __future__ import annotations

import asyncio
import json
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

PORT = 8888
NO_EVENT = 0xFFFFFF  # 16777215: the sensor never reported an event

# type -> (key, kind). kind: "internal" = measured by the gateway itself,
# "event" = wireless sensor whose value is the epoch of its last event.
SENSOR_TYPES: dict[int, tuple[str, str]] = {
    0x01: ("temperature", "internal"),
    0x02: ("humidity", "internal"),
    0x03: ("illuminance", "internal"),
    0x04: ("noise", "internal"),
    0x05: ("air_quality", "internal"),
    0x06: ("pressure", "internal"),
    0x14: ("motion", "event"),
    0x15: ("door", "event"),
    0x17: ("smoke", "event"),
    0x18: ("flood", "event"),
    0x19: ("button", "event"),
    0x29: ("temperature_ext", "internal"),
    0x2A: ("humidity_ext", "internal"),
    0xE1: ("remote", "event"),
    0xE3: ("bulb", "other"),
    0xE4: ("siren", "other"),
}


def convert_internal(key: str, raw: int) -> float | int:
    """Convert a raw internal value to its real unit."""
    if key in ("temperature", "temperature_ext"):
        return round((raw - 1000) / 10, 1)
    if key in ("humidity", "humidity_ext", "pressure"):
        return round(raw / 10, 1)
    return raw


class RevogiError(Exception):
    """Communication error with the gateway."""


@dataclass
class DeviceInfo:
    host: str
    sn: str
    name: str = "SmartSensor"
    mac: str | None = None
    version: str | None = None


@dataclass
class Sensor:
    id: str
    type: int
    key: str
    kind: str
    raw: int
    battery: int | None
    online: int | None

    @property
    def value(self) -> Any:
        if self.kind == "internal":
            return convert_internal(self.key, self.raw)
        if self.kind == "event":
            if self.raw in (NO_EVENT, 0):
                return None
            return datetime.fromtimestamp(self.raw, timezone.utc)
        return self.raw


@dataclass
class Status:
    alarm: int | None = None
    alarm_state: int | None = None
    light: int | None = None
    sensors: dict[str, Sensor] = field(default_factory=dict)


def discovery_message(now: datetime | None = None) -> bytes:
    now = now or datetime.now().astimezone()
    offset = now.utcoffset()
    zone = int(offset.total_seconds() // 3600) + 12 if offset else 12
    return f"00dv=all,{now:%Y-%m-%d},{now:%H:%M:%S},{zone};".encode()


def status_message(sn: str) -> bytes:
    return f'V3{{"sn":"{sn}","cmd":88}}'.encode()


def _load(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8", "replace").strip()
    if text.startswith("V3"):
        text = text[2:]
    return json.loads(text)


def parse_discovery(payload: bytes, host: str) -> DeviceInfo | None:
    try:
        data = _load(payload).get("data") or {}
    except ValueError:
        return None
    if not data.get("sn"):
        return None
    return DeviceInfo(host=host, sn=data["sn"], name=data.get("name") or "SmartSensor",
                      mac=data.get("mac"), version=data.get("ver"))


def parse_status(payload: bytes) -> Status:
    try:
        msg = _load(payload)
    except ValueError as err:
        raise RevogiError(f"Invalid JSON from gateway: {err}") from err
    if msg.get("code") not in (None, 200) or "data" not in msg:
        raise RevogiError(f"Unexpected reply: {msg}")
    data = msg["data"]
    status = Status(alarm=data.get("alarm"), alarm_state=data.get("alarmstate"), light=data.get("light"))
    for item in data.get("sensor", []):
        sid = str(item.get("id", ""))
        try:
            typ = int(sid[:2], 16)
        except ValueError:
            continue
        key, kind = SENSOR_TYPES.get(typ, (f"type_{typ:02x}", "other"))
        status.sensors[sid] = Sensor(id=sid, type=typ, key=key, kind=kind, raw=int(item.get("data", 0)),
                                     battery=item.get("batt"), online=item.get("online"))
    return status


class _Collector(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.replies: list[tuple[bytes, str]] = []
        self.event = asyncio.Event()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.replies.append((data, addr[0]))
        self.event.set()


async def _exchange(target: str, payload: bytes, timeout: float, broadcast: bool = False,
                    wait_all: bool = False) -> list[tuple[bytes, str]]:
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", 0))
    transport, proto = await loop.create_datagram_endpoint(_Collector, sock=sock)
    try:
        transport.sendto(payload, (target, PORT))
        if wait_all:
            await asyncio.sleep(timeout)
        else:
            try:
                await asyncio.wait_for(proto.event.wait(), timeout)
            except asyncio.TimeoutError as err:
                raise RevogiError(f"No reply from {target}") from err
        return proto.replies
    finally:
        transport.close()


async def async_discover(timeout: float = 3.0, broadcast_address: str = "255.255.255.255") -> list[DeviceInfo]:
    """Find gateways on the local network."""
    found: dict[str, DeviceInfo] = {}
    for data, host in await _exchange(broadcast_address, discovery_message(), timeout, broadcast=True, wait_all=True):
        dev = parse_discovery(data, host)
        if dev:
            found[dev.sn] = dev
    return list(found.values())


async def async_identify(host: str, timeout: float = 4.0) -> DeviceInfo:
    """Ask a single gateway (by IP) for its identity."""
    for data, addr in await _exchange(host, discovery_message(), timeout):
        dev = parse_discovery(data, addr)
        if dev:
            return dev
    raise RevogiError(f"{host} did not answer as a Revogi gateway")


async def async_get_status(host: str, sn: str, timeout: float = 4.0, retries: int = 2) -> Status:
    """Read the current sensor status (read-only command 88)."""
    last: Exception | None = None
    for _ in range(retries + 1):
        try:
            replies = await _exchange(host, status_message(sn), timeout)
            return parse_status(replies[0][0])
        except (RevogiError, OSError) as err:
            last = err
            await asyncio.sleep(0.5)
    raise RevogiError(str(last))
