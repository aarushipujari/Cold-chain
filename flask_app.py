"""
Cold-Chain Monitoring System - Research-Grade Flask Web Application
Features:
- Live REST API with MKT (Mean Kinetic Temperature)
- Dynamic Arrhenius Degradation Engine
- Random Forest AI Forecasting & Anomaly Root-Cause Analysis
- Interactive What-If Sandbox simulation with live impact delta
- Audit Certificate Generator
"""

import os
# Prevent python-dotenv from traversing parent directories into restricted folders
os.environ["FLASK_SKIP_DOTENV"] = "1"

import json
import math
from datetime import datetime
import numpy as np
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file

# Import local modules
from vaccine_profiles import VACCINE_DATABASE, calculate_arrhenius_factor
from ai_model import ColdChainAI

app = Flask(__name__)
ai = ColdChainAI()

# WHO Standard Reference Purple Color for VVM
WHO_VVM_RING_COLOR = "#4A2E70"


def compute_vvm_state(stability_pct, cur_temp=4.0, freeze_sensitive=True):
    """
    Computes WHO Vaccine Vial Monitor (VVM) indicator state with active clinical excursion awareness.

    Physical VVM principles (WHO PQS E006/IN05):
    - VVM inner square chemically polymerizes and darkens from cumulative Arrhenius exposure over time.
    - Stage 1 (Fresh, >= 85% stability): Square is white / lighter than ring.
    - Stage 2 (Mild Exposure, 50% - 85%): Square is light violet / lighter than ring.
    - Stage 3 (Discard Point, 25% - 50%): Square matches outer ring color (EXPIRED).
    - Stage 4 (Severe Exposure, < 25%): Square is darker than outer ring.

    Clinical & Operational Contextual Safeguards:
    - Active Heat Excursion (> 8.0°C):
      The physical square remains white if cumulative exposure is low (antigen chemically intact),
      BUT operational status alerts COOL IMMEDIATELY to prevent stability collapse.
    - Active Freeze Hazard (< 0.0°C) on freeze-sensitive vaccines:
      VVM measures heat only; freezing causes irreversible crystal damage while VVM stays white.
      Flags FREEZE QUARANTINE (SHAKE TEST).
    - Nominal Storage (0.0°C - 8.0°C):
      Standard WHO SAFE TO USE / USE FIRST directives.
    """
    s = max(0.0, min(100.0, float(stability_pct)))
    ring_rgb = (74, 46, 112)     # #4A2E70 standard WHO deep violet
    white_rgb = (255, 255, 255)  # #FFFFFF
    dark_rgb = (22, 8, 34)       # Deep scorched violet

    # Physical chemical square photometric color interpolation
    if s >= 50.0:
        factor = (100.0 - s) / 50.0
        r = int(white_rgb[0] + factor * (ring_rgb[0] - white_rgb[0]))
        g = int(white_rgb[1] + factor * (ring_rgb[1] - white_rgb[1]))
        b = int(white_rgb[2] + factor * (ring_rgb[2] - white_rgb[2]))
    else:
        factor = (50.0 - s) / 50.0
        r = int(ring_rgb[0] + factor * (dark_rgb[0] - ring_rgb[0]))
        g = int(ring_rgb[1] + factor * (dark_rgb[1] - ring_rgb[1]))
        b = int(ring_rgb[2] + factor * (dark_rgb[2] - ring_rgb[2]))

    inner_hex = f"#{r:02x}{g:02x}{b:02x}"

    # Determine base chemical stage from cumulative stability
    if s >= 85.0:
        stage = 1
        base_stage_name = "Stage 1 (Fresh)"
    elif s > 50.0:
        stage = 2
        base_stage_name = "Stage 2 (Mild Exposure)"
    elif s >= 25.0:
        stage = 3
        base_stage_name = "Stage 3 (Discard Point)"
    else:
        stage = 4
        base_stage_name = "Stage 4 (Severe Exposure)"

    # Operational evaluation based on live physical conditions
    is_heat_excursion = (cur_temp is not None and cur_temp > 8.0)
    is_freeze_excursion = (cur_temp is not None and cur_temp < 0.0)

    if is_freeze_excursion and freeze_sensitive:
        stage_name = f"{base_stage_name} - FREEZE HAZARD"
        action = "DO NOT USE - FREEZE QUARANTINE (SHAKE TEST)"
        action_short = "FREEZE HAZARD"
        badge_class = "danger"
        color = "#2e86de"
        desc = (
            f"CRITICAL: Active payload is at {cur_temp:.1f}°C (< 0°C). The physical VVM only measures heat, "
            f"NOT freezing! Liquid antigen may suffer irreversible crystal aggregation despite the white square. "
            f"Perform WHO shake test or quarantine batch."
        )
    elif is_heat_excursion:
        if stage == 1:
            stage_name = "Stage 1 (Viable - Excursion Active)"
            action = "VIABLE BUT EXCURSION ACTIVE - COOL IMMEDIATELY"
            action_short = "COOL IMMEDIATELY"
            badge_class = "warning"
            color = "#ff9f43"
            desc = (
                f"Inner square is white ({s:.1f}% stability remaining - antigen chemically potent), BUT the active payload is at "
                f"{cur_temp:.1f}°C (> 8°C). Immediate re-icing or transfer is required to prevent rapid stability collapse!"
            )
        elif stage == 2:
            stage_name = "Stage 2 (Mild Heat - Excursion Active)"
            action = "USE FIRST OR RESTORE 2°C-8°C IMMEDIATELY"
            action_short = "EXCURSION ACTIVE"
            badge_class = "warning"
            color = "#ff9f43"
            desc = (
                f"Inner square is light violet (mild heat accumulation) AND current temperature ({cur_temp:.1f}°C) is above 8°C. "
                f"Accelerated degradation is active. Replenish coolant or administer under FEFO immediately."
            )
        else:
            stage_name = f"{base_stage_name} - EXPIRED"
            action = "DISCARD IMMEDIATELY (EXPIRED & OVERHEATED)"
            action_short = "DISCARD"
            badge_class = "danger"
            color = "#ff4757"
            desc = f"Discard point reached (stability exhausted to {s:.1f}%) and container is overheated ({cur_temp:.1f}°C). Do not administer."
    else:
        # Nominal storage within 0.0°C to 8.0°C
        if stage == 1:
            stage_name = "Stage 1 (Fresh)"
            action = "SAFE TO USE (VACCINE VIABLE)"
            action_short = "SAFE TO USE"
            badge_class = "success"
            color = "#10ac84"
            desc = "Inner square is distinctly lighter than the outer circle. Cold-chain storage is nominal (2°C-8°C)."
        elif stage == 2:
            stage_name = "Stage 2 (Mild Exposure)"
            action = "SAFE TO USE - USE FIRST (FEFO)"
            action_short = "USE FIRST (FEFO)"
            badge_class = "warning"
            color = "#ff9f43"
            desc = "Inner square has turned light violet, but is still lighter than the outer ring. Viable, but prioritize for immediate dispensing (FEFO)."
        elif stage == 3:
            stage_name = "Stage 3 (Discard Point)"
            action = "DO NOT USE - DISCARD POINT REACHED"
            action_short = "DISCARD"
            badge_class = "danger"
            color = "#ff4757"
            desc = "Inner square matches the color of the outer ring. Cumulative Arrhenius stability budget has expired. Discard vial."
        else:
            stage_name = "Stage 4 (Severe Exposure)"
            action = "DISCARD IMMEDIATELY"
            action_short = "REJECT"
            badge_class = "danger"
            color = "#ff3838"
            desc = "Inner square is darker than the outer ring. Severe thermal exposure. Discard immediately."

    return {
        "stage": stage,
        "stage_name": stage_name,
        "action": action,
        "action_short": action_short,
        "badge_class": badge_class,
        "color": color,
        "desc": desc,
        "inner_hex": inner_hex,
        "ring_hex": WHO_VVM_RING_COLOR,
        "is_heat_excursion": is_heat_excursion,
        "is_freeze_excursion": is_freeze_excursion
    }


