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
    if st.button("Save Current Scenario"):
        # This will be populated by the inputs below
        st.session_state.scenarios[scenario_name] = "Saved" 
        st.success(f"Scenario '{scenario_name}' saved!")

    st.divider()
    
    # 1. System Voltages
    st.subheader("Electrical Architecture")
    v_batt = st.number_input("Battery Module Voltage (V)", value=48.0)
    v_payload = st.number_input("Payload Voltage (V)", value=12.0)
    v_cutoff = st.slider("Voltage Cut-off (%)", 0, 20, 10) / 100
    
    # 2. Efficiencies
    st.subheader("Efficiencies (%)")
    eta_dc_dc = st.slider("DC-DC Converter Efficiency", 80, 99, 95) / 100
    eta_dc_ac = st.slider("DC-AC Inverter Efficiency", 80, 99, 90) / 100
    eta_batt = st.slider("Battery Round-trip Efficiency", 80, 99, 98) / 100

# --- MAIN INTERFACE ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Load Profile")
    # Using an interactive table for load management
    load_data = pd.DataFrame(
        [
            {"Name": "Hotel Load", "Power (W)": 50, "Hours": 24, "Peak Factor": 1.0},
            {"Name": "Main Actuator", "Power (W)": 500, "Hours": 2, "Peak Factor": 3.0},
        ]
    )
    edited_loads = st.data_editor(load_data, num_rows="dynamic", use_container_width=True)

    st.subheader("Life & Environment")
    c3, c4, c5 = st.columns(3)
    with c3:
        temp = st.number_input("Op. Temperature (°C)", value=25)
        temp_penalty = 1.0 if temp <= 25 else 1.0 - ((temp - 25) * 0.02) # Generic 2% drop per degree > 25C
    with c4:
        cycles = st.number_input("Target Cycle Life", value=2000)
        cycle_deg = 0.8 # Assume 20% loss at end of cycles
    with c5:
        calendar_years = st.number_input("Calendar Life (Years)", value=10)
        cal_deg = 0.9 # Assume 10% loss over time

# --- LOGIC ENGINE ---
# Total Daily Energy Required (Wh)
total_wh = 0
max_peak_w = 0

for index, row in edited_loads.iterrows():
    # Basic Energy Calc: (Power * Time) / Efficiency
    # We assume DC-DC for simplicity, you can add a toggle per load for AC/DC
    energy = (row['Power (W)'] * row['Hours']) / eta_dc_dc
    total_wh += energy
    
    # Peak Power Calculation
    peak = row['Power (W)'] * row['Peak Factor']
    if peak > max_peak_w:
        max_peak_w = peak

# Safety Buffer & DoD
safety_buffer = st.sidebar.slider("Safety Buffer (%)", 0, 50, 10) / 100
max_dod = st.sidebar.slider("Max Depth of Discharge (%)", 10, 100, 80) / 100

# Final Calculations
# Total Degradation Factor (Compound)
total_deg_factor = temp_penalty * cycle_deg * cal_deg

# Required Usable Energy (EOL)
required_usable_wh = total_wh * (1 + safety_buffer)

# Required Nameplate Energy (BOL)
# Formula: E_req / (DoD * Degradation)
required_nameplate_wh = required_usable_wh / (max_dod * total_deg_factor)
required_ah = required_nameplate_wh / v_batt

with col2:
    st.subheader("Results (BOL)")
    st.metric("Total Required Capacity (Ah)", f"{required_ah:.2f} Ah")
    st.metric("Total Energy (kWh)", f"{(required_nameplate_wh/1000):.2f} kWh")
    
    st.divider()
    st.write("**Peak Demand Check**")
    peak_current = max_peak_w / (v_batt * (1-v_cutoff))
    st.write(f"Max Peak Current: **{peak_current:.2f} A**")
    
    c_rating_req = peak_current / required_ah
    st.write(f"Min. Discharge C-Rating: **{c_rating_req:.2f}C**")

st.info("💡 **Agnostic Assumption:** Calculations assume a linear degradation profile. Results represent 'Beginning of Life' (BOL) capacity required to satisfy 'End of Life' (EOL) requirements.")