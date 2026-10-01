import copy
import json
import time
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Smart Hospital IoT Demo",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("🏥 Smart Hospital Patient Monitoring & Room Automation")

st.caption(
    "Interactive demonstration of the IoT + Digital Twin + AI architecture"
)


# ============================================================
# COMMON HELPERS
# ============================================================

ROOM_ID = "204"
PATIENT_ID = "P12"


def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def lerp(start, end, fraction):
    return start + (end - start) * fraction


def movement_text(value):
    if value > 0.65:
        return "HIGH"
    if value > 0.30:
        return "MEDIUM"
    if value > 0.10:
        return "LOW"
    return "NONE"


def add_log(logs, source, message):
    logs.append(f"{source} → {message}")


# ============================================================
# SCENARIO SELECTOR
# ============================================================

scenario = st.radio(
    "Choose demo scenario",
    [
        "🌙 Sleep-Aware Room Adaptation",
        "🚨 Medical Emergency",
    ],
    horizontal=True,
)

st.divider()


# ============================================================
# ============================================================
# SLEEP DEMO
# ============================================================
# ============================================================

SLEEP_PREFERENCES = {
    "sleep_temperature": 21.5,
    "sleep_light_lux": 60,
    "sleep_lights_pct": 5,
    "sleep_blinds_open_pct": 0,
}


SLEEP_INITIAL_STATE = {

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

    "alert": {
        "state": "IDLE",
    },
}


def estimate_sleep_state(state):

    patient = state["patient"]
    room = state["room"]

    movement_score = (
        1.0 - patient["movement"]
    )

    light_score = clamp(
        1.0 - room["lux"] / 700.0
    )

    temperature_score = clamp(
        1.0
        - abs(
            room["temperature"]
            - SLEEP_PREFERENCES["sleep_temperature"]
        ) / 6.0
    )

    heart_score = clamp(
        1.0
        - abs(
            patient["heart_rate"] - 68.0
        ) / 25.0
    )

    breathing_score = clamp(
        1.0
        - abs(
            patient["breathing_rate"] - 14.0
        ) / 8.0
    )

    probability = (
        0.40 * movement_score
        + 0.25 * light_score
        + 0.20 * temperature_score
        + 0.10 * heart_score
        + 0.05 * breathing_score
    )

    probability = clamp(probability)

    if probability >= 0.80:
        sleep_state = "ASLEEP"

    elif probability >= 0.45:
        sleep_state = "DROWSY"

    else:
        sleep_state = "AWAKE"

    return probability, sleep_state


def sleep_decision(state):

    room = state["room"]
    patient = state["patient"]

    too_hot = (
        room["temperature"]
        > SLEEP_PREFERENCES["sleep_temperature"] + 1
    )

    too_bright = (
        room["lux"]
        > SLEEP_PREFERENCES["sleep_light_lux"] * 2
    )

    if (
        patient["sleep_state"] != "ASLEEP"
        and (too_hot or too_bright)
    ):

        return {
            "action": "ACTIVATE_SLEEP_MODE",

            "temperature":
                SLEEP_PREFERENCES["sleep_temperature"],

            "lights_pct":
                SLEEP_PREFERENCES["sleep_lights_pct"],

            "blinds_open_pct":
                SLEEP_PREFERENCES["sleep_blinds_open_pct"],
        }

    return {
        "action": "NO_ACTION"
    }


def sleep_mqtt_message(command):

    if command["action"] == "NO_ACTION":
        return None

    return {
        "topic": f"hospital/room/{ROOM_ID}/control",

        "payload": {
            "mode": "SLEEP_MODE",

            "lights_pct":
                command["lights_pct"],

            "blinds_open_pct":
                command["blinds_open_pct"],

            "hvac": {
                "enabled": True,

                "setpoint_c":
                    command["temperature"],
            },
        },
    }


def sleep_twin_snapshot(state):

    return {

        "roomId":
            ROOM_ID,

        "assignedPatient":
            PATIENT_ID,

        "patient": {

            "heartRate_bpm":
                round(
                    state["patient"]["heart_rate"],
                    1
                ),

            "breathingRate_rpm":
                round(
                    state["patient"]["breathing_rate"],
                    1
                ),

            "movement":
                movement_text(
                    state["patient"]["movement"]
                ),

            "sleepState":
                state["patient"]["sleep_state"],

            "sleepProbability":
                round(
                    state["patient"]["sleep_probability"],
                    2
                ),
        },

        "room": {

            "temperature_C":
                round(
                    state["room"]["temperature"],
                    1
                ),

            "ambientLight_lux":
                round(
                    state["room"]["lux"]
                ),

            "lights_pct":
                round(
                    state["room"]["lights_pct"]
                ),

            "blindsOpen_pct":
                round(
                    state["room"]["blinds_open_pct"]
                ),

            "acOn":
                state["room"]["ac_on"],

            "acSetpoint_C":
                state["room"]["ac_setpoint"],

            "mode":
                state["room"]["mode"],
        },
    }


