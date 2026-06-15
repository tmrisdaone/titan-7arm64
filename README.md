# TITAN-7 ARM64

Phone-brain bipedal robot running on Termux + Shizuku + Ollama 0.5B + ESP32.

---

## Architecture

```
[Android Phone]  ←brain/main.py (Termux + termux-sensor)
      │  USB OTG
      ▼
[ESP32]  ←esp32_main.py (MicroPython, 50Hz servo PWM)
      │  GPIO/PWM
      ▼
[12× MG996R servos]  →  Bipedal legs, arms
```

The phone runs everything high-level: sensor fusion, LLM intent (Qwen2.5:0.5B via Ollama), UDP commands to the ESP32. The ESP32 does the real-time low-level control so the robot doesn't eat dust if the LLM takes 100ms.

---

## Hardware BOM (Full Build)

| Component | Qty | Est. Price | Notes |
|-----------|-----|-----------|-------|
| ESP32 DEVKIT V1 | 1 | $6 | Main MCU |
| MG996R metal-gear servo | 12 | $3.50 ea | 6 per leg (hip/thigh/knee/ankle), 6 for arms/torso |
| 3S LiPo 11.1V 2200mAh | 1 | $12 | Robot power |
| UBEC 5V 5A step-down | 1 | $4 | Powers the ESP32 + servos cleanly |
| PCA9685 16ch servo driver | 1 | $4 | Lets ESP32 control 12 servos over I2C instead of burning every GPIO |
| MPU6050 IMU | 1 | $2 | Backup per-robot IMU on the robot body itself |
| USB OTG cable | 1 | $2 | Phone to ESP32 serial link |
| 3D-printed chassis | 1 | $10–20 | Your own PETG/PLA print or sponsor print |
| Jumper wires + breadboard | assorted | $5 | Wiring glue |
| **Total** | | **~$112–122** | Assuming you already own a phone |

### Dimensions (rough, 170cm tall bot prototype)

- **Footprint:** 25cm(width) × 35cm(length)
- **Hip height:** ~90cm from ground
- **Thigh:** 18cm
- **Shin:** 16cm
- **Total leg travel:** ~34cm (fully extended)
- **Torso mass:** ~600g (ESP32 + battery + driver boards)
- **Servo torque each:** ~11kg/cm @ 6V → 12 servos gives chain-torque reserve

---

## Shizuku (MANDATORY — Not Optional)

**Shizuku is NOT optional on this build.** Shizuku lives at https://shizuku.rikka.app and is the only stable way to give Termux the elevated permissions this firmware needs on Android 10+.

What Shizuku unlocks for TITAN-7:

- **`termux-sensor` with background wakelock** — keeps the accelerometer/gyro polling alive when the screen sleeps. Without Shizuku, Doze kills your sensors in ~90 seconds and the robot falls over blind.
- **USB OTG serial without `android.hardware.usb.host` whitelisting** — directly opens `/dev/ttyUSB*` from Python to talk to the ESP32.
- **`su`-like access via `shizuku` CLI** for direct `/dev` GPU and DRM node access (see GPU section below).

### Install Shizuku

1. Install the Shizuku app from the Play Store (or F-Droid).
2. Enable Shizuku via **Settings → Developer options → Wireless debugging** (or via ADB on first launch: `adb shell sh /sdcard/Android/data/moe.shizuku.rikka.api/start.sh`).
3. Verify: `shizuku --status` should say `running`.
4. Once Shizuku is up, Termux inherits the elevated permission space.

---

## Termux Sensor Bridge

Your phone already has:
- **Accelerometer** (`加速度传感器`)
- **Gyroscope** (`陀螺仪`)
- **Gravity sensor**
- **Rotation vector**

`termux-sensor` exposes all four. `brain/main.py` polls them at 10Hz over HTTP and builds a quaternion for the robot’s torso orientation. The MPU6050 on the robot itself is just a redundant local backup; the phone is the authoritative IMU because it’s higher quality and already fused.

Polling format:

```json
{"accel": {"x":0.12,"y":-9.81,"z":0.04},"gyro":{"x":0.01,"y":0.02,"z":-0.01}}
```

---

## 0.5B LLM Stack (Ollama)

Yes, you can absolutely run a 0.5B model on the same phone. The model is high-level intent only — it does NOT do per-frame control.

- Pull: `ollama pull qwen2.5:0.5b`
- `brain/main.py` sends a prompt every 200ms: `"orientation: pitch=2.1 roll=0.3 left_hip_load=0.8. Decide: step_forward | adjust_balance | stop"`
- The model returns one of three actions. Python interprets it into motor targets.
- Latency budget: model inference takes ~80–150ms on mid-range Snapdragon; Python PID runs at 50Hz on the ESP32 so it isn't blocked.

Good news: Ollama on Android automatically offloads tensor work to the **NNAPI / GPU / NPU** if Shizuku gives it access. More on that in GPU section below.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/tmrisdaone/titan-7arm64.git
cd titan-7arm64

# 2. Provision Termux
chmod +x setup.sh
./setup.sh

# 3. Install Shizuku from Play Store / F-Droid and start it
#    (required — script will not fully work without it)

# 4. Flash ESP32
#    Use ampy / mpremote to push microcontroller/esp32_main.py to /flash/main.py

