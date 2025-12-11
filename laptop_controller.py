#!/usr/bin/env python3
"""
Laptop Controller - D2D Communication Demo
Web UI to test WiFi, Bluetooth, and LoRa communication with a Raspberry Pi.

Usage:
    python3 laptop_controller.py [--port 8080] [--lora-device /dev/ttyACM0]
"""
import argparse
import csv
import hashlib
import os
import subprocess
import time
from datetime import datetime
from flask import Flask, jsonify, render_template_string, request
import requests

app = Flask(__name__)

# Configuration
PI_WIFI_IP = '192.168.12.1'
PI_BT_IP = '192.168.44.1'
PI_NORMAL_HOST = 'dori.local'  # Pi hostname when on normal network
PI_PORT = 5000
LORA_DEVICE = '/dev/ttyACM0'
LORA_BAUD = 57600
RESULTS_FILE = 'test_results.csv'

# LoRa serial (lazy init)
lora_serial = None


def run_on_pi(cmd, timeout=30):
    """Run a command on the Pi via SSH."""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=no',
             f'dori@{PI_NORMAL_HOST}', cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'SSH timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def check_pi_ssh():
    """Check if Pi is reachable via SSH."""
    result = run_on_pi('echo ok', timeout=10)
    return result.get('success', False) and 'ok' in result.get('stdout', '')


def get_lora():
    """Get or create LoRa serial connection."""
    global lora_serial
    if lora_serial is None:
        try:
            import serial
            lora_serial = serial.Serial(LORA_DEVICE, LORA_BAUD, timeout=2)
            lora_serial.reset_input_buffer()
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


def log_result(technology, test_type, distance, success, metrics):
    """Log test result to CSV file."""
    file_exists = os.path.exists(RESULTS_FILE)
    with open(RESULTS_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                'timestamp', 'technology', 'test_type', 'distance_m',
                'success', 'throughput_mbps', 'latency_ms', 'packet_loss_pct', 'notes'
            ])
        writer.writerow([
            datetime.now().isoformat(),
            technology,
            test_type,
            distance,
            success,
            metrics.get('throughput_mbps', ''),
            metrics.get('latency_ms', ''),
            metrics.get('packet_loss_pct', ''),
            metrics.get('notes', '')
        ])


def check_connection(ip, port=5000, timeout=3):
    """Check if Pi is reachable."""
    try:
        resp = requests.get(f'http://{ip}:{port}/health', timeout=timeout)
        return resp.status_code == 200
    except:
        return False


