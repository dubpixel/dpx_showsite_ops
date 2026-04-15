#!/usr/bin/env python3
"""
DPX Guest Alert Button Controller

Always-running daemon that monitors button inputs on one X410 device
and controls blinking lamp relays on another X410 device.

Architecture:
    - Button Panel (192.168.105.112): 4 digital inputs (colored buttons)
    - Lamp Controller (192.168.105.111): 4 relays (colored lamps) + 1 input (big red button)
    
Behavior:
    - Press colored button → corresponding lamp blinks
    - Hold colored button >10s → that specific lamp turns OFF
    - Press big red button → all lamps turn OFF
    - Multiple lamps can blink simultaneously

Dependencies:
    - pysnmp: SNMP communication with X410 devices
    - pyyaml: Configuration file parsing
    - flask: Health endpoint HTTP server
"""

import os
import sys
import time
import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Literal
from datetime import datetime

import yaml
from flask import Flask, jsonify, request
import paho.mqtt.client as mqtt

try:
    from pysnmp.hlapi import (
        getCmd, setCmd, SnmpEngine, CommunityData, UdpTransportTarget,
        ContextData, ObjectType, ObjectIdentity, OctetString
    )
except ImportError as e:
    print(f"Error: pysnmp library not found or import failed: {e}", file=sys.stderr)
    print("Install with: pip install pysnmp==4.4.12", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# Configuration
# ============================================================================

CONFIG_FILE = Path("/app/config.yaml")
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(message)s'

# X410 OID base for inputs and relays
X410_OID_BASE = "1.3.6.1.4.1.30586.46.0"

# Input OIDs (digital inputs 1-4)
INPUT_OIDS = {
    1: f"{X410_OID_BASE}.1",
    2: f"{X410_OID_BASE}.2",
    3: f"{X410_OID_BASE}.3",
    4: f"{X410_OID_BASE}.4",
}

# Relay OIDs (relay outputs 1-4)
RELAY_OIDS = {
    1: f"{X410_OID_BASE}.5",
    2: f"{X410_OID_BASE}.6",
    3: f"{X410_OID_BASE}.7",
    4: f"{X410_OID_BASE}.8",
}

# SNMP values (STRING type per X410 MIB)
STATE_OFF = "0"
STATE_ON = "1"


# ============================================================================
# Global State
# ============================================================================

class SystemState:
    """Global state container for the button controller."""
    
    def __init__(self):
        # Lamp states: {relay_num: 'off' | 'blink'}
        self.lamp_state: Dict[int, Literal['off', 'blink']] = {1: 'off', 2: 'off', 3: 'off', 4: 'off'}
        
        # Button states (previous cycle) for edge detection
        self.prev_button_state: Dict[int, str] = {1: STATE_OFF, 2: STATE_OFF, 3: STATE_OFF, 4: STATE_OFF}
        self.prev_clear_button_state: str = STATE_OFF
        
        # Button hold timers: {button_num: start_time | None}
        self.button_hold_start: Dict[int, Optional[float]] = {1: None, 2: None, 3: None, 4: None}
        
        # Blink state tracker (which relays are currently ON during blink cycle)
        self.relay_physical_state: Dict[int, bool] = {1: False, 2: False, 3: False, 4: False}
        
        # Statistics
        self.stats = {
            'uptime_start': time.time(),
            'button_presses': {1: 0, 2: 0, 3: 0, 4: 0},
            'clear_presses': 0,
            'hold_resets': {1: 0, 2: 0, 3: 0, 4: 0},
            'snmp_errors': 0,
            'last_poll_time': None,
            'blink_cycles': 0,
        }
        
        # Thread lock for state updates
        self.lock = threading.Lock()


# ============================================================================
# SNMP Helper Functions
# ============================================================================

def snmp_get_input(ip: str, community: str, input_num: int, timeout: int = 1) -> Optional[str]:
    """
    Read digital input state via SNMP GET.
    
    Args:
        ip: Device IP address
        community: SNMP community string
        input_num: Input number (1-4)
        timeout: SNMP timeout in seconds (default: 1s, overridden by config)
        
    Returns:
        "0" for inactive, "1" for active, None on error
    """
    if input_num not in INPUT_OIDS:
        return None
    
    oid = INPUT_OIDS[input_num]
    
    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, 161), timeout=timeout),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication or errorStatus:
            return None
        
        for varBind in varBinds:
            return str(varBind[1])
            
    except Exception as e:
        logging.debug(f"Error reading input {input_num} from {ip}: {e}")
        return None