def sleep_room_html(state):

    patient = state["patient"]
    room = state["room"]

    brightness = clamp(
        room["lux"] / 820
    )

    blinds_closed = (
        100 - room["blinds_open_pct"]
    )

    light_intensity = clamp(
        room["lights_pct"] / 100
    )


    if patient["sleep_state"] == "ASLEEP":

        patient_icon = "😴"
        patient_label = "ASLEEP"
        patient_animation = "none"

    elif patient["sleep_state"] == "DROWSY":

        patient_icon = "🥱"
        patient_label = "DROWSY"
        patient_animation = "floaty 2s ease-in-out infinite"

    else:

        patient_icon = "🧍"
        patient_label = "AWAKE"
        patient_animation = "floaty 1.1s ease-in-out infinite"


    if room["ac_on"]:

        ac_state = (
            f"ON · {room['ac_setpoint']:.1f} °C"
        )

        ac_icon = "❄️"

    else:

        ac_state = "OFF"
        ac_icon = "⭕"


    if room["mode"] == "SLEEP MODE":
        mode_icon = "🌙"

    elif room["mode"] == "ADAPTING":
        mode_icon = "⚙️"

    else:
        mode_icon = "☀️"


    wall_lightness = int(
        72 + brightness * 23
    )


    return f"""
<!DOCTYPE html>

<html>

<head>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    padding: 0;

    background: transparent;

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Arial,
        sans-serif;
}}


@keyframes floaty {{

    0% {{
        transform: translateY(0px);
    }}

    50% {{
        transform: translateY(-7px);
    }}

    100% {{
        transform: translateY(0px);
    }}

}}


.room {{

    position: relative;

    width: 100%;
    height: 420px;

    overflow: hidden;

    border-radius: 22px;

    border:
        1px solid #d1d5db;

    background:
        hsl(
            42,
            34%,
            {wall_lightness}%
        );

    box-shadow:
        0 12px 35px
        rgba(0,0,0,.08);

}}


.floor {{

    position: absolute;

    bottom: 0;
    left: 0;

    width: 100%;
    height: 27%;

    background:
        linear-gradient(
            180deg,
            #d8c5a7,
            #bea786
        );

}}


.title {{

    position: absolute;

    top: 18px;
    left: 20px;

    z-index: 20;

    background: white;

    padding:
        9px 14px;

    border-radius: 12px;

    font-weight: 750;

}}


.window {{

    position: absolute;

    top: 80px;
    left: 35px;

    width: 220px;
    height: 170px;

    border:
        10px solid white;

    overflow: hidden;

    background: #bae6fd;

}}


.blind {{

    position: absolute;

    top: 0;
    left: 0;

    width: 100%;

    height:
        {blinds_closed:.1f}%;

    z-index: 5;

    background:
        repeating-linear-gradient(
            0deg,
            #9ca3af,
            #9ca3af 8px,
            #d1d5db 8px,
            #d1d5db 13px
        );

}}


.light {{

    position: absolute;

    right: 55px;
    top: 65px;

    font-size: 55px;

    opacity:
        {max(0.12, light_intensity)};

}}


.bed {{

    position: absolute;

    left: 20%;
    bottom: 68px;

    width: 57%;
    height: 105px;

    background: #f8fafc;

    border:
        4px solid #94a3b8;

    border-radius:
        24px 24px 9px 9px;

    box-shadow:
        0 8px 0 #64748b;

}}


.patient {{

    position: absolute;

    left: 44%;
    bottom: 155px;

    z-index: 8;

    font-size: 75px;

    animation:
        {patient_animation};

}}


.patient-label {{

    position: absolute;

    left: 45%;
    bottom: 132px;

    background: white;

    padding:
        5px 11px;

    border-radius: 999px;

    font-size: 11px;

    font-weight: 800;

}}


.sensor-panel {{

    position: absolute;

    right: 22px;
    top: 150px;

    padding:
        10px 12px;

    border-radius: 13px;

    background:
        rgba(255,255,255,.92);

    font-size: 12px;

    line-height: 1.7;

}}


.ac {{

    position: absolute;

    right: 22px;
    bottom: 70px;

    width: 160px;

    padding: 12px;

    border-radius: 13px;

    background: white;

    font-size: 12px;

}}


.mode {{

    position: absolute;

    left: 18px;
    bottom: 18px;

    background: #111827;

    color: white;

    padding:
        7px 12px;

    border-radius: 999px;

    font-size: 11px;

    font-weight: 750;

}}

</style>

</head>

<body>


<div class="room">


    <div class="floor"></div>


    <div class="title">

        🏥 Room {ROOM_ID}
        · Patient {PATIENT_ID}

    </div>


    <div class="window">

        <div class="blind"></div>

    </div>


    <div class="light">

        💡

    </div>


    <div class="bed"></div>


    <div class="patient">

        {patient_icon}

    </div>


    <div class="patient-label">

        {patient_label}

    </div>


    <div class="sensor-panel">

        🌡️ {room["temperature"]:.1f} °C

        <br>

        ☀️ {room["lux"]:.0f} lux

        <br>

        🪟 {room["blinds_open_pct"]:.0f}% open

    </div>


    <div class="ac">

        {ac_icon}
        <b>Air conditioning</b>

        <br><br>

        {ac_state}

    </div>


    <div class="mode">

        {mode_icon}
        {room["mode"]}

    </div>


</div>


</body>

</html>
"""


# ============================================================
# ============================================================
# EMERGENCY DEMO
# ============================================================
# ============================================================

EMERGENCY_THRESHOLDS = {
    "high_hr": 140,
    "high_rr": 27,
    "high_anomaly": 0.82,

    "recovered_hr": 95,
    "recovered_rr": 20,
    "recovered_anomaly": 0.25,
}


EMERGENCY_INITIAL_STATE = {

    "patient": {
        "heart_rate": 78.0,
        "breathing_rate": 16.0,
        "anomaly_score": 0.0,
    },

    "clinical": {
        "status": "NORMAL",
        "severity": None,
    },

    "alert": {
        "state": "IDLE",
        "red_light": False,
        "buzzer": False,
        "acknowledged_by": None,
    },
}


def anomaly_score(state):

    hr = (
        state["patient"]["heart_rate"]
    )

    rr = (
        state["patient"]["breathing_rate"]
    )

    hr_score = clamp(
        (hr - 90) / 60
    )

    rr_score = clamp(
        (rr - 18) / 12
    )

    return clamp(
        0.65 * hr_score
        + 0.35 * rr_score
    )


def emergency_decision(state):

    patient = state["patient"]

    if (
        patient["heart_rate"]
        >= EMERGENCY_THRESHOLDS["high_hr"]

        or patient["breathing_rate"]
        >= EMERGENCY_THRESHOLDS["high_rr"]

        or patient["anomaly_score"]
        >= EMERGENCY_THRESHOLDS["high_anomaly"]
    ):

        return {
            "alert": True,
            "severity": "HIGH",
        }

    return {
        "alert": False,
        "severity": None,
    }


def emergency_recovered(state):

    patient = state["patient"]

    return (

        patient["heart_rate"]
        <= EMERGENCY_THRESHOLDS["recovered_hr"]

        and patient["breathing_rate"]
        <= EMERGENCY_THRESHOLDS["recovered_rr"]

        and patient["anomaly_score"]
        <= EMERGENCY_THRESHOLDS["recovered_anomaly"]
    )


