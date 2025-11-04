# Bluetooth PAN Connection Testing Guide
## Manual Commands for Manjaro Laptop ↔ Raspberry Pi

This guide provides step-by-step manual commands to establish a Bluetooth PAN (Personal Area Network) connection between your Manjaro laptop and Raspberry Pi.

---

## Prerequisites

### On Manjaro (Laptop):
```bash
# Install required packages
sudo pacman -S bluez bluez-utils bluez-tools bridge-utils

# Enable Bluetooth service
sudo systemctl enable --now bluetooth
```

### On Raspberry Pi:
```bash
# Install required packages
sudo apt update
sudo apt install bluez bluez-tools bridge-utils

# Enable Bluetooth service
sudo systemctl enable --now bluetooth
```

---

## Method 1: NAP (Network Access Point) Setup

### Step 1: Initial Pairing (Run on BOTH devices)

```bash
# Start bluetoothctl interactive mode
sudo bluetoothctl

# Inside bluetoothctl:
power on
agent on
default-agent
discoverable on
pairable on
scan on

# Wait 10 seconds, note the MAC address of the other device
scan off

# Pair with the other device (replace XX:XX:XX:XX:XX:XX with actual MAC)
pair XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX

# Exit bluetoothctl
exit
```

### Step 2: Set up NAP on Raspberry Pi

```bash
# Get your Bluetooth MAC address
hciconfig hci0 | grep "BD Address"

# Create and configure bridge interface
sudo brctl addbr pan0
sudo ip link set pan0 up
sudo ip addr add 192.168.44.1/24 dev pan0

# Enable IP forwarding
sudo sysctl net.ipv4.ip_forward=1

# Optional: Enable NAT for internet sharing
sudo iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE
sudo iptables -A FORWARD -i pan0 -j ACCEPT

# Start NAP server (choose one method):

# Method A: Using bt-network (if available)
sudo bt-network -s nap pan0 &

# Method B: Using systemd service
sudo systemctl start bluetooth-nap

# Method C: Manual with bluez
sudo hciconfig hci0 lm master,accept
sudo hciconfig hci0 class 0x020300
```

### Step 3: Connect from Laptop as PANU

```bash
# Get the Pi's MAC address (if not already known)
bluetoothctl devices

# Connect to the Pi's NAP service
# Method A: Using bt-network
sudo bt-network -c XX:XX:XX:XX:XX:XX nap

# Method B: Using bluetoothctl and manual setup
sudo bluetoothctl connect XX:XX:XX:XX:XX:XX

# Check if bnep0 interface was created
ip link show | grep bnep

# Configure the bnep0 interface
sudo ip link set bnep0 up
sudo ip addr add 192.168.44.2/24 dev bnep0

# Add route if needed
sudo ip route add 192.168.44.0/24 dev bnep0
```

---

## Method 2: Direct BNEP Connection (Alternative)

### On Raspberry Pi:
```bash
# Load kernel module
sudo modprobe bnep

# Configure Bluetooth for PAN
echo "Enable=Source,Sink,Media,Socket" | sudo tee -a /etc/bluetooth/main.conf
sudo systemctl restart bluetooth

# Create PAN connection listener
sudo sdptool add NAP
sudo hciconfig hci0 piscan
```

### On Laptop:
```bash
# Load kernel module
sudo modprobe bnep

# Create connection
sudo pand --connect XX:XX:XX:XX:XX:XX --service NAP --master --persist

# Configure interface
sudo ifconfig bnep0 192.168.44.2 netmask 255.255.255.0 up
```

---

## Testing Commands

### Basic Connectivity Test:
```bash
# Show all network interfaces
ip addr show

# Show only PAN-related interfaces
ip addr show | grep -E "bnep|pan0"

# Test ping from laptop to Pi
ping -c 4 192.168.44.1

# Test ping from Pi to laptop
ping -c 4 192.168.44.2

# Check Bluetooth connection status
bluetoothctl info XX:XX:XX:XX:XX:XX

# Monitor Bluetooth traffic
sudo hcidump -i hci0
```

### File Transfer Test:
```bash
# Using netcat for simple file transfer
# On Pi (receiver):
nc -l -p 8888 > received_file.txt

# On Laptop (sender):
echo "Test data" | nc 192.168.44.1 8888

# Using SCP (if SSH is installed)
scp test_file.txt pi@192.168.44.1:/home/pi/

# Using Python HTTP server for browsing
# On Pi:
python3 -m http.server 8000 --bind 192.168.44.1

# On Laptop:
curl http://192.168.44.1:8000/
```

---

## Troubleshooting Commands

