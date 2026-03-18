#!/usr/bin/env python3
"""
Physical Control Webhook Receiver

Receives Grafana alert webhooks and triggers physical device control actions
based on alert_actions.yaml configuration.

Endpoints:
    POST /webhook - Receive Grafana alert webhooks
    GET  /health  - Health check endpoint
    GET  /        - Service info and stats
"""

import os
import sys
import subprocess
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import yaml
from flask import Flask, request, jsonify

# ============================================================================
# Configuration
# ============================================================================

app = Flask(__name__)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load alert actions configuration
CONFIG_FILE = Path("/app/alert_actions.yaml")
if not CONFIG_FILE.exists():
    logger.error(f"Configuration file not found: {CONFIG_FILE}")
    sys.exit(1)

with open(CONFIG_FILE) as f:
    CONFIG = yaml.safe_load(f)

# Global settings
SETTINGS = CONFIG.get("settings", {})
LOG_FILE = SETTINGS.get("log_file", "/var/log/physical-control/actions.log")
COMMAND_TIMEOUT = SETTINGS.get("command_timeout", 30)
RETRY_ATTEMPTS = SETTINGS.get("retry_attempts", 1)
RETRY_DELAY = SETTINGS.get("retry_delay", 5)
REQUIRE_AUTH = SETTINGS.get("require_auth", False)
AUTH_TOKEN_ENV = SETTINGS.get("auth_token_env", "WEBHOOK_AUTH_TOKEN")

# Stats tracking
STATS = {
    "webhooks_received": 0,
    "actions_executed": 0,
    "actions_failed": 0,
    "started_at": datetime.utcnow().isoformat()
}

# ============================================================================
# Helper Functions
# ============================================================================

def log_action(message: str, level: str = "INFO"):
    """Log action to both file and stdout."""
    timestamp = datetime.utcnow().isoformat()
    log_entry = f"{timestamp} [{level}] {message}\n"
    
    # Log to file if configured
    if LOG_FILE:
        try:
            log_dir = Path(LOG_FILE).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, 'a') as f:
                f.write(log_entry)
        except Exception as e:
            logger.warning(f"Failed to write to log file: {e}")
    
    # Log to stdout via logger
    if level == "ERROR":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    else:
        logger.info(message)


def match_alert(alert_data: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    """
    Check if alert data matches rule criteria.
    
    Args:
        alert_data: Alert payload from Grafana
        rule: Rule definition from alert_actions.yaml
        
    Returns:
        True if alert matches rule criteria
    """
    match_criteria = rule.get("match", {})
    
    # Match alert name
    if "alert_name" in match_criteria:
        if alert_data.get("alert_name") != match_criteria["alert_name"]:
            return False
    
    # Match labels
    if "labels" in match_criteria:
        alert_labels = alert_data.get("labels", {})
        for key, value in match_criteria["labels"].items():
            if alert_labels.get(key) != value:
                return False
    
    return True


def execute_command(command: str, description: str) -> bool:
    """
    Execute shell command with retry logic.
    
    Args:
        command: Shell command to execute
        description: Human-readable description of action
        
    Returns:
        True if command succeeded
    """
    for attempt in range(RETRY_ATTEMPTS + 1):
        try:
            if attempt > 0:
                log_action(f"Retry attempt {attempt}/{RETRY_ATTEMPTS}: {description}", "INFO")
                import time
                time.sleep(RETRY_DELAY)
            
            log_action(f"Executing: {description}", "INFO")
            log_action(f"Command: {command}", "DEBUG")
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT
            )
            
            if result.returncode == 0:
                log_action(f"✓ Success: {description}", "INFO")
                if result.stdout:
                    log_action(f"Output: {result.stdout.strip()}", "DEBUG")
                STATS["actions_executed"] += 1
                return True
            else:
                log_action(f"✗ Failed: {description} (exit code {result.returncode})", "ERROR")
                if result.stderr:
                    log_action(f"Error: {result.stderr.strip()}", "ERROR")
                
        except subprocess.TimeoutExpired:
            log_action(f"✗ Timeout: {description} (exceeded {COMMAND_TIMEOUT}s)", "ERROR")
        except Exception as e:
            log_action(f"✗ Exception: {description} - {str(e)}", "ERROR")
    
    STATS["actions_failed"] += 1
    return False


