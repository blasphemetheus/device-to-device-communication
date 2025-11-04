#!/usr/bin/env bash

# bluetooth_laptop.sh - Simple Bluetooth PAN script for Manjaro Laptop
# This acts as the PANU (PAN User) client

CLIENT_IP="192.168.44.2/24"
PI_MAC="${2:-}"  # Pass Pi MAC as second argument

start_panu() {
    if [ -z "$PI_MAC" ]; then
        echo "Error: Please provide Raspberry Pi MAC address"
        echo "Usage: $0 start XX:XX:XX:XX:XX:XX"
        exit 1
    fi
    
    echo "Starting Bluetooth PANU on Laptop..."
    echo "Connecting to Pi at $PI_MAC"
    
    # Enable Bluetooth
    sudo systemctl start bluetooth
    sudo bluetoothctl power on
    
    # Connect to Pi
    sudo bluetoothctl connect "$PI_MAC"
    
    # Wait for interface
    sleep 3
    
    # Find bnep interface
    BNEP_IF=$(ip link show | grep -o 'bnep[0-9]' | head -1)
    
    if [ -z "$BNEP_IF" ]; then
        echo "Trying alternative connection method..."
        
        # Try bt-network if available
        if command -v bt-network &> /dev/null; then
            sudo bt-network -c "$PI_MAC" nap &
            sleep 3
            BNEP_IF=$(ip link show | grep -o 'bnep[0-9]' | head -1)
        fi
    fi
    
    if [ -z "$BNEP_IF" ]; then
        echo "Error: Failed to create network interface"
        echo "Make sure:"
        echo "  1. Pi is running NAP server"
        echo "  2. Devices are paired"
        echo "  3. bnep module is loaded (sudo modprobe bnep)"
        exit 1
    fi
    
    # Configure interface
    sudo ip link set "$BNEP_IF" up
    sudo ip addr add "$CLIENT_IP" dev "$BNEP_IF" 2>/dev/null || echo "IP exists"
    
    echo "=========================================="
    echo "Laptop PANU Client Connected!"
    echo "Interface: $BNEP_IF"
    echo "IP Address: 192.168.44.2"
    echo "=========================================="
    echo "Testing connection to Pi..."
    
    ping -c 3 -W 2 192.168.44.1
}

stop_panu() {
    echo "Stopping Bluetooth PANU..."
    
    # Kill bt-network if running
    sudo pkill -f bt-network 2>/dev/null
    
    # Find and remove bnep interfaces
    for iface in $(ip link show | grep -o 'bnep[0-9]'); do
        sudo ip link set "$iface" down
        sudo ip link delete "$iface" 2>/dev/null || true
    done
    
    # Disconnect
    sudo bluetoothctl disconnect
    
    echo "PANU stopped"
}

test_connection() {
    echo "Testing connection to Pi (192.168.44.1)..."
    ping -c 4 -W 2 192.168.44.1
}

status() {
    echo "=== Bluetooth Status ==="
    bluetoothctl show | grep -E "Powered|Discoverable"
    echo ""
    echo "=== Paired Devices ==="
    bluetoothctl paired-devices
    echo ""
    echo "=== Network Interfaces ==="
    for iface in $(ip link show | grep -o 'bnep[0-9]'); do
        echo "Interface: $iface"
        ip addr show "$iface" | grep inet
    done
    echo ""
    echo "=== Connection Status ==="
    bluetoothctl info "$PI_MAC" 2>/dev/null | grep -E "Device|Connected" || echo "Not connected"
}

pair_with_pi() {
    echo "Starting pairing process..."
    echo "Make sure Pi is discoverable!"
    
    sudo bluetoothctl << EOF
power on
agent on
default-agent
scan on
EOF
    
    echo "Scanning for 10 seconds..."
    sleep 10
    
    sudo bluetoothctl scan off
    
    echo "Found devices:"
    sudo bluetoothctl devices
    
    if [ -n "$PI_MAC" ]; then
        echo "Pairing with $PI_MAC..."
        sudo bluetoothctl pair "$PI_MAC"
        sudo bluetoothctl trust "$PI_MAC"
    else
        echo "Run again with: $0 pair XX:XX:XX:XX:XX:XX"
    fi
}

case "${1:-}" in
    start)
        start_panu
        ;;
    stop)
        stop_panu
        ;;
    test)
        test_connection
        ;;
    status)
        status
        ;;
    pair)
        pair_with_pi
        ;;
    *)
        echo "Usage: $0 {start|stop|test|status|pair} [pi_mac_address]"
        echo ""
        echo "Examples:"
        echo "  $0 pair                   # Scan and show devices"
        echo "  $0 pair XX:XX:XX:XX:XX:XX   # Pair with specific Pi"
        echo "  $0 start XX:XX:XX:XX:XX:XX  # Connect to Pi NAP"
        echo "  $0 test                   # Test connection to Pi"
        echo "  $0 status                 # Show current status"
        echo "  $0 stop                   # Disconnect"
        exit 1
        ;;
esac
