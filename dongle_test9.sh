#!/bin/bash

DEVICE=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)

if [ -z "$DEVICE" ]; then
    echo "Error: No ttyACM device found!"
    exit 1
fi

echo "Using: $DEVICE"
echo ""
echo "Touch the bottom-right pin, then press Enter..."
read

echo "Waiting for reconnection..."
sleep 3  # Longer wait

NEW_DEVICE=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)
echo "Device: $NEW_DEVICE"
echo ""
echo "Waiting for module to fully boot..."
sleep 2  # Give module time to boot

echo "Starting capture and sending commands..."

# Capture in background
cat $NEW_DEVICE > output.txt &
PID=$!

sleep 1

# Try sending command WITHOUT break first
echo "Sending sys get ver..."
echo -e "sys get ver\r\n" > $NEW_DEVICE
sleep 2

echo "Sending with break..."
python3 -c "
import serial, time
ser = serial.Serial('$NEW_DEVICE', 57600, timeout=2)
ser.send_break(0.3)
time.sleep(0.2)
ser.write(b'\x55')
time.sleep(0.5)
ser.write(b'sys get ver\r\n')
time.sleep(2)
ser.close()
" 2>/dev/null

sleep 3
kill $PID 2>/dev/null

echo ""
echo "=== Response ==="
cat output.txt
echo ""
echo "=== Hex ==="
hexdump -C output.txt
