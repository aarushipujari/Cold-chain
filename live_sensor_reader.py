"""
Live ESP32 Sensor Reader & Cold-Chain Streamer
Reads real-time temperatures from ESP32 over USB Serial (115200 baud),
prints live formatted metrics to console, and appends to cold_chain_log.csv.
"""

import os
import sys
import time
import re
import csv
from datetime import datetime
import serial
import serial.tools.list_ports

# Configuration
BAUD_RATE = 115200
CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cold_chain_log.csv")


def find_esp32_port():
    """Auto-detects ESP32 COM port."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        if any(chip in desc for chip in ["cp210", "ch340", "uart", "usb-to-serial"]):
            return p.device
    for p in ports:
        if "com" in p.device.lower():
            return p.device
    return "COM3"


def init_csv():
    """Ensures CSV exists with valid column headers."""
    if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
        with open(CSV_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "time_elapsed", "temp_top_c", "temp_core_c", 
                "temp_pack_c", "thermal_gradient", "arrhenius_factor", 
                "cumulative_equiv_hours", "stability_index_pct", "status_label"
            ])
        print(f"[+] Initialized CSV log: {CSV_FILE}")


def append_csv(row):
    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(row)


def main():
    print("=" * 72)
    print("  BioShield AI - Live Hardware Sensor Reader & Streamer")
    print("=" * 72)

    port = find_esp32_port()
    print(f"[*] Target Serial Port : {port} @ {BAUD_RATE} baud")
    print(f"[*] Logging Output     : {CSV_FILE}")
    print("[*] IMPORTANT: Make sure Arduino IDE Serial Monitor is CLOSED!")
    print("=" * 72)

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1.0)
        print(f"[+] Connected to ESP32 on {port} successfully!\n")
    except Exception as e:
        print(f"\n[!] Connection failed on {port}: {e}")
        print("[!] Ensure:")
        print("    1. ESP32 is plugged in via USB.")
        print("    2. Arduino IDE Serial Monitor is closed (frees the COM port).")
        print("    3. Correct USB driver is installed (CP210x or CH340).")
        sys.exit(1)

    init_csv()

    # Regex patterns matching esp32_cold_chain.ino output
    p_status = re.compile(r"Time Elapsed:\s*(.+?)\s*\|\s*Status:\s*(.+)")
    p_t1 = re.compile(r"Probe 1:\s*([\d.-]+)\s*°C")
    p_t2 = re.compile(r"Probe 2:\s*([\d.-]+)\s*°C")
    p_t3 = re.compile(r"Probe 3:\s*([\d.-]+)\s*°C")
    p_accel = re.compile(r"Arrhenius Degradation Factor\s*:\s*([\d.-]+)x")
    p_equiv = re.compile(r"Cumulative Thermal Exposure\s*:\s*([\d.-]+)\s*equiv")
    p_stab = re.compile(r"Estimated Stability Index\s*:\s*([\d.-]+)\s*%")

    frame = {}
    sample_count = 0

    print(f"{'TIME':^10} | {'LID (T1)':^10} | {'CORE (T2)':^11} | {'PACK (T3)':^10} | {'RATE Q(T)':^10} | {'STABILITY':^10} | {'STATUS'}")
    print("-" * 85)

    try:
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                continue

            m = p_status.search(line)
            if m:
                frame['elapsed'] = m.group(1).strip()
                frame['status'] = m.group(2).strip()

            m = p_t1.search(line)
            if m: frame['t1'] = float(m.group(1))

            m = p_t2.search(line)
            if m: frame['t2'] = float(m.group(1))

            m = p_t3.search(line)
            if m: frame['t3'] = float(m.group(1))

            m = p_accel.search(line)
            if m: frame['accel'] = float(m.group(1))

            m = p_equiv.search(line)
            if m: frame['equiv'] = float(m.group(1))

            m = p_stab.search(line)
            if m:
                frame['stab'] = float(m.group(1))

                # When a full block completes, process and display
                if 't1' in frame and 't2' in frame and 't3' in frame:
                    sample_count += 1
                    t1 = frame['t1']
                    t2 = frame['t2']
                    t3 = frame['t3']
                    accel = frame.get('accel', 1.0)
                    equiv = frame.get('equiv', 0.0)
                    stab = frame.get('stab', 100.0)
                    status = frame.get('status', 'NORMAL_COLD_STORAGE')
                    elapsed = frame.get('elapsed', '00m 00s')
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    gradient = round(abs(t1 - t3), 2)

                    # Glitch safety filter (-127°C or 85°C)
                    if t1 > -100 and t2 > -100 and t3 > -100:
                        append_csv([
                            now_str, elapsed, t1, t2, t3, gradient, 
                            accel, equiv, stab, status
                        ])

                        # Color tag for status
                        tag = "✅ SAFE"
                        if t2 > 8.0: tag = "🚨 HEAT EXCURSION"
                        elif t2 < 0.0: tag = "❄️ FREEZE HAZARD"

                        time_display = datetime.now().strftime("%H:%M:%S")
                        print(f"{time_display:^10} | {t1:^8.2f}°C | {t2:^9.2f}°C | {t3:^8.2f}°C | {accel:^8.2f}x | {stab:^8.1f}% | {tag}")

                    frame = {}

    except KeyboardInterrupt:
        print("\n\n[+] Stopped logging gracefully. Total samples logged:", sample_count)
        print(f"[+] Saved to: {CSV_FILE}")
        ser.close()


if __name__ == "__main__":
    main()
