#!/usr/bin/env bash

# Bluetooth PAN (Personal Area Network) Setup Script
# Works on both Manjaro (pacman) and Raspberry Pi (apt-based) systems
# Supports NAP (Network Access Point) and PANU (PAN User) roles

set -e

# Configuration
BRIDGE_NAME="pan0"
BRIDGE_IP_NAP="192.168.44.1/24"
PANU_IP="192.168.44.2/24"
SCRIPT_NAME=$(basename "$0")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Detect package manager
detect_distro() {
    if command -v pacman &> /dev/null; then
        echo "arch"
    elif command -v apt &> /dev/null; then
        echo "debian"
    else
        log_error "Unsupported distribution"
        exit 1
    fi
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run with sudo"
        exit 1
    fi
}

# Install required packages based on distro
install_dependencies() {
    local distro=$1
    log_info "Checking dependencies for $distro..."
    
    if [ "$distro" = "arch" ]; then
        # Manjaro/Arch packages
        local packages="bluez bluez-utils bridge-utils"
        for pkg in $packages; do
            if ! pacman -Qi "$pkg" &> /dev/null; then
                log_info "Installing $pkg..."
                pacman -S --noconfirm "$pkg"
            fi
        done
    elif [ "$distro" = "debian" ]; then
        # Raspberry Pi/Debian packages
        local packages="bluez bluez-tools bridge-utils"
        for pkg in $packages; do
            if ! dpkg -l "$pkg" &> /dev/null; then
                log_info "Installing $pkg..."
                apt-get update && apt-get install -y "$pkg"
            fi
        done
    fi
}

# Enable required services
enable_services() {
    log_info "Enabling Bluetooth services..."
    systemctl enable bluetooth
    systemctl start bluetooth
    
    # Enable compatibility mode for older devices
    if ! grep -q "^Enable=Source,Sink,Media,Socket" /etc/bluetooth/main.conf 2>/dev/null; then
        log_info "Configuring Bluetooth for PAN support..."
        if [ -f /etc/bluetooth/main.conf ]; then
            cp /etc/bluetooth/main.conf /etc/bluetooth/main.conf.bak
        fi
        cat >> /etc/bluetooth/main.conf << EOF

[General]
Enable=Source,Sink,Media,Socket
Class=0x000100
DiscoverableTimeout=0
PairableTimeout=0

[Policy]
AutoEnable=true
EOF
    fi
    
    systemctl restart bluetooth
    sleep 2
}

# Get Bluetooth adapter info
get_bt_adapter() {
    local adapter=$(bluetoothctl list | head -n1 | awk '{print $2}')
    if [ -z "$adapter" ]; then
        log_error "No Bluetooth adapter found"
        exit 1
    fi
    echo "$adapter"
}

# Setup NAP (Network Access Point) - typically on Pi
setup_nap() {
    local bt_mac=$1
    local target_mac=$2
    
    log_info "Setting up NAP (Network Access Point)..."
    
    # Create bridge interface
    log_info "Creating bridge interface $BRIDGE_NAME..."
    brctl addbr "$BRIDGE_NAME" 2>/dev/null || {
        log_warn "Bridge $BRIDGE_NAME already exists"
    }
    
    # Configure bridge
    ip link set "$BRIDGE_NAME" up
    ip addr add "$BRIDGE_IP_NAP" dev "$BRIDGE_NAME" 2>/dev/null || {
        log_warn "IP already assigned to $BRIDGE_NAME"
    }
    
    # Enable IP forwarding
    echo 1 > /proc/sys/net/ipv4/ip_forward
    
    # Setup iptables for NAT (optional, for internet sharing)
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || true
    iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE 2>/dev/null || true
    
    # Start bluetooth-nap service
    log_info "Starting NAP service..."
    
    # Kill existing bt-network if running
    pkill -f "bt-network" 2>/dev/null || true
    
    # Start NAP server (using bluetoothd's built-in NAP)
    if command -v bt-network &> /dev/null; then
        bt-network -s nap "$BRIDGE_NAME" &
        log_info "NAP service started with bt-network"
    else
        # Alternative: use bluetoothd directly
        log_info "Configuring NAP through bluetoothctl..."
        bluetoothctl << EOF
power on
discoverable on
agent on
default-agent
EOF
    fi
    
    log_info "NAP setup complete. Bridge IP: $BRIDGE_IP_NAP"
    log_info "Make sure to pair and trust the client device"
}

