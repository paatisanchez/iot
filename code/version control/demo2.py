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
    page_title="Smart Hospital - Medical Emergency Demo",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("🏥 Smart Hospital — Medical Emergency Demo")

st.caption(
    "Sensors → Context → Digital Twin → AI → "
    "Decision → Alert Service → MQTT → Staff Alert Device"
)

st.warning(
    "⚠️ Demo thresholds are synthetic and are used only to demonstrate "
    "the architecture. They are not intended for clinical use."
)


# ============================================================
# IDENTIFIERS
# ============================================================

ROOM_ID = "204"
PATIENT_ID = "P12"


# ============================================================
# SYNTHETIC DEMO THRESHOLDS
# ============================================================

DEMO_THRESHOLDS = {
    "high_hr": 140,
    "high_rr": 27,
    "high_anomaly_score": 0.82,

    "recovered_hr_max": 95,
    "recovered_rr_max": 20,
    "recovered_anomaly_max": 0.25,
}


# ============================================================
# INITIAL SYSTEM STATE
# ============================================================

INITIAL_STATE = {

    "patient": {
        "id": PATIENT_ID,

        "heart_rate": 78.0,
        "breathing_rate": 16.0,

        "movement": "NORMAL",

        "anomaly_score": 0.0,
    },

    "room": {
        "id": ROOM_ID,
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
        "timestamp": None,
    },
}


# ============================================================
# HELPERS
# ============================================================

def clamp(value, minimum=0.0, maximum=1.0):
    return max(
        minimum,
        min(maximum, value)
    )


def lerp(start, end, fraction):
    return (
        start
        + (end - start) * fraction
    )


# ============================================================
# AI ANALYTICS SERVICE
# ============================================================

def calculate_anomaly_score(state):
    """
    Synthetic demo anomaly model.

    AI outputs an anomaly score.

    It DOES NOT make the final alert decision.
    """

    hr = state["patient"]["heart_rate"]
    rr = state["patient"]["breathing_rate"]

    hr_score = clamp(
        (hr - 90) / 60
    )

    rr_score = clamp(
        (rr - 18) / 12
    )

    score = (
        0.65 * hr_score
        + 0.35 * rr_score
    )

    return clamp(score)


# ============================================================
# DECISION & CONTROL SERVICE
# ============================================================

def evaluate_clinical_state(state):
    """
    FINAL decision is made here.

    Inputs:
    - Digital Twin current state
    - AI anomaly score
    - configured demo thresholds
    """

    hr = state["patient"]["heart_rate"]

    rr = state["patient"]["breathing_rate"]

    anomaly = state["patient"]["anomaly_score"]


    if (
        hr >= DEMO_THRESHOLDS["high_hr"]
        or rr >= DEMO_THRESHOLDS["high_rr"]
        or anomaly >= DEMO_THRESHOLDS["high_anomaly_score"]
    ):

        return {
            "status": "ABNORMAL",
            "severity": "HIGH",
            "trigger_alert": True,
        }


    return {
        "status": "NORMAL",
        "severity": None,
        "trigger_alert": False,
    }


def patient_has_recovered(state):

    hr = state["patient"]["heart_rate"]

    rr = state["patient"]["breathing_rate"]

    anomaly = state["patient"]["anomaly_score"]


    return (
        hr <= DEMO_THRESHOLDS["recovered_hr_max"]
        and rr <= DEMO_THRESHOLDS["recovered_rr_max"]
        and anomaly <= DEMO_THRESHOLDS["recovered_anomaly_max"]
    )


# ============================================================
# MQTT MESSAGES
# ============================================================

def mqtt_activate_alert():

    return {
        "topic": "hospital/staff-office/alert-device",

        "payload": {
            "command": "ACTIVATE",

            "patientId": PATIENT_ID,

            "roomId": ROOM_ID,

            "severity": "HIGH",

            "redLight": "ON",

            "buzzer": "ON",
        },
    }


def mqtt_silence_alert():

    return {
        "topic": "hospital/staff-office/alert-device",

        "payload": {
            "command": "SILENCE",

            "patientId": PATIENT_ID,

            "roomId": ROOM_ID,

            "redLight": "ON",

            "buzzer": "OFF",
        },
    }


