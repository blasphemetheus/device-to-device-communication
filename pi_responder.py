#!/usr/bin/env python3
"""
Pi Responder - Runs on Raspberry Pi
Responds to test requests from the laptop controller.

Usage:
    python3 pi_responder.py [--port 5000] [--lora-device /dev/ttyACM0]
"""
import argparse
import hashlib
import os
import socket
import threading
import time
from flask import Flask, jsonify, request

app = Flask(__name__)

# LoRa serial connection (lazy init)
lora_serial = None
LORA_DEVICE = '/dev/ttyACM0'
LORA_BAUD = 57600


def check_lora_device():
    """Check if LoRa device is physically connected."""
    import glob
    # Check for the specific device
    if os.path.exists(LORA_DEVICE):
        return {'connected': True, 'device': LORA_DEVICE}
    # Check for any ttyACM devices
    acm_devices = glob.glob('/dev/ttyACM*')
    if acm_devices:
        return {'connected': True, 'device': acm_devices[0], 'note': f'Found at {acm_devices[0]} instead of {LORA_DEVICE}'}
    # Check for ttyUSB as fallback
    usb_devices = glob.glob('/dev/ttyUSB*')
    if usb_devices:
        return {'connected': False, 'device': None, 'note': f'Found ttyUSB devices: {usb_devices}, but no ttyACM'}
    return {'connected': False, 'device': None}


def get_lora():
    """Get or create LoRa serial connection."""
    global lora_serial
    if lora_serial is None:
        try:
            import serial
            lora_serial = serial.Serial(LORA_DEVICE, LORA_BAUD, timeout=2)
            lora_serial.reset_input_buffer()
            # Pause MAC for raw radio
            lora_serial.write(b"mac pause\r\n")
            lora_serial.flush()
            time.sleep(0.3)
            lora_serial.read(256)
        except Exception as e:
            print(f"LoRa init error: {e}")
            return None
    return lora_serial


def lora_send_cmd(cmd, delay=0.3):
    """Send command to LoRa module."""
    ser = get_lora()
    if ser is None:
        return None
    ser.write(f"{cmd}\r\n".encode())
    ser.flush()
    time.sleep(delay)
    return ser.read(256).decode('utf-8', errors='replace').strip()


@app.route('/health')
def health():
    """Health check endpoint."""
    lora_check = check_lora_device()
    return jsonify({
        'status': 'ok',
        'device': 'pi',
        'hostname': socket.gethostname(),
        'timestamp': time.time(),
        'lora': lora_check
    })


@app.route('/echo', methods=['POST'])
def echo():
    """Echo back data for throughput testing."""
    data = request.get_data()
    received_hash = hashlib.md5(data).hexdigest()
    return jsonify({
        'status': 'ok',
        'bytes_received': len(data),
        'md5': received_hash,
        'timestamp': time.time()
    })


@app.route('/throughput', methods=['POST'])
def throughput_test():
    """Receive data and report throughput stats."""
    start_time = time.time()
    data = request.get_data()
    elapsed = time.time() - start_time

    size_bytes = len(data)
    size_kb = size_bytes / 1024
    size_mb = size_bytes / (1024 * 1024)
    throughput_kbps = (size_bytes * 8) / (elapsed * 1000) if elapsed > 0 else 0
    throughput_mbps = throughput_kbps / 1000

    return jsonify({
        'status': 'ok',
        'bytes_received': size_bytes,
        'elapsed_seconds': elapsed,
        'throughput_kbps': round(throughput_kbps, 2),
        'throughput_mbps': round(throughput_mbps, 4),
        'md5': hashlib.md5(data).hexdigest(),
        'timestamp': time.time()
    })


