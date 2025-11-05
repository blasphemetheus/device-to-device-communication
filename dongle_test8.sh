#!/bin/bash

echo "==================================="
echo "Step 1: Finding initial device..."
DEVICE=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)

if [ -z "$DEVICE" ]; then
    echo "Error: No ttyACM device found!"
    exit 1
fi

echo "Found: $DEVICE"
echo ""
echo "Step 2: Touch the bottom-right pin NOW (device will disconnect)"
echo "Press Enter after you touch it..."
read

echo ""
echo "Step 3: Waiting for device to reconnect..."
sleep 2

# Find the device again after reconnection
for i in {1..10}; do
    NEW_DEVICE=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)
    if [ -n "$NEW_DEVICE" ]; then
        echo "Device reconnected as: $NEW_DEVICE"
        break
    fi
    echo "Waiting... ($i/10)"
    sleep 1
done

if [ -z "$NEW_DEVICE" ]; then
    echo "Error: Device did not reconnect!"
    exit 1
fi

echo ""
echo "Step 4: Sending command to $NEW_DEVICE..."
sleep 1

cat $NEW_DEVICE > reconnect_test.txt &
PID=$!

python3 -c "
import serial
import time
try:
    ser = serial.Serial('$NEW_DEVICE', 57600, timeout=2)
    ser.send_break(duration=0.3)
    time.sleep(0.2)
    ser.write(b'\x55')
    time.sleep(0.5)
    ser.write(b'sys get ver\r\n')
    time.sleep(3)
    ser.close()
    print('Command sent successfully!')
except Exception as e:
    print(f'Error: {e}')
"

sleep 2
kill $PID 2>/dev/null

echo ""
echo "Response:"
cat reconnect_test.txt
echo ""
echo "Hex:"
hexdump -C reconnect_test.txt