# Setup PANU (PAN User) - typically on laptop
setup_panu() {
    local target_mac=$1
    
    log_info "Setting up PANU (PAN User/Client)..."
    
    # Ensure Bluetooth is powered on
    bluetoothctl power on
    
    # Connect to NAP
    log_info "Connecting to NAP at $target_mac..."
    
    # First, ensure device is paired and trusted
    bluetoothctl << EOF
agent on
default-agent
scan on
EOF
    
    sleep 5
    
    bluetoothctl << EOF
scan off
pair $target_mac
trust $target_mac
EOF
    
    # Connect using PAN profile
    log_info "Establishing PAN connection..."
    
    # Method 1: Using bt-network if available
    if command -v bt-network &> /dev/null; then
        bt-network -c "$target_mac" nap &
        sleep 3
    fi
    
    # Method 2: Using bluetoothctl connect
    bluetoothctl connect "$target_mac"
    sleep 2
    
    # Find the network interface created (usually bnep0)
    local pan_iface=$(ip link show | grep -o 'bnep[0-9]' | head -n1)
    
    if [ -z "$pan_iface" ]; then
        log_error "Failed to create PAN interface"
        log_info "Trying alternative connection method..."
        
        # Alternative: manual bnep connection
        modprobe bnep
        echo "c $target_mac" > /sys/kernel/debug/bluetooth/6lowpan_control 2>/dev/null || true
        sleep 2
        pan_iface=$(ip link show | grep -o 'bnep[0-9]' | head -n1)
    fi
    
    if [ -n "$pan_iface" ]; then
        log_info "PAN interface $pan_iface created"
        
        # Configure IP
        ip link set "$pan_iface" up
        ip addr add "$PANU_IP" dev "$pan_iface" 2>/dev/null || {
            log_warn "IP already assigned to $pan_iface"
        }
        
        log_info "PANU setup complete. Interface: $pan_iface, IP: $PANU_IP"
    else
        log_error "Could not establish PAN connection"
        return 1
    fi
}

# Test connection
test_connection() {
    local role=$1
    local target_ip=$2
    
    log_info "Testing connection..."
    
    if [ "$role" = "nap" ]; then
        target_ip=${target_ip:-"192.168.44.2"}
    else
        target_ip=${target_ip:-"192.168.44.1"}
    fi
    
    # Show network interfaces
    log_info "Network interfaces:"
    ip addr show | grep -E "bnep|pan0" | grep -A2 -B1 "state UP"
    
    # Test ping
    log_info "Pinging $target_ip..."
    if ping -c 3 -W 2 "$target_ip"; then
        log_info "Connection successful!"
        return 0
    else
        log_warn "Ping failed. Connection may not be established yet."
        return 1
    fi
}

# Stop Bluetooth PAN
stop_pan() {
    log_info "Stopping Bluetooth PAN..."
    
    # Kill bt-network processes
    pkill -f "bt-network" 2>/dev/null || true
    
    # Remove bridge
    if ip link show "$BRIDGE_NAME" &> /dev/null; then
        ip link set "$BRIDGE_NAME" down
        brctl delbr "$BRIDGE_NAME" 2>/dev/null || true
    fi
    
    # Remove bnep interfaces
    for iface in $(ip link show | grep -o 'bnep[0-9]'); do
        ip link set "$iface" down
        ip link delete "$iface" 2>/dev/null || true
    done
    
    # Disconnect Bluetooth devices
    bluetoothctl disconnect
    
    # Clear iptables rules
    iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || true
    iptables -t nat -D POSTROUTING -o wlan0 -j MASQUERADE 2>/dev/null || true
    
    log_info "Bluetooth PAN stopped"
}

