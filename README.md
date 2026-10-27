# Cold-Chain Thermal Degradation Monitoring System

**Development of an Edge-Computing Cold-Chain System for Real-Time Thermal Degradation Estimation Using Arrhenius Kinetics**

---

## 📁 Project Structure

```text
Desktop/PROJECTS/cold-chain/
├── dashboard.py                  # Real-time multi-zone graphical dashboard & CSV logger
├── run_dashboard.bat             # One-click desktop launcher
├── cold_chain_log.csv            # Auto-generated timestamped data log
├── esp32_cold_chain/
│   └── esp32_cold_chain.ino      # ESP32 Arrhenius Edge Computing firmware
└── README.md                     # Documentation
```

---

## 🔌 Hardware Wiring & Pinout

| Sensor Lead | Function | ESP32 Pin | Notes |
| :--- | :--- | :--- | :--- |
| **Yellow / White** | **DATA** | **GPIO 23 (D23)** | Shared OneWire bus |
| **Red** | **VCC** | **3V3** | Power rail |
| **Black / Blue** | **GND** | **GND** | Ground rail |
| **Pull-Up Resistor** | $\approx 2.35\text{ k}\Omega$ | **Between D23 and 3V3** | Two $4.7\text{ k}\Omega$ in parallel |

---

## 🔬 Sensor Hardware Addresses

* **Probe 1 (Lid / Ambient):** `28 EE 0E 70 00 00 00 2E`
* **Probe 2 (Core Payload):** `28 9E E4 6D 00 00 00 74`
* **Probe 3 (Ice Pack / Base):** `28 AD 79 70 00 00 00 3E`

---

## 🚀 How to Run the Dashboard

1. **Close the Serial Monitor in Arduino IDE** (frees up COM3).
2. **Double-click `run_dashboard.bat`** (or run `python dashboard.py`).
3. The live graphical window will open and stream live curves while saving data to `cold_chain_log.csv`.
