#!/usr/bin/env python3
"""
LoRa Test Suite - All-in-one testing script for LoRa communication
Supports: Detection, Ping, File Transfer, Spectrum Scan, and more

Author: LoRa Testing Framework
License: MIT
"""

import os
import sys
import time
import json
import base64
import hashlib
import argparse
import threading
from enum import Enum
from datetime import datetime

# Try to import LoRa libraries
try:
    from SX127x.LoRa import *
    from SX127x.board_config import BOARD
    import RPi.GPIO as GPIO
    LORA_AVAILABLE = True
except ImportError:
    LORA_AVAILABLE = False
    print("Warning: LoRa libraries not installed. Run in simulation mode.")
    print("Install with: pip3 install pyLoRa RPi.GPIO spidev")

# ============================================================================
# Configuration Constants
# ============================================================================

class Config:
    """LoRa Configuration Parameters"""
    # Frequency bands by region
    FREQ_US = 915.0      # MHz - US915 band
    FREQ_EU = 868.0      # MHz - EU868 band  
    FREQ_AS = 433.0      # MHz - AS433 band
    FREQ_AU = 915.0      # MHz - AU915 band
    
    # Default configuration
    DEFAULT_FREQ = FREQ_US
    DEFAULT_SF = 7        # Spreading Factor (7-12)
    DEFAULT_BW = 125      # Bandwidth in kHz (125, 250, 500)
    DEFAULT_CR = 5        # Coding Rate 4/5 (5-8)
    DEFAULT_POWER = 20    # TX Power in dBm (2-20)
    DEFAULT_SYNC = 0x12   # Sync word for private network
    
    # File transfer settings
    CHUNK_SIZE = 200      # Bytes per packet
    WINDOW_SIZE = 5       # Sliding window size
    TIMEOUT = 5.0         # Seconds
    MAX_RETRIES = 3       # Retransmission attempts

# ============================================================================
# Base LoRa Class
# ============================================================================

