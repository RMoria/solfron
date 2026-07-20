# Solar Frontier Inverter — Home Assistant integration

Custom Home Assistant integration to read out Solar Frontier SF-WR series inverters
(e.g. SF-WR-3000) over their built-in local web interface. Local polling only — no
cloud, no account required.

## Sensors

| Sensor | Unit | Device class |
|---|---|---|
| DC power | W | power |
| DC voltage | V | voltage |
| DC current | A | current |
| AC power | W | power |
| AC voltage | V | voltage |
| AC current | A | current |
| Frequency | Hz | frequency |
| Yield today | kWh | energy (total_increasing) |
| Yield this month | kWh | energy |
| Yield this year | kWh | energy |
| Yield total | kWh | energy (total_increasing) |
| Clock offset | s | diagnostic |

`Yield today` and `Yield total` can be used directly in the Home Assistant
**Energy dashboard** (Solar production).

### Clock offset (time-difference) sensor

The inverter can go into a fault state when its internal clock drifts too far
from real time (this notably happens around daylight-saving-time changes). The
**Clock offset** sensor reports the difference, in seconds, between the
inverter's clock and Home Assistant's local time (positive = inverter ahead).

The inverter's clock is read from its `gen.screenshot.bmp` LCD image, decoded
in pure Python (no OCR/Pillow dependency). The bottom-left of the screen
alternates every few seconds between the date and the IP address, so the daily
check retries briefly to also capture and verify the date. Attributes expose
`inverter_time`, `inverter_date`, `date_ok` and the `reported_ip`.

You can alert on drift with an automation, e.g. trigger when
`abs(states('sensor.<name>_clock_offset') | float) > 300`.

## Options

After adding the integration, use **Configure** on the integration card to set:

- **Update interval** (default 60 s) — how often measurements/yields are polled.
- **IP/MAC re-check interval** (default 3600 s) — how often the ARP table is
  checked to recover a changed IP address.
- **Clock check interval** (default 86400 s) — how often the inverter clock is
  compared to Home Assistant time.

## MAC-based IP tracking

The MAC address is the leading identifier. On setup the IP you enter is used to
resolve the inverter's MAC from the local ARP table, and the MAC is stored as
the config-entry identity. A background check (default hourly) verifies the IP
still maps to that MAC and recovers a new IP from the ARP table if it changed
(useful for non-static DHCP).

> **Note:** ARP-based lookup only works when Home Assistant can see the inverter
> in its ARP table — i.e. Home Assistant runs on the same network segment
> (host networking, as on Home Assistant OS). If the MAC cannot be resolved,
> the integration falls back to using the entered host as identifier and the
> re-check is skipped.

## Installation

### HACS (recommended)

1. In HACS, add this repository as a **custom repository** (category: *Integration*).
2. Search for **Solar Frontier Inverter** and install it.
3. Restart Home Assistant.

### Manual

Copy `custom_components/solfron` into your Home Assistant `config/custom_components/`
folder and restart Home Assistant.

## Configuration

Settings → Devices & services → **Add integration** → *Solar Frontier Inverter*, then
enter the IP address or hostname of the inverter (for example `192.168.1.50`).

## Requirements

Home Assistant 2025.11 or newer.

## Notes

The inverter serves several `gen.*.js` pages containing HTML tables; this integration
parses those. The yearly totals page reports values in MWh and is converted to kWh
internally so all yield sensors use the same unit.
