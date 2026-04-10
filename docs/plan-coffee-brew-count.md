# Plan: Coffee Brew Counter for DPX Stack

Track daily coffee consumption by decoding Nespresso Vertuo BLE broadcasts and publishing brew events to the metrics pipeline.

**TL;DR:** Add a Nespresso decoder to ble_decoder.py, monitor machine state transitions (IDLE → BREWING → IDLE) from manufacturer data, publish brew events when cycles complete, and visualize daily/weekly coffee stats in Grafana.

**Steps**

1. Add Nespresso Vertuo decoder to [scripts/ble_decoder.py](scripts/ble_decoder.py)
   - Add manufacturer ID 9474 (Nespresso) to decoder registry
   - Implement `decode_nespresso_vertuo()` function to parse 6-byte payload `b'\x00\x89\x00\x00\x00\x00'`
   - Extract status code (bytes 1-2: `0x89` = IDLE/READY, need to capture BREWING status during live test)
   - Handle service UUID detection: `06aa1910-f22a-11e3-9daa-0002a5d5c51b` (Vertuo Next/Pop family)

2. Implement brew event detection via state machine (*depends on step 1*)
   - Track last known machine state per MAC address in memory dict
   - Detect state transitions: IDLE → BREWING → IDLE = one complete brew cycle
   - Publish `brew_event=1` to MQTT when cycle completes (BREWING returns to IDLE)
   - Topic format: `{showsite}/dpx_ops_decoder/{source}/{room}/nespresso_{mac}/brew_event`
   - Include timestamp and duration metrics

3. Add device override for Nespresso machine (*parallel with step 1-2*)
   - Add MAC `CC:DB:A7:A6:6D:5A` to [telegraf/conf.d/device-overrides.json](telegraf/conf.d/device-overrides.json)
   - Set name: `nespresso_vertuo`, room: `office` (or actual location)
   - Set SKU: `Vertuo_Next` for identification
   - Run `iot ble-restart` to reload config

4. Reverse engineer BREWING status code (*parallel with step 1, requires manual testing*)
   - Monitor `iot ble-logs` while brewing a coffee
   - Capture manufacturer data hex values during brew cycle
   - Identify non-IDLE status code (likely `0x??` in bytes 1-2)
   - Update decoder with BREWING status constant

5. Configure Telegraf to ingest brew events (*depends on step 2*)
   - Existing MQTT input already subscribes to `demo_showsite/#`
   - Verify regex processor handles new topic structure with brew_event metric
   - Test that `brew_event` metric arrives in InfluxDB bucket `showsite_sensors`
   - Optional: Add counter for total lifetime brews

6. Create Grafana dashboard for coffee stats (*depends on step 5*)
   - **Panel 1**: Stat panel showing daily brew count (InfluxDB query: `sum(brew_event)` over 24h)
   - **Panel 2**: Time series graph showing hourly brew rate over past 7 days
   - **Panel 3**: Stat panel for total brews this week
   - **Panel 4**: Heat map showing brew times (hour of day × day of week) for caffeine pattern analysis
   - Save dashboard as `Coffee Consumption Tracker`

7. Update roadmap documentation (*depends on step 6*)
   - Add **Phase 8: IoT Lifestyle Tracking** section to [docs/ROADMAP.md](docs/ROADMAP.md) after Phase 7
   - Document Nespresso protocol integration and state machine approach
   - Link to reverse engineering source: [renaudallard/homeassistant_nespresso_smart](https://github.com/renaudallard/homeassistant_nespresso_smart)
   - Mark coffee tracking as complete when dashboard is live

**Relevant files**

- [scripts/ble_decoder.py](scripts/ble_decoder.py#L50) — Update DECODERS dict with Nespresso entry, add `decode_nespresso_vertuo()` function after Govee decoders (~line 190), implement state tracking in `on_message()` callback (~line 240)
- [telegraf/conf.d/device-overrides.json](telegraf/conf.d/device-overrides.json) — Add device entry for MAC `CC:DB:A7:A6:6D:5A`
- [docs/ROADMAP.md](docs/ROADMAP.md#L420) — Add Phase 8: IoT Lifestyle Tracking section
- `grafana/provisioning/dashboards/` — Create `coffee-tracker.json` dashboard

**Verification**

1. Run `iot ble-logs` and confirm Nespresso advertisements are being received (MAC `CC:DB:A7:A6:6D:5A` with manufacturer ID 9474)
2. Brew a coffee while watching logs, capture BREWING status code from manufacturer data hex output
3. Test brew event detection: verify `brew_event=1` is published to MQTT after brew completes
4. Query InfluxDB: `influx query 'from(bucket:"showsite_sensors") |> range(start:-1h) |> filter(fn:(r) => r._field == "brew_event")'`
5. Open Grafana dashboard, verify daily count increments after each brew
6. Monitor for false positives (heat-up cycles, descaling, errors counted as brews)

**Decisions**

- **Advertisement-only monitoring**: The capsule counter is NOT in manufacturer data—it requires authenticated BLE connection. Instead, we track brew events by detecting state transitions from IDLE (0x89) → BREWING (status TBD) → IDLE in the manufacturer data status bytes.
- **State machine approach**: 
  - Status `0x89` (137 decimal) = IDLE/READY (confirmed from protocol docs)
  - Status `0x??` = BREWING (requires live capture to identify)
  - Count each BREWING → IDLE transition as one brew event
  - Ignore state changes that don't complete the full cycle
- **No BLE connection/auth**: Passive monitoring only—no pairing with machine, no reading of characteristics, no control commands. Advertisement data is sufficient for brew counting.
- **Topic structure**: Reuse existing `{showsite}/{node}/{source}/{room}/{device}/{mac}/{metric}` pattern from ble_decoder.py for consistency
- **Excluded from MVP scope**: 
  - Capsule type detection (requires connection)
  - Brew recipe/volume details (not in advertisements)
  - Home Assistant integration (outside DPX Stack)
  - Descaling/cleaning alerts (future phase)
  - Historical backfill from capsule counter (requires connection)

**Further Considerations**

1. **BREWING status code discovery** — Critical for accurate detection. Options:
   - Option A: Monitor logs during brew and capture hex values (recommended for accuracy)
   - Option B: Count any non-IDLE status >30 seconds as brewing (simpler but less precise)
   - Option C: Use protocol docs from [renaudallard repo](https://github.com/renaudallard/homeassistant_nespresso_smart/tree/master/docs) if BREWING status is documented
   - **Recommendation**: Start with Option A (live capture), document the status code in decoder comments

2. **False positive prevention** — How to avoid counting heat-up, descaling, errors as brews?
   - Require minimum time in non-IDLE state (e.g., 30 seconds) before counting
   - Require return to IDLE state within reasonable timeframe (e.g., <5 minutes)
   - Track consecutive state changes to filter noise
   - **Recommendation**: Start simple, add filters if false positives occur in production

3. **Multi-device support** — Handle multiple Nespresso machines?
   - State tracking dict should be keyed by MAC address (already planned)
   - Device overrides support multiple entries with different names/rooms
   - Each machine gets own Grafana panel or use variables to select device
   - **Recommendation**: Design for multi-device from start, test with single machine
