#!/bin/bash

# Find the RN2903 device
DEVICE=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)

if [ -z "$DEVICE" ]; then
    echo "Error: No ttyACM device found!"
    exit 1
fi

echo "Using device: $DEVICE"

cat $DEVICE > timing_test.txt &
PID=$!

python3 -c "
import serial
import time
ser = serial.Serial('$DEVICE', 57600, timeout=1)
ser.send_break(duration=0.3)
time.sleep(0.1)
ser.write(b'\x55')
time.sleep(0.5)
ser.write(b'sys get ver\r\n')
print('Command sent! Now touch the bottom-right pin for 2 seconds...')
time.sleep(5)
ser.close()
"

sleep 1
kill $PID 2>/dev/null

echo "Response:"
cat timing_test.txt
echo ""
echo "Hex:"
hexdump -C timing_test.txt
