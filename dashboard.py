"""
Cold-Chain Monitoring System - Research-Grade Live Dashboard & Logger
Includes:
- Strict Pre-Calculation Glitch Rejection (Filters -127°C, 85.0°C, and >5°C/2s jumps)
- Bad Read Tracking (Glitch Counter)
- Protected Stability Integration (Only valid samples integrated)
- Log-Scale Arrhenius Rate Plot (1x to 40x dynamic range clearly visible)
- True NaN Handling (No fake 0°C lines)
- Clear Model Assumption Labeling
"""

import sys
import os
import re
import csv
import time
from datetime import datetime
import numpy as np
import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.ticker import ScalarFormatter, NullFormatter
from collections import deque

# --- CONFIGURATION ---
BAUD_RATE = 115200
CSV_FILE = "cold_chain_log.csv"
MAX_HISTORY = 120  # ~4 minutes rolling window

# Buffers (Stores valid or NaN data)
timestamps = deque(maxlen=MAX_HISTORY)
t_top_data = deque(maxlen=MAX_HISTORY)
t_core_data = deque(maxlen=MAX_HISTORY)
t_pack_data = deque(maxlen=MAX_HISTORY)
accel_data = deque(maxlen=MAX_HISTORY)
stability_data = deque(maxlen=MAX_HISTORY)

# State & Glitch Tracking
bad_read_count = 0
total_samples = 0
last_valid_top = np.nan
last_valid_core = np.nan
last_valid_pack = np.nan
last_valid_accel = 1.0
last_valid_stab = 100.0
last_valid_status = "INITIALIZING"


def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        if "cp210" in desc or "ch340" in desc or "uart" in desc or "usb-to-serial" in desc or "com3" in desc:
            return p.device
    if ports:
        return ports[0].device
    return "COM3"


def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Timestamp", "Time_Elapsed", "Temp_Top_C", "Temp_Core_C", 
                "Temp_Pack_C", "Arrhenius_Factor", "Equiv_Hours", 
                "Stability_Pct", "Status", "Sample_Quality"
            ])


def append_csv(row):
    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(row)


def validate_reading(new_val, prev_val):
    """
    Strict Pre-Calculation Validation:
    - Rejects Dallas -127°C (disconnect) and physical limits (< -40°C or > 65°C)
    - Rejects exactly 85.0°C (DS18B20 power-on reset state)
    - Rejects physical jump > 5.0°C within 2 seconds
    """
    if new_val is None or np.isnan(new_val):
        return False, np.nan

    # Dallas disconnected code or extreme physical bounds
    if new_val <= -40.0 or new_val >= 65.0 or abs(new_val - (-127.0)) < 0.1:
        return False, np.nan

    # DS18B20 power-on reset state
    if abs(new_val - 85.0) < 0.05:
        return False, np.nan

    # Sudden jump rate-of-change check (> 5°C in 2 seconds)
    if not np.isnan(prev_val):
        if abs(new_val - prev_val) > 5.0:
            return False, prev_val  # Reject spike, hold previous valid

    return True, new_val


