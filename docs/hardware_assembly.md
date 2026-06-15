# TITAN-7 Bipedal Hardware Assembly Guide
## Pelvis, Dual-Leg Mirroring & Torso Mount

---

## 📐 Mechanical Architecture Overview

```
                    ┌─────────────────┐
                    │   PHONE MOUNT   │ ◄─── Torso: neck_pitch (ch14), waist_yaw (ch15)
                    │   (Termux)      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  TORSO PLATE    │ ◄─── 3D printed, bolts to pelvis
                    │  (battery,      │
                    │   ESP32, UBEC)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  PELVIS ASSEMBLY│ ◄─── Shared structure
                    │  ┌─────┬─────┐  │
                    │  │HipY │HipR │  │ ◄─── Pelvis Yaw (ch12) + Roll (ch13)
                    │  └─────┴─────┘  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
       ┌──────▼──────┐  ┌────▼────┐  ┌─────▼──────┐
       │  RIGHT LEG  │  │ (gap)  │  │  LEFT LEG  │
       │  (ch0-5)    │  │        │  │  (ch6-11)  │
       └─────────────┘  └────────┘  └────────────┘
```

---

## 🦴 Pelvis Assembly (Critical for Bipedal Balance)

### Design Requirements
| Requirement | Specification |
|-------------|---------------|
| **Material** | PETG (heat resistant) or ASA, 4-5mm walls, 30% infill |
| **Hip spacing** | 120mm center-to-center (adjust for your servo horns) |
| **Pelvis yaw range** | ±30° (ch12) |
| **Pelvis roll range** | ±15° (ch13) — this IS your weight shift mechanism |
| **Mounting** | 4× M3 bolts to torso plate, 4× M3 to each hip yaw servo |

### Pelvis Function
The pelvis is NOT just a connector — it's the **primary CoM shifter**:
- **Pelvis Roll (ch13)**: Tilts entire hip structure left/right → moves CoM over stance foot
- **Pelvis Yaw (ch12)**: Rotates hips for turning / step alignment
- **Without active pelvis roll**: Robot cannot walk — ankles alone don't provide enough CoM transfer

### 3D Print Files Needed
```
titan-7-stl/
├── pelvis_center.stl       # Main pelvis block (2 hip yaw mounts + roll servo)
├── pelvis_roll_arm.stl     # Lever arm for pelvis roll servo (if not direct drive)
├── hip_yaw_bracket.stl     # ×2 — mounts hip yaw servo to pelvis
├── torso_plate.stl         # Battery/ESP32 mount, bolts to pelvis
└── phone_clamp.stl         # Termux phone holder on torso
```

---

## 🦵 Left Leg Mirroring (Exact Right-Leg Clone)

### Servo Channel Mapping (PCA9685)

| Joint | Right Leg | Left Leg | Notes |
|-------|-----------|----------|-------|
| Hip Yaw | ch0 | ch6 | Positive = outward on both |
| Hip Roll | ch1 | ch7 | **Mirrored**: + = right leg rolls right, left leg rolls left |
| Hip Pitch | ch2 | ch8 | + = forward on both |
| Knee Pitch | ch3 | ch9 | + = bend on both |
| Ankle Pitch | ch4 | ch10 | + = toes up on both |
| Ankle Roll | ch5 | ch11 | **Mirrored**: same as hip roll |

### Physical Mirroring Rules
1. **Hip Yaw servo**: Mount IDENTICAL orientation (both output shafts facing forward)
2. **Hip Roll servo**: Mount MIRRORED (left leg roll servo rotated 180° vs right)
3. **Hip Pitch servo**: Mount IDENTICAL
4. **Knee Pitch servo**: Mount IDENTICAL (both bend backward)
5. **Ankle Pitch servo**: Mount IDENTICAL
6. **Ankle Roll servo**: Mount MIRRORED (same logic as hip roll)

### Wiring Left Leg
```
PCA9685 channels 6-11 → Left leg servos (same wire colors, mirrored mounting)
I2C: SDA=GPIO21, SCL=GPIO22 (shared with right leg)
Power: All servo V+ → UBEC 5V, all GND → UBEC GND
```

---

## 🔧 Torso Mount (Phone + Battery + ESP32)

### Components on Torso Plate
| Item | Mounting |
|------|----------|
| **Phone (Termux brain)** | Spring-loaded clamp, vertical ±15° tilt (neck_pitch ch14) |
| **ESP32 + PCA9685** | Centered, velcro/3M tape |
| **UBEC 5V 5A** | Bolted to plate, heatsink exposed |
| **3S LiPo 2200mAh** | Strapped with Velcro battery strap |
| **MPU6050 (backup IMU)** | Flat on torso plate, SDA/SCL to ESP32 I2C1 |

### Torso Degrees of Freedom
| Channel | Joint | Range | Purpose |
|---------|-------|-------|---------|
| ch14 | Neck Pitch | ±30° | Phone tilt for camera / balance visual |
| ch15 | Waist Yaw | ±45° | Upper body twist for turning momentum |

### Torso Plate Dimensions
- **Size**: 120mm × 80mm × 5mm (carbon fiber or 3D printed PETG)
- **Mounting**: 4× M3 standoffs (20mm) to pelvis top face
- **Cable routing**: Central hole for servo wires from pelvis → PCA9685

---

## ⚡ Complete Wiring Diagram

