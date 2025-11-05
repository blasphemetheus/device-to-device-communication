#!/bin/bash

# First, let's try the break + 0x55 sequence more carefully
stty -F /dev/ttyACM0 57600 raw -echo

# Start listening
cat /dev/ttyACM0 > bootloader_response.txt &
PID=$!

# Send break (zero bits for 300ms) then 0x55
python3 -c "
import serial
import time
ser = serial.Serial('/dev/ttyACM0', 57600, timeout=1)
ser.send_break(duration=0.3)  # Send break signal
time.sleep(0.1)
ser.write(b'\x55')  # Autobaud character
time.sleep(0.5)
ser.write(b'sys get ver\r\n')
time.sleep(1)
ser.close()
"

sleep 2
kill $PID 2>/dev/null

echo "Response:"
cat bootloader_response.txt
hexdump -C bootloader_response.txt
