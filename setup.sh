#!/data/data/com.termux/files/usr/bin/bash
# TITAN-7 ARM64 Termux Setup Script
# Run this once to provision your phone's environment.
# CRITICAL: Shizuku must be running before this script completes.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
bad()  { echo -e "${RED}[FAIL]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
info() { echo -e "${CYAN}[INFO]${NC} $1"; }

echo "═══════════════════════════════════════════════════════"
echo "  🚀 TITAN-7 ARM64 Environment Provisioner"
echo "═══════════════════════════════════════════════════════"
echo ""

# ─── 1. Update and install core dependencies ───────────────────
info "[1/6] Updating packages and installing core deps..."
pkg update -y -o Dpkg::Options::=--force-confdef >/dev/null
pkg install -y python termux-api openssl curl jq >/dev/null
ok "Core packages installed"

# ─── 2. Grant Termux API permissions ──────────────────────────
info "[2/6] Setting up Termux storage & API permissions..."
termux-setup-storage
ok "Storage permission granted"

# ─── 3. Python dependencies ────────────────────────────────────
info "[3/6] Installing Python dependencies..."
pip install --upgrade pip >/dev/null 2>&1
pip install pyserial requests >/dev/null 2>&1
ok "pyserial, requests installed"

# ─── 4. Shizuku — MANDATORY ────────────────────────────────────
info "[4/6] Verifying Shizuku (CRITICAL DEPENDENCY)..."

SHIZUKU_RUNNING=0

# Check if Shizuku CLI is available
if command -v shizuku >/dev/null 2>&1; then
    # Try to get status
    if shizuku --status 2>/dev/null | grep -q "running"; then
        ok "Shizuku service is RUNNING"
        SHIZUKU_RUNNING=1
    else
        warn "Shizuku CLI found but service not running"
    fi
else
    warn "Shizuku CLI not installed in Termux"
fi

# If not running, guide user to start it
if [[ $SHIZUKU_RUNNING -eq 0 ]]; then
    echo ""
    echo -e "${RED}═══════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  SHIZUKU IS NOT RUNNING — TITAN-7 WILL NOT WORK${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Shizuku provides:"
    echo "  • Background sensor wakelock (prevents Doze killing IMU)"
    echo "  • USB OTG serial access to ESP32 (/dev/ttyUSB*)"
    echo "  • GPU/DRM node access for future acceleration"
    echo ""
    echo "To fix:"
    echo "  1. Install Shizuku app from Play Store or F-Droid"
    echo "  2. Open Shizuku app → 'Start' (or enable Wireless Debugging)"
    echo "  3. Run this command to verify:"
    echo -e "     ${CYAN}shizuku --status${NC}"
    echo "  4. Re-run this setup script"
    echo ""
    echo -e "${YELLOW}Continuing without Shizuku — sensors & serial WILL FAIL.${NC}"
    echo ""
    read -p "Press ENTER to continue anyway, or Ctrl+C to cancel..."
fi

# ─── 5. Ollama + Model ────────────────────────────────────────
info "[5/6] Checking Ollama installation..."

if ! command -v ollama >/dev/null 2>&1; then
    warn "Ollama not found"
    echo "  Installing Ollama (Termux-native)..."
    curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || true
    
    if ! command -v ollama >/dev/null 2>&1; then
        bad "Ollama install failed. You may need proot-distro Ubuntu for Ollama on Android."
        echo "  Alternative: pkg install proot-distro && proot-distro install ubuntu"
        echo "  Then run: proot-distro login ubuntu -- apt install ollama"
    else
        ok "Ollama installed"
    fi
else
    ok "Ollama already installed"
fi

# Pull model
if command -v ollama >/dev/null 2>&1; then
    info "[6/6] Pulling Qwen 0.5B model..."
    if ollama pull qwen2:0.5b >/dev/null 2>&1; then
        ok "Model qwen2:0.5b ready"
    else
        warn "Model pull failed (will retry on first run)"
    fi
fi

# ─── Final verification ────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Setup Complete — Verification"
echo "═══════════════════════════════════════════════════════"

# termux-sensor test
if termux-sensor -l >/dev/null 2>&1; then
    ok "termux-api sensor CLI works"
else
    warn "termux-sensor failed (need termux-api app from Play Store + permissions)"
fi

# Check serial port exists
if ls /dev/ttyUSB* >/dev/null 2>&1 || ls /dev/ttyACM* >/dev/null 2>&1; then
    ok "Serial device detected"
else
    warn "No /dev/ttyUSB* or /dev/ttyACM* found (connect ESP32 via USB OTG)"
fi

# Shizuku final status
if [[ $SHIZUKU_RUNNING -eq 1 ]]; then
    ok "Shizuku: RUNNING"
else
    bad "Shizuku: NOT RUNNING (robot will fall over)"
fi

echo ""
echo "Next steps:"
echo "  1. Connect ESP32 via USB OTG"
echo "  2. Flash microcontroller/esp32_main.py to ESP32 (ampy/mpremote/Thonny)"
echo "  3. Run brain: ${CYAN}python3 brain/main.py${NC}"
echo ""
