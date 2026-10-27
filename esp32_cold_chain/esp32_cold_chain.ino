#include <OneWire.h>
#include <math.h>

#define ONE_WIRE_BUS 23   // Pin D23 on ESP32

OneWire ds(ONE_WIRE_BUS);

// Exact permanent 64-bit hardware addresses of your 3 DS18B20 sensors
const byte sensor1[8] = { 0x28, 0xEE, 0x0E, 0x70, 0x00, 0x00, 0x00, 0x2E }; // Top / Lid
const byte sensor2[8] = { 0x28, 0x9E, 0xE4, 0x6D, 0x00, 0x00, 0x00, 0x74 }; // Core / Payload
const byte sensor3[8] = { 0x28, 0xAD, 0x79, 0x70, 0x00, 0x00, 0x00, 0x3E }; // Bottom / Ice Pack

// Arrhenius Kinetics Parameters (WHO Cold-Chain Baseline)
const float R_GAS = 8.314;                  // J/(mol*K)
const float E_A   = 83140.0;                // Assumed Activation energy: 83.14 kJ/mol
const float T_REF_K = 277.15;               // Reference Temp: 4.0 °C in Kelvin
const float MAX_ALLOWABLE_EQUIV_HRS = 48.0; // Allowed equivalent hours at reference temperature

// State Tracking
unsigned long lastSampleTime = 0;
float cumulativeEquivalentHours = 0.0;
float stabilityIndex = 100.0;
unsigned long badReadCount = 0;
unsigned long totalSampleCount = 0;

// Last known valid temperatures
float valid_top = NAN;
float valid_core = NAN;
float valid_pack = NAN;

// 1. REJECT INVALID READINGS BEFORE CALCULATION
bool readAndValidateSensor(const byte addr[8], float &outputTemp, float lastValid) {
  byte data[9];
  ds.reset();
  ds.select(addr);
  ds.write(0xBE); // Read Scratchpad

  for (int i = 0; i < 9; i++) data[i] = ds.read();

  // Condition A: CRC8 checksum verification
  if (OneWire::crc8(data, 8) != data[8]) {
    return false;
  }

  int16_t raw = (data[1] << 8) | data[0];
  float celsius = (float)raw / 16.0;

  // Condition B: Reject -127.0°C (Dallas disconnected code) and physical sensor limits
  if (celsius <= -50.0 || celsius >= 70.0 || fabs(celsius - (-127.0)) < 0.1) {
    return false;
  }

  // Condition C: Reject exactly 85.0°C (DS18B20 power-on reset state)
  if (fabs(celsius - 85.0) < 0.05) {
    return false;
  }

  // Condition D: Rate-of-change limit (> 5.0°C jump in a 2-second interval)
  if (!isnan(lastValid)) {
    if (fabs(celsius - lastValid) > 5.0) {
      return false; // Physical impossibility in 2 seconds
    }
  }

  outputTemp = celsius;
  return true;
}

// Compute Arrhenius Acceleration Factor Q(T)
float calculateArrheniusRate(float tempC) {
  if (tempC <= -20.0) return 0.01;
  float tempK = tempC + 273.15;
  float exponent = (E_A / R_GAS) * ((1.0 / T_REF_K) - (1.0 / tempK));
  return exp(exponent);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n========================================================");
  Serial.println("   EDGE COLD-CHAIN REAL-TIME ARRHENIUS DEGRADATION SYSTEM");
  Serial.println("========================================================\n");
  lastSampleTime = millis();
}

void loop() {
  totalSampleCount++;

  // 1. Broadcast temperature conversion
  ds.reset();
  ds.skip();
  ds.write(0x44);
  delay(750); // 750ms for 12-bit conversion

  // 2. Read and validate each sensor individually
  float raw_t1, raw_t2, raw_t3;
  bool ok1 = readAndValidateSensor(sensor1, raw_t1, valid_top);
  bool ok2 = readAndValidateSensor(sensor2, raw_t2, valid_core);
  bool ok3 = readAndValidateSensor(sensor3, raw_t3, valid_pack);

  bool allValid = ok1 && ok2 && ok3;
  if (!allValid) {
    badReadCount++;
  }

  if (ok1) valid_top = raw_t1;
  if (ok2) valid_core = raw_t2;
  if (ok3) valid_pack = raw_t3;

  // Time delta calculation
  unsigned long now = millis();
  float dt_hours = (float)(now - lastSampleTime) / 3600000.0;
  lastSampleTime = now;

  // 2. ONLY INTEGRATE VALID DATA INTO STABILITY INDEX!
  float accelFactor = 1.0;
  if (ok2) {
    accelFactor = calculateArrheniusRate(valid_core);
    cumulativeEquivalentHours += (accelFactor * dt_hours);
    stabilityIndex = 100.0 * (1.0 - (cumulativeEquivalentHours / MAX_ALLOWABLE_EQUIV_HRS));
    if (stabilityIndex < 0.0) stabilityIndex = 0.0;
  } else if (!isnan(valid_core)) {
    // Current sample rejected: compute display factor on held value, DO NOT ACCUMULATE
    accelFactor = calculateArrheniusRate(valid_core);
  }

  // 3. Cold-Chain Safety Classification
  String status = "NORMAL (2°C - 8°C)";
  float core_disp = isnan(valid_core) ? 4.0 : valid_core;
  if (core_disp < 0.0) {
    status = "CRITICAL: FREEZING HAZARD (< 0°C)";
  } else if (core_disp > 8.0 && core_disp <= 20.0) {
    status = "WARNING: MILD EXCURSION (8°C - 20°C)";
  } else if (core_disp > 20.0) {
    status = "ALERT: SEVERE THERMAL EXCURSION (> 20°C)";
  }

  // 4. Output formatted data block
  unsigned long totalSeconds = now / 1000;
  int mins = totalSeconds / 60;
  int secs = totalSeconds % 60;

  Serial.println("--------------------------------------------------------");
  Serial.printf("Time Elapsed: %02dm %02ds | Status: %s\n", mins, secs, status.c_str());
  Serial.println("--------------------------------------------------------");
  
  if (ok1) Serial.printf("  [Lid / Top]       Probe 1: %.2f °C\n", valid_top);
  else     Serial.printf("  [Lid / Top]       Probe 1: REJECTED (Holding %.2f °C)\n", valid_top);

  if (ok2) Serial.printf("  [Payload / Core]  Probe 2: %.2f °C\n", valid_core);
  else     Serial.printf("  [Payload / Core]  Probe 2: REJECTED (Holding %.2f °C)\n", valid_core);

  if (ok3) Serial.printf("  [Ice Pack / Base] Probe 3: %.2f °C\n", valid_pack);
  else     Serial.printf("  [Ice Pack / Base] Probe 3: REJECTED (Holding %.2f °C)\n", valid_pack);

  Serial.println("--------------------------------------------------------");
  Serial.printf("  Arrhenius Degradation Factor : %.2fx normal rate\n", accelFactor);
  Serial.printf("  Cumulative Thermal Exposure  : %.4f equiv. hrs\n", cumulativeEquivalentHours);
  Serial.printf("  Estimated Stability Index    : %.2f %% (Assumed Ea=83.14 kJ/mol)\n", stabilityIndex);
  Serial.printf("  Sample Integrity             : %s | Bad Reads: %lu/%lu\n", 
                allValid ? "VALID" : "GLITCH REJECTED", badReadCount, totalSampleCount);
  Serial.println("========================================================\n");

  delay(1250);
}