def mqtt_reset_alert():

    return {
        "topic": "hospital/staff-office/alert-device",

        "payload": {
            "command": "RESET",

            "patientId": PATIENT_ID,

            "roomId": ROOM_ID,

            "redLight": "OFF",

            "buzzer": "OFF",
        },
    }


# ============================================================
# DIGITAL TWIN JSON
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
                state["patient"]["movement"],

            "AI_anomalyScore":
                round(
                    state["patient"]["anomaly_score"],
                    2
                ),
        },

        "clinicalState": {

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


# ============================================================
# VISUAL PATIENT MONITOR + STAFF ALERT DEVICE
# ============================================================

def monitor_html(state):

    patient = state["patient"]

    alert = state["alert"]

    clinical = state["clinical"]


    hr = patient["heart_rate"]

    rr = patient["breathing_rate"]

    anomaly = patient["anomaly_score"]


    # --------------------------------------------------------
    # PATIENT COLOR
    # --------------------------------------------------------

    if clinical["severity"] == "HIGH":

        status_color = "#dc2626"
        clinical_label = "HIGH SEVERITY ALERT"

    elif alert["state"] == "RESOLVED":

        status_color = "#16a34a"
        clinical_label = "STABLE"

    else:

        status_color = "#16a34a"
        clinical_label = "MONITORING"


    # --------------------------------------------------------
    # ALERT DEVICE
    # --------------------------------------------------------

    if alert["red_light"]:

        light_color = "#ef4444"

        light_shadow = (
            "0 0 15px #ef4444, "
            "0 0 35px rgba(239,68,68,.75)"
        )

    else:

        light_color = "#6b7280"
        light_shadow = "none"


    if alert["buzzer"]:

        buzzer_icon = "🔊"
        buzzer_text = "BUZZER ON"

    else:

        buzzer_icon = "🔇"
        buzzer_text = "BUZZER OFF"


    # --------------------------------------------------------
    # RED LIGHT BLINKING
    # --------------------------------------------------------

    if (
        alert["state"] == "ACTIVE"
        and alert["red_light"]
    ):

        light_animation = (
            "blink 0.7s infinite"
        )

    else:

        light_animation = "none"


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

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Arial,
        sans-serif;

    background: transparent;
}}


@keyframes blink {{

    0% {{
        opacity: 1;
    }}

    50% {{
        opacity: .35;
    }}

    100% {{
        opacity: 1;
    }}

}}


.demo-wrapper {{

    display: grid;

    grid-template-columns:
        1.5fr 0.8fr;

    gap: 18px;

    width: 100%;

}}


.monitor {{

    min-height: 390px;

    border-radius: 22px;

    padding: 22px;

    color: white;

    background:
        linear-gradient(
            145deg,
            #111827,
            #020617
        );

    border:
        1px solid #374151;

    box-shadow:
        0 12px 35px
        rgba(0,0,0,.15);

}}


.monitor-header {{

    display: flex;

    align-items: center;

    justify-content: space-between;

    padding-bottom: 13px;

    border-bottom:
        1px solid #374151;

}}


.monitor-title {{

    font-size: 18px;

    font-weight: 750;

}}


.patient-id {{

    padding:
        6px 10px;

    border-radius: 999px;

    background: #1f2937;

    font-size: 12px;

}}


.patient-area {{

    display: grid;

    grid-template-columns:
        0.55fr 1fr;

    align-items: center;

    gap: 15px;

    margin-top: 28px;

}}


.patient-icon {{

    font-size: 105px;

    text-align: center;

}}


.vital {{

    margin-bottom: 22px;

}}


.vital-label {{

    color: #9ca3af;

    font-size: 12px;

    text-transform: uppercase;

    letter-spacing: .06em;

}}


.vital-value {{

    font-size: 46px;

    line-height: 1.05;

    font-weight: 800;

}}


.unit {{

    font-size: 15px;

    color: #9ca3af;

}}


.anomaly-panel {{

    margin-top: 15px;

    padding: 14px;

    border-radius: 13px;

    background:
        rgba(255,255,255,.06);

}}


.anomaly-header {{

    display: flex;

    justify-content: space-between;

    font-size: 12px;

    margin-bottom: 8px;

}}


