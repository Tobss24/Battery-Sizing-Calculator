import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Battery Capacity Pro", layout="wide")
st.title("🔋Battery Capacity Calculator")

with st.sidebar:
    st.header("1. System Architecture")
    v_batt = st.number_input("Battery Module Voltage (V)", value=48.0)
    v_cutoff = st.slider("Voltage Cut-off (%)", 0, 20, 10) / 100
    
    st.header("2. Efficiency & Safety")
    eta_dc_dc = st.slider("DC-DC Efficiency (%)", 80, 99, 95) / 100
    safety_buffer = st.slider("Safety Buffer (%)", 0, 50, 10) / 100
    max_dod = st.slider("Max Depth of Discharge (%)", 10, 100, 80) / 100

    st.header("3. Degradation Settings")
    # NEW: These now directly impact the math
    target_retention_cycle = st.slider("Retention after Cycle Life (%)", 50, 100, 80) / 100
    target_retention_calendar = st.slider("Retention after Calendar Life (%)", 50, 100, 90) / 100
    temp_deg_per_degree = st.slider("Temp Penalty (% per °C > 25°C)", 0.0, 5.0, 2.0) / 100

# --- LOAD PROFILE ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Load Schedule")
    load_data = pd.DataFrame([
        {"Name": "Hotel Load", "Power (W)": 50, "Start Hour": 0, "Duration (h)": 24, "Peak Factor": 1.0},
        {"Name": "Main Actuator", "Power (W)": 300, "Start Hour": 8, "Duration (h)": 2, "Peak Factor": 2.5},
    ])
    edited_loads = st.data_editor(load_data, num_rows="dynamic", use_container_width=True)

    # Graphing
    time_steps = np.arange(0, 24, 0.5)
    power_timeline = np.zeros(len(time_steps))
    for _, row in edited_loads.iterrows():
        for i, t in enumerate(time_steps):
            if row['Start Hour'] <= t < (row['Start Hour'] + row['Duration (h)']):
                power_timeline[i] += row['Power (W)']
    
    st.area_chart(pd.DataFrame({"Hour": time_steps, "Power Draw (W)": power_timeline}), x="Hour", y="Power Draw (W)")

    st.subheader("Environmental Factors")
    op_temp = st.number_input("Operating Temperature (°C)", value=25)

# --- THE CALCULATOR ENGINE ---
# 1. Total Energy Required (Wh)
total_wh_needed = 0
max_peak_w = 0
for _, row in edited_loads.iterrows():
    total_wh_needed += (row['Power (W)'] * row['Duration (h)']) / eta_dc_dc
    if (row['Power (W)'] * row['Peak Factor']) > max_peak_w:
        max_peak_w = row['Power (W)'] * row['Peak Factor']

# 2. Compound Degradation Logic
# Temperature Penalty: only applies if temp > 25C
temp_penalty = 1.0
if op_temp > 25:
    temp_penalty = 1.0 - ((op_temp - 25) * temp_deg_per_degree)

# Total Health Multiplier (SOH at End of Life)
total_soh_multiplier = temp_penalty * target_retention_cycle * target_retention_calendar

# 3. Final Sizing
# We divide by SOH because as SOH drops, we need a bigger BOL battery to meet the same EOL need.
required_usable_wh = total_wh_needed * (1 + safety_buffer)
required_nameplate_wh = required_usable_wh / (max_dod * total_soh_multiplier)
required_ah = required_nameplate_wh / v_batt

with col2:
    st.subheader("Sizing Results (BOL)")
    st.metric("Total Capacity (Ah)", f"{required_ah:.2f} Ah")
    st.metric("Total Energy (kWh)", f"{(required_nameplate_wh/1000):.2f} kWh")
    
    st.divider()
    st.write(f"**Calculated EOL State of Health:** {total_soh_multiplier*100:.1f}%")
    st.caption("This is the 'remaining' capacity factor after temp, cycles, and years.")
    
    st.divider()
    peak_current = max_peak_w / (v_batt * (1 - v_cutoff))
    st.write(f"Worst-case Peak: **{peak_current:.2f} A**")