# Show current status
show_status() {
    log_info "Bluetooth PAN Status:"
    echo "------------------------"
    
    # Show Bluetooth adapter
    echo "Bluetooth Adapter:"
    bluetoothctl show | grep -E "Controller|Powered|Discoverable"
    echo ""
    
    # Show paired devices
    echo "Paired Devices:"
    bluetoothctl paired-devices
    echo ""
    
    # Show connected devices
    echo "Connected Devices:"
    bluetoothctl devices Connected
    echo ""
    
    # Show network interfaces
    echo "PAN Network Interfaces:"
    ip addr show | grep -E "bnep|pan0" -A3
    echo ""
    
    # Show routing
    echo "Routing Table:"
    ip route | grep -E "192.168.44|bnep|pan0"
}

# Manual pairing helper
pair_devices() {
    log_info "Starting interactive pairing..."
    log_info "Make sure both devices are discoverable"
    
    bluetoothctl << EOF
power on
agent on
default-agent
discoverable on
pairable on
scan on
EOF
    
    log_info "Scanning for 10 seconds..."
    sleep 10
    
    bluetoothctl scan off
    
    log_info "Available devices:"
    bluetoothctl devices
    
    read -p "Enter the MAC address of the device to pair with: " target_mac
    
    bluetoothctl << EOF
pair $target_mac
trust $target_mac
EOF
    
    log_info "Pairing complete"
}

# Main menu
usage() {
    cat << EOF
Usage: sudo $SCRIPT_NAME <command> [options]

Commands:
    install                 Install dependencies
    start-nap <client-mac>  Start as NAP server (typically on Pi)
    start-panu <nap-mac>    Start as PAN client (typically on laptop)
    stop                    Stop Bluetooth PAN
    status                  Show current status
    pair                    Interactive pairing helper
    test [target-ip]        Test connection with ping
    
Examples:
    # On Raspberry Pi (NAP server):
    sudo $SCRIPT_NAME install
    sudo $SCRIPT_NAME pair
    sudo $SCRIPT_NAME start-nap AA:BB:CC:DD:EE:FF
    
    # On Laptop (PAN client):
    sudo $SCRIPT_NAME install
    sudo $SCRIPT_NAME pair
    sudo $SCRIPT_NAME start-panu 11:22:33:44:55:66
    
    # Test connection:
    sudo $SCRIPT_NAME test
    
    # Check status:
    sudo $SCRIPT_NAME status
    
    # Stop connection:
    sudo $SCRIPT_NAME stop

Note: MAC addresses can be found using 'bluetoothctl devices' after pairing
EOF
    exit 0
}

# Main execution
main() {
    check_root
    
    case "${1:-}" in
        install)
            distro=$(detect_distro)
            install_dependencies "$distro"
            enable_services
            log_info "Installation complete"
            ;;
        start-nap)
            if [ -z "${2:-}" ]; then
                log_error "Please provide client MAC address"
                usage
            fi
            bt_mac=$(get_bt_adapter)
            setup_nap "$bt_mac" "$2"
            ;;
        start-panu)
            if [ -z "${2:-}" ]; then
                log_error "Please provide NAP server MAC address"
                usage
            fi
            setup_panu "$2"
            ;;
        stop)
            stop_pan
            ;;
        status)
            show_status
            ;;
        pair)
            pair_devices
            ;;
        test)
            # Detect role based on network config
            if ip addr show | grep -q "$BRIDGE_IP_NAP"; then
                test_connection "nap" "${2:-}"
            else
                test_connection "panu" "${2:-}"
            fi
            ;;
        *)
            usage
            ;;
    esac
}

# Run main function
main "$@"
