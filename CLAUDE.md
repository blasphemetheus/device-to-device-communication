# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**IoT Course Project (Hands-On Option)** for University of Missouri IoT course. Implementing **device-to-device communication** between a Raspberry Pi 3 Model B+ and a Manjaro Linux laptop using three communication methods:

1. **WiFi Ad-hoc (IBSS)** - Working
2. **Bluetooth PAN** - Partially working
3. **LoRa (RN2903)** - In progress via Elixir apps

### Academic Context

This project is inspired by Prof. Abderrahmen Mtibaa's research paper:
> "On Practical Device-to-Device Wireless Communication: A Measurement Driven Study" (IEEE 2017)
> Authors: Mtibaa, Emam, Tariq, Essameldin, Harras (Carnegie Mellon University)

**Key findings from the paper relevant to this project:**
- WiFi ad-hoc: 10-45 Mbps throughput, 200-420m range (indoor corridors extend range ~10% via signal reflection)
- Bluetooth: 0.6-2 Mbps throughput, 20-150m range (indoor line-of-sight best)
- Raspberry Pi with USB dongles: Higher coverage but "lossy" (~50% packet loss at 220m) due to non-integrated wireless
- Indoor corridors help "canalize" signals, extending range
- Metrics to measure: throughput, packet loss ratio, RTT, RSSI

### Deliverables
1. **Written Report**: Problem, system design, implementation, evaluation, lessons learned
2. **Demo Video**: 5-8 minutes showing system in action

### Hardware
- **Raspberry Pi 3 Model B+** (borrowed from Abde, hostname: `dori`, user: `dori`)
- **Laptop**: Manjaro Linux (user: `dori`)
- **LoRa dongles**: RN-2903-PICTAIL (x2) - USB serial devices at `/dev/ttyACM*`, 57600 baud
- **LoRa Hat** (optional): LoRa/GPS Hat 915MHz for Pi (not yet tested)

### Key IP Addresses
- WiFi Ad-hoc: Pi = `192.168.12.1`, Laptop = `192.168.12.2`
- Bluetooth PAN: Pi = `192.168.44.1`, Laptop = `192.168.44.2`
- Pi MAC (Bluetooth): `B8:27:EB:D6:9C:95`

## Elixir Applications (LoRa Testing)

Two Elixir apps were created to replace the Python scripts for LoRa field testing:

### d2d_demo (Web Dashboard)
- **Location**: `/home/dori/git/d2d/d2d_demo`
- **Type**: Phoenix LiveView web app
- **Purpose**: Web UI for controlling LoRa module, viewing TX/RX, configuring radio
- **Run**: `cd /home/dori/git/d2d/d2d_demo && mix phx.server` then open http://localhost:4000
- **Logs**: Writes to `logs/d2d_demo_YYYYMMDD_HHMMSS.log`

### d2d_responder (Headless/CLI)
- **Location**: `/home/dori/git/d2d/d2d_responder`
- **Type**: Plain OTP application (no web UI)
- **Purpose**: Run on Pi - beacon mode (periodic TX) or echo mode (RX and respond)
- **Run**: `cd /home/dori/git/d2d/d2d_responder && iex -S mix`
- **Logs**: Writes to `logs/d2d_responder_YYYYMMDD_HHMMSS.log`

**Key commands in IEx:**
```elixir
D2dResponder.connect()                    # Connect to /dev/ttyACM0
D2dResponder.beacon(message: "TEST", interval: 5000)  # TX every 5s
D2dResponder.echo(prefix: "ACK:")         # Echo received messages
D2dResponder.stop_beacon()
D2dResponder.stop_echo()
D2dResponder.status()
```

**Both apps use:**
- `circuits_uart` for serial communication
- RN2903 AT command protocol (`mac pause`, `radio tx <hex>`, `radio rx <timeout>`)
- File logging for field data collection (TSV format with timestamps)

## Shell Scripts (WiFi/Bluetooth)

### WiFi Ad-hoc (Working)
```bash
# On Pi (via SSH before WiFi goes down):
ssh dori@dori.local "nohup sudo /home/dori/d2d/adhoc.sh start pi &"

# On Laptop:
sudo ./adhoc.sh start laptop
ping 192.168.12.1  # Test connection

# Restore normal WiFi:
sudo ./adhoc.sh stop
```

### Bluetooth PAN (In Progress)
```bash
# On Pi (start NAP server):
sudo bt-network -s nap pan0

# On Laptop:
./bluetooth_laptop.sh pair B8:27:EB:D6:9C:95
./bluetooth_laptop.sh start B8:27:EB:D6:9C:95
```

### LoRa Serial (Manual Testing)
```bash
# Find device:
ls /dev/ttyACM*

# Test serial (57600 baud, CR+LF line endings):
picocom -b 57600 --omap crcrlf /dev/ttyACM0

# Key RN2903 commands:
# sys get ver     - Get firmware version
# mac pause       - Pause LoRaWAN stack for raw LoRa
# radio tx <hex>  - Transmit hex data
# radio rx 0      - Receive continuously
```

User must be in `uucp` group (Manjaro) or `dialout` group (Pi): `sudo usermod -aG uucp $USER`

## Test Protocol (Based on Research Paper)

### Suggested Distances
| Technology | Test Distances |
|------------|----------------|
| WiFi Ad-hoc | 0m, 10m, 30m, 50m, 100m |
| Bluetooth | 0m, 5m, 10m, 15m, 20m |
| LoRa | 0m, 50m, 100m, 200m, 500m |

### Metrics to Collect
1. **Throughput**: Bytes/second for file transfers
2. **Packet Loss**: % of UDP packets lost
3. **RTT**: Round-trip time for echo packets
4. **RSSI**: Signal strength (if available)

### Expected Results (from paper)
| Technology | Max Throughput | Max Range | Best For |
|------------|---------------|-----------|----------|
| WiFi Ad-hoc | 10-45 Mbps | 200-420m | High bandwidth, medium range |
| Bluetooth | 0.6-2 Mbps | 20-150m | Low power, short range |
| LoRa | <50 kbps | 1-10+ km | Long range, low bandwidth |

## Important Files

- `IoT_Course_Project.md` - Assignment requirements
- `IoT_D2D_Comm_Notes.md` - Detailed setup notes and troubleshooting log
- `DEMO_QUICKSTART.md` - Python version quickstart (legacy)
- `ELIXIR_QUICKSTART.md` - Elixir apps quickstart for field testing
- `On_practical_device-to-device_wireless_communication_A_measurement_driven_study.pdf` - Prof's research paper