.anomaly-track {{

    height: 12px;

    width: 100%;

    border-radius: 999px;

    overflow: hidden;

    background: #374151;

}}


.anomaly-fill {{

    width:
        {anomaly * 100:.1f}%;

    height: 100%;

    background:
        {status_color};

}}


.clinical-status {{

    margin-top: 18px;

    padding:
        10px 12px;

    border-radius: 10px;

    background:
        {status_color};

    font-weight: 800;

    text-align: center;

}}


.alert-device {{

    min-height: 390px;

    border-radius: 22px;

    padding:
        22px 18px;

    border:
        1px solid #d1d5db;

    background:
        #f9fafb;

    display: flex;

    flex-direction: column;

    align-items: center;

    justify-content: center;

    text-align: center;

}}


.device-title {{

    font-size: 14px;

    font-weight: 800;

    margin-bottom: 25px;

    color: #111827;

}}


.red-light {{

    width: 92px;

    height: 92px;

    border-radius: 50%;

    background:
        {light_color};

    box-shadow:
        {light_shadow};

    animation:
        {light_animation};

    margin-bottom: 28px;

    border:
        6px solid #d1d5db;

}}


.buzzer {{

    font-size: 52px;

    margin-bottom: 5px;

}}


.buzzer-text {{

    color: #374151;

    font-size: 13px;

    font-weight: 800;

}}


.alert-state {{

    margin-top: 25px;

    padding:
        7px 12px;

    border-radius: 999px;

    background: #111827;

    color: white;

    font-size: 11px;

    font-weight: 800;

}}

</style>

</head>


<body>


<div class="demo-wrapper">


    <div class="monitor">

        <div class="monitor-header">

            <div class="monitor-title">

                🫀 Patient Monitor

            </div>

            <div class="patient-id">

                Room {ROOM_ID}
                · Patient {PATIENT_ID}

            </div>

        </div>


        <div class="patient-area">


            <div class="patient-icon">

                🛏️

            </div>


            <div>


                <div class="vital">

                    <div class="vital-label">

                        ❤️ Heart rate

                    </div>

                    <div class="vital-value">

                        {hr:.0f}

                        <span class="unit">

                            bpm

                        </span>

                    </div>

                </div>


                <div class="vital">

                    <div class="vital-label">

                        🫁 Breathing rate

                    </div>

                    <div class="vital-value">

                        {rr:.0f}

                        <span class="unit">

                            rpm

                        </span>

                    </div>

                </div>


            </div>


        </div>


        <div class="anomaly-panel">

            <div class="anomaly-header">

                <span>
                    AI anomaly score
                </span>

                <b>
                    {anomaly * 100:.0f}%
                </b>

            </div>


            <div class="anomaly-track">

                <div class="anomaly-fill"></div>

            </div>

        </div>


        <div class="clinical-status">

            {clinical_label}

        </div>


    </div>


    <div class="alert-device">


        <div class="device-title">

            🚨 Medical Staff Office
            <br>
            Alert Device

        </div>


        <div class="red-light"></div>


        <div class="buzzer">

            {buzzer_icon}

        </div>


        <div class="buzzer-text">

            {buzzer_text}

        </div>


        <div class="alert-state">

            {alert["state"]}

        </div>


    </div>


</div>


</body>

