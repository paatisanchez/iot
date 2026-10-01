import copy
import json
import time
from html import escape

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Smart Hospital IoT Demo",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ROOM_ID = "204"
PATIENT_ID = "P12"

# ============================================================
# GLOBAL STYLE (injected once per run)
# ============================================================

GLOBAL_CSS = """
<style>
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
}
.block-container { padding-top: 1.4rem; max-width: 1400px; }
.hero {
    background: linear-gradient(120deg, #0f172a, #1e3a8a 55%, #0e7490);
    color: white; border-radius: 20px; padding: 24px 30px; margin-bottom: 15px;
}
.hero h1 { margin: 0; padding: 0; color: white; font-size: 1.8rem; font-weight: 800; }
.hero p { margin: 7px 0 13px; color: #cbd5e1; }
.badge {
    display: inline-block; background: rgba(255,255,255,.12);
    border: 1px solid rgba(255,255,255,.22); border-radius: 999px;
    padding: 3px 12px; margin: 0 6px 4px 0; font-size: .75rem;
}
.pipe { display: flex; gap: 6px; flex-wrap: wrap; margin: 5px 0 12px 0; }
.chip {
    flex: 1; min-width: 95px; text-align: center; padding: 9px 4px;
    border-radius: 10px; font-size: .68rem; font-weight: 700;
    letter-spacing: .04em; background: #f1f5f9; color: #94a3b8;
    border: 1px solid #e2e8f0;
}
.chip.done { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
.chip.active {
    background: #2563eb; color: white; border-color: #2563eb;
    box-shadow: 0 0 0 4px rgba(37,99,235,.15);
}
.chip.active.danger {
    background: #dc2626; border-color: #dc2626;
    box-shadow: 0 0 0 4px rgba(220,38,38,.15);
}
.term {
    background: #0b1220; color: #d1d5db; border-radius: 14px;
    padding: 12px 14px; min-height: 125px;
    font-family: ui-monospace, Menlo, Consolas, monospace;
    font-size: .78rem; line-height: 1.75;
}
.term .src { color: #38bdf8; font-weight: 700; }
.term .empty { color: #64748b; }
</style>

<div class="hero">
    <h1>🏥 Smart Hospital · Patient Monitoring & Room Automation</h1>
    <p>Interactive demonstration of the IoT + Digital Twin + AI architecture.</p>
    <span class="badge">Sensors → MQTT → Context</span>
    <span class="badge">Digital Twin</span>
    <span class="badge">AI estimation</span>
    <span class="badge">Decision & Control</span>
    <span class="badge">Actuation + Feedback</span>
</div>
"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ============================================================
# COMMON HELPERS
# ============================================================

def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def lerp(start, end, fraction):
    return start + (end - start) * fraction


def ease_out(fraction):
    return 1 - (1 - fraction) ** 2


def movement_text(value):
    if value > 0.65:
        return "HIGH"
    if value > 0.30:
        return "MEDIUM"
    if value > 0.10:
        return "LOW"
    return "NONE"


def pause(seconds):
    time.sleep(seconds / float(st.session_state.get("speed", 1)))


def add_log(logs, source, message):
    logs.append((source, message))


def log_html(logs, number=9):
    if not logs:
        return '<div class="term"><span class="empty">Waiting for demo…</span></div>'
    body = "<br>".join(
        f'<span class="src">{escape(src)}</span> → {escape(msg)}'
        for src, msg in logs[-number:]
    )
    return f'<div class="term">{body}</div>'


def pipeline_html(stages, active=None, danger=False):
    active_index = stages.index(active) if active in stages else -1
    chips = []
    for index, stage in enumerate(stages):
        css = "chip"
        if index == active_index:
            css += " active danger" if danger else " active"
        elif 0 <= active_index and index < active_index:
            css += " done"
        chips.append(f'<div class="{css}">{escape(stage)}</div>')
    return f'<div class="pipe">{"".join(chips)}</div>'


def draw_charts(slots, history, columns):
    if len(history) < 2:
        for slot in slots:
            slot.caption("Data will appear during the demo.")
        return
    df = pd.DataFrame(history).set_index("step")
    for slot, column in zip(slots, columns):
        slot.line_chart(df[[column]], height=190)


def make_chart_slots(title, titles):
    """Creates the row of bordered chart placeholders and returns the slots."""
    st.markdown(f"##### {title}")
    slots = []
    for column, chart_title in zip(st.columns(len(titles)), titles):
        with column, st.container(border=True):
            st.markdown(f"**{chart_title}**")
            slots.append(st.empty())
    return slots


def render_log_and_mqtt(log_slot, mqtt_slot, logs, mqtt, n_lines, empty_msg):
    log_slot.markdown(log_html(logs, n_lines), unsafe_allow_html=True)
    if mqtt:
        mqtt_slot.code(json.dumps(mqtt, indent=2), language="json")
    else:
        mqtt_slot.caption(empty_msg)


def render_probability_box(score, text_by_level):
    """Progress bar + coloured status box. text_by_level: (fn_name, text)."""
    st.progress(score)
    kind, text = text_by_level
    getattr(st, kind)(text)


# ============================================================
# ============================================================
# SLEEP SCENARIO
# ============================================================
# ============================================================

SLEEP_PREFS = {
    "sleep_temperature": 21.5,
    "sleep_light_lux": 60,
    "sleep_lights_pct": 5,
    "sleep_blinds_open_pct": 0,
}

SLEEP_INITIAL = {
    "patient": {
        "id": PATIENT_ID,
        "heart_rate": 82.0,
        "breathing_rate": 18.0,
        "movement": 0.90,
        "sleep_probability": 0.08,
        "sleep_state": "AWAKE",
    },
    "room": {
        "id": ROOM_ID,
        "temperature": 27.5,
        "lux": 820.0,
        "lights_pct": 80.0,
        "blinds_open_pct": 100.0,
        "ac_on": False,
        "ac_setpoint": None,
        "mode": "NORMAL",
    },
}

SLEEP_PIPELINE = [
    "SENSORS", "CONTEXT", "DIGITAL TWIN", "AI",
    "DECISION", "MQTT", "ACTUATION", "FEEDBACK",
]

# Final values reached by the adaptation animation
SLEEP_ROOM_TARGETS = {
    "temperature": 21.6,
    "lux": 40,
    "lights_pct": SLEEP_PREFS["sleep_lights_pct"],
    "blinds_open_pct": 0,
}
SLEEP_PATIENT_TARGETS = {"movement": 0.02, "heart_rate": 67, "breathing_rate": 14}


def estimate_sleep_state(state):
    patient, room = state["patient"], state["room"]

    movement_score = 1.0 - patient["movement"]
    heart_score = clamp(1.0 - abs(patient["heart_rate"] - 62.0) / 25.0)
    breathing_score = clamp(1.0 - abs(patient["breathing_rate"] - 13.0) / 8.0)
    light_score = clamp(1.0 - room["lux"] / 700.0)
    temperature_score = clamp(
        1.0 - abs(room["temperature"] - SLEEP_PREFS["sleep_temperature"]) / 6.0
    )

    probability = clamp(
        0.45 * movement_score
        + 0.25 * heart_score
        + 0.20 * breathing_score
        + 0.05 * light_score
        + 0.05 * temperature_score
    )

    if probability >= 0.80:
        label = "ASLEEP"
    elif probability >= 0.45:
        label = "DROWSY"
    else:
        label = "AWAKE"
    return probability, label


def sleep_decision(state):
    patient, room = state["patient"], state["room"]
    reasons = []

    if patient["sleep_state"] != "ASLEEP":
        if room["temperature"] > SLEEP_PREFS["sleep_temperature"] + 1:
            reasons.append("room too warm")
        if room["lux"] > SLEEP_PREFS["sleep_light_lux"] * 2:
            reasons.append("room too bright")

    if not reasons:
        return {"action": "NO_ACTION"}

    return {
        "action": "ACTIVATE_SLEEP_MODE",
        "temperature": SLEEP_PREFS["sleep_temperature"],
        "lights_pct": SLEEP_PREFS["sleep_lights_pct"],
        "blinds_open_pct": SLEEP_PREFS["sleep_blinds_open_pct"],
        "reasons": reasons,
    }


def sleep_mqtt_message(command):
    if command["action"] == "NO_ACTION":
        return None
    return {
        "topic": f"hospital/room/{ROOM_ID}/control",
        "payload": {
            "mode": "SLEEP_MODE",
            "lights_pct": command["lights_pct"],
            "blinds_open_pct": command["blinds_open_pct"],
            "hvac": {"enabled": True, "setpoint_c": command["temperature"]},
        },
    }


def sleep_twin_snapshot(state):
    p, r = state["patient"], state["room"]
    return {
        "roomId": ROOM_ID,
        "assignedPatient": PATIENT_ID,
        "patient": {
            "heartRate_bpm": round(p["heart_rate"], 1),
            "breathingRate_rpm": round(p["breathing_rate"], 1),
            "movement": movement_text(p["movement"]),
            "sleepState": p["sleep_state"],
            "sleepProbability": round(p["sleep_probability"], 2),
        },
        "room": {
            "temperature_C": round(r["temperature"], 1),
            "ambientLight_lux": round(r["lux"]),
            "lights_pct": round(r["lights_pct"]),
            "blindsOpen_pct": round(r["blinds_open_pct"]),
            "acOn": r["ac_on"],
            "acSetpoint_C": r["ac_setpoint"],
            "mode": r["mode"],
        },
    }


# ============================================================
# SLEEP ROOM HTML
# ============================================================

ROOM_CSS = """
<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; }
@keyframes floaty { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-7px); } }
.room { position: relative; height: 420px; overflow: hidden; border-radius: 22px;
        border: 1px solid #cbd5e1; box-shadow: 0 12px 35px rgba(0,0,0,.10); }
.floor { position: absolute; left: 0; bottom: 0; width: 100%; height: 27%;
         background: linear-gradient(180deg, #d8c5a7, #bea786); }
.shade { position: absolute; inset: 0; background: #0b1026; pointer-events: none; z-index: 15; }
.pill { position: absolute; background: white; padding: 8px 13px; border-radius: 12px;
        font-weight: 700; font-size: 13px; z-index: 20; }
.window { position: absolute; top: 80px; left: 35px; width: 200px; height: 160px;
          border: 10px solid white; overflow: hidden;
          background: linear-gradient(#7dd3fc, #bae6fd); }
.blind { position: absolute; top: 0; left: 0; width: 100%; z-index: 5;
         background: repeating-linear-gradient(0deg, #9ca3af, #9ca3af 8px, #d1d5db 8px, #d1d5db 13px); }
.lamp { position: absolute; right: 60px; top: 40px; font-size: 50px; z-index: 16; }
.bed { position: absolute; left: 16%; bottom: 68px; width: 50%; height: 105px;
       background: #f8fafc; border: 4px solid #94a3b8; border-radius: 24px 24px 9px 9px;
       box-shadow: 0 8px 0 #64748b; }
.patient { position: absolute; left: 36%; bottom: 150px; z-index: 18; font-size: 72px; }
.patient-label { position: absolute; left: 38%; bottom: 128px; z-index: 19; background: white;
                 padding: 4px 11px; border-radius: 999px; font-size: 11px; font-weight: 800; }
.panel { position: absolute; z-index: 20; padding: 10px 12px; border-radius: 13px;
         background: rgba(255,255,255,.94); font-size: 12px; line-height: 1.7; }
.mode { position: absolute; left: 18px; bottom: 18px; z-index: 20; background: #111827;
        color: white; padding: 7px 12px; border-radius: 999px; font-size: 11px; font-weight: 750; }
</style>
"""

PATIENT_VISUALS = {
    "ASLEEP": ("😴", "none"),
    "DROWSY": ("🥱", "floaty 2s ease-in-out infinite"),
    "AWAKE": ("🧍", "floaty 1.1s ease-in-out infinite"),
}
MODE_ICONS = {"SLEEP MODE": "🌙", "ADAPTING": "⚙️"}


def sleep_room_html(state):
    patient, room = state["patient"], state["room"]

    darkness = 0.60 * clamp(1 - room["lux"] / 820.0)
    cool = clamp((27.5 - room["temperature"]) / 6.0)
    hue = 35 + cool * 175
    blinds_closed = 100 - room["blinds_open_pct"]
    lamp = clamp(room["lights_pct"] / 100.0)

    label = patient["sleep_state"]
    icon, animation = PATIENT_VISUALS.get(label, PATIENT_VISUALS["AWAKE"])

    if room["ac_on"]:
        ac = f"❄️ <b>A/C</b><br>ON · {room['ac_setpoint']:.1f} °C"
    else:
        ac = "⭕ <b>A/C</b><br>OFF"

    mode_icon = MODE_ICONS.get(room["mode"], "☀️")

    return f"""<!DOCTYPE html>
<html><head>{ROOM_CSS}</head><body>
<div class="room" style="background: hsl({hue:.0f}, 30%, 88%);">
  <div class="floor"></div>
  <div class="shade" style="opacity: {darkness:.2f};"></div>
  <div class="pill" style="top:16px; left:18px;">🏥 Room {ROOM_ID} · Patient {PATIENT_ID}</div>
  <div class="window"><div class="blind" style="height: {blinds_closed:.1f}%;"></div></div>
  <div class="lamp" style="opacity: {max(0.15, lamp):.2f};
       filter: drop-shadow(0 0 {lamp * 18:.0f}px #facc15);">💡</div>
  <div class="bed"></div>
  <div class="patient" style="animation: {animation};">{icon}</div>
  <div class="patient-label">{label}</div>
  <div class="panel" style="right:18px; top:110px;">
    🌡️ {room["temperature"]:.1f} °C<br>
    ☀️ {room["lux"]:.0f} lux<br>
    🪟 {room["blinds_open_pct"]:.0f}% open
  </div>
  <div class="panel" style="right:18px; bottom:60px; width:140px;">{ac}</div>
  <div class="mode">{mode_icon} {room["mode"]}</div>
</div>
</body></html>"""


# ============================================================
# ============================================================
# EMERGENCY SCENARIO
# ============================================================
# ============================================================

EMG = {
    "elevated_anomaly": 0.40,
    "high_anomaly": 0.75,
    "sustained_samples": 3,
    "recovered_hr": 100,
    "recovered_rr": 20,
    "recovered_anomaly": 0.25,
}

EMG_INITIAL = {
    "patient": {"heart_rate": 78.0, "breathing_rate": 16.0, "anomaly_score": 0.0},
    "clinical": {"status": "NORMAL", "severity": None},
    "alert": {"state": "IDLE", "red_light": False, "buzzer": False, "acknowledged_by": None},
}

EMG_PIPELINE = [
    "SENSORS", "CONTEXT", "DIGITAL TWIN", "AI",
    "DECISION", "ALERT SERVICE", "MQTT", "STAFF DEVICE",
]

# Piecewise-linear risk curves: (vital value) -> risk in [0, 1].
# Values outside the range are clamped to the end points.
_HR_POINTS = ([40, 60, 90, 110, 130], [1.0, 0.0, 0.0, 0.5, 1.0])
_RR_POINTS = ([8, 12, 20, 25], [1.0, 0.0, 0.0, 1.0])


def heart_rate_risk(hr):
    return float(np.interp(hr, *_HR_POINTS))


def breathing_rate_risk(rr):
    return float(np.interp(rr, *_RR_POINTS))


def anomaly_score(state):
    """One very abnormal vital OR two moderate ones raise the total score."""
    patient = state["patient"]
    hr_risk = heart_rate_risk(patient["heart_rate"])
    rr_risk = breathing_rate_risk(patient["breathing_rate"])
    return clamp(1.0 - (1.0 - hr_risk) * (1.0 - rr_risk))


def anomaly_level(score):
    """Classifies an anomaly score as LOW / ELEVATED / HIGH (single source of truth)."""
    if score >= EMG["high_anomaly"]:
        return "HIGH"
    if score >= EMG["elevated_anomaly"]:
        return "ELEVATED"
    return "LOW"


def update_sustained(sustained, score):
    """Consecutive samples with a HIGH anomaly; any lower sample resets the count."""
    return sustained + 1 if score >= EMG["high_anomaly"] else 0


def emergency_decision(state, sustained):
    """Final clinical decision: only a SUSTAINED high anomaly raises an alert."""
    score = state["patient"]["anomaly_score"]
    if score >= EMG["high_anomaly"] and sustained >= EMG["sustained_samples"]:
        return {"alert": True, "severity": "HIGH"}
    return {"alert": False, "severity": None}


def recovery_decision(state):
    """The alert can only be resolved when all recovery thresholds are met."""
    p = state["patient"]
    recovered = (
        p["heart_rate"] <= EMG["recovered_hr"]
        and p["breathing_rate"] <= EMG["recovered_rr"]
        and p["anomaly_score"] <= EMG["recovered_anomaly"]
    )
    return {"recovered": recovered}


def emergency_mqtt(command):
    payloads = {
        "ACTIVATE": {
            "command": "ACTIVATE", "patientId": PATIENT_ID, "roomId": ROOM_ID,
            "severity": "HIGH", "redLight": "ON", "buzzer": "ON",
        },
        "SILENCE": {"command": "SILENCE", "redLight": "ON", "buzzer": "OFF"},
        "RESET": {"command": "RESET", "redLight": "OFF", "buzzer": "OFF"},
    }
    if command not in payloads:
        return None
    return {"topic": "hospital/staff-office/alert-device", "payload": payloads[command]}


def emergency_twin_snapshot(state):
    p, c, a = state["patient"], state["clinical"], state["alert"]
    return {
        "roomId": ROOM_ID,
        "assignedPatient": PATIENT_ID,
        "patient": {
            "heartRate_bpm": round(p["heart_rate"], 1),
            "breathingRate_rpm": round(p["breathing_rate"], 1),
            "AI_anomalyScore": round(p["anomaly_score"], 2),
        },
        "clinical": {"status": c["status"], "severity": c["severity"]},
        "alert": {
            "state": a["state"],
            "redLight": a["red_light"],
            "buzzer": a["buzzer"],
            "acknowledgedBy": a["acknowledged_by"],
        },
    }


# ============================================================
# EMERGENCY HTML
# ============================================================

EMG_CSS = """
<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: .25; } }
@keyframes beat { 0%, 100% { transform: scale(1); } 15% { transform: scale(1.09); } }
.wrap { display: grid; grid-template-columns: 1.5fr .8fr; gap: 16px; }
.monitor { height: 390px; border-radius: 22px; padding: 22px;
           background: linear-gradient(145deg, #111827, #020617); color: white; overflow: hidden; }
.header { display: flex; justify-content: space-between; align-items: center;
          border-bottom: 1px solid #374151; padding-bottom: 12px; font-weight: 800; }
.tag { padding: 5px 10px; border-radius: 999px; background: #1f2937; font-size: 12px; }
.vitals { margin-top: 26px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.label { color: #9ca3af; font-size: 12px; text-transform: uppercase; }
.value { font-size: 48px; font-weight: 800; display: inline-block; }
.unit { font-size: 15px; color: #9ca3af; }
.anomaly { margin-top: 30px; padding: 15px; border-radius: 12px; background: rgba(255,255,255,.07); }
.track { margin-top: 8px; height: 12px; background: #374151; border-radius: 999px; overflow: hidden; }
.fill { height: 100%; }
.device { height: 390px; border-radius: 22px; background: #f9fafb; border: 1px solid #d1d5db;
          display: flex; flex-direction: column; align-items: center; justify-content: center;
          text-align: center; color: #111827; }
.light { width: 90px; height: 90px; border-radius: 50%; border: 6px solid #d1d5db; margin: 25px 0; }
.state { margin-top: 20px; background: #111827; color: white; padding: 7px 12px;
         border-radius: 999px; font-size: 12px; font-weight: 800; }
</style>
"""


def emergency_html(state):
    patient, alert = state["patient"], state["alert"]
    hr, rr, anomaly = patient["heart_rate"], patient["breathing_rate"], patient["anomaly_score"]

    beat_duration = 60.0 / max(hr, 30.0)

    vital_color = {"HIGH": "#f87171", "ELEVATED": "#fbbf24", "LOW": "#4ade80"}[
        anomaly_level(anomaly)
    ]

    if alert["red_light"]:
        light_color = "#ef4444"
        light_glow = "0 0 18px #ef4444, 0 0 40px rgba(239,68,68,.65)"
    else:
        light_color = "#6b7280"
        light_glow = "none"

    blinking = alert["state"] == "ACTIVE" and alert["red_light"]
    light_animation = "blink .7s infinite" if blinking else "none"

    buzzer_icon = "🔊" if alert["buzzer"] else "🔇"
    buzzer_text = "BUZZER ON" if alert["buzzer"] else "BUZZER OFF"

    return f"""<!DOCTYPE html>
<html><head>{EMG_CSS}</head><body>
<div class="wrap">
  <div class="monitor">
    <div class="header">
      <span>🫀 Patient monitor</span>
      <span class="tag">Room {ROOM_ID} · Patient {PATIENT_ID}</span>
    </div>
    <div class="vitals">
      <div>
        <div class="label">❤️ Heart rate</div>
        <span class="value" style="color:{vital_color}; animation: beat {beat_duration:.2f}s infinite;">{hr:.0f}</span>
        <span class="unit">bpm</span>
      </div>
      <div>
        <div class="label">🫁 Breathing rate</div>
        <span class="value" style="color:{vital_color};">{rr:.0f}</span>
        <span class="unit">rpm</span>
      </div>
    </div>
    <div class="anomaly">
      <b>AI anomaly score: {anomaly * 100:.0f}%</b>
      <div class="track">
        <div class="fill" style="width:{anomaly * 100:.1f}%; background:{vital_color};"></div>
      </div>
    </div>
  </div>
  <div class="device">
    <b>🚨 Medical staff office<br>Alert device</b>
    <div class="light" style="background:{light_color}; box-shadow:{light_glow}; animation:{light_animation};"></div>
    <div style="font-size:55px;">{buzzer_icon}</div>
    <div style="font-size:11px; font-weight:800; color:#475569;">{buzzer_text}</div>
    <div class="state">{alert["state"]}</div>
  </div>
</div>
</body></html>"""


# ============================================================
# SESSION STATE
# ============================================================

def fresh_sleep():
    return {
        "state": copy.deepcopy(SLEEP_INITIAL),
        "logs": [], "history": [], "mqtt": None,
        "decision": "WAITING", "stage": None,
    }


def fresh_emergency():
    return {
        "state": copy.deepcopy(EMG_INITIAL),
        "logs": [], "history": [], "mqtt": None,
        "phase": "IDLE", "stage": None,
    }


if "sleep" not in st.session_state:
    st.session_state.sleep = fresh_sleep()
if "emg" not in st.session_state:
    st.session_state.emg = fresh_emergency()


# ============================================================
# TOP SCENARIO SELECTOR
# ============================================================

top_left, top_right = st.columns([3, 1])

scenario = top_left.radio(
    "Choose demo scenario",
    ["🌙 Sleep-Aware Room Adaptation", "🚨 Medical Emergency"],
    horizontal=True,
    label_visibility="collapsed",
    key="scenario_selector",
)

top_right.select_slider(
    "Demo speed",
    options=[0.5, 1, 2, 4],
    value=1,
    key="speed",
    format_func=lambda value: f"{value}×",
)


# ============================================================
# ============================================================
# SLEEP VIEW
# ============================================================
# ============================================================

def sleep_view():
    S = st.session_state.sleep

    st.info(
        "Patient P12 is awake while Room 204 is too warm "
        "and too bright. The system adapts the room until "
        "the AI estimates that the patient is asleep."
    )

    b1, b2 = st.columns(2)
    start = b1.button("▶ Start sleep demo", type="primary",
                      use_container_width=True, key="start_sleep")
    reset = b2.button("↻ Reset", use_container_width=True, key="reset_sleep")

    if reset:
        st.session_state.sleep = fresh_sleep()
        st.rerun()

    pipe = st.empty()
    left, right = st.columns([1.15, 1], gap="large")

    with left:
        with st.container(border=True):
            st.markdown("##### 🏨 Room 204")
            room_slot = st.empty()
        st.markdown("##### 📡 Architecture event log")
        log_slot = st.empty()
        st.markdown("##### 📨 MQTT command")
        mqtt_slot = st.empty()

    with right:
        with st.container(border=True):
            st.markdown("##### 🪞 Live digital twin")
            metrics_slot = st.empty()
        with st.container(border=True):
            ai_slot = st.empty()
        with st.container(border=True):
            decision_slot = st.empty()
        with st.container(border=True):
            st.markdown("##### 🚨 Clinical alert service")
            st.success("🟢 IDLE — no clinical emergency detected")
            st.caption("This scenario concerns room comfort and sleep.")
        with st.expander("Digital twin snapshot (JSON)"):
            twin_slot = st.empty()

    chart_slots = make_chart_slots(
        "📈 Physical state evolution",
        ["Temperature (°C)", "Ambient light (lux)", "Sleep probability (%)"],
    )

    # ---------------------------------------------------------
    # RENDER
    # ---------------------------------------------------------
    def render(active=None):
        if active is not None:
            S["stage"] = active

        state = S["state"]
        patient, room = state["patient"], state["room"]

        pipe.markdown(pipeline_html(SLEEP_PIPELINE, S["stage"]), unsafe_allow_html=True)

        with room_slot.container():
            components.html(sleep_room_html(state), height=435, scrolling=False)

        with metrics_slot.container():
            m1, m2 = st.columns(2)
            with m1:
                st.metric("🌡 Temperature", f"{room['temperature']:.1f} °C")
                st.caption(f"Target: {SLEEP_PREFS['sleep_temperature']} °C")
                st.metric("☀️ Ambient light", f"{room['lux']:.0f} lux")
                st.caption(f"Target: ≤ {SLEEP_PREFS['sleep_light_lux']} lux")
            with m2:
                st.metric("❤️ Heart rate", f"{patient['heart_rate']:.0f} bpm")
                st.metric("🫁 Breathing rate", f"{patient['breathing_rate']:.0f} rpm")
                st.metric("🚶 Movement", movement_text(patient["movement"]))

        with ai_slot.container():
            st.markdown("##### 🤖 AI sleep-state estimate")
            probability = patient["sleep_probability"]
            text = f"{patient['sleep_state']} — {probability * 100:.0f}% probability"
            level = {
                "ASLEEP": ("success", "😴 " + text),
                "DROWSY": ("warning", "🥱 " + text),
            }.get(patient["sleep_state"], ("info", "👁️ " + text))
            render_probability_box(probability, level)
            st.caption(
                "The AI estimates the patient's state. "
                "It does not directly control the room."
            )

        with decision_slot.container():
            st.markdown("##### 🧠 Decision & control service")
            decision = S["decision"]
            if decision == "WAITING":
                st.info("Waiting for contextualised data.")
            elif decision == "ADAPT":
                st.warning("🌙 Sleep-aware adaptation activated")
                st.write("🪟 Close blinds · 💡 Dim lighting · ❄️ Cool room to 21.5 °C")
            elif decision == "ADAPTING":
                st.info("⚙️ Room adaptation in progress…")
            elif decision == "ASLEEP":
                st.success("✅ Sleep conditions reached — maintaining Sleep Mode targets.")

        render_log_and_mqtt(log_slot, mqtt_slot, S["logs"], S["mqtt"], 8,
                            "No control command published yet.")
        twin_slot.json(sleep_twin_snapshot(state), expanded=True)
        draw_charts(chart_slots, S["history"],
                    ["Temperature", "Ambient light", "Sleep probability"])

    # ---------------------------------------------------------
    # RUN
    # ---------------------------------------------------------
    def run():
        state = copy.deepcopy(SLEEP_INITIAL)
        S.update(state=state, logs=[], history=[], mqtt=None,
                 decision="WAITING", stage=None)

        logs = S["logs"]
        patient, room = state["patient"], state["room"]

        def update_ai():
            probability, label = estimate_sleep_state(state)
            patient["sleep_probability"] = probability
            patient["sleep_state"] = label
            return probability, label

        def record(step, probability):
            S["history"].append({
                "step": step,
                "Temperature": room["temperature"],
                "Ambient light": room["lux"],
                "Sleep probability": probability * 100,
            })

        def stage(name, message, delay, source=None):
            add_log(logs, source or name, message)
            render(name)
            pause(delay)

        probability, label = update_ai()
        record(0, probability)

        stage("SENSORS",
              f"HR={patient['heart_rate']:.0f} bpm | "
              f"RR={patient['breathing_rate']:.0f} rpm | "
              f"movement={movement_text(patient['movement'])} | "
              f"{room['temperature']:.1f}°C | {room['lux']:.0f} lux", 1.1)
        stage("CONTEXT",
              f"Measurements mapped to Patient {PATIENT_ID} in Room {ROOM_ID}.", 0.9)
        stage("DIGITAL TWIN", "Patient-room state synchronised.", 0.9)
        stage("AI", f"Patient state={label} | probability={probability * 100:.0f}%", 1.0)

        command = sleep_decision(state)

        if command["action"] == "NO_ACTION":
            add_log(logs, "DECISION", "No room adaptation required.")
            render("DECISION")
            return

        S["decision"] = "ADAPT"
        stage("DECISION",
              "Patient awake + " + " + ".join(command["reasons"]) + " → activate Sleep Mode.",
              1.1)

        S["mqtt"] = sleep_mqtt_message(command)
        room["mode"] = "ADAPTING"
        stage("MQTT", "Sleep Mode command published.", 0.9)

        room["ac_on"] = True
        room["ac_setpoint"] = SLEEP_PREFS["sleep_temperature"]
        S["decision"] = "ADAPTING"

        initial_room = dict(room)
        initial_patient = dict(patient)
        steps = 24

        for step in range(1, steps + 1):
            easing = ease_out(step / steps)

            for key, target in SLEEP_ROOM_TARGETS.items():
                room[key] = lerp(initial_room[key], target, easing)
            for key, target in SLEEP_PATIENT_TARGETS.items():
                patient[key] = lerp(initial_patient[key], target, easing)

            previous_state = patient["sleep_state"]
            probability, label = update_ai()
            record(step, probability)

            if step == 1:
                add_log(logs, "ACTUATION", "A/C ON | lights dimming | blinds closing.")
            if step == 8:
                add_log(logs, "FEEDBACK", "Actuator state returned through MQTT.")
            if label != previous_state:
                add_log(logs, "AI",
                        f"State change {previous_state} → {label} ({probability * 100:.0f}%).")
            if label == "ASLEEP":
                S["decision"] = "ASLEEP"

            render("ACTUATION" if step < 10 else "FEEDBACK")
            pause(0.28)

        room["mode"] = "SLEEP MODE"
        S["decision"] = "ASLEEP"
        add_log(logs, "SYSTEM", "Patient asleep. Sleep Mode maintained.")
        render("FEEDBACK")

    if start:
        run()
    else:
        render()


# ============================================================
# ============================================================
# EMERGENCY VIEW
# ============================================================
# ============================================================

DANGER_PHASES = {"ESCALATING", "ACTIVE", "ACKNOWLEDGED", "RECOVERING"}

# alert state -> (streamlit box, headline, detail line)
ALERT_PANELS = {
    "IDLE": ("success", "🟢 IDLE", None),
    "ACTIVE": ("error", "🔴 ACTIVE",
               "🔴 Red warning light: **ON** · 🔊 Buzzer: **ON**"),
    "ACKNOWLEDGED": ("warning", "🟠 ACKNOWLEDGED",
                     "🔴 Red warning light: **ON** · 🔇 Buzzer: **OFF**"),
    "RESOLVED": ("success", "✅ RESOLVED",
                 "⚫ Red warning light: **OFF** · 🔇 Buzzer: **OFF**"),
}


def emergency_view():
    E = st.session_state.emg

    st.warning("⚠️ Synthetic demo values only. Thresholds are not intended for clinical use.")
    st.info(
        "The patient develops abnormal vital signs. "
        "The AI detects the anomaly, the Decision Service "
        "raises a clinical alert after sustained abnormality, "
        "and the physical staff alarm is activated."
    )

    b1, b2, b3, b4 = st.columns(4)
    start = b1.button("▶ Start emergency", type="primary", use_container_width=True,
                      disabled=E["phase"] not in ("IDLE", "RESOLVED"),
                      key="start_emergency")
    acknowledge_button = b2.button("✓ Acknowledge", use_container_width=True,
                                   disabled=E["phase"] != "ACTIVE",
                                   key="ack_emergency")
    recovery_button = b3.button("♡ Simulate recovery", use_container_width=True,
                                disabled=E["phase"] != "ACKNOWLEDGED",
                                key="recovery_emergency")
    reset = b4.button("↻ Reset", use_container_width=True, key="reset_emergency")

    if reset:
        st.session_state.emg = fresh_emergency()
        st.rerun()

    pipe = st.empty()
    left, right = st.columns([1.15, 1], gap="large")

    with left:
        with st.container(border=True):
            st.markdown("##### 🏥 Patient & physical alert")
            monitor_slot = st.empty()
        st.markdown("##### 📡 Architecture event log")
        log_slot = st.empty()
        st.markdown("##### 📨 MQTT command")
        mqtt_slot = st.empty()

    with right:
        with st.container(border=True):
            st.markdown("##### 🪞 Live digital twin")
            metrics_slot = st.empty()
        with st.container(border=True):
            ai_slot = st.empty()
        with st.container(border=True):
            decision_slot = st.empty()
        with st.container(border=True):
            alert_slot = st.empty()
        with st.expander("Digital twin snapshot (JSON)"):
            twin_slot = st.empty()

    chart_slots = make_chart_slots(
        "📈 Patient state evolution",
        ["Heart rate (bpm)", "Breathing rate (rpm)", "AI anomaly score (%)"],
    )

    # ---------------------------------------------------------
    # RENDER
    # ---------------------------------------------------------
    def render(active=None):
        if active is not None:
            E["stage"] = active

        state = E["state"]
        patient, alert = state["patient"], state["alert"]

        pipe.markdown(
            pipeline_html(EMG_PIPELINE, E["stage"], danger=E["phase"] in DANGER_PHASES),
            unsafe_allow_html=True,
        )

        with monitor_slot.container():
            components.html(emergency_html(state), height=405, scrolling=False)

        with metrics_slot.container():
            m1, m2 = st.columns(2)
            m1.metric("❤️ Heart rate", f"{patient['heart_rate']:.0f} bpm")
            m2.metric("🫁 Breathing rate", f"{patient['breathing_rate']:.0f} rpm")

        with ai_slot.container():
            st.markdown("##### 🤖 AI anomaly detection")
            score = patient["anomaly_score"]
            level = {
                "HIGH": ("error", f"⚠️ HIGH anomaly — {score * 100:.0f}%"),
                "ELEVATED": ("warning", f"Elevated anomaly — {score * 100:.0f}%"),
                "LOW": ("success", f"Low anomaly — {score * 100:.0f}%"),
            }[anomaly_level(score)]
            render_probability_box(score, level)
            st.caption(
                "The AI estimates abnormality. "
                "The Decision Service makes the final alert decision."
            )

        with decision_slot.container():
            st.markdown("##### 🧠 Decision & control service")
            phase = E["phase"]
            if phase == "IDLE":
                st.success("Patient state considered normal.")
            elif phase == "ESCALATING":
                st.warning("Monitoring abnormal physiological trend…")
            elif phase in ("ACTIVE", "ACKNOWLEDGED"):
                st.error("🚨 FINAL DECISION: HIGH severity clinical alert")
                st.write(f"**Patient:** {PATIENT_ID} · **Room:** {ROOM_ID}")
            elif phase == "RECOVERING":
                st.warning("Monitoring recovery…")
            elif phase == "RESOLVED":
                st.success("✅ Patient condition returned to the configured normal range.")

        with alert_slot.container():
            st.markdown("##### 🚨 Clinical alert lifecycle service")
            kind, headline, detail = ALERT_PANELS.get(alert["state"], ALERT_PANELS["IDLE"])
            getattr(st, kind)(headline)
            if detail:
                st.write(detail)

        render_log_and_mqtt(log_slot, mqtt_slot, E["logs"], E["mqtt"], 9,
                            "No alert-device command published yet.")
        twin_slot.json(emergency_twin_snapshot(state), expanded=True)
        draw_charts(chart_slots, E["history"],
                    ["Heart rate", "Breathing rate", "Anomaly score"])

    # ---------------------------------------------------------
    # HISTORY
    # ---------------------------------------------------------
    def add_history(state, step):
        p = state["patient"]
        E["history"].append({
            "step": step,
            "Heart rate": p["heart_rate"],
            "Breathing rate": p["breathing_rate"],
            "Anomaly score": p["anomaly_score"] * 100,
        })

    # ---------------------------------------------------------
    # START EMERGENCY
    # ---------------------------------------------------------
    def run_emergency():
        state = copy.deepcopy(EMG_INITIAL)
        E.update(state=state, logs=[], history=[], mqtt=None,
                 phase="ESCALATING", stage=None)

        logs = E["logs"]
        patient = state["patient"]

        def stage(name, message, delay=None, source=None):
            add_log(logs, source or name, message)
            render(name)
            if delay:
                pause(delay)

        add_history(state, 0)
        stage("SENSORS", "HR=78 bpm | RR=16 rpm | patient initially stable.", 1.0)
        stage("CONTEXT",
              f"Measurements mapped to Patient {PATIENT_ID} / Room {ROOM_ID}.", 0.8)
        stage("DIGITAL TWIN", "Initial patient state synchronised.", 0.8)

        # Escalation
        sustained = 0
        elevated_logged = False

        for step in range(1, 21):
            easing = (step / 20) ** 1.25
            patient["heart_rate"] = lerp(78, 148, easing)
            patient["breathing_rate"] = lerp(16, 28, easing)
            patient["anomaly_score"] = anomaly_score(state)
            score = patient["anomaly_score"]
            add_history(state, step)

            if step == 6:
                add_log(logs, "SENSORS", "Heart rate and breathing rate are rising.")

            if not elevated_logged and anomaly_level(score) != "LOW":
                add_log(logs, "AI", f"Elevated anomaly score ({score * 100:.0f}%).")
                elevated_logged = True

            sustained = update_sustained(sustained, score)

            render("SENSORS" if step < 8 else "DIGITAL TWIN" if step < 11 else "AI")
            pause(0.22)

            if sustained >= EMG["sustained_samples"]:
                add_log(logs, "AI",
                        f"High anomaly sustained for {sustained} samples "
                        f"(HR {patient['heart_rate']:.0f}, "
                        f"RR {patient['breathing_rate']:.0f}).")
                break

        # Final decision
        decision = emergency_decision(state, sustained)

        if not decision["alert"]:
            E["phase"] = "IDLE"
            add_log(logs, "DECISION", "No sustained anomaly — no alert.")
            render("DECISION")
            return

        state["clinical"].update(status="ABNORMAL", severity=decision["severity"])
        stage("DECISION", "HIGH severity clinical alert generated.", 0.9)

        state["alert"].update(state="ACTIVE", red_light=True, buzzer=True,
                              acknowledged_by=None)
        E["phase"] = "ACTIVE"
        stage("ALERT SERVICE", "Alert lifecycle state → ACTIVE.", 0.9)

        E["mqtt"] = emergency_mqtt("ACTIVATE")
        stage("MQTT", "ACTIVATE command published.", 0.9)

        stage("STAFF DEVICE", "Red light ON | buzzer ON.")

    # ---------------------------------------------------------
    # ACKNOWLEDGE
    # ---------------------------------------------------------
    def acknowledge():
        E["state"]["alert"].update(state="ACKNOWLEDGED", red_light=True,
                                   buzzer=False, acknowledged_by="Medical Staff")
        E["phase"] = "ACKNOWLEDGED"
        E["mqtt"] = emergency_mqtt("SILENCE")
        E["stage"] = "MQTT"

        logs = E["logs"]
        add_log(logs, "MEDICAL STAFF", "Alert acknowledged through dashboard.")
        add_log(logs, "ALERT SERVICE", "Alert lifecycle state → ACKNOWLEDGED.")
        add_log(logs, "MQTT",
                "SILENCE command → buzzer OFF, red light remains ON.")

    # ---------------------------------------------------------
    # RECOVERY
    # ---------------------------------------------------------
    def run_recovery():
        state = E["state"]
        patient, logs = state["patient"], E["logs"]

        def stage(name, message, delay=None):
            add_log(logs, name, message)
            render(name)
            if delay:
                pause(delay)

        E["phase"] = "RECOVERING"
        add_log(logs, "SYSTEM", "Recovery simulation started.")

        initial_hr = patient["heart_rate"]
        initial_rr = patient["breathing_rate"]
        base_step = len(E["history"])

        # The alert stays ACKNOWLEDGED (light ON) while the patient recovers.
        for index in range(1, 21):
            easing = ease_out(index / 20)
            patient["heart_rate"] = lerp(initial_hr, 82.0, easing)
            patient["breathing_rate"] = lerp(initial_rr, 17.0, easing)
            patient["anomaly_score"] = anomaly_score(state)
            add_history(state, base_step + index)

            if index == 4:
                add_log(logs, "SENSORS", "Heart rate and breathing rate decreasing.")
            if index == 10:
                add_log(logs, "DIGITAL TWIN", "Recovery state synchronised.")
            if index == 16:
                add_log(logs, "AI", "Anomaly score returning towards normal range.")

            render("SENSORS" if index < 7 else "DIGITAL TWIN" if index < 14 else "AI")
            pause(0.23)

        # Force final normal values
        patient["heart_rate"] = 82.0
        patient["breathing_rate"] = 17.0
        patient["anomaly_score"] = anomaly_score(state)
        add_history(state, base_step + 21)

        if not recovery_decision(state)["recovered"]:
            E["phase"] = "ACKNOWLEDGED"
            stage("DECISION",
                  "Recovery thresholds not met — alert stays ACKNOWLEDGED.")
            return

        state["clinical"].update(status="NORMAL", severity=None)
        stage("DECISION",
              "Patient condition returned to the configured normal range.", 0.8)

        state["alert"].update(state="RESOLVED", red_light=False, buzzer=False)
        E["phase"] = "RESOLVED"
        stage("ALERT SERVICE", "Alert lifecycle state → RESOLVED.", 0.8)

        E["mqtt"] = emergency_mqtt("RESET")
        stage("MQTT", "RESET command published → red light OFF | buzzer OFF.", 0.8)

        # Explicit reset so the physical device can't inherit an old ACTIVE state
        state["alert"]["red_light"] = False
        state["alert"]["buzzer"] = False
        stage("STAFF DEVICE", "Alert device reset → red light OFF | buzzer OFF.")

    # ---------------------------------------------------------
    # BUTTON EVENTS
    # ---------------------------------------------------------
    if start:
        run_emergency()
        st.rerun()
    if acknowledge_button:
        acknowledge()
        st.rerun()
    if recovery_button:
        run_recovery()
        st.rerun()

    render()


# ============================================================
# ROUTER
# ============================================================

if scenario.startswith("🌙"):
    sleep_view()
else:
    emergency_view()


# ============================================================
# EXPLANATION
# ============================================================

st.divider()

with st.expander("🧠 Architecture logic"):
    st.markdown(
        """
### Common architecture

Both scenarios reuse the same main architectural flow:

**Sensors → MQTT → Context Service → Digital Twin → AI → Decision Service**

The two scenarios then follow different branches.

---

### 🌙 Sleep-aware adaptation

The AI estimates:

**AWAKE → DROWSY → ASLEEP**

using mainly:

- movement;
- heart rate;
- breathing rate.

Room conditions are also considered, but with a lower weight.

The **Decision & Control Service**, not the AI, decides whether the room should be adapted.

If the patient is awake while the room is too warm or too bright, the system sends commands to:

- close the blinds;
- dim the lights;
- activate the A/C.

Actuator feedback updates the Digital Twin again.

---

### 🚨 Medical emergency

The AI generates an **anomaly score** from heart rate and breathing rate.

A single abnormal sample does not immediately generate an alarm.

For this demo, a high anomaly must be sustained for several consecutive samples.

The **Decision & Control Service** then generates the final clinical alert.

The Clinical Alert Lifecycle Service manages:

**ACTIVE → ACKNOWLEDGED → RESOLVED**

#### ACTIVE

- Red warning light ON
- Buzzer ON

#### ACKNOWLEDGED

- Red warning light ON
- Buzzer OFF

Acknowledgement only means that medical staff have seen the alert.

#### RESOLVED

Once the simulated patient has recovered:

- Red warning light OFF
- Buzzer OFF
- MQTT RESET command is published.

---

### Responsibilities

A useful way to explain the architecture is:

**Sensors observe.  
The Digital Twin represents.  
AI analyses.  
The Decision Service decides.  
Actuators execute.**
"""
    )

with st.expander("⚠️ About the medical values"):
    st.markdown(
        """
All physiological thresholds and patient values used in the
medical-emergency scenario are **synthetic demo values**.

They are included only to demonstrate:

**sensor data → anomaly detection → decision → alert lifecycle → physical actuation**

They are not clinically validated and must not be interpreted as
medical guidance.
"""
    )
