import copy
import json

import numpy as np
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Smart Hospital IoT Demo", page_icon="🏥", layout="wide",
                   initial_sidebar_state="collapsed")

ROOM, PAT = "204", "P12"

# ============================================================
# C4 COMPONENTS (same names as the C4 L2 / L3 diagrams)
# ============================================================
PPS = "Patient Physiological Sensors"
RES = "Room Environment Sensors"
REA = "Room Environment Actuators"
SOD = "Staff Office Alert Device"
SIG = "Sensor Ingestion Gateway"
ACT = "Room & Staff Alert Actuation Gateway"
BRK = "Hospital IoT Message Broker"
CTX = "IoT Data Context & Normalization Service"
OPDB = "Patient-Room Operational Database"
TDB = "Patient & Room Telemetry Database"
TWIN = "Patient-in-Room Digital Twin"
AI = "AI Analytics & Prediction Service"
DEC = "Patient & Room Decision & Control Service"
LIFE = "Clinical Alert Lifecycle Service"
PORT = "Clinical Monitoring Portal"
DTSR = "Digital Twin State Receiver"
AIRR = "AI Result Receiver"
COORD = "Decision Coordinator"
CFG = "Configuration & Preference Repository"
SLE = "Sleep & Room Adaptation Engine"
RCP = "Room Control Command Publisher"
CADE = "Clinical Alert Decision Engine"
SCT = "Sustained Condition Tracker"
CAEP = "Clinical Alert Event Publisher"

PHY, EDGE, INT, L3C, BACK = "#64748b", "#2E7D5B", "#7B3FA0", "#B8541A", "#1168BD"
NODES = {
    PPS: (22, 62, 150, 46, PHY), RES: (22, 128, 150, 46, PHY), REA: (22, 196, 150, 46, PHY),
    SIG: (206, 80, 150, 50, EDGE), ACT: (206, 190, 150, 58, EDGE),
    SOD: (22, 318, 160, 46, PHY), PORT: (200, 318, 160, 46, BACK),
    CTX: (410, 62, 210, 54, BACK), BRK: (410, 160, 210, 54, BACK), LIFE: (410, 270, 210, 54, BACK),
    OPDB: (650, 62, 190, 46, BACK), TDB: (650, 122, 190, 46, BACK), TWIN: (650, 200, 190, 54, INT),
    DEC: (870, 62, 200, 54, L3C), AI: (870, 200, 200, 54, INT),
    DTSR: (24, 420, 210, 46, L3C), AIRR: (254, 420, 210, 46, L3C), COORD: (484, 420, 210, 46, L3C),
    CFG: (714, 420, 220, 46, BACK), SLE: (954, 420, 224, 46, L3C),
    CADE: (24, 500, 210, 46, L3C), SCT: (254, 500, 210, 46, "#6B5B95"),
    RCP: (484, 500, 210, 46, L3C), CAEP: (714, 500, 220, 46, L3C),
}
ZONES = [
    (8, 28, 368, 260, "🏨 Room 204 · C4 L2 Edge"),
    (8, 296, 368, 86, "🏢 Medical Staff Room"),
    (392, 28, 800, 354, "☁️ C4 L2 · Hospital Backend Platform"),
    (8, 392, 1184, 176, "🧠 C4 L3 · Decision & Control Service (internals)"),
]


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def lerp(a, b, f):
    return a + (b - a) * f


class Tape:
    """Stores each simulation message together with the physical state at that moment."""

    def __init__(self):
        self.frames, self.n, self.st = [], 0, {}

    def emit(self, src, dst, proto, chan, summary, payload, scope, stage, narr, gate=None):
        self.n += 1
        self.frames.append(dict(id=f"M{self.n:03d}", src=src, dst=dst, proto=proto, chan=chan,
                                summary=summary, payload=payload, scope=scope, stage=stage,
                                narr=narr, gate=gate, state=copy.deepcopy(self.st)))


# ============================================================
# SCENARIO 1 · SLEEP
# ============================================================
PREF = {"sleep_temperature": 21.5, "sleep_light_lux": 60, "sleep_lights_pct": 5, "sleep_blinds_open_pct": 0}
S_STAGES = ["SENSORS", "CONTEXT", "DIGITAL TWIN", "AI", "DECISION", "MQTT", "ACTUATION", "FEEDBACK"]
TARGET = dict(temp=21.6, lux=40, lights=5, blinds=0, mov=0.02, hr=67, rr=14)


def sleep_estimate(s):
    p = clamp(0.45 * (1 - s["mov"]) + 0.25 * clamp(1 - abs(s["hr"] - 62) / 25)
              + 0.20 * clamp(1 - abs(s["rr"] - 13) / 8) + 0.05 * clamp(1 - s["lux"] / 700)
              + 0.05 * clamp(1 - abs(s["temp"] - 21.5) / 6))
    return p, ("ASLEEP" if p >= .8 else "DROWSY" if p >= .45 else "AWAKE")