</html>
"""


# ============================================================
# EVENT LOG + HISTORY
# ============================================================

def add_log(logs, source, message):

    logs.append(
        f"{source} → {message}"
    )


def add_history(history, state, step):

    history.append({

        "step":
            step,

        "Heart rate":
            state["patient"]["heart_rate"],

        "Breathing rate":
            state["patient"]["breathing_rate"],

        "AI anomaly score":
            state["patient"]["anomaly_score"] * 100,

    })


# ============================================================
# PIPELINE
# ============================================================

PIPELINE = [
    "SENSORS",
    "CONTEXT",
    "DIGITAL TWIN",
    "AI",
    "DECISION",
    "ALERT SERVICE",
    "MQTT",
    "STAFF DEVICE",
]


# ============================================================
# SESSION STATE
# ============================================================

if "emergency_state" not in st.session_state:

    st.session_state.emergency_state = (
        copy.deepcopy(
            INITIAL_STATE
        )
    )


if "emergency_logs" not in st.session_state:

    st.session_state.emergency_logs = []


if "emergency_history" not in st.session_state:

    st.session_state.emergency_history = []


if "emergency_mqtt" not in st.session_state:

    st.session_state.emergency_mqtt = None


if "demo_phase" not in st.session_state:

    st.session_state.demo_phase = "IDLE"


if "decision_message" not in st.session_state:

    st.session_state.decision_message = (
        "Patient currently stable."
    )


# ============================================================
# TOP CONTROLS
# ============================================================

control_columns = st.columns(
    [1, 1, 1.4, 1.4, 3]
)


with control_columns[0]:

    start_demo = st.button(
        "▶ START EMERGENCY",
        type="primary",
        use_container_width=True,
        disabled=(
            st.session_state.demo_phase
            not in ["IDLE", "RESOLVED"]
        ),
    )


with control_columns[1]:

    reset_demo = st.button(
        "↻ RESET",
        use_container_width=True,
    )


with control_columns[2]:

    acknowledge_alert = st.button(
        "✓ ACKNOWLEDGE ALERT",
        use_container_width=True,
        disabled=(
            st.session_state.demo_phase
            != "ACTIVE"
        ),
    )


with control_columns[3]:

    simulate_recovery = st.button(
        "♡ SIMULATE RECOVERY",
        use_container_width=True,
        disabled=(
            st.session_state.demo_phase
            != "ACKNOWLEDGED"
        ),
    )


with control_columns[4]:

    st.info(
        "The demo stops when the clinical alert becomes ACTIVE. "
        "A healthcare professional must acknowledge it before "
        "the recovery phase can begin."
    )


# ============================================================
# RESET
# ============================================================

if reset_demo:

    st.session_state.emergency_state = (
        copy.deepcopy(
            INITIAL_STATE
        )
    )

    st.session_state.emergency_logs = []

    st.session_state.emergency_history = []

    st.session_state.emergency_mqtt = None

    st.session_state.demo_phase = "IDLE"

    st.session_state.decision_message = (
        "Patient currently stable."
    )

    st.rerun()


# ============================================================
# PIPELINE PLACEHOLDERS
# ============================================================

pipeline_columns = st.columns(
    len(PIPELINE)
)

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

            slot.error(
                f"▶ {stage}"
            )

        else:

            slot.caption(
                stage
            )


# ============================================================
# MAIN PAGE LAYOUT
# ============================================================

st.divider()


left_column, right_column = st.columns(
    [1.2, 1],
    gap="large",
)


# ============================================================
# LEFT COLUMN
# ============================================================

with left_column:

    st.subheader(
        "🏥 Patient & Physical Alert System"
    )

    monitor_slot = st.empty()


    st.markdown(
        "### 📡 Architecture Event Log"
    )

    log_slot = st.empty()


    mqtt_title_slot = st.empty()

    mqtt_slot = st.empty()


# ============================================================
# RIGHT COLUMN
# ============================================================

with right_column:

    st.subheader(
        "🪞 Live Digital Twin"
    )

    metrics_slot = st.empty()


    ai_slot = st.empty()


    decision_slot = st.empty()


    alert_slot = st.empty()


    st.markdown(
        "### 🪞 Digital Twin Snapshot"
    )

    twin_slot = st.empty()


# ============================================================
# CHARTS
# ============================================================

st.divider()

st.subheader(
    "📈 Patient State Evolution"
)


chart_1, chart_2, chart_3 = st.columns(3)


with chart_1:

    hr_chart_slot = st.empty()


with chart_2:

    rr_chart_slot = st.empty()


with chart_3:

    anomaly_chart_slot = st.empty()


# ============================================================
# RENDER FUNCTIONS
# ============================================================

def render_monitor(state):

    monitor_slot.empty()

    with monitor_slot.container():

        components.html(
            monitor_html(state),
            height=415,
            scrolling=False,
        )


def render_metrics(state):

    metrics_slot.empty()

    with metrics_slot.container():

        c1, c2 = st.columns(2)


        with c1:

            st.metric(
                "❤️ Heart rate",
                (
                    f"{state['patient']['heart_rate']:.0f} bpm"
                ),
            )

            st.caption(
                "Synthetic demo HIGH threshold: "
                f"{DEMO_THRESHOLDS['high_hr']} bpm"
            )


        with c2:

            st.metric(
                "🫁 Breathing rate",
                (
                    f"{state['patient']['breathing_rate']:.0f} rpm"
                ),
            )

            st.caption(
                "Synthetic demo HIGH threshold: "
                f"{DEMO_THRESHOLDS['high_rr']} rpm"
            )


def render_ai(state):

    ai_slot.empty()

    with ai_slot.container():

        st.markdown(
            "### 🤖 AI Anomaly Detection"
        )


        score = (
            state["patient"]["anomaly_score"]
        )


        st.progress(
            score
        )


        if score >= DEMO_THRESHOLDS[
            "high_anomaly_score"
        ]:

            st.error(
                f"⚠️ HIGH ANOMALY — "
                f"{score * 100:.0f}%"
            )

        elif score >= 0.45:

            st.warning(
                f"Elevated anomaly score — "
                f"{score * 100:.0f}%"
            )

        else:

            st.success(
                f"Normal / low anomaly score — "
                f"{score * 100:.0f}%"
            )


        st.caption(
            "The AI estimates abnormality. "
            "It does not activate the clinical alert directly."
        )


def render_decision():

    decision_slot.empty()

    with decision_slot.container():

        st.markdown(
            "### 🧠 Decision & Control Service"
        )


        if (
            st.session_state.demo_phase
            == "IDLE"
        ):

            st.success(
                "Patient state considered normal."
            )


        elif (
            st.session_state.demo_phase
            == "ESCALATING"
        ):

            st.warning(
                "Monitoring abnormal trend..."
            )


        elif (
            st.session_state.demo_phase
            in ["ACTIVE", "ACKNOWLEDGED"]
        ):

            st.error(
                "🚨 FINAL DECISION: "
                "HIGH severity clinical alert"
            )


            st.write(
                "Patient: **P12**"
            )

            st.write(
                "Room: **204**"
            )

            st.write(
                "Abnormal parameters: "
                "**heart rate + breathing rate**"
            )


        elif (
            st.session_state.demo_phase
            == "RECOVERING"
        ):

            st.warning(
                "Monitoring recovery..."
            )


        elif (
            st.session_state.demo_phase
            == "RESOLVED"
        ):

            st.success(
                "✅ Patient condition returned "
                "to demo normal range."
            )


def render_alert(state):

    alert_slot.empty()

    with alert_slot.container():

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

            st.caption(
                "Waiting for healthcare staff acknowledgement."
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

            st.caption(
                "The alert has been seen, "
                "but the patient condition is still abnormal."
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

            st.caption(
                "Patient state returned to configured demo range."
            )


def render_log(logs):

    log_slot.empty()

    with log_slot.container():

        if not logs:

            st.info(
                "Waiting for demo..."
            )

        else:

            log_text = "\n".join(
                logs[-9:]
            )

            st.code(
                log_text,
                language=None,
            )


def render_mqtt(message):

    mqtt_title_slot.empty()

    mqtt_slot.empty()


    mqtt_title_slot.markdown(
        "### 📨 Latest MQTT Command"
    )


    if message is None:

        mqtt_slot.caption(
            "No alert-device command published yet."
        )


    else:

        mqtt_slot.code(
            json.dumps(
                message,
                indent=2,
            ),
            language="json",
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


def render_charts(history):

    hr_chart_slot.empty()

    rr_chart_slot.empty()

    anomaly_chart_slot.empty()


    if len(history) < 2:

        hr_chart_slot.caption(
            "Heart-rate data will appear during the demo."
        )

        rr_chart_slot.caption(
            "Breathing-rate data will appear during the demo."
        )

        anomaly_chart_slot.caption(
            "AI anomaly score will appear during the demo."
        )

        return


    df = (
        pd.DataFrame(history)
        .set_index("step")
    )


    with hr_chart_slot.container():

        st.caption(
            "Heart rate"
        )

        st.line_chart(
            df[
                ["Heart rate"]
            ],
            height=190,
        )


    with rr_chart_slot.container():

        st.caption(
            "Breathing rate"
        )

        st.line_chart(
            df[
                ["Breathing rate"]
            ],
            height=190,
        )


    with anomaly_chart_slot.container():

        st.caption(
            "AI anomaly score (%)"
        )

        st.line_chart(
            df[
                ["AI anomaly score"]
            ],
            height=190,
        )


def render_all(
    active_pipeline=None
):

    state = (
        st.session_state.emergency_state
    )

    render_pipeline(
        active_pipeline
    )

    render_monitor(
        state
    )

    render_metrics(
        state
    )

    render_ai(
        state
    )

    render_decision()

    render_alert(
        state
    )

    render_log(
        st.session_state.emergency_logs
    )

    render_mqtt(
        st.session_state.emergency_mqtt
    )

    render_twin(
        state
    )

    render_charts(
        st.session_state.emergency_history
    )


# ============================================================
# START EMERGENCY ANIMATION
# ============================================================

def run_emergency():

    state = copy.deepcopy(
        INITIAL_STATE
    )

    logs = []

    history = []


    st.session_state.demo_phase = (
        "ESCALATING"
    )

    st.session_state.emergency_state = (
        state
    )

    st.session_state.emergency_logs = (
        logs
    )

    st.session_state.emergency_history = (
        history
    )

    st.session_state.emergency_mqtt = (
        None
    )


    # ========================================================
    # NORMAL SENSOR STATE
    # ========================================================

    add_log(
        logs,
        "SENSORS",
        (
            "HR=78 bpm | RR=16 rpm | "
            "patient initially stable."
        ),
    )


    add_history(
        history,
        state,
        0,
    )


    render_all(
        "SENSORS"
    )

    time.sleep(1.2)


    # ========================================================
    # CONTEXT
    # ========================================================

    add_log(
        logs,
        "CONTEXT",
        (
            "Measurements mapped to "
            "Patient P12 in Room 204."
        ),
    )


    render_all(
        "CONTEXT"
    )

    time.sleep(1.1)


    # ========================================================
    # DIGITAL TWIN
    # ========================================================

    add_log(
        logs,
        "DIGITAL TWIN",
        (
            "Initial patient state synchronized."
        ),
    )


    render_all(
        "DIGITAL TWIN"
    )

    time.sleep(1.1)


    # ========================================================
    # ABNORMAL PHYSIOLOGICAL TREND
    # ========================================================

    initial_hr = 78.0

    final_hr = 148.0

    initial_rr = 16.0

    final_rr = 28.0


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
                initial_hr,
                final_hr,
                eased,
            )
        )


        state["patient"]["breathing_rate"] = (
            lerp(
                initial_rr,
                final_rr,
                eased,
            )
        )


        anomaly = (
            calculate_anomaly_score(
                state
            )
        )


        state["patient"]["anomaly_score"] = (
            anomaly
        )


        decision = (
            evaluate_clinical_state(
                state
            )
        )


        state["clinical"]["status"] = (
            decision["status"]
        )

        state["clinical"]["severity"] = (
            decision["severity"]
        )


        add_history(
            history,
            state,
            step,
        )


        if step == 5:

            add_log(
                logs,
                "SENSORS",
                (
                    "Heart rate and breathing rate "
                    "are increasing."
                ),
            )


        if step == 10:

            add_log(
                logs,
                "DIGITAL TWIN",
                (
                    "Updated physiological state synchronized."
                ),
            )


        if step == 14:

            add_log(
                logs,
                "AI",
                (
                    "Anomaly score rising significantly."
                ),
            )


        if step < 8:

            active = "SENSORS"

        elif step < 14:

            active = "DIGITAL TWIN"

        else:

            active = "AI"


        render_all(
            active
        )


        time.sleep(0.25)


    # ========================================================
    # FINAL AI RESULT
    # ========================================================

    add_log(
        logs,
        "AI",
        (
            f"Anomaly score="
            f"{state['patient']['anomaly_score']:.2f}"
        ),
    )


    render_all(
        "AI"
    )

    time.sleep(1.1)


    # ========================================================
    # DECISION SERVICE
    # ========================================================

    decision = (
        evaluate_clinical_state(
            state
        )
    )


    state["clinical"]["status"] = (
        decision["status"]
    )

    state["clinical"]["severity"] = (
        decision["severity"]
    )


    add_log(
        logs,
        "DECISION",
        (
            "HIGH severity clinical alert "
            "generated for Patient P12 / Room 204."
        ),
    )


    render_all(
        "DECISION"
    )

    time.sleep(1.2)


    # ========================================================
    # ALERT LIFECYCLE SERVICE
    # ========================================================

    state["alert"]["state"] = (
        "ACTIVE"
    )

    state["alert"]["red_light"] = (
        True
    )

    state["alert"]["buzzer"] = (
        True
    )

    state["alert"]["timestamp"] = (
        datetime.now().strftime(
            "%H:%M:%S"
        )
    )


    st.session_state.demo_phase = (
        "ACTIVE"
    )


    add_log(
        logs,
        "ALERT SERVICE",
        (
            "Alert lifecycle state → ACTIVE."
        ),
    )


    render_all(
        "ALERT SERVICE"
    )

    time.sleep(1.1)


    # ========================================================
    # MQTT ACTIVATE
    # ========================================================

    st.session_state.emergency_mqtt = (
        mqtt_activate_alert()
    )


    add_log(
        logs,
        "MQTT",
        (
            "ACTIVATE command published "
            "for staff alert device."
        ),
    )


    render_all(
        "MQTT"
    )

    time.sleep(1.1)


    # ========================================================
    # STAFF ALERT DEVICE
    # ========================================================

    add_log(
        logs,
        "STAFF DEVICE",
        (
            "Red light ON | buzzer ON."
        ),
    )


    render_all(
        "STAFF DEVICE"
    )

    time.sleep(1.0)


    # Save state
    st.session_state.emergency_state = (
        state
    )

    st.session_state.emergency_logs = (
        logs
    )

    st.session_state.emergency_history = (
        history
    )


# ============================================================
# ACKNOWLEDGE ALERT
# ============================================================

def acknowledge():

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


    st.session_state.demo_phase = (
        "ACKNOWLEDGED"
    )


    st.session_state.emergency_mqtt = (
        mqtt_silence_alert()
    )


    add_log(
        st.session_state.emergency_logs,
        "MEDICAL STAFF",
        (
            "Clinical alert acknowledged "
            "through dashboard."
        ),
    )


    add_log(
        st.session_state.emergency_logs,
        "ALERT SERVICE",
        (
            "State → ACKNOWLEDGED."
        ),
    )


    add_log(
        st.session_state.emergency_logs,
        "MQTT",
        (
            "SILENCE command published. "
            "Buzzer OFF, red light remains ON."
        ),
    )


# ============================================================
# RECOVERY ANIMATION
# ============================================================

def run_recovery():

    state = (
        st.session_state.emergency_state
    )

    logs = (
        st.session_state.emergency_logs
    )

    history = (
        st.session_state.emergency_history
    )


    st.session_state.demo_phase = (
        "RECOVERING"
    )


    add_log(
        logs,
        "SYSTEM",
        (
            "Simulating patient recovery."
        ),
    )


    initial_hr = (
        state["patient"]["heart_rate"]
    )

    initial_rr = (
        state["patient"]["breathing_rate"]
    )


    final_hr = 82.0

    final_rr = 17.0


    starting_step = (
        len(history)
    )


    steps = 20


    for i in range(
        1,
        steps + 1
    ):

        fraction = (
            i / steps
        )


        eased = (
            1
            - (1 - fraction) ** 2
        )


        state["patient"]["heart_rate"] = (
            lerp(
                initial_hr,
                final_hr,
                eased,
            )
        )


        state["patient"]["breathing_rate"] = (
            lerp(
                initial_rr,
                final_rr,
                eased,
            )
        )


        state["patient"]["anomaly_score"] = (
            calculate_anomaly_score(
                state
            )
        )


        add_history(
            history,
            state,
            starting_step + i,
        )


        if i == 5:

            add_log(
                logs,
                "SENSORS",
                (
                    "Heart rate and breathing rate decreasing."
                ),
            )


        if i == 10:

            add_log(
                logs,
                "DIGITAL TWIN",
                (
                    "Recovery state synchronized."
                ),
            )


        if i == 15:

            add_log(
                logs,
                "AI",
                (
                    "Anomaly score returning "
                    "toward normal range."
                ),
            )


        if i < 7:

            active = "SENSORS"

        elif i < 14:

            active = "DIGITAL TWIN"

        else:

            active = "AI"


        render_all(
            active
        )


        time.sleep(0.27)


    # ========================================================
    # RECOVERY DECISION
    # ========================================================

    if patient_has_recovered(
        state
    ):

        state["clinical"]["status"] = (
            "NORMAL"
        )

        state["clinical"]["severity"] = (
            None
        )


        add_log(
            logs,
            "DECISION",
            (
                "Patient condition considered recovered."
            ),
        )


        render_all(
            "DECISION"
        )

        time.sleep(1.0)


        # ----------------------------------------------------
        # ALERT RESOLVED
        # ----------------------------------------------------

        state["alert"]["state"] = (
            "RESOLVED"
        )

        state["alert"]["red_light"] = (
            False
        )

        state["alert"]["buzzer"] = (
            False
        )


        st.session_state.demo_phase = (
            "RESOLVED"
        )


        add_log(
            logs,
            "ALERT SERVICE",
            (
                "Alert lifecycle state → RESOLVED."
            ),
        )


        render_all(
            "ALERT SERVICE"
        )

        time.sleep(1.0)


        # ----------------------------------------------------
        # MQTT RESET
        # ----------------------------------------------------

        st.session_state.emergency_mqtt = (
            mqtt_reset_alert()
        )


        add_log(
            logs,
            "MQTT",
            (
                "RESET command published."
            ),
        )


        render_all(
            "MQTT"
        )

        time.sleep(1.0)


        add_log(
            logs,
            "STAFF DEVICE",
            (
                "Red light OFF | buzzer OFF."
            ),
        )


        render_all(
            "STAFF DEVICE"
        )


    st.session_state.emergency_state = (
        state
    )


# ============================================================
# BUTTON ACTIONS
# ============================================================

if start_demo:

    run_emergency()

    st.rerun()


if acknowledge_alert:

    acknowledge()

    st.rerun()


if simulate_recovery:

    run_recovery()

    st.rerun()


# ============================================================
# NORMAL PAGE DISPLAY
# ============================================================

render_all(
    None
)


# ============================================================
# ALERT LIFECYCLE EXPLANATION
# ============================================================

st.divider()


with st.expander(
    "ℹ️ How this medical emergency demo maps to the C4 architecture"
):

    st.markdown(
        """
