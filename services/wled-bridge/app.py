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
import random
import re
import socket
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from threading import Thread, Timer

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

def build_wled_text_cmd(text: str, led_count: int, color: list, speed: int, m12: int = 14, pal: int = 0) -> str:
    """
    Build a WLED JSON segment command that displays scrolling text (fx: 122).

    WLED's Scrolling Text effect reads the segment name field ('n') as the text
    to display. Works on both 1D strips and 2D matrices.

    Args:
        text:      The string to scroll across the display
        led_count: Total number of LEDs in the segment (e.g. 170 for 17×10 matrix)
        color:     [R, G, B] primary text color
        speed:     Scroll speed 0–255
        pal:       WLED palette ID (0 = solid color, non-zero uses built-in palette)

    Returns:
        JSON string ready to publish to {device_topic}/api
    """
    payload = {
        "seg": [
            {
                "id":    0,
                "start": 0,
                "stop":  led_count,
                "fx":    122,   # Scrolling Text
                "sx":    speed,
                "ix":    128,
                "col":   [color, [0, 0, 0], [0, 0, 0]],
                "n":     text,  # segment name = text to scroll
                "on":    True,
                "bri":   200,
                "m12":   m12,   # 2D transform param ("Rotate" in scrolling text UI)
                "pal":   pal,   # 0 = force Color 1 (solid); non-zero = built-in palette
            }
        ]
    }
    return json.dumps(payload)