def emergency_mqtt(command):

    if command == "ACTIVATE":

        return {
            "topic":
                "hospital/staff-office/alert-device",

            "payload": {
                "command": "ACTIVATE",
                "patientId": PATIENT_ID,
                "roomId": ROOM_ID,
                "severity": "HIGH",
                "redLight": "ON",
                "buzzer": "ON",
            },
        }


    if command == "SILENCE":

        return {
            "topic":
                "hospital/staff-office/alert-device",

            "payload": {
                "command": "SILENCE",
                "redLight": "ON",
                "buzzer": "OFF",
            },
        }


    if command == "RESET":

        return {
            "topic":
                "hospital/staff-office/alert-device",

            "payload": {
                "command": "RESET",
                "redLight": "OFF",
                "buzzer": "OFF",
            },
        }

    return None


def emergency_twin_snapshot(state):

    return {

        "roomId": ROOM_ID,

        "assignedPatient": PATIENT_ID,

        "patient": {

            "heartRate_bpm":
                round(
                    state["patient"]["heart_rate"],
                    1
                ),

            "breathingRate_rpm":
                round(
                    state["patient"]["breathing_rate"],
                    1
                ),

            "AI_anomalyScore":
                round(
                    state["patient"]["anomaly_score"],
                    2
                ),
        },

        "clinical": {
            "status":
                state["clinical"]["status"],

            "severity":
                state["clinical"]["severity"],
        },

        "alert": {
            "state":
                state["alert"]["state"],

            "redLight":
                state["alert"]["red_light"],

            "buzzer":
                state["alert"]["buzzer"],

            "acknowledgedBy":
                state["alert"]["acknowledged_by"],
        },
    }


def emergency_html(state):

    patient = state["patient"]

    alert = state["alert"]

    anomaly = (
        patient["anomaly_score"]
    )


    if alert["red_light"]:

        light_color = "#ef4444"

        glow = (
            "0 0 18px #ef4444, "
            "0 0 40px rgba(239,68,68,.65)"
        )

    else:

        light_color = "#6b7280"

        glow = "none"


    if (
        alert["state"] == "ACTIVE"
        and alert["red_light"]
    ):

        animation = (
            "blink .7s infinite"
        )

    else:

        animation = "none"


    buzzer = (
        "🔊"
        if alert["buzzer"]
        else "🔇"
    )


    return f"""
<!DOCTYPE html>

<html>

<head>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Arial,
        sans-serif;
}}


@keyframes blink {{

    0% {{
        opacity: 1;
    }}

    50% {{
        opacity: .25;
    }}

    100% {{
        opacity: 1;
    }}

}}


.wrapper {{

    display: grid;

    grid-template-columns:
        1.5fr .8fr;

    gap: 16px;

}}


.monitor {{

    height: 390px;

    border-radius: 22px;

    padding: 22px;

    background:
        linear-gradient(
            145deg,
            #111827,
            #020617
        );

    color: white;

}}


.header {{

    display: flex;

    justify-content: space-between;

    border-bottom:
        1px solid #374151;

    padding-bottom: 12px;

    font-weight: 800;

}}


.patient-id {{

    padding:
        5px 10px;

    border-radius: 999px;

    background: #1f2937;

    font-size: 12px;

}}


.vitals {{

    margin-top: 28px;

    display: grid;

    grid-template-columns:
        1fr 1fr;

    gap: 20px;

}}


.label {{

    color: #9ca3af;

    font-size: 12px;

    text-transform: uppercase;

}}


.value {{

    font-size: 48px;

    font-weight: 800;

}}


.unit {{

    font-size: 15px;

    color: #9ca3af;

}}


.anomaly {{

    margin-top: 35px;

    padding: 15px;

    border-radius: 12px;

    background:
        rgba(255,255,255,.07);

}}


.track {{

    margin-top: 8px;

    width: 100%;

    height: 12px;

    background: #374151;

    border-radius: 999px;

    overflow: hidden;

}}


.fill {{

    height: 100%;

    width:
        {anomaly * 100:.1f}%;

    background:
        #ef4444;

}}


.device {{

    height: 390px;

    border-radius: 22px;

    background: #f9fafb;

    border:
        1px solid #d1d5db;

    display: flex;

    flex-direction: column;

    align-items: center;

    justify-content: center;

}}


.red-light {{

    width: 90px;
    height: 90px;

    border-radius: 50%;

    background:
        {light_color};

    box-shadow:
        {glow};

    animation:
        {animation};

    border:
        6px solid #d1d5db;

    margin:
        25px 0;

}}


.buzzer {{

    font-size: 55px;

}}


.state {{

    margin-top: 20px;

    background: #111827;

    color: white;

    padding:
        7px 12px;

    border-radius: 999px;

    font-size: 12px;

    font-weight: 800;

}}

</style>

</head>


<body>


<div class="wrapper">


    <div class="monitor">


        <div class="header">

            <span>
                🫀 Patient Monitor
            </span>

            <span class="patient-id">

                Room {ROOM_ID}
                · Patient {PATIENT_ID}

            </span>

        </div>


        <div class="vitals">


            <div>

                <div class="label">
                    ❤️ Heart rate
                </div>

                <div class="value">

                    {patient["heart_rate"]:.0f}

                    <span class="unit">
                        bpm
                    </span>

                </div>

            </div>


            <div>

                <div class="label">
                    🫁 Breathing rate
                </div>

                <div class="value">

                    {patient["breathing_rate"]:.0f}

                    <span class="unit">
                        rpm
                    </span>

                </div>

            </div>


        </div>


        <div class="anomaly">

            <b>

                AI anomaly score:
                {anomaly * 100:.0f}%

            </b>


            <div class="track">

                <div class="fill"></div>

            </div>

        </div>


    </div>


    <div class="device">


        <b>

            🚨 Medical Staff Office
            <br>
            Alert Device

        </b>


        <div class="red-light"></div>


        <div class="buzzer">

            {buzzer}

        </div>


        <div class="state">

            {alert["state"]}

        </div>


    </div>


</div>


</body>

</html>
"""


# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================

if "sleep_state" not in st.session_state:

    st.session_state.sleep_state = (
        copy.deepcopy(
            SLEEP_INITIAL_STATE
        )
    )


if "sleep_logs" not in st.session_state:

    st.session_state.sleep_logs = []


if "sleep_history" not in st.session_state:

    st.session_state.sleep_history = []


if "sleep_mqtt" not in st.session_state:

    st.session_state.sleep_mqtt = None


if "sleep_decision_status" not in st.session_state:

    st.session_state.sleep_decision_status = "WAITING"


