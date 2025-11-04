# Complete LoRa Testing Guide
## Point-to-Point Communication, Ping Testing, and File Transfer

---

## Table of Contents
1. [Understanding LoRa Fundamentals](#understanding-lora-fundamentals)
2. [Hardware Setup & Detection](#hardware-setup--detection)
3. [Manual Connection Testing](#manual-connection-testing)
4. [Automated Ping Script](#automated-ping-script)
5. [File Transfer Implementation](#file-transfer-implementation)
6. [Advanced Configuration Options](#advanced-configuration-options)
7. [Troubleshooting Guide](#troubleshooting-guide)

---

## Understanding LoRa Fundamentals

### What is LoRa?
LoRa (Long Range) is a proprietary spread spectrum modulation technique that operates in sub-gigahertz frequency bands. Unlike WiFi or Bluetooth, LoRa is designed for:
- **Long-range communication** (2-15km in rural areas, 2-5km in urban areas)
- **Low power consumption** (battery can last years)
- **Low data rates** (0.3 kbps to 50 kbps)
- **High penetration** through obstacles

### Key LoRa Parameters Explained

```python
# Understanding each parameter's impact on communication

FREQUENCY = 915.0  # MHz (or 433.0, 868.0 depending on region)
# - 433 MHz: Better penetration, longer range, slower data rate
# - 868 MHz: European standard, balanced performance
# - 915 MHz: North American standard, higher data rate possible

SPREADING_FACTOR = 7  # Range: 7-12
# - SF7: Fastest data rate (50 kbps), shortest range, least interference resistance
# - SF12: Slowest data rate (0.3 kbps), longest range, best interference resistance
# - Each +1 SF doubles transmission time, increases range by ~2.5dB

BANDWIDTH = 125  # kHz (can be 125, 250, 500)
# - 125 kHz: Longest range, slowest data rate, best sensitivity
# - 250 kHz: Medium range and speed
# - 500 kHz: Shortest range, fastest data rate, worst sensitivity
# - Formula: Data Rate = SF * (BW/2^SF) * CR

CODING_RATE = 5  # 4/5 (can be 5-8, representing 4/5 to 4/8)
# - 4/5: Least redundancy, fastest, least error correction
# - 4/8: Most redundancy, slowest, best error correction
# - Higher values = more reliable but slower

TX_POWER = 20  # dBm (2-20 for most modules)
# - 2 dBm: ~1.6mW, shortest range, least battery drain
# - 14 dBm: ~25mW, medium range
# - 20 dBm: ~100mW, maximum range, highest battery drain
# - Each +3dBm doubles transmission power

SYNC_WORD = 0x12  # Network ID (0x00-0xFF)
# - Must match between devices to communicate
# - 0x12: Private networks (default)
# - 0x34: Public LoRaWAN networks
# - Acts like a network filter

PREAMBLE_LENGTH = 8  # symbols (6-65535)
# - Longer = more reliable detection, more power/time
# - Shorter = faster transmission, may miss packets
# - Default 8 is good balance
```

### LoRa vs LoRaWAN
- **LoRa**: Physical layer, point-to-point, what we're using
- **LoRaWAN**: Network protocol built on LoRa, requires gateway, cloud connectivity

---

## Hardware Setup & Detection

### Common LoRa Modules

#### 1. SX1276/SX1278 Based Modules
```bash
# RFM95W, RFM96W, RFM98W (HopeRF)
# - Most common, well-supported
# - 20dBm max power
# - SPI interface

# Dragino LoRa/GPS HAT
# - Raspberry Pi HAT form factor
# - Includes GPS receiver
# - Uses SPI0, CE1
```

#### 2. SX1262 Based Modules (Newer)
```bash
# RFM95W-V2.0, LLCC68
# - Lower power consumption
# - Better receiver sensitivity
# - More configuration options
```

### Initial Hardware Detection

```bash
# Check if SPI is enabled (Raspberry Pi)
ls /dev/spidev*
# Should show: /dev/spidev0.0  /dev/spidev0.1

# Enable SPI if needed
sudo raspi-config
# Interface Options -> SPI -> Enable

# Check GPIO access
gpio readall  # Shows pin status

# Install detection tools
pip3 install spidev RPi.GPIO pyLoRa

# Python detection script
cat > detect_lora.py << 'EOF'
#!/usr/bin/env python3
import spidev
import RPi.GPIO as GPIO
import time

# Pin configuration (adjust for your module)
NSS_PIN = 8    # CE0 or CE1
DIO0_PIN = 24  # Interrupt pin
RESET_PIN = 22 # Reset pin

def detect_lora():
    """Detect LoRa module presence"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RESET_PIN, GPIO.OUT)
    GPIO.setup(NSS_PIN, GPIO.OUT)
    GPIO.setup(DIO0_PIN, GPIO.IN)
    
    # Reset module
    GPIO.output(RESET_PIN, GPIO.LOW)
    time.sleep(0.01)
    GPIO.output(RESET_PIN, GPIO.HIGH)
    time.sleep(0.01)
    
    # Try SPI communication
    spi = spidev.SpiDev()
    spi.open(0, 0)  # bus 0, device 0
    spi.max_speed_hz = 5000000
    
    # Read version register (0x42)
    version = spi.xfer([0x42 & 0x7F, 0x00])[1]
    
    if version == 0x12:
        print("✓ SX1276/77/78/79 detected!")
        return True
    elif version == 0x22:
        print("✓ SX1262 detected!")
        return True
    else:
        print(f"✗ Unknown device (version: 0x{version:02X})")
        return False
    
    spi.close()
    GPIO.cleanup()

if __name__ == "__main__":
    detect_lora()
EOF

python3 detect_lora.py
```

---

## Manual Connection Testing

### Basic Python LoRa Library Setup

```bash
# Install pyLoRa library
git clone https://github.com/rpsreal/pySX127x
cd pySX127x
pip3 install -e .

# Or use the simpler raspi-lora
pip3 install raspi-lora
```

### Manual Transmitter Script

```python
#!/usr/bin/env python3
# lora_transmitter.py - Detailed manual transmission

from time import sleep
from SX127x.LoRa import *
from SX127x.board_config import BOARD
import RPi.GPIO as GPIO

# Initialize board
BOARD.setup()

class LoRaTransmitter(LoRa):
    def __init__(self, verbose=True):
        super(LoRaTransmitter, self).__init__(verbose)
        self.set_mode(MODE.SLEEP)
        
        # Configure LoRa parameters with explanations
        self.set_dio_mapping([1,0,0,0,0,0])  # DIO0=TxDone, DIO1=RxTimeout
        
        # Frequency configuration
        # Calculate: freq_reg = freq_mhz * (2^19) / 32
        self.set_freq(915.0)  # MHz - Must match between devices
        
        # Power Amplifier configuration
        self.set_pa_config(
            pa_select=1,    # 1=PA_BOOST pin (up to +20dBm)
                           # 0=RFO pin (up to +14dBm, better efficiency)
            max_power=7,    # Only used for PA_SELECT=1
            output_power=15 # Actual power in dBm (2-20)
        )
        
        # Modulation parameters
        self.set_spreading_factor(7)   # SF7 = 128 chips/symbol
        self.set_bw(BW.BW125)          # 125kHz bandwidth
        self.set_coding_rate(CODING_RATE.CR4_5)  # 4/5 FEC rate
        
        # Packet configuration
        self.set_preamble(8)            # 8 symbols preamble
        self.set_sync_word(0x12)        # Private network sync
        self.set_rx_crc(True)           # Enable CRC checking
        
        # LNA (Low Noise Amplifier) for receiving
        self.set_lna_gain(GAIN.G1)     # Maximum gain
        self.set_agc_auto(True)        # Auto gain control
        
        print("LoRa Transmitter Configuration:")
        print(f"  Frequency: {self.get_freq():.1f} MHz")
        print(f"  Spreading Factor: {self.get_spreading_factor()}")
        print(f"  Bandwidth: {self.get_bw()} kHz")
        print(f"  Coding Rate: 4/{self.get_coding_rate()}")
        print(f"  Sync Word: 0x{self.get_sync_word():02X}")
        
    def transmit_packet(self, message):
        """Transmit a single packet with timing info"""
        self.set_mode(MODE.STDBY)  # Must be in standby to write FIFO
        
        # Prepare payload
        payload = list(message.encode())
        self.write_payload(payload)
        
        print(f"TX: '{message}' ({len(payload)} bytes)")
        
        # Calculate air time (approximate)
        # Time = (symbols * 2^SF) / BW
        symbols = 8 + max((8*len(payload) - 4*self.get_spreading_factor() + 28), 0)
        air_time_ms = symbols * (2**self.get_spreading_factor()) / 125
        print(f"  Estimated air time: {air_time_ms:.1f} ms")
        
        # Start transmission
        self.set_mode(MODE.TX)
        
        # Wait for transmission complete (DIO0 interrupt)
        start_time = time.time()
        while self.get_irq_flags()['tx_done'] == 0:
            sleep(0.001)
        
        actual_time = (time.time() - start_time) * 1000
        print(f"  Actual transmit time: {actual_time:.1f} ms")
        
        # Clear IRQ
        self.clear_irq_flags(TxDone=1)
        self.set_mode(MODE.STDBY)

# Usage
if __name__ == "__main__":
    lora = LoRaTransmitter(verbose=True)
    
    try:
        while True:
            lora.transmit_packet("Hello LoRa!")
            sleep(2)
            
            # Send different packet types
            lora.transmit_packet(f"Time: {int(time.time())}")
            sleep(2)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        lora.set_mode(MODE.SLEEP)
        BOARD.teardown()
```

### Manual Receiver Script

```python
#!/usr/bin/env python3
# lora_receiver.py - Detailed manual reception

from time import sleep
from SX127x.LoRa import *
from SX127x.board_config import BOARD
import RPi.GPIO as GPIO

BOARD.setup()

class LoRaReceiver(LoRa):
    def __init__(self, verbose=True):
        super(LoRaReceiver, self).__init__(verbose)
        self.set_mode(MODE.SLEEP)
        
        # Must match transmitter configuration exactly!
        self.set_dio_mapping([0,0,0,0,0,0])  # DIO0=RxDone
        self.set_freq(915.0)
        self.set_pa_config(pa_select=1, max_power=7, output_power=15)
        self.set_spreading_factor(7)
        self.set_bw(BW.BW125)
        self.set_coding_rate(CODING_RATE.CR4_5)
        self.set_preamble(8)
        self.set_sync_word(0x12)
        self.set_rx_crc(True)
        self.set_lna_gain(GAIN.G1)
        self.set_agc_auto(True)
        
        print("LoRa Receiver Ready")
        print(f"Listening on {self.get_freq():.1f} MHz...")
        
    def on_rx_done(self):
        """Called when packet received (interrupt handler)"""
        # Get packet data
        payload = self.read_payload(nocheck=True)
        
        # Decode message
        try:
            message = bytes(payload).decode('utf-8', errors='ignore')
        except:
            message = str(payload)
        
        # Get signal statistics
        rssi = self.get_pkt_rssi_value()      # Received Signal Strength
        snr = self.get_pkt_snr_value()        # Signal-to-Noise Ratio
        freq_error = self.get_freq_error()     # Frequency offset
        
        print(f"\n=== Packet Received ===")
        print(f"Message: '{message}'")
        print(f"Length: {len(payload)} bytes")
        print(f"RSSI: {rssi} dBm")
        print(f"SNR: {snr:.1f} dB")
        print(f"Freq Error: {freq_error:.1f} Hz")
        
        # Signal quality interpretation
        if rssi > -50:
            quality = "Excellent"
        elif rssi > -80:
            quality = "Good"
        elif rssi > -100:
            quality = "Fair"
        else:
            quality = "Poor"
        print(f"Signal Quality: {quality}")
        
        # Calculate distance estimate (free space path loss)
        # Distance = 10^((Tx_Power - RSSI - 32.45 - 20*log10(freq_mhz))/20)
        import math
        tx_power = 20  # Assuming 20dBm transmit
        path_loss = tx_power - rssi
        freq_mhz = self.get_freq()
        distance_m = 10**((path_loss - 32.45 - 20*math.log10(freq_mhz))/20)
        print(f"Estimated Distance: {distance_m:.0f} meters (free space)")
        
    def start_receive(self):
        """Put module in continuous receive mode"""
        self.reset_ptr_rx()  # Reset FIFO pointer
        self.set_mode(MODE.RXCONT)  # Continuous receive mode
        
        while True:
            sleep(0.1)
            # Check for received packet
            if self.get_irq_flags()['rx_done']:
                self.clear_irq_flags(RxDone=1)
                self.on_rx_done()
                self.set_mode(MODE.RXCONT)  # Back to RX mode

# Usage
if __name__ == "__main__":
    lora = LoRaReceiver(verbose=False)
    
    try:
        lora.start_receive()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        lora.set_mode(MODE.SLEEP)
        BOARD.teardown()
```

---

## Automated Ping Script

```python
#!/usr/bin/env python3
# lora_ping.py - Automated ping test with statistics

import time
import threading
import json
from datetime import datetime
from SX127x.LoRa import *
from SX127x.board_config import BOARD

class LoRaPing(LoRa):
    def __init__(self, node_id="NODE_A", ping_mode=True):
        super(LoRaPing, self).__init__(verbose=False)
        self.node_id = node_id
        self.ping_mode = ping_mode  # True=sender, False=responder
        self.stats = {
            'sent': 0,
            'received': 0,
            'lost': 0,
            'rtt_min': float('inf'),
            'rtt_max': 0,
            'rtt_avg': 0,
            'rtt_total': 0,
            'rssi_min': float('inf'),
            'rssi_max': float('-inf'),
            'rssi_avg': 0,
            'rssi_total': 0
        }
        self.pending_pings = {}
        self.configure_lora()
        
    def configure_lora(self):
        """Standard configuration for both nodes"""
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([0,0,0,0,0,0])
        self.set_freq(915.0)
        self.set_pa_config(pa_select=1, max_power=7, output_power=20)
        self.set_spreading_factor(7)
        self.set_bw(BW.BW125)
        self.set_coding_rate(CODING_RATE.CR4_5)
        self.set_preamble(8)
        self.set_sync_word(0x12)
        self.set_rx_crc(True)
        self.set_lna_gain(GAIN.G1)
        self.set_agc_auto(True)
        
    def create_ping_packet(self, seq):
        """Create ping packet with metadata"""
        packet = {
            'type': 'PING',
            'from': self.node_id,
            'seq': seq,
            'time': time.time()
        }
        return json.dumps(packet)
    
    def create_pong_packet(self, ping_packet):
        """Create response packet"""
        packet = {
            'type': 'PONG',
            'from': self.node_id,
            'seq': ping_packet['seq'],
            'ping_time': ping_packet['time']
        }
        return json.dumps(packet)
    
    def send_packet(self, data):
        """Send a packet"""
        self.set_mode(MODE.STDBY)
        payload = list(data.encode())[:255]  # Max 255 bytes
        self.write_payload(payload)
        self.set_mode(MODE.TX)
        
        # Wait for TX complete
        timeout = time.time() + 5
        while time.time() < timeout:
            if self.get_irq_flags()['tx_done']:
                self.clear_irq_flags(TxDone=1)
                return True
        return False
    
    def receive_packet(self, timeout=1.0):
        """Receive a packet with timeout"""
        self.set_mode(MODE.RXCONT)
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            if self.get_irq_flags()['rx_done']:
                self.clear_irq_flags(RxDone=1)
                
                # Read packet
                payload = self.read_payload(nocheck=True)
                rssi = self.get_pkt_rssi_value()
                snr = self.get_pkt_snr_value()
                
                try:
                    message = bytes(payload).decode('utf-8')
                    packet = json.loads(message)
                    return packet, rssi, snr
                except:
                    pass
                    
        return None, None, None
    
    def run_ping_sender(self, target_id="NODE_B", count=10, interval=1.0):
        """Send ping packets and wait for responses"""
        print(f"PING {target_id}: {count} packets, {interval}s interval")
        print("=" * 50)
        
        for seq in range(1, count + 1):
            # Send ping
            ping_data = self.create_ping_packet(seq)
            send_time = time.time()
            
            if self.send_packet(ping_data):
                self.stats['sent'] += 1
                self.pending_pings[seq] = send_time
                
                # Wait for pong
                packet, rssi, snr = self.receive_packet(timeout=2.0)
                
                if packet and packet['type'] == 'PONG':
                    rtt = (time.time() - send_time) * 1000  # ms
                    self.stats['received'] += 1
                    
                    # Update RTT stats
                    self.stats['rtt_total'] += rtt
                    self.stats['rtt_min'] = min(self.stats['rtt_min'], rtt)
                    self.stats['rtt_max'] = max(self.stats['rtt_max'], rtt)
                    self.stats['rtt_avg'] = self.stats['rtt_total'] / self.stats['received']
                    
                    # Update RSSI stats
                    self.stats['rssi_total'] += rssi
                    self.stats['rssi_min'] = min(self.stats['rssi_min'], rssi)
                    self.stats['rssi_max'] = max(self.stats['rssi_max'], rssi)
                    self.stats['rssi_avg'] = self.stats['rssi_total'] / self.stats['received']
                    
                    print(f"[{seq}] Reply from {packet['from']}: " +
                          f"time={rtt:.1f}ms RSSI={rssi}dBm SNR={snr:.1f}dB")
                else:
                    self.stats['lost'] += 1
                    print(f"[{seq}] Request timeout")
            else:
                print(f"[{seq}] Transmission failed")
                self.stats['lost'] += 1
            
            if seq < count:
                time.sleep(interval)
        
        # Print statistics
        self.print_statistics()
    
    def run_pong_responder(self):
        """Respond to ping packets"""
        print(f"LoRa Ping Responder - {self.node_id}")
        print("Waiting for ping packets...")
        print("=" * 50)
        
        while True:
            packet, rssi, snr = self.receive_packet(timeout=10.0)
            
            if packet and packet['type'] == 'PING':
                print(f"Ping from {packet['from']}: seq={packet['seq']} " +
                      f"RSSI={rssi}dBm SNR={snr:.1f}dB")
                
                # Send pong response
                pong_data = self.create_pong_packet(packet)
                if self.send_packet(pong_data):
                    print(f"  → Sent pong response")
                else:
                    print(f"  → Failed to send pong")
    
    def print_statistics(self):
        """Print ping statistics"""
        print("\n" + "=" * 50)
        print("--- LoRa Ping Statistics ---")
        print(f"Packets: Sent = {self.stats['sent']}, " +
              f"Received = {self.stats['received']}, " +
              f"Lost = {self.stats['lost']} " +
              f"({self.stats['lost']/self.stats['sent']*100:.1f}% loss)")
        
        if self.stats['received'] > 0:
            print(f"Round-trip times (ms):")
            print(f"  Min/Avg/Max = {self.stats['rtt_min']:.1f}/" +
                  f"{self.stats['rtt_avg']:.1f}/" +
                  f"{self.stats['rtt_max']:.1f}")
            print(f"Signal strength (dBm):")
            print(f"  Min/Avg/Max = {self.stats['rssi_min']}/" +
                  f"{self.stats['rssi_avg']:.0f}/" +
                  f"{self.stats['rssi_max']}")

# Main execution
if __name__ == "__main__":
    import sys
    
    BOARD.setup()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Sender:    python3 lora_ping.py send [count] [interval]")
        print("  Responder: python3 lora_ping.py respond")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    try:
        if mode == "send":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            interval = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
            
            ping = LoRaPing(node_id="NODE_A", ping_mode=True)
            ping.run_ping_sender(target_id="NODE_B", count=count, interval=interval)
            
        elif mode == "respond":
            ping = LoRaPing(node_id="NODE_B", ping_mode=False)
            ping.run_pong_responder()
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        BOARD.teardown()
```

---

## File Transfer Implementation

```python
#!/usr/bin/env python3
# lora_file_transfer.py - Reliable file transfer over LoRa

import os
import time
import hashlib
import base64
import json
from enum import Enum
from SX127x.LoRa import *
from SX127x.board_config import BOARD

class PacketType(Enum):
    FILE_INFO = 1
    FILE_DATA = 2
    FILE_ACK = 3
    FILE_NACK = 4
    FILE_COMPLETE = 5
    FILE_ABORT = 6

class LoRaFileTransfer(LoRa):
    def __init__(self, node_id="NODE"):
        super(LoRaFileTransfer, self).__init__(verbose=False)
        self.node_id = node_id
        self.chunk_size = 200  # Max payload size (leave room for headers)
        self.window_size = 5   # Sliding window for flow control
        self.timeout = 5.0     # Seconds
        self.max_retries = 3
        self.configure_lora()
        
    def configure_lora(self):
        """Configure for reliable transfer (lower SF for speed)"""
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([0,0,0,0,0,0])
        self.set_freq(915.0)
        self.set_pa_config(pa_select=1, max_power=7, output_power=20)
        
        # SF7 for faster transfer (sacrifice range for speed)
        self.set_spreading_factor(7)
        self.set_bw(BW.BW250)  # Higher bandwidth for speed
        self.set_coding_rate(CODING_RATE.CR4_5)
        
        self.set_preamble(8)
        self.set_sync_word(0x12)
        self.set_rx_crc(True)
        self.set_lna_gain(GAIN.G1)
        self.set_agc_auto(True)
        
        # Calculate data rate
        sf = 7
        bw = 250000  # Hz
        cr = 1.25  # 4/5
        data_rate = sf * (bw / (2**sf)) * cr / 1000  # kbps
        print(f"Configured for ~{data_rate:.1f} kbps data rate")
    
    def send_file(self, filepath, dest_node="NODE_B"):
        """Send a file with reliability mechanisms"""
        if not os.path.exists(filepath):
            print(f"Error: File {filepath} not found")
            return False
        
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        
        # Calculate file hash
        with open(filepath, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        print(f"Sending file: {filename}")
        print(f"Size: {filesize} bytes")
        print(f"Hash: {file_hash}")
        print(f"Chunk size: {self.chunk_size} bytes")
        
        # Calculate chunks
        num_chunks = (filesize + self.chunk_size - 1) // self.chunk_size
        print(f"Total chunks: {num_chunks}")
        
        # Step 1: Send file info
        file_info = {
            'type': PacketType.FILE_INFO.value,
            'from': self.node_id,
            'to': dest_node,
            'filename': filename,
            'filesize': filesize,
            'hash': file_hash,
            'chunks': num_chunks,
            'chunk_size': self.chunk_size
        }
        
        print("\n[1/3] Sending file info...")
        if not self.send_packet_reliable(json.dumps(file_info)):
            print("Failed to send file info")
            return False
        
        # Wait for acknowledgment
        response = self.wait_for_ack(PacketType.FILE_INFO)
        if not response:
            print("No acknowledgment for file info")
            return False
        
        # Step 2: Send file data chunks
        print("\n[2/3] Sending file data...")
        with open(filepath, 'rb') as f:
            chunk_num = 0
            sent_chunks = 0
            window_base = 0
            pending_acks = {}
            
            while chunk_num < num_chunks:
                # Send window of chunks
                while (chunk_num < num_chunks and 
                       chunk_num < window_base + self.window_size):
                    
                    f.seek(chunk_num * self.chunk_size)
                    chunk_data = f.read(self.chunk_size)
                    
                    # Create data packet
                    data_packet = {
                        'type': PacketType.FILE_DATA.value,
                        'from': self.node_id,
                        'to': dest_node,
                        'chunk': chunk_num,
                        'total': num_chunks,
                        'data': base64.b64encode(chunk_data).decode()
                    }
                    
                    # Send chunk
                    if self.send_packet(json.dumps(data_packet)):
                        pending_acks[chunk_num] = time.time()
                        sent_chunks += 1
                        
                        # Progress indicator
                        progress = (sent_chunks / num_chunks) * 100
                        print(f"\rProgress: [{sent_chunks}/{num_chunks}] " +
                              f"{progress:.1f}%", end='')
                    
                    chunk_num += 1
                
                # Wait for ACKs and slide window
                ack_timeout = time.time() + self.timeout
                while window_base in pending_acks and time.time() < ack_timeout:
                    packet, _, _ = self.receive_packet(0.1)
                    if packet and packet.get('type') == PacketType.FILE_ACK.value:
                        acked_chunk = packet.get('chunk')
                        if acked_chunk in pending_acks:
                            del pending_acks[acked_chunk]
                            if acked_chunk == window_base:
                                window_base += 1
                                while window_base not in pending_acks and window_base < chunk_num:
                                    window_base += 1
                
                # Handle timeouts/retransmissions
                for chunk in list(pending_acks.keys()):
                    if time.time() - pending_acks[chunk] > self.timeout:
                        print(f"\nRetransmitting chunk {chunk}")
                        # Retransmit logic here
                        chunk_num = min(chunk_num, chunk)
                        break
        
        print("\n")
        
        # Step 3: Send completion signal
        print("[3/3] Sending completion signal...")
        complete_packet = {
            'type': PacketType.FILE_COMPLETE.value,
            'from': self.node_id,
            'to': dest_node,
            'filename': filename,
            'hash': file_hash
        }
        
        if self.send_packet_reliable(json.dumps(complete_packet)):
            print(f"✓ File transfer complete: {filename}")
            return True
        
        return False
    
    def receive_file(self, save_dir="./received"):
        """Receive a file with reliability"""
        os.makedirs(save_dir, exist_ok=True)
        print("Waiting for file transfer...")
        
        file_info = None
        received_chunks = {}
        
        while True:
            packet, rssi, snr = self.receive_packet(10.0)
            
            if not packet:
                continue
            
            packet_type = PacketType(packet.get('type', 0))
            
            if packet_type == PacketType.FILE_INFO:
                # Received file info
                file_info = packet
                print(f"\nReceiving file: {file_info['filename']}")
                print(f"Size: {file_info['filesize']} bytes")
                print(f"Chunks: {file_info['chunks']}")
                
                # Send ACK
                self.send_ack(PacketType.FILE_INFO, packet['from'])
                received_chunks = {}
                
            elif packet_type == PacketType.FILE_DATA and file_info:
                # Received data chunk
                chunk_num = packet['chunk']
                chunk_data = base64.b64decode(packet['data'])
                received_chunks[chunk_num] = chunk_data
                
                # Send ACK for chunk
                ack_packet = {
                    'type': PacketType.FILE_ACK.value,
                    'from': self.node_id,
                    'to': packet['from'],
                    'chunk': chunk_num
                }
                self.send_packet(json.dumps(ack_packet))
                
                # Progress
                progress = (len(received_chunks) / file_info['chunks']) * 100
                print(f"\rProgress: [{len(received_chunks)}/{file_info['chunks']}] " +
                      f"{progress:.1f}%", end='')
                
            elif packet_type == PacketType.FILE_COMPLETE and file_info:
                print("\n\nFile transfer complete, assembling file...")
                
                # Assemble file
                filepath = os.path.join(save_dir, file_info['filename'])
                with open(filepath, 'wb') as f:
                    for i in range(file_info['chunks']):
                        if i in received_chunks:
                            f.write(received_chunks[i])
                        else:
                            print(f"Warning: Missing chunk {i}")
                
                # Verify hash
                with open(filepath, 'rb') as f:
                    received_hash = hashlib.md5(f.read()).hexdigest()
                
                if received_hash == packet['hash']:
                    print(f"✓ File saved successfully: {filepath}")
                    print(f"✓ Hash verified: {received_hash}")
                else:
                    print(f"✗ Hash mismatch! Expected: {packet['hash']}")
                    print(f"  Received: {received_hash}")
                
                # Send final ACK
                self.send_ack(PacketType.FILE_COMPLETE, packet['from'])
                break
    
    def send_packet(self, data):
        """Send a single packet"""
        self.set_mode(MODE.STDBY)
        payload = list(data.encode())[:255]
        self.write_payload(payload)
        self.set_mode(MODE.TX)
        
        timeout = time.time() + 5
        while time.time() < timeout:
            if self.get_irq_flags()['tx_done']:
                self.clear_irq_flags(TxDone=1)
                return True
        return False
    
    def send_packet_reliable(self, data, max_retries=3):
        """Send packet with retries"""
        for attempt in range(max_retries):
            if self.send_packet(data):
                return True
            print(f"Retry {attempt + 1}/{max_retries}")
            time.sleep(0.5)
        return False
    
    def receive_packet(self, timeout=1.0):
        """Receive a packet"""
        self.set_mode(MODE.RXCONT)
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            if self.get_irq_flags()['rx_done']:
                self.clear_irq_flags(RxDone=1)
                payload = self.read_payload(nocheck=True)
                rssi = self.get_pkt_rssi_value()
                snr = self.get_pkt_snr_value()
                
                try:
                    message = bytes(payload).decode('utf-8')
                    packet = json.loads(message)
                    return packet, rssi, snr
                except:
                    pass
        
        return None, None, None
    
    def send_ack(self, packet_type, to_node):
        """Send acknowledgment"""
        ack = {
            'type': PacketType.FILE_ACK.value,
            'from': self.node_id,
            'to': to_node,
            'ack_type': packet_type.value
        }
        return self.send_packet(json.dumps(ack))
    
    def wait_for_ack(self, expected_type, timeout=5.0):
        """Wait for specific acknowledgment"""
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            packet, _, _ = self.receive_packet(0.5)
            if (packet and 
                packet.get('type') == PacketType.FILE_ACK.value and
                packet.get('ack_type') == expected_type.value):
                return packet
        return None

# Main execution
if __name__ == "__main__":
    import sys
    
    BOARD.setup()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Send:    python3 lora_file_transfer.py send <filepath>")
        print("  Receive: python3 lora_file_transfer.py receive [save_dir]")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    try:
        transfer = LoRaFileTransfer(node_id="NODE_A" if mode == "send" else "NODE_B")
        
        if mode == "send" and len(sys.argv) > 2:
            filepath = sys.argv[2]
            transfer.send_file(filepath, dest_node="NODE_B")
            
        elif mode == "receive":
            save_dir = sys.argv[2] if len(sys.argv) > 2 else "./received"
            transfer.receive_file(save_dir)
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        BOARD.teardown()
```

---

## Advanced Configuration Options

### 1. Adaptive Data Rate (ADR)

```python
class AdaptiveLoRa:
    """Automatically adjust SF based on link quality"""
    
    def __init__(self):
        self.rssi_history = []
        self.sf_current = 7
        
    def adapt_spreading_factor(self, rssi):
        """Adjust SF based on RSSI"""
        self.rssi_history.append(rssi)
        if len(self.rssi_history) > 10:
            self.rssi_history.pop(0)
        
        avg_rssi = sum(self.rssi_history) / len(self.rssi_history)
        
        # SF adjustment thresholds
        if avg_rssi > -80 and self.sf_current > 7:
            # Good signal, decrease SF for speed
            self.sf_current -= 1
            print(f"ADR: Decreasing to SF{self.sf_current}")
        elif avg_rssi < -110 and self.sf_current < 12:
            # Poor signal, increase SF for range
            self.sf_current += 1
            print(f"ADR: Increasing to SF{self.sf_current}")
        
        return self.sf_current
```

### 2. Frequency Hopping

```python
class FrequencyHopping:
    """Implement FHSS for interference avoidance"""
    
    def __init__(self):
        # Define channel list (US915 band)
        self.channels = [
            902.3, 902.5, 902.7, 902.9, 903.1,
            903.3, 903.5, 903.7, 903.9, 904.1
        ]
        self.current_channel = 0
        self.hop_pattern = self.generate_hop_pattern()
    
    def generate_hop_pattern(self, seed=0x12):
        """Generate pseudo-random hop pattern"""
        import random
        random.seed(seed)  # Same seed = same pattern
        pattern = self.channels.copy()
        random.shuffle(pattern)
        return pattern
    
    def next_channel(self):
        """Get next frequency in hop sequence"""
        freq = self.hop_pattern[self.current_channel]
        self.current_channel = (self.current_channel + 1) % len(self.hop_pattern)
        return freq
```

### 3. Listen Before Talk (LBT)

```python
def listen_before_talk(lora, threshold=-80, duration=0.1):
    """Check if channel is clear before transmitting"""
    lora.set_mode(MODE.CAD)  # Channel Activity Detection
    
    start_time = time.time()
    while (time.time() - start_time) < duration:
        if lora.get_irq_flags()['cad_done']:
            if lora.get_irq_flags()['cad_detected']:
                # Channel busy
                print("Channel busy, waiting...")
                time.sleep(random.uniform(0.1, 0.5))
                return False
            else:
                # Channel clear
                return True
    
    return True
```

---

## Troubleshooting Guide

### Common Issues and Solutions

```bash
# 1. Module Not Detected
# Check SPI enabled
ls /dev/spidev*
# Enable: sudo raspi-config -> Interfacing -> SPI

# 2. Permission Denied
# Add user to spi/gpio groups
sudo usermod -a -G spi,gpio $USER
# Logout and login again

# 3. High Packet Loss
# Check antenna connection
# Reduce data rate (increase SF)
# Check for interference (WiFi on 2.4GHz)

# 4. Short Range
# Check antenna (should be straight, vertical)
# Increase TX power
# Increase spreading factor
# Check for obstacles (walls, metal)

# 5. Slow Transfer Speed
# Reduce SF (if signal allows)
# Increase bandwidth
# Optimize packet size

# 6. Module Heating Up
# Reduce TX power
# Add delay between transmissions
# Check duty cycle regulations
```

### Spectrum Analyzer (Poor Man's Version)

```python
def spectrum_scan(lora, start_freq=902, end_freq=928, step=0.2):
    """Scan spectrum for interference"""
    print(f"Scanning {start_freq}-{end_freq} MHz...")
    results = []
    
    freq = start_freq
    while freq <= end_freq:
        lora.set_freq(freq)
        lora.set_mode(MODE.RXCONT)
        
        # Measure RSSI
        time.sleep(0.01)
        rssi = lora.get_rssi_value()
        results.append((freq, rssi))
        
        # Display
        bar = '#' * max(0, int((rssi + 120) / 2))
        print(f"{freq:5.1f} MHz: {rssi:4d} dBm {bar}")
        
        freq += step
    
    # Find clearest frequency
    clearest = min(results, key=lambda x: x[1])
    print(f"\nClearest frequency: {clearest[0]} MHz ({clearest[1]} dBm)")
    
    return results
```

### Legal Considerations

```python
# Duty Cycle Calculator (EU requirement: 1% duty cycle)
def calculate_duty_cycle(sf, bw_khz, payload_bytes, transmissions_per_hour):
    """Calculate duty cycle for regulatory compliance"""
    
    # Time on air calculation (simplified)
    symbols = 8 + max((8*payload_bytes - 4*sf + 28), 0)
    time_on_air_ms = symbols * (2**sf) / bw_khz
    
    # Duty cycle
    time_per_hour_ms = transmissions_per_hour * time_on_air_ms
    duty_cycle_percent = (time_per_hour_ms / 3600000) * 100
    
    print(f"Configuration: SF{sf}, BW={bw_khz}kHz, {payload_bytes} bytes")
    print(f"Time on air: {time_on_air_ms:.1f} ms per packet")
    print(f"Duty cycle: {duty_cycle_percent:.3f}% at {transmissions_per_hour} tx/hour")
    
    if duty_cycle_percent > 1.0:
        print("⚠️  WARNING: Exceeds 1% duty cycle regulation!")
        max_tx = int(36000 / time_on_air_ms)
        print(f"   Maximum transmissions: {max_tx} per hour")
    
    return duty_cycle_percent

# Example check
calculate_duty_cycle(sf=7, bw_khz=125, payload_bytes=50, transmissions_per_hour=100)
```

This guide provides everything needed for LoRa testing, from basic concepts to advanced implementations!
