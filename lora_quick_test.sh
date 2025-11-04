#!/usr/bin/env bash

# lora_quick_test.sh - Quick LoRa testing script
# Makes it easy to test LoRa communication between two devices

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LORA_SCRIPT="${SCRIPT_DIR}/lora_test.py"

# Functions
print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}        LoRa Communication Test Suite${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}\n"
}

print_menu() {
    echo -e "${GREEN}Select Test Mode:${NC}"
    echo ""
    echo "  1) Detect LoRa Module"
    echo "  2) Quick Ping Test (Device A → Device B)"
    echo "  3) Quick Ping Test (Device B → Device A)"
    echo "  4) Continuous Ping Monitor"
    echo "  5) Send File"
    echo "  6) Receive File"
    echo "  7) Spectrum Scanner"
    echo "  8) Range Test"
    echo "  9) Install Dependencies"
    echo "  0) Exit"
    echo ""
}

install_dependencies() {
    echo -e "${YELLOW}Installing LoRa dependencies...${NC}"
    
    # Detect system type
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu/Raspberry Pi
        echo "Detected Debian-based system"
        sudo apt-get update
        sudo apt-get install -y python3-pip python3-dev python3-spidev python3-rpi.gpio git
        
    elif command -v pacman &> /dev/null; then
        # Arch/Manjaro
        echo "Detected Arch-based system"
        sudo pacman -S --needed python-pip python-spidev python-raspberry-gpio git
        
    else
        echo -e "${RED}Unsupported system. Please install manually.${NC}"
        exit 1
    fi
    
    # Install Python packages
    echo "Installing Python packages..."
    pip3 install --user spidev RPi.GPIO
    
    # Clone and install pyLoRa
    if [ ! -d "/tmp/pySX127x" ]; then
        echo "Downloading LoRa library..."
        git clone https://github.com/rpsreal/pySX127x /tmp/pySX127x
        cd /tmp/pySX127x
        pip3 install --user -e .
        cd -
    fi
    
    # Enable SPI
    echo -e "${YELLOW}Enabling SPI interface...${NC}"
    if [ -f /boot/config.txt ]; then
        if ! grep -q "^dtparam=spi=on" /boot/config.txt; then
            echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
            echo -e "${YELLOW}SPI enabled. Please reboot for changes to take effect.${NC}"
        fi
    fi
    
    echo -e "${GREEN}✓ Dependencies installed successfully!${NC}"
}

detect_module() {
    echo -e "${YELLOW}Detecting LoRa module...${NC}\n"
    python3 "$LORA_SCRIPT" detect
}

quick_ping_a() {
    echo -e "${GREEN}Starting Device A (Ping Sender)${NC}"
    echo -e "${YELLOW}Make sure Device B is running in respond mode!${NC}\n"
    
    read -p "Number of pings [10]: " count
    count=${count:-10}
    
    read -p "Interval in seconds [1.0]: " interval
    interval=${interval:-1.0}
    
    read -p "Frequency in MHz [915.0]: " freq
    freq=${freq:-915.0}
    
    python3 "$LORA_SCRIPT" --freq "$freq" --node NODE_A ping send \
        --target NODE_B --count "$count" --interval "$interval"
}

quick_ping_b() {
    echo -e "${GREEN}Starting Device B (Ping Responder)${NC}"
    echo -e "${YELLOW}Waiting for pings from Device A...${NC}\n"
    
    read -p "Frequency in MHz [915.0]: " freq
    freq=${freq:-915.0}
    
    python3 "$LORA_SCRIPT" --freq "$freq" --node NODE_B ping respond
}

continuous_monitor() {
    echo -e "${GREEN}Continuous Ping Monitor${NC}"
    echo "This will run continuous ping tests with statistics"
    echo ""
    
    read -p "Run as [A]sender or [B]responder? " mode
    read -p "Frequency in MHz [915.0]: " freq
    freq=${freq:-915.0}
    
    if [[ "$mode" =~ ^[Aa]$ ]]; then
        while true; do
            python3 "$LORA_SCRIPT" --freq "$freq" --node NODE_A ping send \
                --count 100 --interval 0.5
            echo -e "\n${YELLOW}Restarting in 5 seconds...${NC}"
            sleep 5
        done
    else
        python3 "$LORA_SCRIPT" --freq "$freq" --node NODE_B ping respond
    fi
}

