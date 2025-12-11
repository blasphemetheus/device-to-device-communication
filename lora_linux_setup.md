# RN2903 LoRa Setup on Manjaro Linux

## Problem

The RN2903-PICTAIL USB dongle worked on Windows (via TeraTerm) but failed on Linux with `screen` or `picocom`, producing garbled output or `[screen is terminating]`.

## Root Cause

The RN2903 requires **CR+LF** (`\r\n`) line endings. Default Linux terminal tools send only LF (`\n`), causing the device to ignore commands.

## Solution

### Prerequisites

1. **User must be in `uucp` group** (Manjaro) or `dialout` group (Debian/Ubuntu):
   ```bash
   sudo usermod -aG uucp $USER
   # Log out and back in for group change to take effect
   ```

2. **Verify device is detected**:
   ```bash
   ls /dev/ttyACM*
   # Should show /dev/ttyACM0

   dmesg | tail -20 | grep -i lora
   # Should show "LoRa Tech. PICtail Board"
   ```

### Option 1: Python with pyserial (Recommended)

```bash
# Install pyserial if needed
pip install pyserial
```

```python
#!/usr/bin/env python3
"""RN2903 LoRa communication on Linux"""
import serial
import time

def connect(port='/dev/ttyACM0', baudrate=57600):
    """Connect to RN2903 device."""
    ser = serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=2
    )
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser

def send_cmd(ser, cmd, delay=0.3):
    """Send command and return response. Handles CR+LF automatically."""
    ser.write(f"{cmd}\r\n".encode())
    ser.flush()
    time.sleep(delay)
    response = ser.read(256).decode('utf-8', errors='replace').strip()
    return response

def main():
    ser = connect()

    # Get firmware version
    print(f"Version: {send_cmd(ser, 'sys get ver')}")

    # Pause LoRaWAN MAC to use raw radio
    send_cmd(ser, 'mac pause')

    # Check radio settings
    print(f"Mode: {send_cmd(ser, 'radio get mod')}")
    print(f"Frequency: {send_cmd(ser, 'radio get freq')} Hz")
    print(f"SF: {send_cmd(ser, 'radio get sf')}")
    print(f"BW: {send_cmd(ser, 'radio get bw')} kHz")

    # Transmit "HELLO" (hex: 48454C4C4F)
    result = send_cmd(ser, 'radio tx 48454C4C4F', delay=0.5)
    print(f"TX result: {result}")

    # Wait for radio_tx_ok
    time.sleep(1)
    extra = ser.read(256).decode('utf-8', errors='replace').strip()
    if extra:
        print(f"TX status: {extra}")

    ser.close()

if __name__ == '__main__':
    main()
```

### Option 2: Elixir with Circuits.UART

```bash
# In your mix.exs, add:
# {:circuits_uart, "~> 1.5"}
```

```elixir
defmodule LoRa.RN2903 do
  @moduledoc """
  RN2903 LoRa communication module.
  """

  @default_port "/dev/ttyACM0"
  @baudrate 57600

  def start(port \\ @default_port) do
    {:ok, uart} = Circuits.UART.start_link()

    :ok = Circuits.UART.open(uart, port,
      speed: @baudrate,
      data_bits: 8,
      stop_bits: 1,
      parity: :none,
      active: false
    )

    {:ok, uart}
  end

  def send_cmd(uart, cmd) do
    # RN2903 requires CR+LF line endings
    Circuits.UART.write(uart, "#{cmd}\r\n")
    Circuits.UART.drain(uart)

    # Read response (may need multiple reads for longer responses)
    Process.sleep(300)
    case Circuits.UART.read(uart, 500) do
      {:ok, data} -> String.trim(data)
      {:error, reason} -> {:error, reason}
    end
  end

  def get_version(uart), do: send_cmd(uart, "sys get ver")

  def pause_mac(uart), do: send_cmd(uart, "mac pause")

  def radio_tx(uart, hex_data), do: send_cmd(uart, "radio tx #{hex_data}")

  def radio_rx(uart, timeout \\ 0), do: send_cmd(uart, "radio rx #{timeout}")

  def stop(uart), do: Circuits.UART.close(uart)
end

# Usage:
# {:ok, uart} = LoRa.RN2903.start()
# LoRa.RN2903.get_version(uart)
# LoRa.RN2903.pause_mac(uart)
# LoRa.RN2903.radio_tx(uart, "48454C4C4F")  # "HELLO"
# LoRa.RN2903.stop(uart)
```

### Option 3: picocom (Interactive)

The key is `--omap crcrlf` to convert Enter to CR+LF:

```bash
picocom -b 57600 --omap crcrlf /dev/ttyACM0
```

Then type commands interactively:
```
sys get ver
mac pause
radio tx 48454C4C4F
```

Exit with `Ctrl+A` then `Ctrl+X`.

## RN2903 Command Reference

| Command | Description |
|---------|-------------|
| `sys get ver` | Get firmware version |
| `sys get hweui` | Get hardware EUI |
| `mac pause` | Pause LoRaWAN stack (required for raw radio) |
| `radio get mod` | Get modulation (lora/fsk) |
| `radio get freq` | Get frequency in Hz |
| `radio get sf` | Get spreading factor (sf7-sf12) |
| `radio get bw` | Get bandwidth (125/250/500 kHz) |
| `radio get pwr` | Get TX power in dBm |
| `radio tx <hex>` | Transmit hex data |
| `radio rx <timeout>` | Receive (0 = continuous, or ms) |
| `radio set freq <hz>` | Set frequency |
| `radio set sf <sf7-12>` | Set spreading factor |
| `radio set pwr <dbm>` | Set TX power |

## Troubleshooting

### "Permission denied" on /dev/ttyACM0
```bash
# Add user to uucp group
sudo usermod -aG uucp $USER
# Log out and back in
```

### No /dev/ttyACM* device
```bash
# Check USB connection
lsusb | grep Microchip
# Should show: "Microchip Technology, Inc. CDC RS-232 Emulation Demo"

# Check kernel messages
dmesg | tail -30 | grep -i acm
```

### Commands return nothing
- Ensure you're sending CR+LF (`\r\n`) not just LF (`\n`)
- Check baudrate is 57600
- Try resetting device by unplugging/replugging

### "invalid_param" response
- Command syntax error, check spelling
- For `radio tx`, data must be valid hex (even number of chars)

## Test Results (Dec 10, 2025)

```
sys get ver -> RN2903 0.9.5 Sep 02 2015 17:19:55
sys get hweui -> 0004A30B001A865B
mac pause -> 4294967245
radio get mod -> lora
radio get freq -> 923300000
radio get pwr -> 2
radio get sf -> sf12
radio get bw -> 125
radio tx 48454C4C4F -> ok
(followed by) radio_tx_ok
```

Device confirmed working on Manjaro Linux.
