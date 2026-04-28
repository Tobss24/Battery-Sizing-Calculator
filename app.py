import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Battery Sizer Pro", layout="wide")
st.title("🔋 Professional Battery Capacity Sizing Tool")

with st.sidebar:
    st.header("1. System Architecture")
    # Setting 'value' as float (48.0) and 'step' to 0.1 enables float input
    v_batt = st.number_input("Battery Module Voltage (V)", value=48.0, step=0.1, format="%.2f")
    v_cutoff = st.slider("Voltage Cut-off (%)", 0.0, 20.0, 10.0) / 100.0
    
    st.header("2. Efficiency & Safety")
    eta_dc_dc = st.slider("DC-DC Efficiency (%)", 70.0, 100.0, 95.0) / 100.0
    safety_buffer = st.slider("Safety Buffer (%)", 0.0, 100.0, 10.0) / 100.0
    max_dod = st.slider("Max Depth of Discharge (%)", 10.0, 100.0, 80.0) / 100.0

    st.header("3. Degradation Settings")
    target_retention_cycle = st.slider("Retention after Cycle Life (%)", 10.0, 100.0, 80.0) / 100.0
    target_retention_calendar = st.slider("Retention after Calendar Life (%)", 10.0, 100.0, 90.0) / 100.0
    temp_deg_per_degree = st.number_input("Temp Penalty (% per °C > 25°C)", value=2.0, step=0.1) / 100.0

# --- LOAD PROFILE ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Load Schedule")
    # Using floats in the initial dictionary forces the editor to accept decimals
    load_data = pd.DataFrame([
        {"Name": "Hotel Load", "Power (W)": 50.5, "Start Hour": 0.0, "Duration (h)": 24.0, "Peak Factor": 1.0},
        {"Name": "Main Actuator", "Power (W)": 300.75, "Start Hour": 8.5, "Duration (h)": 2.25, "Peak Factor": 2.5},
    ])
    
    # Configure columns to ensure float precision
    edited_loads = st.data_editor(
        load_data, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Power (W)": st.column_config.NumberColumn(format="%.2f"),
            "Start Hour": st.column_config.NumberColumn(min_value=0, max_value=24, format="%.2f"),
            "Duration (h)": st.column_config.NumberColumn(format="%.2f"),
            "Peak Factor": st.column_config.NumberColumn(format="%.2f"),
        }
    )

    # Graphing logic with high-resolution time steps
    time_steps = np.arange(0, 24, 0.25) # 15-minute intervals
    power_timeline = np.zeros(len(time_steps))
    for _, row in edited_loads.iterrows():
        for i, t in enumerate(time_steps):
            if float(row['Start Hour']) <= t < (float(row['Start Hour']) + float(row['Duration (h)'])):
                power_timeline[i] += float(row['Power (W)'])
    
    st.area_chart(pd.DataFrame({"Hour": time_steps, "Power Draw (W)": power_timeline}), x="Hour", y="Power Draw (W)")

    st.subheader("Environmental Factors")
    op_temp = st.number_input("Operating Temperature (°C)", value=25.0, step=0.5)

# --- THE CALCULATOR ENGINE ---
total_wh_needed = 0.0
max_peak_w = 0.0

for _, row in edited_loads.iterrows():
    # Calculation using float cast to be safe
    p = float(row['Power (W)'])
    d = float(row['Duration (h)'])
    pf = float(row['Peak Factor'])
    
    total_wh_needed += (p * d) / eta_dc_dc
    if (p * pf) > max_peak_w:
        max_peak_w = p * pf

# Temperature Penalty: only applies if temp > 25C
temp_penalty = 1.0
if op_temp > 25.0:
    temp_penalty = 1.0 - ((op_temp - 25.0) * temp_deg_per_degree)

# Compound SOH
total_soh_multiplier = float(temp_penalty * target_retention_cycle * target_retention_calendar)

# Sizing Math
required_usable_wh = total_wh_needed * (1.0 + safety_buffer)
required_nameplate_wh = required_usable_wh / (max_dod * total_soh_multiplier)
required_ah = required_nameplate_wh / v_batt

with col2:
    st.subheader("Sizing Results (BOL)")
    st.metric("Total Capacity (Ah)", f"{required_ah:.3f} Ah")
    st.metric("Total Energy (kWh)", f"{(required_nameplate_wh/1000.0):.4f} kWh")
    
    st.divider()
    st.write(f"**Calculated EOL State of Health:** {total_soh_multiplier*100.0:.2f}%")
    
    st.divider()
    # Physics check: Low voltage = High current
    peak_current = max_peak_w / (v_batt * (1.0 - v_cutoff))
    st.write(f"Worst-case Peak: **{peak_current:.2f} A**")
    
    c_rating_req = peak_current / required_ah if required_ah > 0 else 0
    st.write(f"Min. Discharge C-Rating: **{c_rating_req:.2f}C**")