def run_throughput_test(ip, size_kb=1024, port=5000):
    """Run throughput test by sending data to Pi."""
    data = os.urandom(size_kb * 1024)
    data_hash = hashlib.md5(data).hexdigest()

    start_time = time.time()
    try:
        resp = requests.post(
            f'http://{ip}:{port}/throughput',
            data=data,
            timeout=60
        )
        elapsed = time.time() - start_time

        if resp.status_code == 200:
            result = resp.json()
            result['local_elapsed'] = elapsed
            result['local_throughput_mbps'] = (size_kb * 1024 * 8) / (elapsed * 1_000_000)
            result['hash_match'] = result.get('md5') == data_hash
            return {'success': True, **result}
        return {'success': False, 'error': f'HTTP {resp.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def run_latency_test(ip, count=10, port=5000):
    """Run latency test (RTT) with multiple pings."""
    rtts = []
    for i in range(count):
        start = time.time()
        try:
            resp = requests.get(f'http://{ip}:{port}/health', timeout=5)
            if resp.status_code == 200:
                rtts.append((time.time() - start) * 1000)
        except:
            pass
        time.sleep(0.1)

    if rtts:
        return {
            'success': True,
            'count': len(rtts),
            'min_ms': round(min(rtts), 2),
            'max_ms': round(max(rtts), 2),
            'avg_ms': round(sum(rtts) / len(rtts), 2),
            'packet_loss_pct': round((1 - len(rtts) / count) * 100, 1)
        }
    return {'success': False, 'error': 'No successful pings'}


# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>D2D Communication Demo</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }
        h1 { color: #00d4ff; text-align: center; }
        h2 { color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
        .card {
            background: #16213e;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .card h3 { margin-top: 0; color: #00d4ff; }
        .status { padding: 8px 16px; border-radius: 20px; display: inline-block; margin: 10px 0; }
        .status.connected { background: #00c853; color: white; }
        .status.disconnected { background: #ff5252; color: white; }
        .status.unknown { background: #666; color: white; }
        button {
            background: #00d4ff;
            color: #1a1a2e;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            margin: 5px;
            transition: all 0.2s;
        }
        button:hover { background: #00a8cc; transform: translateY(-2px); }
        button:disabled { background: #666; cursor: not-allowed; transform: none; }
        button.danger { background: #ff5252; }
        button.danger:hover { background: #ff1744; }
        input, select {
            padding: 10px;
            border-radius: 6px;
            border: 1px solid #444;
            background: #0f0f23;
            color: #eee;
            margin: 5px;
            font-size: 14px;
        }
        .result {
            background: #0f0f23;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            font-family: monospace;
            white-space: pre-wrap;
            max-height: 300px;
            overflow-y: auto;
        }
        .result.success { border-left: 4px solid #00c853; }
        .result.error { border-left: 4px solid #ff5252; }
        .controls { margin: 10px 0; }
        label { display: block; margin: 10px 0 5px; color: #aaa; }
        .test-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #333; }
        th { color: #00d4ff; }
        .spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid #333;
                   border-top-color: #00d4ff; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <h1>Device-to-Device Communication Demo</h1>
    <p style="text-align:center;color:#888;">Laptop (Controller) → Raspberry Pi (Responder)</p>

    <div class="grid">
        <!-- WiFi Ad-hoc Card -->
        <div class="card">
            <h3>WiFi Ad-hoc</h3>
            <div>
                Status: <span id="wifi-status" class="status unknown">Checking...</span>
            </div>
            <div class="controls">
                <button onclick="startWifi()">Start Ad-hoc</button>
                <button onclick="stopWifi()" class="danger">Stop</button>
                <button onclick="checkWifi()">Check Connection</button>
            </div>
            <div class="test-row">
                <label>Distance (m):</label>
                <input type="number" id="wifi-distance" value="0" min="0" style="width:80px;">
                <label>Size (KB):</label>
                <input type="number" id="wifi-size" value="1024" min="1" style="width:80px;">
            </div>
            <div class="controls">
                <button onclick="runWifiThroughput()">Run Throughput Test</button>
                <button onclick="runWifiLatency()">Run Latency Test</button>
            </div>
            <div id="wifi-result" class="result" style="display:none;"></div>
        </div>

        <!-- Bluetooth Card -->
        <div class="card">
            <h3>Bluetooth PAN</h3>
            <div>
                Status: <span id="bt-status" class="status unknown">Checking...</span>
            </div>
            <div class="controls">
                <button onclick="startBluetooth()">Start BT PAN</button>
                <button onclick="stopBluetooth()" class="danger">Stop</button>
                <button onclick="checkBluetooth()">Check Connection</button>
            </div>
            <div class="test-row">
                <label>Distance (m):</label>
                <input type="number" id="bt-distance" value="0" min="0" style="width:80px;">
                <label>Size (KB):</label>
                <input type="number" id="bt-size" value="100" min="1" style="width:80px;">
            </div>
            <div class="controls">
                <button onclick="runBtThroughput()">Run Throughput Test</button>
                <button onclick="runBtLatency()">Run Latency Test</button>
            </div>
            <div id="bt-result" class="result" style="display:none;"></div>
        </div>

        <!-- LoRa Card -->
        <div class="card">
            <h3>LoRa (RN2903)</h3>
            <div>
                Status: <span id="lora-status" class="status unknown">Checking...</span>
            </div>
            <div class="controls">
                <button onclick="checkLora()">Check Module</button>
            </div>
            <div class="test-row">
                <label>Distance (m):</label>
                <input type="number" id="lora-distance" value="0" min="0" style="width:80px;">
                <label>Packets:</label>
                <input type="number" id="lora-packets" value="10" min="1" style="width:80px;">
            </div>
            <div class="controls">
                <button onclick="runLoraTest()">Run Packet Test</button>
                <button onclick="sendLoraMessage()">Send Single Message</button>
            </div>
            <div class="test-row">
                <label>Message:</label>
                <input type="text" id="lora-message" value="HELLO" style="width:150px;">
            </div>
            <div id="lora-result" class="result" style="display:none;"></div>
        </div>

        <!-- Pi Control Card -->
        <div class="card">
            <h3>Raspberry Pi Control</h3>
            <div>
                SSH: <span id="pi-ssh-status" class="status unknown">Checking...</span>
            </div>
            <div>
                Responder: <span id="pi-responder-status" class="status unknown">Checking...</span>
            </div>
            <div>
                Pi LoRa: <span id="pi-lora-status" class="status unknown">Checking...</span>
            </div>
            <div class="controls">
                <button onclick="checkPiStatus()">Refresh Status</button>
            </div>
            <div class="controls">
                <button onclick="startPiResponder()">Start Responder</button>
                <button onclick="stopPiResponder()" class="danger">Stop Responder</button>
            </div>
            <div class="controls">
                <button onclick="startPiAdhoc()">Start Pi Ad-hoc</button>
                <button onclick="stopPiAdhoc()" class="danger">Stop Pi Ad-hoc</button>
            </div>
            <hr style="border-color:#333;margin:15px 0;">
            <div><strong>LoRa Distance Testing:</strong></div>
            <div>
                Pi LoRa Mode: <span id="pi-lora-mode" class="status unknown">Unknown</span>
            </div>
            <div class="controls">
                <button onclick="startPiBeacon()">Start Beacon</button>
                <button onclick="stopPiBeacon()" class="danger">Stop Beacon</button>
            </div>
            <div class="controls">
                <button onclick="startPiEcho()">Start Echo</button>
                <button onclick="stopPiEcho()" class="danger">Stop Echo</button>
            </div>
            <div id="pi-result" class="result" style="display:none;"></div>
        </div>
    </div>

    <h2>Test Results</h2>
    <div class="card">
        <button onclick="loadResults()">Refresh Results</button>
        <button onclick="downloadResults()">Download CSV</button>
        <button onclick="clearResults()" class="danger">Clear All</button>
        <div id="results-table"></div>
    </div>

    <script>
        const PI_PORT = 5000;
        const WIFI_IP = '192.168.12.1';
        const BT_IP = '192.168.44.1';

        function showResult(elementId, data, success) {
            const el = document.getElementById(elementId);
            el.style.display = 'block';
            el.className = 'result ' + (success ? 'success' : 'error');
            el.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
        }

        function setStatus(elementId, connected, text) {
            const el = document.getElementById(elementId);
            el.className = 'status ' + (connected ? 'connected' : 'disconnected');
            el.textContent = text || (connected ? 'Connected' : 'Disconnected');
        }

        async function apiCall(endpoint, options = {}) {
            try {
                const resp = await fetch('/api' + endpoint, {
                    method: options.method || 'GET',
                    headers: {'Content-Type': 'application/json'},
                    body: options.body ? JSON.stringify(options.body) : undefined
                });
                return await resp.json();
            } catch (e) {
                return {success: false, error: e.message};
            }
        }

        // WiFi functions
        async function checkWifi() {
            setStatus('wifi-status', false, 'Checking...');
            const result = await apiCall('/wifi/check');
            setStatus('wifi-status', result.connected, result.connected ? 'Connected' : 'Not Connected');
            showResult('wifi-result', result, result.connected);
        }

        async function startWifi() {
            showResult('wifi-result', 'Starting WiFi ad-hoc...', true);
            const result = await apiCall('/wifi/start', {method: 'POST'});
            showResult('wifi-result', result, result.success);
            setTimeout(checkWifi, 3000);
        }

        async function stopWifi() {
            const result = await apiCall('/wifi/stop', {method: 'POST'});
            showResult('wifi-result', result, result.success);
            setStatus('wifi-status', false, 'Stopped');
        }

        async function runWifiThroughput() {
            const distance = document.getElementById('wifi-distance').value;
            const size = document.getElementById('wifi-size').value;
            showResult('wifi-result', 'Running throughput test...', true);
            const result = await apiCall('/wifi/throughput', {
                method: 'POST',
                body: {distance: distance, size_kb: parseInt(size)}
            });
            showResult('wifi-result', result, result.success);
            loadResults();
        }

        async function runWifiLatency() {
            const distance = document.getElementById('wifi-distance').value;
            showResult('wifi-result', 'Running latency test...', true);
            const result = await apiCall('/wifi/latency', {
                method: 'POST',
                body: {distance: distance}
            });
            showResult('wifi-result', result, result.success);
            loadResults();
        }

        // Bluetooth functions
        async function checkBluetooth() {
            setStatus('bt-status', false, 'Checking...');
            const result = await apiCall('/bluetooth/check');
            setStatus('bt-status', result.connected, result.connected ? 'Connected' : 'Not Connected');
            showResult('bt-result', result, result.connected);
        }

        async function startBluetooth() {
            showResult('bt-result', 'Starting Bluetooth PAN...', true);
            const result = await apiCall('/bluetooth/start', {method: 'POST'});
            showResult('bt-result', result, result.success);
            setTimeout(checkBluetooth, 3000);
        }

        async function stopBluetooth() {
            const result = await apiCall('/bluetooth/stop', {method: 'POST'});
            showResult('bt-result', result, result.success);
            setStatus('bt-status', false, 'Stopped');
        }

        async function runBtThroughput() {
            const distance = document.getElementById('bt-distance').value;
            const size = document.getElementById('bt-size').value;
            showResult('bt-result', 'Running throughput test...', true);
            const result = await apiCall('/bluetooth/throughput', {
                method: 'POST',
                body: {distance: distance, size_kb: parseInt(size)}
            });
            showResult('bt-result', result, result.success);
            loadResults();
        }

        async function runBtLatency() {
            const distance = document.getElementById('bt-distance').value;
            showResult('bt-result', 'Running latency test...', true);
            const result = await apiCall('/bluetooth/latency', {
                method: 'POST',
                body: {distance: distance}
            });
            showResult('bt-result', result, result.success);
            loadResults();
        }

        // LoRa functions
        async function checkLora() {
            setStatus('lora-status', false, 'Checking...');
            const result = await apiCall('/lora/status');
            setStatus('lora-status', result.success, result.success ? 'Module OK' : 'Not Available');
            showResult('lora-result', result, result.success);
        }

        async function runLoraTest() {
            const distance = document.getElementById('lora-distance').value;
            const packets = document.getElementById('lora-packets').value;
            showResult('lora-result', 'Running LoRa packet test...', true);
            const result = await apiCall('/lora/test', {
                method: 'POST',
                body: {distance: distance, packet_count: parseInt(packets)}
            });
            showResult('lora-result', result, result.success);
            loadResults();
        }

        async function sendLoraMessage() {
            const message = document.getElementById('lora-message').value;
            showResult('lora-result', 'Sending: ' + message, true);
            const result = await apiCall('/lora/send', {
                method: 'POST',
                body: {message: message}
            });
            showResult('lora-result', result, result.success);
        }

        // Results functions
        async function loadResults() {
            const result = await apiCall('/results');
            if (result.success && result.results) {
                let html = '<table><tr><th>Time</th><th>Tech</th><th>Test</th><th>Distance</th><th>Success</th><th>Throughput</th><th>Latency</th><th>Loss</th></tr>';
                result.results.slice(-20).reverse().forEach(r => {
                    html += `<tr>
                        <td>${r.timestamp ? r.timestamp.split('T')[1].split('.')[0] : ''}</td>
                        <td>${r.technology}</td>
                        <td>${r.test_type}</td>
                        <td>${r.distance_m}m</td>
                        <td style="color:${r.success === 'True' ? '#00c853' : '#ff5252'}">${r.success}</td>
                        <td>${r.throughput_mbps ? r.throughput_mbps + ' Mbps' : '-'}</td>
                        <td>${r.latency_ms ? r.latency_ms + ' ms' : '-'}</td>
                        <td>${r.packet_loss_pct ? r.packet_loss_pct + '%' : '-'}</td>
                    </tr>`;
                });
                html += '</table>';
                document.getElementById('results-table').innerHTML = html;
            }
        }

        function downloadResults() {
            window.location.href = '/api/results/download';
        }

        async function clearResults() {
            if (confirm('Clear all test results?')) {
                await apiCall('/results/clear', {method: 'POST'});
                loadResults();
            }
        }

        // Pi control functions
        async function checkPiStatus() {
            setStatus('pi-ssh-status', false, 'Checking...');
            setStatus('pi-responder-status', false, 'Checking...');
            setStatus('pi-lora-status', false, 'Checking...');

            const result = await apiCall('/pi/status');

            if (result.ssh) {
                setStatus('pi-ssh-status', true, 'Connected');
                setStatus('pi-responder-status', result.responder_running,
                    result.responder_running ? 'Running' : 'Stopped');
                setStatus('pi-lora-status', result.lora_connected,
                    result.lora_connected ? 'Connected' : 'Not detected');
            } else {
                setStatus('pi-ssh-status', false, 'Not reachable');
                setStatus('pi-responder-status', false, 'Unknown');
                setStatus('pi-lora-status', false, 'Unknown');
            }
            showResult('pi-result', result, result.success);
        }

        async function startPiResponder() {
            showResult('pi-result', 'Starting Pi responder...', true);
            const result = await apiCall('/pi/responder/start', {method: 'POST'});
            showResult('pi-result', result, result.success);
            setTimeout(checkPiStatus, 2000);
        }

        async function stopPiResponder() {
            showResult('pi-result', 'Stopping Pi responder...', true);
            const result = await apiCall('/pi/responder/stop', {method: 'POST'});
            showResult('pi-result', result, result.success);
            setTimeout(checkPiStatus, 1000);
        }

        async function startPiAdhoc() {
            showResult('pi-result', 'Starting Pi ad-hoc (this will disconnect SSH)...', true);
            const result = await apiCall('/pi/adhoc/start', {method: 'POST'});
            showResult('pi-result', result, result.success);
        }

        async function stopPiAdhoc() {
            showResult('pi-result', 'Stopping Pi ad-hoc...', true);
            const result = await apiCall('/pi/adhoc/stop', {method: 'POST'});
            showResult('pi-result', result, result.success);
            setTimeout(checkPiStatus, 3000);
        }

        async function startPiBeacon() {
            showResult('pi-result', 'Starting Pi LoRa beacon mode...', true);
            const result = await apiCall('/pi/lora/beacon/start', {method: 'POST'});
            showResult('pi-result', result, result.success);
            if (result.success) {
                setStatus('pi-lora-mode', true, 'Beacon');
            }
        }

        async function stopPiBeacon() {
            showResult('pi-result', 'Stopping Pi LoRa beacon...', true);
            const result = await apiCall('/pi/lora/beacon/stop', {method: 'POST'});
            showResult('pi-result', result, result.success);
            setStatus('pi-lora-mode', false, 'Idle');
        }

        async function startPiEcho() {
            showResult('pi-result', 'Starting Pi LoRa echo mode...', true);
            const result = await apiCall('/pi/lora/echo/start', {method: 'POST'});
            showResult('pi-result', result, result.success);
            if (result.success) {
                setStatus('pi-lora-mode', true, 'Echo');
            }
        }

        async function stopPiEcho() {
            showResult('pi-result', 'Stopping Pi LoRa echo...', true);
            const result = await apiCall('/pi/lora/echo/stop', {method: 'POST'});
            showResult('pi-result', result, result.success);
            setStatus('pi-lora-mode', false, 'Idle');
        }

        // Initial checks
        checkWifi();
        checkBluetooth();
        checkLora();
        checkPiStatus();
        loadResults();
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """Serve the main web UI."""
    return render_template_string(HTML_TEMPLATE)


# WiFi API endpoints
@app.route('/api/wifi/check')
def api_wifi_check():
    """Check WiFi ad-hoc connection to Pi."""
    connected = check_connection(PI_WIFI_IP, PI_PORT)
    return jsonify({'connected': connected, 'ip': PI_WIFI_IP})


@app.route('/api/wifi/start', methods=['POST'])
def api_wifi_start():
    """Start WiFi ad-hoc mode."""
    try:
        script = '/home/dori/git/device-to-device-communication/adhoc.sh'
        if os.path.exists(script):
            result = subprocess.run(
                ['sudo', script, 'start', 'laptop'],
                capture_output=True, text=True, timeout=30
            )
            return jsonify({
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            })
        return jsonify({'success': False, 'error': 'adhoc.sh not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/wifi/stop', methods=['POST'])
def api_wifi_stop():
    """Stop WiFi ad-hoc mode."""
    try:
        script = '/home/dori/git/device-to-device-communication/adhoc.sh'
        if os.path.exists(script):
            result = subprocess.run(
                ['sudo', script, 'stop'],
                capture_output=True, text=True, timeout=30
            )
            return jsonify({'success': result.returncode == 0})
        return jsonify({'success': False, 'error': 'adhoc.sh not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/wifi/throughput', methods=['POST'])
def api_wifi_throughput():
    """Run WiFi throughput test."""
    data = request.get_json() or {}
    distance = data.get('distance', 0)
    size_kb = data.get('size_kb', 1024)

    result = run_throughput_test(PI_WIFI_IP, size_kb)

    log_result('WiFi', 'throughput', distance, result['success'], {
        'throughput_mbps': result.get('local_throughput_mbps', 0),
        'notes': f'{size_kb}KB transfer'
    })

    return jsonify(result)


@app.route('/api/wifi/latency', methods=['POST'])
def api_wifi_latency():
    """Run WiFi latency test."""
    data = request.get_json() or {}
    distance = data.get('distance', 0)

    result = run_latency_test(PI_WIFI_IP)

    log_result('WiFi', 'latency', distance, result['success'], {
        'latency_ms': result.get('avg_ms', 0),
        'packet_loss_pct': result.get('packet_loss_pct', 0)
    })

    return jsonify(result)


# Bluetooth API endpoints
@app.route('/api/bluetooth/check')
def api_bt_check():
    """Check Bluetooth PAN connection to Pi."""
    connected = check_connection(PI_BT_IP, PI_PORT)
    return jsonify({'connected': connected, 'ip': PI_BT_IP})


@app.route('/api/bluetooth/start', methods=['POST'])
def api_bt_start():
    """Start Bluetooth PAN connection."""
    try:
        script = '/home/dori/git/device-to-device-communication/bluetooth_laptop.sh'
        pi_mac = 'B8:27:EB:D6:9C:95'
        if os.path.exists(script):
            result = subprocess.run(
                [script, 'start', pi_mac],
                capture_output=True, text=True, timeout=30
            )
            return jsonify({
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            })
        return jsonify({'success': False, 'error': 'bluetooth_laptop.sh not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/bluetooth/stop', methods=['POST'])
def api_bt_stop():
    """Stop Bluetooth PAN connection."""
    try:
        script = '/home/dori/git/device-to-device-communication/bluetooth_laptop.sh'
        if os.path.exists(script):
            result = subprocess.run(
                [script, 'stop'],
                capture_output=True, text=True, timeout=30
            )
            return jsonify({'success': result.returncode == 0})
        return jsonify({'success': False, 'error': 'bluetooth_laptop.sh not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/bluetooth/throughput', methods=['POST'])
def api_bt_throughput():
    """Run Bluetooth throughput test."""
    data = request.get_json() or {}
    distance = data.get('distance', 0)
    size_kb = data.get('size_kb', 100)

    result = run_throughput_test(PI_BT_IP, size_kb)

    log_result('Bluetooth', 'throughput', distance, result['success'], {
        'throughput_mbps': result.get('local_throughput_mbps', 0),
        'notes': f'{size_kb}KB transfer'
    })

    return jsonify(result)


@app.route('/api/bluetooth/latency', methods=['POST'])
def api_bt_latency():
    """Run Bluetooth latency test."""
    data = request.get_json() or {}
    distance = data.get('distance', 0)

    result = run_latency_test(PI_BT_IP)

    log_result('Bluetooth', 'latency', distance, result['success'], {
        'latency_ms': result.get('avg_ms', 0),
        'packet_loss_pct': result.get('packet_loss_pct', 0)
    })

    return jsonify(result)


# LoRa API endpoints
@app.route('/api/lora/status')
def api_lora_status():
    """Check LoRa module status."""
    try:
        version = lora_send_cmd("sys get ver")
        if version:
            hweui = lora_send_cmd("sys get hweui")
            freq = lora_send_cmd("radio get freq")
            sf = lora_send_cmd("radio get sf")
            return jsonify({
                'success': True,
                'version': version,
                'hweui': hweui,
                'frequency': freq,
                'spreading_factor': sf
            })
        return jsonify({'success': False, 'error': 'No response from module'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/lora/send', methods=['POST'])
def api_lora_send():
    """Send a LoRa message."""
    data = request.get_json() or {}
    message = data.get('message', 'HELLO')
    hex_data = message.encode().hex()

    try:
        result = lora_send_cmd(f"radio tx {hex_data}", delay=0.5)
        time.sleep(1)
        ser = get_lora()
        extra = ser.read(256).decode('utf-8', errors='replace').strip() if ser else ''

        success = 'ok' in (result or '').lower() or 'radio_tx_ok' in extra.lower()

        return jsonify({
            'success': success,
            'sent': message,
            'hex': hex_data,
            'response': result,
            'confirmation': extra
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/lora/test', methods=['POST'])
def api_lora_test():
    """Run LoRa packet delivery test."""
    data = request.get_json() or {}
    distance = data.get('distance', 0)
    packet_count = data.get('packet_count', 10)

    sent = 0
    confirmed = 0
    results = []

    for i in range(packet_count):
        msg = f"PKT{i:03d}"
        hex_data = msg.encode().hex()

        try:
            result = lora_send_cmd(f"radio tx {hex_data}", delay=0.5)
            time.sleep(1)
            ser = get_lora()
            extra = ser.read(256).decode('utf-8', errors='replace').strip() if ser else ''

            success = 'ok' in (result or '').lower() or 'radio_tx_ok' in extra.lower()
            sent += 1
            if success:
                confirmed += 1
            results.append({'packet': i, 'success': success})
        except Exception as e:
            results.append({'packet': i, 'success': False, 'error': str(e)})

        time.sleep(0.5)

    success_rate = (confirmed / sent * 100) if sent > 0 else 0
    packet_loss = 100 - success_rate

    log_result('LoRa', 'packet_test', distance, confirmed > 0, {
        'packet_loss_pct': round(packet_loss, 1),
        'notes': f'{confirmed}/{sent} packets confirmed'
    })

    return jsonify({
        'success': True,
        'sent': sent,
        'confirmed': confirmed,
        'success_rate': round(success_rate, 1),
        'packet_loss_pct': round(packet_loss, 1),
        'results': results
    })


# Results API endpoints
@app.route('/api/results')
def api_results():
    """Get test results."""
    if not os.path.exists(RESULTS_FILE):
        return jsonify({'success': True, 'results': []})

    results = []
    with open(RESULTS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)

    return jsonify({'success': True, 'results': results})


@app.route('/api/results/download')
def api_results_download():
    """Download results as CSV."""
    from flask import send_file
    if os.path.exists(RESULTS_FILE):
        return send_file(RESULTS_FILE, as_attachment=True)
    return jsonify({'error': 'No results file'}), 404


@app.route('/api/results/clear', methods=['POST'])
def api_results_clear():
    """Clear all results."""
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)
    return jsonify({'success': True})


# Pi Control API endpoints
@app.route('/api/pi/status')
def api_pi_status():
    """Check Pi status via SSH."""
    ssh_ok = check_pi_ssh()
    if not ssh_ok:
        return jsonify({'success': False, 'ssh': False, 'error': 'Cannot reach Pi via SSH'})

    # Check if responder is running
    result = run_on_pi('pgrep -f pi_responder.py')
    responder_running = result.get('success', False)

    # Check LoRa device on Pi
    lora_result = run_on_pi('ls /dev/ttyACM* 2>/dev/null || echo "none"')
    lora_device = lora_result.get('stdout', '').strip()
    lora_connected = lora_device and lora_device != 'none'

    return jsonify({
        'success': True,
        'ssh': True,
        'responder_running': responder_running,
        'lora_connected': lora_connected,
        'lora_device': lora_device if lora_connected else None
    })


@app.route('/api/pi/responder/start', methods=['POST'])
def api_pi_responder_start():
    """Start pi_responder.py on the Pi."""
    # First check if already running
    check = run_on_pi('pgrep -f pi_responder.py')
    if check.get('success'):
        return jsonify({'success': True, 'message': 'Already running'})

    # Start in background with nohup
    result = run_on_pi('nohup python3 ~/pi_responder.py > ~/responder.log 2>&1 &')
    time.sleep(2)  # Give it time to start

    # Verify it started
    check = run_on_pi('pgrep -f pi_responder.py')
    if check.get('success'):
        return jsonify({'success': True, 'message': 'Started'})
    return jsonify({'success': False, 'error': 'Failed to start'})


@app.route('/api/pi/responder/stop', methods=['POST'])
def api_pi_responder_stop():
    """Stop pi_responder.py on the Pi."""
    result = run_on_pi('pkill -f pi_responder.py')
    return jsonify({'success': True, 'message': 'Stopped'})


@app.route('/api/pi/adhoc/start', methods=['POST'])
def api_pi_adhoc_start():
    """Start WiFi ad-hoc on Pi."""
    # Check if adhoc.sh exists on Pi
    check = run_on_pi('ls ~/d2d/adhoc.sh 2>/dev/null || ls ~/adhoc.sh 2>/dev/null')
    if not check.get('success'):
        return jsonify({'success': False, 'error': 'adhoc.sh not found on Pi'})

    script_path = check.get('stdout', '').strip().split('\n')[0]
    result = run_on_pi(f'sudo {script_path} start pi', timeout=60)
    return jsonify({
        'success': result.get('success', False),
        'output': result.get('stdout', ''),
        'error': result.get('stderr', '')
    })


@app.route('/api/pi/adhoc/stop', methods=['POST'])
def api_pi_adhoc_stop():
    """Stop WiFi ad-hoc on Pi."""
    check = run_on_pi('ls ~/d2d/adhoc.sh 2>/dev/null || ls ~/adhoc.sh 2>/dev/null')
    if not check.get('success'):
        return jsonify({'success': False, 'error': 'adhoc.sh not found on Pi'})

    script_path = check.get('stdout', '').strip().split('\n')[0]
    result = run_on_pi(f'sudo {script_path} stop', timeout=60)
    return jsonify({
        'success': result.get('success', False),
        'output': result.get('stdout', ''),
        'error': result.get('stderr', '')
    })


# Pi LoRa mode control (proxy to Pi's responder API)
def call_pi_api(endpoint, method='GET', json_data=None):
    """Call the Pi responder API."""
    try:
        url = f'http://{PI_NORMAL_HOST}:{PI_PORT}{endpoint}'
        if method == 'GET':
            resp = requests.get(url, timeout=10)
        else:
            resp = requests.post(url, json=json_data, timeout=10)
        return resp.json()
    except Exception as e:
        return {'success': False, 'error': str(e)}


@app.route('/api/pi/lora/beacon/start', methods=['POST'])
def api_pi_lora_beacon_start():
    """Start LoRa beacon mode on Pi."""
    return jsonify(call_pi_api('/lora/beacon/start', 'POST', {'interval': 5}))


@app.route('/api/pi/lora/beacon/stop', methods=['POST'])
def api_pi_lora_beacon_stop():
    """Stop LoRa beacon mode on Pi."""
    return jsonify(call_pi_api('/lora/beacon/stop', 'POST'))


@app.route('/api/pi/lora/echo/start', methods=['POST'])
def api_pi_lora_echo_start():
    """Start LoRa echo mode on Pi."""
    return jsonify(call_pi_api('/lora/echo/start', 'POST'))


@app.route('/api/pi/lora/echo/stop', methods=['POST'])
def api_pi_lora_echo_stop():
    """Stop LoRa echo mode on Pi."""
    return jsonify(call_pi_api('/lora/echo/stop', 'POST'))


@app.route('/api/pi/lora/mode')
def api_pi_lora_mode():
    """Get Pi's current LoRa mode."""
    return jsonify(call_pi_api('/lora/mode'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Laptop Controller for D2D testing')
    parser.add_argument('--port', type=int, default=8080, help='Flask port')
    parser.add_argument('--lora-device', default='/dev/ttyACM0', help='LoRa serial device')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    args = parser.parse_args()

    LORA_DEVICE = args.lora_device

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║               D2D Communication Demo - Controller             ║
╠══════════════════════════════════════════════════════════════╣
║  Open in browser: http://localhost:{args.port}                    ║
║                                                               ║
║  Pi IPs:                                                      ║
║    WiFi Ad-hoc:  {PI_WIFI_IP}                               ║
║    Bluetooth:    {PI_BT_IP}                               ║
║                                                               ║
║  Make sure Pi is running pi_responder.py                     ║
║  (or use the Pi Control panel to start it remotely)          ║
╠══════════════════════════════════════════════════════════════╣
║  Note: Debug mode shows this banner twice on startup -       ║
║        this is normal Flask reloader behavior.               ║
╚══════════════════════════════════════════════════════════════╝
    """)

    app.run(host=args.host, port=args.port, debug=True, use_reloader=True)
