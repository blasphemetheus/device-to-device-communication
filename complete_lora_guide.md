# LoRa Point-to-Point Communication Guide
## Complete Testing Framework with Bash Scripts and Elixir Support

---

## Table of Contents
1. [Understanding LoRa Technology](#understanding-lora-technology)
2. [Hardware Setup](#hardware-setup)
3. [Bash Script Testing Framework](#bash-script-testing-framework)
4. [Elixir LoRa Implementation](#elixir-lora-implementation)
5. [Manual Testing Commands](#manual-testing-commands)
6. [File Transfer Protocol](#file-transfer-protocol)
7. [Advanced Configurations](#advanced-configurations)
8. [Troubleshooting Reference](#troubleshooting-reference)

---

## Understanding LoRa Technology

### What Makes LoRa Different

LoRa (Long Range) is a **chirp spread spectrum** modulation technique that trades data rate for range and power efficiency. Unlike your WiFi ad-hoc or Bluetooth PAN connections which operate in the 2.4GHz band, LoRa typically uses sub-GHz frequencies.

```bash
# Frequency bands by region (ISM bands - no license required)
US902-928:   902-928 MHz  # Americas
EU863-870:   863-870 MHz  # Europe  
AS923:       923 MHz      # Asia
AU915-928:   915-928 MHz  # Australia
IN865-867:   865-867 MHz  # India
```

### Key Parameters Explained

#### Spreading Factor (SF)
The spreading factor determines how much the data is "spread" in time. Think of it like speaking slower to be understood from farther away:

```bash
SF7:  Fast speech, close range    = 2^7  = 128 chips/symbol
SF8:  Slower...                   = 2^8  = 256 chips/symbol
SF9:  Even slower...               = 2^9  = 512 chips/symbol
SF10: Getting very slow...         = 2^10 = 1024 chips/symbol
SF11: Very slow and clear...       = 2^11 = 2048 chips/symbol
SF12: Extremely slow, max range    = 2^12 = 4096 chips/symbol

# Each +1 SF roughly:
# - Doubles transmission time
# - Adds ~2.5dB link budget (extends range ~40%)
# - Halves data rate
```

#### Bandwidth (BW)
The bandwidth is like the width of the highway for your data:

```bash
125 kHz: Narrow road, slow but goes far   (most common)
250 kHz: Medium road, balanced
500 kHz: Wide road, fast but shorter range

# Relationship: Narrower bandwidth = better sensitivity = longer range
```

#### Coding Rate (CR)
Error correction overhead - like adding redundancy to your message:

```bash
4/5: "HELLO"     -> "HELLO1"     (least redundancy, fastest)
4/6: "HELLO"     -> "HELLO12"    
4/7: "HELLO"     -> "HELLO123"   
4/8: "HELLO"     -> "HELLO1234"  (most redundancy, most reliable)
```

### Data Rate Calculation

```bash
# Simplified formula
Data_Rate = SF × (BW / 2^SF) × CR

# Examples:
SF7,  BW125kHz, CR4/5:  ~5.5 kbps  (fastest)
SF9,  BW125kHz, CR4/5:  ~1.8 kbps  (balanced)
SF12, BW125kHz, CR4/8:  ~0.18 kbps (slowest, longest range)
```

### Time on Air Calculator

```bash
#!/bin/bash
# lora_airtime.sh - Calculate how long a packet takes to transmit

calculate_airtime() {
    local sf=$1
    local bw=$2
    local payload=$3
    local cr=$4
    
    # Simplified calculation (milliseconds)
    local symbols=$((8 + (8*payload - 4*sf + 28 + 16) / (4*sf)))
    local symbol_time=$(echo "scale=3; (2^$sf) / $bw" | bc)
    local airtime=$(echo "scale=1; $symbols * $symbol_time" | bc)
    
    echo "Configuration: SF$sf, BW${bw}kHz, ${payload} bytes"
    echo "Time on air: ${airtime} ms"
    echo "Max packets/sec: $(echo "scale=1; 1000 / $airtime" | bc)"
}

# Usage examples
calculate_airtime 7 125 20 5   # Fast, short range
calculate_airtime 12 125 20 8  # Slow, long range
```

---

## Hardware Setup

### Common LoRa Modules

| Module | Chip | Frequency | Power | Interface | Notes |
|--------|------|-----------|-------|-----------|-------|
| RFM95W | SX1276 | 868/915 MHz | 20dBm | SPI | Most common, cheap |
| RFM96W | SX1276 | 433 MHz | 20dBm | SPI | Better penetration |
| Dragino HAT | SX1276 | 868/915 MHz | 20dBm | SPI | Pi HAT form factor |
| RAK811 | SX1276 | Multiple | 20dBm | UART/SPI | Has MCU onboard |
| E32-TTL | SX1278 | 433/868/915 | 30dBm | UART | High power option |

### Wiring for Raspberry Pi

```bash
# SPI Connections for RFM95W/96W to Raspberry Pi
Module Pin  ->  RPi Pin   (GPIO)    Function
==========      ========  ======    ========
VIN         ->  Pin 1     (3.3V)    Power
GND         ->  Pin 6     (GND)     Ground  
SCK         ->  Pin 23    (GPIO11)  SPI Clock
MISO        ->  Pin 21    (GPIO9)   SPI MISO
MOSI        ->  Pin 19    (GPIO10)  SPI MOSI
NSS/CS      ->  Pin 24    (GPIO8)   Chip Select
RST         ->  Pin 22    (GPIO25)  Reset
DIO0        ->  Pin 7     (GPIO4)   TX/RX Done Interrupt
DIO1        ->  Pin 16    (GPIO23)  RX Timeout (optional)
DIO2        ->  Pin 18    (GPIO24)  FHSS Change (optional)
```

### Hardware Detection Script

```bash
#!/bin/bash
# detect_lora.sh - Detect LoRa module via SPI

detect_lora_module() {
    echo "=== LoRa Module Detection ==="
    
    # Check if SPI is enabled
    if [ ! -e /dev/spidev0.0 ]; then
        echo "❌ SPI not enabled!"
        echo "Run: sudo raspi-config -> Interfacing Options -> SPI"
        return 1
    fi
    echo "✓ SPI interface found"
    
    # Check if we can access SPI (need root or spi group)
    if [ ! -r /dev/spidev0.0 ]; then
        echo "❌ Cannot access SPI. Running with sudo or add user to spi group:"
        echo "   sudo usermod -a -G spi $USER"
        return 1
    fi
    echo "✓ SPI accessible"
    
    # Use Python to read version register
    python3 - <<EOF
import spidev
import RPi.GPIO as GPIO
import time

# Pin configuration
RESET_PIN = 25
NSS_PIN = 8

GPIO.setmode(GPIO.BCM)
GPIO.setup(RESET_PIN, GPIO.OUT)

# Reset module
GPIO.output(RESET_PIN, GPIO.LOW)
time.sleep(0.01)
GPIO.output(RESET_PIN, GPIO.HIGH)
time.sleep(0.1)

# Open SPI
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 5000000

# Read version register (0x42)
version = spi.xfer2([0x42 & 0x7F, 0x00])[1]

if version == 0x12:
    print("✓ SX1276/77/78/79 detected (version 0x{:02X})".format(version))
    print("✓ Module ready for use!")
elif version == 0x22:
    print("✓ SX1262 detected (version 0x{:02X})".format(version))
else:
    print("❌ Unknown chip version: 0x{:02X}".format(version))
    print("   Check wiring and power supply")

spi.close()
GPIO.cleanup()
EOF
}

# Run detection
detect_lora_module
```

---

## Bash Script Testing Framework

### Master LoRa Test Script

```bash
#!/bin/bash
# lora_test.sh - Main LoRa testing framework

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/lora.conf"
LOG_DIR="$SCRIPT_DIR/logs"
PYTHON_HELPER="$SCRIPT_DIR/lora_helper.py"

# Default parameters
DEFAULT_FREQ=915.0
DEFAULT_SF=7
DEFAULT_BW=125
DEFAULT_POWER=20
DEFAULT_SYNC=0x12

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Load configuration
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    else
        cat > "$CONFIG_FILE" <<EOF
# LoRa Configuration
FREQ=${DEFAULT_FREQ}
SF=${DEFAULT_SF}
BW=${DEFAULT_BW}
POWER=${DEFAULT_POWER}
SYNC_WORD=${DEFAULT_SYNC}
NODE_ID="NODE_A"
EOF
        echo "Created default config: $CONFIG_FILE"
    fi
}

# Initialize environment
init() {
    mkdir -p "$LOG_DIR"
    load_config
    
    # Check dependencies
    for cmd in python3 bc; do
        if ! command -v $cmd &> /dev/null; then
            echo -e "${RED}Missing dependency: $cmd${NC}"
            exit 1
        fi
    done
}

# Create Python helper for SPI communication
create_python_helper() {
    cat > "$PYTHON_HELPER" <<'PYEOF'
#!/usr/bin/env python3
import sys
import json
import time
import spidev
import RPi.GPIO as GPIO

class LoRaHelper:
    def __init__(self, config):
        self.config = config
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 5000000
        
        # GPIO setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(config['reset_pin'], GPIO.OUT)
        GPIO.setup(config['dio0_pin'], GPIO.IN)
        
        self.reset()
        self.configure()
    
    def reset(self):
        GPIO.output(self.config['reset_pin'], GPIO.LOW)
        time.sleep(0.01)
        GPIO.output(self.config['reset_pin'], GPIO.HIGH)
        time.sleep(0.1)
    
    def write_register(self, addr, value):
        self.spi.xfer2([addr | 0x80, value])
    
    def read_register(self, addr):
        return self.spi.xfer2([addr & 0x7F, 0x00])[1]
    
    def configure(self):
        # Set sleep mode
        self.write_register(0x01, 0x00)
        
        # Set frequency
        freq = int(self.config['freq'] * 65536 / 32)
        self.write_register(0x06, (freq >> 16) & 0xFF)
        self.write_register(0x07, (freq >> 8) & 0xFF)
        self.write_register(0x08, freq & 0xFF)
        
        # Set SF, BW, CR
        sf = self.config['sf']
        bw_map = {125: 0x70, 250: 0x80, 500: 0x90}
        bw = bw_map.get(self.config['bw'], 0x70)
        self.write_register(0x1D, bw | 0x04)  # BW + CR 4/5
        self.write_register(0x1E, (sf << 4) | 0x04)  # SF + CRC on
        
        # Set power
        self.write_register(0x09, 0x8F)  # Max power
        
        # Set sync word
        self.write_register(0x39, self.config['sync_word'])
    
    def send_packet(self, data):
        # Set FIFO pointer
        self.write_register(0x0D, 0x00)
        
        # Write payload
        payload = data.encode() if isinstance(data, str) else data
        self.write_register(0x00, len(payload))
        for byte in payload:
            self.write_register(0x00, byte)
        
        # TX mode
        self.write_register(0x01, 0x03)
        
        # Wait for TX done
        timeout = time.time() + 5
        while time.time() < timeout:
            if GPIO.input(self.config['dio0_pin']):
                self.write_register(0x12, 0xFF)  # Clear IRQ
                return True
        return False
    
    def receive_packet(self, timeout=1.0):
        # RX mode
        self.write_register(0x01, 0x05)
        
        start = time.time()
        while (time.time() - start) < timeout:
            if GPIO.input(self.config['dio0_pin']):
                # Read packet
                self.write_register(0x12, 0xFF)  # Clear IRQ
                length = self.read_register(0x13)
                
                # Read FIFO
                self.write_register(0x0D, 0x00)
                payload = []
                for _ in range(length):
                    payload.append(self.read_register(0x00))
                
                # Get RSSI
                rssi = self.read_register(0x1A) - 137
                
                try:
                    data = bytes(payload).decode('utf-8')
                except:
                    data = str(payload)
                
                return {'data': data, 'rssi': rssi, 'length': length}
        
        return None
    
    def cleanup(self):
        self.write_register(0x01, 0x00)  # Sleep mode
        self.spi.close()
        GPIO.cleanup()

# Command line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['send', 'receive', 'ping'])
    parser.add_argument('--freq', type=float, default=915.0)
    parser.add_argument('--sf', type=int, default=7)
    parser.add_argument('--bw', type=int, default=125)
    parser.add_argument('--sync', type=int, default=0x12)
    parser.add_argument('--data', type=str, default='Hello LoRa')
    parser.add_argument('--count', type=int, default=10)
    
    args = parser.parse_args()
    
    config = {
        'freq': args.freq,
        'sf': args.sf,
        'bw': args.bw,
        'sync_word': args.sync,
        'reset_pin': 25,
        'dio0_pin': 4
    }
    
    lora = LoRaHelper(config)
    
    try:
        if args.command == 'send':
            if lora.send_packet(args.data):
                print(f"Sent: {args.data}")
            else:
                print("Send failed")
                
        elif args.command == 'receive':
            print("Waiting for packets...")
            while True:
                pkt = lora.receive_packet(timeout=10)
                if pkt:
                    print(f"RX: {pkt['data']} (RSSI: {pkt['rssi']} dBm)")
                    
        elif args.command == 'ping':
            sent = 0
            received = 0
            
            for i in range(args.count):
                msg = f"PING_{i}_{time.time()}"
                if lora.send_packet(msg):
                    sent += 1
                    pkt = lora.receive_packet(timeout=2)
                    if pkt and 'PONG' in pkt['data']:
                        received += 1
                        print(f"[{i}] Reply: RSSI={pkt['rssi']} dBm")
                    else:
                        print(f"[{i}] Timeout")
                time.sleep(1)
            
            print(f"\nStats: {received}/{sent} received ({100*received/sent:.1f}%)")
            
    finally:
        lora.cleanup()
PYEOF
    chmod +x "$PYTHON_HELPER"
}

# Ping test function
lora_ping() {
    local target=${1:-"NODE_B"}
    local count=${2:-10}
    local interval=${3:-1}
    
    echo -e "${GREEN}Starting LoRa Ping Test${NC}"
    echo "Target: $target, Count: $count, Interval: ${interval}s"
    echo "Configuration: ${FREQ}MHz SF${SF} BW${BW}kHz"
    echo "=========================================="
    
    local sent=0
    local received=0
    local total_rssi=0
    
    for ((i=1; i<=count; i++)); do
        # Send ping
        local timestamp=$(date +%s%N)
        local ping_data="PING:${NODE_ID}:${target}:${i}:${timestamp}"
        
        if python3 "$PYTHON_HELPER" send --data "$ping_data" \
            --freq $FREQ --sf $SF --bw $BW --sync $SYNC_WORD; then
            sent=$((sent + 1))
            
            # Wait for pong
            local response=$(python3 "$PYTHON_HELPER" receive \
                --freq $FREQ --sf $SF --bw $BW --sync $SYNC_WORD \
                | grep "RX:" | head -n1)
            
            if [[ "$response" == *"PONG"* ]]; then
                received=$((received + 1))
                local rssi=$(echo "$response" | grep -o "RSSI: [0-9-]*" | awk '{print $2}')
                total_rssi=$((total_rssi + rssi))
                
                local rtt=$(($(date +%s%N) - timestamp))
                local rtt_ms=$(echo "scale=1; $rtt / 1000000" | bc)
                
                echo -e "[${i}] ${GREEN}✓${NC} Reply from $target: time=${rtt_ms}ms RSSI=${rssi}dBm"
            else
                echo -e "[${i}] ${RED}✗${NC} Request timeout"
            fi
        else
            echo -e "[${i}] ${RED}✗${NC} Send failed"
        fi
        
        sleep "$interval"
    done
    
    # Statistics
    echo "=========================================="
    echo -e "${BLUE}--- Ping Statistics ---${NC}"
    echo "Packets: Sent = $sent, Received = $received, Lost = $((sent - received))"
    
    if [ $received -gt 0 ]; then
        local loss_percent=$(echo "scale=1; 100 * ($sent - $received) / $sent" | bc)
        local avg_rssi=$((total_rssi / received))
        echo "Packet loss: ${loss_percent}%"
        echo "Average RSSI: ${avg_rssi} dBm"
    fi
}

# File transfer function
lora_send_file() {
    local filepath=$1
    local dest=${2:-"NODE_B"}
    
    if [ ! -f "$filepath" ]; then
        echo -e "${RED}File not found: $filepath${NC}"
        return 1
    fi
    
    local filename=$(basename "$filepath")
    local filesize=$(stat -c%s "$filepath")
    local chunk_size=200
    local chunks=$(( (filesize + chunk_size - 1) / chunk_size ))
    
    echo -e "${GREEN}Sending file: $filename${NC}"
    echo "Size: $filesize bytes"
    echo "Chunks: $chunks × $chunk_size bytes"
    echo "=========================================="
    
    # Send file info
    local info="FILE:INFO:$filename:$filesize:$chunks"
    python3 "$PYTHON_HELPER" send --data "$info" \
        --freq $FREQ --sf $SF --bw $BW --sync $SYNC_WORD
    
    # Send chunks
    local sent=0
    while IFS= read -r -n$chunk_size chunk; do
        local chunk_data="FILE:DATA:$sent:$(echo -n "$chunk" | base64 -w0)"
        
        if python3 "$PYTHON_HELPER" send --data "$chunk_data" \
            --freq $FREQ --sf $SF --bw $BW --sync $SYNC_WORD; then
            sent=$((sent + 1))
            local progress=$(echo "scale=1; 100 * $sent / $chunks" | bc)
            echo -ne "\rProgress: [$sent/$chunks] ${progress}%"
        fi
        
        # Flow control
        if [ $((sent % 5)) -eq 0 ]; then
            sleep 0.5
        fi
    done < "$filepath"
    
    echo -e "\n${GREEN}✓ File transfer complete${NC}"
}

# Spectrum scanner
lora_spectrum_scan() {
    local start=${1:-902}
    local end=${2:-928}
    local step=${3:-1}
    
    echo -e "${GREEN}LoRa Spectrum Scanner${NC}"
    echo "Range: ${start}-${end} MHz, Step: ${step} MHz"
    echo "=========================================="
    
    local clearest_freq=""
    local clearest_rssi=0
    
    for ((freq=start; freq<=end; freq+=step)); do
        # Set to RX mode and measure RSSI
        local rssi=$(python3 - <<EOF
import spidev
import time

spi = spidev.SpiDev()
spi.open(0, 0)

# Set frequency
freq_reg = int($freq * 65536 / 32)
spi.xfer2([0x86, (freq_reg >> 16) & 0xFF])
spi.xfer2([0x87, (freq_reg >> 8) & 0xFF])
spi.xfer2([0x88, freq_reg & 0xFF])

# Set to RX mode
spi.xfer2([0x81, 0x05])
time.sleep(0.1)

# Read RSSI
rssi = spi.xfer2([0x1B, 0x00])[1] - 137
print(rssi)

spi.close()
EOF
        )
        
        # Display bar graph
        local bar_len=$(( (rssi + 120) / 2 ))
        local bar=""
        for ((i=0; i<bar_len; i++)); do
            bar="${bar}█"
        done
        
        printf "%4d MHz: %4d dBm %s\n" "$freq" "$rssi" "$bar"
        
        if [ -z "$clearest_freq" ] || [ "$rssi" -lt "$clearest_rssi" ]; then
            clearest_freq=$freq
            clearest_rssi=$rssi
        fi
    done
    
    echo "=========================================="
    echo -e "${GREEN}Clearest frequency: ${clearest_freq} MHz at ${clearest_rssi} dBm${NC}"
}

# Range test
lora_range_test() {
    local mode=${1:-"tx"}
    
    if [ "$mode" == "tx" ]; then
        echo -e "${GREEN}Range Test - Transmitter${NC}"
        echo "Sending beacon every 2 seconds..."
        echo "Move away from receiver to test range"
        echo "=========================================="
        
        local seq=0
        while true; do
            local beacon="BEACON:${NODE_ID}:${seq}:$(date +%s)"
            python3 "$PYTHON_HELPER" send --data "$beacon" \
                --freq $FREQ --sf $SF --bw $BW --sync $SYNC_WORD \
                --power $POWER
            
            echo -ne "\rBeacon #${seq} sent"
            seq=$((seq + 1))
            sleep 2
        done
    else
        echo -e "${GREEN}Range Test - Receiver${NC}"
        echo "Listening for beacons..."
        echo "=========================================="
        
        python3 "$PYTHON_HELPER" receive \
            --freq $FREQ --sf $SF --bw $BW --sync $SYNC_WORD
    fi
}

# Main menu
show_menu() {
    echo -e "\n${BLUE}=== LoRa Test Menu ===${NC}"
    echo "Current config: ${FREQ}MHz SF${SF} BW${BW}kHz Power${POWER}dBm"
    echo ""
    echo "1) Detect LoRa module"
    echo "2) Ping test"
    echo "3) Send file"
    echo "4) Receive file"
    echo "5) Spectrum scan"
    echo "6) Range test (TX)"
    echo "7) Range test (RX)"
    echo "8) Configure parameters"
    echo "9) Install dependencies"
    echo "0) Exit"
    echo ""
    read -p "Select option: " choice
}

# Configuration menu
configure_menu() {
    echo -e "\n${BLUE}=== Configure LoRa Parameters ===${NC}"
    
    read -p "Frequency MHz [$FREQ]: " new_freq
    FREQ=${new_freq:-$FREQ}
    
    read -p "Spreading Factor (7-12) [$SF]: " new_sf
    SF=${new_sf:-$SF}
    
    read -p "Bandwidth kHz (125/250/500) [$BW]: " new_bw
    BW=${new_bw:-$BW}
    
    read -p "TX Power dBm (2-20) [$POWER]: " new_power
    POWER=${new_power:-$POWER}
    
    read -p "Node ID [$NODE_ID]: " new_id
    NODE_ID=${new_id:-$NODE_ID}
    
    # Save configuration
    cat > "$CONFIG_FILE" <<EOF
FREQ=$FREQ
SF=$SF
BW=$BW
POWER=$POWER
SYNC_WORD=$SYNC_WORD
NODE_ID="$NODE_ID"
EOF
    
    echo -e "${GREEN}Configuration saved${NC}"
}

# Install dependencies
install_deps() {
    echo -e "${YELLOW}Installing LoRa dependencies...${NC}"
    
    # Python packages
    pip3 install --user spidev RPi.GPIO
    
    # Enable SPI
    if [ ! -e /dev/spidev0.0 ]; then
        echo "Enabling SPI..."
        sudo raspi-config nonint do_spi 0
        echo -e "${YELLOW}Please reboot for SPI to take effect${NC}"
    fi
    
    # Create Python helper
    create_python_helper
    
    echo -e "${GREEN}Dependencies installed${NC}"
}

# Main loop
main() {
    init
    
    while true; do
        show_menu
        
        case $choice in
            1) detect_lora_module ;;
            2) 
                read -p "Number of pings [10]: " count
                lora_ping "NODE_B" ${count:-10} 1
                ;;
            3)
                read -p "File path: " filepath
                lora_send_file "$filepath"
                ;;
            4)
                echo "Starting file receiver..."
                python3 "$PYTHON_HELPER" receive \
                    --freq $FREQ --sf $SF --bw $BW
                ;;
            5)
                read -p "Start freq [902]: " start
                read -p "End freq [928]: " end
                lora_spectrum_scan ${start:-902} ${end:-928} 1
                ;;
            6) lora_range_test tx ;;
            7) lora_range_test rx ;;
            8) configure_menu ;;
            9) install_deps ;;
            0) exit 0 ;;
            *) echo -e "${RED}Invalid option${NC}" ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

# Run if executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
```

---

## Elixir LoRa Implementation

### Elixir SPI Library for LoRa

```elixir
# lib/lora.ex
defmodule LoRa do
  @moduledoc """
  LoRa communication library for Elixir
  Uses Circuits.SPI for hardware communication
  """
  
  use GenServer
  alias Circuits.{SPI, GPIO}
  require Logger
  
  # Register addresses
  @reg_fifo 0x00
  @reg_op_mode 0x01
  @reg_freq_msb 0x06
  @reg_freq_mid 0x07
  @reg_freq_lsb 0x08
  @reg_pa_config 0x09
  @reg_fifo_addr_ptr 0x0D
  @reg_fifo_tx_base 0x0E
  @reg_fifo_rx_base 0x0F
  @reg_irq_flags 0x12
  @reg_rx_nb_bytes 0x13
  @reg_pkt_rssi_value 0x1A
  @reg_modem_config_1 0x1D
  @reg_modem_config_2 0x1E
  @reg_sync_word 0x39
  
  # Operating modes
  @mode_sleep 0x00
  @mode_standby 0x01
  @mode_tx 0x03
  @mode_rx_cont 0x05
  
  defstruct [:spi, :gpio_reset, :gpio_dio0, :config]
  
  # Client API
  
  def start_link(opts \\ []) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end
  
  def configure(params) do
    GenServer.call(__MODULE__, {:configure, params})
  end
  
  def send_packet(data) do
    GenServer.call(__MODULE__, {:send, data})
  end
  
  def receive_packet(timeout \\ 1000) do
    GenServer.call(__MODULE__, {:receive, timeout})
  end
  
  def ping(target, count \\ 10) do
    GenServer.call(__MODULE__, {:ping, target, count}, count * 3000)
  end
  
  # Server Callbacks
  
  @impl true
  def init(opts) do
    # Open SPI
    {:ok, spi} = SPI.open("spidev0.0", 
      speed_hz: 5_000_000,
      mode: 0,
      bits_per_word: 8
    )
    
    # Setup GPIO pins
    {:ok, gpio_reset} = GPIO.open(25, :output)
    {:ok, gpio_dio0} = GPIO.open(4, :input)
    
    # Default config
    config = %{
      freq: Keyword.get(opts, :freq, 915.0),
      sf: Keyword.get(opts, :sf, 7),
      bw: Keyword.get(opts, :bw, 125),
      power: Keyword.get(opts, :power, 20),
      sync_word: Keyword.get(opts, :sync_word, 0x12)
    }
    
    state = %__MODULE__{
      spi: spi,
      gpio_reset: gpio_reset,
      gpio_dio0: gpio_dio0,
      config: config
    }
    
    # Reset and configure
    reset_module(state)
    configure_radio(state)
    
    {:ok, state}
  end
  
  @impl true
  def handle_call({:configure, params}, _from, state) do
    new_config = Map.merge(state.config, params)
    new_state = %{state | config: new_config}
    configure_radio(new_state)
    {:reply, :ok, new_state}
  end
  
  @impl true
  def handle_call({:send, data}, _from, state) do
    result = do_send_packet(state, data)
    {:reply, result, state}
  end
  
  @impl true
  def handle_call({:receive, timeout}, _from, state) do
    result = do_receive_packet(state, timeout)
    {:reply, result, state}
  end
  
  @impl true
  def handle_call({:ping, target, count}, _from, state) do
    results = do_ping_test(state, target, count)
    {:reply, results, state}
  end
  
  # Private functions
  
  defp reset_module(state) do
    GPIO.write(state.gpio_reset, 0)
    :timer.sleep(10)
    GPIO.write(state.gpio_reset, 1)
    :timer.sleep(100)
  end
  
  defp write_register(state, addr, value) do
    SPI.transfer(state.spi, <<addr ||| 0x80, value>>)
  end
  
  defp read_register(state, addr) do
    <<_addr, value>> = SPI.transfer(state.spi, <<addr &&& 0x7F, 0x00>>)
    value
  end
  
  defp configure_radio(state) do
    %{freq: freq, sf: sf, bw: bw, power: power, sync_word: sync} = state.config
    
    # Sleep mode
    write_register(state, @reg_op_mode, @mode_sleep ||| 0x80)
    
    # Set frequency
    freq_reg = trunc(freq * 65536 / 32)
    write_register(state, @reg_freq_msb, freq_reg >>> 16 &&& 0xFF)
    write_register(state, @reg_freq_mid, freq_reg >>> 8 &&& 0xFF)
    write_register(state, @reg_freq_lsb, freq_reg &&& 0xFF)
    
    # Set power
    write_register(state, @reg_pa_config, 0x80 ||| power)
    
    # Set SF, BW, CR
    bw_val = case bw do
      125 -> 0x70
      250 -> 0x80
      500 -> 0x90
      _ -> 0x70
    end
    
    write_register(state, @reg_modem_config_1, bw_val ||| 0x02)  # BW + CR 4/6
    write_register(state, @reg_modem_config_2, sf <<< 4 ||| 0x04)  # SF + CRC on
    
    # Set sync word
    write_register(state, @reg_sync_word, sync)
    
    # Set FIFO pointers
    write_register(state, @reg_fifo_tx_base, 0x00)
    write_register(state, @reg_fifo_rx_base, 0x00)
    
    Logger.info("LoRa configured: #{freq}MHz SF#{sf} BW#{bw}kHz Power#{power}dBm")
  end
  
  defp do_send_packet(state, data) when is_binary(data) do
    # Standby mode
    write_register(state, @reg_op_mode, @mode_standby ||| 0x80)
    
    # Reset FIFO pointer
    write_register(state, @reg_fifo_addr_ptr, 0x00)
    
    # Write payload
    payload = :binary.bin_to_list(data)
    Enum.each(payload, fn byte ->
      write_register(state, @reg_fifo, byte)
    end)
    
    # Set payload length
    write_register(state, 0x22, length(payload))
    
    # TX mode
    write_register(state, @reg_op_mode, @mode_tx ||| 0x80)
    
    # Wait for TX done (poll DIO0 or IRQ flag)
    wait_tx_done(state, 5000)
  end
  
  defp wait_tx_done(state, timeout) when timeout > 0 do
    case GPIO.read(state.gpio_dio0) do
      1 ->
        # Clear IRQ
        write_register(state, @reg_irq_flags, 0xFF)
        {:ok, :sent}
      0 ->
        :timer.sleep(10)
        wait_tx_done(state, timeout - 10)
    end
  end
  defp wait_tx_done(_state, _timeout), do: {:error, :timeout}
  
  defp do_receive_packet(state, timeout) do
    # RX continuous mode
    write_register(state, @reg_op_mode, @mode_rx_cont ||| 0x80)
    
    # Wait for packet
    wait_rx_done(state, timeout)
  end
  
  defp wait_rx_done(state, timeout) when timeout > 0 do
    case GPIO.read(state.gpio_dio0) do
      1 ->
        # Read packet
        length = read_register(state, @reg_rx_nb_bytes)
        
        # Reset FIFO pointer
        write_register(state, @reg_fifo_addr_ptr, 0x00)
        
        # Read payload
        payload = for _ <- 1..length do
          read_register(state, @reg_fifo)
        end
        
        # Get RSSI
        rssi = read_register(state, @reg_pkt_rssi_value) - 137
        
        # Clear IRQ
        write_register(state, @reg_irq_flags, 0xFF)
        
        {:ok, %{
          data: :binary.list_to_bin(payload),
          rssi: rssi,
          length: length
        }}
      0 ->
        :timer.sleep(10)
        wait_rx_done(state, timeout - 10)
    end
  end
  defp wait_rx_done(_state, _timeout), do: {:error, :timeout}
  
  defp do_ping_test(state, target, count) do
    node_id = "NODE_A"
    
    Enum.map(1..count, fn seq ->
      timestamp = System.system_time(:millisecond)
      ping_data = "PING:#{node_id}:#{target}:#{seq}:#{timestamp}"
      
      case do_send_packet(state, ping_data) do
        {:ok, :sent} ->
          case do_receive_packet(state, 2000) do
            {:ok, packet} ->
              rtt = System.system_time(:millisecond) - timestamp
              Logger.info("[#{seq}] Reply: RTT=#{rtt}ms RSSI=#{packet.rssi}dBm")
              {:ok, %{seq: seq, rtt: rtt, rssi: packet.rssi}}
            {:error, :timeout} ->
              Logger.warn("[#{seq}] Timeout")
              {:error, :timeout}
          end
        error ->
          Logger.error("[#{seq}] Send failed: #{inspect(error)}")
          error
      end
    end)
    |> summarize_ping_results(count)
  end
  
  defp summarize_ping_results(results, total) do
    successful = Enum.filter(results, &match?({:ok, _}, &1))
    received = length(successful)
    lost = total - received
    
    stats = if received > 0 do
      rtts = Enum.map(successful, fn {:ok, r} -> r.rtt end)
      rssis = Enum.map(successful, fn {:ok, r} -> r.rssi end)
      
      %{
        min_rtt: Enum.min(rtts),
        max_rtt: Enum.max(rtts),
        avg_rtt: Enum.sum(rtts) / received,
        avg_rssi: Enum.sum(rssis) / received
      }
    else
      %{}
    end
    
    Map.merge(stats, %{
      sent: total,
      received: received,
      lost: lost,
      loss_percent: lost / total * 100
    })
  end
end
```

### Elixir Mix Task for Testing

```elixir
# lib/mix/tasks/lora.ex
defmodule Mix.Tasks.Lora do
  use Mix.Task
  
  @shortdoc "LoRa communication tasks"
  
  @moduledoc """
  LoRa testing tasks
  
  ## Examples
  
      mix lora.ping --target NODE_B --count 10
      mix lora.send --file /path/to/file
      mix lora.receive
      mix lora.spectrum --start 902 --end 928
  """
  
  def run(args) do
    Application.ensure_all_started(:circuits_spi)
    Application.ensure_all_started(:circuits_gpio)
    
    {opts, _, _} = OptionParser.parse(args,
      switches: [
        freq: :float,
        sf: :integer,
        bw: :integer,
        power: :integer,
        target: :string,
        count: :integer,
        file: :string,
        start: :integer,
        stop: :integer
      ]
    )
    
    # Start LoRa GenServer
    {:ok, _pid} = LoRa.start_link(opts)
    
    case List.first(args) do
      "ping" -> do_ping(opts)
      "send" -> do_send(opts)
      "receive" -> do_receive(opts)
      "spectrum" -> do_spectrum(opts)
      _ -> IO.puts("Unknown command. Use: ping, send, receive, spectrum")
    end
  end
  
  defp do_ping(opts) do
    target = Keyword.get(opts, :target, "NODE_B")
    count = Keyword.get(opts, :count, 10)
    
    IO.puts("Starting ping to #{target}...")
    results = LoRa.ping(target, count)
    
    IO.puts("\n--- Ping Statistics ---")
    IO.puts("Packets: Sent = #{results.sent}, Received = #{results.received}")
    IO.puts("Packet loss: #{Float.round(results.loss_percent, 1)}%")
    
    if results[:avg_rtt] do
      IO.puts("RTT min/avg/max = #{results.min_rtt}/#{Float.round(results.avg_rtt, 1)}/#{results.max_rtt} ms")
      IO.puts("Average RSSI: #{Float.round(results.avg_rssi, 1)} dBm")
    end
  end
  
  defp do_send(opts) do
    case Keyword.get(opts, :file) do
      nil ->
        IO.puts("Sending test packet...")
        LoRa.send_packet("Hello from Elixir LoRa!")
      
      filepath ->
        send_file(filepath)
    end
  end
  
  defp send_file(filepath) do
    case File.read(filepath) do
      {:ok, content} ->
        chunks = chunk_binary(content, 200)
        total = length(chunks)
        
        IO.puts("Sending file: #{filepath}")
        IO.puts("Size: #{byte_size(content)} bytes")
        IO.puts("Chunks: #{total}")
        
        # Send file info
        info = "FILE:INFO:#{Path.basename(filepath)}:#{byte_size(content)}:#{total}"
        LoRa.send_packet(info)
        
        # Send chunks
        Enum.with_index(chunks)
        |> Enum.each(fn {chunk, index} ->
          data = "FILE:DATA:#{index}:#{Base.encode64(chunk)}"
          LoRa.send_packet(data)
          
          progress = Float.round((index + 1) / total * 100, 1)
          IO.write("\rProgress: #{progress}%")
        end)
        
        IO.puts("\n✓ File sent")
        
      {:error, reason} ->
        IO.puts("Error reading file: #{reason}")
    end
  end
  
  defp chunk_binary(binary, chunk_size) do
    do_chunk_binary(binary, chunk_size, [])
  end
  
  defp do_chunk_binary(<<>>, _size, acc), do: Enum.reverse(acc)
  defp do_chunk_binary(binary, size, acc) do
    {chunk, rest} = 
      case binary do
        <<chunk::binary-size(size), rest::binary>> -> {chunk, rest}
        small -> {small, <<>>}
      end
    do_chunk_binary(rest, size, [chunk | acc])
  end
  
  defp do_receive(_opts) do
    IO.puts("Listening for packets... (Ctrl+C to stop)")
    receive_loop()
  end
  
  defp receive_loop() do
    case LoRa.receive_packet(10_000) do
      {:ok, packet} ->
        IO.puts("RX: #{packet.data} (RSSI: #{packet.rssi} dBm)")
        receive_loop()
      
      {:error, :timeout} ->
        receive_loop()
    end
  end
  
  defp do_spectrum(opts) do
    start_freq = Keyword.get(opts, :start, 902)
    stop_freq = Keyword.get(opts, :stop, 928)
    
    IO.puts("Scanning #{start_freq}-#{stop_freq} MHz...")
    
    results = 
      start_freq..stop_freq
      |> Enum.map(fn freq ->
        LoRa.configure(%{freq: freq})
        {:ok, packet} = LoRa.receive_packet(100)
        rssi = packet[:rssi] || -120
        
        bar = String.duplicate("█", max(0, div(rssi + 120, 2)))
        IO.puts("#{freq} MHz: #{rssi} dBm #{bar}")
        
        {freq, rssi}
      end)
    
    {clear_freq, clear_rssi} = Enum.min_by(results, fn {_f, r} -> r end)
    IO.puts("\nClearest: #{clear_freq} MHz at #{clear_rssi} dBm")
  end
end
```

---

## Manual Testing Commands

### Direct SPI Testing

```bash
# Test SPI communication directly
# Read LoRa version register (should return 0x12 for SX1276)

# Using spi-tools (install: apt install spi-tools)
spi-config -d /dev/spidev0.0 -m 0 -s 5000000
echo -n -e '\x42\x00' | spi-pipe -d /dev/spidev0.0 -b 2 | hexdump -C

# Using Python one-liner
python3 -c "
import spidev
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 5000000
version = spi.xfer2([0x42, 0x00])[1]
print(f'Version: 0x{version:02X}')
spi.close()
"

# Using dd (raw but works)
echo -n -e '\x42\x00' | sudo dd of=/dev/spidev0.0 bs=2 count=1
sudo dd if=/dev/spidev0.0 bs=2 count=1 | hexdump -C
```

### GPIO Testing

```bash
# Test GPIO pins for LoRa module

# Export pins
echo 25 > /sys/class/gpio/export  # Reset pin
echo 4 > /sys/class/gpio/export   # DIO0 pin

# Set directions
echo out > /sys/class/gpio/gpio25/direction
echo in > /sys/class/gpio/gpio4/direction

# Reset module
echo 0 > /sys/class/gpio/gpio25/value
sleep 0.1
echo 1 > /sys/class/gpio/gpio25/value

# Read DIO0 state
cat /sys/class/gpio/gpio4/value

# Cleanup
echo 25 > /sys/class/gpio/unexport
echo 4 > /sys/class/gpio/unexport
```

### Continuous Monitoring

```bash
#!/bin/bash
# monitor_lora.sh - Monitor LoRa communication in real-time

monitor_rssi() {
    echo "Monitoring RSSI levels..."
    while true; do
        rssi=$(python3 -c "
import spidev
spi = spidev.SpiDev()
spi.open(0, 0)
spi.xfer2([0x81, 0x05])  # RX mode
rssi = spi.xfer2([0x1B, 0x00])[1] - 137
print(rssi)
spi.close()
" 2>/dev/null)
        
        printf "\rRSSI: %4d dBm  " "$rssi"
        
        # Visual indicator
        if [ "$rssi" -gt -50 ]; then
            echo -n "████████ Excellent"
        elif [ "$rssi" -gt -80 ]; then
            echo -n "██████   Good     "
        elif [ "$rssi" -gt -100 ]; then
            echo -n "████     Fair     "
        else
            echo -n "██       Poor     "
        fi
        
        sleep 0.5
    done
}

monitor_packets() {
    echo "Monitoring packets..."
    python3 - <<'EOF'
import spidev
import time

spi = spidev.SpiDev()
spi.open(0, 0)

# Configure for RX
spi.xfer2([0x81, 0x05])  # RX continuous

while True:
    # Check for RX done flag
    irq = spi.xfer2([0x12, 0x00])[1]
    
    if irq & 0x40:  # RX done
        # Read packet
        length = spi.xfer2([0x13, 0x00])[1]
        rssi = spi.xfer2([0x1A, 0x00])[1] - 137
        
        payload = []
        for i in range(length):
            payload.append(spi.xfer2([0x00, 0x00])[1])
        
        try:
            data = bytes(payload).decode('utf-8')
            print(f"[{time.strftime('%H:%M:%S')}] RX: {data} (RSSI: {rssi} dBm)")
        except:
            print(f"[{time.strftime('%H:%M:%S')}] RX: {length} bytes (RSSI: {rssi} dBm)")
        
        # Clear IRQ
        spi.xfer2([0x92, 0xFF])
    
    time.sleep(0.1)

spi.close()
EOF
}

# Main
case "${1:-rssi}" in
    rssi) monitor_rssi ;;
    packets) monitor_packets ;;
    *) echo "Usage: $0 {rssi|packets}" ;;
esac
```

---

## File Transfer Protocol

### Simple Protocol Implementation

```bash
#!/bin/bash
# lora_file_transfer.sh - File transfer over LoRa

CHUNK_SIZE=200
RETRY_COUNT=3

send_file() {
    local file="$1"
    local dest="${2:-NODE_B}"
    
    if [ ! -f "$file" ]; then
        echo "File not found: $file"
        return 1
    fi
    
    local filename=$(basename "$file")
    local filesize=$(stat -c%s "$file")
    local md5sum=$(md5sum "$file" | cut -d' ' -f1)
    
    echo "Sending: $filename ($filesize bytes)"
    echo "MD5: $md5sum"
    
    # Protocol:
    # 1. START:<filename>:<size>:<md5>:<chunks>
    # 2. DATA:<chunk_num>:<total>:<base64_data>
    # 3. END:<filename>:<md5>
    
    # Calculate chunks
    local chunks=$(( (filesize + CHUNK_SIZE - 1) / CHUNK_SIZE ))
    
    # Send start packet
    send_packet "START:$filename:$filesize:$md5sum:$chunks"
    
    # Send data chunks
    local offset=0
    local chunk_num=0
    
    while [ $offset -lt $filesize ]; do
        # Extract chunk
        local chunk=$(dd if="$file" bs=1 skip=$offset count=$CHUNK_SIZE 2>/dev/null | base64 -w0)
        
        # Send with retry
        local retry=0
        while [ $retry -lt $RETRY_COUNT ]; do
            if send_packet "DATA:$chunk_num:$chunks:$chunk"; then
                break
            fi
            retry=$((retry + 1))
            echo "Retry $retry/$RETRY_COUNT for chunk $chunk_num"
        done
        
        chunk_num=$((chunk_num + 1))
        offset=$((offset + CHUNK_SIZE))
        
        # Progress
        local progress=$(echo "scale=1; 100 * $chunk_num / $chunks" | bc)
        echo -ne "\rProgress: $progress% [$chunk_num/$chunks]"
    done
    
    echo ""
    
    # Send end packet
    send_packet "END:$filename:$md5sum"
    
    echo "✓ Transfer complete"
}

receive_file() {
    local save_dir="${1:-./received}"
    mkdir -p "$save_dir"
    
    echo "Waiting for file transfer..."
    
    local state="IDLE"
    local filename=""
    local filesize=0
    local expected_md5=""
    local chunks=0
    local received_chunks=""
    
    while true; do
        local packet=$(receive_packet)
        
        if [[ "$packet" =~ ^START:(.+):(.+):(.+):(.+) ]]; then
            filename="${BASH_REMATCH[1]}"
            filesize="${BASH_REMATCH[2]}"
            expected_md5="${BASH_REMATCH[3]}"
            chunks="${BASH_REMATCH[4]}"
            
            echo "Receiving: $filename ($filesize bytes, $chunks chunks)"
            state="RECEIVING"
            received_chunks=""
            
            # Create temp file
            > "$save_dir/$filename.tmp"
            
        elif [[ "$packet" =~ ^DATA:(.+):(.+):(.+) ]] && [ "$state" = "RECEIVING" ]; then
            local chunk_num="${BASH_REMATCH[1]}"
            local total="${BASH_REMATCH[2]}"
            local data="${BASH_REMATCH[3]}"
            
            # Decode and append
            echo "$data" | base64 -d >> "$save_dir/$filename.tmp"
            
            received_chunks="$received_chunks $chunk_num"
            local received_count=$(echo "$received_chunks" | wc -w)
            
            # Progress
            local progress=$(echo "scale=1; 100 * $received_count / $chunks" | bc)
            echo -ne "\rProgress: $progress% [$received_count/$chunks]"
            
        elif [[ "$packet" =~ ^END:(.+):(.+) ]] && [ "$state" = "RECEIVING" ]; then
            echo ""
            
            # Verify MD5
            local actual_md5=$(md5sum "$save_dir/$filename.tmp" | cut -d' ' -f1)
            
            if [ "$actual_md5" = "$expected_md5" ]; then
                mv "$save_dir/$filename.tmp" "$save_dir/$filename"
                echo "✓ File saved: $save_dir/$filename"
                echo "✓ MD5 verified: $actual_md5"
            else
                echo "✗ MD5 mismatch!"
                echo "  Expected: $expected_md5"
                echo "  Actual: $actual_md5"
                rm "$save_dir/$filename.tmp"
            fi
            
            state="IDLE"
        fi
    done
}

# Helper functions (implement based on your LoRa library)
send_packet() {
    local data="$1"
    # Implementation depends on your LoRa interface
    python3 -c "
from lora_helper import LoRa
lora = LoRa()
lora.send('$data')
"
}

receive_packet() {
    # Implementation depends on your LoRa interface
    python3 -c "
from lora_helper import LoRa
lora = LoRa()
packet = lora.receive(timeout=10)
if packet:
    print(packet['data'])
"
}

# Main
case "${1:-}" in
    send)
        send_file "$2" "$3"
        ;;
    receive)
        receive_file "$2"
        ;;
    *)
        echo "Usage:"
        echo "  $0 send <file> [destination]"
        echo "  $0 receive [save_directory]"
        ;;
esac
```

---

## Advanced Configurations

### Adaptive Data Rate

```bash
#!/bin/bash
# adaptive_lora.sh - Automatically adjust parameters based on link quality

adapt_parameters() {
    local rssi=$1
    local packet_loss=$2
    
    # Current parameters
    local sf=${SF:-7}
    local bw=${BW:-125}
    
    echo "Current: SF$sf BW${bw}kHz"
    echo "Link: RSSI=${rssi}dBm Loss=${packet_loss}%"
    
    # Adaptation logic
    if [ "$packet_loss" -gt 20 ]; then
        # High loss - increase robustness
        if [ $sf -lt 12 ]; then
            sf=$((sf + 1))
            echo "→ Increasing to SF$sf for better reliability"
        elif [ $bw -gt 125 ]; then
            bw=$((bw / 2))
            echo "→ Decreasing to BW${bw}kHz for better sensitivity"
        fi
    elif [ "$packet_loss" -lt 5 ] && [ "$rssi" -gt -80 ]; then
        # Good link - increase speed
        if [ $sf -gt 7 ]; then
            sf=$((sf - 1))
            echo "→ Decreasing to SF$sf for higher speed"
        elif [ $bw -lt 500 ]; then
            bw=$((bw * 2))
            echo "→ Increasing to BW${bw}kHz for higher speed"
        fi
    fi
    
    # Apply new parameters
    export SF=$sf
    export BW=$bw
    
    # Reconfigure
    python3 -c "
from lora_helper import LoRa
lora = LoRa()
lora.configure(sf=$sf, bw=$bw)
print('Applied new configuration')
"
}

# Continuous adaptation loop
while true; do
    # Run ping test
    result=$(./lora_test.sh ping 10)
    
    # Extract metrics
    rssi=$(echo "$result" | grep "Average RSSI" | awk '{print $3}')
    loss=$(echo "$result" | grep "loss" | grep -o '[0-9.]*%' | tr -d '%')
    
    # Adapt if needed
    adapt_parameters "$rssi" "$loss"
    
    sleep 30
done
```

### Frequency Hopping

```bash
#!/bin/bash
# frequency_hopping.sh - FHSS implementation

# Define hop sequence (must be same on both devices)
HOP_SEQUENCE=(915.0 915.5 916.0 916.5 917.0 917.5 918.0 918.5)
HOP_INTERVAL=1  # seconds
CURRENT_HOP=0

get_next_frequency() {
    CURRENT_HOP=$(( (CURRENT_HOP + 1) % ${#HOP_SEQUENCE[@]} ))
    echo "${HOP_SEQUENCE[$CURRENT_HOP]}"
}

synchronized_hopping() {
    # Synchronize based on system time
    local epoch=$(date +%s)
    local hop_index=$((epoch / HOP_INTERVAL % ${#HOP_SEQUENCE[@]}))
    echo "${HOP_SEQUENCE[$hop_index]}"
}

# Transmit with hopping
transmit_with_fhss() {
    local message="$1"
    
    while true; do
        local freq=$(synchronized_hopping)
        
        echo "Hopping to ${freq} MHz"
        
        python3 -c "
from lora_helper import LoRa
lora = LoRa()
lora.configure(freq=$freq)
lora.send('$message')
"
        
        sleep $HOP_INTERVAL
    done
}

# Receive with hopping
receive_with_fhss() {
    while true; do
        local freq=$(synchronized_hopping)
        
        echo "Listening on ${freq} MHz"
        
        python3 -c "
from lora_helper import LoRa
lora = LoRa()
lora.configure(freq=$freq)
packet = lora.receive(timeout=$HOP_INTERVAL)
if packet:
    print(f\"RX on {freq} MHz: {packet['data']}\")
"
    done
}

# Main
case "$1" in
    tx) transmit_with_fhss "$2" ;;
    rx) receive_with_fhss ;;
    *) echo "Usage: $0 {tx|rx} [message]" ;;
esac
```

### Listen Before Talk (LBT)

```bash
#!/bin/bash
# lbt_lora.sh - Implement carrier sense for collision avoidance

check_channel_clear() {
    local threshold=${1:--100}  # dBm
    
    # Sample RSSI multiple times
    local samples=10
    local clear_count=0
    
    for ((i=0; i<samples; i++)); do
        rssi=$(python3 -c "
from lora_helper import LoRa
lora = LoRa()
print(lora.get_rssi())
")
        
        if [ "$rssi" -lt "$threshold" ]; then
            clear_count=$((clear_count + 1))
        fi
        
        sleep 0.01
    done
    
    # Channel is clear if 80% of samples are below threshold
    if [ $clear_count -gt $((samples * 8 / 10)) ]; then
        return 0  # Clear
    else
        return 1  # Busy
    fi
}

transmit_with_lbt() {
    local data="$1"
    local max_retries=5
    local backoff=100  # ms
    
    for ((retry=0; retry<max_retries; retry++)); do
        echo "Checking channel..."
        
        if check_channel_clear; then
            echo "Channel clear, transmitting..."
            send_packet "$data"
            return 0
        else
            echo "Channel busy, backing off..."
            sleep $(echo "scale=3; $backoff * $((RANDOM % 10)) / 1000" | bc)
            backoff=$((backoff * 2))  # Exponential backoff
        fi
    done
    
    echo "Failed to find clear channel after $max_retries attempts"
    return 1
}
```

---

## Troubleshooting Reference

### Common Issues and Solutions

```bash
# Diagnostic script
#!/bin/bash
# diagnose_lora.sh - Comprehensive LoRa troubleshooting

run_diagnostics() {
    echo "=== LoRa Diagnostics ==="
    echo "Date: $(date)"
    echo ""
    
    # 1. Check SPI interface
    echo "1. SPI Interface:"
    if [ -e /dev/spidev0.0 ]; then
        echo "   ✓ /dev/spidev0.0 exists"
        ls -l /dev/spidev0.* 2>/dev/null
    else
        echo "   ✗ SPI not found"
        echo "   → Enable with: sudo raspi-config"
    fi
    echo ""
    
    # 2. Check GPIO access
    echo "2. GPIO Access:"
    if [ -d /sys/class/gpio ]; then
        echo "   ✓ GPIO sysfs available"
    else
        echo "   ✗ GPIO not accessible"
    fi
    echo ""
    
    # 3. Check Python modules
    echo "3. Python Dependencies:"
    for module in spidev RPi.GPIO; do
        if python3 -c "import $module" 2>/dev/null; then
            echo "   ✓ $module installed"
        else
            echo "   ✗ $module missing"
            echo "   → Install with: pip3 install $module"
        fi
    done
    echo ""
    
    # 4. Check LoRa module
    echo "4. LoRa Module Detection:"
    python3 -c "
import spidev
import RPi.GPIO as GPIO
import time

try:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(25, GPIO.OUT)
    GPIO.output(25, 0)
    time.sleep(0.01)
    GPIO.output(25, 1)
    time.sleep(0.1)
    
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 5000000
    
    version = spi.xfer2([0x42, 0x00])[1]
    
    if version == 0x12:
        print('   ✓ SX127x detected (version 0x{:02X})'.format(version))
    else:
        print('   ? Unknown chip (version 0x{:02X})'.format(version))
    
    spi.close()
    GPIO.cleanup()
except Exception as e:
    print('   ✗ Error: {}'.format(e))
" 2>&1
    echo ""
    
    # 5. Power check
    echo "5. Power Supply:"
    if [ -f /sys/class/power_supply/BAT0/voltage_now ]; then
        voltage=$(cat /sys/class/power_supply/BAT0/voltage_now)
        voltage_v=$(echo "scale=2; $voltage / 1000000" | bc)
        echo "   Battery voltage: ${voltage_v}V"
    fi
    
    # Check 3.3V rail if possible
    echo "   Note: LoRa modules require stable 3.3V supply"
    echo ""
    
    # 6. Interference check
    echo "6. Potential Interference:"
    echo "   WiFi 2.4GHz: $(iwlist wlan0 freq 2>/dev/null | grep -c "2.4")"
    echo "   Bluetooth: $(hciconfig 2>/dev/null | grep -c "UP")"
    echo ""
    
    # 7. Module temperature (if sensor available)
    echo "7. System Temperature:"
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        temp=$(cat /sys/class/thermal/thermal_zone0/temp)
        temp_c=$(echo "scale=1; $temp / 1000" | bc)
        echo "   CPU: ${temp_c}°C"
        
        if (( $(echo "$temp_c > 70" | bc -l) )); then
            echo "   ⚠ High temperature may affect performance"
        fi
    fi
    echo ""
    
    # 8. Wiring check reminder
    echo "8. Wiring Checklist:"
    echo "   □ VIN → 3.3V (Pin 1)"
    echo "   □ GND → GND (Pin 6)"
    echo "   □ SCK → GPIO11 (Pin 23)"
    echo "   □ MISO → GPIO9 (Pin 21)"
    echo "   □ MOSI → GPIO10 (Pin 19)"
    echo "   □ NSS → GPIO8 (Pin 24)"
    echo "   □ RST → GPIO25 (Pin 22)"
    echo "   □ DIO0 → GPIO4 (Pin 7)"
    echo "   □ Antenna connected"
    echo ""
    
    # 9. Recommendations
    echo "9. Recommendations:"
    
    # Check for common issues
    if ! [ -e /dev/spidev0.0 ]; then
        echo "   → Enable SPI interface first"
    fi
    
    if ! python3 -c "import spidev" 2>/dev/null; then
        echo "   → Install Python SPI library"
    fi
    
    echo "   → Use SF7-9 for testing (balance of speed/range)"
    echo "   → Start with high TX power (20dBm) for initial tests"
    echo "   → Ensure antennas are vertical and unobstructed"
    echo "   → Keep modules >1m apart for close-range testing"
}

# Performance test
performance_test() {
    echo "=== LoRa Performance Test ==="
    
    for sf in 7 8 9 10 11 12; do
        echo ""
        echo "Testing SF$sf..."
        
        # Calculate theoretical metrics
        datarate=$(echo "scale=2; $sf * 125 / 2^$sf * 1.25" | bc)
        airtime=$(echo "scale=1; (8 + 4.25 * $sf) * 2^$sf / 125" | bc)
        
        echo "  Theoretical data rate: ${datarate} kbps"
        echo "  Air time (20 bytes): ${airtime} ms"
        
        # Run actual test
        python3 -c "
from lora_helper import LoRa
import time

lora = LoRa()
lora.configure(sf=$sf)

# Send test packet
start = time.time()
lora.send('X' * 20)
duration = (time.time() - start) * 1000

print(f'  Actual air time: {duration:.1f} ms')
"
    done
}

# Main menu
echo "LoRa Diagnostic Tool"
echo "===================="
echo "1) Run full diagnostics"
echo "2) Performance test"
echo "3) Monitor mode"
echo ""
read -p "Select option: " choice

case $choice in
    1) run_diagnostics ;;
    2) performance_test ;;
    3) ./monitor_lora.sh ;;
    *) echo "Invalid option" ;;
esac
```

---

## Quick Reference Card

```bash
# LoRa Quick Reference
# ====================

# Frequencies by Region
US: 902-928 MHz
EU: 863-870 MHz
AS: 923 MHz
AU: 915-928 MHz

# Spreading Factors (Time vs Range)
SF7:  Fastest, shortest range    (~5.5 kbps)
SF9:  Balanced                   (~1.8 kbps)
SF12: Slowest, longest range     (~0.2 kbps)

# Bandwidth Options
125 kHz: Best range (standard)
250 kHz: Balanced
500 kHz: Highest speed

# Typical Ranges
Urban:    2-5 km
Rural:    10-15 km
Line-of-sight: 20+ km

# Power Consumption
Sleep:    0.2 µA
Receive:  10 mA
Transmit: 20-120 mA (depends on power)

# Quick Commands
Detect:   ./lora_test.sh detect
Ping:     ./lora_test.sh ping 10
Send:     ./lora_test.sh send file.txt
Receive:  ./lora_test.sh receive
Spectrum: ./lora_test.sh spectrum 902 928

# Optimization Tips
- For max range: SF12, BW125, Power20
- For max speed: SF7, BW500, Power20
- For battery: SF7-9, BW125, Power14
- For interference: Use frequency hopping
- For reliability: Add retransmissions and ACKs
```

This comprehensive guide provides everything you need for LoRa testing with focus on bash scripting and Elixir support, moving away from Python-centric examples while still maintaining compatibility where needed.