def sleep_tape():
    T = Tape()
    s = dict(hr=82.0, rr=18.0, mov=0.9, temp=27.5, lux=820.0, lights=80.0, blinds=100.0,
             ac=False, acSet=None, mode="NORMAL", sleep="AWAKE", prob=0.0)
    T.st = s
    e = T.emit

    def ai():
        s["prob"], s["sleep"] = sleep_estimate(s)

    def twin():
        return dict(roomId=ROOM, patient=dict(hr=round(s["hr"]), rr=round(s["rr"]), sleepState=s["sleep"],
                                              sleepProb=round(s["prob"], 2)),
                    room=dict(temp=round(s["temp"], 1), lux=round(s["lux"]), lights=round(s["lights"]),
                              blindsOpen=round(s["blinds"]), ac=s["ac"]))

    ai()
    body = dict(patientId=PAT, heartRate_bpm=82, breathingRate_rpm=18, movement=0.9)
    env = dict(roomId=ROOM, temperature_C=27.5, ambientLight_lux=820)
    tel = dict(patient=body, room=env)
    tp = f"hospital/room/{ROOM}/telemetry"
    e(PPS, SIG, "BLE", "BLE characteristic", "Physiological data", body, "L2", "SENSORS",
      "Patient is awake and moving. Sensors capture heart rate, breathing rate and movement.")
    e(RES, SIG, "BLE / Zigbee", "room sensor net", "Room data", env, "L2", "SENSORS",
      "Room is 27.5 °C and 820 lux: too warm and bright for sleep.")
    e(SIG, BRK, "MQTT/TLS + JSON", tp, "Publish normalized telemetry", tel, "L2", "SENSORS",
      "Gateway combines the readings and publishes them to the MQTT broker.")
    e(BRK, CTX, "MQTT subscription", tp, "Forward telemetry", tel, "L2", "CONTEXT",
      "Broker forwards the event to the context service.")
    e(CTX, OPDB, "SQL", "patient_room_mapping", "Resolve patient ↔ room", dict(patientId=PAT, roomId=ROOM),
      "L2", "CONTEXT", "Room 204 data is linked to patient P12.")
    e(CTX, TDB, "Time-Series API", "telemetry/write", "Store telemetry", tel, "L2", "CONTEXT",
      "Telemetry is stored for history.")
    e(CTX, TWIN, "Internal Event / API", "twin/updatePhysicalState", "Update physical state", tel, "L2",
      "DIGITAL TWIN", "Digital Twin now reflects the patient and room state.")
    e(TWIN, AI, "Internal API", "ai/analyseSleepState", "Send current state", twin(), "L2", "AI",
      "Digital Twin asks AI to estimate the sleep state.")
    e(AI, TWIN, "Internal API", "twin/updateDerivedState", "Update derived state",
      dict(sleepState=s["sleep"], prob=round(s["prob"], 3)), "L2", "AI",
      f"AI result: {s['sleep']} ({s['prob']*100:.0f}%). AI analyzes; it does not control the room.")
    e(TWIN, DEC, "Internal API", "decision/currentState", "Physical + derived state", twin(), "L2", "DECISION",
      "Digital Twin sends the full state to the Decision Service.")
    e(TWIN, DTSR, "Internal API / Event", "DecisionContext.state", "Receive state", twin(), "L3", "DECISION",
      "Inside the Decision Service, state enters through the State Receiver.")
    e(DTSR, COORD, "In-process call", "DecisionContext.state", "Forward state",
      dict(sleepState=s["sleep"], room=env), "L3", "DECISION", "Coordinator receives the context.")
    e(COORD, CFG, "Repository call", "preferences/read", "Read sleep preferences", PREF, "L3", "DECISION",
      "Coordinator loads the target temperature and lighting.")
    e(CFG, OPDB, "SQL", "sleep_preferences", "Read configured targets", PREF, "L3", "DECISION",
      "Preferences are loaded from the operational database.")
    e(COORD, SLE, "In-process call", "evaluate(DecisionContext)", "Evaluate room adaptation",
      dict(sleepState=s["sleep"], room=env, preferences=PREF), "L3", "DECISION",
      "Room conditions are outside the sleep targets → adaptation is required.")
    cmd = dict(mode="SLEEP_MODE", lights_pct=5, blinds_open_pct=0, hvac=dict(enabled=True, setpoint_c=21.5))
    e(SLE, RCP, "In-process event", "RoomControlAction", "Create Sleep Mode targets", cmd, "L3", "DECISION",
      "Decision Service activates Sleep Mode.")
    ct = f"hospital/room/{ROOM}/control"
    s["mode"] = "ADAPTING"
    e(RCP, BRK, "MQTT/TLS + JSON", ct, "Publish blinds / lights / HVAC command", cmd, "L3", "MQTT",
      "Control command is published through MQTT. Room starts adapting.")
    e(BRK, ACT, "MQTT/TLS", ct, "Forward control command", cmd, "L2", "ACTUATION",
      "Broker forwards the command to the room actuation gateway.")
    init = dict(s)
    for k, v in TARGET.items():
        s[k] = lerp(init[k], v, .15)
    s["ac"], s["acSet"] = True, 21.5
    ai()
    e(ACT, REA, "Zigbee / Modbus", "lights + blinds + HVAC", "Control lights, blinds and HVAC", cmd, "L2",
      "ACTUATION", "❄️ HVAC turns on, blinds close and lights dim.")
    for fr in (.45, .75, 1.0):
        for k, v in TARGET.items():
            s[k] = lerp(init[k], v, fr)
        prev = s["sleep"]
        ai()
        if fr == 1.0:
            s["mode"] = "SLEEP MODE"
        act = dict(lights_pct=round(s["lights"]), blindsOpen_pct=round(s["blinds"]),
                   temperature_C=round(s["temp"], 1), acOn=True)
        at = f"hospital/room/{ROOM}/actuator-state"
        e(REA, ACT, "Zigbee / Modbus", "device state / ack", "Report actuator state", act, "L2",
          "FEEDBACK", f"Blinds {round(100-s['blinds'])}% closed, lights {round(s['lights'])}%, {s['temp']:.1f} °C.")
        e(ACT, BRK, "MQTT/TLS", at, "Publish state / ack", act, "L2", "FEEDBACK", "Gateway confirms the applied state.")
        e(BRK, CTX, "MQTT subscription", at, "Forward actuator event", act, "L2", "FEEDBACK",
          "Context service receives the physical confirmation.")
        e(CTX, TWIN, "Internal Event / API", "twin/updateActuatorState", "Close physical-digital loop", act,
          "L2", "FEEDBACK", "Digital Twin resynchronizes with the real room.")
        e(TWIN, AI, "Internal API", "ai/re-evaluateSleepState", "Re-evaluate state", twin(), "L2", "AI",
          "AI re-evaluates using the updated room and patient data.")
        e(AI, TWIN, "Internal API", "twin/updateDerivedState", "Update derived state",
          dict(sleepState=s["sleep"], prob=round(s["prob"], 3)), "L2", "AI",
          f"{'Change: ' + prev + ' → ' if prev != s['sleep'] else ''}{s['sleep']} ({s['prob']*100:.0f}%).")
    e(TWIN, DEC, "Internal API", "decision/currentState", "Final synchronized state", twin(), "L2", "FEEDBACK",
      "😴 Patient is asleep. Sleep Mode remains active.")
    return T.frames


