# TITAN-7 ESP32 Motor Controller (MicroPython)
# Flash this to your ESP32 using ampy/mpremote/Thonny.
# Dual-leg bipedal firmware with pelvis assembly, weight shifting, torso mount.

import machine
import time
import sys
import math

# ═══════════════════════════════════════════════════════════════
# HARDWARE CONFIG — 12 SERVOS + PELVIS + TORSO
# ═══════════════════════════════════════════════════════════════

# RIGHT LEG (channels 0-5 on PCA9685)
# 0: Hip Yaw, 1: Hip Roll, 2: Hip Pitch, 3: Knee Pitch, 4: Ankle Pitch, 5: Ankle Roll
RIGHT_LEG = {
    'hip_yaw':      0,
    'hip_roll':     1,
    'hip_pitch':    2,
    'knee_pitch':   3,
    'ankle_pitch':  4,
    'ankle_roll':   5,
}

# LEFT LEG (channels 6-11 on PCA9685) — MIRRORED
# 6: Hip Yaw, 7: Hip Roll, 8: Hip Pitch, 9: Knee Pitch, 10: Ankle Pitch, 11: Ankle Roll
LEFT_LEG = {
    'hip_yaw':      6,
    'hip_roll':     7,
    'hip_pitch':    8,
    'knee_pitch':   9,
    'ankle_pitch': 10,
    'ankle_roll':  11,
}

# PELVIS ASSEMBLY (shared hip structure)
# 12: Pelvis Yaw (whole butt rotates left/right)
# 13: Pelvis Roll (whole butt tilts left/right — weight shift)
PELVIS = {
    'yaw':   12,
    'roll':  13,
}

# TORSO MOUNT (channel 14: neck/phone tilt, 15: waist twist if needed)
TORSO = {
    'neck_pitch': 14,
    'waist_yaw':  15,
}

# ALL SERVO CHANNELS IN ORDER
SERVO_MAP = [
    RIGHT_LEG['hip_yaw'], RIGHT_LEG['hip_roll'], RIGHT_LEG['hip_pitch'],
    RIGHT_LEG['knee_pitch'], RIGHT_LEG['ankle_pitch'], RIGHT_LEG['ankle_roll'],
    LEFT_LEG['hip_yaw'], LEFT_LEG['hip_roll'], LEFT_LEG['hip_pitch'],
    LEFT_LEG['knee_pitch'], LEFT_LEG['ankle_pitch'], LEFT_LEG['ankle_roll'],
    PELVIS['yaw'], PELVIS['roll'],
    TORSO['neck_pitch'], TORSO['waist_yaw'],
]

# PCA9685 I2C
PCA9685_ADDR = 0x40
PCA9685_FREQ = 50  # 50Hz for analog servos
BAUD_RATE = 115200

# PWM LIMITS (16-bit duty cycle 0-65535)
# 1ms pulse = ~3277, 2ms pulse = ~6554, 1.5ms center = ~4915
SERVO_MIN = 2400   # ~0.73ms  (-90 deg hard limit)
SERVO_MAX = 7400   # ~2.25ms  (+90 deg hard limit)
SERVO_CENTER = 4915  # 1.5ms center (0 deg)

# ═══════════════════════════════════════════════════════════════
# I2C / PCA9685 DRIVER
# ═══════════════════════════════════════════════════════════════

class PCA9685:
    MODE1 = 0x00
    PRESCALE = 0xFE
    LED0_ON_L = 0x06
    
    def __init__(self, i2c, address=PCA9685_ADDR):
        self.i2c = i2c
        self.addr = address
        self._init()
    
    def _init(self):
        # Reset
        self.i2c.writeto_mem(self.addr, self.MODE1, b'\x00')
        time.sleep_ms(5)
        # Set frequency
        prescale_val = int(25000000.0 / (4096 * PCA9685_FREQ) - 1)
        old_mode = self.i2c.readfrom_mem(self.addr, self.MODE1, 1)[0]
        self.i2c.writeto_mem(self.addr, self.MODE1, bytes([(old_mode & 0x7F) | 0x10]))  # sleep
        self.i2c.writeto_mem(self.addr, self.PRESCALE, bytes([prescale_val]))
        self.i2c.writeto_mem(self.addr, self.MODE1, bytes([old_mode | 0xA1]))  # auto-increment + restart
        time.sleep_ms(5)
    
    def set_pwm(self, channel, on, off):
        base = self.LED0_ON_L + 4 * channel
        data = bytes([on & 0xFF, on >> 8, off & 0xFF, off >> 8])
        self.i2c.writeto_mem(self.addr, base, data)
    
    def set_servo(self, channel, duty):
        duty = max(SERVO_MIN, min(SERVO_MAX, int(duty)))
        self.set_pwm(channel, 0, duty)

# ═══════════════════════════════════════════════════════════════
# KINEMATICS HELPERS
# ═══════════════════════════════════════════════════════════════

def angle_to_duty(angle_deg):
    """Convert -90..+90 degrees to PWM duty cycle."""
    angle_deg = max(-90, min(90, angle_deg))
    return int(SERVO_CENTER + (angle_deg / 90.0) * 2500)

