#!/usr/bin/env python3
"""
TITAN-7 ARM64 Brain Controller v2.0
Runs on Termux. Reads phone sensors, queries local Ollama, and sends
coordinated bipedal commands to ESP32 (dual-leg + pelvis + torso).
"""

import subprocess
import json
import requests
import serial
import time
import math
import threading

# ─── CONFIG ─────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2:0.5b"
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200

# Command queue for async sending
cmd_queue = []
queue_lock = threading.Lock()

# ─── TERMUX SENSOR POLLING ─────────────────────────────────────
class TermuxSensor:
    @staticmethod
    def get_imu():
        try:
            cmd = ['termux-sensor', '-s', 'Gyroscope,Accelerometer', '-n', '1', '-d', '100']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
            data = json.loads(result.stdout)
            
            gyro = data['sensors'].get('Gyroscope', {}).get('values', [0,0,0])
            accel = data['sensors'].get('Accelerometer', {}).get('values', [0,0,0])
            
            return {
                "pitch_rate": gyro[0],   # rad/s
                "roll_rate": gyro[1],
                "yaw_rate": gyro[2],
                "x_accel": accel[0],     # m/s^2
                "y_accel": accel[1],
                "z_accel": accel[2],
                "timestamp": time.time()
            }
        except Exception as e:
            return {"error": str(e)}

# ─── LLM CORTEX ────────────────────────────────────────────────
class LLMCortex:
    @staticmethod
    def get_action_intent(sensor_data, current_state="standing", step_phase=0):
        """Queries 0.5B model for high-level gait decision."""
        # Build structured prompt
        pitch_rate = sensor_data.get('pitch_rate', 0)
        roll_rate = sensor_data.get('roll_rate', 0)
        z_accel = sensor_data.get('z_accel', 9.81)
        
        # Detect tilt
        pitch_deg = math.degrees(math.atan2(pitch_rate, 9.81)) if abs(pitch_rate) > 0.01 else 0
        roll_deg = math.degrees(math.atan2(roll_rate, 9.81)) if abs(roll_rate) > 0.01 else 0
        
        prompt = f"""BIPEDAL ROBOT CONTROL
State: {current_state}
Step phase: {step_phase} (0=double support, 1=right swing, 2=left swing)
IMU: pitch={pitch_deg:.1f}deg roll={roll_deg:.1f}deg z_accel={z_accel:.1f}

RULES:
- If z_accel < 8.0: robot falling forward → LEAN:backward
- If z_accel > 11.5: robot leaning back → LEAN:forward  
- If roll > 3: leaning right → SHIFT:left
- If roll < -3: leaning left → SHIFT:right
- If |pitch| < 2 and |roll| < 2 and step_phase==0: WALK:1
- If stepping and phase>0: HOLD
- Default: HOLD

Output ONE JSON:
{{"command": "WALK:1"|"STEP:right:15"|"SHIFT:left:8"|"LEAN:forward:10"|"HOLD"|"TURN:left:15", "reasoning": "brief why"}}"""
        
        try:
            response = requests.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.1,
                "num_predict": 128
            }, timeout=5)
            
            res_json = response.json()
            import re
            match = re.search(r'\{.*\}', res_json.get('response', '{}'), re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"command": "HOLD", "reasoning": "parse failed"}
        except Exception as e:
            return {"command": "HOLD", "reasoning": f"error: {e}"}

# ─── MOTOR CONTROLLER (async queue) ──────────────────────────
class MotorController:
    def __init__(self, port, baud):
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self.running = True
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.sender_thread.start()
        time.sleep(2)  # Wait for ESP32 reset
    
    def _sender_loop(self):
        while self.running:
            with queue_lock:
                if cmd_queue:
                    cmd = cmd_queue.pop(0)
                else:
                    cmd = None
            
            if cmd:
                full_cmd = f"CMD:{cmd}\n"
                try:
                    self.ser.write(full_cmd.encode('utf-8'))
                    # Read response
                    resp = self.ser.readline().decode('utf-8').strip()
                    if resp:
                        print(f"[ESP32] {resp}")
                except Exception as e:
                    print(f"[TX ERROR] {e}")
            
            time.sleep(0.02)  # 50Hz send rate
    
    def send(self, command):
        with queue_lock:
            cmd_queue.append(command)
    
    def close(self):
        self.running = False
        self.sender_thread.join(timeout=1)
        self.ser.close()

