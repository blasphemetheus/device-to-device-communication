#!/bin/bash

cat /dev/ttyACM0 > timing_test.txt &
PID=$!

python3 -c "
import serial
import time
ser = serial.Serial('/dev/ttyACM1', 57600, timeout=1)
ser.send_break(duration=0.3)
time.sleep(0.1)
ser.write(b'\x55')
time.sleep(0.5)
ser.write(b'sys get ver\r\n')
print('Command sent! Now touch the bottom-right pin for 2 seconds...')
time.sleep(5)  # Wait for you to touch the pin
ser.close()
"

sleep 1
kill $PID 2>/dev/null

echo "Response:"
cat timing_test.txt
