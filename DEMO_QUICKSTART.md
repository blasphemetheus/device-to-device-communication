# D2D Communication Demo - Quick Start

## Files Created

| File | Purpose | Run On |
|------|---------|--------|
| `laptop_controller.py` | Web UI controller | Laptop |
| `pi_responder.py` | API responder | Raspberry Pi |
| `test_results.csv` | Auto-generated test data | Laptop |

## Setup

### 1. On the Raspberry Pi

```bash
# Copy pi_responder.py to Pi (via USB, scp when on same network, etc.)
scp pi_responder.py dori@dori.local:/home/dori/

# SSH to Pi and install dependencies
ssh dori@dori.local
pip install flask pyserial

# Run the responder
python3 pi_responder.py --port 5000
```

### 2. On the Laptop

```bash
cd /home/dori/git/device-to-device-communication

# Run the controller
python3 laptop_controller.py

# Open browser to: http://localhost:8080
```

## Running Tests

### WiFi Ad-hoc Test
1. Click "Start Ad-hoc" on laptop (runs adhoc.sh)
2. On Pi terminal, also run: `sudo /home/dori/d2d/adhoc.sh start pi`
3. Wait for "Connected" status
4. Enter distance, click "Run Throughput Test" or "Run Latency Test"
5. Click "Stop" when done to restore normal WiFi

### Bluetooth Test
1. Ensure Pi is running `bt-network -s nap pan0`
2. Click "Start BT PAN" on laptop
3. Wait for connection
4. Run tests

### LoRa Test
1. Plug LoRa dongle into laptop (and Pi if testing bidirectional)
2. Click "Check Module" to verify
3. Enter distance, number of packets
4. Click "Run Packet Test"

## Test Protocol for Your Report

### Suggested Distances

| Technology | Test Distances |
|------------|----------------|
| WiFi | 0m, 10m, 30m, 50m, 100m |
| Bluetooth | 0m, 5m, 10m, 15m, 20m |
| LoRa | 0m, 50m, 100m, 200m, 500m |

### Data Collection
1. For each technology and distance:
   - Run throughput test 3x
   - Run latency test 3x
2. Results auto-save to `test_results.csv`
3. Click "Download CSV" for your report data

## Expected Results (for your conclusion)

Based on your professor's paper:

| Technology | Max Throughput | Max Range | Best For |
|------------|---------------|-----------|----------|
| WiFi Ad-hoc | 10-40 Mbps | ~200-400m | High bandwidth, medium range |
| Bluetooth | 0.5-2 Mbps | ~20-50m | Low power, short range |
| LoRa | <50 kbps | 1-10+ km | Long range, low bandwidth |

## Troubleshooting

### WiFi won't connect
- Check both devices ran adhoc.sh with correct role (pi/laptop)
- Verify IP addresses: Pi=192.168.12.1, Laptop=192.168.12.2
- Try `ping 192.168.12.1` manually

### Bluetooth won't connect
- Ensure devices are paired: `bluetoothctl` → `paired-devices`
- Pi needs: `sudo bt-network -s nap pan0`
- May need `bluez-utils` (Manjaro) or `bluez-tools` (Pi)

### LoRa no response
- Check device: `ls /dev/ttyACM*`
- User must be in `uucp` group: `groups $USER`
- Try: `picocom -b 57600 --omap crcrlf /dev/ttyACM0`

## Video Demo Script

1. **Intro** (30s): Show laptop and Pi, explain D2D communication goal
2. **WiFi Demo** (2min): Start ad-hoc, run throughput at 0m and 30m, show results
3. **Bluetooth Demo** (2min): Connect PAN, run tests, compare to WiFi
4. **LoRa Demo** (2min): Send packets at increasing distances, show packet delivery
5. **Results** (1min): Show CSV data, quick graph of throughput vs distance
6. **Conclusion** (30s): WiFi=fast/medium range, BT=slow/short, LoRa=slowest/longest
