# Demo Script · Smart Hospital Patient Monitoring & Room Automation

**Format:** Live demo of `app.py` (Streamlit)  
**Total:** ~8 min  
**Main focus:** Scenario 1 – Sleep Room Adaptation  
**Setup:** Browser full-screen, speed 1×, scenario **“Sleep room adaptation”** selected.

Message numbers (`M0xx`) are the counters shown in the app, so you can move directly to them with the slider if necessary.

> **Note:** All physiological values, AI outputs and thresholds shown in the prototype are synthetic demo values and are not clinically validated.

---

## 0 · Opening — Architecture overview (≈ 45 s)

> “In a hospital, patient monitoring and room automation are usually treated as two separate systems. Our project combines them into one continuous workflow.
>
> The basic idea is:
>
> **Sensing → Communication → Contextualization → Decision → Physical action → Feedback.**
>
> We monitor a patient in Room 204 using wearable and environmental sensors, create a synchronized digital representation of that patient and room, and then use that information either to adapt the environment or to generate a clinical alert.”

*Point at the architecture.*

> “There are three important architectural ideas behind the system.
>
> First, sensors and actuators communicate through an **MQTT broker**.
>
> Second, the **Patient-in-Room Digital Twin** represents the current synchronized state of the patient, the room and the actuators.
>
> And third, the **Decision & Control Service** is the only component allowed to take actions. AI can analyse data, but it cannot directly control a device or trigger an alarm.
>
> What you see here is essentially our C4 architecture running. The diagram below highlights each component as messages move through the system.”

*Point at:*

- stage bar: **SENSORS → COMMUNICATION → CONTEXT → DECISION → ACTUATION → FEEDBACK**
- JSON/message panel
- message counter
- highlighted C4 components

> “Orange represents the message currently being processed, while green shows communication paths that have already been used. Messages are also labelled with their corresponding **C4 Level 2 or Level 3 component**.”

---

# 1 · Scenario 1 — Sleep Room Adaptation (≈ 4 min 15 s)

*Press **Play**.*

## 1.1 Sensing: starting from the physical room (M001–M004)

> “We start from the physical world.
>
> Patient P12 is currently awake and moving. At the same time, the environmental sensors detect that Room 204 is relatively bright and warm: around **27.5 degrees and 820 lux**.
>
> For comparison, this patient has configured sleep preferences of approximately **22.5 degrees and 60 lux**.”

*Point to patient status, room temperature and lux.*

> “An important detail here is that individual sensors do not need to understand the complete hospital context.
>
> For example, the wearable knows its own `device_id` and produces measurements such as heart rate, breathing rate and movement. The room sensors produce temperature and light measurements.”

*Point to JSON.*

> “These raw measurements are collected by the **Sensor Ingestion Gateway**, converted into a common JSON format and published through **MQTT over TLS**.
>
> The gateway is intentionally simple: it transports information, but it does not decide whether the patient is sleeping, whether the room is too warm or whether the lights should be changed.”

---

## 1.2 Contextualization: turning sensor data into hospital context (M005–M009)

> “The next step is contextualization.
>
> A message such as ‘wearable 17 reports a heart rate of 72’ is not very useful by itself. The system needs to know **who that wearable belongs to and where that patient currently is**.”

*Point to Context & Normalization Service.*

> “The **IoT Data Context & Normalization Service** resolves the relationship:
>
> `device → patient → room`.
>
> Using the operational database, it identifies this as **Patient P12 in Room 204**.”

> “The readings are normalized and timestamped, stored in the time-series database for historical analysis, and then used to update the **Digital Twin**.”

*Point to Digital Twin.*

> “This is one of the most important components in our architecture.
>
> The Digital Twin is not simply another database. It represents the **current synchronized state of the real environment**.
>
> At this moment it contains the latest patient vitals, movement, room temperature, light level and device state.”

### AI-derived context

> “But raw sensor values are not enough to make every decision.
>
> The Digital Twin therefore sends the relevant physiological information to the **AI Inference Service**.”

*Point as AI component activates.*

> “For this scenario, the AI estimates the patient's sleep state.
>
> It returns a derived state such as **AWAKE**, together with a probability, and this information is written back into the Digital Twin.”

> “This distinction is important:
>
> **AI analyses the situation; it does not control the room.**
>
> Its output becomes another input for the Decision Service.”

---

## 1.3 Decision Service: combining physical and derived state (M010–M021)

> “Now we move from **C4 Level 2 into C4 Level 3**, because we are entering the internal structure of the Decision & Control Service.”

*Point to Level 3 diagram.*

> “The Decision Service receives two types of information:
>
> the synchronized physical state from the Digital Twin and the AI-derived context.”

> “Inside the service, the **Decision Coordinator** combines them into a single `DecisionContext`.”

*Point to JSON.*

> “This object is essentially the complete snapshot needed to make a decision.
>
> It contains the **physical state** — for example temperature, lux, movement and vital signs — together with the **AI-derived context**, such as the current sleep classification.”