### 1. Patient Physiological Sensors

The simulated patient sensors continuously provide:

- Heart rate
- Breathing rate
- Movement

---

### 2. IoT Data Context & Normalization Service

The incoming sensor measurements are associated with:

**Patient P12 → Room 204**

---

### 3. Patient-in-Room Digital Twin

The Digital Twin maintains the synchronized patient state.

During the emergency it reflects the progressively increasing
heart rate and breathing rate.

---

### 4. AI Analytics & Prediction Service

The AI produces an **anomaly score**.

It does not decide whether the clinical alarm must be activated.

---

### 5. Patient & Room Decision & Control Service

The Decision Service receives:

**Digital Twin state + AI anomaly score + configured thresholds**

and makes the final decision:

**HIGH severity clinical alert**

---

### 6. Clinical Alert Lifecycle Service

The alert lifecycle is:

**ACTIVE → ACKNOWLEDGED → RESOLVED**

#### ACTIVE

- Red light ON
- Buzzer ON

#### ACKNOWLEDGED

A healthcare professional acknowledges the alert through the dashboard.

- Red light remains ON
- Buzzer turns OFF

Acknowledgement does **not** mean the patient has recovered.

#### RESOLVED

When the monitored patient state returns to the configured demo range:

- Red light OFF
- Buzzer OFF

---

### 7. MQTT + Actuation Gateway

The Alert Service publishes:

`ACTIVATE`

then:

`SILENCE`

and finally:

`RESET`

through the MQTT broker.

The Room & Staff Alert Actuation Gateway translates these commands
into the physical red-light and buzzer states.

---

### Important

All thresholds and physiological changes shown in this demo are
**synthetic values created only to demonstrate the IoT architecture**.
They must not be interpreted as medical guidance or clinically validated thresholds.
"""
    )