# ─── STATE MACHINE ─────────────────────────────────────────────
class GaitStateMachine:
    def __init__(self):
        self.state = "standing"
        self.step_phase = 0  # 0=double, 1=right_swing, 2=left_swing
        self.steps_taken = 0
        self.last_llm_call = 0
        self.llm_interval = 1.0  # seconds
    
    def update(self, sensor_data, llm_intent, mc):
        now = time.time()
        
        # Execute LLM command
        cmd = llm_intent.get("command", "HOLD")
        reasoning = llm_intent.get("reasoning", "")
        print(f"🧠 LLM: {cmd} — {reasoning}")
        
        if cmd != "HOLD":
            mc.send(cmd)
        
        # Update internal state based on command
        if cmd.startswith("WALK") or cmd.startswith("STEP"):
            self.state = "walking"
            if "right" in cmd.lower():
                self.step_phase = 1
            elif "left" in cmd.lower():
                self.step_phase = 2
            self.steps_taken += 1
        elif cmd.startswith("SHIFT") or cmd.startswith("LEAN"):
            self.state = "balancing"
            self.step_phase = 0
        elif cmd.startswith("TURN"):
            self.state = "turning"
        else:
            self.state = "standing"
            self.step_phase = 0
        
        return self.state, self.step_phase

# ─── MAIN LOOP ─────────────────────────────────────────────────
def main():
    print("═══════════════════════════════════════")
    print("  TITAN-7 ARM64 BRAIN v2.0")
    print("  Dual-Leg + Pelvis + Torso Control")
    print("═══════════════════════════════════════")
    
    # Check termux-api
    if subprocess.run(['termux-sensor', '-l'], capture_output=True).returncode != 0:
        print("❌ termux-api not installed. Run: pkg install termux-api")
        return
    
    # Connect to ESP32
    try:
        mc = MotorController(SERIAL_PORT, BAUD_RATE)
        print(f"✅ Connected to ESP32 on {SERIAL_PORT}")
    except Exception as e:
        print(f"⚠️ Could not connect to serial: {e}")
        print("Running in SIMULATION mode (no motor output).")
        mc = None
    
    gait = GaitStateMachine()
    loop_count = 0
    
    try:
        while True:
            loop_count += 1
            
            # 1. Read Sensors (10Hz = 100ms)
            sensors = TermuxSensor.get_imu()
            if "error" in sensors:
                print(f"⚠️ Sensor error: {sensors['error']}")
                time.sleep(0.1)
                continue
            
            # 2. LLM Decision (every 10 loops = ~1Hz)
            if loop_count % 10 == 0:
                intent = LLMCortex.get_action_intent(
                    sensors, 
                    gait.state, 
                    gait.step_phase
                )
                gait.update(sensors, intent, mc)
            
            # 3. Debug output (every 20 loops = 2Hz)
            if loop_count % 20 == 0:
                print(f"📊 IMU: pitch={math.degrees(math.atan2(sensors['pitch_rate'], 9.81)):.1f}° "
                      f"roll={math.degrees(math.atan2(sensors['roll_rate'], 9.81)):.1f}° "
                      f"z={sensors['z_accel']:.1f} | State: {gait.state} "
                      f"Phase: {gait.step_phase} Steps: {gait.steps_taken}")
            
            time.sleep(0.1)  # 10Hz main loop
    
    except KeyboardInterrupt:
        print("\n🛑 Shutting down TITAN-7 Brain...")
        if mc:
            mc.send("NEUTRAL")
            time.sleep(0.5)
            mc.send("RELAX")
            mc.close()

if __name__ == "__main__":
    main()
