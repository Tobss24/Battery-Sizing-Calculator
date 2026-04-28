import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Battery Sizer Pro", layout="wide")
st.title("🔋 Professional Battery Capacity Sizing Tool")

# --- SCENARIO MANAGER ---
if 'scenarios' not in st.session_state:
    st.session_state.scenarios = {}

with st.sidebar:
    st.header("Settings & Scenarios")
    scenario_name = st.text_input("Scenario Name", value="Baseline")
    
    # 1. System Voltages
    st.subheader("Electrical Architecture")
    v_batt = st.number_input("Battery Module Voltage (V)", value=48.0)
    v_payload = st.number_input("Payload Voltage (V)", value=12.0)
    v_cutoff = st.slider("Voltage Cut-off (%)", 0, 20, 10) / 100
    
    # 2. Efficiencies
    st.subheader("Efficiencies (%)")
    eta_dc_dc = st.slider("DC-DC Converter Efficiency", 80, 99, 95) / 100
    eta_dc_ac = st.slider("DC-AC Inverter Efficiency", 80, 99, 90) / 100
    
    # 3. Safety & DoD
    st.subheader("System Limits")
    safety_buffer = st.slider("Safety Buffer (%)", 0, 50, 10) / 100
    max_dod = st.slider("Max Depth of Discharge (%)", 10, 100, 80) / 100

# --- MAIN INTERFACE ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Load Profile & Schedule")
    # Added "Start Hour" to enable the Power vs Time graph
    load_data = pd.DataFrame(
        [
            {"Name": "Hotel Load", "Power (W)": 50, "Start Hour": 0, "Duration (h)": 24, "Peak Factor": 1.0},
            {"Name": "Main Actuator", "Power (W)": 300, "Start Hour": 8, "Duration (h)": 2, "Peak Factor": 2.0},
            {"Name": "Lighting", "Power (W)": 100, "Start Hour": 18, "Duration (h)": 6, "Peak Factor": 1.1},
        ]
    )
    edited_loads = st.data_editor(load_data, num_rows="dynamic", use_container_width=True)

    # --- GRAPHING LOGIC ---
    st.subheader("Power vs. Time (24h Profile)")
    
    # Create a 24-hour timeline (0 to 23)
    time_steps = np.arange(0, 24, 0.5) # 30-minute increments for smoothness
    power_timeline = np.zeros(len(time_steps))

    for _, row in edited_loads.iterrows():
        p = row['Power (W)']
        start = row['Start Hour']
        dur = row['Duration (h)']
        
        # Fill the timeline where the load is active
        for i, t in enumerate(time_steps):
            if start <= t < (start + dur):
                power_timeline[i] += p

    chart_data = pd.DataFrame({"Hour": time_steps, "Power Draw (W)": power_timeline})
    st.area_chart(chart_data, x="Hour", y="Power Draw (W)")

    st.subheader("Life & Environment")
    c3, c4, c5 = st.columns(3)
    with c3:
        temp = st.number_input("Op. Temperature (°C)", value=25)
        temp_penalty = 1.0 if temp <= 25 else 1.0 - ((temp - 25) * 0.02)
    with c4:
        cycles = st.number_input("Target Cycle Life", value=2000)
        cycle_deg = 0.8 
    with c5:
        calendar_years = st.number_input("Calendar Life (Years)", value=10)
        cal_deg = 0.9 

# --- LOGIC ENGINE ---
total_wh = 0
max_peak_w = 0

for _, row in edited_loads.iterrows():
    # Efficiency applied here
    energy = (row['Power (W)'] * row['Duration (h)']) / eta_dc_dc
    total_wh += energy
    
    # Peak check
    peak = row['Power (W)'] * row['Peak Factor']
    if peak > max_peak_w:
        max_peak_w = peak

total_deg_factor = temp_penalty * cycle_deg * cal_deg
required_usable_wh = total_wh * (1 + safety_buffer)
required_nameplate_wh = required_usable_wh / (max_dod * total_deg_factor)
required_ah = required_nameplate_wh / v_batt

with col2:
    st.subheader("Results (BOL)")
    st.metric("Total Required Capacity", f"{required_ah:.2f} Ah")
    st.metric("Total Energy (Wh)", f"{int(required_nameplate_wh)} Wh")
    
    st.divider()
    st.write("**Peak Demand Check**")
    peak_current = max_peak_w / (v_batt * (1-v_cutoff))
    st.write(f"Worst-case Peak Current: **{peak_current:.2f} A**")
    
    c_rating_req = peak_current / required_ah
    st.write(f"Min. Discharge C-Rating: **{c_rating_req:.2f}C**")

st.info("💡 **Graph Tip:** Overlapping 'Start Hours' will stack the power draw. Use this to identify if your battery can handle simultaneous high-power events.")
