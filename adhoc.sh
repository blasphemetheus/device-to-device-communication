#!/usr/bin/env bash

# This script makes creating or joining an ad-hoc WiFi network (IBSS) easier
# It can also shut down an ad-hoc network

# Usage:
#    sudo ./adhoc.sh start pi
#    sudo ./adhoc.sh start laptop
#    sudo ./adhoc.sh start pi --timeout 300
#    sudo ./adhoc.sh stop

SSID="PiAdhoc"
FREQ=2437  # channel 6 (2.437 GHz)
PIDFILE="/tmp/adhoc_timeout.pid"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run with sudo" >&2
  exit 1
fi

# Check for required commands
for cmd in iw ip systemctl; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "Error: Required command '$cmd' not found" >&2
    exit 1
  fi
done

# Detect WiFi interface (take first one if multiple)
IFACE=$(iw dev | awk '$1=="Interface"{print $2}' | head -n1)

if [ -z "$IFACE" ]; then
  echo "Error: No WiFi interface detected" >&2
  exit 1
fi

ACTION="${1:-}"
ROLE="${2:-}"

# Optional timeout section (seconds)
TIMEOUT=0
if [[ "${3:-}" == "--timeout" && -n "${4:-}" ]]; then
  TIMEOUT=$4
  if ! [[ "$TIMEOUT" =~ ^[0-9]+$ ]] || [ "$TIMEOUT" -le 0 ]; then
    echo "Error: Timeout must be a positive integer" >&2
    exit 1
  fi
fi

# Default IPs
PI_IP="192.168.12.1/24"
LAPTOP_IP="192.168.12.2/24"

# Function to cleanup on error
cleanup() {
  echo "Cleaning up..." >&2
  ip addr flush dev "$IFACE" 2>/dev/null || true
  ip link set "$IFACE" down 2>/dev/null || true
  iw dev "$IFACE" set type managed 2>/dev/null || true
  ip link set "$IFACE" up 2>/dev/null || true
  if ! systemctl is-active --quiet NetworkManager 2>/dev/null; then
    systemctl start NetworkManager 2>/dev/null || true
  fi
}

if [ "$ACTION" = "start" ]; then
  # Check if already in IBSS mode
  if iw dev "$IFACE" info 2>/dev/null | grep -q "type ibss"; then
    echo "Warning: Interface $IFACE is already in IBSS mode" >&2
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      exit 1
    fi
  fi

  # Set up cleanup trap
  trap cleanup ERR

  if [ "$TIMEOUT" -gt 0 ]; then
    echo "Will stop ad-hoc mode automatically in $TIMEOUT seconds..."
    SCRIPT_PATH=$(realpath "$0")
    nohup bash -c "sleep $TIMEOUT && '$SCRIPT_PATH' stop" >/dev/null 2>&1 &
    echo $! > "$PIDFILE"
    echo "Timeout PID saved to $PIDFILE (kill it to cancel auto-stop)"
  fi

  echo "Using the interface: $IFACE"
  
  # Stop NetworkManager if it's running
  if systemctl is-active --quiet NetworkManager 2>/dev/null; then
    echo "Stopping NetworkManager..."
    systemctl stop NetworkManager || {
      echo "Warning: Failed to stop NetworkManager" >&2
    }
  else
    echo "NetworkManager is not running, skipping..."
  fi

  echo "Setting up ad-hoc network: SSID=$SSID FREQ=$FREQ"
  
  # Bring up ad-hoc network
  ip link set "$IFACE" down || {
    echo "Error: Failed to bring interface down" >&2
    exit 1
  }
  
  iw dev "$IFACE" set type ibss || {
    echo "Error: Failed to set interface type to IBSS" >&2
    exit 1
  }
  
  ip link set "$IFACE" up || {
    echo "Error: Failed to bring interface up" >&2
    exit 1
  }
  
  iw dev "$IFACE" ibss join "$SSID" "$FREQ" || {
    echo "Error: Failed to join IBSS network" >&2
    exit 1
  }

  if [ "$ROLE" = "pi" ]; then
    ip addr add "$PI_IP" dev "$IFACE" || {
      echo "Error: Failed to assign IP address" >&2
      exit 1
    }
    echo "Raspberry Pi Ad-hoc network '$SSID' started on $IFACE with IP $PI_IP"
  elif [ "$ROLE" = "laptop" ]; then
    ip addr add "$LAPTOP_IP" dev "$IFACE" || {
      echo "Error: Failed to assign IP address" >&2
      exit 1
    }
    echo "Laptop ad-hoc network '$SSID' started on $IFACE with IP $LAPTOP_IP"
  else
    echo "Error: Please specify 'pi' or 'laptop' after 'start'" >&2
    echo "Example: sudo ./adhoc.sh start pi" >&2
    exit 1
  fi

  # Remove cleanup trap on success
  trap - ERR

  echo "You can now ping the other device."

elif [ "$ACTION" = "stop" ]; then
  # Cancel timeout if running
  if [ -f "$PIDFILE" ]; then
    TIMEOUT_PID=$(cat "$PIDFILE" 2>/dev/null || echo "")
    if [ -n "$TIMEOUT_PID" ] && kill -0 "$TIMEOUT_PID" 2>/dev/null; then
      echo "Cancelling auto-stop timeout..."
      kill "$TIMEOUT_PID" 2>/dev/null || true
    fi
    rm -f "$PIDFILE"
  fi

  echo "Restoring managed mode on $IFACE"
  ip addr flush dev "$IFACE" 2>/dev/null || true
  ip link set "$IFACE" down 2>/dev/null || true
  iw dev "$IFACE" set type managed 2>/dev/null || {
    echo "Warning: Failed to set interface type to managed" >&2
  }
  ip link set "$IFACE" up 2>/dev/null || {
    echo "Warning: Failed to bring interface up" >&2
  }
  
  # Start NetworkManager if it's not running
  if ! systemctl is-active --quiet NetworkManager 2>/dev/null; then
    echo "Starting NetworkManager..."
    systemctl start NetworkManager || {
      echo "Warning: Failed to start NetworkManager" >&2
    }
  else
    echo "NetworkManager is already running"
  fi
  
  echo "Normal WiFi Restored"
else
  echo "Usage:"
  echo "  sudo ./adhoc.sh start pi"
  echo "  sudo ./adhoc.sh start laptop"
  echo "  sudo ./adhoc.sh start pi --timeout 300"
  echo "  sudo ./adhoc.sh stop"
  exit 1
fi
