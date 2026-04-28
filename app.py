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

    # Power vs Time Graph
    time_steps = np.arange(0, 24, 0.25)
    power_timeline = np.zeros(len(time_steps))
    for _, row in edited_loads.iterrows():
        try:
            for i, t in enumerate(time_steps):
                if float(row['Start Hour']) <= t < (float(row['Start Hour']) + float(row['Duration (h)'])):
                    power_timeline[i] += float(row['Power (W)'])
        except: continue
    
    st.area_chart(pd.DataFrame({"Hour": time_steps, "Power Draw (W)": power_timeline}), x="Hour", y="Power Draw (W)")

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
        m_weight = st.number_input("Module Weight (kg)", value=150.0, step=0.1)

# --- THE CALCULATOR ENGINE ---
# Protection against zero-division
if v_batt_target > 0 and m_volt > 0 and m_cap > 0:
    total_wh_discharged = 0.0
    max_peak_power_w = 0.0

    for _, row in edited_loads.iterrows():
        try:
            p = float(row['Power (W)'])
            d = float(row['Duration (h)'])
            pf = float(row['Peak Factor'])
            total_wh_discharged += (p * d) / eta_disch
            if (p * pf) > max_peak_power_w:
                max_peak_power_w = p * pf
        except: continue

    # SOH Calculation
    temp_penalty = 1.0 - ((op_temp - 25.0) * temp_penalty_rate) if op_temp > 25.0 else 1.0
    total_soh = max(0.01, float(temp_penalty * ret_cycle * ret_cal))

    # System Capacity Needs
    req_usable_wh = total_wh_discharged * (1.0 + safety_buffer)
    req_nameplate_wh = req_usable_wh / (max(0.1, max_dod) * total_soh)
    req_ah = req_nameplate_wh / v_batt_target

    # Hardware Configuration
    n_s = int(np.ceil(v_batt_target / m_volt))
    peak_current_system = max_peak_power_w / (v_batt_target * (1.0 - v_cutoff_pct))

    # Parallel Strings (3-Way Constraint)
    n_p_cap = int(np.ceil(req_ah / m_cap))
    n_p_cont = int(np.ceil((max_peak_power_w / v_batt_target) / m_cont_i)) if m_cont_i > 0 else 1
    n_p_peak = int(np.ceil(peak_current_system / m_peak_i)) if m_peak_i > 0 else 1

    n_p = max(n_p_cap, n_p_cont, n_p_peak)
    total_modules = n_s * n_p

    # Charge Time
    energy_replenish_wh = req_usable_wh / eta_charge
    t_bulk = (energy_replenish_wh * taper_start_pct) / max_charge_p if max_charge_p > 0 else 0
    t_taper = ((energy_replenish_wh * (1.0 - taper_start_pct)) / max_charge_p) * taper_multiplier if max_charge_p > 0 else 0
    total_t_charge = t_bulk + t_taper

    # --- RESULTS DISPLAY ---
    with col2:
        st.subheader("System Results (BOL)")
        st.metric("Total Capacity (Ah)", f"{req_ah:.2f} Ah")
        st.metric("Total Energy (kWh)", f"{(req_nameplate_wh/1000.0):.2f} kWh")
        
        st.divider()
        st.subheader("Hardware Configuration")
        st.metric("Pack Layout", f"{n_s}S {n_p}P")
        st.write(f"Total Modules: **{total_modules}**")
        st.write(f"Total Weight: **{total_modules * m_weight:.1f} kg**")
        st.write(f"Actual Voltage: **{n_s * m_volt:.1f} V**")
        
        st.divider()
        st.subheader("Performance & Safety")
        st.write(f"Worst-case Peak: **{peak_current_system:.2f} A**")
        st.write(f"EOL State of Health: **{total_soh*100.0:.1f}%**")
        
        st.divider()
        st.subheader("Charging")
        st.metric("Total Time", f"{total_t_charge:.2f} hrs")
        charge_c = (max_charge_p / (n_s * m_volt)) / (n_p * m_cap)
        st.write(f"Charge C-Rate: **{charge_c:.3f} C**")
        if charge_c > max_charge_c_limit:
            st.error("⚠️ Over Charge Limit!")
        else:
            st.success("✅ Charge Rate Safe")
else:
    with col2:
        st.warning("Please ensure System Voltage and Module specs are greater than 0.")