class LoRaNode:
    """Base class for LoRa operations"""
    
    def __init__(self, node_id="NODE", freq=None, sf=None, bw=None):
        self.node_id = node_id
        self.freq = freq or Config.DEFAULT_FREQ
        self.sf = sf or Config.DEFAULT_SF
        self.bw = bw or Config.DEFAULT_BW
        
        if LORA_AVAILABLE:
            self.setup_hardware()
        else:
            print("Running in simulation mode")
            self.lora = None
    
    def setup_hardware(self):
        """Initialize LoRa hardware"""
        BOARD.setup()
        
        class LoRaTransceiver(LoRa):
            def __init__(self_inner, verbose=False):
                super(LoRaTransceiver, self_inner).__init__(verbose)
        
        self.lora = LoRaTransceiver(verbose=False)
        self.configure_radio()
    
    def configure_radio(self):
        """Configure LoRa radio parameters"""
        if not self.lora:
            return
            
        self.lora.set_mode(MODE.SLEEP)
        self.lora.set_dio_mapping([0,0,0,0,0,0])
        
        # Frequency
        self.lora.set_freq(self.freq)
        
        # Power amplifier
        self.lora.set_pa_config(
            pa_select=1,
            max_power=7,
            output_power=Config.DEFAULT_POWER
        )
        
        # Modulation parameters
        self.lora.set_spreading_factor(self.sf)
        
        # Bandwidth mapping
        bw_map = {125: BW.BW125, 250: BW.BW250, 500: BW.BW500}
        self.lora.set_bw(bw_map.get(self.bw, BW.BW125))
        
        # Error coding
        self.lora.set_coding_rate(CODING_RATE.CR4_5)
        
        # Packet settings
        self.lora.set_preamble(8)
        self.lora.set_sync_word(Config.DEFAULT_SYNC)
        self.lora.set_rx_crc(True)
        
        # Receiver settings
        self.lora.set_lna_gain(GAIN.G1)
        self.lora.set_agc_auto(True)
        
        print(f"LoRa configured: {self.freq}MHz SF{self.sf} BW{self.bw}kHz")
    
    def calculate_airtime(self, payload_size):
        """Calculate time on air for payload"""
        # Simplified calculation
        symbols = 8 + max((8*payload_size - 4*self.sf + 28), 0)
        airtime_ms = symbols * (2**self.sf) / self.bw
        return airtime_ms
    
    def calculate_datarate(self):
        """Calculate theoretical data rate"""
        datarate = self.sf * (self.bw / (2**self.sf)) * 1.25  # kbps
        return datarate
    
    def send_packet(self, data):
        """Send a packet"""
        if not self.lora:
            print(f"SIM TX: {data[:50]}...")
            return True
            
        try:
            self.lora.set_mode(MODE.STDBY)
            
            if isinstance(data, str):
                payload = list(data.encode())
            else:
                payload = list(data)
            
            payload = payload[:255]  # Max LoRa packet size
            
            self.lora.write_payload(payload)
            self.lora.set_mode(MODE.TX)
            
            # Wait for TX done
            timeout = time.time() + 5
            while time.time() < timeout:
                if self.lora.get_irq_flags()['tx_done']:
                    self.lora.clear_irq_flags(TxDone=1)
                    return True
                time.sleep(0.001)
            
            return False
        except Exception as e:
            print(f"TX Error: {e}")
            return False
    
    def receive_packet(self, timeout=1.0):
        """Receive a packet"""
        if not self.lora:
            # Simulation mode
            return None, -50, 10
        
        try:
            self.lora.set_mode(MODE.RXCONT)
            start_time = time.time()
            
            while (time.time() - start_time) < timeout:
                if self.lora.get_irq_flags()['rx_done']:
                    self.lora.clear_irq_flags(RxDone=1)
                    
                    payload = self.lora.read_payload(nocheck=True)
                    rssi = self.lora.get_pkt_rssi_value()
                    snr = self.lora.get_pkt_snr_value()
                    
                    # Try to decode
                    try:
                        if isinstance(payload, list):
                            data = bytes(payload).decode('utf-8')
                        else:
                            data = payload
                    except:
                        data = payload
                    
                    return data, rssi, snr
                
                time.sleep(0.01)
            
            return None, None, None
            
        except Exception as e:
            print(f"RX Error: {e}")
            return None, None, None
    
    def cleanup(self):
        """Clean up hardware resources"""
        if self.lora:
            self.lora.set_mode(MODE.SLEEP)
            BOARD.teardown()

# ============================================================================
# Module Detection
# ============================================================================

def detect_lora_module():
    """Detect and identify LoRa module"""
    
    if not LORA_AVAILABLE:
        print("LoRa libraries not available")
        return False
    
    try:
        import spidev
        import RPi.GPIO as GPIO
        
        print("Detecting LoRa module...")
        
        # GPIO setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Common pin configurations
        configs = [
            {"NSS": 8, "RESET": 22, "DIO0": 24, "bus": 0, "device": 0},  # Config 1
            {"NSS": 7, "RESET": 17, "DIO0": 4, "bus": 0, "device": 1},   # Config 2
        ]
        
        for i, config in enumerate(configs):
            print(f"\nTrying configuration {i+1}...")
            
            try:
                # Setup pins
                GPIO.setup(config["RESET"], GPIO.OUT)
                GPIO.setup(config["NSS"], GPIO.OUT)
                GPIO.setup(config["DIO0"], GPIO.IN)
                
                # Reset module
                GPIO.output(config["RESET"], GPIO.LOW)
                time.sleep(0.01)
                GPIO.output(config["RESET"], GPIO.HIGH)
                time.sleep(0.1)
                
                # Try SPI communication
                spi = spidev.SpiDev()
                spi.open(config["bus"], config["device"])
                spi.max_speed_hz = 5000000
                
                # Read version register (0x42)
                GPIO.output(config["NSS"], GPIO.LOW)
                version = spi.xfer([0x42 & 0x7F, 0x00])[1]
                GPIO.output(config["NSS"], GPIO.HIGH)
                
                # Check version
                if version == 0x12:
                    print(f"✓ Found SX1276/77/78/79 module!")
                    print(f"  Version: 0x{version:02X}")
                    print(f"  SPI: /dev/spidev{config['bus']}.{config['device']}")
                    print(f"  Pins: NSS={config['NSS']}, RESET={config['RESET']}, DIO0={config['DIO0']}")
                    spi.close()
                    return True
                elif version == 0x22:
                    print(f"✓ Found SX1262 module!")
                    print(f"  Version: 0x{version:02X}")
                    spi.close()
                    return True
                else:
                    print(f"  Unknown version: 0x{version:02X}")
                
                spi.close()
                
            except Exception as e:
                print(f"  Failed: {e}")
                continue
        
        print("\n✗ No LoRa module detected")
        print("\nTroubleshooting:")
        print("1. Check SPI is enabled: sudo raspi-config -> Interfacing -> SPI")
        print("2. Check wiring connections")
        print("3. Check power supply (3.3V)")
        print("4. Try different SPI device: /dev/spidev0.0 or /dev/spidev0.1")
        
        return False
        
    except Exception as e:
        print(f"Detection failed: {e}")
        return False
    finally:
        GPIO.cleanup()

