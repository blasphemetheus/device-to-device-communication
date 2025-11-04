#!/usr/bin/env bash

# bluetooth_pi.sh - Simple Bluetooth PAN script for Raspberry Pi
# This acts as the NAP (Network Access Point) server

BRIDGE_IP="192.168.44.1/24"
BRIDGE_NAME="pan0"
LAPTOP_MAC="${1:-}"  # Pass laptop MAC as first argument

start_nap() {
    echo "Starting Bluetooth NAP on Raspberry Pi..."
    
    # Enable Bluetooth
    sudo systemctl start bluetooth
    sudo bluetoothctl power on
    
    # Create bridge
    sudo brctl addbr "$BRIDGE_NAME" 2>/dev/null || echo "Bridge exists"
    sudo ip link set "$BRIDGE_NAME" up
    sudo ip addr add "$BRIDGE_IP" dev "$BRIDGE_NAME" 2>/dev/null || echo "IP exists"
    
    # Enable forwarding
    echo 1 | sudo tee /proc/sys/net/ipv4/ip_forward > /dev/null
    
    # Make discoverable
    sudo bluetoothctl discoverable on
    
    # Start NAP service (try multiple methods)
    if command -v bt-network &> /dev/null; then
        sudo pkill -f bt-network 2>/dev/null
        sudo bt-network -s nap "$BRIDGE_NAME" &
        echo "NAP started with bt-network"
    else
        # Alternative method
        sudo sdptool add NAP 2>/dev/null
        sudo hciconfig hci0 lm master,accept
        echo "NAP configured manually"
    fi
    
    echo "=========================================="
    echo "Raspberry Pi NAP Server Ready!"
    echo "IP Address: 192.168.44.1"
    echo "Bridge: $BRIDGE_NAME"
    echo "=========================================="
    echo "Run 'sudo ./bluetooth_laptop.sh start <PI_MAC>' on the laptop"
    
    if [ -n "$LAPTOP_MAC" ]; then
        echo "Waiting for laptop ($LAPTOP_MAC) to connect..."
    fi
}

stop_nap() {
    echo "Stopping Bluetooth NAP..."
    
    # Kill NAP service
    sudo pkill -f bt-network 2>/dev/null
    
    # Remove bridge
    sudo ip link set "$BRIDGE_NAME" down 2>/dev/null
    sudo brctl delbr "$BRIDGE_NAME" 2>/dev/null
    
    # Disconnect
    sudo bluetoothctl disconnect
    
    echo "NAP stopped"
}

test_connection() {
    echo "Testing connection to laptop (192.168.44.2)..."
    ping -c 4 -W 2 192.168.44.2
}

status() {
    echo "=== Bluetooth Status ==="
    bluetoothctl show | grep -E "Powered|Discoverable"
    echo ""
    echo "=== Paired Devices ==="
    bluetoothctl paired-devices
    echo ""
    echo "=== Network Interfaces ==="
    ip addr show "$BRIDGE_NAME" 2>/dev/null || echo "Bridge not found"
    echo ""
    echo "=== Connected Devices ==="
    bluetoothctl devices Connected
}

case "${1:-start}" in
    start)
        start_nap
        ;;
    stop)
        stop_nap
        ;;
    test)
        test_connection
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|test|status} [laptop_mac]"
        echo ""
        echo "Examples:"
        echo "  $0 start                  # Start NAP server"
        echo "  $0 start AA:BB:CC:DD:EE:FF  # Start and wait for specific laptop"
        echo "  $0 test                   # Test connection to laptop"
        echo "  $0 status                 # Show current status"
        echo "  $0 stop                   # Stop NAP server"
        exit 1
        ;;
esac