def build_wled_matrix_clear_cmd(led_count: int) -> str:
    """
    Build a WLED JSON segment command that blanks the matrix (solid black, fx: 0).

    Args:
        led_count: Total number of LEDs in the segment

    Returns:
        JSON string ready to publish to {device_topic}/api
    """
    payload = {
        "seg": [
            {
                "id":    0,
                "start": 0,
                "stop":  led_count,
                "fx":    0,
                "col":   [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
                "on":    True,
            }
        ]
    }
    return json.dumps(payload)


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

        # ── Matrix / scrolling text ──────────────────────────────────────────
        self.matrix_cfg = config.get("matrix")
        self.matrix_api_topic = None
        self.matrix_text_sub_topic = None
        self._text_clear_timer = None
        self._udp_thread = None

        if self.matrix_cfg:
            self.matrix_api_topic = f"{self.matrix_cfg['device_topic']}/api"
            self.matrix_text_sub_topic = self.matrix_cfg["text_topic"]
            udp_port = int(self.matrix_cfg.get("udp_port", 0))
            if udp_port:
                self._start_udp_listener(udp_port)

        self.client = mqtt.Client(client_id="dpx_wled_bridge")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self._heartbeat_timer = None
        self._screensaver_ids = None  # cached after first fetch

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
            # Subscribe to matrix text topic if configured
            if self.matrix_cfg:
                client.subscribe(self.matrix_text_sub_topic)
                log.info(f"Subscribed (matrix text): {self.matrix_text_sub_topic}")
                log.info(f"Matrix device topic: {self.matrix_cfg['device_topic']}  →  api: {self.matrix_api_topic}")
                udp_port = int(self.matrix_cfg.get("udp_port", 0))
                if udp_port:
                    log.info(f"Matrix UDP listener: port {udp_port}")
            self._schedule_heartbeat()
        else:
            log.error(f"MQTT connect failed (rc={rc})")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            log.warning(f"Unexpected disconnect (rc={rc}), reconnecting...")

    def _on_message(self, client, userdata, msg):
        """Route incoming MQTT messages to the appropriate zone handler."""
        # Matrix text topic takes priority
        if self.matrix_cfg and msg.topic == self.matrix_text_sub_topic:
            self._handle_matrix_text(msg)
            return
        # Check state zones (exact topic match)
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

    # ── Matrix / scrolling text ──────────────────────────────────────────────

    def _parse_text_payload(self, raw: bytes) -> tuple:
        """
        Parse an incoming text payload (MQTT or UDP).

        Accepts plain string or JSON:
            "DOORS OPEN"
            {"text": "...", "color": [R, G, B], "speed": 0-255, "ttl": seconds}

        Defaults: env vars (WLED_MATRIX_DEFAULT_SPEED / _COLOR / _TTL) override
        config.yaml values — change them in .env + iot wled-restart, no rebuild needed.

        Returns (text, color, speed, ttl).
        """
        cfg = self.matrix_cfg

        # Env vars win over config.yaml defaults — restart is enough to apply changes
        _cfg_color = cfg.get("default_color", [255, 220, 0])
        _env_color = os.getenv("WLED_MATRIX_DEFAULT_COLOR", "")
        if _env_color:
            try:
                default_color = [int(x) for x in _env_color.split(",")]
            except ValueError:
                default_color = _cfg_color
        else:
            default_color = _cfg_color

        default_speed = int(os.getenv("WLED_MATRIX_DEFAULT_SPEED", str(cfg.get("default_speed", 255))))
        default_ttl   = int(os.getenv("WLED_MATRIX_DEFAULT_TTL",   str(cfg.get("default_ttl",   30))))

        try:
            decoded = raw.decode().strip()
        except Exception:
            return None, default_color, default_speed, default_ttl

        try:
            data   = json.loads(decoded)
            text   = str(data.get("text", "")).strip()
            color  = data.get("color", default_color)
            speed  = int(data.get("speed", default_speed))
            ttl    = int(data.get("ttl", default_ttl))
            m12    = int(data.get("rotate", 14))  # payload key "rotate" maps to WLED m12
            pal    = int(data.get("pal", 0))
        except (json.JSONDecodeError, TypeError):
            text   = decoded
            color  = default_color
            speed  = default_speed
            ttl    = default_ttl
            m12    = 14
            pal    = 0

        return text or None, color, speed, ttl, m12, pal

    def _dispatch_matrix_text(self, text: str, color: list, speed: int, ttl: int, m12: int = 14, pal: int = 0):
        """
        Send scrolling text to the matrix and schedule a clear after TTL seconds.
        Called by both the MQTT handler and the UDP listener.
        """
        led_count = int(self.matrix_cfg.get("led_count", 170))

        # Cancel any pending clear from a previous message
        if self._text_clear_timer is not None:
            self._text_clear_timer.cancel()
            self._text_clear_timer = None

        # Activate text preset first if configured — loads correct m12/rotate etc.
        text_preset = self.matrix_cfg.get("text_preset")
        if text_preset:
            log.info(f"[matrix] activating text preset {text_preset} → {self.matrix_api_topic}")
            self.client.publish(
                self.matrix_api_topic,
                json.dumps({"ps": int(text_preset)}),
            )
        else:
            log.warning("[matrix] no text_preset configured — m12/rotate may be wrong after screensaver")

        self.client.publish(
            self.matrix_api_topic,
            build_wled_text_cmd(text, led_count, color, speed, m12, pal),
        )
        log.info(
            f"[matrix] text={text!r}  color=RGB{tuple(color)}  "
            f"speed={speed}  pal={pal}  m12={m12}  ttl={ttl}s  →  {self.matrix_api_topic}"
        )

        self._text_clear_timer = Timer(ttl, self._clear_matrix)
        self._text_clear_timer.daemon = True
        self._text_clear_timer.start()

    def _handle_matrix_text(self, msg):
        """Handle a matrix text message arriving via MQTT."""
        text, color, speed, ttl, m12, pal = self._parse_text_payload(msg.payload)
        if not text:
            log.warning("[matrix] received empty text payload, ignoring")
            return
        self._dispatch_matrix_text(text, color, speed, ttl, m12, pal)

    def _get_screensaver_ids(self) -> list:
        """Return screensaver preset IDs (all presets except text_preset), cached."""
        if self._screensaver_ids is not None:
            return self._screensaver_ids
        wled_host = self.matrix_cfg.get("wled_host", "")
        if not wled_host:
            self._screensaver_ids = []
            return []
        text_preset = self.matrix_cfg.get("text_preset")
        for path in ("/json/presets", "/presets.json"):
            try:
                url = f"http://{wled_host}{path}"
                with urllib.request.urlopen(url, timeout=3) as resp:
                    data = json.loads(resp.read())
                ids = [int(k) for k in data.keys() if k.isdigit() and k != "0"]
                if text_preset:
                    ids = [i for i in ids if i != int(text_preset)]
                self._screensaver_ids = ids
                log.info(f"[matrix] screensaver preset pool: {ids}")
                return ids
            except Exception as e:
                log.debug(f"[matrix] preset fetch {path}: {e}")
        self._screensaver_ids = []
        return []

    def _clear_matrix(self):
        """After TTL expires, activate a random screensaver preset (or blank if none configured)."""
        self._text_clear_timer = None
        ids = self._get_screensaver_ids()
        if ids:
            preset = random.choice(ids)
            self.client.publish(self.matrix_api_topic, json.dumps({"ps": preset}))
            log.info(f"[matrix] TTL expired → screensaver preset {preset}  →  {self.matrix_api_topic}")
        else:
            led_count = int(self.matrix_cfg.get("led_count", 170))
            self.client.publish(self.matrix_api_topic, build_wled_matrix_clear_cmd(led_count))
            log.info(f"[matrix] TTL expired — cleared (no screensaver presets)  →  {self.matrix_api_topic}")

    def _start_udp_listener(self, port: int):
        """Start a daemon thread that listens for UDP text datagrams."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", port))
            sock.settimeout(1.0)  # allow clean shutdown via daemon exit
        except OSError as e:
            log.error(f"[matrix] UDP listener failed to bind port {port}: {e}")
            return

        def _loop():
            log.info(f"[matrix] UDP listener ready on port {port}")
            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                text, color, speed, ttl, m12, pal = self._parse_text_payload(data)
                if not text:
                    log.warning(f"[matrix] UDP empty payload from {addr}, ignoring")
                    continue
                log.info(f"[matrix] UDP from {addr[0]}:{addr[1]}")
                self._dispatch_matrix_text(text, color, speed, ttl, m12, pal)

        self._udp_thread = Thread(target=_loop, name="matrix-udp", daemon=True)
        self._udp_thread.start()

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
            if self._text_clear_timer:
                self._text_clear_timer.cancel()
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