> “The Coordinator also retrieves configuration from the repository. This includes things such as clinical thresholds and the patient's room preferences.”

### Two independent decision engines

> “Once that context is prepared, the Coordinator invokes two independent rule engines.”

*Point first to clinical engine.*

> “The **Clinical Alert Decision Engine** checks whether there is a medical reason to generate an alert.
>
> In this case, the patient's physiological values are normal, so its result is simply:
>
> **NO_CHANGE.**”

*Point to Sleep & Room Adaptation Engine.*

> “In parallel, the **Sleep & Room Adaptation Engine** evaluates the environmental side.
>
> It can see three things:
>
> the patient is transitioning towards sleep, the room is much brighter than the configured target, and the temperature is also above the preferred value.”

> “Based on that combined context, it decides to activate **Sleep Mode**.”

### Why the separation matters

> “This separation is deliberate.
>
> The AI does not say ‘turn off the lights’.
>
> A sensor does not say ‘turn on the air conditioning’.
>
> The Digital Twin does not decide either.
>
> Only the Decision Service converts the current state into an explicit action.”

---

## 1.4 Command and physical actuation (M022 onward)

> “Once the decision has been made, the **Room Control Command Publisher** creates the command.”

*Point to JSON.*

> “Notice that the command contains a unique `command_id`.
>
> That identifier becomes important later because it allows us to connect the command we sent with the acknowledgement returned by the physical device.”

> “The command is published through MQTT and received by the **Actuation Gateway**.”

*Watch room animation.*

> “The gateway translates the generic hospital command into the protocol required by the physical device — for example Zigbee or Modbus.
>
> Now we can see the room reacting:
>
> the blinds close, the lights dim and the air conditioning switches on.”

---

## 1.5 Feedback: closing the loop (M030–M049)

> “If the architecture stopped here, however, we would have an open-loop system.
>
> We would know what we *asked* the devices to do, but not what actually happened.”

> “Our architecture therefore includes two forms of feedback.”

### Actuator feedback

> “First, the actuators report their actual state.”

*Point to actuator acknowledgement.*

> “For example, the light controller reports that the requested level has actually been applied.
>
> The acknowledgement contains `ack_of`, referencing the original `command_id`.”

> “That message travels back through MQTT, is contextualized again and updates the Digital Twin.”

> “So the Digital Twin represents not only what the system *wanted* the room to look like, but what the actuators say they are actually doing.”

### Sensor feedback

> “Second, we receive feedback from the sensors themselves.
>
> This allows us to verify the physical effect of the action.”

*Watch temperature/lux values.*

> “Light levels decrease, temperature starts moving towards the target, movement reduces and the physiological data changes accordingly.”

> “The new sensor readings repeat the same pipeline:
>
> **sensor → MQTT → contextualization → Digital Twin → AI → Decision Service.**”

### Changing sleep state

> “The AI now re-evaluates the patient using the new measurements.
>
> We can see the derived state move from **AWAKE**, to **DROWSY**, and finally to **ASLEEP**.”

> “Again, the AI is not causing the physical actions. It is simply updating the context available to the Decision Service.”

---

## 1.6 Stable state: no unnecessary commands (M050–M053)

> “Finally, the system evaluates the room once more.
>
> The patient is now classified as **ASLEEP**, and the room conditions are within the configured targets.”

> “The Decision Service therefore returns:
>
> **NO_CHANGE.**”

*Point to absence of new command.*

> “And importantly, no new MQTT command is published.
>
> The publisher only sends a command when the required target state changes. This avoids repeatedly commanding devices that are already in the correct state.”

### Scenario 1 takeaway

> “So the complete loop we have just demonstrated is:
>
> **Sense → contextualize → update the twin → analyse → decide → actuate → receive feedback → update the twin again.**
>
> This closed loop is the main architectural idea of the project.”

---

# 2 · Scenario 2 — Medical Emergency (≈ 2 min)

*Switch to **Medical emergency** and press **Play**.*

> “The second scenario uses almost exactly the same architecture, so instead of following every message again, I will focus only on what changes: the **decision logic**.”

---

## 2.1 Deterioration and sustained condition (M001–M036)

> “Initially, Patient P12 is stable: around **78 beats per minute**, **16 breaths per minute**, with a LOW anomaly score.”

> “The patient then begins to deteriorate and the AI anomaly score rises from ELEVATED to HIGH.”

*Point to counter.*

> “However, a single abnormal sample does not immediately trigger an alarm.
>
> The **Sustained Condition Tracker** requires three consecutive HIGH samples.”

> “So we see:
>
> **1 of 3, 2 of 3, and finally 3 of 3.**
>
> This simple mechanism helps prevent isolated noisy readings from generating unnecessary alarms.”

---

## 2.2 Clinical decision and alert lifecycle (M037–M053)

> “Once the condition reaches 3 out of 3, the Decision Coordinator creates the same type of DecisionContext we saw before.”