def calculate_mkt(temps_c, delta_h=83140.0):
    if len(temps_c) == 0:
        return 4.0
    r = 8.314 # J/(mol*K)
    temps_k = [t + 273.15 for t in temps_c if not np.isnan(t)]
    if not temps_k:
        return 4.0
    sum_exp = sum(math.exp(-delta_h / (r * tk)) for tk in temps_k)
    mkt_k = (delta_h / r) / (-math.log(sum_exp / len(temps_k)))
    return round(mkt_k - 273.15, 2)


def load_scenario_df(scenario_name):
    path = os.path.join(os.path.dirname(__file__), "datasets", f"{scenario_name}.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    if scenario_name == "live_log" and os.path.exists("cold_chain_log.csv"):
        return pd.read_csv("cold_chain_log.csv")
    return None


@app.route('/')
def index():
    vaccines = list(VACCINE_DATABASE.keys())
    return render_template('index.html', vaccines=vaccines, default_vaccine=vaccines[0])


@app.route('/api/telemetry', methods=['GET'])
def get_telemetry():
    scenario = request.args.get('scenario', 'last_mile_outreach')
    vaccine = request.args.get('vaccine', 'Hepatitis B Vaccine (Recombinant)')
    scrub_pct = float(request.args.get('scrub_pct', 70.0))

    # Sandbox Overrides
    ambient_override = request.args.get('ambient', None)
    lid_override = (request.args.get('lid_open', 'false').lower() == 'true')

    profile = VACCINE_DATABASE.get(vaccine, VACCINE_DATABASE["Hepatitis B Vaccine (Recombinant)"])
    df = load_scenario_df(scenario)

    if df is None or len(df) == 0:
        return jsonify({"error": "No data available"})

    total_len = len(df)
    active_len = max(10, int(total_len * (scrub_pct / 100.0)))
    sub_df = df.iloc[:active_len].copy()

    # Base baseline for delta comparison
    baseline_core = float(sub_df["temp_core_c"].iloc[-1])
    baseline_top = float(sub_df["temp_top_c"].iloc[-1])

    # Apply sandbox stress modifiers
    sandbox_active = False
    if ambient_override is not None:
        amb = float(ambient_override)
        if abs(amb - 32.0) > 0.5:
            sandbox_active = True
            delta_amb = (amb - 32.0)
            sub_df["temp_top_c"] = sub_df["temp_top_c"] + delta_amb * 0.45
            sub_df["temp_core_c"] = sub_df["temp_core_c"] + delta_amb * 0.22

    if lid_override:
        sandbox_active = True
        n_pts = min(15, len(sub_df))
        idx_tail = sub_df.index[-n_pts:]
        sub_df.loc[idx_tail, "temp_top_c"] = sub_df.loc[idx_tail, "temp_top_c"] + 14.5
        sub_df.loc[idx_tail, "temp_core_c"] = sub_df.loc[idx_tail, "temp_core_c"] + 4.8

    # Recalculate Arrhenius parameters for selected vaccine
    arrhenius_factors = [calculate_arrhenius_factor(t, vaccine) for t in sub_df["temp_core_c"]]
    sub_df["arrhenius_factor"] = np.round(arrhenius_factors, 2)
    dt_hours = 5.0 / 3600.0
    equiv_hours = np.cumsum(sub_df["arrhenius_factor"] * dt_hours)
    sub_df["cumulative_equiv_hours"] = np.round(equiv_hours, 4)
    stability = 100.0 * (1.0 - (equiv_hours / profile["max_allowable_equiv_hours"]))
    sub_df["stability_index_pct"] = np.round(np.clip(stability, 0.0, 100.0), 2)

    # Current point values
    latest = sub_df.iloc[-1]
    cur_top = round(float(latest["temp_top_c"]), 2)
    cur_core = round(float(latest["temp_core_c"]), 2)
    cur_pack = round(float(latest["temp_pack_c"]), 2)
    cur_accel = round(float(latest["arrhenius_factor"]), 2)
    cur_stab = round(float(latest["stability_index_pct"]), 2)
    cur_equiv = round(float(latest["cumulative_equiv_hours"]), 4)

    # Calculate MKT
    mkt_val = calculate_mkt(sub_df["temp_core_c"].tolist(), profile["activation_energy_j"])

    # AI Prediction
    ai_res = ai.predict(sub_df[["temp_top_c", "temp_core_c", "temp_pack_c"]])

    # Downsample history to 50 points for smooth Chart.js rendering
    step = max(1, len(sub_df) // 50)
    chart_df = sub_df.iloc[::step]
    labels = [str(i) for i in range(len(chart_df))]

    # Safety Classification & PQS Verdict
    excursion_points = (sub_df["temp_core_c"] > 8.0).sum()
    freeze_points = (sub_df["temp_core_c"] < 0.0).sum()
    
    if freeze_points > 0 and profile["freeze_sensitive"]:
        compliance_verdict = "REJECTED (IRREVERSIBLE FREEZE DAMAGE)"
        verdict_class = "danger"
    elif cur_stab < 70.0:
        compliance_verdict = "QUARANTINE (STABILITY BUDGET EXHAUSTED)"
        verdict_class = "danger"
    elif excursion_points > 0:
        compliance_verdict = "CONDITIONAL ACCEPT (EXCURSION MONITORED)"
        verdict_class = "warning"
    else:
        compliance_verdict = "PASSED (WHO PQS COMPLIANT)"
        verdict_class = "success"

    # Sandbox impact metrics
    sandbox_impact = {
        "active": sandbox_active,
        "delta_core": round(cur_core - baseline_core, 2),
        "delta_top": round(cur_top - baseline_top, 2),
        "accel_jump": cur_accel,
        "tte_impact": ai_res["time_to_excursion_min"],
        "anomaly": str(ai_res["anomaly_class"]).replace("_", " ")
    }

    # WHO Vaccine Vial Monitor (VVM) indicator state with active excursion check
    vvm_res = compute_vvm_state(cur_stab, cur_temp=cur_core, freeze_sensitive=profile.get("freeze_sensitive", True))

    return jsonify({
        "current": {
            "t_top": cur_top,
            "t_core": cur_core,
            "t_pack": cur_pack,
            "gradient": round(abs(cur_top - cur_pack), 2),
            "accel": cur_accel,
            "stability": cur_stab,
            "equiv_hours": cur_equiv,
            "mkt_c": mkt_val,
            "vaccine_name": vaccine,
            "category": profile["category"],
            "ea_kj": profile["activation_energy_j"] / 1000.0,
            "freeze_sensitive": profile["freeze_sensitive"],
            "compliance_verdict": compliance_verdict,
            "verdict_class": verdict_class
        },
        "vvm": vvm_res,
        "ai": {
            "pred_15m": float(ai_res["pred_core_15m"]),
            "pred_30m": float(ai_res["pred_core_30m"]),
            "tte_min": ai_res["time_to_excursion_min"],
            "anomaly_class": str(ai_res["anomaly_class"]).replace("_", " "),
            "confidence": float(ai_res["confidence"]),
            "recommendation": str(ai_res["recommendation"])
        },
        "sandbox": sandbox_impact,
        "chart": {
            "labels": labels,
            "t_top": chart_df["temp_top_c"].tolist(),
            "t_core": chart_df["temp_core_c"].tolist(),
            "t_pack": chart_df["temp_pack_c"].tolist(),
            "accel": chart_df["arrhenius_factor"].tolist(),
            "stability": chart_df["stability_index_pct"].tolist()
        }
    })


@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    scenario = request.args.get('scenario', 'last_mile_outreach')
    path = os.path.join(os.path.dirname(__file__), "datasets", f"{scenario}.csv")
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=f"cold_chain_{scenario}.csv")
    return jsonify({"error": "File not found"}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[*] Starting Enhanced Cold-Chain Flask Dashboard on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, load_dotenv=False)
