#!/usr/bin/env python3
# ================================================================================
# MATRIX BLAST — Web UI for WLED scrolling text
# ================================================================================
# Simple FastAPI service that lets operators type messages into a browser form
# and blast them to one or more WLED matrix signs via MQTT.
#
# Endpoints:
#   GET  /        Render the blast form
#   POST /blast   Publish text to the selected sign's MQTT topic
#   GET  /health  Health check
#
# Signs are defined in config.yaml — add entries there for each new matrix.
# ================================================================================

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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

BROKER    = os.getenv("BROKER", "localhost")
PORT      = int(os.getenv("MQTT_PORT", "1883"))
SHOWSITE  = os.getenv("SHOWSITE_NAME", "demo_showsite")

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
    with open(CONFIG_FILE) as f:
        raw = yaml.safe_load(f)
    return expand_env(raw)


config = load_config()
SIGNS = {s["id"]: s for s in config.get("signs", [])}

# ============================================================================
# MQTT client (persistent connection, shared across requests)
# ============================================================================

mqtt_client = mqtt.Client(client_id="dpx_matrix_blast")


def mqtt_connect():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            log.info(f"MQTT connected to {BROKER}:{PORT}")
        else:
            log.error(f"MQTT connect failed (rc={rc})")

    def on_disconnect(client, userdata, rc):
        if rc != 0:
            log.warning(f"MQTT unexpected disconnect (rc={rc})")

    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    try:
        mqtt_client.connect(BROKER, PORT, keepalive=60)
        mqtt_client.loop_start()
    except Exception as e:
        log.error(f"MQTT connection failed: {e}")


def mqtt_disconnect():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


# ============================================================================
# FastAPI app
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Matrix Blast starting — signs: {list(SIGNS.keys())}")
    mqtt_connect()
    yield
    mqtt_disconnect()
    log.info("Matrix Blast stopped")


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "signs": list(SIGNS.values())},
    )


@app.post("/blast", response_class=HTMLResponse)
async def blast(
    request: Request,
    sign_id: str  = Form(...),
    text:    str  = Form(...),
    r:       int  = Form(255),
    g:       int  = Form(220),
    b:       int  = Form(0),
    speed:   int  = Form(255),
    ttl:     int  = Form(30),
):
    sign = SIGNS.get(sign_id)
    if not sign:
        return HTMLResponse(f'<span class="status-err">Unknown sign: {sign_id}</span>')

    text = text.strip()
    if not text:
        return HTMLResponse('<span class="status-err">Message cannot be empty.</span>')

    payload = json.dumps({
        "text":  text,
        "color": [max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))],
        "speed": max(0, min(255, speed)),
        "ttl":   max(1, ttl),
    })

    try:
        result = mqtt_client.publish(sign["topic"], payload, qos=0)
        result.wait_for_publish(timeout=3.0)
        log.info(f"[blast] sign={sign_id} text={text!r} → {sign['topic']}")
        return HTMLResponse(f'<span class="status-ok">✓ Sent to {sign["name"]}</span>')
    except Exception as e:
        log.error(f"[blast] MQTT publish failed: {e}")
        return HTMLResponse(f'<span class="status-err">✗ MQTT error: {e}</span>')


@app.get("/health")
async def health():
    return {"status": "ok", "signs": list(SIGNS.keys())}