send_file() {
    echo -e "${GREEN}File Transfer - Sender${NC}\n"
    
    read -p "File to send: " filepath
    if [ ! -f "$filepath" ]; then
        echo -e "${RED}File not found: $filepath${NC}"
        return 1
    fi
    
    read -p "Frequency in MHz [915.0]: " freq
    freq=${freq:-915.0}
    
    read -p "Spreading Factor (7-12) [7]: " sf
    sf=${sf:-7}
    
    echo -e "${YELLOW}Starting file transfer...${NC}"
    python3 "$LORA_SCRIPT" --freq "$freq" --sf "$sf" --node NODE_A \
        file send "$filepath" --dest NODE_B
}

receive_file() {
    echo -e "${GREEN}File Transfer - Receiver${NC}\n"
    
    read -p "Save directory [./received]: " savedir
    savedir=${savedir:-./received}
    
    read -p "Frequency in MHz [915.0]: " freq
    freq=${freq:-915.0}
    
    read -p "Spreading Factor (7-12) [7]: " sf
    sf=${sf:-7}
    
    echo -e "${YELLOW}Waiting for file transfer...${NC}"
    python3 "$LORA_SCRIPT" --freq "$freq" --sf "$sf" --node NODE_B \
        file receive --dir "$savedir"
}

spectrum_scan() {
    echo -e "${GREEN}Spectrum Scanner${NC}"
    echo "Scan for interference and find clear channels"
    echo ""
    
    read -p "Start frequency MHz [902]: " start
    start=${start:-902}
    
    read -p "End frequency MHz [928]: " end
    end=${end:-928}
    
    read -p "Step size MHz [1.0]: " step
    step=${step:-1.0}
    
    python3 "$LORA_SCRIPT" spectrum --start "$start" --end "$end" --step "$step"
}

range_test() {
    echo -e "${GREEN}Range Test Mode${NC}"
    echo "Test maximum communication range"
    echo ""
    echo "Configuration for range testing:"
    echo "  • SF12 for maximum range (slow)"
    echo "  • SF10 for balanced range/speed"
    echo "  • SF7 for high speed (short range)"
    echo ""
    
    read -p "Run as [A]sender or [B]responder? " mode
    
    read -p "Frequency in MHz [915.0]: " freq
    freq=${freq:-915.0}
    
    read -p "Spreading Factor (7-12) [10]: " sf
    sf=${sf:-10}
    
    read -p "TX Power dBm (2-20) [20]: " power
    power=${power:-20}
    
    if [[ "$mode" =~ ^[Aa]$ ]]; then
        echo -e "\n${YELLOW}Range Test - Sender${NC}"
        echo "Move away from receiver while monitoring signal"
        echo ""
        python3 "$LORA_SCRIPT" --freq "$freq" --sf "$sf" --power "$power" \
            --node NODE_A ping send --count 1000 --interval 2
    else
        echo -e "\n${YELLOW}Range Test - Responder${NC}"
        echo "Signal strength will be displayed for each ping"
        echo ""
        python3 "$LORA_SCRIPT" --freq "$freq" --sf "$sf" --power "$power" \
            --node NODE_B ping respond
    fi
}

# Check for Python script
if [ ! -f "$LORA_SCRIPT" ]; then
    echo -e "${RED}Error: lora_test.py not found in $SCRIPT_DIR${NC}"
    echo "Please ensure lora_test.py is in the same directory as this script"
    exit 1
fi

# Main loop
print_header

while true; do
    print_menu
    read -p "Select option: " choice
    
    case $choice in
        1)
            detect_module
            ;;
        2)
            quick_ping_a
            ;;
        3)
            quick_ping_b
            ;;
        4)
            continuous_monitor
            ;;
        5)
            send_file
            ;;
        6)
            receive_file
            ;;
        7)
            spectrum_scan
            ;;
        8)
            range_test
            ;;
        9)
            install_dependencies
            ;;
        0)
            echo -e "${GREEN}Exiting...${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
    clear
    print_header
done