def process_alert(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process incoming alert and execute matching actions.
    
    Args:
        alert_data: Alert payload from Grafana
        
    Returns:
        Dict with processing results
    """
    alert_name = alert_data.get("alert_name", "Unknown")
    state = alert_data.get("state", "unknown")
    
    log_action(f"Processing alert: {alert_name} (state: {state})", "INFO")
    
    results = {
        "alert_name": alert_name,
        "state": state,
        "matched_rules": [],
        "actions_executed": 0,
        "actions_failed": 0
    }
    
    # Find matching rules
    for rule in CONFIG.get("alerts", []):
        if match_alert(alert_data, rule):
            rule_name = rule.get("name", "Unnamed Rule")
            results["matched_rules"].append(rule_name)
            log_action(f"Matched rule: {rule_name}", "INFO")
            
            # Execute actions for current state
            actions = rule.get("actions", {}).get(state, [])
            
            if not actions:
                log_action(f"No actions defined for state: {state}", "WARNING")
                continue
            
            for action in actions:
                device = action.get("device", "unknown")
                command = action.get("command", "")
                description = action.get("description", "No description")
                
                if not command:
                    log_action(f"Skipping action with empty command", "WARNING")
                    continue
                
                # Execute command
                success = execute_command(command, f"[{device}] {description}")
                
                if success:
                    results["actions_executed"] += 1
                else:
                    results["actions_failed"] += 1
    
    if not results["matched_rules"]:
        log_action(f"No matching rules found for alert: {alert_name}", "WARNING")
    
    return results


# ============================================================================
# Flask Routes
# ============================================================================

@app.route("/", methods=["GET"])
def index():
    """Service info and statistics."""
    return jsonify({
        "service": "physical-control-webhook-receiver",
        "version": "1.0.0",
        "stats": STATS,
        "config": {
            "alerts_configured": len(CONFIG.get("alerts", [])),
            "log_file": LOG_FILE,
            "command_timeout": COMMAND_TIMEOUT,
            "require_auth": REQUIRE_AUTH
        }
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Receive and process Grafana alert webhooks.
    
    Expected payload format (Grafana webhook):
    {
        "title": "Alert title",
        "state": "alerting" or "resolved",
        "message": "Alert message",
        "ruleName": "Rule name",
        "labels": {"key": "value"},
        ...
    }
    """
    STATS["webhooks_received"] += 1
    
    # Authentication check
    if REQUIRE_AUTH:
        auth_token = os.getenv(AUTH_TOKEN_ENV)
        provided_token = request.headers.get("Authorization", "").replace("Bearer ", "")
        
        if not auth_token or provided_token != auth_token:
            log_action("Unauthorized webhook request", "WARNING")
            return jsonify({"error": "Unauthorized"}), 401
    
    # Parse webhook payload
    try:
        payload = request.get_json()
        
        if not payload:
            log_action("Empty webhook payload", "WARNING")
            return jsonify({"error": "Empty payload"}), 400
        
        # Extract alert data (adapt to Grafana's webhook format)
        alert_data = {
            "alert_name": payload.get("ruleName", payload.get("title", "Unknown")),
            "state": payload.get("state", "unknown"),
            "message": payload.get("message", ""),
            "labels": payload.get("labels", {}),
            "value": payload.get("value"),
            "threshold": payload.get("threshold"),
            "raw_payload": payload
        }
        
        log_action(f"Received webhook: {json.dumps(alert_data, indent=2)}", "DEBUG")
        
        # Process alert and execute actions
        results = process_alert(alert_data)
        
        return jsonify({
            "status": "processed",
            "results": results
        }), 200
        
    except Exception as e:
        log_action(f"Error processing webhook: {str(e)}", "ERROR")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Physical Control Webhook Receiver")
    logger.info("=" * 60)
    logger.info(f"Configuration: {CONFIG_FILE}")
    logger.info(f"Alerts configured: {len(CONFIG.get('alerts', []))}")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"Authentication: {'Enabled' if REQUIRE_AUTH else 'Disabled'}")
    logger.info("=" * 60)
    
    # Create log directory if needed
    if LOG_FILE:
        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    
    # Start Flask server
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
