#!/usr/bin/env python3
# ================================================================================
# PYTHON SERVICE - WLED MQTT BRIDGE
# ================================================================================
# Maps MQTT sensor data to WLED ropelight pixel zones via WLED's native MQTT API.
# Tent temperature → last 25px of 100px ropelight (pixels 75–99).
# Zone system is extensible — add future zones in config.yaml without code changes.
# ================================================================================
# PROJECT: dpx-showsite-ops
# ================================================================================
#
# File:         services/wled-bridge/app.py
# Purpose:      Subscribe to MQTT sensor topics, map values to RGB colors,
#               publish segment control commands to WLED via MQTT.
# Dependencies: paho-mqtt, pyyaml
#
# ================================================================================

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Timer

import paho.mqtt.client as mqtt
import yaml

# ============================================================================
# Version
# ============================================================================

VERSION_FILE = Path(__file__).parent.parent.parent / "VERSION"
try:
    VERSION = VERSION_FILE.read_text().strip()
except Exception:
    VERSION = "unknown"

# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

BROKER = os.getenv("BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
SHOWSITE = os.getenv("SHOWSITE_NAME", "demo_showsite")
WLED_DEVICE_TOPIC = os.getenv("WLED_DEVICE_TOPIC", "wled")  # full MQTT base topic, e.g. coachella_26/wled-rambo

CONFIG_FILE = Path(__file__).parent / "config.yaml"


def expand_env(value):
    """Recursively expand ${VAR} placeholders in config values."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env(i) for i in value]
    return value


def load_config():
    """Load and validate config.yaml, expanding env vars."""
    if not CONFIG_FILE.exists():
        log.error(f"Config file not found: {CONFIG_FILE}")
        sys.exit(1)

    with open(CONFIG_FILE) as f:
        raw = yaml.safe_load(f)

    config = expand_env(raw)
    return config


# ============================================================================
# Color Interpolation
# ============================================================================

def interpolate_color(temp_f: float, gradient: list) -> list:
    """
    Map a temperature value to an RGB color using linear interpolation
    between gradient stops.

    Args:
        temp_f:   Temperature in Fahrenheit
        gradient: List of dicts with keys 'temp_f' and 'rgb' ([R, G, B]),
                  sorted ascending by temp_f.

    Returns:
        [R, G, B] integers 0–255
    """
    if not gradient:
        return [128, 128, 128]

    # Clamp to edges
    if temp_f <= gradient[0]["temp_f"]:
        return list(gradient[0]["rgb"])
    if temp_f >= gradient[-1]["temp_f"]:
        return list(gradient[-1]["rgb"])

    # Find surrounding stops and interpolate
    for i in range(len(gradient) - 1):
        lo = gradient[i]
        hi = gradient[i + 1]
        if lo["temp_f"] <= temp_f <= hi["temp_f"]:
            t = (temp_f - lo["temp_f"]) / (hi["temp_f"] - lo["temp_f"])
            r = round(lo["rgb"][0] + t * (hi["rgb"][0] - lo["rgb"][0]))
            g = round(lo["rgb"][1] + t * (hi["rgb"][1] - lo["rgb"][1]))
            b = round(lo["rgb"][2] + t * (hi["rgb"][2] - lo["rgb"][2]))
            return [r, g, b]

    return [128, 128, 128]


# ============================================================================
# WLED Command Builder
# ============================================================================

def build_wled_segment_cmd(zone: dict, rgb: list) -> str:
    """
    Build a WLED JSON segment command for the given zone and color.

    WLED MQTT API: publish to wled/{device}/api
    Payload is the same JSON as the HTTP /json endpoint.
    Segment stop is exclusive (WLED convention).

    Args:
        zone: Zone config dict with 'pixels' (start/stop) and 'id'
        rgb:  [R, G, B] color list

    Returns:
        JSON string ready to publish
    """
    payload = {
        "seg": [
            {
                "id":    zone["segment_id"],
                "start": zone["pixels"]["start"],
                "stop":  zone["pixels"]["stop"],
                "col":   [rgb, [0, 0, 0], [0, 0, 0]],  # primary, secondary, tertiary
                "fx":    0,   # solid effect
                "bri":   255,
                "on":    True,
            }
        ]
    }
    return json.dumps(payload)


# ============================================================================
# Zone State Tracking
# ============================================================================

class ZoneState:
    """Tracks last known value and color for a zone, for heartbeat logging."""

    def __init__(self, zone_id: str, zone_name: str):
        self.zone_id = zone_id
        self.zone_name = zone_name
        self.last_temp_f = None
        self.last_rgb = None
        self.last_update = None

    def update(self, temp_f: float, rgb: list):
        self.last_temp_f = temp_f
        self.last_rgb = rgb
        self.last_update = datetime.now()

    def summary(self) -> str:
        if self.last_temp_f is None:
            return f"[{self.zone_id}] no data yet"
        age = (datetime.now() - self.last_update).seconds
        # last_temp_f is float for temperature zones, string for state zones
        if isinstance(self.last_temp_f, float):
            value_str = f"{self.last_temp_f:.1f}°F"
        else:
            value_str = str(self.last_temp_f)
        return f"[{self.zone_id}] {value_str} → RGB{tuple(self.last_rgb)} ({age}s ago)"


# ============================================================================
# WLED Bridge Core
# ============================================================================

class WLEDBridge:
    def __init__(self, config: dict):
        self.config = config
        self.wled_device_topic = config["wled"]["device_topic"]
        self.zones = config.get("zones", [])
        self.zone_states = {
            z["id"]: ZoneState(z["id"], z["name"]) for z in self.zones
        }

        # Build routing lookups by source type
        # Temperature zones: keyed by room name (lowercased)
        self.room_to_zone = {}
        # State zones: keyed by exact MQTT topic string
        self.state_topic_to_zone = {}

        self.static_zones = []  # published once on connect

        for zone in self.zones:
            src = zone.get("source", {})
            src_type = src.get("type", "mqtt_temperature")
            if src_type == "mqtt_temperature":
                room = src.get("room", "").lower()
                if room:
                    self.room_to_zone[room] = zone
            elif src_type == "mqtt_state":
                topic = src.get("topic", "")
                if topic:
                    self.state_topic_to_zone[topic] = zone
            elif src_type == "static":
                self.static_zones.append(zone)

        # MQTT topics
        self.temp_topic = f"{SHOWSITE}/dpx_ops_decoder/+/+/+/+/temperature"
        # WLED subscribes to {device_topic}/api for JSON segment commands
        self.wled_topic = f"{self.wled_device_topic}/api"

        self.client = mqtt.Client(client_id="dpx_wled_bridge")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self._heartbeat_timer = None

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info(f"Connected to MQTT broker at {BROKER}:{PORT}")
            log.info(f"WLED device topic: {self.wled_device_topic}  →  api: {self.wled_topic}")
            # Subscribe to temperature wildcard
            client.subscribe(self.temp_topic)
            log.info(f"Subscribed (temp):  {self.temp_topic}")
            # Subscribe to each state zone topic individually
            for topic in self.state_topic_to_zone:
                client.subscribe(topic)
                log.info(f"Subscribed (state): {topic}")
            log.info(f"Active zones: {[z['id'] for z in self.zones]}")
            # Publish static zones immediately (e.g. dark segment blackout)
            for zone in self.static_zones:
                rgb = zone.get("color", [0, 0, 0])
                client.publish(self.wled_topic, build_wled_segment_cmd(zone, rgb))
                log.info(f"[{zone['id']}] static → RGB{tuple(rgb)} → px {zone['pixels']['start']}–{zone['pixels']['stop'] - 1}")
            self._schedule_heartbeat()
        else:
            log.error(f"MQTT connect failed (rc={rc})")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            log.warning(f"Unexpected disconnect (rc={rc}), reconnecting...")

    def _on_message(self, client, userdata, msg):
        """Route incoming MQTT messages to the appropriate zone handler."""
        # Check state zones first (exact topic match)
        if msg.topic in self.state_topic_to_zone:
            self._handle_state_message(msg)
        else:
            self._handle_temp_message(msg)

    def _handle_temp_message(self, msg):
        """
        Handle temperature message from BLE decoder.

        Topic format: {site}/dpx_ops_decoder/{gw}/{room}/{device}/{mac}/temperature
        Indices:        0         1              2    3      4       5       6
        """
        try:
            temp_f = float(msg.payload)
        except (ValueError, TypeError):
            return

        parts = msg.topic.split("/")
        if len(parts) < 7:
            return

        room = parts[3].lower()
        zone = self.room_to_zone.get(room)
        if not zone:
            return

        rgb = interpolate_color(temp_f, zone["gradient"])
        self.client.publish(self.wled_topic, build_wled_segment_cmd(zone, rgb))

        zone_id = zone["id"]
        self.zone_states[zone_id].update(temp_f, rgb)

        log.info(
            f"[{zone_id}] room={room}  {temp_f:.1f}°F  →  RGB{tuple(rgb)}  "
            f"→  px {zone['pixels']['start']}–{zone['pixels']['stop'] - 1}  "
            f"→  {self.wled_topic}"
        )

    def _handle_state_message(self, msg):
        """
        Handle mqtt_state message (e.g. button lamp state).

        Payload: "on" → color_on, anything else → color_off
        """
        zone = self.state_topic_to_zone.get(msg.topic)
        if not zone:
            return

        try:
            payload = msg.payload.decode().strip().lower()
        except Exception:
            return

        rgb = zone["color_on"] if payload == "on" else zone["color_off"]
        self.client.publish(self.wled_topic, build_wled_segment_cmd(zone, rgb))

        zone_id = zone["id"]
        # Reuse ZoneState with temp_f=None — store payload string as display value
        self.zone_states[zone_id].last_temp_f = payload
        self.zone_states[zone_id].last_rgb = rgb
        self.zone_states[zone_id].last_update = datetime.now()

        log.info(
            f"[{zone_id}] state={payload}  →  RGB{tuple(rgb)}  "
            f"→  px {zone['pixels']['start']}–{zone['pixels']['stop'] - 1}  "
            f"→  {self.wled_topic}"
        )

    def _schedule_heartbeat(self):
        """Log zone states every 60 seconds."""
        self._heartbeat_timer = Timer(60.0, self._heartbeat)
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _heartbeat(self):
        log.info("── heartbeat ──")
        for state in self.zone_states.values():
            log.info(f"  {state.summary()}")
        self._schedule_heartbeat()

    def run(self):
        """Connect and start the MQTT event loop."""
        try:
            self.client.connect(BROKER, PORT, keepalive=60)
            log.info("Starting WLED bridge loop...")
            self.client.loop_forever()
        except KeyboardInterrupt:
            log.info("Shutting down...")
            if self._heartbeat_timer:
                self._heartbeat_timer.cancel()
            self.client.disconnect()
        except Exception as e:
            log.error(f"Fatal error: {e}")
            sys.exit(1)


# ============================================================================
# Entry Point
# ============================================================================

def main():
    log.info("=" * 60)
    log.info(f"DPX WLED Bridge v{VERSION}")
    log.info("=" * 60)

    config = load_config()

    zones = config.get("zones", [])
    log.info(f"Showsite:    {SHOWSITE}")
    log.info(f"WLED topic:  {config['wled']['device_topic']}/api")
    log.info(f"LED count:   {config['wled'].get('led_count', 100)}")
    log.info(f"Zones:       {len(zones)}")
    for z in zones:
        px = z["pixels"]
        room = z["source"].get("room", "?")
        log.info(
            f"  {z['id']:20s}  px {px['start']:3d}–{px['stop'] - 1:3d}  "
            f"room={room}  name={z['name']}"
        )
    log.info("")

    bridge = WLEDBridge(config)
    bridge.run()


if __name__ == "__main__":
    main()
