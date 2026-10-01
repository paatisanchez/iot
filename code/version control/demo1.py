import copy
import json
import time

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Smart Hospital Demo",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("🏥 Smart Hospital — Sleep-Aware Room Demo")

st.caption(
    "Sensors → Context → Digital Twin → AI → "
    "Decision → MQTT → Actuation → Feedback"
)


# ============================================================
# CONFIGURATION DATABASE
# ============================================================

ROOM_ID = "204"
PATIENT_ID = "P12"

PREFERENCES = {
    "sleep_mode_enabled": True,
    "sleep_temperature": 21.5,
    "sleep_light_lux": 60,
    "sleep_lights_pct": 5,
    "sleep_blinds_open_pct": 0,
}


# ============================================================
# INITIAL STATE
# ============================================================

INITIAL_STATE = {
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
        "severity": None,
    },
}


# ============================================================
# HELPERS
# ============================================================

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


# ============================================================
# AI SERVICE
# ============================================================

def estimate_sleep_state(state):
    """
    Simplified AI output used for the demo.

    The AI estimates the patient's sleep state.
    It does NOT directly control the room.
    """

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
            - PREFERENCES["sleep_temperature"]
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


# ============================================================
# DECISION & CONTROL SERVICE
# ============================================================

def evaluate_room_policy(state):
    """
    Final decision is made here.

    Inputs:
    - Digital Twin
    - AI sleep estimate
    - Room preferences
    - Configured thresholds
    """

    patient = state["patient"]
    room = state["room"]

    too_hot = (
        room["temperature"]
        > PREFERENCES["sleep_temperature"] + 1.0
    )

    too_bright = (
        room["lux"]
        > PREFERENCES["sleep_light_lux"] * 2
    )

    patient_not_asleep = (
        patient["sleep_state"] != "ASLEEP"
    )

    if (
        PREFERENCES["sleep_mode_enabled"]
        and patient_not_asleep
        and (too_hot or too_bright)
    ):

        return {
            "action": "ACTIVATE_SLEEP_MODE",
            "temperature": PREFERENCES["sleep_temperature"],
            "lights_pct": PREFERENCES["sleep_lights_pct"],
            "blinds_open_pct": PREFERENCES["sleep_blinds_open_pct"],
            "ac_on": True,
        }

    return {
        "action": "NO_ACTION"
    }


# ============================================================
# MQTT
# ============================================================

def build_mqtt_message(command):

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
                "enabled":
                    command["ac_on"],

                "setpoint_c":
                    command["temperature"],
            },
        },
    }


# ============================================================
# DIGITAL TWIN SNAPSHOT
# ============================================================

def digital_twin_snapshot(state):

    return {
        "roomId":
            state["room"]["id"],

        "assignedPatient":
            state["patient"]["id"],

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

        "clinicalAlert": {
            "state":
                state["alert"]["state"]
        },
    }


# ============================================================
# ROOM VISUAL
# ============================================================

def room_html(state):

    patient = state["patient"]
    room = state["room"]

    brightness = clamp(
        room["lux"] / 820.0
    )

    blinds_closed = (
        100 - room["blinds_open_pct"]
    )

    light_intensity = clamp(
        room["lights_pct"] / 100
    )


    # --------------------------------------------------------
    # PATIENT APPEARANCE
    # --------------------------------------------------------

    if patient["sleep_state"] == "ASLEEP":

        patient_icon = "😴"
        patient_label = "ASLEEP"
        patient_animation = "none"

    elif patient["sleep_state"] == "DROWSY":

        patient_icon = "🥱"
        patient_label = "DROWSY"

        patient_animation = (
            "floaty 2s ease-in-out infinite"
        )

    else:

        patient_icon = "🧍"
        patient_label = "AWAKE"

        patient_animation = (
            "floaty 1.1s ease-in-out infinite"
        )


    # --------------------------------------------------------
    # AC
    # --------------------------------------------------------

    if room["ac_on"]:

        ac_icon = "❄️"

        ac_state = (
            f"ON · "
            f"{room['ac_setpoint']:.1f} °C"
        )

    else:

        ac_icon = "⭕"
        ac_state = "OFF"


    # --------------------------------------------------------
    # ROOM MODE
    # --------------------------------------------------------

    if room["mode"] == "SLEEP MODE":
        mode_icon = "🌙"

    elif room["mode"] == "ADAPTING":
        mode_icon = "⚙️"

    else:
        mode_icon = "☀️"


    # --------------------------------------------------------
    # COLORS
    # --------------------------------------------------------

    wall_lightness = int(
        72 + brightness * 23
    )

    window_r = int(
        70 + brightness * 170
    )

    window_g = int(
        100 + brightness * 145
    )

    window_b = int(
        130 + brightness * 115
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
        transform: translateY(0);
    }}

    50% {{
        transform: translateY(-7px);
    }}

    100% {{
        transform: translateY(0);
    }}

}}