def snmp_set_relay(ip: str, community: str, relay_num: int, state: str, timeout: int = 1) -> bool:
    """
    Set relay state via SNMP SET.
    
    Args:
        ip: Device IP address
        community: SNMP community string
        relay_num: Relay number (1-4)
        state: "0" for OFF, "1" for ON
        timeout: SNMP timeout in seconds
        
    Returns:
        True on success, False on error
    """
    if relay_num not in RELAY_OIDS:
        return False
    
    oid = RELAY_OIDS[relay_num]
    
    try:
        iterator = setCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, 161), timeout=timeout),
            ContextData(),
            ObjectType(ObjectIdentity(oid), OctetString(state))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication or errorStatus:
            return False
        
        return True
            
    except Exception as e:
        logging.debug(f"Error setting relay {relay_num} on {ip}: {e}")
        return False


# ============================================================================
# Main Controller Logic
# ============================================================================

class ButtonController:
    """Main controller that polls buttons and manages lamp blinking."""
    
    def __init__(self, config: dict, state: SystemState):
        self.config = config
        self.state = state
        
        # Extract config values
        self.lamp_ip = config['devices']['lamp_controller']['ip']
        self.button_ip = config['devices']['button_panel']['ip']
        self.snmp_community = os.getenv('X410_SNMP_COMMUNITY', config['snmp']['community'])
        self.snmp_timeout = config['snmp']['timeout']
        self.poll_interval = config['snmp']['poll_interval_ms'] / 1000.0  # Convert to seconds
        self.blink_frequency = float(os.getenv('BUTTON_BLINK_HZ', config['blink']['frequency_hz']))
        self.hold_threshold = config['button_hold']['reset_threshold_seconds']
        
        # Calculate blink timing
        self.blink_period = 1.0 / self.blink_frequency  # Full cycle time
        self.blink_interval = self.blink_period / 2  # Half period (on/off toggle time)
        
        self.running = False

        # Relay number → lowercase color name (from config)
        self.relay_colors = {
            num: color.lower()
            for num, color in config['devices']['lamp_controller']['relays'].items()
        }

        # MQTT client for publishing lamp state changes to wled-bridge and other subscribers
        # Optional — button service continues working if broker is unavailable
        self.showsite = os.getenv('SHOWSITE_NAME', 'demo_showsite')
        self._mqtt = mqtt.Client(client_id="dpx_button_controller")
        self._mqtt_broker = os.getenv('BROKER', 'mosquitto')
        self._mqtt_connected = False
        self._mqtt.on_connect = self._on_mqtt_connect
        self._mqtt.on_disconnect = self._on_mqtt_disconnect
        try:
            self._mqtt.connect_async(self._mqtt_broker, 1883, keepalive=60)
            self._mqtt.loop_start()
        except Exception as e:
            logging.warning(f"MQTT unavailable ({e}) — lamp state will not be published")

        logging.info(f"ButtonController initialized")
        logging.info(f"  Lamp IP: {self.lamp_ip}")
        logging.info(f"  Button IP: {self.button_ip}")
        logging.info(f"  SNMP timeout: {self.snmp_timeout}s")
        logging.info(f"  Poll interval: {self.poll_interval*1000:.0f}ms")
        logging.info(f"  Blink frequency: {self.blink_frequency}Hz ({self.blink_interval*1000:.0f}ms per toggle)")
        logging.info(f"  Hold reset threshold: {self.hold_threshold}s")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._mqtt_connected = True
            logging.info(f"MQTT connected to {self._mqtt_broker}:1883 — publishing lamp states")
            # Publish current state of all lamps on (re)connect
            with self.state.lock:
                for relay_num in range(1, 5):
                    self._publish_lamp_state(relay_num, self.state.lamp_state[relay_num])
        else:
            logging.warning(f"MQTT connect failed (rc={rc})")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        self._mqtt_connected = False
        if rc != 0:
            logging.warning(f"MQTT disconnected (rc={rc}), will retry")

    def _publish_lamp_state(self, relay_num: int, lamp_state: str):
        """Publish lamp state to MQTT. Call within state.lock or after state is set."""
        if not self._mqtt_connected:
            return
        color = self.relay_colors.get(relay_num, f"relay{relay_num}")
        topic = f"{self.showsite}/button/{color}/state"
        payload = "on" if lamp_state == "blink" else "off"
        try:
            self._mqtt.publish(topic, payload, retain=True)
        except Exception as e:
            logging.debug(f"MQTT publish failed for {topic}: {e}")

    def poll_buttons(self):
        """Poll button states and update lamp state based on button presses and holds."""
        current_time = time.time()
        
        logging.debug(f"Polling buttons on {self.button_ip}...")
        
        # Poll colored buttons (1-4) on button panel
        for button_num in range(1, 5):
            button_state = snmp_get_input(self.button_ip, self.snmp_community, button_num, self.snmp_timeout)
            
            if button_state is None:
                # SNMP error - skip this button
                logging.debug(f"  Button {button_num}: SNMP ERROR")
                with self.state.lock:
                    self.state.stats['snmp_errors'] += 1
                continue
            
            logging.debug(f"  Button {button_num}: {button_state}")
            
            with self.state.lock:
                prev_state = self.state.prev_button_state[button_num]
                
                # Detect rising edge (button press)
                if button_state == STATE_ON and prev_state == STATE_OFF:
                    logging.info(f"Button {button_num} pressed → Lamp {button_num} BLINK")
                    self.state.lamp_state[button_num] = 'blink'
                    self._publish_lamp_state(button_num, 'blink')
                    self.state.button_hold_start[button_num] = current_time
                    self.state.stats['button_presses'][button_num] += 1
                
                # Detect button hold (for individual reset)
                elif button_state == STATE_ON and self.state.button_hold_start[button_num] is not None:
                    hold_duration = current_time - self.state.button_hold_start[button_num]
                    
                    if hold_duration >= self.hold_threshold:
                        if self.state.lamp_state[button_num] != 'off':
                            logging.info(f"Button {button_num} held {hold_duration:.1f}s → Reset lamp {button_num} OFF")
                            self.state.lamp_state[button_num] = 'off'
                            self._publish_lamp_state(button_num, 'off')
                            self.state.stats['hold_resets'][button_num] += 1
                        # Clear hold timer to prevent repeated triggers
                        self.state.button_hold_start[button_num] = None
                
                # Button released
                elif button_state == STATE_OFF:
                    self.state.button_hold_start[button_num] = None
                
                # Update previous state
                self.state.prev_button_state[button_num] = button_state
        
        # Poll big red button (clear all) on lamp controller
        clear_state = snmp_get_input(self.lamp_ip, self.snmp_community, 1, self.snmp_timeout)
        
        if clear_state is not None:
            logging.debug(f"  Clear button: {clear_state}")
            with self.state.lock:
                # Detect rising edge (clear button press)
                if clear_state == STATE_ON and self.state.prev_clear_button_state == STATE_OFF:
                    logging.info("BIG RED BUTTON pressed → Clear all lamps")
                    for i in range(1, 5):
                        self.state.lamp_state[i] = 'off'
                        self._publish_lamp_state(i, 'off')
                    self.state.stats['clear_presses'] += 1
                
                self.state.prev_clear_button_state = clear_state
        else:
            logging.debug(f"  Clear button: SNMP ERROR")
        
        # Update last poll time
        with self.state.lock:
            self.state.stats['last_poll_time'] = current_time
    
    def update_relays(self):
        """Update physical relay states based on lamp state (blink toggle)."""
        logging.debug("Updating relays...")
        
        with self.state.lock:
            for relay_num in range(1, 5):
                lamp_mode = self.state.lamp_state[relay_num]
                
                if lamp_mode == 'blink':
                    # Toggle relay state
                    new_state = not self.state.relay_physical_state[relay_num]
                    self.state.relay_physical_state[relay_num] = new_state
                    
                    snmp_state = STATE_ON if new_state else STATE_OFF
                    logging.debug(f"  Lamp {relay_num}: BLINK → {snmp_state}")
                    success = snmp_set_relay(self.lamp_ip, self.snmp_community, relay_num, snmp_state, self.snmp_timeout)
                    
                    if not success:
                        logging.debug(f"  Lamp {relay_num}: SNMP SET FAILED")
                        self.state.stats['snmp_errors'] += 1
                
                elif lamp_mode == 'off':
                    # Ensure relay is OFF
                    if self.state.relay_physical_state[relay_num]:
                        self.state.relay_physical_state[relay_num] = False
                        logging.debug(f"  Lamp {relay_num}: OFF")
                        success = snmp_set_relay(self.lamp_ip, self.snmp_community, relay_num, STATE_OFF, self.snmp_timeout)
                        
                        if not success:
                            logging.debug(f"  Lamp {relay_num}: SNMP SET FAILED")
                            self.state.stats['snmp_errors'] += 1
            
            self.state.stats['blink_cycles'] += 1
    
    def run(self):
        """Main control loop - polls buttons and drives blink timer."""
        self.running = True
        last_blink_update = time.time()
        
        logging.info("Starting button controller loop...")
        sys.stdout.flush()  # Force flush
        
        try:
            loop_count = 0
            while self.running:
                loop_start = time.time()
                
                # Log every 100th iteration to show we're alive
                if loop_count % 100 == 0:
                    logging.info(f"Controller loop iteration {loop_count}")
                    sys.stdout.flush()
                
                loop_count += 1
                
                # Poll buttons at configured interval
                self.poll_buttons()
                
                # Update relay blink states at blink interval
                if (loop_start - last_blink_update) >= self.blink_interval:
                    self.update_relays()
                    last_blink_update = loop_start
                
                # Sleep for remainder of poll interval
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.poll_interval - elapsed)
                time.sleep(sleep_time)
        
        except KeyboardInterrupt:
            logging.info("Received shutdown signal")
        except Exception as e:
            logging.error(f"Fatal error in control loop: {e}", exc_info=True)
            sys.stdout.flush()
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown - turn off all relays."""
        logging.info("Shutting down - clearing all lamps...")
        self.running = False
        
        # Turn off all relays
        for relay_num in range(1, 5):
            snmp_set_relay(self.lamp_ip, self.snmp_community, relay_num, STATE_OFF, self.snmp_timeout)
        
        logging.info("Shutdown complete")
    
    def clear_all_lamps(self):
        """Manually clear all lamps (same as big red button)."""
        with self.state.lock:
            for i in range(1, 5):
                self.state.lamp_state[i] = 'off'
                self._publish_lamp_state(i, 'off')
        logging.info("Manual clear - all lamps OFF")
    
    def reset_lamp(self, lamp_num: int):
        """Manually reset specific lamp."""
        if lamp_num in range(1, 5):
            with self.state.lock:
                self.state.lamp_state[lamp_num] = 'off'
                self._publish_lamp_state(lamp_num, 'off')
            logging.info(f"Manual reset - lamp {lamp_num} OFF")
            return True
        return False


# ============================================================================
# Health/Metrics HTTP Server
# ============================================================================

def create_health_app(controller: ButtonController, state: SystemState, config: dict):
    """Create Flask app for health checks and metrics."""
    app = Flask(__name__)
    
    # Disable Flask's default logging (we handle it)
    import logging as flask_logging
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)
    
    @app.route('/health')
    def health():
        """Health check endpoint - returns system status."""
        with state.lock:
            uptime = time.time() - state.stats['uptime_start']
            
            # Get lamp states with color names
            lamp_states = {}
            for num in range(1, 5):
                color = config['devices']['lamp_controller']['relays'][num]
                lamp_states[color.lower()] = {
                    'relay': num,
                    'state': state.lamp_state[num],
                    'physical_on': state.relay_physical_state[num]
                }
            
            response = {
                'status': 'healthy',
                'uptime_seconds': round(uptime, 1),
                'lamp_states': lamp_states,
                'stats': {
                    'button_presses': state.stats['button_presses'],
                    'clear_presses': state.stats['clear_presses'],
                    'hold_resets': state.stats['hold_resets'],
                    'snmp_errors': state.stats['snmp_errors'],
                    'blink_cycles': state.stats['blink_cycles'],
                    'last_poll': state.stats['last_poll_time']
                },
                'config': {
                    'lamp_ip': controller.lamp_ip,
                    'button_ip': controller.button_ip,
                    'blink_hz': controller.blink_frequency,
                    'poll_ms': controller.poll_interval * 1000,
                    'hold_threshold_s': controller.hold_threshold
                }
            }
        
        return jsonify(response)
    
    @app.route('/metrics')
    def metrics():
        """Prometheus-compatible metrics endpoint."""
        with state.lock:
            uptime = time.time() - state.stats['uptime_start']
            
            lines = [
                '# HELP button_controller_uptime_seconds Time since controller started',
                '# TYPE button_controller_uptime_seconds gauge',
                f'button_controller_uptime_seconds {uptime:.1f}',
                '',
                '# HELP button_presses_total Total button presses by color',
                '# TYPE button_presses_total counter',
            ]
            
            for num, count in state.stats['button_presses'].items():
                color = config['devices']['lamp_controller']['relays'][num].lower()
                lines.append(f'button_presses_total{{color="{color}"}} {count}')
            
            lines.extend([
                '',
                '# HELP clear_button_presses_total Total big red button presses',
                '# TYPE clear_button_presses_total counter',
                f'clear_button_presses_total {state.stats["clear_presses"]}',
                '',
                '# HELP hold_resets_total Total hold-to-reset events by color',
                '# TYPE hold_resets_total counter',
            ])
            
            for num, count in state.stats['hold_resets'].items():
                color = config['devices']['lamp_controller']['relays'][num].lower()
                lines.append(f'hold_resets_total{{color="{color}"}} {count}')
            
            lines.extend([
                '',
                '# HELP lamp_state Current lamp state (0=off, 1=blink)',
                '# TYPE lamp_state gauge',
            ])
            
            for num in range(1, 5):
                color = config['devices']['lamp_controller']['relays'][num].lower()
                value = 1 if state.lamp_state[num] == 'blink' else 0
                lines.append(f'lamp_state{{color="{color}"}} {value}')
            
            lines.extend([
                '',
                '# HELP snmp_errors_total Total SNMP communication errors',
                '# TYPE snmp_errors_total counter',
                f'snmp_errors_total {state.stats["snmp_errors"]}',
                '',
                '# HELP blink_cycles_total Total blink update cycles',
                '# TYPE blink_cycles_total counter',
                f'blink_cycles_total {state.stats["blink_cycles"]}',
                ''
            ])
        
        return '\n'.join(lines), 200, {'Content-Type': 'text/plain; charset=utf-8'}
    
    @app.route('/clear', methods=['POST'])
    def clear():
        """Manually trigger clear all lamps."""
        controller.clear_all_lamps()
        return jsonify({'status': 'success', 'action': 'cleared_all_lamps'})
    
    @app.route('/reset/<color>', methods=['POST'])
    def reset_lamp(color):
        """Reset specific lamp by color name."""
        # Map color name to relay number
        color_map = {
            'red': 1,
            'yellow': 2,
            'green': 3,
            'blue': 4
        }
        
        lamp_num = color_map.get(color.lower())
        if lamp_num is None:
            return jsonify({'status': 'error', 'message': f'Invalid color: {color}'}), 400
        
        success = controller.reset_lamp(lamp_num)
        if success:
            return jsonify({'status': 'success', 'action': f'reset_lamp_{color}', 'relay': lamp_num})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to reset lamp'}), 500
    
    @app.route('/')
    def index():
        """Service info."""
        return jsonify({
            'service': 'DPX Guest Alert Button Controller',
            'version': '1.0.0',
            'endpoints': {
                'GET /health': 'Health check and status',
                'GET /metrics': 'Prometheus metrics',
                'POST /clear': 'Clear all lamps',
                'POST /reset/<color>': 'Reset specific lamp (red/yellow/green/blue)'
            }
        })
    
    return app


# ============================================================================
# Main Entry Point
# ============================================================================

def load_config() -> dict:
    """Load configuration from YAML file."""
    if not CONFIG_FILE.exists():
        print(f"Error: Configuration file not found: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    try:
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=LOG_FORMAT,
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        
        logging.info("=== DPX Guest Alert Button Controller ===")
        
        # Load configuration
        config = load_config()
        logging.info("Configuration loaded successfully")
        
        # Initialize state
        state = SystemState()
        
        # Create controller
        controller = ButtonController(config, state)
        
        # Start health server in background thread
        health_port = config['health']['port']
        health_app = create_health_app(controller, state, config)
        
        def run_health_server():
            try:
                logging.info(f"Flask health server thread starting on 0.0.0.0:{health_port}")
                health_app.run(host='0.0.0.0', port=health_port, debug=False, use_reloader=False, threaded=True)
            except Exception as e:
                logging.error(f"Health server failed to start: {e}", exc_info=True)
        
        health_thread = threading.Thread(target=run_health_server, daemon=True)
        health_thread.start()
        time.sleep(0.5)  # Give Flask time to bind
        logging.info(f"Health server started on port {health_port}")
        
        # Run main controller (blocks until shutdown)
        logging.info("About to start controller.run()...")
        controller.run()
        logging.info("Controller.run() exited normally")
        
    except Exception as e:
        logging.error(f"FATAL ERROR in main(): {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