# ============================================================
# SCENARIO 2 · EMERGENCY
# ============================================================
E_STAGES = ["SENSORS", "CONTEXT", "DIGITAL TWIN", "AI", "DECISION", "ALERTS", "MQTT", "DEVICE"]


def anomaly(hr, rr):
    h = float(np.interp(hr, [40, 60, 90, 110, 130], [1, 0, 0, .5, 1]))
    r = float(np.interp(rr, [8, 12, 20, 25], [1, 0, 0, 1]))
    return clamp(1 - (1 - h) * (1 - r))


def level(x):
    return "HIGH" if x >= .75 else "ELEVATED" if x >= .4 else "LOW"


def emg_tape():
    T = Tape()
    s = dict(hr=78.0, rr=16.0, anom=0.0, alert="IDLE", red=False, buz=False, phase="NORMAL", sust=0)
    T.st = s
    e = T.emit
    tp = f"hospital/room/{ROOM}/telemetry"
    dt = "hospital/staff-office/alert-device"

    def smp():
        return dict(patientId=PAT, roomId=ROOM, heartRate_bpm=round(s["hr"], 1), breathingRate_rpm=round(s["rr"], 1))

    def twin():
        return dict(roomId=ROOM, hr=round(s["hr"]), rr=round(s["rr"]), anomaly=round(s["anom"], 2),
                    alert=dict(state=s["alert"], redLight=s["red"], buzzer=s["buz"]))

    def chain(n1, n5):
        p = smp()
        e(SIG, BRK, "MQTT/TLS + JSON", tp, "Publish new sample", p, "L2", "SENSORS", n1)
        e(BRK, CTX, "MQTT subscription", tp, "Forward sample", p, "L2", "CONTEXT", "Sample reaches the context service.")
        e(CTX, TWIN, "Internal Event / API", "twin/updatePhysicalState", "Synchronize state", p, "L2",
          "DIGITAL TWIN", "Digital Twin updates the patient state.")
        e(TWIN, AI, "Internal API", "ai/analyseClinicalState", "Analyze anomaly", p, "L2", "AI",
          "AI calculates the anomaly score.")
        e(AI, DEC, "Internal API", "decision/clinicalPrediction", "Send anomaly score",
          dict(anomalyScore=round(s["anom"], 3), level=level(s["anom"])), "L2", "AI", n5)

    def l3_eval(first, engine_msg):
        e(TWIN, DEC, "Internal API", "decision/currentState", "Physical + derived state", twin(), "L2", "DECISION", first)
        e(TWIN, DTSR, "Internal API / Event", "DecisionContext.state", "Receive state", twin(), "L3", "DECISION",
          "Inside the Decision Service (C4 L3).")
        e(AI, AIRR, "Internal API / Event", "DecisionContext.aiResult", "Recibe anomaly score",
          dict(anomalyScore=round(s["anom"], 3)), "L3", "DECISION", "AI result enters through the AI Result Receiver.")
        e(DTSR, COORD, "In-process call", "DecisionContext.state", "Forward state", dict(hr=round(s["hr"]), rr=round(s["rr"])),
          "L3", "DECISION", "Coordinator combines state + AI result.")
        e(AIRR, COORD, "In-process call", "DecisionContext.aiResult", "Reenvía score", dict(anomalyScore=round(s["anom"], 3)),
          "L3", "DECISION", "Decision context is complete.")
        th = dict(high_anomaly=.75, sustained_samples=3)
        e(COORD, CFG, "Repository call", "thresholds/read", "Read clinical thresholds", th, "L3", "DECISION", "Load configured thresholds.")
        e(CFG, OPDB, "SQL", "clinical_thresholds", "Read thresholds", th, "L3", "DECISION", "Thresholds come from the operational database.")
        e(COORD, CADE, "In-process call", "evaluate(DecisionContext)", "Run clinical evaluation",
          dict(anomalyScore=round(s["anom"], 3), sustainedSamples=s["sust"]), "L3", "DECISION", engine_msg)

    e(PPS, SIG, "BLE", "BLE characteristic", "Initial reading", smp(), "L2", "SENSORS",
      "Patient P12 is stable: 78 bpm, 16 rpm.")
    e(SIG, BRK, "MQTT/TLS + JSON", tp, "Publish telemetry", smp(), "L2", "SENSORS", "Gateway publishes to the MQTT broker.")
    e(BRK, CTX, "MQTT subscription", tp, "Forward telemetry", smp(), "L2", "CONTEXT", "Context service receives it.")
    e(CTX, OPDB, "SQL", "patient_room_mapping", "Resolve P12 ↔ 204", dict(patientId=PAT, roomId=ROOM), "L2", "CONTEXT", "Data is linked to the patient.")
    e(CTX, TDB, "Time-Series API", "telemetry/write", "Store telemetry", smp(), "L2", "CONTEXT", "Telemetry stored.")
    e(CTX, TWIN, "Internal Event / API", "twin/updatePhysicalState", "Synchronize state", smp(), "L2", "DIGITAL TWIN", "Digital Twin reflects the patient state.")
    e(TWIN, AI, "Internal API", "ai/analyseClinicalState", "Send state", twin(), "L2", "AI", "AI analysis: low anomaly.")

    s["phase"] = "ESCALATING"
    for k in range(1, 21):
        f = (k / 20) ** 1.25
        s["hr"], s["rr"] = lerp(78, 148, f), lerp(16, 28, f)
        s["anom"] = anomaly(s["hr"], s["rr"])
        s["sust"] = s["sust"] + 1 if s["anom"] >= .75 else 0
        if k in (5, 10) or s["sust"] >= 3:
            chain(f"⚠️ Patient deteriorates: {s['hr']:.0f} bpm · {s['rr']:.0f} rpm.",
                  f"Anomaly {level(s['anom'])} ({s['anom']*100:.0f}%) · consecutive HIGH samples: {s['sust']}/3.")
        if s["sust"] >= 3:
            break

    l3_eval("A single spike is not enough. The system checks for a sustained anomaly.", "Coordinator requests the final clinical decision.")
    e(CADE, SCT, "In-memory state", "consecutive-sample window", "Lee/actualiza condición sostenida",
      dict(consecutiveHigh=s["sust"]), "L3", "DECISION", f"{s['sust']} consecutive HIGH samples ≥ 3 → sustained condition.")
    ev = dict(event="ALERT", severity="HIGH", patientId=PAT, roomId=ROOM)
    e(CADE, CAEP, "In-process event", "ClinicalDecision", "Create ALERT / HIGH decision", ev, "L3", "DECISION",
      "🚨 Final decision: HIGH severity clinical alert.")
    e(CAEP, LIFE, "Internal Event", "clinical-alert/event", "Send final decision", ev, "L3", "ALERTS",
      "Alert Lifecycle Service manages ACTIVE → ACK → RESOLVED.")
    s.update(alert="ACTIVE", red=True, buz=True, phase="ALERT")
    e(LIFE, PORT, "WebSocket", "clinical-alerts/live", "Notify staff: ACTIVE", dict(state="ACTIVE", severity="HIGH", patientId=PAT),
      "L2", "ALERTS", "Clinical portal shows the alert.")
    e(LIFE, OPDB, "SQL", "alert_state", "Store ACTIVE state", dict(state="ACTIVE"), "L2", "ALERTS", "State stored.")
    pl = dict(command="ACTIVATE", patientId=PAT, severity="HIGH", redLight="ON", buzzer="ON")
    e(LIFE, BRK, "MQTT/TLS + JSON", dt, "Publish ACTIVATE", pl, "L2", "MQTT", "Alarm command is published to the broker.")
    e(BRK, ACT, "MQTT/TLS", dt, "Forward ACTIVATE", pl, "L2", "MQTT", "Actuation gateway receives it.")
    e(ACT, SOD, "GPIO / Relay", "red-light + buzzer", "Red light ON + buzzer ON", pl, "L2", "DEVICE",
      "🔴🔊 Staff alarm is active. Click “Acknowledge alert” to continue.", gate="ack")

    # --- Acknowledge
    s.update(alert="ACKNOWLEDGED", buz=False, phase="ACK")
    e(PORT, LIFE, "REST / HTTPS", "POST /alerts/{id}/acknowledge", "Staff acknowledges alert",
      dict(patientId=PAT, acknowledgedBy="Medical Staff"), "L2", "ALERTS", "👩‍⚕️ A nurse acknowledges the alert in the portal.")
    e(LIFE, OPDB, "SQL", "alert_state", "Store ACKNOWLEDGED state", dict(state="ACKNOWLEDGED"), "L2", "ALERTS", "State stored.")
    pl = dict(command="SILENCE", redLight="ON", buzzer="OFF")
    e(LIFE, BRK, "MQTT/TLS + JSON", dt, "Publish SILENCE", pl, "L2", "MQTT", "Buzzer is silenced.")
    e(BRK, ACT, "MQTT/TLS", dt, "Forward SILENCE", pl, "L2", "MQTT", "Command reaches the actuation gateway.")
    e(ACT, SOD, "GPIO / Relay", "buzzer relay", "Buzzer OFF, red light ON", pl, "L2", "DEVICE",
      "🔇 Buzzer is off; red light remains on until recovery.", gate="recovery")

    # --- Recovery
    s["phase"] = "RECOVERING"
    i0 = dict(s)
    for k in range(1, 21):
        f = 1 - (1 - k / 20) ** 2
        s["hr"], s["rr"] = lerp(i0["hr"], 82, f), lerp(i0["rr"], 17, f)
        s["anom"] = anomaly(s["hr"], s["rr"])
        if k in (10, 20):
            chain(f"💚 Recovery: {s['hr']:.0f} bpm · {s['rr']:.0f} rpm.", f"Anomaly {level(s['anom'])} ({s['anom']*100:.0f}%).")
    l3_eval("Recovery criteria are evaluated.", "HR ≤ 100, RR ≤ 20 and anomaly ≤ 25% → recovery confirmed.")
    ev = dict(event="RECOVERY", patientId=PAT, roomId=ROOM)
    e(CADE, CAEP, "In-process event", "ClinicalDecision", "Create RECOVERY decision", ev, "L3", "DECISION", "✅ Patient returns to normal range.")
    e(CAEP, LIFE, "Internal Event", "clinical-alert/event", "Send recovery event", ev, "L3", "ALERTS", "Alert lifecycle moves to RESOLVED.")
    s.update(alert="RESOLVED", red=False, buz=False, phase="RESOLVED")
    e(LIFE, OPDB, "SQL", "alert_state", "Store RESOLVED state", dict(state="RESOLVED"), "L2", "ALERTS", "State stored.")
    e(LIFE, PORT, "WebSocket", "clinical-alerts/live", "Notify RESOLVED", dict(state="RESOLVED"), "L2", "ALERTS", "Clinical portal shows the alert as resolved.")
    pl = dict(command="RESET", redLight="OFF", buzzer="OFF")
    e(LIFE, BRK, "MQTT/TLS + JSON", dt, "Publish RESET", pl, "L2", "MQTT", "Reset command is published.")
    e(BRK, ACT, "MQTT/TLS", dt, "Forward RESET", pl, "L2", "MQTT", "Command reaches the actuation gateway.")
    e(ACT, SOD, "GPIO / Relay", "red-light + buzzer", "Red light OFF, buzzer OFF", pl, "L2", "DEVICE",
      "⚫ Alert device reset. Alert cycle complete.")
    return T.frames


