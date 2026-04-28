import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Battery Sizer Pro", layout="wide")
st.title("🔋 Professional Battery Capacity Sizing Tool")

# --- SIDEBAR: SYSTEM PARAMETERS ---
with st.sidebar:
    st.header("1. System Architecture")
    v_batt_target = st.number_input("Target System Voltage (V)", value=300.0, step=1.0, format="%.2f")
    v_cutoff_pct = st.slider("Voltage Cut-off (%)", 0.0, 20.0, 10.0) / 100.0
    
    st.header("2. Efficiency & Safety")
    eta_disch = st.slider("Discharge Efficiency (%)", 70.0, 100.0, 95.0) / 100.0
    safety_buffer = st.slider("Safety Buffer (%)", 0.0, 100.0, 10.0) / 100.0
    max_dod = st.slider("Max Depth of Discharge (%)", 10.0, 100.0, 80.0) / 100.0

    st.header("3. Charging Parameters")
    max_charge_p = st.number_input("Max Charge Power (W)", value=5000.0, step=100.0)
    eta_charge = st.slider("Charge Efficiency (%)", 70.0, 99.0, 90.0) / 100.0
    taper_start_pct = st.slider("Taper Phase Starts at (%)", 50, 95, 80) / 100.0
    taper_multiplier = st.number_input("Taper Time Multiplier", value=1.5, step=0.1)
    max_charge_c_limit = st.number_input("Max Allowable Charge C-Rate", value=0.5, step=0.1)

    st.header("4. Degradation & Environment")
    op_temp = st.number_input("Operating Temp (°C)", value=25.0, step=0.5)
    ret_cycle = st.slider("Retention after Cycle Life (%)", 10.0, 100.0, 80.0) / 100.0
    ret_cal = st.slider("Retention after Calendar Life (%)", 10.0, 100.0, 90.0) / 100.0
    temp_penalty_rate = st.number_input("Temp Penalty (% per °C > 25°C)", value=2.0, step=0.1) / 100.0

# --- MAIN INTERFACE: LOAD PROFILE ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Load Schedule")
    load_df = pd.DataFrame([
        {"Name": "Base Load", "Power (W)": 1000.0, "Start Hour": 0.0, "Duration (h)": 24.0, "Peak Factor": 1.0},
        {"Name": "Heavy Load", "Power (W)": 5000.0, "Start Hour": 10.0, "Duration (h)": 2.5, "Peak Factor": 2.0},
    ])
    
    edited_loads = st.data_editor(
        load_df, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Power (W)": st.column_config.NumberColumn(format="%.2f"),
            "Start Hour": st.column_config.NumberColumn(min_value=0, max_value=24, format="%.2f"),
            "Duration (h)": st.column_config.NumberColumn(format="%.2f"),
            "Peak Factor": st.column_config.NumberColumn(format="%.2f"),
        }
    )

    # Power vs Time Graph Logic
    time_steps = np.arange(0, 24, 0.25)
    power_timeline = np.zeros(len(time_steps))
    for _, row in edited_loads.iterrows():
        for i, t in enumerate(time_steps):
            if float(row['Start Hour']) <= t < (float(row['Start Hour']) + float(row['Duration (h)'])):
                power_timeline[i] += float(row['Power (W)'])
    
    st.area_chart(pd.DataFrame({"Hour": time_steps, "Power Draw (W)": power_timeline}), x="Hour", y="Power Draw (W)")

    # Hardware Module Specifications
    st.divider()
    st.subheader("5. Module Specifications (COTS)")
    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        m_volt = st.number_input("Module Nom. Voltage (V)", value=311.0, step=0.1)
        m_cap = st.number_input("Module Capacity (Ah)", value=57.0, step=0.1)
    with mc2:
        m_cont_i = st.number_input("Module Cont. Discharge (A)", value=15.0, step=0.1)
        m_peak_i = st.number_input("Module Peak Discharge (A)", value=20.0, step=0.1)
    with mc3:
        m_weight = st.number_input("Module Weight (kg)", value=15)
