#!/bin/bash

cat /dev/ttyACM0 > full_response.txt &
PID=$!

python3 -c "
import serial
import time
ser = serial.Serial('/dev/ttyACM0', 57600, timeout=1)
ser.send_break(duration=0.3)
time.sleep(0.1)
ser.write(b'\x55')
time.sleep(0.5)
ser.write(b'sys get ver\r\n')
time.sleep(3)  # Wait longer for full response
ser.close()
"

sleep 4  # Give more time
kill $PID 2>/dev/null

echo "Full Response:"
cat full_response.txt
echo ""
echo "Hex:"
hexdump -C full_response.txt