if "emergency_state" not in st.session_state:

    st.session_state.emergency_state = (
        copy.deepcopy(
            EMERGENCY_INITIAL_STATE
        )
    )


if "emergency_logs" not in st.session_state:

    st.session_state.emergency_logs = []


if "emergency_history" not in st.session_state:

    st.session_state.emergency_history = []


if "emergency_mqtt" not in st.session_state:

    st.session_state.emergency_mqtt = None


if "emergency_phase" not in st.session_state:

    st.session_state.emergency_phase = "IDLE"


# ============================================================
# ============================================================
# DISPLAY SLEEP DEMO
# ============================================================
# ============================================================

if scenario == "🌙 Sleep-Aware Room Adaptation":

    st.subheader(
        "🌙 Scenario 1 — Sleep-Aware Room Adaptation"
    )

    st.info(
        "Patient P12 is awake while Room 204 is too warm "
        "and too bright. The system automatically adapts "
        "the room until the patient falls asleep."
    )


    start_col, reset_col = st.columns(
        [1, 1]
    )


    with start_col:

        start_sleep = st.button(
            "▶ START SLEEP DEMO",
            type="primary",
            use_container_width=True,
        )


    with reset_col:

        reset_sleep = st.button(
            "↻ RESET SLEEP DEMO",
            use_container_width=True,
        )


    if reset_sleep:

        st.session_state.sleep_state = (
            copy.deepcopy(
                SLEEP_INITIAL_STATE
            )
        )

        st.session_state.sleep_logs = []

        st.session_state.sleep_history = []

        st.session_state.sleep_mqtt = None

        st.session_state.sleep_decision_status = (
            "WAITING"
        )

        st.rerun()


    # ========================================================
    # PIPELINE
    # ========================================================

    sleep_pipeline = [
        "SENSORS",
        "CONTEXT",
        "DIGITAL TWIN",
        "AI",
        "DECISION",
        "MQTT",
        "ACTUATION",
        "FEEDBACK",
    ]


    pipeline_columns = st.columns(
        len(sleep_pipeline)
    )


    sleep_pipeline_slots = [
        col.empty()
        for col in pipeline_columns
    ]


    def render_sleep_pipeline(active=None):

        for slot, stage in zip(
            sleep_pipeline_slots,
            sleep_pipeline
        ):

            slot.empty()

            if stage == active:

                slot.info(
                    f"▶ {stage}"
                )

            else:

                slot.caption(
                    stage
                )


    st.divider()


    left, right = st.columns(
        [1.15, 1],
        gap="large",
    )


    with left:

        st.subheader(
            "🏨 Room 204"
        )

        sleep_room_slot = st.empty()


        st.markdown(
            "### 📡 Architecture Event Log"
        )

        sleep_log_slot = st.empty()


        sleep_mqtt_title = st.empty()

        sleep_mqtt_slot = st.empty()


    with right:

        st.subheader(
            "🪞 Live Digital Twin"
        )

        sleep_metrics_slot = st.empty()

        sleep_ai_slot = st.empty()

        sleep_decision_slot = st.empty()


        st.markdown(
            "### 🚨 Clinical Alert Service"
        )

        st.success(
            "🟢 IDLE — no clinical emergency detected"
        )

        st.caption(
            "This scenario concerns room comfort and sleep."
        )


        st.markdown(
            "### 🪞 Digital Twin Snapshot"
        )

        sleep_twin_slot = st.empty()


    st.divider()

    st.subheader(
        "📈 Physical State Evolution"
    )


    c1, c2, c3 = st.columns(3)


    with c1:
        sleep_temp_chart = st.empty()

    with c2:
        sleep_light_chart = st.empty()

    with c3:
        sleep_probability_chart = st.empty()


    def render_sleep(
        state,
        active=None,
        decision_status="WAITING",
        logs=None,
        history=None,
        mqtt=None,
    ):

        logs = logs or []

        history = history or []


        render_sleep_pipeline(
            active
        )


        sleep_room_slot.empty()

        with sleep_room_slot.container():

            components.html(
                sleep_room_html(state),
                height=435,
                scrolling=False,
            )


        sleep_metrics_slot.empty()

        with sleep_metrics_slot.container():

            m1, m2 = st.columns(2)


            with m1:

                st.metric(
                    "🌡 Temperature",
                    f"{state['room']['temperature']:.1f} °C"
                )

                st.caption(
                    "Sleep target: "
                    f"{SLEEP_PREFERENCES['sleep_temperature']} °C"
                )


                st.metric(
                    "☀️ Ambient light",
                    f"{state['room']['lux']:.0f} lux"
                )

                st.caption(
                    "Sleep target: "
                    f"≤ {SLEEP_PREFERENCES['sleep_light_lux']} lux"
                )


            with m2:

                st.metric(
                    "❤️ Heart rate",
                    f"{state['patient']['heart_rate']:.0f} bpm"
                )

                st.metric(
                    "🫁 Breathing rate",
                    f"{state['patient']['breathing_rate']:.0f} rpm"
                )

                st.metric(
                    "🚶 Movement",
                    movement_text(
                        state["patient"]["movement"]
                    )
                )


        sleep_ai_slot.empty()

        with sleep_ai_slot.container():

            st.markdown(
                "### 🤖 AI Sleep-State Estimate"
            )

            probability = (
                state["patient"]["sleep_probability"]
            )

            st.progress(
                probability
            )


            if (
                state["patient"]["sleep_state"]
                == "ASLEEP"
            ):

                st.success(
                    f"😴 ASLEEP — "
                    f"{probability * 100:.0f}% probability"
                )

            elif (
                state["patient"]["sleep_state"]
                == "DROWSY"
            ):

                st.warning(
                    f"🥱 DROWSY — "
                    f"{probability * 100:.0f}% probability"
                )

            else:

                st.info(
                    f"👁️ AWAKE — "
                    f"{probability * 100:.0f}% probability"
                )


            st.caption(
                "AI estimates the patient's state. "
                "It does not directly control the room."
            )


        sleep_decision_slot.empty()

        with sleep_decision_slot.container():

            st.markdown(
                "### 🧠 Decision & Control Service"
            )


            if decision_status == "WAITING":

                st.info(
                    "Waiting for contextualized data."
                )


            elif decision_status == "ADAPT":

                st.warning(
                    "🌙 Sleep-aware adaptation activated"
                )

                st.write(
                    "🪟 Close blinds"
                )

                st.write(
                    "💡 Dim lighting"
                )

                st.write(
                    "❄️ Cool room to 21.5 °C"
                )


            elif decision_status == "ADAPTING":

                st.info(
                    "⚙️ Room adaptation in progress..."
                )


            elif decision_status == "ASLEEP":

                st.success(
                    "✅ Sleep conditions reached"
                )

                st.write(
                    "Maintaining Sleep Mode targets."
                )


        sleep_log_slot.empty()

        with sleep_log_slot.container():

            if logs:

                st.code(
                    "\n".join(
                        logs[-8:]
                    ),
                    language=None,
                )

            else:

                st.info(
                    "Waiting for demo..."
                )


        sleep_mqtt_title.empty()

        sleep_mqtt_slot.empty()

        sleep_mqtt_title.markdown(
            "### 📨 MQTT Command"
        )


        if mqtt:

            sleep_mqtt_slot.code(
                json.dumps(
                    mqtt,
                    indent=2,
                ),
                language="json",
            )

        else:

            sleep_mqtt_slot.caption(
                "No control command published yet."
            )


        sleep_twin_slot.empty()

        sleep_twin_slot.json(
            sleep_twin_snapshot(
                state
            ),
            expanded=False,
        )


        sleep_temp_chart.empty()

        sleep_light_chart.empty()

        sleep_probability_chart.empty()


        if len(history) > 1:

            df = pd.DataFrame(
                history
            ).set_index(
                "step"
            )


            sleep_temp_chart.line_chart(
                df[
                    ["Temperature"]
                ],
                height=190,
            )


            sleep_light_chart.line_chart(
                df[
                    ["Ambient light"]
                ],
                height=190,
            )


            sleep_probability_chart.line_chart(
                df[
                    ["Sleep probability"]
                ],
                height=190,
            )


    def run_sleep_demo():

        state = copy.deepcopy(
            SLEEP_INITIAL_STATE
        )

        logs = []

        history = []

        mqtt = None


        probability, sleep_state = (
            estimate_sleep_state(
                state
            )
        )

        state["patient"]["sleep_probability"] = (
            probability
        )

        state["patient"]["sleep_state"] = (
            sleep_state
        )


        history.append({
            "step": 0,

            "Temperature":
                state["room"]["temperature"],

            "Ambient light":
                state["room"]["lux"],

            "Sleep probability":
                probability * 100,
        })


        add_log(
            logs,
            "SENSORS",
            (
                "HR=82 | RR=18 | movement=HIGH | "
                "temperature=27.5°C | light=820 lux"
            ),
        )


        render_sleep(
            state,
            "SENSORS",
            "WAITING",
            logs,
            history,
            mqtt,
        )

        time.sleep(1.2)


        add_log(
            logs,
            "CONTEXT",
            (
                "Measurements mapped to "
                "Patient P12 in Room 204."
            ),
        )

        render_sleep(
            state,
            "CONTEXT",
            "WAITING",
            logs,
            history,
            mqtt,
        )

        time.sleep(1.1)


        add_log(
            logs,
            "DIGITAL TWIN",
            (
                "Patient-room state synchronized."
            ),
        )

        render_sleep(
            state,
            "DIGITAL TWIN",
            "WAITING",
            logs,
            history,
            mqtt,
        )

        time.sleep(1.1)


        add_log(
            logs,
            "AI",
            (
                f"Patient state={sleep_state} | "
                f"probability={probability * 100:.0f}%"
            ),
        )

        render_sleep(
            state,
            "AI",
            "WAITING",
            logs,
            history,
            mqtt,
        )

        time.sleep(1.2)


        command = sleep_decision(
            state
        )


        add_log(
            logs,
            "DECISION",
            (
                "Patient awake + room too hot + "
                "too bright → Sleep Mode."
            ),
        )


        render_sleep(
            state,
            "DECISION",
            "ADAPT",
            logs,
            history,
            mqtt,
        )

        time.sleep(1.3)


        mqtt = sleep_mqtt_message(
            command
        )

        state["room"]["mode"] = (
            "ADAPTING"
        )


        add_log(
            logs,
            "MQTT",
            "Sleep Mode command published.",
        )


        render_sleep(
            state,
            "MQTT",
            "ADAPT",
            logs,
            history,
            mqtt,
        )

        time.sleep(1.1)


        state["room"]["ac_on"] = True

        state["room"]["ac_setpoint"] = (
            SLEEP_PREFERENCES[
                "sleep_temperature"
            ]
        )


        initial = copy.deepcopy(
            state
        )


        steps = 24


        for step in range(
            1,
            steps + 1
        ):

            fraction = (
                step / steps
            )

            eased = (
                1 - (1 - fraction) ** 2
            )


            state["room"]["temperature"] = lerp(
                initial["room"]["temperature"],
                21.6,
                eased,
            )


            state["room"]["lux"] = lerp(
                initial["room"]["lux"],
                40,
                eased,
            )


            state["room"]["lights_pct"] = lerp(
                initial["room"]["lights_pct"],
                5,
                eased,
            )


            state["room"]["blinds_open_pct"] = lerp(
                initial["room"]["blinds_open_pct"],
                0,
                eased,
            )


            state["patient"]["movement"] = lerp(
                initial["patient"]["movement"],
                0.02,
                eased,
            )


            state["patient"]["heart_rate"] = lerp(
                initial["patient"]["heart_rate"],
                67,
                eased,
            )


            state["patient"]["breathing_rate"] = lerp(
                initial["patient"]["breathing_rate"],
                14,
                eased,
            )


            probability, sleep_state = (
                estimate_sleep_state(
                    state
                )
            )


            state["patient"]["sleep_probability"] = (
                probability
            )

            state["patient"]["sleep_state"] = (
                sleep_state
            )


            history.append({

                "step": step,

                "Temperature":
                    state["room"]["temperature"],

                "Ambient light":
                    state["room"]["lux"],

                "Sleep probability":
                    probability * 100,
            })


            if step == 1:

                add_log(
                    logs,
                    "ACTUATION",
                    (
                        "A/C ON | lights dimming | "
                        "blinds closing."
                    ),
                )


            if step == 8:

                add_log(
                    logs,
                    "FEEDBACK",
                    (
                        "Actuator state returned through MQTT."
                    ),
                )


            if step == 15:

                add_log(
                    logs,
                    "AI",
                    (
                        "Sleep probability increasing."
                    ),
                )


            render_sleep(
                state,

                (
                    "ACTUATION"
                    if step < 10
                    else "FEEDBACK"
                ),

                (
                    "ASLEEP"
                    if sleep_state == "ASLEEP"
                    else "ADAPTING"
                ),

                logs,
                history,
                mqtt,
            )


            time.sleep(0.30)


        state["room"]["mode"] = (
            "SLEEP MODE"
        )


        add_log(
            logs,
            "SYSTEM",
            (
                "Patient asleep. "
                "Sleep Mode maintained."
            ),
        )


        render_sleep(
            state,
            "FEEDBACK",
            "ASLEEP",
            logs,
            history,
            mqtt,
        )


        st.session_state.sleep_state = (
            state
        )

        st.session_state.sleep_logs = (
            logs
        )

        st.session_state.sleep_history = (
            history
        )

        st.session_state.sleep_mqtt = (
            mqtt
        )

        st.session_state.sleep_decision_status = (
            "ASLEEP"
        )


    if start_sleep:

        run_sleep_demo()

    else:

        state = copy.deepcopy(
            st.session_state.sleep_state
        )

        probability, sleep_state = (
            estimate_sleep_state(
                state
            )
        )

        state["patient"]["sleep_probability"] = (
            probability
        )

        state["patient"]["sleep_state"] = (
            sleep_state
        )


        render_sleep(
            state,
            None,
            st.session_state.sleep_decision_status,
            st.session_state.sleep_logs,
            st.session_state.sleep_history,
            st.session_state.sleep_mqtt,
        )