@app.route('/lora/status')
def lora_status():
    """Get LoRa module status."""
    try:
        version = lora_send_cmd("sys get ver")
        hweui = lora_send_cmd("sys get hweui")
        freq = lora_send_cmd("radio get freq")
        sf = lora_send_cmd("radio get sf")
        return jsonify({
            'status': 'ok',
            'version': version,
            'hweui': hweui,
            'frequency': freq,
            'spreading_factor': sf
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/lora/receive', methods=['POST'])
def lora_receive():
    """Put LoRa in receive mode and wait for packet."""
    timeout_ms = request.json.get('timeout_ms', 10000) if request.is_json else 10000

    try:
        ser = get_lora()
        if ser is None:
            return jsonify({'status': 'error', 'error': 'LoRa not available'}), 500

        # Clear buffer and start receiving
        ser.reset_input_buffer()
        ser.write(f"radio rx {timeout_ms}\r\n".encode())
        ser.flush()

        # Wait for response
        time.sleep(0.3)
        initial = ser.read(256).decode('utf-8', errors='replace').strip()

        if 'ok' not in initial.lower():
            return jsonify({'status': 'error', 'error': initial})

        # Wait for actual data
        start = time.time()
        timeout_sec = (timeout_ms / 1000) + 2
        while time.time() - start < timeout_sec:
            data = ser.read(256).decode('utf-8', errors='replace').strip()
            if data:
                if 'radio_rx' in data:
                    # Extract hex data after "radio_rx "
                    parts = data.split()
                    if len(parts) >= 2:
                        hex_data = parts[1]
                        try:
                            decoded = bytes.fromhex(hex_data).decode('utf-8', errors='replace')
                        except:
                            decoded = hex_data
                        return jsonify({
                            'status': 'ok',
                            'received': True,
                            'hex_data': hex_data,
                            'decoded': decoded,
                            'elapsed': time.time() - start
                        })
                elif 'radio_err' in data:
                    return jsonify({
                        'status': 'ok',
                        'received': False,
                        'reason': 'timeout'
                    })
            time.sleep(0.1)

        return jsonify({
            'status': 'ok',
            'received': False,
            'reason': 'timeout'
        })

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/lora/send', methods=['POST'])
def lora_send():
    """Send data via LoRa (for bidirectional testing)."""
    if not request.is_json:
        return jsonify({'status': 'error', 'error': 'JSON required'}), 400

    message = request.json.get('message', 'PONG')
    hex_data = message.encode().hex()

    try:
        result = lora_send_cmd(f"radio tx {hex_data}", delay=0.5)
        # Wait for tx confirmation
        time.sleep(1)
        ser = get_lora()
        extra = ser.read(256).decode('utf-8', errors='replace').strip() if ser else ''

        success = 'ok' in (result or '').lower() or 'radio_tx_ok' in extra.lower()

        return jsonify({
            'status': 'ok' if success else 'error',
            'sent': message,
            'hex': hex_data,
            'response': result,
            'confirmation': extra
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


# Global flags for LoRa modes
lora_beacon_active = False
lora_echo_active = False
beacon_count = 0


def run_lora_beacon(interval=5):
    """Background thread to send periodic LoRa beacons."""
    global beacon_count, lora_beacon_active
    print(f"[LoRa Beacon] Starting - sending every {interval}s")

    while lora_beacon_active:
        try:
            ser = get_lora()
            if ser is None:
                print("[LoRa Beacon] No device, waiting...")
                time.sleep(5)
                continue

            beacon_count += 1
            msg = f"BEACON{beacon_count:04d}"
            hex_data = msg.encode().hex()

            ser.reset_input_buffer()
            ser.write(f"radio tx {hex_data}\r\n".encode())
            ser.flush()
            time.sleep(0.5)
            response = ser.read(256).decode('utf-8', errors='replace').strip()

            # Wait for tx confirmation
            time.sleep(1)
            extra = ser.read(256).decode('utf-8', errors='replace').strip()

            success = 'ok' in response.lower() or 'radio_tx_ok' in extra.lower()
            status = "OK" if success else "FAIL"
            print(f"[LoRa Beacon] #{beacon_count} sent: {msg} [{status}]")

        except Exception as e:
            print(f"[LoRa Beacon] Error: {e}")

        time.sleep(interval)

    print("[LoRa Beacon] Stopped")


def run_lora_echo():
    """Background thread to listen for LoRa packets and echo them back."""
    global lora_echo_active
    print("[LoRa Echo] Starting - listening for packets...")

    while lora_echo_active:
        try:
            ser = get_lora()
            if ser is None:
                print("[LoRa Echo] No device, waiting...")
                time.sleep(5)
                continue

            # Put radio in receive mode
            ser.reset_input_buffer()
            ser.write(b"radio rx 0\r\n")  # Continuous receive
            ser.flush()
            time.sleep(0.3)
            initial = ser.read(256).decode('utf-8', errors='replace').strip()

            if 'ok' not in initial.lower():
                print(f"[LoRa Echo] RX mode failed: {initial}")
                time.sleep(2)
                continue

            # Wait for incoming packet
            start = time.time()
            while lora_echo_active and (time.time() - start) < 30:
                if ser.in_waiting > 0:
                    data = ser.read(256).decode('utf-8', errors='replace').strip()

                    if 'radio_rx' in data:
                        # Extract hex data
                        parts = data.split()
                        if len(parts) >= 2:
                            hex_data = parts[1]
                            try:
                                decoded = bytes.fromhex(hex_data).decode('utf-8', errors='replace')
                            except:
                                decoded = hex_data
                            print(f"[LoRa Echo] Received: {decoded}")

                            # Echo back with "ECHO:" prefix
                            echo_msg = f"ECHO:{decoded}"
                            echo_hex = echo_msg.encode().hex()

                            time.sleep(0.5)  # Small delay before responding
                            ser.write(f"radio tx {echo_hex}\r\n".encode())
                            ser.flush()
                            time.sleep(1)
                            tx_resp = ser.read(256).decode('utf-8', errors='replace').strip()
                            print(f"[LoRa Echo] Sent response: {echo_msg}")
                            break

                    elif 'radio_err' in data:
                        # Timeout, restart receive
                        break

                time.sleep(0.1)

        except Exception as e:
            print(f"[LoRa Echo] Error: {e}")
            time.sleep(2)

    print("[LoRa Echo] Stopped")


@app.route('/lora/beacon/start', methods=['POST'])
def lora_beacon_start():
    """Start LoRa beacon mode."""
    global lora_beacon_active, lora_echo_active, beacon_count

    if lora_beacon_active:
        return jsonify({'success': True, 'message': 'Already running'})

    # Stop echo mode if running
    lora_echo_active = False
    time.sleep(1)

    interval = 5
    if request.is_json:
        interval = request.json.get('interval', 5)

    lora_beacon_active = True
    beacon_count = 0
    thread = threading.Thread(target=run_lora_beacon, args=(interval,), daemon=True)
    thread.start()

    return jsonify({'success': True, 'message': f'Beacon started (every {interval}s)'})


@app.route('/lora/beacon/stop', methods=['POST'])
def lora_beacon_stop():
    """Stop LoRa beacon mode."""
    global lora_beacon_active
    lora_beacon_active = False
    return jsonify({'success': True, 'message': 'Beacon stopping...', 'beacons_sent': beacon_count})


@app.route('/lora/echo/start', methods=['POST'])
def lora_echo_start():
    """Start LoRa echo mode."""
    global lora_echo_active, lora_beacon_active

    if lora_echo_active:
        return jsonify({'success': True, 'message': 'Already running'})

    # Stop beacon mode if running
    lora_beacon_active = False
    time.sleep(1)

    lora_echo_active = True
    thread = threading.Thread(target=run_lora_echo, daemon=True)
    thread.start()

    return jsonify({'success': True, 'message': 'Echo mode started'})


@app.route('/lora/echo/stop', methods=['POST'])
def lora_echo_stop():
    """Stop LoRa echo mode."""
    global lora_echo_active
    lora_echo_active = False
    return jsonify({'success': True, 'message': 'Echo mode stopping...'})


@app.route('/lora/mode')
def lora_mode_status():
    """Get current LoRa mode status."""
    return jsonify({
        'beacon_active': lora_beacon_active,
        'echo_active': lora_echo_active,
        'beacons_sent': beacon_count
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pi Responder for D2D testing')
    parser.add_argument('--port', type=int, default=5000, help='Flask port')
    parser.add_argument('--lora-device', default='/dev/ttyACM0', help='LoRa serial device')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--lora-beacon', type=int, metavar='INTERVAL',
                        help='Start in LoRa beacon mode (send every N seconds)')
    parser.add_argument('--lora-echo', action='store_true',
                        help='Start in LoRa echo mode (listen and respond)')
    args = parser.parse_args()

    LORA_DEVICE = args.lora_device

    # Check LoRa on startup
    lora_check = check_lora_device()
    if lora_check['connected']:
        lora_status_str = f"✓ Connected ({lora_check['device']})"
    else:
        lora_status_str = "✗ Not detected"
        if 'note' in lora_check:
            lora_status_str += f" - {lora_check['note']}"

    # Determine LoRa mode
    lora_mode_str = "Idle"
    if args.lora_beacon:
        lora_mode_str = f"Beacon (every {args.lora_beacon}s)"
    elif args.lora_echo:
        lora_mode_str = "Echo (listen & respond)"

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    Pi Responder Started                       ║
╠══════════════════════════════════════════════════════════════╣
║  LoRa Module: {lora_status_str:<46}║
║  LoRa Mode:   {lora_mode_str:<46}║
╠══════════════════════════════════════════════════════════════╣
║  Endpoints:                                                   ║
║    GET  /health            - Health check                     ║
║    POST /throughput        - Throughput test                  ║
║    GET  /lora/status       - LoRa module status               ║
║    POST /lora/beacon/start - Start beacon mode                ║
║    POST /lora/beacon/stop  - Stop beacon mode                 ║
║    POST /lora/echo/start   - Start echo mode                  ║
║    POST /lora/echo/stop    - Stop echo mode                   ║
║    GET  /lora/mode         - Current LoRa mode status         ║
╠══════════════════════════════════════════════════════════════╣
║  CLI Options:                                                 ║
║    --lora-beacon 5   Start sending beacons every 5 seconds    ║
║    --lora-echo       Start in listen & echo mode              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Start LoRa mode if requested via CLI
    if args.lora_beacon:
        lora_beacon_active = True
        thread = threading.Thread(target=run_lora_beacon, args=(args.lora_beacon,), daemon=True)
        thread.start()
    elif args.lora_echo:
        lora_echo_active = True
        thread = threading.Thread(target=run_lora_echo, daemon=True)
        thread.start()

    app.run(host=args.host, port=args.port, debug=False, threaded=True)
