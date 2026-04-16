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

import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
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
# Per-sign message queue
#
# Active message is protected for the first 50% of its TTL.  Any blasts that
# arrive during that window are enqueued and dispatched automatically once the
# lock expires, in order.
# ============================================================================

@dataclass
class ActiveMessage:
    text:    str
    sent_at: float
    ttl:     int

    def lock_expires_at(self) -> float:
        return self.sent_at + self.ttl * 0.5

    def lock_remaining(self) -> float:
        return max(0.0, self.lock_expires_at() - time.monotonic())


@dataclass
class PendingBlast:
    text:    str
    payload: str   # pre-serialised JSON
    ttl:     int


@dataclass
class SignState:
    active: ActiveMessage | None = None
    queue:  list[PendingBlast]   = field(default_factory=list)


# sign_id → SignState
_state: dict[str, SignState] = {}


def _sign_state(sign_id: str) -> SignState:
    if sign_id not in _state:
        _state[sign_id] = SignState()
    return _state[sign_id]


def _do_publish(sign: dict, blast: PendingBlast) -> None:
    """Fire-and-forget MQTT publish; raises on failure."""
    result = mqtt_client.publish(sign["topic"], blast.payload, qos=0)
    result.wait_for_publish(timeout=3.0)
    log.info(f"[blast] sign={sign['id']} text={blast.text!r} → {sign['topic']}")


async def _queue_worker() -> None:
    """Background task: drain queues as active-message locks expire."""
    while True:
        await asyncio.sleep(0.5)
        for sign_id, state in _state.items():
            if not state.active or not state.queue:
                continue
            if state.active.lock_remaining() > 0:
                continue
            # Lock expired — send next queued message
            nxt = state.queue.pop(0)
            sign = SIGNS[sign_id]
            try:
                _do_publish(sign, nxt)
                state.active = ActiveMessage(text=nxt.text, sent_at=time.monotonic(), ttl=nxt.ttl)
            except Exception as e:
                log.error(f"[queue_worker] publish failed for sign={sign_id}: {e}")

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
    worker = asyncio.create_task(_queue_worker())
    yield
    worker.cancel()
    mqtt_disconnect()
    log.info("Matrix Blast stopped")


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"signs": list(SIGNS.values())})


@app.post("/blast", response_class=HTMLResponse)
async def blast(
    request:   Request,
    sign_id:   str  = Form(...),
    text:      str  = Form(...),
    from_name: str  = Form(""),
    r:         int  = Form(255),
    g:         int  = Form(220),
    b:         int  = Form(0),
    speed:     int  = Form(255),
    ttl:       int  = Form(30),
):
    sign = SIGNS.get(sign_id)
    if not sign:
        return HTMLResponse(f'<span class="status-err">Unknown sign: {sign_id}</span>')

    text = text.strip()
    if not text:
        return HTMLResponse('<span class="status-err">Message cannot be empty.</span>')

    from_name = from_name.strip()
    if from_name:
        text = f"{from_name}: {text}"

    ttl = max(1, ttl)
    payload = json.dumps({
        "text":  text,
        "color": [max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))],
        "speed": max(0, min(255, speed)),
        "ttl":   ttl,
    })
    blast = PendingBlast(text=text, payload=payload, ttl=ttl)
    state = _sign_state(sign_id)

    # If the sign is locked, queue and return position
    if state.active and state.active.lock_remaining() > 0:
        state.queue.append(blast)
        pos = len(state.queue)
        log.info(f"[blast] queued pos={pos} sign={sign_id} text={text!r}")
        return HTMLResponse(f'<span class="status-ok">&#9654; Queued (#{pos})</span>')

    # Otherwise send immediately
    try:
        _do_publish(sign, blast)
        state.active = ActiveMessage(text=text, sent_at=time.monotonic(), ttl=ttl)
        return HTMLResponse(f'<span class="status-ok">✓ Sent to {sign["name"]}</span>')
    except Exception as e:
        log.error(f"[blast] MQTT publish failed: {e}")
        return HTMLResponse(f'<span class="status-err">✗ MQTT error: {e}</span>')


@app.get("/health")
async def health():
    return {"status": "ok", "signs": list(SIGNS.keys())}