.room {{

    width: 100%;
    height: 420px;

    position: relative;

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


.room-title {{

    position: absolute;

    top: 18px;
    left: 20px;

    z-index: 20;

    background:
        rgba(255,255,255,.95);

    border-radius: 12px;

    padding:
        9px 14px;

    font-size: 14px;

    font-weight: 750;

    box-shadow:
        0 3px 12px
        rgba(0,0,0,.08);

}}


.window {{

    position: absolute;

    top: 80px;
    left: 35px;

    width: 220px;
    height: 170px;

    border:
        10px solid white;

    border-radius: 7px;

    overflow: hidden;

    background:
        rgb(
            {window_r},
            {window_g},
            {window_b}
        );

    box-shadow:
        0 4px 16px
        rgba(0,0,0,.08);

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


.window-v {{

    position: absolute;

    left: 50%;
    top: 0;

    width: 7px;
    height: 100%;

    background: white;

}}


.window-h {{

    position: absolute;

    left: 0;
    top: 50%;

    width: 100%;
    height: 7px;

    background: white;

}}


.light {{

    position: absolute;

    right: 55px;
    top: 65px;

    font-size: 55px;

    opacity:
        {max(0.12, light_intensity)};

    filter:
        drop-shadow(
            0 0
            {int(5 + light_intensity * 25)}px
            rgba(255,220,80,.7)
        );

}}


.bed {{

    position: absolute;

    left: 20%;
    bottom: 68px;

    width: 57%;
    height: 105px;

    background:
        linear-gradient(
            180deg,
            #fafafa,
            #eef2f7
        );

    border:
        4px solid #94a3b8;

    border-radius:
        24px 24px 9px 9px;

    box-shadow:
        0 8px 0 #64748b;

}}


.pillow {{

    position: absolute;

    top: 17px;
    left: 8%;

    width: 28%;
    height: 40px;

    background: white;

    border:
        1px solid #e5e7eb;

    border-radius: 22px;

}}


.blanket {{

    position: absolute;

    right: 4%;
    bottom: 0;

    width: 58%;
    height: 65px;

    background: #dbeafe;

    border-radius:
        20px 20px 5px 5px;

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

    z-index: 9;

    background:
        rgba(255,255,255,.95);

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

    min-width: 145px;

    border-radius: 13px;

    background:
        rgba(255,255,255,.92);

    border:
        1px solid #e5e7eb;

    font-size: 11px;

    line-height: 1.7;

}}


.ac {{

    position: absolute;

    right: 22px;
    bottom: 70px;

    width: 160px;

    padding:
        12px 13px;

    border-radius: 13px;

    background:
        rgba(255,255,255,.95);

    border:
        1px solid #d1d5db;

    box-shadow:
        0 4px 12px
        rgba(0,0,0,.07);

    font-size: 12px;

}}


.ac-title {{

    font-weight: 750;

    margin-bottom: 5px;

}}


.ac-state {{

    font-size: 15px;

    font-weight: 800;

}}


.mode {{

    position: absolute;

    left: 18px;
    bottom: 18px;

    z-index: 10;

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


    <div class="room-title">

        🏥 Room {ROOM_ID}
        &nbsp;·&nbsp;
        Patient {PATIENT_ID}

    </div>


    <div class="window">

        <div class="blind"></div>

        <div class="window-v"></div>

        <div class="window-h"></div>

    </div>


    <div class="light">
        💡
    </div>


    <div class="bed">

        <div class="pillow"></div>

        <div class="blanket"></div>

    </div>


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

        <div class="ac-title">

            {ac_icon}
            Air conditioning

        </div>

        <div class="ac-state">

            {ac_state}

        </div>

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
# LOG + HISTORY
# ============================================================

def add_log(logs, source, message):

    logs.append(
        f"{source} → {message}"
    )


def add_history(history, state, step):

    history.append({

        "step":
            step,

        "Temperature":
            state["room"]["temperature"],

        "Ambient light":
            state["room"]["lux"],

        "Sleep probability":
            state["patient"]["sleep_probability"] * 100,

    })


# ============================================================
# SESSION STATE
# ============================================================

if "state" not in st.session_state:

    st.session_state.state = (
        copy.deepcopy(
            INITIAL_STATE
        )
    )


if "logs" not in st.session_state:

    st.session_state.logs = []


if "history" not in st.session_state:

    st.session_state.history = []


if "mqtt" not in st.session_state:

    st.session_state.mqtt = None


if "decision" not in st.session_state:

    st.session_state.decision = "WAITING"


# ============================================================
# CONTROL BUTTONS
# ============================================================

start_col, reset_col, explanation_col = st.columns(
    [1, 1, 4],
    gap="medium",
)


with start_col:

    start_demo = st.button(
        "▶ START DEMO",
        type="primary",
        use_container_width=True,
    )


with reset_col:

    reset_demo = st.button(
        "↻ RESET",
        use_container_width=True,
    )


with explanation_col:

    st.info(
        "Patient P12 is awake in Room 204. "
        "The room is too warm and too bright. "
        "The system adapts the environment until "
        "the patient falls asleep."
    )


if reset_demo:

    st.session_state.state = (
        copy.deepcopy(
            INITIAL_STATE
        )
    )

    st.session_state.logs = []

    st.session_state.history = []

    st.session_state.mqtt = None

    st.session_state.decision = "WAITING"

    st.rerun()


# ============================================================
# ARCHITECTURE PIPELINE
# ============================================================

PIPELINE = [
    "SENSORS",
    "CONTEXT",
    "DIGITAL TWIN",
    "AI",
    "DECISION",
    "MQTT",
    "ACTUATION",
    "FEEDBACK",
]


pipeline_columns = st.columns(8)

pipeline_slots = [
    column.empty()
    for column in pipeline_columns
]


def render_pipeline(active=None):

    for slot, stage in zip(
        pipeline_slots,
        PIPELINE
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


# ============================================================
# PAGE LAYOUT
# ============================================================

st.divider()


main_left, main_right = st.columns(
    [1.15, 1],
    gap="large",
)


# ============================================================
# LEFT COLUMN
# ============================================================

with main_left:

    st.subheader(
        f"🏨 Room {ROOM_ID}"
    )

    room_slot = st.empty()


    st.markdown(
        "### 📡 Architecture Event Log"
    )

    log_slot = st.empty()


    mqtt_title_slot = st.empty()

    mqtt_slot = st.empty()


# ============================================================
# RIGHT COLUMN
# ============================================================

with main_right:

    st.subheader(
        "🪞 Live Digital Twin"
    )

    metrics_slot = st.empty()


    ai_slot = st.empty()


    decision_slot = st.empty()


    # Clinical Alert is STATIC.
    # It is deliberately outside the animated render functions.

    st.markdown(
        "### 🚨 Clinical Alert Service"
    )

    st.success(
        "🟢 IDLE — no clinical emergency detected"
    )

    st.caption(
        "This scenario concerns room comfort and sleep, "
        "not a clinical emergency."
    )


    st.markdown(
        "### 🪞 Digital Twin Snapshot"
    )

    twin_slot = st.empty()


# ============================================================
# CHARTS
# ============================================================

st.divider()

st.subheader(
    "📈 Physical State Evolution"
)


chart1, chart2, chart3 = st.columns(
    3,
    gap="medium"
)


with chart1:

    temperature_chart = st.empty()


with chart2:

    light_chart = st.empty()


with chart3:

    sleep_chart = st.empty()


# ============================================================
# RENDER FUNCTIONS
# ============================================================

def render_room(state):

    room_slot.empty()

    with room_slot.container():

        components.html(
            room_html(state),
            height=435,
            scrolling=False,
        )


def render_metrics(state):

    metrics_slot.empty()

    with metrics_slot.container():

        left, right = st.columns(2)


        with left:

            st.metric(
                "🌡️ Temperature",
                f"{state['room']['temperature']:.1f} °C",
            )

            st.caption(
                f"Sleep target: "
                f"{PREFERENCES['sleep_temperature']} °C"
            )


            st.metric(
                "☀️ Ambient light",
                f"{state['room']['lux']:.0f} lux",
            )

            st.caption(
                f"Sleep target: "
                f"≤ {PREFERENCES['sleep_light_lux']} lux"
            )


            st.metric(
                "🪟 Blinds",
                f"{state['room']['blinds_open_pct']:.0f}% open",
            )


        with right:

            st.metric(
                "❤️ Heart rate",
                f"{state['patient']['heart_rate']:.0f} bpm",
            )


            st.metric(
                "🫁 Breathing rate",
                f"{state['patient']['breathing_rate']:.0f} rpm",
            )


            st.metric(
                "🚶 Movement",
                movement_text(
                    state["patient"]["movement"]
                ),
            )


def render_ai(state):

    ai_slot.empty()

    with ai_slot.container():

        st.markdown(
            "### 🤖 AI Sleep-State Estimate"
        )

        probability = (
            state["patient"]["sleep_probability"]
        )

        st.progress(
            probability
        )


        if state["patient"]["sleep_state"] == "ASLEEP":

            st.success(
                f"😴 ASLEEP — "
                f"{probability * 100:.0f}% probability"
            )


        elif state["patient"]["sleep_state"] == "DROWSY":

            st.warning(
                f"🥱 DROWSY — "
                f"{probability * 100:.0f}% sleep probability"
            )


        else:

            st.info(
                f"👁️ AWAKE — "
                f"{probability * 100:.0f}% sleep probability"
            )


        st.caption(
            "AI estimates patient state. "
            "It does not directly control the room."
        )


def render_decision(status):

    decision_slot.empty()

    with decision_slot.container():

        st.markdown(
            "### 🧠 Decision & Control Service"
        )


        if status == "WAITING":

            st.info(
                "Waiting for contextualized patient-room data."
            )


        elif status == "ADAPT":

            st.warning(
                "🌙 Sleep-aware room adaptation activated"
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


        elif status == "ADAPTING":

            st.info(
                "⚙️ Sleep Mode adaptation in progress..."
            )

            st.write(
                "🪟 Blinds adjusting"
            )

            st.write(
                "💡 Light decreasing"
            )

            st.write(
                "❄️ Room cooling"
            )


        elif status == "ASLEEP":

            st.success(
                "✅ Sleep conditions reached"
            )

            st.write(
                "Maintaining Sleep Mode targets."
            )


def render_log(logs):

    log_slot.empty()

    with log_slot.container():

        if not logs:

            st.info(
                "Waiting for demo..."
            )

        else:

            visible_logs = (
                logs[-8:]
            )

            log_text = "\n".join(
                visible_logs
            )

            st.code(
                log_text,
                language=None,
            )


def render_twin(state):

    twin_slot.empty()

    with twin_slot.container():

        st.json(
            digital_twin_snapshot(
                state
            ),
            expanded=False,
        )


def render_mqtt(message):

    mqtt_title_slot.empty()

    mqtt_slot.empty()


    mqtt_title_slot.markdown(
        "### 📨 MQTT Command"
    )


    if message is None:

        mqtt_slot.caption(
            "No control command published yet."
        )

    else:

        mqtt_slot.code(
            json.dumps(
                message,
                indent=2,
            ),
            language="json",
        )


def render_charts(history):

    temperature_chart.empty()

    light_chart.empty()

    sleep_chart.empty()


    if len(history) < 2:

        temperature_chart.caption(
            "Temperature data will appear during the demo."
        )

        light_chart.caption(
            "Light data will appear during the demo."
        )

        sleep_chart.caption(
            "Sleep probability will appear during the demo."
        )

        return


    dataframe = (
        pd.DataFrame(
            history
        )
        .set_index(
            "step"
        )
    )


    with temperature_chart.container():

        st.caption(
            "Room temperature"
        )

        st.line_chart(
            dataframe[
                ["Temperature"]
            ],
            height=190,
        )


    with light_chart.container():

        st.caption(
            "Ambient light"
        )

        st.line_chart(
            dataframe[
                ["Ambient light"]
            ],
            height=190,
        )


    with sleep_chart.container():

        st.caption(
            "AI sleep probability (%)"
        )

        st.line_chart(
            dataframe[
                ["Sleep probability"]
            ],
            height=190,
        )


def render_all(
    state,
    active_stage,
    decision_status,
    logs,
    history,
    mqtt_message,
):

    render_pipeline(
        active_stage
    )

    render_room(
        state
    )

    render_metrics(
        state
    )

    render_ai(
        state
    )

    render_decision(
        decision_status
    )

    render_log(
        logs
    )

    render_twin(
        state
    )

    render_mqtt(
        mqtt_message
    )

    render_charts(
        history
    )


# ============================================================
# DEMO
# ============================================================

def run_demo():

    state = copy.deepcopy(
        INITIAL_STATE
    )

    logs = []

    history = []

    mqtt_message = None


    # ========================================================
    # STEP 1 — SENSORS
    # ========================================================

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


    add_log(
        logs,
        "SENSORS",
        (
            "HR=82 bpm | RR=18 rpm | "
            "movement=HIGH | "
            "temperature=27.5°C | "
            "light=820 lux"
        ),
    )


    add_history(
        history,
        state,
        0,
    )


    render_all(
        state,
        "SENSORS",
        "WAITING",
        logs,
        history,
        mqtt_message,
    )

    time.sleep(1.3)


    # ========================================================
    # STEP 2 — CONTEXT
    # ========================================================

    add_log(
        logs,
        "CONTEXT",
        (
            "Measurements associated with "
            "Patient P12 in Room 204."
        ),
    )


    render_all(
        state,
        "CONTEXT",
        "WAITING",
        logs,
        history,
        mqtt_message,
    )

    time.sleep(1.2)


    # ========================================================
    # STEP 3 — DIGITAL TWIN
    # ========================================================

    add_log(
        logs,
        "DIGITAL TWIN",
        (
            "Patient, room and device "
            "state synchronized."
        ),
    )


    render_all(
        state,
        "DIGITAL TWIN",
        "WAITING",
        logs,
        history,
        mqtt_message,
    )

    time.sleep(1.2)


    # ========================================================
    # STEP 4 — AI
    # ========================================================

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


    add_log(
        logs,
        "AI",
        (
            f"State={sleep_state} | "
            f"sleep probability="
            f"{probability * 100:.0f}%"
        ),
    )


    render_all(
        state,
        "AI",
        "WAITING",
        logs,
        history,
        mqtt_message,
    )

    time.sleep(1.4)


    # ========================================================
    # STEP 5 — DECISION
    # ========================================================

    command = (
        evaluate_room_policy(
            state
        )
    )


    if (
        command["action"]
        == "ACTIVATE_SLEEP_MODE"
    ):

        decision_status = "ADAPT"

        add_log(
            logs,
            "DECISION",
            (
                "Patient awake + room too hot "
                "+ too bright → activate Sleep Mode."
            ),
        )

    else:

        decision_status = "WAITING"


    render_all(
        state,
        "DECISION",
        decision_status,
        logs,
        history,
        mqtt_message,
    )

    time.sleep(1.6)


    # ========================================================
    # STEP 6 — MQTT
    # ========================================================

    mqtt_message = (
        build_mqtt_message(
            command
        )
    )


    state["room"]["mode"] = (
        "ADAPTING"
    )


    add_log(
        logs,
        "MQTT",
        (
            "Sleep Mode command published "
            "to hospital/room/204/control."
        ),
    )


    render_all(
        state,
        "MQTT",
        "ADAPT",
        logs,
        history,
        mqtt_message,
    )

    time.sleep(1.3)


    # ========================================================
    # ACTUATION + FEEDBACK LOOP
    # ========================================================

    state["room"]["ac_on"] = True

    state["room"]["ac_setpoint"] = (
        PREFERENCES[
            "sleep_temperature"
        ]
    )


    initial_temperature = (
        state["room"]["temperature"]
    )

    initial_lux = (
        state["room"]["lux"]
    )

    initial_lights = (
        state["room"]["lights_pct"]
    )

    initial_blinds = (
        state["room"]["blinds_open_pct"]
    )

    initial_movement = (
        state["patient"]["movement"]
    )

    initial_hr = (
        state["patient"]["heart_rate"]
    )

    initial_rr = (
        state["patient"]["breathing_rate"]
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
            1
            - (1 - fraction) ** 2
        )


        # ----------------------------------------------------
        # ROOM ADAPTATION
        # ----------------------------------------------------

        state["room"]["temperature"] = lerp(
            initial_temperature,
            21.6,
            eased,
        )


        state["room"]["lux"] = lerp(
            initial_lux,
            40,
            eased,
        )


        state["room"]["lights_pct"] = lerp(
            initial_lights,
            PREFERENCES[
                "sleep_lights_pct"
            ],
            eased,
        )


        state["room"]["blinds_open_pct"] = lerp(
            initial_blinds,
            PREFERENCES[
                "sleep_blinds_open_pct"
            ],
            eased,
        )


        # ----------------------------------------------------
        # PATIENT RESPONSE
        # ----------------------------------------------------

        state["patient"]["movement"] = lerp(
            initial_movement,
            0.02,
            eased,
        )


        state["patient"]["heart_rate"] = lerp(
            initial_hr,
            67,
            eased,
        )


        state["patient"]["breathing_rate"] = lerp(
            initial_rr,
            14,
            eased,
        )


        # ----------------------------------------------------
        # FEEDBACK → DIGITAL TWIN → AI
        # ----------------------------------------------------

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


        add_history(
            history,
            state,
            step,
        )


        # ----------------------------------------------------
        # EVENT LOG
        # ----------------------------------------------------

        if step == 1:

            add_log(
                logs,
                "ACTUATION",
                (
                    "A/C ON | lights dimming | "
                    "blinds closing."
                ),
            )


        if step == 6:

            add_log(
                logs,
                "FEEDBACK",
                (
                    "Physical actuator state "
                    "received through MQTT."
                ),
            )


        if step == 11:

            add_log(
                logs,
                "DIGITAL TWIN",
                (
                    "New physical room "
                    "state synchronized."
                ),
            )


        if step == 15:

            add_log(
                logs,
                "AI",
                (
                    "Movement decreasing and "
                    "sleep probability increasing."
                ),
            )


        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        if sleep_state == "ASLEEP":

            decision_status = "ASLEEP"

        else:

            decision_status = "ADAPTING"


        if step <= 10:

            active_stage = "ACTUATION"

        else:

            active_stage = "FEEDBACK"


        render_all(
            state,
            active_stage,
            decision_status,
            logs,
            history,
            mqtt_message,
        )


        time.sleep(0.32)


    # ========================================================
    # FINAL STATE
    # ========================================================

    state["room"]["mode"] = (
        "SLEEP MODE"
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


    add_log(
        logs,
        "AI",
        (
            f"Patient detected as "
            f"{sleep_state} "
            f"({probability * 100:.0f}%)."
        ),
    )


    add_log(
        logs,
        "DECISION",
        (
            "Sleep conditions reached → "
            "maintain Sleep Mode."
        ),
    )


    add_log(
        logs,
        "SYSTEM",
        "Scenario completed successfully.",
    )


    render_all(
        state,
        "FEEDBACK",
        "ASLEEP",
        logs,
        history,
        mqtt_message,
    )


    # --------------------------------------------------------
    # SAVE FINAL STATE
    # --------------------------------------------------------

    st.session_state.state = (
        copy.deepcopy(
            state
        )
    )

    st.session_state.logs = (
        list(logs)
    )

    st.session_state.history = (
        list(history)
    )

    st.session_state.mqtt = (
        mqtt_message
    )

    st.session_state.decision = (
        "ASLEEP"
    )


# ============================================================
# DISPLAY
# ============================================================

if start_demo:

    run_demo()

else:

    state = (
        copy.deepcopy(
            st.session_state.state
        )
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


    render_all(
        state,
        None,
        st.session_state.decision,
        st.session_state.logs,
        st.session_state.history,
        st.session_state.mqtt,
    )


# ============================================================
# ARCHITECTURE EXPLANATION
# ============================================================

st.divider()


with st.expander(
    "ℹ️ How this demo maps to the C4 architecture"
):

    st.markdown(
        """
### 1. Sensors

The simulated sensors provide:

- Heart rate
- Breathing rate
- Movement
- Room temperature
- Ambient light

### 2. IoT Data Context & Normalization Service

The incoming sensor data is mapped to:

**Room 204 → Patient P12**

### 3. Patient-in-Room Digital Twin

The Digital Twin maintains the synchronized current state of:

- Patient
- Room
- Devices
- Derived sleep state

### 4. AI Analytics & Prediction Service

The AI estimates:

**AWAKE → DROWSY → ASLEEP**

and produces a sleep probability.

The AI does not directly control the room.

### 5. Decision & Control Service

The Decision Service combines:

**Digital Twin + AI estimate + thresholds + preferences**

and makes the final decision.

### 6. MQTT + Actuation Gateway

The Sleep Mode command is published through MQTT.

The Actuation Gateway controls:

- Lights
- Motorized blinds
- Air conditioning

### 7. Feedback

The actuator state returns through MQTT and updates the Digital Twin.

### 8. Clinical Alert Service

The Clinical Alert Service remains **IDLE** because this scenario concerns sleep and room comfort, not a clinical emergency.
"""
    )