# ============================================================================
# Ping Test
# ============================================================================

class LoRaPing(LoRaNode):
    """LoRa Ping implementation"""
    
    def __init__(self, node_id="NODE_A", **kwargs):
        super().__init__(node_id, **kwargs)
        self.reset_stats()
    
    def reset_stats(self):
        """Reset ping statistics"""
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
    
    def run_ping(self, target="NODE_B", count=10, interval=1.0, size=32):
        """Run ping test"""
        print(f"\nPING {target}: {count} packets, {interval}s interval, {size} bytes")
        print("="*60)
        
        for seq in range(1, count + 1):
            # Create ping packet
            padding = 'X' * max(0, size - 20)  # Adjust for JSON overhead
            ping_packet = json.dumps({
                'type': 'PING',
                'from': self.node_id,
                'to': target,
                'seq': seq,
                'time': time.time(),
                'data': padding
            })
            
            # Send ping
            send_time = time.time()
            if self.send_packet(ping_packet):
                self.stats['sent'] += 1
                
                # Wait for pong
                response, rssi, snr = self.receive_packet(timeout=2.0)
                
                if response:
                    try:
                        pong = json.loads(response)
                        if pong.get('type') == 'PONG' and pong.get('seq') == seq:
                            rtt = (time.time() - send_time) * 1000
                            self.update_stats(rtt, rssi)
                            
                            print(f"[{seq}] Reply from {pong['from']}: " +
                                  f"time={rtt:.1f}ms RSSI={rssi}dBm SNR={snr:.1f}dB")
                        else:
                            self.stats['lost'] += 1
                            print(f"[{seq}] Invalid response")
                    except:
                        self.stats['lost'] += 1
                        print(f"[{seq}] Malformed response")
                else:
                    self.stats['lost'] += 1
                    print(f"[{seq}] Request timeout")
            else:
                self.stats['lost'] += 1
                print(f"[{seq}] Transmission failed")
            
            # Interval delay
            if seq < count:
                time.sleep(interval)
        
        self.print_statistics()
    
    def run_pong(self):
        """Run pong responder"""
        print(f"\nLoRa Pong Responder - {self.node_id}")
        print("Listening for ping packets... (Ctrl+C to stop)")
        print("="*60)
        
        while True:
            try:
                data, rssi, snr = self.receive_packet(timeout=10.0)
                
                if data:
                    try:
                        ping = json.loads(data)
                        if ping.get('type') == 'PING':
                            print(f"Ping from {ping['from']}: seq={ping['seq']} " +
                                  f"RSSI={rssi}dBm SNR={snr:.1f}dB")
                            
                            # Send pong
                            pong_packet = json.dumps({
                                'type': 'PONG',
                                'from': self.node_id,
                                'to': ping['from'],
                                'seq': ping['seq'],
                                'ping_time': ping['time']
                            })
                            
                            if self.send_packet(pong_packet):
                                print(f"  → Pong sent")
                    except:
                        pass
            except KeyboardInterrupt:
                break
    
    def update_stats(self, rtt, rssi):
        """Update statistics"""
        self.stats['received'] += 1
        
        # RTT stats
        self.stats['rtt_total'] += rtt
        self.stats['rtt_min'] = min(self.stats['rtt_min'], rtt)
        self.stats['rtt_max'] = max(self.stats['rtt_max'], rtt)
        self.stats['rtt_avg'] = self.stats['rtt_total'] / self.stats['received']
        
        # RSSI stats
        if rssi is not None:
            self.stats['rssi_total'] += rssi
            self.stats['rssi_min'] = min(self.stats['rssi_min'], rssi)
            self.stats['rssi_max'] = max(self.stats['rssi_max'], rssi)
            self.stats['rssi_avg'] = self.stats['rssi_total'] / self.stats['received']
    
    def print_statistics(self):
        """Print ping statistics"""
        print("\n" + "="*60)
        print("--- LoRa Ping Statistics ---")
        
        if self.stats['sent'] > 0:
            loss_percent = (self.stats['lost'] / self.stats['sent']) * 100
            print(f"Packets: Sent = {self.stats['sent']}, " +
                  f"Received = {self.stats['received']}, " +
                  f"Lost = {self.stats['lost']} ({loss_percent:.1f}% loss)")
        
        if self.stats['received'] > 0:
            print(f"Round-trip time (ms):")
            print(f"  Min/Avg/Max = {self.stats['rtt_min']:.1f}/" +
                  f"{self.stats['rtt_avg']:.1f}/" +
                  f"{self.stats['rtt_max']:.1f}")
            
            if self.stats['rssi_min'] != float('inf'):
                print(f"Signal strength (dBm):")
                print(f"  Min/Avg/Max = {self.stats['rssi_min']:.0f}/" +
                      f"{self.stats['rssi_avg']:.0f}/" +
                      f"{self.stats['rssi_max']:.0f}")
        
        # Data rate info
        datarate = self.calculate_datarate()
        airtime = self.calculate_airtime(32)
        print(f"\nLink info:")
        print(f"  Data rate: ~{datarate:.1f} kbps")
        print(f"  Air time: ~{airtime:.1f} ms per packet")