# ============================================================
# PLAYER (HTML + JS): room state + synchronized C4 messages
# ============================================================
PLAYER = r"""
<style>
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Arial,sans-serif;background:#f8fafc;color:#0f172a}
.bar{display:flex;gap:6px;margin-bottom:8px}.chip{flex:1;text-align:center;font-size:11px;font-weight:800;padding:8px 2px;border-radius:9px;background:#e2e8f0;color:#94a3b8;transition:.3s}
.chip.done{background:#d1fae5;color:#047857}.chip.on{background:#2563eb;color:#fff;box-shadow:0 0 0 4px #2563eb30}.chip.on.d{background:#dc2626;box-shadow:0 0 0 4px #dc262630}
.top{display:grid;grid-template-columns:1fr 1.15fr;gap:12px}.card{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:12px}
#scene{height:340px;border-radius:14px;position:relative;overflow:hidden}.narr{margin-top:8px;padding:10px 12px;border-radius:12px;background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;font-weight:650;font-size:14px;min-height:58px}
.badge{position:absolute;left:50%;top:10px;transform:translateX(-50%);z-index:30;background:#0f172a;color:#fff;padding:5px 12px;border-radius:99px;font-size:12px;font-weight:800;animation:fl 1s infinite;white-space:nowrap}
@keyframes fl{50%{opacity:.55}}@keyframes bl{50%{opacity:.2}}
.msg{display:grid;grid-template-columns:1fr 80px 1fr;gap:8px;align-items:center}.nd{color:#fff;border-radius:12px;padding:10px;min-height:66px;font-weight:800;font-size:13px}.nd small{display:block;font-size:10px;opacity:.8;font-weight:600}
.arrow{height:4px;background:linear-gradient(90deg,#94a3b8,#f97316);border-radius:9px;position:relative}.arrow:after{content:"";position:absolute;right:-2px;top:-6px;border-left:12px solid #f97316;border-top:8px solid transparent;border-bottom:8px solid transparent}
.tg{display:inline-block;font-size:11px;font-weight:800;padding:3px 8px;border-radius:99px;margin:0 4px 6px 0;background:#e2e8f0}.l3{background:#ffedd5;color:#9a3412}.l2{background:#dbeafe;color:#1d4ed8}.pr{background:#ede9fe;color:#6d28d9}
pre{margin:8px 0 0;background:#0b1220;color:#a7f3d0;border-radius:10px;padding:8px 10px;font-size:11px;max-height:150px;overflow:auto}
.ctl{display:flex;gap:8px;align-items:center;margin:10px 0;flex-wrap:wrap}button,select{border:0;border-radius:10px;padding:9px 14px;font-weight:800;cursor:pointer;background:#1e293b;color:#fff;font-size:13px}
button.g{background:#dc2626;animation:fl .8s infinite}button:disabled{opacity:.35}input[type=range]{flex:1;min-width:120px}
.tr{font-size:12px;display:flex;flex-direction:column;gap:4px;margin-top:6px}.tr div{padding:5px 8px;border-radius:8px;background:#f1f5f9}.tr div:last-child{background:#dbeafe;font-weight:700}
svg text{font-family:Arial,sans-serif}.leg{font-size:12px;color:#64748b;margin:0 0 6px}
</style>
<div class="bar" id="bar"></div>
<div class="top">
 <div class="card"><b id="stt"></b><div id="scene" style="margin-top:8px"></div><div class="narr" id="narr"></div></div>
 <div class="card"><b>Current C4 message</b><div style="margin:8px 0" id="tags"></div>
  <div class="msg"><div class="nd" id="ns"></div><div class="arrow"></div><div class="nd" id="nd"></div></div>
  <div style="margin-top:8px;font-size:14px"><b id="sm"></b><div style="color:#64748b;font-size:12px" id="ch"></div></div>
  <pre id="pl"></pre></div>
</div>
<div class="ctl"><button id="rs">⏮ Reset</button><button id="pv">◀</button><button id="pp">▶ Play</button><button id="nx">▶|</button>
 <select id="sp"><option value=".5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select>
 <input type="range" id="rg" min="0" value="0"><span id="cnt" style="font-weight:800"></span><button id="gt" class="g" style="display:none"></button></div>
<div class="card"><p class="leg">🟠 current message · 🟢 used links · ● message in transit · faded nodes = not active yet</p>
 <svg id="map" viewBox="0 0 1200 580" width="100%"></svg></div>
<div class="card" style="margin-top:12px"><b>Recent messages</b><div class="tr" id="tr"></div></div>
<script>
const D=__DATA__,F=D.frames,N=D.nodes,KIND=D.kind,$=id=>document.getElementById(id);
let i=-1,playing=false,speed=1,timer=null,cur=null,rel={},raf=0;
const cl=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
$('bar').innerHTML=D.stages.map((s,k)=>`<div class="chip" id="c${k}">${s}</div>`).join('');
$('stt').textContent=KIND=='sleep'?'🏨 Room 204 · live':'🏥 Patient P12 · clinical alert · live';
// ---- static SVG
let S='<defs><marker id="ao" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto"><polygon points="0 0,9 3,0 6" fill="#f97316"/></marker><marker id="ag" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto"><polygon points="0 0,9 3,0 6" fill="#16a34a"/></marker></defs>';
D.zones.forEach(z=>{S+=`<rect x="${z[0]}" y="${z[1]}" width="${z[2]}" height="${z[3]}" rx="16" fill="#f8fafc" stroke="#cbd5e1" stroke-dasharray="6 5"/><text x="${z[0]+12}" y="${z[1]+19}" font-size="13" font-weight="700" fill="#475569">${z[4]}</text>`});
S+='<g id="eg"></g>';
Object.keys(N).forEach((n,k)=>{const r=N[n],w=n.split(' '),m=n.length>24?Math.ceil(w.length/2):w.length,L=n.length>24?[w.slice(0,m).join(' '),w.slice(m).join(' ')]:[n];
 S+=`<g id="n${k}" opacity=".3"><rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" rx="11" fill="${r.c}"/>`+L.map((t,j)=>`<text x="${r.x+r.w/2}" y="${r.y+r.h/2+4+(L.length==2?(j?7:-8):0)}" text-anchor="middle" fill="#fff" font-size="11.5" font-weight="800">${t}</text>`).join('')+'</g>'});
S+='<circle id="pk" r="9" fill="#f97316" stroke="#fff" stroke-width="2.5" style="display:none"/>';$('map').innerHTML=S;
const names=Object.keys(N);
function clip(R,t){const cx=R.x+R.w/2,cy=R.y+R.h/2,dx=t[0]-cx,dy=t[1]-cy,s=Math.min(dx?R.w/2/Math.abs(dx):1e9,dy?R.h/2/Math.abs(dy):1e9);return[cx+dx*s,cy+dy*s]}
function edge(a,b){const A=N[a],B=N[b],ac=[A.x+A.w/2,A.y+A.h/2],bc=[B.x+B.w/2,B.y+B.h/2],p=clip(A,bc),q=clip(B,ac),dx=q[0]-p[0],dy=q[1]-p[1],L=Math.hypot(dx,dy)||1,nx=-dy/L*7,ny=dx/L*7;return[p[0]+nx,p[1]+ny,q[0]+nx,q[1]+ny]}
// ---- scene
function sleepScene(s){const dark=.6*cl(1-s.lux/820),hue=35+cl((27.5-s.temp)/6)*175,lamp=cl(s.lights/100),ic=s.sleep=='ASLEEP'?'😴':s.sleep=='DROWSY'?'🥱':'🧍',an=s.sleep=='ASLEEP'?'none':s.sleep=='DROWSY'?'fl 2s infinite':'fl .8s infinite';
 return `<div style="position:absolute;inset:0;background:hsl(${hue},30%,88%)"></div><div style="position:absolute;left:0;bottom:0;width:100%;height:27%;background:linear-gradient(#d8c5a7,#bea786)"></div>
 <div style="position:absolute;inset:0;background:#0b1026;opacity:${dark};z-index:15;pointer-events:none"></div>
 <div style="position:absolute;top:60px;left:22px;width:150px;height:120px;border:8px solid #fff;overflow:hidden;background:linear-gradient(#7dd3fc,#bae6fd)"><div style="width:100%;height:${100-s.blinds}%;background:repeating-linear-gradient(0deg,#9ca3af,#9ca3af 7px,#d1d5db 7px,#d1d5db 11px)"></div></div>
 <div style="position:absolute;top:22px;left:20px;font-size:12px;font-weight:800;background:#fff;padding:4px 10px;border-radius:9px;z-index:20">🪟 Blinds ${Math.round(s.blinds)}% open</div>
 <div style="position:absolute;right:120px;top:26px;font-size:44px;z-index:16;opacity:${Math.max(.15,lamp)};filter:drop-shadow(0 0 ${lamp*18}px #facc15)">💡</div>
 <div style="position:absolute;left:14%;bottom:52px;width:52%;height:84px;background:#f8fafc;border:4px solid #94a3b8;border-radius:22px 22px 8px 8px"></div>
 <div style="position:absolute;left:34%;bottom:112px;font-size:62px;z-index:18;animation:${an}">${ic}</div>
 <div style="position:absolute;left:34%;bottom:88px;z-index:19;background:#fff;padding:3px 10px;border-radius:99px;font-size:11px;font-weight:800">${s.sleep} · ${Math.round(s.prob*100)}%</div>
 <div style="position:absolute;right:12px;top:70px;z-index:20;background:#ffffffee;padding:8px 10px;border-radius:12px;font-size:12px;line-height:1.7">🌡️ ${s.temp.toFixed(1)} °C<br>☀️ ${Math.round(s.lux)} lux<br>💡 lights ${Math.round(s.lights)}%<br>❤️ ${Math.round(s.hr)} bpm · 🫁 ${Math.round(s.rr)} rpm</div>
 <div style="position:absolute;right:12px;bottom:14px;z-index:20;background:#ffffffee;padding:8px 10px;border-radius:12px;font-size:12px">${s.ac?'❄️ <b>A/C ON</b> '+s.acSet+' °C':'⭕ <b>A/C OFF</b>'}</div>
 <div style="position:absolute;left:12px;bottom:12px;z-index:20;background:#111827;color:#fff;padding:6px 12px;border-radius:99px;font-size:11px;font-weight:800">${s.mode=='SLEEP MODE'?'🌙':s.mode=='ADAPTING'?'⚙️':'☀️'} ${s.mode}</div>`}
function emgScene(s){const c=s.anom>=.75?'#f87171':s.anom>=.4?'#fbbf24':'#4ade80',bd=(60/Math.max(s.hr,30)).toFixed(2),on=s.red;
 return `<div style="position:absolute;inset:0;background:#e2e8f0"></div><div style="position:absolute;left:0;top:0;bottom:0;width:60%;padding:16px;background:linear-gradient(145deg,#111827,#020617);color:#fff">
 <div style="font-weight:800;border-bottom:1px solid #374151;padding-bottom:8px">🫀 Monitor · Room 204 · P12</div>
 <div style="display:flex;gap:26px;margin-top:20px"><div><div style="font-size:11px;color:#9ca3af">❤️ HEART RATE</div><span style="font-size:46px;font-weight:800;color:${c};display:inline-block;animation:bt ${bd}s infinite">${Math.round(s.hr)}</span> bpm</div>
 <div><div style="font-size:11px;color:#9ca3af">🫁 BREATHING RATE</div><span style="font-size:46px;font-weight:800;color:${c}">${Math.round(s.rr)}</span> rpm</div></div>
 <div style="margin-top:22px;padding:12px;border-radius:12px;background:#ffffff14"><b>IA · anomaly score ${Math.round(s.anom*100)}%</b><div style="height:12px;background:#374151;border-radius:9px;margin-top:8px;overflow:hidden"><div style="height:100%;width:${s.anom*100}%;background:${c}"></div></div>
 <div style="font-size:12px;color:#9ca3af;margin-top:8px">Consecutive HIGH samples: <b style="color:#fff">${s.sust}/3</b></div></div></div>
 <div style="position:absolute;right:0;top:0;bottom:0;width:40%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;background:#f9fafb"><b style="font-size:13px">🏢 Staff room<br>Alert device</b>
 <div style="width:78px;height:78px;border-radius:50%;border:6px solid #d1d5db;margin:14px 0;background:${on?'#ef4444':'#6b7280'};box-shadow:${on?'0 0 20px #ef4444,0 0 44px #ef4444aa':'none'};animation:${s.alert=='ACTIVE'?'bl .7s infinite':'none'}"></div>
 <div style="font-size:42px">${s.buz?'🔊':'🔇'}</div><div style="font-size:11px;font-weight:800;color:#475569">${s.buz?'BUZZER ON':'BUZZER OFF'}</div>
 <div style="margin-top:12px;background:#111827;color:#fff;padding:6px 12px;border-radius:99px;font-size:12px;font-weight:800">${s.alert}</div></div>
 <style>@keyframes bt{15%{transform:scale(1.1)}}</style>`}
const draw=s=>{$('scene').innerHTML=(KIND=='sleep'?sleepScene:emgScene)(s)+`<style>@keyframes fl{50%{opacity:.5}}@keyframes bl{50%{opacity:.2}}</style>`+badge(F[Math.max(i,0)])};
const BADGE={PPS:'📡 Patient sensors send data',RES:'📡 Room sensors send data',REAd:'⚙️ Actuators apply the command',REAs:'↩️ Actuators confirm their state',SODd:'🚨 Alert device receives the command',PORT:'👩‍⚕️ Staff uses the clinical portal'};
function badge(f){if(!f)return'';let t='';if(f.src==D.k.PPS)t=BADGE.PPS;else if(f.src==D.k.RES)t=BADGE.RES;else if(f.dst==D.k.REA)t=BADGE.REAd;else if(f.src==D.k.REA)t=BADGE.REAs;else if(f.dst==D.k.SOD)t=BADGE.SODd;else if(f.src==D.k.PORT||f.dst==D.k.PORT)t=BADGE.PORT;return t?`<div class="badge">${t}</div>`:''}
function tween(to){cancelAnimationFrame(raf);const from=cur?{...cur}:{...to},t0=performance.now(),dur=700/speed;
 (function st(t){const k=cl((t-t0)/dur),o={...to};for(const q in to)if(typeof to[q]=='number'&&typeof from[q]=='number')o[q]=from[q]+(to[q]-from[q])*k;cur=o;draw(o);if(k<1)raf=requestAnimationFrame(st)})(t0)}
function packet(f){const p=$('pk'),e=edge(f.src,f.dst),t0=performance.now(),dur=1000/speed;p.style.display='';
 (function st(t){const k=cl((t-t0)/dur);p.setAttribute('cx',e[0]+(e[2]-e[0])*k);p.setAttribute('cy',e[1]+(e[3]-e[1])*k);if(k<1)requestAnimationFrame(st);else setTimeout(()=>p.style.display=i==F.indexOf(f)?'':'none',150)})(t0)}
function show(){const f=F[i],idx=D.stages.indexOf(f.stage),danger=D.kind=='emg'&&['ALERT','ACK','RECOVERING','ESCALATING'].includes(f.state.phase);
 D.stages.forEach((s,k)=>$('c'+k).className='chip'+(k==idx?' on'+(danger?' d':''):k<idx?' done':''));
 const a=N[f.src],b=N[f.dst];$('ns').style.background=a.c;$('nd').style.background=b.c;
 $('ns').innerHTML=`<small>FROM</small>${f.src}`;$('nd').innerHTML=`<small>TO</small>${f.dst}`;
 $('tags').innerHTML=`<span class="tg ${f.scope=='L3'?'l3':'l2'}">C4 ${f.scope}</span><span class="tg pr">${f.proto}</span><span class="tg">${f.id}</span>`;
 $('sm').textContent=f.summary;$('ch').textContent='Channel / endpoint: '+f.chan;
 $('pl').textContent=JSON.stringify({messageId:f.id,from:f.src,to:f.dst,protocol:f.proto,channel:f.chan,payload:f.payload},null,1);
 $('narr').innerHTML=f.narr;$('rg').value=i;$('cnt').textContent=`${i+1}/${F.length}`;
 const cnt={};F.slice(0,i+1).forEach(m=>{const k=m.src+'|'+m.dst;cnt[k]=(cnt[k]||0)+1});const T=new Set();F.slice(0,i+1).forEach(m=>{T.add(m.src);T.add(m.dst)});
 let g='';for(const k in cnt){const[s,d]=k.split('|'),e=edge(s,d),now=s==f.src&&d==f.dst,c=now?'#f97316':'#16a34a',mx=(e[0]+e[2])/2,my=(e[1]+e[3])/2;
  g+=`<line x1="${e[0]}" y1="${e[1]}" x2="${e[2]}" y2="${e[3]}" stroke="${c}" stroke-width="${now?4.5:2.6}" marker-end="url(#${now?'ao':'ag'})"/><circle cx="${mx}" cy="${my}" r="9" fill="#fff" stroke="${c}" stroke-width="2"/><text x="${mx}" y="${my+4}" text-anchor="middle" font-size="11" font-weight="800">${cnt[k]}</text>`}
 $('eg').innerHTML=g;names.forEach((n,k)=>{const el=$('n'+k);el.setAttribute('opacity',T.has(n)?1:.3);el.firstChild.setAttribute('stroke',n==f.src||n==f.dst?'#f97316':'none');el.firstChild.setAttribute('stroke-width',4)});
 $('tr').innerHTML=F.slice(Math.max(0,i-5),i+1).map(m=>`<div>${m.id} · ${m.scope} · ${m.src} → ${m.dst} — ${m.summary}</div>`).join('');
 const gt=$('gt');if(f.gate&&!rel[i]){gt.style.display='';gt.textContent=D.gates[f.gate];stop()}else gt.style.display='none';
 tween(f.state);packet(f)}
function go(k){if(k<0||k>=F.length)return;i=k;show()}
function nxt(){if(F[i]&&F[i].gate&&!rel[i]){stop();return false}if(i<F.length-1){go(i+1);return true}stop();return false}
function stop(){playing=false;clearTimeout(timer);$('pp').textContent='▶ Play'}
function loop(){if(!playing)return;if(!nxt())return;timer=setTimeout(loop,2300/speed)}
$('pp').onclick=()=>{if(playing){stop();return}playing=true;$('pp').textContent='⏸ Pause';loop()};
$('nx').onclick=()=>{stop();nxt()};$('pv').onclick=()=>{stop();go(i-1)};$('rs').onclick=()=>{stop();rel={};cur=null;go(0)};
$('sp').onchange=e=>{speed=parseFloat(e.target.value)};$('rg').max=F.length-1;$('rg').oninput=e=>{stop();go(+e.target.value)};
$('gt').onclick=()=>{rel[i]=true;$('gt').style.display='none';playing=true;$('pp').textContent='⏸ Pause';loop()};
go(0);
</script>
"""


