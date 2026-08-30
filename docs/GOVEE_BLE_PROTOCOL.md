# Govee BLE Protocol Reference

Consolidated, ground-truth notes on decoding Govee thermo-hygrometer BLE advertisements, from a
2026-08-30 debugging session on a companion project ([`DPX_CYD_TEMP`](https://github.com/dubpixel/DPX_CYD_TEMP)).
That project hit, and root-caused, the same class of decode/scan bugs this repo's
`scripts/ble_decoder.py` has -- worth reading before touching Govee BLE code here again.

Everything marked **CONFIRMED** below was checked against real captured bytes: either a phone
BLE scanner (nRF Connect) reading a named, physical unit directly, or a live decode on real
firmware cross-checked against another sensor in the same room at the same time. Nothing here is
copied from a third-party GitHub repo without a real capture backing it up -- that's the mistake
this doc exists to stop repeating (see "How we got this wrong twice" below).

## Manufacturer data layout, by model

All multi-byte fields are **little-endian** unless noted. Byte 0 is the first byte of BLE
manufacturer-specific data, i.e. it INCLUDES the 2-byte company ID (`88 EC` on the wire = company
ID `0xEC88` in host byte order). If your capture tool or library strips the company ID before
handing you the payload, shift every offset below down by 2.

### H5075 / H5072 -- company ID `0xEC88`

**CONFIRMED.** Packed 3-byte big-endian encoding, not simple little-endian fields:

```
Byte 0-1: Manufacturer ID (0xEC88, little-endian on the wire)
Byte 2:   flags (unused by the decoder)
Byte 3-5: packed temp+humidity, 24-bit BIG-endian integer
          bit 23:    sign bit for temperature (1 = negative)
          bits 22-0: magnitude
          magnitude / 1000       -> whole+tenths of degrees C
          magnitude % 1000       -> tenths of a percent RH
Byte 6:   battery percent (0-100)
```

Example, live capture: `88 EC 00 03 75 C2 3C 00` → bytes 3-5 = `03 75 C2` → 24-bit BE magnitude
`0x0375C2` = 226,754 → `226754 / 1000 = 226` → 22.6°C, `226754 % 1000 = 754` → 75.4%RH. Matches
the real observed reading from this exact payload (22.6°C / 75.4%RH) exactly. The important,
repeatedly-confirmed facts: it's one packed 24-bit BE integer at bytes 3-5, not two separate LE
fields, and battery is a single byte at offset 6.

**This repo's `decode_h5075()` in `scripts/ble_decoder.py` uses a totally different, explicitly
labeled "empirical approximation (TBD)" formula** (`temp_c = (raw+16)/40`, `humidity =
(b[5]-135)/2.5`, treating bytes 3-4 as a plain 16-bit BE pair rather than part of a 3-byte packed
value). That formula was likely reverse-engineered from limited samples before the packed-integer
structure was understood elsewhere. Recommend replacing it with the packed-integer decode above --
it's the one used by Theengs, Home Assistant's `Bluetooth-Devices/govee-ble`, and now confirmed
independently via phone capture and repeated live hardware decodes at `dpx_cyd_temp`.

### H5074 -- company ID `0xEC88`

**CONFIRMED**, live capture 2026-08-30, unit `Govee_H5074_4E6F`:

```
Byte 0-1: Manufacturer ID (0xEC88, LE)
Byte 2:   flags (unused)
Byte 3-4: temperature, int16 LE, divide by 100, signed
Byte 5-6: humidity, uint16 LE, divide by 100
Byte 7:   battery percent
```

Raw: `88 EC 00 B1 08 78 1C 64 02` → temp = `0x08B1`/100 = 22.25°C, humidity = `0x1C78`/100 =
72.88%RH, battery = `0x64` = 100%. Matched an H5075 in the same room at the same time (22.6-22.8°C
/ 75.x%RH) closely enough to trust, though not identically -- different physical placement.

Separate little-endian fields, NOT the H5075's packed 24-bit scheme, despite sharing a company ID.
This is the single most common source of bugs in Govee decoders: **company ID does not identify
the model.**

### H5051 / H5052 / H5071 -- company ID `0xEC88`

**CONFIRMED**, live capture 2026-08-30, unit `Govee_H5051_405D`, plus a second physical unit
decoded live on real firmware.

**Same exact layout as the H5074 above**, just in an 11-byte buffer instead of 9 (3 extra unused
trailing bytes):

```
Byte 0-1: Manufacturer ID (0xEC88, LE)
Byte 2:   flags (unused)
Byte 3-4: temperature, int16 LE, /100, signed
Byte 5-6: humidity, uint16 LE, /100          <-- NOT a single byte, see below
Byte 7:   battery percent
Byte 8-10: unused
```

Raw: `88 EC 00 B3 07 73 1C 00 D8 01 01` → temp = `0x07B3`/100 = 19.71°C, humidity =
`0x1C73`/100 = 72.83%RH. Confirmed live from two separate physical units: one at 22.7°C/72.1%RH,
battery 100%; another at 20.0°C/72.6%RH, battery 0% (weaker RSSI, plausibly a real low-battery
unit or just further away -- not independently confirmed which).

**This repo's `decode_h5051()` in `scripts/ble_decoder.py` has the humidity field wrong**:

```python
def decode_h5051(b):
    temp_raw = b[3] | (b[4] << 8)
    return {
        "temp_f": ...,
        "humidity": b[5] / 10.0,   # <-- WRONG: single byte, caps at 25.5%
        "battery": b[7]
    }
```

Temperature offset and formula are right. Humidity is wrong: a single byte divided by 10 caps out
at 25.5% RH, which is too low for a room sensor and doesn't match reality. Against the real
capture above, this formula computes **11.5% humidity** where the correct decode (and two other
sensors in the same room) all read ~72-73%. Fix: read bytes 5-6 as a little-endian uint16 and
divide by 100, exactly like the H5074.

*(Side note on how this doc's source project got it wrong too: `dpx_cyd_temp` initially copied
this exact single-byte-humidity formula from this repo's `ble_decoder.py`, assuming a research
project with a physically-present unit was more authoritative than a third-party GitHub source.
It wasn't -- this formula was itself never checked against a live H5051 capture before today. Both
projects were carrying the same unverified guess. See "How we got this wrong twice" below.)*

### H5100 / H5101 / H5102 / H5104 / H5105 / H5174 / H5177 / H5108 -- company ID `0x0001`

**Not yet confirmed against real hardware** (no unit available at `dpx_cyd_temp` either). Per
Theengs' `H5102_json.h`: same packed-vs-separate-field question doesn't apply here -- it uses the
H5075's packed 24-bit big-endian scheme, just shifted one byte later:

```
Byte 0-1: Manufacturer ID (0x0001, LE) -- registered to someone else in the Bluetooth SIG list;
          Govee uses it anyway
Byte 2-3: flags/unused
Byte 4-6: packed temp+humidity, same 24-bit BE scheme as H5075
Byte 7:   battery
```

Treat this whole family as best-effort until an actual unit is captured.

## The scan-mode gotcha: active vs. passive

**This is probably the single most valuable fact in this document if you ever run your own BLE
gateway code (ESP32, Theengs, or otherwise) against Govee sensors.**

The H5051 and H5074 put their manufacturer data in the **`SCAN_RSP`** packet, not the primary
`ADV_IND` advertisement. The H5075 puts its data in the primary `ADV_IND`. A **passive** BLE scan
(no scan request sent) only ever sees `ADV_IND` -- it will NEVER see manufacturer data from an
H5051 or H5074, no matter how long it scans, how tight its duty cycle is, or how much debug
logging is added. It looks exactly like "not broadcasting," "out of range," or -- if you don't
know to check for it -- like a hardware limitation.

`dpx_cyd_temp` chased this for a full debugging session, at one point wrongly concluding it was a
BLE-5-extended-advertising hardware ceiling on the classic ESP32 (a real, separate fact about that
chip -- see below -- that happened not to be the actual cause here). The real fix was one line:
switch the scan to **active** (`setActiveScan(true)` in NimBLE terms), which requests a scan
response from every advertiser it sees. That alone made both models decode correctly and
immediately, with a phone (which scans actively by default) having caught them in about 2 seconds
the whole time.

If this repo's own ESP32 gateways or Theengs config are ever missing H5051/H5074 readings, check
active-vs-passive scan mode first, before anything else.

### A real, separate fact about classic ESP32 hardware (not the cause here, but worth knowing)

The original ESP32 (WROOM-32/WROVER) has a Bluetooth 4.2 controller and genuinely cannot receive
BLE 5 **extended advertising** -- NimBLE's own headers refuse to even compile that mode for this
chip (`#error Extended advertising is not supported on ESP32.`). ESP32-S3, C3, C6, and H2 all have
BLE 5 controllers and can. This is real, and matters if some future device genuinely does use
extended advertising -- but don't reach for it as an explanation until active-vs-passive scan mode
has been ruled out first. It's the more exotic and less likely cause of the two.

## How we got this wrong twice

Worth internalizing for next time: `dpx_cyd_temp` treated `bluetooth-devices/govee-ble` (a GitHub
project) as ground truth for the H5051 in one version, then treated this repo's `ble_decoder.py`
as ground truth in the next version, then this doc treats a phone-captured live packet as ground
truth. Two "authoritative-looking" sources were both wrong on the same field (humidity scaling)
in the same way, likely because one was copied from the other, or both copied a third common
source, without either ever being checked against a real device. **A second source agreeing with
a first source is not independent confirmation if neither has touched real hardware.** The bar
that actually cleared this was a phone scanner reading a real, physically-present, named unit.

## Sources

- Real captures: phone BLE scanner (nRF Connect), 2026-08-30, three physical units side by side
  (H5051 x2, H5074, H5075)
- `dpx_cyd_temp` repo: `firmware/platformio/govee-cyd-pio/lib/govee_decode/govee_decode.c` (the
  decoder implementation this doc's confirmed formats are drawn from) and
  `firmware/platformio/govee-cyd-pio/src/ble_govee.cpp` (the active-scan fix)
- This repo: `scripts/ble_decoder.py` (the decoder with the humidity bug noted above)
- Theengs Decoder (`H5074_json.h`, `H5102_json.h`) and `Bluetooth-Devices/govee-ble` (Home
  Assistant's own Govee integration) for the H5100 family layout, unconfirmed against hardware