### Debug Bluetooth Issues:
```bash
# Check Bluetooth service status
sudo systemctl status bluetooth

# Check kernel messages
sudo dmesg | grep -i bluetooth

# Check Bluetooth controller
hciconfig -a

# Reset Bluetooth controller
sudo hciconfig hci0 reset

# Check if PAN profile is available
sdptool browse local | grep -A 10 "NAP"

# List all Bluetooth services
sdptool browse XX:XX:XX:XX:XX:XX

# Monitor D-Bus messages
sudo dbus-monitor --system | grep bluetooth
```

### Network Debugging:
```bash
# Check routing table
ip route show

# Check ARP table
arp -a

# Trace route
traceroute 192.168.44.1

# Check interface statistics
ip -s link show bnep0

# Monitor network traffic
sudo tcpdump -i bnep0 -n

# Check iptables rules
sudo iptables -L -n -v
```

---

## Quick Connection Scripts

### quick_connect_pi.sh (for Raspberry Pi)
```bash
#!/bin/bash
# Quick NAP setup for Pi

LAPTOP_MAC="XX:XX:XX:XX:XX:XX"  # Replace with laptop's MAC

sudo bluetoothctl power on
sudo brctl addbr pan0 2>/dev/null || true
sudo ip link set pan0 up
sudo ip addr add 192.168.44.1/24 dev pan0 2>/dev/null || true
sudo bt-network -s nap pan0 &

echo "NAP started. Waiting for connection from $LAPTOP_MAC"
echo "Pi IP: 192.168.44.1"
```

### quick_connect_laptop.sh (for Laptop)
```bash
#!/bin/bash
# Quick PANU setup for Laptop

PI_MAC="YY:YY:YY:YY:YY:YY"  # Replace with Pi's MAC

sudo bluetoothctl power on
sudo bluetoothctl connect $PI_MAC
sleep 3

IFACE=$(ip link show | grep -o 'bnep[0-9]' | head -1)
if [ -n "$IFACE" ]; then
    sudo ip link set $IFACE up
    sudo ip addr add 192.168.44.2/24 dev $IFACE 2>/dev/null || true
    echo "Connected on $IFACE with IP 192.168.44.2"
    ping -c 3 192.168.44.1
else
    echo "Failed to create interface"
fi
```

---

## Persistent Configuration

### /etc/bluetooth/main.conf additions:
```ini
[General]
Enable=Source,Sink,Media,Socket
Class=0x020300
DiscoverableTimeout=0
PairableTimeout=0

[Policy]
AutoEnable=true
```

### systemd service for auto-connection:
Create `/etc/systemd/system/bluetooth-pan.service`:
```ini
[Unit]
Description=Bluetooth PAN Auto Connection
After=bluetooth.service
Requires=bluetooth.service

[Service]
Type=simple
ExecStart=/usr/local/bin/bluetooth_pan.sh start-nap XX:XX:XX:XX:XX:XX
ExecStop=/usr/local/bin/bluetooth_pan.sh stop
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

## Alternative: Using BlueZ D-Bus API

```python
#!/usr/bin/env python3
# test_pan_connection.py

import dbus
import time

bus = dbus.SystemBus()

# Get the Bluetooth adapter
adapter_path = "/org/bluez/hci0"
adapter = dbus.Interface(
    bus.get_object("org.bluez", adapter_path),
    "org.bluez.Adapter1"
)

# Power on
adapter.Set("org.bluez.Adapter1", "Powered", True)
adapter.Set("org.bluez.Adapter1", "Discoverable", True)

# Find device
device_path = f"{adapter_path}/dev_XX_XX_XX_XX_XX_XX"  # Replace XX
device = dbus.Interface(
    bus.get_object("org.bluez", device_path),
    "org.bluez.Device1"
)

# Connect
network = dbus.Interface(
    bus.get_object("org.bluez", device_path),
    "org.bluez.Network1"
)

try:
    # Connect as PANU to NAP
    interface = network.Connect("nap")
    print(f"Connected! Interface: {interface}")
except Exception as e:
    print(f"Connection failed: {e}")
```

---

## Notes

1. **MAC Address Format**: In bluetoothctl use colons (AA:BB:CC:DD:EE:FF), in file paths use underscores (AA_BB_CC_DD_EE_FF)

2. **Common Issues**:
   - If bnep0 doesn't appear, check if the bnep kernel module is loaded
   - If connection drops, check power management settings
   - Some devices need Legacy Pairing enabled

3. **Security**: For production use, implement proper authentication and encryption

4. **Performance**: Bluetooth PAN typically provides 1-3 Mbps throughput

5. **Power Management**: Disable Bluetooth sleep mode for stable connections:
   ```bash
   sudo hciconfig hci0 noscan
   sudo hciconfig hci0 -a
   ```
