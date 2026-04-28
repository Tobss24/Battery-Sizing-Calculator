import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Battery Sizer Pro", layout="wide")
st.title("🔋 Professional Battery Capacity Sizing Tool")

with st.sidebar:
    st.header("1. System Architecture")
    v_batt = st.number_input("Battery Module Voltage (V)", value=48.0, step=0.1, format="%.2f")
    v_cutoff = st.slider("Voltage Cut-off (%)", 0.0, 20.0, 10.0) / 100.0
    
    st.header("2. Discharge Eff. & Safety")
    eta_dc_dc = st.slider("Discharge Efficiency (%)", 70.0, 100.0, 95.0) / 100.0
    safety_buffer = st.slider("Safety Buffer (%)", 0.0, 100.0, 10.0) / 100.0
    max_dod = st.slider("Max Depth of Discharge (%)", 10.0, 100.0, 80.0) / 100.0

    st.header("3. Charging Parameters")
    max_charge_p = st.number_input("Max Charge Power (W)", value=500.0, step=10.0)
    eta_charge = st.slider("Charge Efficiency (%)", 70.0, 99.0, 90.0) / 100.0
    # NEW: Taper Logic
    taper_start_pct = st.slider("Taper Phase Starts at (%)", 50, 95, 80) / 100.0
    taper_multiplier = st.number_input("Taper Time Multiplier", value=1.5, step=0.1)
    max_charge_c_rate = st.number_input("Max Allowable Charge C-Rate", value=0.5, step=0.1)

    st.header("4. Degradation Settings")
    target_retention_cycle = st.slider("Retention after Cycle Life (%)", 10.0, 100.0, 80.0) / 100.0
    target_retention_calendar = st.slider("Retention after Calendar Life (%)", 10.0, 100.0, 90.0) / 100.0
    temp_deg_per_degree = st.number_input("Temp Penalty (% per °C > 25°C)", value=2.0, step=0.1) / 100.0

# --- LOAD PROFILE ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Load Schedule")
    load_data = pd.DataFrame([
        {"Name": "Hotel Load", "Power (W)": 50.0, "Start Hour": 0.0, "Duration (h)": 24.0, "Peak Factor": 1.0},
        {"Name": "Main Actuator", "Power (W)": 300.0, "Start Hour": 8.0, "Duration (h)": 2.0, "Peak Factor": 2.5},
    ])
    edited_loads = st.data_editor(load_data, num_rows="dynamic", use_container_width=True)

    # Power vs Time Graph
    time_steps = np.arange(0, 24, 0.25)
    power_timeline = np.zeros(len(time_steps))
    for _, row in edited_loads.iterrows():
        for i, t in enumerate(time_steps):
            if float(row['Start Hour']) <= t < (float(row['Start Hour']) + float(row['Duration (h)'])):
                power_timeline[i] += float(row['Power (W)'])
    
    st.area_chart(pd.DataFrame({"Hour": time_steps, "Power Draw (W)": power_timeline}), x="Hour", y="Power Draw (W)")
    op_temp = st.number_input("Operating Temperature (°C)", value=25.0, step=0.5)

# --- CALCULATOR ENGINE ---
total_wh_discharged = 0.0
max_peak_w = 0.0

for _, row in edited_loads.iterrows():
    total_wh_discharged += (float(row['Power (W)']) * float(row['Duration (h)'])) / eta_dc_dc
    if (float(row['Power (W)']) * float(row['Peak Factor'])) > max_peak_w:
        max_peak_w = float(row['Power (W)']) * float(row['Peak Factor'])

# SOH Logic
temp_penalty = 1.0 - ((op_temp - 25.0) * temp_deg_per_degree) if op_temp > 25.0 else 1.0
total_soh_multiplier = float(temp_penalty * target_retention_cycle * target_retention_calendar)

# Sizing Math
required_usable_wh = total_wh_discharged * (1.0 + safety_buffer)
required_nameplate_wh = required_usable_wh / (max_dod * total_soh_multiplier)
required_ah = required_nameplate_wh / v_batt

# NEW: Refined Charge Time Math
energy_to_replenish_wh = required_usable_wh / eta_charge

# Phase 1: Bulk (Constant Power)
bulk_energy_wh = energy_to_replenish_wh * taper_start_pct
t_bulk = bulk_energy_wh / max_charge_p if max_charge_p > 0 else 0

# Phase 2: Taper (Slowing down)
taper_energy_wh = energy_to_replenish_wh * (1.0 - taper_start_pct)
# We apply the multiplier to the theoretical time for the remaining energy
t_taper = (taper_energy_wh / max_charge_p) * taper_multiplier if max_charge_p > 0 else 0

total_charge_time = t_bulk + t_taper

with col2:
    st.subheader("Sizing Results (BOL)")
    st.metric("Total Capacity (Ah)", f"{required_ah:.2f} Ah")
    st.metric("Total Energy (kWh)", f"{(required_nameplate_wh/1000.0):.3f} kWh")
    
    st.divider()
    st.subheader("Charging Analysis")
    st.metric("Total Charge Time", f"{total_charge_time:.2f} hrs")
    
    c1, c2 = st.columns(2)
    c1.caption(f"Bulk: {t_bulk:.2f}h")
    c2.caption(f"Taper: {t_taper:.2f}h")
    
    actual_charge_c_rate = (max_charge_p / v_batt) / required_ah if required_ah > 0 else 0
    st.write(f"Actual Charge C-Rate: **{actual_charge_c_rate:.3f} C**")
    
    if actual_charge_c_rate > max_charge_c_rate:
        st.error(f"⚠️ Warning: Charge C-rate exceeds limit!")
    else:
        st.success("✅ Charge C-rate safe.")

    st.divider()
    st.write(f"**EOL State of Health:** {total_soh_multiplier*100.0:.1f}%")
    peak_current = max_peak_w / (v_batt * (1.0 - v_cutoff))
    st.write(f"Worst-case Discharge: **{peak_current:.2f} A**")
# --- MODULE SPECIFICATION INPUTS ---
st.header("5. Module Specifications (COTS)")
m_volt = st.number_input("Module Nominal Voltage (V)", value=12.0)
m_cap = st.number_input("Module Capacity (Ah)", value=100.0)
m_cont_i = st.number_input("Module Max Cont. Discharge (A)", value=50.0)
m_peak_i = st.number_input("Module Max Peak Discharge (A)", value=100.0)
m_weight = st.number_input("Module Weight (kg)", value=10.0)

# --- CONFIGURATION ENGINE ---
# 1. Calculate Series
n_series = int(np.ceil(v_batt / m_volt))
achieved_v = n_series * m_volt

# 2. Calculate Parallel (based on Ah)
n_parallel = int(np.ceil(required_ah / m_cap))

# 3. Verify against Peak Current
system_peak_limit = n_parallel * m_peak_i
while system_peak_limit < peak_current:
    n_parallel += 1
    system_peak_limit = n_parallel * m_peak_i

total_modules = n_series * n_parallel
total_pack_weight = total_modules * m_weight

# --- DISPLAY CONFIG ---
st.subheader("Pack Configuration")
col_a, col_b, col_c = st.columns(3)
col_a.metric("Configuration", f"{n_series}S {n_parallel}P")
col_b.metric("Total Modules", f"{total_modules}")
col_c.metric("Pack Weight", f"{total_pack_weight:.1f} kg")

st.write(f"This configuration provides **{achieved_v:.1f}V** nominal.")
