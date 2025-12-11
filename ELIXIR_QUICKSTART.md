# Elixir LoRa Apps - Field Testing Quickstart

## Overview

Two Elixir applications for LoRa field testing:

| App | Run On | Purpose |
|-----|--------|---------|
| **d2d_demo** | Laptop | Web dashboard for TX/RX control |
| **d2d_responder** | Raspberry Pi | Headless beacon/echo responder |

Both apps log all TX/RX events to timestamped files in `logs/` for post-field analysis.

## Pre-Field Checklist

### On Laptop (Manjaro)
```bash
# Verify you're in uucp group for serial access
groups | grep uucp

# Build d2d_demo
cd /home/dori/git/d2d/d2d_demo
mix deps.get && mix compile
```

### On Raspberry Pi
```bash
# SSH to Pi
ssh dori@dori.local

# Verify dialout group
groups | grep dialout

# Install Elixir if needed
sudo apt install elixir erlang

# Copy d2d_responder to Pi (from laptop)
# Option 1: Via SCP (while on same WiFi)
scp -r /home/dori/git/d2d/d2d_responder dori@dori.local:/home/dori/

# Option 2: Via USB drive

# Build on Pi
cd /home/dori/d2d_responder
mix deps.get && mix compile
```

## Field Test Procedure

### Step 1: Set Up the Pi (Responder)

Plug LoRa dongle into Pi, then:

```bash
ssh dori@dori.local
cd /home/dori/d2d_responder
iex -S mix
```

In IEx on the Pi:
```elixir
# Check the LoRa dongle appeared
# (run in another terminal: ls /dev/ttyACM*)

# Connect to LoRa module
D2dResponder.connect()
# Should return :ok

# Start beacon mode - transmits every 5 seconds
D2dResponder.beacon(message: "PING", interval: 5000)

# OR start echo mode - listens and responds
D2dResponder.echo(prefix: "ACK:")

# Check status anytime
D2dResponder.status()
```

### Step 2: Set Up the Laptop (Controller)

Plug LoRa dongle into laptop, then:

```bash
cd /home/dori/git/d2d/d2d_demo
mix phx.server
```

Open browser to: **http://localhost:4000**

In the web UI:
1. Click **Connect** to connect to `/dev/ttyACM0`
2. Verify "Connected" status (green badge)
3. Click **Listen** to enter receive mode
4. You should see beacon messages from the Pi appear in the activity log

### Step 3: Run Distance Tests

At each test distance (0m, 50m, 100m, 200m, 500m):

1. **Record the distance** (use measuring tape or GPS)

2. **Packet Delivery Test**:
   - Pi: `D2dResponder.beacon(message: "D100M", interval: 2000)` (adjust message for distance)
   - Laptop: Watch activity log, count received vs expected
   - Run for 60 seconds = 30 packets expected

3. **Echo/RTT Test** (optional):
   - Pi: `D2dResponder.echo(prefix: "ACK:")`
   - Laptop: Send messages via web UI, measure response time

4. **Move to next distance**, repeat

### Step 4: Collect Logs

After field testing:

```bash
# On laptop - get demo logs
ls /home/dori/git/d2d/d2d_demo/logs/

# On Pi - get responder logs
scp dori@dori.local:/home/dori/d2d_responder/logs/*.log ./

# Log format (TSV):
# TIMESTAMP	TX/RX/EVENT	MESSAGE	HEX
```

## Quick Reference

### d2d_responder Commands (IEx)

```elixir
D2dResponder.connect()                     # Connect to /dev/ttyACM0
D2dResponder.connect("/dev/ttyACM1")       # Connect to specific port
D2dResponder.disconnect()                  # Disconnect

D2dResponder.beacon()                      # Start beacon (default: "BEACON", 5s)
D2dResponder.beacon(message: "HI", interval: 3000)
D2dResponder.stop_beacon()

D2dResponder.echo()                        # Start echo (default prefix: "ECHO:")
D2dResponder.echo(prefix: "ACK:")
D2dResponder.stop_echo()

D2dResponder.tx("Hello")                   # Send single message
D2dResponder.cmd("sys get ver")            # Send raw command
D2dResponder.status()                      # Show connection status

D2dResponder.configure(                    # Configure radio
  frequency: 915_000_000,
  sf: 7,                                   # Spreading factor 7-12
  bw: 125,                                 # Bandwidth: 125, 250, 500
  power: 14                                # TX power: -3 to 14
)
```

### d2d_demo Web UI

- **Connect/Disconnect**: Serial port control
- **Transmit**: Send messages
- **Listen**: Enter receive mode
- **Config**: Change frequency, SF, BW, power
- **Activity Log**: Real-time event stream
- **Messages**: Received message history

### Troubleshooting

**"No serial device found"**
```bash
ls /dev/ttyACM*
# If empty, replug the LoRa dongle
# Check dmesg | tail for USB errors
```

**"Permission denied" on serial port**
```bash
# Manjaro
sudo usermod -aG uucp $USER
# Pi
sudo usermod -aG dialout $USER
# Then logout/login or reboot
```

**No response from LoRa module**
```elixir
# Try raw command
D2dResponder.cmd("sys get ver")
# Should return firmware version like "RN2903 1.0.5"

# If no response, check baud rate (should be 57600)
# Try picocom for manual testing:
# picocom -b 57600 --omap crcrlf /dev/ttyACM0
```

**Messages not received at distance**
- Increase spreading factor (higher SF = longer range, slower speed)
- Check antenna connections
- Ensure both devices on same frequency (default: 915 MHz for US)

```elixir
# On both devices, set SF to 12 for max range:
D2dResponder.configure(sf: 12)
```

## Video Demo Script

1. **Intro** (30s): Show laptop and Pi with LoRa dongles
2. **Setup** (1min): Start responder on Pi, start demo on laptop, show connection
3. **Close Range** (1min): Demo TX/RX at 0m, show messages appearing
4. **Distance Test** (3min): Walk to 100m, 200m, show continued communication
5. **Log Analysis** (1min): Show log files, explain data format
6. **Conclusion** (30s): LoRa = long range, low bandwidth, ideal for IoT sensors

## Log File Analysis

After field testing, analyze logs:

```bash
# Count successful transmissions
grep "TX" logs/d2d_demo_*.log | wc -l

# Count received messages
grep "RX" logs/d2d_responder_*.log | wc -l

# Calculate packet delivery ratio
# PDR = (RX count / TX count) * 100
```

Sample log entry:
```
2025-12-11T14:31:05Z	TX	"PING"	50494E47
2025-12-11T14:31:07Z	EVENT	:tx_ok
2025-12-11T14:32:15Z	RX	"ACK:PING"	41434B3A50494E47
```