# ============================================================================
# File Transfer
# ============================================================================

class LoRaFileTransfer(LoRaNode):
    """LoRa File Transfer implementation"""
    
    def __init__(self, node_id="NODE", **kwargs):
        super().__init__(node_id, **kwargs)
        self.chunk_size = Config.CHUNK_SIZE
        self.window_size = Config.WINDOW_SIZE
    
    def send_file(self, filepath, dest="NODE_B"):
        """Send a file"""
        if not os.path.exists(filepath):
            print(f"Error: File not found: {filepath}")
            return False
        
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        
        # Calculate hash
        with open(filepath, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        print(f"\nSending file: {filename}")
        print(f"Size: {filesize} bytes")
        print(f"Hash: {file_hash}")
        
        # Calculate chunks
        num_chunks = (filesize + self.chunk_size - 1) // self.chunk_size
        print(f"Chunks: {num_chunks} x {self.chunk_size} bytes")
        
        # Send file info
        info_packet = json.dumps({
            'type': 'FILE_INFO',
            'from': self.node_id,
            'to': dest,
            'filename': filename,
            'size': filesize,
            'chunks': num_chunks,
            'hash': file_hash
        })
        
        print("\nSending file info...")
        if not self.send_packet(info_packet):
            print("Failed to send file info")
            return False
        
        # Wait for ACK
        response, _, _ = self.receive_packet(timeout=5.0)
        if not response:
            print("No acknowledgment received")
            return False
        
        # Send chunks
        print("Sending data chunks...")
        sent = 0
        with open(filepath, 'rb') as f:
            for chunk_num in range(num_chunks):
                chunk_data = f.read(self.chunk_size)
                
                chunk_packet = json.dumps({
                    'type': 'FILE_DATA',
                    'chunk': chunk_num,
                    'total': num_chunks,
                    'data': base64.b64encode(chunk_data).decode()
                })
                
                if self.send_packet(chunk_packet):
                    sent += 1
                    progress = (sent / num_chunks) * 100
                    print(f"\rProgress: [{sent}/{num_chunks}] {progress:.1f}%", end='')
                else:
                    print(f"\nFailed to send chunk {chunk_num}")
                
                # Simple flow control
                if chunk_num % self.window_size == 0:
                    time.sleep(0.1)
        
        print("\n\nFile transfer complete!")
        
        # Send completion
        complete_packet = json.dumps({
            'type': 'FILE_COMPLETE',
            'filename': filename,
            'hash': file_hash
        })
        self.send_packet(complete_packet)
        
        return True
    
    def receive_file(self, save_dir="./received"):
        """Receive a file"""
        os.makedirs(save_dir, exist_ok=True)
        
        print(f"\nWaiting for file transfer...")
        print(f"Save directory: {save_dir}")
        print("="*60)
        
        file_info = None
        chunks = {}
        
        while True:
            data, rssi, snr = self.receive_packet(timeout=10.0)
            
            if not data:
                continue
            
            try:
                packet = json.loads(data)
                packet_type = packet.get('type')
                
                if packet_type == 'FILE_INFO':
                    file_info = packet
                    print(f"\nReceiving: {file_info['filename']}")
                    print(f"Size: {file_info['size']} bytes")
                    print(f"Chunks: {file_info['chunks']}")
                    chunks = {}
                    
                    # Send ACK
                    ack = json.dumps({'type': 'ACK', 'from': self.node_id})
                    self.send_packet(ack)
                    
                elif packet_type == 'FILE_DATA' and file_info:
                    chunk_num = packet['chunk']
                    chunk_data = base64.b64decode(packet['data'])
                    chunks[chunk_num] = chunk_data
                    
                    progress = (len(chunks) / file_info['chunks']) * 100
                    print(f"\rProgress: [{len(chunks)}/{file_info['chunks']}] " +
                          f"{progress:.1f}%", end='')
                    
                elif packet_type == 'FILE_COMPLETE' and file_info:
                    print("\n\nAssembling file...")
                    
                    # Save file
                    filepath = os.path.join(save_dir, file_info['filename'])
                    with open(filepath, 'wb') as f:
                        for i in range(file_info['chunks']):
                            if i in chunks:
                                f.write(chunks[i])
                    
                    # Verify hash
                    with open(filepath, 'rb') as f:
                        received_hash = hashlib.md5(f.read()).hexdigest()
                    
                    if received_hash == packet['hash']:
                        print(f"✓ File saved: {filepath}")
                        print(f"✓ Hash verified: {received_hash}")
                    else:
                        print(f"✗ Hash mismatch!")
                    
                    break
                    
            except Exception as e:
                print(f"Error processing packet: {e}")

# ============================================================================
# Spectrum Scanner
# ============================================================================

def spectrum_scan(start_freq=902, end_freq=928, step=1.0):
    """Scan frequency spectrum for interference"""
    
    print(f"\nScanning {start_freq}-{end_freq} MHz (step: {step} MHz)")
    print("="*60)
    
    if not LORA_AVAILABLE:
        print("LoRa hardware not available for spectrum scan")
        return
    
    node = LoRaNode("SCANNER")
    results = []
    
    try:
        freq = start_freq
        while freq <= end_freq:
            node.lora.set_freq(freq)
            node.lora.set_mode(MODE.RXCONT)
            
            time.sleep(0.05)  # Settle time
            rssi = node.lora.get_rssi_value()
            results.append((freq, rssi))
            
            # Display bar graph
            bar_len = max(0, int((rssi + 120) / 2))
            bar = '█' * bar_len
            print(f"{freq:6.1f} MHz: {rssi:4d} dBm {bar}")
            
            freq += step
        
        # Find clearest frequency
        if results:
            clearest = min(results, key=lambda x: x[1])
            noisiest = max(results, key=lambda x: x[1])
            
            print("\n" + "="*60)
            print(f"Clearest: {clearest[0]:.1f} MHz at {clearest[1]} dBm")
            print(f"Noisiest: {noisiest[0]:.1f} MHz at {noisiest[1]} dBm")
        
    finally:
        node.cleanup()
    
    return results

# ============================================================================
# Main Command Line Interface
# ============================================================================

def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description='LoRa Testing Suite - Complete toolkit for LoRa communication',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Detect LoRa module
  %(prog)s detect
  
  # Run ping test
  %(prog)s ping send --count 20 --interval 0.5
  %(prog)s ping respond
  
  # File transfer
  %(prog)s file send /path/to/file.txt
  %(prog)s file receive
  
  # Spectrum scan
  %(prog)s spectrum --start 902 --end 928 --step 0.5
  
  # Custom configuration
  %(prog)s --freq 868 --sf 10 --bw 250 ping send
        """
    )
    
    # Global options
    parser.add_argument('--freq', type=float, help='Frequency in MHz')
    parser.add_argument('--sf', type=int, choices=range(7,13), help='Spreading factor (7-12)')
    parser.add_argument('--bw', type=int, choices=[125,250,500], help='Bandwidth in kHz')
    parser.add_argument('--power', type=int, choices=range(2,21), help='TX power in dBm (2-20)')
    parser.add_argument('--node', type=str, default='NODE_A', help='Node identifier')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Detect command
    subparsers.add_parser('detect', help='Detect LoRa module')
    
    # Ping command
    ping_parser = subparsers.add_parser('ping', help='Ping test')
    ping_sub = ping_parser.add_subparsers(dest='ping_mode')
    
    ping_send = ping_sub.add_parser('send', help='Send ping packets')
    ping_send.add_argument('--target', default='NODE_B', help='Target node ID')
    ping_send.add_argument('--count', type=int, default=10, help='Number of pings')
    ping_send.add_argument('--interval', type=float, default=1.0, help='Interval between pings')
    ping_send.add_argument('--size', type=int, default=32, help='Packet size in bytes')
    
    ping_sub.add_parser('respond', help='Respond to pings')
    
    # File command
    file_parser = subparsers.add_parser('file', help='File transfer')
    file_sub = file_parser.add_subparsers(dest='file_mode')
    
    file_send = file_sub.add_parser('send', help='Send file')
    file_send.add_argument('filepath', help='Path to file')
    file_send.add_argument('--dest', default='NODE_B', help='Destination node')
    
    file_receive = file_sub.add_parser('receive', help='Receive file')
    file_receive.add_argument('--dir', default='./received', help='Save directory')
    
    # Spectrum command
    spectrum_parser = subparsers.add_parser('spectrum', help='Spectrum scan')
    spectrum_parser.add_argument('--start', type=float, default=902, help='Start frequency (MHz)')
    spectrum_parser.add_argument('--end', type=float, default=928, help='End frequency (MHz)')
    spectrum_parser.add_argument('--step', type=float, default=1.0, help='Step size (MHz)')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Handle commands
    try:
        if args.command == 'detect':
            detect_lora_module()
            
        elif args.command == 'ping':
            ping = LoRaPing(
                node_id=args.node,
                freq=args.freq,
                sf=args.sf,
                bw=args.bw
            )
            
            try:
                if args.ping_mode == 'send':
                    ping.run_ping(
                        target=args.target,
                        count=args.count,
                        interval=args.interval,
                        size=args.size
                    )
                elif args.ping_mode == 'respond':
                    ping.run_pong()
                else:
                    ping_parser.print_help()
            finally:
                ping.cleanup()
                
        elif args.command == 'file':
            transfer = LoRaFileTransfer(
                node_id=args.node,
                freq=args.freq,
                sf=args.sf,
                bw=args.bw
            )
            
            try:
                if args.file_mode == 'send':
                    transfer.send_file(args.filepath, args.dest)
                elif args.file_mode == 'receive':
                    transfer.receive_file(args.dir)
                else:
                    file_parser.print_help()
            finally:
                transfer.cleanup()
                
        elif args.command == 'spectrum':
            spectrum_scan(args.start, args.end, args.step)
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
