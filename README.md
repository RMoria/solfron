# Solar Frontier Inverter — Home Assistant integration

Custom Home Assistant integration to read out Solar Frontier SF-WR series inverters
(e.g. SF-WR-3000) over their built-in local web interface. Local polling only — no
cloud, no account required.

The SF-WR series are OEM Steca **StecaGrid coolcept** inverters; this integration
talks to that built-in web server (`gen.*.js` pages).

## Compatibility & testing

- ✅ **Tested and confirmed on the SF-WR-3000** (single-phase).
- 🟡 **Three-phase models (e.g. the SF-WR-5503x series): best-effort, untested.**
  The per-phase support is based on the field layout used by the older
  [ernestasga/ha-solarfrontier](https://github.com/ernestasga/ha-solarfrontier)
  integration, not verified against real three-phase hardware. Info and yield
  values should work; per-phase measurements are added automatically when the
  inverter reports them.
- Other single-phase SF-WR / StecaGrid coolcept models with the web server
  (1500, 2000, 2010, 2020, 2500, 3010, 3600, 4003, 4200, …) are likely to work
  as-is, but are unconfirmed.

**Using a different model? Please share your results** by opening an issue. If
something doesn't parse correctly, a full capture of the inverter's web pages
(for example an [HTTrack](https://www.httrack.com/) mirror of the `gen.*.js`
files) makes it easy to add support.

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

On **three-phase** inverters, per-phase sensors (`AC power/voltage/current/frequency L1–L3`)
are added automatically when the inverter reports them; single-phase inverters
don't get these.

### Energy dashboard

For the **Energy dashboard** (Solar production), use **`Yield today`**. It is a
`total_increasing` energy sensor in kWh with fine (3-decimal) resolution.

> ⚠️ **Do not use `Yield total` in the Energy dashboard.** Its source page
> reports lifetime yield in **MWh**, which is converted to kWh (×1000). That
> gives it a resolution of only ~1 kWh, so the small daily/hourly deltas the
> Energy dashboard derives from it would be too coarse/inaccurate. `Yield total`
> is fine as an informational sensor, just not as the dashboard's production
> source.

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

- **Update interval** (default 300 s / 5 min) — how often measurements/yields
  are polled. Five minutes is plenty for solar data; you can lower it (down to
  10 s) if you really want faster updates.
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

### Is NMAP required?

**No.** This integration does not use or depend on Nmap; it reads the kernel ARP
table (`/proc/net/arp`) directly, and normal polling keeps the inverter in that
table.

If you also run Home Assistant's **Nmap Tracker** integration, you may notice its
`device_tracker` entity attached to the same device here — that's just Home
Assistant merging entities that share the same **MAC address** (which this
integration sets on the device); it is not a dependency.

That said, Nmap Tracker (or any subnet-scanning tool) can *help* in one case: if
the inverter's IP changes via DHCP, Home Assistant no longer talks to the old IP,
so the new IP↔MAC pair only appears in the ARP table if something scans the
subnet. A periodic Nmap scan populates that entry, improving the chance the
automatic IP recovery finds the new address. Without it, recovery still works as
long as the new IP ends up in the ARP table by other means.

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
