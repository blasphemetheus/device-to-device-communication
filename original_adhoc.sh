#!/usr/bin/env bash

# this is a script to make doing WiFi ad-hoc stuff easier
#  so like to Create or join an ad-hoc WiFi network (IBSS)
#  also to shut one down

# Usage:
#    sudo ./adhoc.sh start pi
#    sudo ./adhoc.sh start laptop
#    sudo ./adhoc.sh stop

SSID="PiAdhoc"
FREQ=2437 # channel 6 (2.437 GHz

#IP="192.168.12.2/24"

# detect WiFi interface
IFACE=$(iw dev | awk '$1=="Interface"{print $2}')

if [ -z "$IFACE" ]; then
  echo " No WiFi interface detected"
  exit 1
fi

ACTION=$1
ROLE=$2

# optional timeout section (seconds)
TIMEOUT=0
if [[ "$3" == "--timeout" && -n "$4" ]]; then
  TIMEOUT=$4
fi

# Default IPs
PI_IP="192.168.12.1/24"
LAPTOP_IP="192.168.12.2/24"

if [ "$ACTION" = "start" ]; then
  if [ "$TIMEOUT" -gt 0 ]; then
    echo "Will stop ad-hoc mode automatically in $TIMEOUT seconds..."
    nohup bash -c "sleep $TIMEOUT && sudo $(realpath $0) stop" >/dev/null 2>$1 &
  fi

  echo "Using the interface: $IFACE"
  echo "Stopping NetworkManager..."
  sudo systemctl stop NetworkManager

  echo "Setting up ad-hoc network: SSID=$SSID FREQ=$FREQ"
  # bring up ad-hoc network
  sudo ip link set "$IFACE" down
  sudo iw dev "$IFACE" set type ibss
  sudo ip link set "$IFACE" up
  sudo iw dev "$IFACE" ibss join "$SSID" "$FREQ"

  if [ "$ROLE" = "pi" ]; then
    sudo ip addr add "$PI_IP" dev "$IFACE"
    echo "Raspberry Pi Ad-hoc network '$SSID' started on $IFACE with IP $PI_IP"
  elif [ "$ROLE" = "laptop" ]; then
    sudo ip addr add "$LAPTOP_IP" dev "$IFACE"
    echo "Laptop ad-hoc network '$SSID' started on $IFACE with IP $LAPTOP_IP"
  else
    echo "Please specify 'pi' or 'laptop after 'start'"
    echo "so like -> sudo ./adhoc.sh start pi"
    exit 1
  fi

  echo "You can now ping the other device."

elif [ "$ACTION" = "stop" ]; then
  echo "Restoring managed mode on $IFACE"
  sudo ip addr flush dev "$IFACE"
  sudo ip link set "$IFACE" down
  sudo iw dev "$IFACE" set type managed
  sudo ip link set "$IFACE" up
  sudo systemctl start NetworkManager
  echo "Normal WiFi Restored"
else
  echo "Usage:"
  echo "  sudo ./adhoc.sh start pi"
  echo "  sudo ./adhoc.sh start laptop"
  echo "  sudo ./adhoc.sh stop"
  exit 1
fi