# ============================================================
# ============================================================
# DISPLAY EMERGENCY DEMO
# ============================================================
# ============================================================

else:

    st.subheader(
        "🚨 Scenario 2 — Medical Emergency"
    )


    st.warning(
        "Synthetic demo values only. "
        "Thresholds are not intended for clinical use."
    )


    st.info(
        "The patient develops abnormal physiological values. "
        "The system activates a clinical alert and the physical "
        "staff alarm. The demo then requires manual acknowledgement."
    )


    b1, b2, b3, b4 = st.columns(
        4
    )


    with b1:

        start_emergency = st.button(
            "▶ START EMERGENCY",
            type="primary",
            use_container_width=True,

            disabled=(
                st.session_state.emergency_phase
                not in ["IDLE", "RESOLVED"]
            ),
        )


    with b2:

        acknowledge = st.button(
            "✓ ACKNOWLEDGE",
            use_container_width=True,

            disabled=(
                st.session_state.emergency_phase
                != "ACTIVE"
            ),
        )


    with b3:

        recover = st.button(
            "♡ SIMULATE RECOVERY",
            use_container_width=True,

            disabled=(
                st.session_state.emergency_phase
                != "ACKNOWLEDGED"
            ),
        )


    with b4:

        reset_emergency = st.button(
            "↻ RESET",
            use_container_width=True,
        )


    if reset_emergency:

        st.session_state.emergency_state = (
            copy.deepcopy(
                EMERGENCY_INITIAL_STATE
            )
        )

        st.session_state.emergency_logs = []

        st.session_state.emergency_history = []

        st.session_state.emergency_mqtt = None

        st.session_state.emergency_phase = (
            "IDLE"
        )

        st.rerun()


    emergency_pipeline = [
        "SENSORS",
        "CONTEXT",
        "DIGITAL TWIN",
        "AI",
        "DECISION",
        "ALERT SERVICE",
        "MQTT",
        "STAFF DEVICE",
    ]


    pcols = st.columns(
        len(emergency_pipeline)
    )

    emergency_pipeline_slots = [
        col.empty()
        for col in pcols
    ]


    def render_emergency_pipeline(
        active=None
    ):

        for slot, stage in zip(
            emergency_pipeline_slots,
            emergency_pipeline
        ):

            slot.empty()

            if stage == active:

                slot.error(
                    f"▶ {stage}"
                )

            else:

                slot.caption(
                    stage
                )


    st.divider()


    left, right = st.columns(
        [1.15, 1],
        gap="large",
    )


    with left:

        st.subheader(
            "🏥 Patient & Physical Alert"
        )

        emergency_monitor_slot = st.empty()


        st.markdown(
            "### 📡 Architecture Event Log"
        )

        emergency_log_slot = st.empty()


        emergency_mqtt_title = st.empty()

        emergency_mqtt_slot = st.empty()


    with right:

        st.subheader(
            "🪞 Live Digital Twin"
        )

        emergency_metrics_slot = st.empty()

        emergency_ai_slot = st.empty()

        emergency_decision_slot = st.empty()

        emergency_alert_slot = st.empty()


        st.markdown(
            "### 🪞 Digital Twin Snapshot"
        )

        emergency_twin_slot = st.empty()


    st.divider()

    st.subheader(
        "📈 Patient State Evolution"
    )


    ec1, ec2, ec3 = st.columns(3)


    with ec1:
        emergency_hr_chart = st.empty()

    with ec2:
        emergency_rr_chart = st.empty()

    with ec3:
        emergency_ai_chart = st.empty()


    def render_emergency(
        active=None
    ):

        state = (
            st.session_state.emergency_state
        )


        render_emergency_pipeline(
            active
        )


        emergency_monitor_slot.empty()

        with emergency_monitor_slot.container():

            components.html(
                emergency_html(
                    state
                ),
                height=405,
                scrolling=False,
            )


        emergency_metrics_slot.empty()

        with emergency_metrics_slot.container():

            m1, m2 = st.columns(2)


            with m1:

                st.metric(
                    "❤️ Heart rate",
                    f"{state['patient']['heart_rate']:.0f} bpm"
                )


            with m2:

                st.metric(
                    "🫁 Breathing rate",
                    f"{state['patient']['breathing_rate']:.0f} rpm"
                )


        emergency_ai_slot.empty()

        with emergency_ai_slot.container():

            st.markdown(
                "### 🤖 AI Anomaly Detection"
            )


            score = (
                state["patient"]["anomaly_score"]
            )


            st.progress(
                score
            )


            if score >= 0.82:

                st.error(
                    f"⚠️ HIGH anomaly — "
                    f"{score * 100:.0f}%"
                )

            elif score >= 0.45:

                st.warning(
                    f"Elevated anomaly — "
                    f"{score * 100:.0f}%"
                )

            else:

                st.success(
                    f"Low anomaly — "
                    f"{score * 100:.0f}%"
                )


            st.caption(
                "AI estimates abnormality. "
                "The Decision Service makes the final alert decision."
            )


        emergency_decision_slot.empty()

        with emergency_decision_slot.container():

            st.markdown(
                "### 🧠 Decision & Control Service"
            )


            phase = (
                st.session_state.emergency_phase
            )


            if phase == "IDLE":

                st.success(
                    "Patient state considered normal."
                )


            elif phase == "ESCALATING":

                st.warning(
                    "Monitoring abnormal physiological trend..."
                )


            elif phase in [
                "ACTIVE",
                "ACKNOWLEDGED",
            ]:

                st.error(
                    "🚨 FINAL DECISION: HIGH severity clinical alert"
                )

                st.write(
                    "**Patient:** P12"
                )

                st.write(
                    "**Room:** 204"
                )


            elif phase == "RECOVERING":

                st.warning(
                    "Monitoring recovery..."
                )


            elif phase == "RESOLVED":

                st.success(
                    "✅ Patient condition returned "
                    "to configured demo range."
                )


        emergency_alert_slot.empty()

        with emergency_alert_slot.container():

            st.markdown(
                "### 🚨 Clinical Alert Lifecycle Service"
            )


            alert_state = (
                state["alert"]["state"]
            )


            if alert_state == "IDLE":

                st.success(
                    "🟢 IDLE"
                )


            elif alert_state == "ACTIVE":

                st.error(
                    "🔴 ACTIVE"
                )

                st.write(
                    "🔴 Red warning light: **ON**"
                )

                st.write(
                    "🔊 Buzzer: **ON**"
                )


            elif alert_state == "ACKNOWLEDGED":

                st.warning(
                    "🟠 ACKNOWLEDGED"
                )

                st.write(
                    "🔴 Red warning light: **ON**"
                )

                st.write(
                    "🔇 Buzzer: **OFF**"
                )


            elif alert_state == "RESOLVED":

                st.success(
                    "✅ RESOLVED"
                )

                st.write(
                    "⚫ Red warning light: **OFF**"
                )

                st.write(
                    "🔇 Buzzer: **OFF**"
                )


        emergency_log_slot.empty()

        with emergency_log_slot.container():

            logs = (
                st.session_state.emergency_logs
            )

            if logs:

                st.code(
                    "\n".join(
                        logs[-9:]
                    ),
                    language=None,
                )

            else:

                st.info(
                    "Waiting for demo..."
                )


        emergency_mqtt_title.empty()

        emergency_mqtt_slot.empty()

        emergency_mqtt_title.markdown(
            "### 📨 MQTT Command"
        )


        if st.session_state.emergency_mqtt:

            emergency_mqtt_slot.code(
                json.dumps(
                    st.session_state.emergency_mqtt,
                    indent=2,
                ),
                language="json",
            )

        else:

            emergency_mqtt_slot.caption(
                "No alert-device command published yet."
            )


        emergency_twin_slot.empty()

        emergency_twin_slot.json(
            emergency_twin_snapshot(
                state
            ),
            expanded=False,
        )


        history = (
            st.session_state.emergency_history
        )


        emergency_hr_chart.empty()

        emergency_rr_chart.empty()

        emergency_ai_chart.empty()


        if len(history) > 1:

            df = pd.DataFrame(
                history
            ).set_index(
                "step"
            )


            emergency_hr_chart.line_chart(
                df[
                    ["Heart rate"]
                ],
                height=190,
            )


            emergency_rr_chart.line_chart(
                df[
                    ["Breathing rate"]
                ],
                height=190,
            )


            emergency_ai_chart.line_chart(
                df[
                    ["Anomaly score"]
                ],
                height=190,
            )


    def add_emergency_history(
        state,
        step
    ):

        st.session_state.emergency_history.append({

            "step": step,

            "Heart rate":
                state["patient"]["heart_rate"],

            "Breathing rate":
                state["patient"]["breathing_rate"],

            "Anomaly score":
                state["patient"]["anomaly_score"] * 100,
        })


    def run_emergency_demo():

        state = copy.deepcopy(
            EMERGENCY_INITIAL_STATE
        )


        st.session_state.emergency_state = (
            state
        )

        st.session_state.emergency_logs = []

        st.session_state.emergency_history = []

        st.session_state.emergency_mqtt = None

        st.session_state.emergency_phase = (
            "ESCALATING"
        )


        add_log(
            st.session_state.emergency_logs,
            "SENSORS",
            (
                "HR=78 bpm | RR=16 rpm | "
                "patient initially stable."
            ),
        )


        add_emergency_history(
            state,
            0
        )


        render_emergency(
            "SENSORS"
        )

        time.sleep(1.1)


        add_log(
            st.session_state.emergency_logs,
            "CONTEXT",
            (
                "Measurements mapped to "
                "Patient P12 / Room 204."
            ),
        )


        render_emergency(
            "CONTEXT"
        )

        time.sleep(1.0)


        add_log(
            st.session_state.emergency_logs,
            "DIGITAL TWIN",
            (
                "Initial patient state synchronized."
            ),
        )


        render_emergency(
            "DIGITAL TWIN"
        )

        time.sleep(1.0)


        steps = 20


        for step in range(
            1,
            steps + 1
        ):

            fraction = (
                step / steps
            )

            eased = (
                fraction ** 1.25
            )


            state["patient"]["heart_rate"] = (
                lerp(
                    78,
                    148,
                    eased,
                )
            )


            state["patient"]["breathing_rate"] = (
                lerp(
                    16,
                    28,
                    eased,
                )
            )


            state["patient"]["anomaly_score"] = (
                anomaly_score(
                    state
                )
            )


            add_emergency_history(
                state,
                step
            )


            if step == 6:

                add_log(
                    st.session_state.emergency_logs,
                    "SENSORS",
                    (
                        "Heart rate and breathing rate rising."
                    ),
                )


            if step == 12:

                add_log(
                    st.session_state.emergency_logs,
                    "DIGITAL TWIN",
                    (
                        "Abnormal trend synchronized."
                    ),
                )


            if step == 16:

                add_log(
                    st.session_state.emergency_logs,
                    "AI",
                    (
                        "High anomaly score detected."
                    ),
                )


            render_emergency(
                (
                    "SENSORS"
                    if step < 8
                    else
                    "DIGITAL TWIN"
                    if step < 14
                    else
                    "AI"
                )
            )


            time.sleep(0.24)


        decision = (
            emergency_decision(
                state
            )
        )


        state["clinical"]["status"] = (
            "ABNORMAL"
        )

        state["clinical"]["severity"] = (
            decision["severity"]
        )


        add_log(
            st.session_state.emergency_logs,
            "DECISION",
            (
                "HIGH severity clinical alert generated."
            ),
        )


        render_emergency(
            "DECISION"
        )

        time.sleep(1.0)


        state["alert"]["state"] = (
            "ACTIVE"
        )

        state["alert"]["red_light"] = (
            True
        )

        state["alert"]["buzzer"] = (
            True
        )


        st.session_state.emergency_phase = (
            "ACTIVE"
        )


        add_log(
            st.session_state.emergency_logs,
            "ALERT SERVICE",
            "Alert state → ACTIVE.",
        )


        render_emergency(
            "ALERT SERVICE"
        )

        time.sleep(1.0)


        st.session_state.emergency_mqtt = (
            emergency_mqtt(
                "ACTIVATE"
            )
        )


        add_log(
            st.session_state.emergency_logs,
            "MQTT",
            (
                "ACTIVATE command published."
            ),
        )


        render_emergency(
            "MQTT"
        )

        time.sleep(1.0)


        add_log(
            st.session_state.emergency_logs,
            "STAFF DEVICE",
            (
                "Red light ON | buzzer ON."
            ),
        )


        render_emergency(
            "STAFF DEVICE"
        )


    def acknowledge_emergency():

        state = (
            st.session_state.emergency_state
        )


        state["alert"]["state"] = (
            "ACKNOWLEDGED"
        )

        state["alert"]["red_light"] = (
            True
        )

        state["alert"]["buzzer"] = (
            False
        )

        state["alert"]["acknowledged_by"] = (
            "Medical Staff"
        )


        st.session_state.emergency_phase = (
            "ACKNOWLEDGED"
        )


        st.session_state.emergency_mqtt = (
            emergency_mqtt(
                "SILENCE"
            )
        )


        add_log(
            st.session_state.emergency_logs,
            "MEDICAL STAFF",
            (
                "Alert acknowledged through dashboard."
            ),
        )


        add_log(
            st.session_state.emergency_logs,
            "MQTT",
            (
                "SILENCE → buzzer OFF, "
                "red light remains ON."
            ),
        )


    def run_recovery():

        state = (
            st.session_state.emergency_state
        )


        st.session_state.emergency_phase = (
            "RECOVERING"
        )


        starting_hr = (
            state["patient"]["heart_rate"]
        )

        starting_rr = (
            state["patient"]["breathing_rate"]
        )


        starting_step = (
            len(
                st.session_state.emergency_history
            )
        )


        for i in range(
            1,
            21
        ):

            fraction = (
                i / 20
            )

            eased = (
                1 - (1 - fraction) ** 2
            )


            state["patient"]["heart_rate"] = (
                lerp(
                    starting_hr,
                    82,
                    eased,
                )
            )


            state["patient"]["breathing_rate"] = (
                lerp(
                    starting_rr,
                    17,
                    eased,
                )
            )


            state["patient"]["anomaly_score"] = (
                anomaly_score(
                    state
                )
            )


            add_emergency_history(
                state,
                starting_step + i,
            )


            render_emergency(
                (
                    "SENSORS"
                    if i < 7
                    else
                    "DIGITAL TWIN"
                    if i < 14
                    else
                    "AI"
                )
            )


            time.sleep(0.25)


        if emergency_recovered(
            state
        ):

            state["clinical"]["status"] = (
                "NORMAL"
            )

            state["clinical"]["severity"] = (
                None
            )


            add_log(
                st.session_state.emergency_logs,
                "DECISION",
                (
                    "Patient condition considered recovered."
                ),
            )


            render_emergency(
                "DECISION"
            )

            time.sleep(1.0)


            state["alert"]["state"] = (
                "RESOLVED"
            )

            state["alert"]["red_light"] = (
                False
            )

            state["alert"]["buzzer"] = (
                False
            )


            st.session_state.emergency_phase = (
                "RESOLVED"
            )


            add_log(
                st.session_state.emergency_logs,
                "ALERT SERVICE",
                (
                    "Alert state → RESOLVED."
                ),
            )


            st.session_state.emergency_mqtt = (
                emergency_mqtt(
                    "RESET"
                )
            )


            add_log(
                st.session_state.emergency_logs,
                "MQTT",
                (
                    "RESET → red light OFF, "
                    "buzzer OFF."
                ),
            )


            render_emergency(
                "STAFF DEVICE"
            )


    if start_emergency:

        run_emergency_demo()

        st.rerun()


    if acknowledge:

        acknowledge_emergency()

        st.rerun()


    if recover:

        run_recovery()

        st.rerun()


    render_emergency(
        None
    )