> “This time the **Clinical Alert Decision Engine** returns:
>
> **ALERT — severity HIGH.**”

> “The alert contains the patient, room and abnormal parameters.”

> “Again, the AI itself has not triggered the alarm. The AI produced an anomaly score; the Decision Service applied the safety logic and made the decision.”

> “The decision then goes to the **Clinical Alert Lifecycle Service**, which manages the state of the alert:
>
> **ACTIVE → ACKNOWLEDGED → RESOLVED.**”

*Demo pauses.*

> “The alert is stored, the clinical portal receives the update through WebSocket, and an MQTT command activates the staff alert device.”

> “We now see the **red light and buzzer**.”

---

## 2.3 Acknowledgement and recovery

*Click **✓ Acknowledge alert**.*

> “Medical staff acknowledge the alarm through the portal.
>
> The lifecycle moves to **ACKNOWLEDGED**, and the buzzer is silenced.”

> “The red light remains active because acknowledging an alarm does not mean that the patient has recovered.”

*Click **♡ Simulate recovery**.*

> “Recovery also requires a sustained normal condition.
>
> Once the values remain within the recovery thresholds for three consecutive samples, the Clinical Engine returns **RECOVERY**.”

> “The lifecycle changes to **RESOLVED**, the portal is updated and a RESET command switches off the remaining alert indicator.”

### Scenario 2 takeaway

> “So the second scenario demonstrates that the same sensing, MQTT, Digital Twin and Decision architecture can support a completely different use case simply by changing the decision logic and the resulting actuator.”

---

# 3 · Wrap-up (≈ 45 s)

> “To finish, there are three main ideas we want to highlight.
>
> **First**, the Digital Twin acts as the synchronized source of truth for the current patient and room state, and the loop is closed using both sensor and actuator feedback.
>
> **Second**, we deliberately separate **AI from decision-making**. AI produces derived information; explicit and configurable logic inside the Decision Service determines what the system actually does.
>
> **Third**, the architecture is extensible. Telemetry, commands and feedback all use the same MQTT communication backbone, while gateways isolate device-specific protocols.
>
> So adding another sensor or actuator does not require redesigning the core architecture.
>
> The prototype uses simulated devices and AI outputs, but the communication flow, message structure and component responsibilities directly implement the C4 Level 2, Level 3 and Level 4 architecture presented in our report.”

---

# Likely Questions

| Question | Short answer |
|---|---|
| **Why does AI not trigger the alarm directly?** | Because AI output is only evidence. Thresholds, sustained-condition logic and safety rules are handled explicitly by the Decision Service. |
| **Why use a Digital Twin instead of only a database?** | The databases store history and configuration. The Digital Twin represents the latest synchronized physical and derived state used for decisions. |
| **Why do you need actuator feedback?** | A command only tells us what we requested. Feedback confirms what the physical device actually did and allows the Digital Twin to stay synchronized. |
| **How do you meet the 2-second alert requirement?** | The critical path is event-driven — Decision Service → Lifecycle → MQTT → Gateway → device — with no polling. The prototype does not benchmark real latency because it uses simulated devices. |
| **Why MQTT?** | It provides lightweight publish/subscribe communication suitable for IoT devices and allows telemetry, commands and feedback to use the same communication backbone. |
| **What is simulated?** | Sensor measurements, AI outputs and physical devices. The architectural components, messages and decision flow represent the intended implementation. |
| **What happens with one noisy sensor value?** | One isolated abnormal value is not sufficient. The Sustained Condition Tracker requires consecutive abnormal samples before creating an alert and consecutive normal samples before resolving it. |
| **Why does the Decision Service have two engines?** | Clinical safety and room automation are different concerns. Separating them makes each rule set easier to configure, test and extend independently. |
| **Could the system work without AI?** | Yes. AI provides additional derived context, but the Decision Service can still evaluate deterministic rules from sensor data. |
| **What happens if the actuator does not acknowledge a command?** | The Digital Twin would not confirm the requested physical state. In a production implementation this could trigger retries, timeout handling or a device-failure alert. |

---

# Practical Presentation Tips

For **Scenario 1**, keep the demo around **1× speed initially**, because this is where you should explain the architecture. Once the audience understands the pipeline, you can increase to **2×** during the feedback iterations.

Spend most of your explanation around four moments:

**raw sensor message → contextualized Digital Twin → DecisionContext → actuator feedback.**

Those four screens explain almost the entire architecture.

For **Scenario 2**, do not explain MQTT, normalization or the Digital Twin again. Start with:

> “Same pipeline, different decision logic.”

Then focus only on:

**3 consecutive samples → ALERT → ACKNOWLEDGED → sustained recovery → RESOLVED.**

The two manual pauses — **Acknowledge** and **Simulate recovery** — are useful moments to speak without the demo moving underneath you.

If you are short on time, Scenario 1 is the one to preserve. Scenario 2 can be reduced to approximately **90 seconds** without losing the main message.