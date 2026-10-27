"""
AI-Based Edge-Computing Cold-Chain Monitoring System
Web Dashboard (Streamlit + Plotly + Scikit-Learn AI)
"""

import os
import sys
import time
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Import local modules
from vaccine_profiles import VACCINE_DATABASE, calculate_arrhenius_factor
from ai_model import ColdChainAI

# Page Configuration
st.set_page_config(
    page_title="AI Cold-Chain Monitor | Arrhenius Kinetics",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern medical IoT dark-mode styling
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .metric-val {
        font-size: 28px;
        font-weight: 700;
        margin-top: 4px;
    }
    .metric-label {
        font-size: 13px;
        color: #a0aec0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .status-normal { color: #00e676; }
    .status-warning { color: #ffb300; }
    .status-danger { color: #ff1744; }
    .status-freeze { color: #29b6f6; }
</style>
""", unsafe_allow_html=True)

# Initialize AI engine
@st.cache_resource
def get_ai_engine():
    return ColdChainAI()

ai = get_ai_engine()

# --- SIDEBAR CONTROLS ---
st.sidebar.image("https://img.icons8.com/fluency/96/cold.png", width=64)
st.sidebar.title("Cold-Chain AI Monitor")
st.sidebar.markdown("**Arrhenius Degradation & AI Forecasting**")

# 1. Vaccine / Medicine Selector
st.sidebar.subheader("💊 Biomedical Product Profile")
vaccine_name = st.sidebar.selectbox("Select Target Payload:", list(VACCINE_DATABASE.keys()))
profile = VACCINE_DATABASE[vaccine_name]

with st.sidebar.expander("ℹ️ Kinetic & Stability Specs", expanded=False):
    st.markdown(f"**Category:** {profile['category']}")
    st.markdown(f"**Activation Energy ($E_a$):** {profile['activation_energy_j']/1000.0:.1f} kJ/mol")
    st.markdown(f"**Safe Storage Band:** {profile['safe_min_c']}°C to {profile['safe_max_c']}°C")
    st.markdown(f"**Freeze Sensitive:** {'⚠️ YES (Irreversible damage)' if profile['freeze_sensitive'] else 'No'}")
    st.markdown(f"**Allowed Excursion Budget:** {profile['max_allowable_equiv_hours']} equivalent hours")
    st.caption(profile['description'])

# 2. Data Source Selector
st.sidebar.subheader("📡 Data Source & Simulation")
data_source = st.sidebar.selectbox(
    "Choose Data Stream:",
    [
        "🚚 Last-Mile Outreach (Heatwave + Lid Open)",
        "❄️ Accidental Freezing (Unconditioned Ice Pack)",
        "🔌 Clinic Power Outage (Passive Warming)",
        "✅ Compliant Standard Transport (2-8°C)",
        "📁 Live Logged CSV (cold_chain_log.csv)",
        "🔌 Live ESP32 Hardware (COM3)"
    ]
)

# Load selected dataset
dataset_path = None
is_live_hardware = False

if "Last-Mile" in data_source:
    dataset_path = os.path.join(os.path.dirname(__file__), "datasets", "last_mile_outreach.csv")
elif "Freezing" in data_source:
    dataset_path = os.path.join(os.path.dirname(__file__), "datasets", "accidental_freezing.csv")
elif "Power Outage" in data_source:
    dataset_path = os.path.join(os.path.dirname(__file__), "datasets", "power_outage_clinic.csv")
elif "Compliant" in data_source:
    dataset_path = os.path.join(os.path.dirname(__file__), "datasets", "compliant_transport.csv")
elif "Live Logged" in data_source:
    dataset_path = os.path.join(os.path.dirname(__file__), "cold_chain_log.csv")
else:
    is_live_hardware = True

# Load dataframe
if dataset_path and os.path.exists(dataset_path):
    df_full = pd.read_csv(dataset_path)
    # Normalize column names if needed
    col_map = {
        "Temp_Top_C": "temp_top_c", "Temp_Core_C": "temp_core_c", "Temp_Pack_C": "temp_pack_c",
        "Timestamp": "timestamp", "Status": "status_label"
    }
    df_full.rename(columns=col_map, inplace=True)
else:
    # Fallback synthetic demo
    df_full = pd.DataFrame({
        "timestamp": pd.date_range("2026-10-23 09:00", periods=100, freq="10s"),
        "temp_top_c": np.linspace(5.0, 18.0, 100),
        "temp_core_c": np.linspace(4.0, 9.5, 100),
        "temp_pack_c": np.linspace(1.5, 6.0, 100),
        "status_label": ["NORMAL_COLD_STORAGE"] * 70 + ["COOLANT_EXHAUSTION"] * 30
    })

# Time scrubber slider for scenario simulation playback
total_rows = len(df_full)
playback_idx = st.sidebar.slider("Trip Progress Scrub (%):", 5, 100, 75, step=5)
rows_to_show = max(10, int(total_rows * (playback_idx / 100.0)))
df_view = df_full.iloc[:rows_to_show].copy()

# Recalculate Arrhenius parameters dynamically for currently selected vaccine
df_view["arrhenius_factor"] = [calculate_arrhenius_factor(t, vaccine_name) for t in df_view["temp_core_c"]]
dt_hours = 5.0 / 3600.0
equiv_hours = np.cumsum(df_view["arrhenius_factor"] * dt_hours)
df_view["cumulative_equiv_hours"] = equiv_hours
stability = 100.0 * (1.0 - (equiv_hours / profile["max_allowable_equiv_hours"]))
df_view["stability_index_pct"] = np.clip(stability, 0.0, 100.0)

# Current point values
latest_row = df_view.iloc[-1]
cur_t_top = float(latest_row["temp_top_c"])
cur_t_core = float(latest_row["temp_core_c"])
cur_t_pack = float(latest_row["temp_pack_c"])
cur_accel = float(latest_row["arrhenius_factor"])
cur_stability = float(latest_row["stability_index_pct"])
cur_gradient = abs(cur_t_top - cur_t_pack)

# Run AI Inference on current window
ai_res = ai.predict(df_view[["temp_top_c", "temp_core_c", "temp_pack_c"]])

# --- HEADER SECTION ---
st.title("🛡️ Smart Cold-Chain: AI-Driven Thermal Degradation & Forecasting")
st.markdown(
    f"Active Payload: **{vaccine_name}** | Reference: **4.0°C** | "
    f"Assumed Activation Energy $E_a$: **{profile['activation_energy_j']/1000.0:.1f} kJ/mol**"
)

# --- TOP METRIC CARDS ---
col1, col2, col3, col4, col5 = st.columns(5)

# Status color logic
if cur_t_core < 0.0:
    core_color = "status-freeze"
    core_status = "FREEZING HAZARD (<0°C)"
elif 2.0 <= cur_t_core <= 8.0:
    core_color = "status-normal"
    core_status = "SAFE (2°C - 8°C)"
elif 8.0 < cur_t_core <= 20.0:
    core_color = "status-warning"
    core_status = "MILD EXCURSION"
else:
    core_color = "status-danger"
    core_status = "SEVERE EXCURSION (>20°C)"

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Payload Core Temp</div>
        <div class="metric-val {core_color}">{cur_t_core:.2f} °C</div>
        <small class="{core_color}">{core_status}</small>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Arrhenius Rate Q(T)</div>
        <div class="metric-val" style="color: #ffb300;">{cur_accel:.2f}x</div>
        <small style="color: #a0aec0;">vs 1.0x Baseline (4°C)</small>
    </div>
    """, unsafe_allow_html=True)

with col3:
    stab_color = "status-normal" if cur_stability > 80 else ("status-warning" if cur_stability > 50 else "status-danger")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Product Stability</div>
        <div class="metric-val {stab_color}">{cur_stability:.1f} %</div>
        <small style="color: #a0aec0;">Model Estimate (Assumed Ea)</small>
    </div>
    """, unsafe_allow_html=True)

with col4:
    tte_val = ai_res["time_to_excursion_min"]
    if tte_val == 0.0:
        tte_str = "EXCURSION ACTIVE"
        tte_col = "status-danger"
    elif tte_val is not None:
        tte_str = f"{tte_val:.1f} min"
        tte_col = "status-warning" if tte_val < 30 else "status-normal"
    else:
        tte_str = "> 60 min"
        tte_col = "status-normal"
        
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">AI Time-to-Excursion</div>
        <div class="metric-val {tte_col}">{tte_str}</div>
        <small style="color: #a0aec0;">Until 8.0°C Breach</small>
    </div>
    """, unsafe_allow_html=True)

with col5:
    anom_label = ai_res["anomaly_class"].replace("_", " ")
    anom_col = "status-normal" if "NORMAL" in anom_label else ("status-freeze" if "FREEZING" in anom_label else "status-danger")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">AI Diagnostic Class</div>
        <div class="metric-val {anom_col}" style="font-size: 20px;">{anom_label}</div>
        <small style="color: #a0aec0;">Confidence: {ai_res['confidence']}%</small>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# AI Recommendation Alert Banner
if "NORMAL" not in ai_res["anomaly_class"]:
    st.warning(f"🚨 **AI Diagnostic Alert:** {ai_res['recommendation']}")
else:
    st.success(f"✅ **System Health:** {ai_res['recommendation']}")

# --- MAIN CHARTS SECTION ---
tab1, tab2, tab3 = st.tabs(["📈 Spatial Thermal Profiles & AI Forecast", "⚡ Arrhenius Kinetics & Stability Decay", "🧊 Cold-Box Digital Twin"])

with tab1:
    fig_temp = go.Figure()

    x_hist = list(range(len(df_view)))

    # Historical Probes
    fig_temp.add_trace(go.Scatter(
        x=x_hist, y=df_view["temp_top_c"],
        name="Probe 1: Lid / Infiltration", line=dict(color="#ffa726", width=2)
    ))
    fig_temp.add_trace(go.Scatter(
        x=x_hist, y=df_view["temp_core_c"],
        name="Probe 2: Core Payload (Vaccine)", line=dict(color="#ff5252", width=3)
    ))
    fig_temp.add_trace(go.Scatter(
        x=x_hist, y=df_view["temp_pack_c"],
        name="Probe 3: Ice Pack / Base", line=dict(color="#00e5ff", width=2)
    ))

    # AI Forecast Cone (+15m, +30m)
    last_x = x_hist[-1]
    # In 5-sec samples: 15 mins = 180 samples, 30 mins = 360 samples
    x_forecast = [last_x, last_x + 180, last_x + 360]
    y_forecast = [cur_t_core, ai_res["pred_core_15m"], ai_res["pred_core_30m"]]

    fig_temp.add_trace(go.Scatter(
        x=x_forecast, y=y_forecast,
        name="🤖 AI Core Forecast (+15m, +30m)",
        line=dict(color="#ff4081", width=3, dash="dot"),
        mode="lines+markers"
    ))

    # WHO Standard Safe Band (2 - 8 °C)
    fig_temp.add_hrect(
        y0=2.0, y1=8.0, fillcolor="#00e676", opacity=0.12,
        layer="below", line_width=0, annotation_text="WHO Safe Band (2°C - 8°C)",
        annotation_position="top left"
    )
    # Freeze limit
    fig_temp.add_hline(y=0.0, line=dict(color="#29b6f6", dash="dash"), annotation_text="Freeze Limit (0°C)")
    # Excursion limit
    fig_temp.add_hline(y=8.0, line=dict(color="#ff1744", dash="dash"), annotation_text="Excursion Limit (8°C)")

    fig_temp.update_layout(
        title="Multi-Point Spatial Cold-Chain Thermal Profile with Predictive AI Forecast",
        xaxis_title="Time Steps (5s intervals)",
        yaxis_title="Temperature (°C)",
        template="plotly_dark",
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_temp, use_container_width=True)

with tab2:
    col_k1, col_k2 = st.columns(2)

    with col_k1:
        fig_accel = go.Figure()
        fig_accel.add_trace(go.Scatter(
            x=x_hist, y=df_view["arrhenius_factor"],
            name="Acceleration Factor Q(T)", line=dict(color="#ffd600", width=2.5)
        ))
        fig_accel.add_hline(y=1.0, line=dict(color="#00e676", dash="dash"), annotation_text="1.0x Baseline (4°C)")
        fig_accel.update_yaxes(type="log", title="Q(T) Factor [Log Scale]")
        fig_accel.update_layout(
            title=f"Arrhenius Kinetic Acceleration Q(T) for {vaccine_name}",
            xaxis_title="Time Steps",
            template="plotly_dark",
            height=380
        )
        st.plotly_chart(fig_accel, use_container_width=True)

    with col_k2:
        fig_stab = go.Figure()
        fig_stab.add_trace(go.Scatter(
            x=x_hist, y=df_view["stability_index_pct"],
            name="Remaining Stability Index", line=dict(color="#00e676" if cur_stability > 80 else "#ff1744", width=3)
        ))
        fig_stab.update_layout(
            title=f"Theoretical Product Stability Index Decay (Budget: {profile['max_allowable_equiv_hours']}h)",
            xaxis_title="Time Steps",
            yaxis_title="Stability Index (%)",
            yaxis=dict(range=[0, 105]),
            template="plotly_dark",
            height=380
        )
        st.plotly_chart(fig_stab, use_container_width=True)

with tab3:
    st.subheader("🧊 Cold-Box Spatial Thermal Gradient (Digital Twin)")
    st.markdown("Visualizes Fourier's conduction gradient across the cooler container from top boundary to base cooling pack.")

    col_box1, col_box2 = st.columns([1.5, 1])

    with col_box1:
        # 2D Heatmap of temperature across height
        height_levels = ["Top / Lid (Probe 1)", "Mid-Upper Air", "Core Payload (Probe 2)", "Mid-Lower Air", "Base / Ice Pack (Probe 3)"]
        time_slices = [-30, -20, -10, -5, -1] # recent points
        
        heat_matrix = []
        for h in [cur_t_top, (cur_t_top*0.7 + cur_t_core*0.3), cur_t_core, (cur_t_core*0.4 + cur_t_pack*0.6), cur_t_pack]:
            heat_matrix.append([h] * 5)

        fig_heat = go.Figure(data=go.Heatmap(
            z=heat_matrix,
            y=height_levels,
            x=["T-4", "T-3", "T-2", "T-1", "Current"],
            colorscale="Viridis",
            colorbar=dict(title="Temp (°C)")
        ))
        fig_heat.update_layout(
            title="Spatial Thermal Gradient Profile",
            template="plotly_dark",
            height=360
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    with col_box2:
        st.markdown(f"""
        ### Container Thermodynamic Health
        * **Top-to-Base Thermal Gradient ($\Delta T$):** `{cur_gradient:.2f} °C`
        * **Insulation Heat Flux Index:** `{'HIGH (Heat Infiltration)' if cur_gradient > 12.0 else 'NORMAL'}`
        * **Freezing Protection Status:** `{'⚠️ DANGER: Vials at freezing risk' if cur_t_pack < 1.0 and profile['freeze_sensitive'] else 'SAFE'}`
        * **Coolant Phase Status:** `{'Ice pack actively buffering latent heat' if cur_t_pack < 2.0 else 'Ice melted - Sensible heat rising'}`
        """)

# --- EXPORT DATASET ---
st.divider()
st.subheader("💾 Audit & Compliance Log Export")
csv_bytes = df_view.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Export Session Audit Log (CSV)",
    data=csv_bytes,
    file_name=f"cold_chain_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime="text/csv"
)