def build_player(kind):
    frames = sleep_tape() if kind == "sleep" else emg_tape()
    nodes = {n: dict(x=v[0], y=v[1], w=v[2], h=v[3], c=v[4]) for n, v in NODES.items()}
    if kind == "sleep":
        nodes = {n: v for n, v in nodes.items() if n not in (SOD, PORT, LIFE, CAEP, CADE, SCT, AIRR)}
        zones = [z for z in ZONES if "Staff" not in z[4]]
        stages, gates = S_STAGES, {}
    else:
        nodes = {n: v for n, v in nodes.items() if n not in (RES, REA, SLE, RCP)}
        zones = ZONES
        stages, gates = E_STAGES, {"ack": "✓ Acknowledge alert", "recovery": "♡ Simulate recovery"}
    data = dict(frames=frames, nodes=nodes, zones=zones, kind=kind, stages=stages, gates=gates,
                k=dict(PPS=PPS, RES=RES, REA=REA, SOD=SOD, PORT=PORT))
    return PLAYER.replace("__DATA__", json.dumps(data, ensure_ascii=False))


# ============================================================
# UI
# ============================================================
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 1.5rem;}
</style>
""", unsafe_allow_html=True)

scenario = st.radio(
    "Choose demo",
    ["🌙 Sleep room adaptation", "🚨 Medical emergency"],
    horizontal=True
)
kind = "sleep" if scenario.startswith("🌙") else "emg"

if kind == "sleep":
    st.caption("Press Play to follow the sensor → Digital Twin → AI → decision → actuator flow.")
else:
    st.caption("Press Play. The demo pauses for staff acknowledgement and patient recovery.")

components.html(build_player(kind), height=1420, scrolling=True)