def deg_to_rad(d): return d * math.pi / 180

# ═══════════════════════════════════════════════════════════════
# POSE ENGINE — BASIC BIPEDAL GAIT WITH WEIGHT SHIFT
# ═══════════════════════════════════════════════════════════════

class BipedPoseEngine:
    def __init__(self, pca):
        self.pca = pca
        self.current_pose = {ch: 0 for ch in SERVO_MAP}
        self.phase = 0.0
        self.step_length = 15  # degrees
        self.step_height = 25  # degrees
        self.weight_shift = 8  # pelvis roll for CoM transfer
        
    def set_channel(self, name, angle, leg='right'):
        """Set servo by anatomical name."""
        if leg == 'right':
            ch = RIGHT_LEG.get(name)
        elif leg == 'left':
            ch = LEFT_LEG.get(name)
        elif leg == 'pelvis':
            ch = PELVIS.get(name)
        elif leg == 'torso':
            ch = TORSO.get(name)
        else:
            return
        if ch is not None:
            duty = angle_to_duty(angle)
            self.pca.set_servo(ch, duty)
            self.current_pose[ch] = angle
    
    def set_both_legs(self, name, angle):
        """Mirror angle to both legs (left gets -angle for roll/yaw)."""
        if name in ['hip_roll', 'hip_yaw', 'ankle_roll']:
            self.set_channel(name, angle, 'right')
            self.set_channel(name, -angle, 'left')
        elif name in ['hip_pitch', 'knee_pitch', 'ankle_pitch']:
            # Pitch is same direction for both legs
            self.set_channel(name, angle, 'right')
            self.set_channel(name, angle, 'left')
    
    def stand_neutral(self):
        """Full neutral stand — all joints 0, pelvis level."""
        for name in ['hip_yaw', 'hip_roll', 'hip_pitch', 'knee_pitch', 'ankle_pitch', 'ankle_roll']:
            self.set_both_legs(name, 0)
        self.set_channel('roll', 0, 'pelvis')
        self.set_channel('yaw', 0, 'pelvis')
        self.set_channel('neck_pitch', 0, 'torso')
        self.set_channel('waist_yaw', 0, 'torso')
        print("POSE: NEUTRAL_STAND")
    
    def weight_shift_to(self, side, amount=None):
        """Shift CoM to 'left' or 'right' via pelvis roll + ankle strategy."""
        if amount is None:
            amount = self.weight_shift
        
        if side == 'left':
            # Pelvis tilts left -> CoM over left foot
            # Right ankle rolls outward to compensate
            self.set_channel('roll', -amount, 'pelvis')
            self.set_channel('ankle_roll', -amount, 'right')
            self.set_channel('ankle_roll', amount, 'left')
            self.set_channel('hip_roll', amount, 'right')
            self.set_channel('hip_roll', -amount, 'left')
        elif side == 'right':
            self.set_channel('roll', amount, 'pelvis')
            self.set_channel('ankle_roll', amount, 'right')
            self.set_channel('ankle_roll', -amount, 'left')
            self.set_channel('hip_roll', -amount, 'right')
            self.set_channel('hip_roll', amount, 'left')
        print(f"WEIGHT_SHIFT: {side} ({amount}deg)")
    
    def step_forward(self, leg='right', swing=15, lift=25):
        """Single step with weight shift.
        leg='right': right leg swings forward, weight on left
        """
        if leg == 'right':
            stance, swing_leg = 'left', 'right'
            weight_side = 'left'
        else:
            stance, swing_leg = 'right', 'left'
            weight_side = 'right'
        
        # PHASE 1: Weight shift onto stance leg
        self.weight_shift_to(weight_side)
        time.sleep_ms(200)
        
        # PHASE 2: Swing leg lifts & extends
        self.set_channel('hip_pitch', swing, swing_leg)
        self.set_channel('knee_pitch', -lift, swing_leg)
        self.set_channel('ankle_pitch', int(lift/2), swing_leg)
        time.sleep_ms(300)
        
        # PHASE 3: Swing leg plants, hip pushes back
        self.set_channel('hip_pitch', -int(swing/2), swing_leg)
        self.set_channel('knee_pitch', 0, swing_leg)
        self.set_channel('ankle_pitch', 0, swing_leg)
        time.sleep_ms(200)
        
        # PHASE 4: Transfer weight, stance leg becomes swing
        self.stand_neutral()
    
    def walk_cycle(self, steps=4, step_length=15):
        """Alternating walk cycle."""
        print(f"GAIT: WALK_CYCLE ({steps} steps)")
        for i in range(steps):
            leg = 'right' if i % 2 == 0 else 'left'
            self.step_forward(leg=leg, swing=step_length)
            time.sleep_ms(100)
        self.stand_neutral()
    
    def turn_in_place(self, direction='left', angle=15):
        """Pivot on both feet using hip yaw + pelvis yaw."""
        if direction == 'left':
            self.set_both_legs('hip_yaw', -angle)
            self.set_channel('yaw', -angle, 'pelvis')
        else:
            self.set_both_legs('hip_yaw', angle)
            self.set_channel('yaw', angle, 'pelvis')
        time.sleep_ms(400)
        self.stand_neutral()
    
    def lean(self, direction='forward', amount=10):
        """Lean torso + pelvis for dynamic balance."""
        if direction == 'forward':
            self.set_both_legs('hip_pitch', -amount)
            self.set_both_legs('ankle_pitch', amount)
            self.set_channel('neck_pitch', amount, 'torso')
        elif direction == 'backward':
            self.set_both_legs('hip_pitch', amount)
            self.set_both_legs('ankle_pitch', -amount)
            self.set_channel('neck_pitch', -amount, 'torso')
        elif direction == 'left':
            self.weight_shift_to('left', amount)
            self.set_channel('waist_yaw', -amount, 'torso')
        elif direction == 'right':
            self.weight_shift_to('right', amount)
            self.set_channel('waist_yaw', amount, 'torso')
        print(f"LEAN: {direction} ({amount}deg)")

