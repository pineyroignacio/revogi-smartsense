# Revogi Smart Sense (local) for Home Assistant

Unofficial, **cloud-free** integration for the **Revogi Smart Sense** alarm/sensor kit
(gateway SGW001 "SmartSensor"). It talks to the gateway directly on your LAN using the same
local protocol as the RevogiHome app's *Local Mode*. No Revogi account needed.

> Not affiliated with or endorsed by Revogi. Use at your own risk.

*[Español más abajo](#español)*

## What you get
From the gateway itself:
- Temperature, humidity, illuminance (lux), noise (dB), atmospheric pressure (mbar)
- Alarm mode (raw value) and *Alarm triggered* binary sensor

For every paired wireless sensor (each one shows up as its own device):
- **Last event** timestamp and **battery**
- Motion / door / smoke / flood sensors also get a binary sensor that turns **on** for a
  configurable time (default 30 s) after each event — use it in automations.
- Unknown sensor types are exposed with their raw value (please report them, see below).

The integration is **read-only**: it never arms/disarms or changes anything on the gateway.

## Installation (HACS)
1. HACS → ⋮ → **Custom repositories** → add `https://github.com/pineyroignacio/revogi-smartsense`, category **Integration**.
2. Install **Revogi Smart Sense (local)** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Revogi Smart Sense**.
   Gateways on the same network are found automatically; otherwise enter the gateway IP.

Manual install: copy `custom_components/revogi_smartsense` into your `config/custom_components/` and restart.

**Requirements:** Home Assistant and the gateway must be on the same network/VLAN for
auto-discovery (UDP broadcast, port 8888). With a manual IP it also works across routed networks
as long as UDP 8888 is allowed. Give the gateway a DHCP reservation; if its IP changes anyway the
integration finds it again by serial number.

**Options:** polling interval (default 10 s) and how long event binary sensors stay on.

## Tested devices
| Device | Firmware | Status |
|---|---|---|
| Smart Sense gateway SGW001 (SmartSensor) | 6.06 | ✅ temperature, humidity, lux, noise, pressure, button, door, motion |

Have another model or firmware? Open an issue with **Settings → Devices → your gateway → ⋮ →
Download diagnostics** attached (serial, MAC and IP are redacted automatically).

## Protocol notes
UDP port 8888, plain text JSON:
- Discovery: `00dv=all,YYYY-MM-DD,HH:MM:SS,<utc_offset_hours+12>;` → `{"response":0,"data":{"sn","name","mac","ver",…}}`
- Status: `V3{"sn":"<SN>","cmd":88}` → `V3{"response":517,"code":200,"data":{"alarm","alarmstate","sensor":[{"id","data","batt","online"}]}}`
- Sensor type = first byte of `id`: `01` temp `(v-1000)/10` °C · `02` humidity `v/10` % · `03` lux ·
  `04` dB · `05` air quality · `06` pressure `v/10` mbar · `14` motion · `15` door · `17` smoke ·
  `18` flood · `19` button · `E1` key fob · `E4` siren. For event sensors `data` is the Unix time of
  the last event (`16777215` = never).

## Roadmap / help wanted
- Map `alarmstate` values to armed/disarmed/home (needs captures of the app while arming).
- Alarm control panel (arm/disarm) — needs the local command, contributions welcome.

---

## Español

Integración **no oficial y sin nube** para el kit de alarma **Revogi Smart Sense** (gateway
SGW001). Habla directo con el gateway en tu red local, con el mismo protocolo que usa el
*Modo Local* de la app RevogiHome. No necesita cuenta de Revogi y **solo lee**: nunca arma,
desarma ni cambia nada.

**Instalación:** HACS → ⋮ → *Repositorios personalizados* → `https://github.com/pineyroignacio/revogi-smartsense`
(categoría *Integración*) → instalar → reiniciar → *Configuración → Dispositivos y servicios →
Agregar integración → Revogi Smart Sense*. Si el gateway está en la misma red lo encuentra solo;
si no, pedís la IP.

**Qué trae:** temperatura, humedad, luz, ruido y presión del gateway; modo de alarma y "alarma
disparada"; y por cada sensor inalámbrico, su último evento, batería y (movimiento, puerta, humo,
inundación) un sensor binario que se activa unos segundos tras cada evento, ideal para automatizaciones.

¿Tenés otro modelo? Abrí un *issue* adjuntando los diagnósticos (se ocultan serie, MAC e IP).
