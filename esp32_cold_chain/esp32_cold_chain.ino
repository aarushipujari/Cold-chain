#include <OneWire.h>
#include <DallasTemperature.h>
#include <math.h>

// GPIO Pin where all 3 DS18B20 data wires are connected
#define ONE_WIRE_BUS 23

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// Arrhenius Degradation Parameters (WHO 2°C - 8°C Baseline)
const float R_GAS = 8.314;           // J/(mol*K)
const float E_A   = 83140.0;         // Assumed Activation Energy: 83.14 kJ/mol
const float T_REF_K = 277.15;        // Reference Temp: 4.0 °C in Kelvin
const float MAX_EQUIV_HRS = 48.0;    // Allowable exposure budget

unsigned long startTime = 0;
unsigned long lastSampleTime = 0;
float cumulativeEquivHours = 0.0;
float stabilityIndex = 100.0;
int deviceCount = 0;

DeviceAddress addr1, addr2, addr3;

// Helper to print 64-bit ROM address
void printAddress(DeviceAddress deviceAddress) {
  for (uint8_t i = 0; i < 8; i++) {
    if (deviceAddress[i] < 16) Serial.print("0");
    Serial.print(deviceAddress[i], HEX);
    if (i < 7) Serial.print(":");
  }
}

// Compute Arrhenius rate multiplier Q(T)
float calculateArrheniusRate(float tempC) {
  if (tempC <= -20.0) return 0.01;
  float tempK = tempC + 273.15;
  float exponent = (E_A / R_GAS) * ((1.0 / T_REF_K) - (1.0 / tempK));
  return exp(exponent);
}

void setup() {
  Serial.begin(115200);
  delay(1500);

  Serial.println("\n========================================================");
  Serial.println("   COLD-CHAIN 3-ZONE MULTI-POINT SENSOR TELEMETRY");
  Serial.println("========================================================");

  sensors.begin();
  deviceCount = sensors.getDeviceCount();
  Serial.printf("Bus Status: Found %d DS18B20 sensor(s) on GPIO %d\n", deviceCount, ONE_WIRE_BUS);

  if (deviceCount < 3) {
    Serial.println("\n[!] WARNING: Fewer than 3 sensors detected!");
    Serial.println("    - Check that all 3 yellow wires connect to GPIO 23");
    Serial.println("    - Check 4.7k ohm resistor between 3V3 and GPIO 23\n");
  }

  // Print addresses of each probe found
  if (sensors.getAddress(addr1, 0)) {
    Serial.print("  [Probe 1 - Lid / Top]       Address: ");
    printAddress(addr1);
    Serial.println();
  }
  if (sensors.getAddress(addr2, 1)) {
    Serial.print("  [Probe 2 - Core Payload]    Address: ");
    printAddress(addr2);
    Serial.println();
  }
  if (sensors.getAddress(addr3, 2)) {
    Serial.print("  [Probe 3 - Ice Pack / Base] Address: ");
    printAddress(addr3);
    Serial.println();
  }

  Serial.println("========================================================\n");
  startTime = millis();
  lastSampleTime = millis();
}

void loop() {
  // If sensors were missing at boot, re-scan
  if (deviceCount < 3) {
    deviceCount = sensors.getDeviceCount();
  }

  // Request temperature conversions from all 3 probes
  sensors.requestTemperatures();

  float t_top  = sensors.getTempCByIndex(0); // Probe 1: Lid / Top
  float t_core = sensors.getTempCByIndex(1); // Probe 2: Core Payload (Vaccine)
  float t_pack = sensors.getTempCByIndex(2); // Probe 3: Ice Pack / Base

  // Validate core reading
  bool validCore = (t_core > -40.0 && t_core < 75.0 && t_core != 85.0);

  // Time delta integration
  unsigned long now = millis();
  float dt_hours = (float)(now - lastSampleTime) / 3600000.0;
  lastSampleTime = now;

  float accelFactor = 1.0;
  if (validCore) {
    accelFactor = calculateArrheniusRate(t_core);
    cumulativeEquivHours += (accelFactor * dt_hours);
    stabilityIndex = 100.0 * (1.0 - (cumulativeEquivHours / MAX_EQUIV_HRS));
    if (stabilityIndex < 0.0) stabilityIndex = 0.0;
  }

  // WHO Cold-Chain Status Classification
  String status = "NORMAL (2°C - 8°C)";
  if (!validCore) {
    status = "SENSOR DISCONNECTED";
  } else if (t_core < 0.0) {
    status = "CRITICAL: FREEZING HAZARD (< 0°C)";
  } else if (t_core > 8.0 && t_core <= 20.0) {
    status = "WARNING: HIGH TEMP EXCURSION (8°C - 20°C)";
  } else if (t_core > 20.0) {
    status = "ALERT: SEVERE THERMAL EXCURSION (> 20°C)";
  }

  // Format time elapsed
  unsigned long totalSec = (now - startTime) / 1000;
  int mins = totalSec / 60;
  int secs = totalSec % 60;

  // Print exact formatted block (parsed by Python dashboards)
  Serial.println("--------------------------------------------------------");
  Serial.printf("Time Elapsed: %02dm %02ds | Status: %s\n", mins, secs, status.c_str());
  Serial.println("--------------------------------------------------------");
  
  if (t_top == DEVICE_DISCONNECTED_C) Serial.println("  [Lid / Top]       Probe 1: DISCONNECTED (-127°C)");
  else Serial.printf("  [Lid / Top]       Probe 1: %.2f °C\n", t_top);

  if (t_core == DEVICE_DISCONNECTED_C) Serial.println("  [Payload / Core]  Probe 2: DISCONNECTED (-127°C)");
  else Serial.printf("  [Payload / Core]  Probe 2: %.2f °C\n", t_core);

  if (t_pack == DEVICE_DISCONNECTED_C) Serial.println("  [Ice Pack / Base] Probe 3: DISCONNECTED (-127°C)");
  else Serial.printf("  [Ice Pack / Base] Probe 3: %.2f °C\n", t_pack);

  Serial.println("--------------------------------------------------------");
  Serial.printf("  Arrhenius Degradation Factor : %.2fx normal rate\n", accelFactor);
  Serial.printf("  Cumulative Thermal Exposure  : %.4f equiv. hrs\n", cumulativeEquivHours);
  Serial.printf("  Estimated Stability Index    : %.2f %%\n", stabilityIndex);
  Serial.println("========================================================\n");

  delay(1500);
}