```
                    ┌───────────────────┐
                    │   3S LiPo 11.1V   │
                    │    2200mAh        │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   UBEC 5V 5A      │◄─── Steps 11.1V → 5V
                    │  (heatsink up!)   │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
       ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
       │ PCA9685 V+  │ │ ESP32 VIN   │ │ MPU6050 VCC │
       │ (servo pwr) │ │ (logic)     │ │ (3.3V)      │
       └─────────────┘ └─────────────┘ └─────────────┘
              │               │               │
       ┌──────▼───────────────▼───────────────▼┐
       │           COMMON GND RAIL              │
       │  UBEC(-) = ESP32 GND = PCA9685 GND =   │
       │  Servo GND = MPU6050 GND = Battery(-)  │
       └────────────────────────────────────────┘

I2C BUS (shared):
  ESP32 GPIO21 (SDA) ────┬──── PCA9685 SDA (0x40)
  ESP32 GPIO22 (SCL) ────┼──── PCA9685 SCL
                         │
                         ├──── MPU6050 SDA (0x68)
                         └──── MPU6050 SCL

UART (Phone ↔ ESP32):
  Phone USB OTG ── /dev/ttyUSB0 ── ESP32 UART0 (GPIO1=TX, GPIO3=RX) @ 115200

SERVO SIGNALS (PCA9685 → Servos):
  ch0-5  → Right leg (HipY, HipR, HipP, Knee, AnkleP, AnkleR)
  ch6-11 → Left  leg (HipY, HipR, HipP, Knee, AnkleP, AnkleR) [MIRRORED]
  ch12   → Pelvis Yaw
  ch13   → Pelvis Roll
  ch14   → Torso Neck Pitch
  ch15   → Torso Waist Yaw
```

---

## 📏 Kinematic Dimensions (Current Prototype)

| Segment | Length | Notes |
|---------|--------|-------|
| Thigh (hip→knee) | 150mm | 3D print or carbon tube |
| Shin (knee→ankle) | 150mm | Same as thigh for symmetry |
| Foot (ankle→ground) | 60mm | Flat plate or printed foot |
| Hip width (pelvis) | 120mm | Center-to-center hip yaw |
| Ankle height (standing) | ~300mm | Thigh + shin vertical |
| Total height | ~400mm | Standing neutral |

### Servo Torque Check (MG996R @ 6V = 11kg·cm)
| Joint | Max Load (est.) | Safety Factor |
|-------|-----------------|---------------|
| Hip Pitch | ~3.5kg (full weight) | 3.1x ✅ |
| Knee Pitch | ~2.8kg | 3.9x ✅ |
| Ankle Pitch | ~2.0kg | 5.5x ✅ |
| Hip Roll | ~1.2kg (side load) | 9.2x ✅ |
| Pelvis Roll | ~4.0kg (full CoM shift) | 2.7x ⚠️ consider dual servo |

> ⚠️ **Pelvis Roll** carries the most load. If it stalls, upgrade to:
> - 2× MG996R in parallel on ch13 (mechanical linkage)
> - Or single HS-805BB (27kg·cm) / 3D-printed gear reduction

---

## 🛠️ Assembly Order

1. **Print all parts** (PETG, 0.2mm layer, 30% gyroid infill)
2. **Assemble right leg** → test each servo range with `NEUTRAL` + `STEP:right:15`
3. **Assemble left leg** → mirror mounting, test `STEP:left:15`
4. **Build pelvis** → mount both hip yaw servos, install pelvis roll servo
5. **Mount legs to pelvis** → bolt hip yaw brackets to pelvis sides
6. **Wire all 12 leg servos** to PCA9685 ch0-11
7. **Install pelvis yaw/roll** (ch12, ch13) → test `SHIFT:left:8` `SHIFT:right:8`
8. **Mount torso plate** on pelvis (4× M3 standoffs)
9. **Mount ESP32, PCA9685, UBEC, battery** on torso
10. **Mount phone clamp** on torso neck servo (ch14)
11. **Full integration test**: `NEUTRAL` → `WALK:4:15` → `LEAN:forward:10`

---

## 🧪 Validation Checklist

| Test | Command | Expected |
|------|---------|----------|
| Right leg neutral | `NEUTRAL` | All ch0-5 at 0° |
| Left leg neutral | `NEUTRAL` | All ch6-11 at 0° |
| Right step | `STEP:right:15` | Right leg swings, left stance |
| Left step | `STEP:left:15` | Left leg swings, right stance |
| Weight shift left | `SHIFT:left:8` | Pelvis rolls left, ankles compensate |
| Weight shift right | `SHIFT:right:8` | Pelvis rolls right, ankles compensate |
| Walk cycle | `WALK:4:15` | 4 alternating steps |
| Lean forward | `LEAN:forward:10` | Both hips pitch back, ankles forward |
| Turn | `TURN:left:15` | Hip yaw + pelvis yaw left |

---

## 🔗 Repository Integration

Files to add/update:
```
titan-7arm64/
├── microcontroller/esp32_main.py   # ← Updated with dual-leg + pelvis + torso
├── brain/main.py                   # ← Updated with gait state machine
├── docs/
│   ├── hardware_assembly.md        # ← THIS FILE
│   ├── pelvis_assembly.md          # Detailed pelvis print + build
│   └── torso_mount.md              # Torso plate + phone clamp
└── stl/                            # Add your STL files here
    ├── pelvis_center.stl
    ├── hip_yaw_bracket.stl
    ├── torso_plate.stl
    └── phone_clamp.stl
```

---

*Built for the dreamers shipping hardware from Termux. The pelvis IS the robot.*
 