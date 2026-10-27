"""
Cold-Chain Realistic Transport Dataset Generator
Simulates physics-based thermodynamic trajectories for standard cold-chain scenarios:
1. Last-Mile Rural Outreach (Ambient Heatwave + Lid Openings)
2. Storage Refrigerator Power Outage (Passive Runaway)
3. Accidental Freezing Excursion (Unconditioned Ice Pack)
4. Compliant Controlled Transport (WHO PQS Standard 2-8°C)
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from vaccine_profiles import calculate_arrhenius_factor

DATASET_DIR = os.path.join(os.path.dirname(__file__), "datasets")
os.makedirs(DATASET_DIR, exist_ok=True)


def generate_trip_data(scenario="last_mile_outreach", duration_hours=3.5, step_seconds=5):
    """
    Generates a timestamped multi-point thermodynamic trajectory.
    Physics modeled:
    - Heat conduction: Fourier's law through insulation
    - Latent heat buffer: Ice melting plateau at 0°C
    - Convective infiltration: Lid openings
    - Thermal inertia of liquid vial core
    """
    np.random.seed(42)
    steps = int(duration_hours * 3600 / step_seconds)
    timestamps = [datetime(2026, 10, 23, 8, 0, 0) + timedelta(seconds=i * step_seconds) for i in range(steps)]
    
    t_top = np.zeros(steps)
    t_core = np.zeros(steps)
    t_pack = np.zeros(steps)
    labels = []
    
    # Initial conditions
    if scenario == "last_mile_outreach":
        # Ambient 34°C - 38°C. Carrier box with melting ice.
        cur_top = 6.0
        cur_core = 3.5
        cur_pack = 0.5
        ice_latent_capacity = steps * 0.65 # Ice finishes melting at 65% of trip
        
        for i in range(steps):
            frac = i / steps
            ambient = 32.0 + 6.0 * np.sin(frac * np.pi) # Ambient warms to 38°C
            
            # Lid opening event between 40% and 50% of trip (e.g. 5 minutes open)
            lid_open = (0.42 <= frac <= 0.48)
            
            # Pack physics
            if i < ice_latent_capacity:
                cur_pack += 0.0003 + np.random.normal(0, 0.02)
                cur_pack = np.clip(cur_pack, 0.2, 1.8)
            else:
                # Ice exhausted, pack warms up
                cur_pack += 0.0035 * (ambient - cur_pack) * (step_seconds / 60.0)
            
            # Top boundary physics
            if lid_open:
                cur_top += 0.08 * (ambient - cur_top) * (step_seconds / 60.0)
                label = "LID_SEAL_BREACH"
            else:
                cur_top += 0.015 * (ambient - cur_top) * (step_seconds / 60.0)
                if i >= ice_latent_capacity:
                    label = "COOLANT_EXHAUSTION"
                else:
                    label = "NORMAL_COLD_STORAGE"
            
            # Core payload physics (thermal inertia from pack and top)
            target_core = 0.65 * cur_pack + 0.35 * cur_top
            cur_core += 0.012 * (target_core - cur_core) * (step_seconds / 60.0) + np.random.normal(0, 0.01)
            
            t_top[i] = round(cur_top, 2)
            t_core[i] = round(cur_core, 2)
            t_pack[i] = round(cur_pack, 2)
            labels.append(label)

    elif scenario == "accidental_freezing":
        # Unconditioned frozen ice pack at -15°C placed directly against vials
        cur_top = 3.0
        cur_core = 1.5
        cur_pack = -8.0
        
        for i in range(steps):
            cur_pack += 0.002 * (25.0 - cur_pack) * (step_seconds / 60.0)
            cur_top += 0.003 * (25.0 - cur_top) * (step_seconds / 60.0)
            cur_core += 0.018 * (cur_pack - cur_core) * (step_seconds / 60.0) + np.random.normal(0, 0.01)
            
            t_top[i] = round(cur_top, 2)
            t_core[i] = round(cur_core, 2)
            t_pack[i] = round(cur_pack, 2)
            labels.append("FREEZING_HAZARD" if cur_core < 0.0 or cur_pack < 0.0 else "NORMAL_COLD_STORAGE")

    elif scenario == "power_outage_clinic":
        # Passive warming from 4°C to 28°C
        cur_top = 4.2
        cur_core = 3.8
        cur_pack = 2.5
        ambient = 29.0
        for i in range(steps):
            cur_top += 0.008 * (ambient - cur_top) * (step_seconds / 60.0)
            cur_pack += 0.004 * (ambient - cur_pack) * (step_seconds / 60.0)
            cur_core += 0.005 * (cur_top - cur_core) * (step_seconds / 60.0) + np.random.normal(0, 0.01)
            
            t_top[i] = round(cur_top, 2)
            t_core[i] = round(cur_core, 2)
            t_pack[i] = round(cur_pack, 2)
            labels.append("COOLANT_EXHAUSTION" if cur_core > 8.0 else "NORMAL_COLD_STORAGE")

    else: # Compliant
        for i in range(steps):
            t_top[i] = round(4.5 + 0.8 * np.sin(i / 100.0) + np.random.normal(0, 0.05), 2)
            t_core[i] = round(4.0 + 0.3 * np.sin(i / 150.0) + np.random.normal(0, 0.02), 2)
            t_pack[i] = round(2.5 + 0.4 * np.sin(i / 120.0) + np.random.normal(0, 0.03), 2)
            labels.append("NORMAL_COLD_STORAGE")

    df = pd.DataFrame({
        "timestamp": timestamps,
        "temp_top_c": t_top,
        "temp_core_c": t_core,
        "temp_pack_c": t_pack,
        "thermal_gradient": np.round(np.abs(t_top - t_pack), 2),
        "status_label": labels
    })
    
    # Calculate Arrhenius factor and stability index for Hepatitis B default
    accel = [calculate_arrhenius_factor(t, "Hepatitis B Vaccine (Recombinant)") for t in df["temp_core_c"]]
    df["arrhenius_factor"] = np.round(accel, 2)
    
    dt_hours = step_seconds / 3600.0
    equiv_hours = np.cumsum(df["arrhenius_factor"] * dt_hours)
    df["cumulative_equiv_hours"] = np.round(equiv_hours, 4)
    
    # Max allowable 72 hours
    stability = 100.0 * (1.0 - (equiv_hours / 72.0))
    df["stability_index_pct"] = np.round(np.clip(stability, 0.0, 100.0), 2)
    
    filename = os.path.join(DATASET_DIR, f"{scenario}.csv")
    df.to_csv(filename, index=False)
    print(f"[+] Generated dataset: {filename} ({len(df)} rows)")
    return filename


if __name__ == "__main__":
    generate_trip_data("last_mile_outreach")
    generate_trip_data("accidental_freezing")
    generate_trip_data("power_outage_clinic")
    generate_trip_data("compliant_transport")
