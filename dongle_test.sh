#!/bin/bash

# Configure port
stty -F /dev/ttyACM0 57600 raw -echo -echok -echoctl -echoke

# Start capturing
cat /dev/ttyACM0 > response.txt &
PID=$!

# Send break using stty (this sends 0 bits for duration)
stty -F /dev/ttyACM0 -brk
sleep 0.3
stty -F /dev/ttyACM0 brk

# Send 0x55 for autobaud
printf '\x55' > /dev/ttyACM0
sleep 0.5

# Send command
echo -e "sys get ver\r\n" > /dev/ttyACM0
sleep 2

kill $PID 2>/dev/null
cat response.txt
hexdump -C response.txt