# ============================================================
# ARCHITECTURE SUMMARY
# ============================================================

st.divider()


with st.expander(
    "ℹ️ What the two demos demonstrate"
):

    st.markdown(
        """
### Common architecture

Both scenarios begin with the same core flow:

**Sensors → Gateway → MQTT → Context Service → Digital Twin → AI → Decision Service**

The difference appears after the final decision.

---

### 🌙 Sleep scenario

The AI estimates:

**AWAKE → DROWSY → ASLEEP**

The Decision Service detects that the patient is awake while the room is too hot and too bright.

It sends commands to:

- dim the lights;
- close the blinds;
- cool the room.

The actuator state is fed back into the Digital Twin.

---

### 🚨 Medical emergency scenario

The AI calculates an anomaly score from the simulated physiological measurements.

The Decision Service makes the final clinical-alert decision.

The Clinical Alert Lifecycle Service then manages:

**ACTIVE → ACKNOWLEDGED → RESOLVED**

#### ACTIVE
- Red light ON
- Buzzer ON

#### ACKNOWLEDGED
- Red light ON
- Buzzer OFF

#### RESOLVED
- Red light OFF
- Buzzer OFF

---

### Important

The physiological thresholds used in the emergency scenario are synthetic demo values only and are not clinically validated.
"""
    )