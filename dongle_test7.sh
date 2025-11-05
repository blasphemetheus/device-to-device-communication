#!/bin/bash

DEVICE=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)

if [ -z "$DEVICE" ]; then
    echo "Error: No ttyACM device found!"
    exit 1
fi

echo "Using device: $DEVICE"
echo "==================================="
echo "INSTRUCTIONS:"
echo "1. Touch and HOLD the bottom-right pin NOW"
echo "2. Keep holding it for the entire test"
echo "3. Press Enter when ready..."
read

cat $DEVICE > full_test.txt &
PID=$!

python3 -c "
import serial
import time
ser = serial.Serial('$DEVICE', 57600, timeout=2)
time.sleep(0.5)
ser.send_break(duration=0.3)
time.sleep(0.2)
ser.write(b'\x55')
time.sleep(0.5)
ser.write(b'sys get ver\r\n')
print('Command sent! Keep holding the pin...')
time.sleep(5)  # Long wait to capture full response
ser.close()
"

sleep 1
kill $PID 2>/dev/null

echo ""
echo "Response:"
cat full_test.txt
echo ""
echo "Hex:"
hexdump -C full_test.txt