# ═══════════════════════════════════════════════════════════════
# COMMAND PARSER
# ═══════════════════════════════════════════════════════════════

pose = None

def parse_command(cmd):
    global pose
    cmd = cmd.strip().upper()
    
    if cmd == "NEUTRAL":
        pose.stand_neutral()
        return "OK: NEUTRAL"
    
    elif cmd == "WALK":
        pose.walk_cycle(steps=4)
        return "OK: WALK_CYCLE"
    
    elif cmd.startswith("WALK:"):
        # WALK:steps:length
        parts = cmd.split(':')
        steps = int(parts[1]) if len(parts) > 1 else 4
        length = int(parts[2]) if len(parts) > 2 else 15
        pose.walk_cycle(steps=steps, step_length=length)
        return f"OK: WALK {steps} steps @ {length}deg"
    
    elif cmd.startswith("STEP:"):
        # STEP:left|right:length
        parts = cmd.split(':')
        leg = parts[1].lower() if len(parts) > 1 else 'right'
        length = int(parts[2]) if len(parts) > 2 else 15
        pose.step_forward(leg=leg, swing=length)
        return f"OK: STEP {leg}"
    
    elif cmd.startswith("SHIFT:"):
        # SHIFT:left|right:amount
        parts = cmd.split(':')
        side = parts[1].lower() if len(parts) > 1 else 'left'
        amount = int(parts[2]) if len(parts) > 2 else 8
        pose.weight_shift_to(side, amount)
        return f"OK: SHIFT {side} {amount}deg"
    
    elif cmd.startswith("LEAN:"):
        # LEAN:forward|backward|left|right:amount
        parts = cmd.split(':')
        direction = parts[1].lower() if len(parts) > 1 else 'forward'
        amount = int(parts[2]) if len(parts) > 2 else 10
        pose.lean(direction, amount)
        return f"OK: LEAN {direction}"
    
    elif cmd.startswith("TURN:"):
        # TURN:left|right:angle
        parts = cmd.split(':')
        direction = parts[1].lower() if len(parts) > 1 else 'left'
        angle = int(parts[2]) if len(parts) > 2 else 15
        pose.turn_in_place(direction, angle)
        return f"OK: TURN {direction}"
    
    elif cmd == "HOLD":
        # Freeze current position
        print("POSE: HOLD")
        return "OK: HOLD"
    
    elif cmd == "RELAX":
        # Disable all PWM (servos go limp)
        for ch in SERVO_MAP:
            pose.pca.set_pwm(ch, 0, 0)
        return "OK: RELAXED"
    
    else:
        return f"UNKNOWN: {cmd}"

# ═══════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════

def main():
    global pose
    
    print("═══════════════════════════════════════")
    print("  TITAN-7 BIPEDAL FIRMWARE v2.0")
    print("  12-DOF Legs + Pelvis + Torso Mount")
    print("═══════════════════════════════════════")
    
    # Init I2C + PCA9685
    i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
    devices = i2c.scan()
    if PCA9685_ADDR not in devices:
        print(f"❌ PCA9685 not found at 0x{PCA9685_ADDR:02X}. Found: {[hex(d) for d in devices]}")
        return
    
    pca = PCA9685(i2c)
    pose = BipedPoseEngine(pca)
    print("✅ PCA9685 initialized @ 50Hz")
    
    # Boot to neutral
    pose.stand_neutral()
    
    # UART for phone communication
    uart = machine.UART(0, baudrate=BAUD_RATE)
    print(f"✅ UART ready @ {BAUD_RATE} baud")
    print("🎮 Waiting for commands...")
    
    buffer = ""
    
    while True:
        if uart.any():
            try:
                data = uart.read()
                if data:
                    buffer += data.decode('utf-8')
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            print(f"RX: {line}")
                            response = parse_command(line)
                            uart.write(f"{response}\n".encode())
                            print(f"TX: {response}")
            except Exception as e:
                print(f"UART ERROR: {e}")
                buffer = ""
        
        time.sleep_ms(10)  # 100Hz polling

if __name__ == "__main__":
    main()