# 5. Run the brain
python3 brain/main.py
```

---

## Wiring Diagram

```
Phone (USB OTG) → ESP32 UART2 (GPIO16=RX, GPIO17=TX) @ 115200 baud

ESP32 I2C → PCA9685 @ 0x40
  PCA9685 channels 0-11 → MG996R signal wires
  PCA9686 V+ → UBEC 5V output
  PCA9686 GND → ESP32 GND + UBEC GND

MPU6050 I2C → ESP32 (optional, local backup IMU)
  VCC → 3.3V, GND → GND, SDA → GPIO21, SCL → GPIO22
```

---

## Repo Layout

```
titan-7arm64/
├── README.md          ← you are here
├── setup.sh           ← Termux one-click bootstrap
├── brain/
│   └── main.py        ← orchestrator (sensors → LLM → ESP32 UDP)
├── microcontroller/
│   └── esp32_main.py  ← MicroPython: PID gait, serial listener
└── docs/
    └── gpu-shizuku.md ← direct GPU access guide + script
```

---

## Ongoing TODO

- [ ] Walk cycle gait generator with online foot-placement planner
- [ ] Vision module (camera + YOLOv8-nano) on the phone for obstacle avoidance
- [ ] Voice module (Whisper.cpp tiny + Piper TTS) for "hey titan" wake word
- [ ] Web dashboard over WebSocket from phone:8000

---

*Built for the dreamers shipping hardware from Termux.*

---

# Full Hardware Blueprint (docs/blueprint.md)

## MANDATORY: Shizuku (Not Optional)
Shizuku lives at https://shizuku.rikka.app. Android aggressively kills background processes and throttles sensor polling to save battery. To achieve 50Hz+ polling rate required for bipedal balance without the phone putting Termux to sleep, you **must** use Shizuku to grant Termux elevated, battery-optimized permissions.

What Shizuku unlocks for TITAN-7:
- **`termux-sensor` with background wakelock** — keeps the accelerometer/gyro polling alive when the screen sleeps. Without Shizuku, Doze kills your sensors in ~90 seconds and the robot falls over blind.
- **USB OTG serial without `android.hardware.usb.host` whitelisting** — directly opens `/dev/ttyUSB*` from Python to talk to the ESP32.
- **`su`-like access via `shizuku` CLI** for direct `/dev` GPU and DRM node access (see GPU section below).

### Install Shizuku
1. Install the Shizuku app from the Play Store (or F-Droid).
2. Enable Shizuku via **Settings → Developer options → Wireless debugging** (or via ADB on first launch: `adb shell sh /sdcard/Android/data/moe.shizuku.rikka.api/start.sh`).
3. Verify: `shizuku --status` should say `running`.
4. Once Shizuku is up, Termux inherits the elevated permission space.

---

## Future: Termux + X11 + GPU via Shizuku
Shizuku unlocks `/dev/dri/*` and `/dev/graphics/*` DRM nodes that are normally hidden from userland. This lets X11 render hardware-accelerated desktops directly on your phone’s GPU (Mali/Adreno) without needing root. **See `scripts/gpu_x11_shizuku.sh` for the one-click launcher.**

Warnings:
- Raw DRM access bypasses Android’s display compositor. Use at your own risk.
- High GPU usage drains battery fast.
- Only tested on Snapdragon/MediaTek Mali/Adreno devices.

---

## BOM (Bill of Materials)
| Component | Qty | Est. Price | Purpose |
|-----------|-----|-----------|---------|
| ESP32 Dev Board (WROOM-32) | 1 | $6 | Low-latency motor controller & serial bridge |
| MG996R Metal-Gear Servos | 12 | $60 ($5/ea) | Heavy-duty joint actuation (6 per leg) |
| 3S LiPo Battery (11.1V, 2200mAh) | 1 | $20 | Main power for all 12 servos |
| UBEC (5V 5A) | 1 | $8 | Steps 11.1V down to safe 5V for ESP32 & logic |
| USB OTG Adapter | 1 | $3 | Connects phone to ESP32 via serial |
| 3D Printed Chassis | 1 | $24 | Structural frame |
| **Total** | | **~$121** | Assuming you already own a phone |

---

## Wiring Guide
1. **Power**: LiPo (+) → UBEC (+IN), LiPo (-) → UBEC (-IN).
2. **Servo Power**: All 12 servo VCC → UBEC (+OUT), all servo GND → UBEC (-OUT). *DO NOT power servos from the ESP32.*
3. **Logic Power**: UBEC (+OUT) → ESP32 VIN, UBEC (-OUT) → ESP32 GND.
4. **Signal**: ESP32 GPIO pins (e.g., 12-17 for Left Leg, 18-23 for Right Leg) → Servo PWM signal wires.
5. **Comm**: ESP32 TX/RX → Phone via USB OTG (Serial).

---

## Kinematics / Dimensions
- **Leg Configuration**: 6-DOF per leg (Hip Yaw, Hip Roll, Hip Pitch, Knee Pitch, Ankle Pitch, Ankle Roll).
- **Thigh Length**: ~150mm
- **Shin Length**: ~150mm
- **Total Height**: ~400mm (standing)
- **Weight Target**: < 2.5kg (to stay within MG996R torque limits)