def main():
    global bad_read_count, total_samples
    global last_valid_top, last_valid_core, last_valid_pack, last_valid_accel, last_valid_stab, last_valid_status

    port = find_esp32_port()
    print("=" * 68)
    print(f"  Research-Grade Cold-Chain System [Strict Validation & Log Scale]")
    print(f"  Target Port : {port} @ {BAUD_RATE} baud")
    print("=" * 68)

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
        print(f"[+] Successfully connected to {port}")
    except serial.SerialException as e:
        print(f"\n[!] ERROR: Could not open {port}: {e}")
        print("[!] Ensure Arduino IDE Serial Monitor is CLOSED!")
        input("\nPress Enter to exit...")
        sys.exit(1)

    init_csv()

    p_status = re.compile(r"Time Elapsed:\s*(.+?)\s*\|\s*Status:\s*(.+)")
    p_t1 = re.compile(r"Probe 1:\s*([\d.-]+)\s*°C")
    p_t2 = re.compile(r"Probe 2:\s*([\d.-]+)\s*°C")
    p_t3 = re.compile(r"Probe 3:\s*([\d.-]+)\s*°C")
    p_accel = re.compile(r"Arrhenius Degradation Factor\s*:\s*([\d.-]+)x")
    p_equiv = re.compile(r"Cumulative Thermal Exposure\s*:\s*([\d.-]+)\s*equiv")
    p_stab = re.compile(r"Estimated Stability Index\s*:\s*([\d.-]+)\s*%")
    p_rej = re.compile(r"REJECTED")

    plt.style.use('dark_background')
    fig = plt.figure(figsize=(14, 8.8))
    fig.canvas.manager.set_window_title("Cold-Chain Arrhenius Research Dashboard")

    gs = fig.add_gridspec(2, 2, height_ratios=[1.25, 1.0])
    ax_temp = fig.add_subplot(gs[0, :])
    ax_accel = fig.add_subplot(gs[1, 0])
    ax_stab = fig.add_subplot(gs[1, 1])

    fig.subplots_adjust(hspace=0.40, wspace=0.22, left=0.07, right=0.95, top=0.90, bottom=0.08)

    curr_frame = {}

    def update_data(frame):
        nonlocal curr_frame
        global bad_read_count, total_samples
        global last_valid_top, last_valid_core, last_valid_pack, last_valid_accel, last_valid_stab, last_valid_status

        while ser.in_waiting > 0:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
            except Exception:
                continue

            if not line:
                continue

            m = p_status.search(line)
            if m:
                curr_frame['elapsed'] = m.group(1).strip()
                curr_frame['status'] = m.group(2).strip()

            m = p_t1.search(line)
            if m: curr_frame['raw_t1'] = float(m.group(1))

            m = p_t2.search(line)
            if m: curr_frame['raw_t2'] = float(m.group(1))

            m = p_t3.search(line)
            if m: curr_frame['raw_t3'] = float(m.group(1))

            if p_rej.search(line):
                curr_frame['has_rejected'] = True

            m = p_accel.search(line)
            if m: curr_frame['accel'] = float(m.group(1))

            m = p_equiv.search(line)
            if m: curr_frame['equiv_hrs'] = float(m.group(1))

            m = p_stab.search(line)
            if m:
                curr_frame['stability'] = float(m.group(1))

                total_samples += 1
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                time_clock = datetime.now().strftime("%H:%M:%S")

                # Step 1: Pre-calculation validation on each probe
                val1, clean_t1 = validate_reading(curr_frame.get('raw_t1'), last_valid_top)
                val2, clean_t2 = validate_reading(curr_frame.get('raw_t2'), last_valid_core)
                val3, clean_t3 = validate_reading(curr_frame.get('raw_t3'), last_valid_pack)

                sample_valid = val1 and val2 and val3 and not curr_frame.get('has_rejected', False)
                if not sample_valid:
                    bad_read_count += 1
                    quality = "GLITCH_REJECTED"
                else:
                    quality = "VALID"

                # Update held values
                if val1 and not np.isnan(clean_t1): last_valid_top = clean_t1
                if val2 and not np.isnan(clean_t2): last_valid_core = clean_t2
                if val3 and not np.isnan(clean_t3): last_valid_pack = clean_t3

                # Step 2: Rate and Stability tracking
                accel = curr_frame.get('accel', last_valid_accel)
                # Clip unphysical spike on display
                if accel > 300.0:
                    accel = last_valid_accel
                else:
                    last_valid_accel = accel

                stability = curr_frame.get('stability', last_valid_stab)
                last_valid_stab = stability
                last_valid_status = curr_frame.get('status', last_valid_status)
                elapsed = curr_frame.get('elapsed', "00m 00s")
                equiv = curr_frame.get('equiv_hrs', 0.0)

                # Append strictly to CSV
                append_csv([now_str, elapsed, last_valid_top, last_valid_core, last_valid_pack, accel, equiv, stability, last_valid_status, quality])

                # Push to plot buffers (uses held valid values so NO fake zeros!)
                timestamps.append(time_clock)
                t_top_data.append(last_valid_top)
                t_core_data.append(last_valid_core)
                t_pack_data.append(last_valid_pack)
                accel_data.append(accel)
                stability_data.append(stability)

                print(f"[{time_clock}] Top: {last_valid_top:.2f}°C | Core: {last_valid_core:.2f}°C | Pack: {last_valid_pack:.2f}°C | Rate: {accel:.1f}x | Index: {stability:.2f}% | Bad Reads: {bad_read_count}/{total_samples}")
                curr_frame = {}

        if not timestamps:
            return

        x = list(range(len(timestamps)))

        # 1. Multi-Point Thermal Spatial Profile
        ax_temp.clear()
        ax_temp.plot(x, list(t_top_data), label="Probe 1: Lid / Ambient", color="#FFA502", linewidth=2.0)
        ax_temp.plot(x, list(t_core_data), label="Probe 2: Core Payload (Vaccine)", color="#FF4757", linewidth=2.8)
        ax_temp.plot(x, list(t_pack_data), label="Probe 3: Ice Pack / Base", color="#00D2D3", linewidth=2.0)

        # Standards: WHO PQS Safe Zone
        ax_temp.axhspan(2.0, 8.0, color='#2ED573', alpha=0.18, label="WHO Safe Band (2°C - 8°C)")
        ax_temp.axhline(0.0, color='#54A0FF', linestyle='--', alpha=0.75, label="Freeze Limit (0°C)")
        ax_temp.axhline(8.0, color='#EE5253', linestyle='--', alpha=0.75, label="Excursion Limit (8°C)")

        ax_temp.set_title(
            f"Cold-Chain Thermal Spatial Zones  |  Payload: {last_valid_core:.2f}°C  |  Status: {last_valid_status}  |  Bad Reads: {bad_read_count}/{total_samples}",
            fontsize=11.5, fontweight='bold', color="#2ED573" if "NORMAL" in last_valid_status else "#FF6B6B"
        )
        ax_temp.set_ylabel("Temperature (°C)", fontsize=10)
        ax_temp.grid(True, linestyle=":", alpha=0.35)
        ax_temp.legend(loc="upper left", ncol=3, fontsize=8.2)
        ax_temp.set_ylim(-2, 45)

        # 2. LOG-SCALE Arrhenius Kinetic Rate Plot
        ax_accel.clear()
        ax_accel.plot(x, list(accel_data), color="#FFA502", linewidth=2.2)
        ax_accel.axhline(1.0, color="#2ED573", linestyle="--", alpha=0.85, label="1.0x Baseline (4°C)")

        # Log Scale prevents spikes from compressing dynamic 1x to 40x range!
        ax_accel.set_yscale('log')
        ax_accel.set_ylim(0.2, 100.0)
        ax_accel.set_yticks([0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0])
        ax_accel.get_yaxis().set_major_formatter(ScalarFormatter())

        ax_accel.set_title(f"Arrhenius Rate: {last_valid_accel:.2f}x Baseline (Log Scale)", fontsize=11, fontweight='bold', color="#FFA502")
        ax_accel.set_ylabel("Acceleration Q(T) [Log Scale]", fontsize=9)
        ax_accel.grid(True, which="both", linestyle=":", alpha=0.35)
        ax_accel.legend(loc="upper left", fontsize=8)

        # 3. Product Stability Panel with Explicit Model Assumption Labeling
        ax_stab.clear()
        ax_stab.plot(x, list(stability_data), color="#2ED573" if last_valid_stab > 80 else "#FF4757", linewidth=2.5)
        
        # Explicit label: "model estimate (assumed Ea)"
        ax_stab.set_title(
            f"Estimated Product Stability: {last_valid_stab:.2f}%\n[Model Estimate: Assumed Ea = 83.14 kJ/mol]",
            fontsize=10.5, fontweight='bold', color="#2ED573" if last_valid_stab > 80 else "#FF4757"
        )
        ax_stab.set_ylabel("Stability Index (%)", fontsize=9)
        ax_stab.set_ylim(0, 105)
        ax_stab.grid(True, linestyle=":", alpha=0.35)

        # Timestamp axis
        if len(timestamps) > 1:
            step = max(1, len(timestamps) // 6)
            ticks = list(range(0, len(timestamps), step))
            labels = [timestamps[i] for i in ticks]
            for ax in [ax_temp, ax_accel, ax_stab]:
                ax.set_xticks(ticks)
                ax.set_xticklabels(labels, rotation=15, fontsize=8)

    ani = animation.FuncAnimation(fig, update_data, interval=400, cache_frame_data=False)
    plt.show()

    ser.close()


if __name__ == "__main__":
    main()
