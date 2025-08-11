import pandas as pd
import numpy as np  # ✅ Needed for std dev
import os
import re
from concurrent.futures import ThreadPoolExecutor

# === STEP 0: CONFIGURATION ===
input_folder = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Egaming/Input"
output_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Egaming/Output"
test_case_map_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/code/test case map.xlsx"
mcc_mnc_map_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/code/mncmcc_maping.xlsx"
os.makedirs(output_path, exist_ok=True)


# === STEP 1: Load all raw HTTP files in parallel and extract Country and Type Mobility from filename ===
def load_file(file):
    full_path = os.path.join(input_folder, file)
    try:
        df_part = pd.read_excel(full_path)

        # === STEP 1B: Fill MCC and MNC per file ===
      
        df_part["MCC"] = pd.to_numeric(df_part["MCC"], errors="coerce")
        df_part["MNC"] = pd.to_numeric(df_part["MNC"], errors="coerce")
        first_mcc = df_part["MCC"].dropna().iloc[0] if not df_part["MCC"].dropna().empty else None
        first_mnc = df_part["MNC"].dropna().iloc[0] if not df_part["MNC"].dropna().empty else None
        df_part["MCC"] = df_part["MCC"].fillna(first_mcc)
        df_part["MNC"] = df_part["MNC"].fillna(first_mnc)
        
         # Extract Device
        first_device = df_part["DeviceDescription"].dropna().iloc[0] if not df_part["DeviceDescription"].dropna().empty else None
        df_part["DeviceDescription"] = df_part["DeviceDescription"].fillna(first_device)

    
        # === STEP 1C: Extract Country from filename ===
        base_name = os.path.splitext(file)[0]
        parts = base_name.split("_")
        df_part["Country"] = parts[1] if len(parts) > 1 else "Unknown"
        
        
        df_part["Test Name"] = (
        f"{parts[2][-4:]}_{parts[3]}"
        if len(parts) > 3
        else "Unknown"
        )


        # === STEP 1D: Set Type Mobility based on keyword in filename ===
       
        if 'BMTT' in base_name:
            df_part["Type Mobility"] = 'Test Train'
        elif 'BMWT' in base_name:
            df_part["Type Mobility"] = 'Walk Test'
        elif 'BMDT' in base_name:
            df_part["Type Mobility"] = 'Drive Test'
        else:
            df_part["Type Mobility"] = 'Unknown'

        df_part["__source_file__"] = file
        print(f"✅ Loaded: {file}")
        return df_part

    except Exception as e:
        print(f"⚠️ Failed to read {file}: {e}")
        return None

file_list = [f for f in os.listdir(input_folder) if f.endswith(".xlsx") and "Data_EGaming" in f and "clean" not in f]
with ThreadPoolExecutor(max_workers=4) as executor:
    df_list = list(executor.map(load_file, file_list))
df_list = [df for df in df_list if df is not None]
if not df_list:
    raise ValueError("No EGaming raw files loaded.")
df = pd.concat(df_list, ignore_index=True)


# === STEP 3: Identify segment start and end ===
start_indices = df.index[df['TWAMP Operation Start'].notna()].tolist()
end_indices = df.index[df['TWAMP Operation End'].notna()].tolist()

# === STEP 4: Create Segment Index column ===
df["Test Id"] = None
seg_pointer = 0
for start in start_indices:
    end = next((e for e in end_indices if e > start), None)
    if end is not None:
        df.loc[start:end, "Test Id"] = seg_pointer + 1
        seg_pointer += 1

# === STEP 5: Fill 'Logfile Name' within each segment ===
df["Logfile Name"] = df.groupby("Test Id")["Logfile Name"].ffill().bfill()


mean_cols = [
    "TWAMP_Chunk_Interactivity_Score",
    "TWAMP_Packet_Delay_Variation_Median_ms",
    "TWAMP_Packet_Delay_Variation_Standard_Deviation",
    "TWAMP_Jitter_Median_ms",
    "TWAMP_Jitter_Variance_ms"
    "TWAMP_Chunk_Interactivity_Score",
    "TWAMP_Packet_Delay_Variation_Score",
    "TWAMP_Chunk_Jitter_Average_ms",
    "TWAMP_Chunk_Jitter_Max_ms",
    "TWAMP_Chunk_Jitter_Median_ms",
    "TWAMP_Chunk_Jitter_Min_ms",
    "TWAMP_Chunk_Jitter_Standard_Deviation_ms",
    "TWAMP_Chunk_Jitter_Variance_ms",
    "TWAMP_Jitter_Average_ms",
    "TWAMP_Jitter_Max_ms",
    "TWAMP_Jitter_Median_ms",
    "TWAMP_Jitter_Min_ms",
    "TWAMP_Jitter_Standard_Deviation_ms",
    "TWAMP_Jitter_Variance_ms",
    "TWAMP_Latency_Score",
    "TWAMP_Chunk_Packet_Loss",
    "TWAMP_Packet_Loss",
    "TWAMP_Packet_Loss_Score",
    "TWAMP_Overall_Session_Packet_Loss",
    "TWAMP_Chunk_Rtt_Average_ms",
    "TWAMP_Chunk_Rtt_Max_ms",
    "TWAMP_Chunk_Rtt_Median_ms",
    "TWAMP_Chunk_Rtt_Min_ms",
    "TWAMP_Chunk_Rtt_Standard_Deviation_ms",
    "TWAMP_Chunk_Rtt_Variance_ms",
    "TWAMP_Overall_Session_Rtt_Average_ms",
    "TWAMP_Overall_Session_Rtt_Max_ms",
    "TWAMP_Overall_Session_Rtt_Median_ms",
    "TWAMP_Overall_Session_Rtt_Min_ms",
    "TWAMP_Overall_Session_Rtt_Standard_Deviation_ms",
    "TWAMP_Overall_Session_Rtt_Variance_ms",
    "TWAMP_Rtt_Average_ms",
    "TWAMP_Rtt_Max_ms",
    "TWAMP_Rtt_Median_ms",
    "TWAMP_Rtt_Min_ms",
    "TWAMP_Rtt_Standard_Deviation_ms",
    "TWAMP_Rtt_Variance_ms",
    "LTE Serving Cell Channel RSSI(dBm)",
    "LTE Serving Cell RSRP(dBm)",
    "LTE Serving Cell RS SINR(dB)",
    "LTE Serving Cell RSRQ (dB)",
    "LTE_Serving_Cell_Count_Average",
    "LTE Secondary Serving Cell 1 Channel RSSI (dBm)",
    "LTE Secondary Serving Cell 1 RSRP (dBm)",
    "LTE Secondary Serving Cell 1 RS SINR (dB)",
    "LTE Secondary Serving Cell 1 RSRQ (dB)",
    "LTE Neighbor Cell 1 RSRP",
    "LTE Neighbor Cell 1 RSRQ",
    "LTE Serving Cell DL Pathloss Carrier 1 (dB)",
    "LTE MAC DL Throughput (kbps)",
    "LTE MAC DL Throughput Carrier 1 (kbps)",
    "LTE MAC DL Throughput Carrier 2 (kbps)",
    "LTE MAC DL Throughput Carrier 3 (kbps)",
    "LTE MAC DL Throughput Carrier 4 (kbps)",
    "LTE MAC UL Throughput (kbps)",
    "LTE MAC UL Throughput Carrier 1 (kbps)",
    "LTE MAC UL Throughput Carrier 2 (kbps)",
    "LTE MAC UL Throughput Carrier 3 (kbps)",
    "LTE MAC UL Throughput Carrier 4 (kbps)",
    "LTE PDSCH BLER (%)",
    "LTE PDSCH Phy Throughput (kbps)",
    "LTE PDSCH Phy Throughput Total (kbps)",
    "LTE PDSCH Phy Throughput Carrier 1 (kbps)",
    "LTE PDSCH Phy Throughput Carrier 2 (kbps)",
    "LTE PDSCH Phy Throughput Carrier 3 (kbps)",
    "LTE PDSCH Phy Throughput Carrier 4 (kbps)",
    "PUSCH BLER (%)",
    "LTE PUSCH Phy Throughput (kbps)",
    "LTE PUSCH Phy Throughput Total (kbps)",
    "LTE PUSCH Phy Throughput Carrier 1 (kbps)",
    "LTE PUSCH Phy Throughput Carrier 2 (kbps)",
    "LTE PUSCH Phy Throughput Carrier 3 (kbps)",
    "PUSCH Phy Throughput Carrier 4 (kbps)",
    "LTE RLC Throughput DL (Kbps)",
    "LTE RLC Throughput UL (Kbps)",
    "LTE Bearer Maximum Bitrate DL (kbit/s)",
    "LTE PDN Connection AMBR DL (kbps)",
    "NR Serving Beam 1 NRARFCN DL",
    "NR Serving Beam 1 Bandwidth DL",
    "NR Serving Beam 1 Bandwidth UL",
    "NR Serving Beam 1 GSCN",
    "NR Serving Beam 2 NRARFCN DL",
    "NR Serving Beam 2 Bandwidth DL",
    "NR Serving Beam 2 Bandwidth UL",
    "NR Serving Beam 2 GSCN",
    "NR Serving Cell SS RSSI Top #1",
    "NR Serving Cell SS RSRP Top #1",
    "NR Serving Cell SS SINR Top #1",
    "NR Serving Cell SS RSRQ Top #1",
    "NR Neighbor Cell 1 SS RSRP (dBm)",
    "NR Neighbor Cell 1 SS SINR (dB)",
    "NR Neighbor Cell 1 SS RSRQ (dB)",
    "NR Phy Throughput Multi-RAT DL (kbps)",
    "NR Phy Throughput Multi-RAT UL (kbps)",
    "NR PDSCH Phy Throughput Total (Kbps)",
    "NR Pcell PDSCH Scheduled Throughput (Mbps)",
    "NR PDSCH Phy Throughput Serving Beam 1 (Kbps)",
    "NR PDSCH BLER (%) Serving Beam 1",
    "NR PDSCH CQI Serving Beam 1",
    "NR PDSCH RI Serving Beam 1",
    "NR DL Pathloss Serving Beam 1",
    "NR PDSCH Phy Throughput Serving Beam 2 (Kbps)",
    "NR PDSCH BLER (%) Serving Beam 2",
    "NR PDSCH CQI Serving Beam 2",
    "NR PDSCH RI Serving Beam 2",
    "NR DL Pathloss Serving Beam 2",
    "NR PUSCH Phy Throughput Total (kbps)",
    "NR Pcell PUSCH Scheduled Throughput (Mbps)",
    "NR PUSCH Phy Throughput Serving Beam 1 (Kbps)",
    "NR PUSCH BLER (%) Serving Beam 1",
    "NR PUSCH Phy Throughput Serving Beam 2 (Kbps)",
    "NR PUSCH BLER (%) Serving Beam 2",
    "NR MAC DL Throughput Total (kbps)",
    "NR MAC UL Throughput Total (kbps)",
    "NR RLC DL Throughput Total (kbps)",
    "NR RLC UL Throughput Total (kbps)",
    "NR RLC DL Throughput (Kbps)",
    "NR RLC UL Throughput (Kbps)",
    "NR BWPs Configured Count DL serving Beam 1",
    "NR BWPs Configured Count DL serving Beam 2",
    "NR BWPs Configured Count UL Serving Beam 1",
    "NR BWPs Configured Count UL Serving Beam 2",
    "MR-DC Cell 1 SINR (dB)",
    "PDSCH Average RBs per Allocated Slot Serving Beam 1",
    "PDSCH Average RBs per Allocated Slot per TB Serving Beam 1",
    "PDSCH RB Allocation Count Serving Beam 1",
    "PDSCH RB Allocation Count per TB Serving Beam 1",
    "PDSCH RB Allocation Usage Serving Beam 1 (%)",
    "PDSCH Slot Allocation Count Serving Beam 1",
    "PDSCH Slot Allocation Count per TB Serving Beam 1",
    "PDSCH Slot Allocation TDD Serving Beam 1 (%)",
    "PDSCH Slot Allocation Total Serving Beam 1 (%)",
    "PDSCH Slot Utilization Serving Beam 1 (%)",
    "PDSCH RB Dist Current Count Serving Beam 1",
    "PDSCH RB Utillization Dist Current Count Serving Beam 1",
    "PDSCH Average RBs per Allocated Slot Serving Beam 2",
    "PDSCH Average RBs per Allocated Slot per TB Serving Beam 2",
    "PDSCH RB Allocation Count Serving Beam 2",
    "PDSCH RB Allocation Count per TB Serving Beam 2",
    "PDSCH RB Allocation Usage Serving Beam 2 (%)",
    "PDSCH Slot Allocation Count Serving Beam 2",
    "PDSCH Slot Allocation Count per TB Serving Beam 2",
    "PDSCH Slot Allocation TDD Serving Beam 2 (%)",
    "PDSCH Slot Allocation Total Serving Beam 2 (%)",
    "PDSCH Slot Utilization Serving Beam 2 (%)",
    "PDSCH RB Dist Current Count Serving Beam 2",
    "PDSCH RB Utillization Dist Current Count Serving Beam 2",
    "PUSCH Average RBs per Allocated Slot Serving Beam 1",
    "PUSCH RB Allocation Count Serving Beam 1",
    "PUSCH RB Allocation Usage Serving Beam 1 (%)",
    "PUSCH Slot Allocation Count Serving Beam 1",
    "PUSCH Slot Allocation TDD Serving Beam 1 (%)",
    "PUSCH Slot Allocation Total Serving Beam 1 (%)",
    "PUSCH Slot Utilization Serving Beam 1 (%)",
    "PUSCH RB Dist Current Count Serving Beam 1",
    "PUSCH RB Utillization Dist Current Count Serving Beam 1",
    "PUSCH Average RBs per Allocated Slot Serving Beam 2",
    "PUSCH RB Allocation Count Serving Beam 2",
    "PUSCH RB Allocation Usage Serving Beam 2 (%)",
    "PUSCH Slot Allocation Count Serving Beam 2",
    "PUSCH Slot Allocation TDD Serving Beam 2 (%)",
    "PUSCH Slot Allocation Total Serving Beam 2 (%)",
    "PUSCH Slot Utilization Serving Beam 2 (%)",
    "PUSCH RB Dist Current Count Serving Beam 2",
    "PUSCH RB Utillization Dist Current Count Serving Beam 2",
    "TWAMP_Interactivity_Score",
    "Radio Common Throughput DL (kbps)"


]
for col in mean_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        

        
# Aggregation functions ===
"""
def stdev(x):
    x_clean = x.dropna()
    if len(x_clean) > 1:
        return np.nanstd(x_clean, ddof=1)
    elif len(x_clean) == 1:
        return x_clean.iloc[0]
    else:
        return None
        
        
def variance(x):
    x_clean = x.dropna()
    if len(x_clean) > 1:
        return np.var(x_clean, ddof=1)  # Sample variance
    elif len(x_clean) == 1:
        return x_clean.iloc[0] 
    else:
        return None
"""
def first_val(x): return x.dropna().iloc[0] if not x.dropna().empty else None
def last_val(x): return x.dropna().iloc[-1] if not x.dropna().empty else None
def modus(x): return x.mode().iloc[0] if not x.mode().empty else None


# === STEP 7: Aggregation rules from Table Design ===
agg_rules = {
    "Date Time": first_val,
    "Test Name": first_val,
    "TWAMP Address" : modus,
    "TWAMP Start Time" : modus,
    "TWAMP End Time": modus,    
    "Latitude": first_val,
    "Longitude": first_val,
    "Country": first_val,
    "Type Mobility": first_val,
    "DeviceDescription": first_val,
    "IMEI": first_val,
    "IMSI": first_val,
    "MCC": first_val,
    "MNC": first_val,
    "SIM Operator": first_val,
    "Technology_Detail": modus,
    "Multi RAT Connectivity Mode": modus,
    "RadioAccessTechnologyState": modus,
    "TWAMP Start Sessions": modus,
    "TWAMP Start Sessions Acknowledgement": modus,
    "TWAMP Stop Session": modus,
    "TWAMP Operation Start": modus,
    "TWAMP Operation End": modus,
    "TWAMP Operation Attempt": modus,
    "TWAMP Operation Error": modus,
    "TWAMP Operation Success": modus,
    "TWAMP_Chunk_Interactivity_Score": "mean",
    "TWAMP_Packet_Delay_Variation_Median_ms": "mean",
    "TWAMP_Packet_Delay_Variation_Score": "mean",
    "TWAMP_Packet_Delay_Variation_Standard_Deviation": "mean",
    "TWAMP_Chunk_Jitter_Average_ms": "mean",
    "TWAMP_Chunk_Jitter_Max_ms": "max",
    "TWAMP_Chunk_Jitter_Median_ms": "median",
    "TWAMP_Chunk_Jitter_Min_ms": "min",
    "TWAMP_Chunk_Jitter_Standard_Deviation_ms": "mean",
    "TWAMP_Chunk_Jitter_Variance_ms": "mean",
    "TWAMP_Jitter_Average_ms": "mean",
    "TWAMP_Jitter_Max_ms": "max",
    "TWAMP_Jitter_Median_ms": "median",
    "TWAMP_Jitter_Min_ms": "min",
    "TWAMP_Jitter_Standard_Deviation_ms": "mean",
    "TWAMP_Jitter_Variance_ms": "mean",
    "TWAMP_Latency_Score": "mean",
    "TWAMP_Chunk_Packet_Loss": "sum",
    "TWAMP_Packet_Loss": "sum",
    "TWAMP_Packet_Loss_Score": "mean",
    "TWAMP_Overall_Session_Packet_Loss": "sum",
    "TWAMP_Chunk_Rtt_Average_ms": "mean",
    "TWAMP_Chunk_Rtt_Max_ms": "max",
    "TWAMP_Chunk_Rtt_Median_ms": "median",
    "TWAMP_Chunk_Rtt_Min_ms": "min",
    "TWAMP_Chunk_Rtt_Standard_Deviation_ms": "mean",
    "TWAMP_Chunk_Rtt_Variance_ms": "mean",
    "TWAMP_Overall_Session_Rtt_Average_ms": "mean",
    "TWAMP_Overall_Session_Rtt_Max_ms": "max",
    "TWAMP_Overall_Session_Rtt_Median_ms": "median",
    "TWAMP_Overall_Session_Rtt_Min_ms": "min",
    "TWAMP_Overall_Session_Rtt_Standard_Deviation_ms": "mean",
    "TWAMP_Overall_Session_Rtt_Variance_ms": "mean",
    "TWAMP_Rtt_Average_ms": "mean",
    "TWAMP_Rtt_Max_ms": "max",
    "TWAMP_Rtt_Median_ms": "median",
    "TWAMP_Rtt_Min_ms": "min",
    "TWAMP_Rtt_Standard_Deviation_ms": "mean",
    "TWAMP_Rtt_Variance_ms": "mean",
    "TWAMP_Interactivity_Score": "mean",
    "LTE Cell Identity(eNB Part)": modus,
    "LTE Cell Identity(Cell Part)": modus,
    "LTE Serving Cell Identity": modus,
    "LTE Serving Cell DL EARFCN": modus,
    "LTE Serving Cell Frequency Band": modus,
    "LTE Serving Cell Channel RSSI(dBm)": "mean",
    "LTE Serving Cell RSRP(dBm)": "mean",
    "LTE Serving Cell RS SINR(dB)": "mean",
    "LTE Serving Cell RSRQ (dB)": "mean",
    "LTE_Serving_Cell_Count_Average": "mean",
    "LTE Secondary Serving Cell 1 Identity": modus,
    "LTE Secondary Serving Cell 1 DL EARFCN": modus,
    "LTE Secondary Serving Cell 1 Frequency Band": modus,
    "LTE Secondary Serving Cell 1 Channel RSSI (dBm)": "mean",
    "LTE Secondary Serving Cell 1 RSRP (dBm)": "mean",
    "LTE Secondary Serving Cell 1 RS SINR (dB)": "mean",
    "LTE Secondary Serving Cell 1 RSRQ (dB)": "mean",
    "LTE Neighbor Cell 1 PCI": modus,
    "LTE Neighbor Cell 1 DL EARFCN": modus,
    "LTE Neighbor Cell 1 RSRP": "mean",
    "LTE Neighbor Cell 1 RSRQ": "mean",
    "LTE Serving Cell DL Pathloss Carrier 1 (dB)": "mean",
    "LTE MAC DL Throughput (kbps)": "mean",
    "LTE MAC DL Throughput Carrier 1 (kbps)": "mean",
    "LTE MAC DL Throughput Carrier 2 (kbps)": "mean",
    "LTE MAC DL Throughput Carrier 3 (kbps)": "mean",
    "LTE MAC DL Throughput Carrier 4 (kbps)": "mean",
    "LTE MAC UL Throughput (kbps)": "mean",
    "LTE MAC UL Throughput Carrier 1 (kbps)": "mean",
    "LTE MAC UL Throughput Carrier 2 (kbps)": "mean",
    "LTE MAC UL Throughput Carrier 3 (kbps)": "mean",
    "LTE MAC UL Throughput Carrier 4 (kbps)": "mean",
    "LTE PDSCH Modulation": modus,
    "LTE PDSCH MCS": modus,
    "LTE PDSCH BLER (%)": "mean",
    "LTE PDSCH Phy Throughput (kbps)": "mean",
    "LTE PDSCH Phy Throughput Total (kbps)": "mean",
    "LTE PDSCH Phy Throughput Carrier 1 (kbps)": "mean",
    "LTE PDSCH Phy Throughput Carrier 2 (kbps)": "mean",
    "LTE PDSCH Phy Throughput Carrier 3 (kbps)": "mean",
    "LTE PDSCH Phy Throughput Carrier 4 (kbps)": "mean",
    "LTE PUSCH Modulation ": modus,
    "LTE PUSCH MCS ": modus,
    "PUSCH BLER (%)": "mean",
    "LTE PUSCH Phy Throughput (kbps)": "mean",
    "LTE PUSCH Phy Throughput Total (kbps)": "mean",
    "LTE PUSCH Phy Throughput Carrier 1 (kbps)": "mean",
    "LTE PUSCH Phy Throughput Carrier 2 (kbps)": "mean",
    "LTE PUSCH Phy Throughput Carrier 3 (kbps)": "mean",
    "PUSCH Phy Throughput Carrier 4 (kbps)": "mean",
    "LTE RLC Throughput DL (Kbps)": "mean",
    "LTE RLC Throughput UL (Kbps)": "mean",
    "LTE Bearer Maximum Bitrate DL (kbit/s)": "mean",
    "LTE PDN Connection AMBR DL (kbps)": "mean",
    "NR Serving Beam 1 Cell Identity": modus,
    "NR Serving Beam 1 NRARFCN DL": "mean",
    "NR Serving Beam 1 Band": modus,
    "NR Serving Beam 1 Bandwidth DL": "mean",
    "NR Serving Beam 1 Bandwidth UL": "mean",
    "NR Serving Beam 1 SSB Index": modus,
    "NR Serving Beam 1 Cell Type": modus,
    "NR Serving Beam 1 GSCN": "mean",
    "NR Serving Beam 2 Cell Identity": modus,
    "NR Serving Beam 2 NRARFCN DL": "mean",
    "NR Serving Beam 2 Band": modus,
    "NR Serving Beam 2 Bandwidth DL": "mean",
    "NR Serving Beam 2 Bandwidth UL": "mean",
    "NR Serving Beam 2 SSB Index": modus,
    "NR Serving Beam 2 Cell Type": modus,
    "NR Serving Beam 2 GSCN": "mean",
    "NR Serving Cell Identity Top #1": modus,
    "NR Serving Cell NRARFCN DL Top #1": modus,
    "NR Serving Cell SS RSSI Top #1": "mean",
    "NR Serving Cell SS RSRP Top #1": "mean",
    "NR Serving Cell SS SINR Top #1": "mean",
    "NR Serving Cell SS RSRQ Top #1": "mean",
    "NR PCell SSB Serving Beam Index Top #1": modus,
    "NR Neighbor Cell 1 Cell Identity": modus,
    "NR Neighbor Cell 1 NRARFCN": modus,
    "NR Neighbor Cell 1 SS RSRP (dBm)": "mean",
    "NR Neighbor Cell 1 SS SINR (dB)": "mean",
    "NR Neighbor Cell 1 SS RSRQ (dB)": "mean",
    "NR Neighbor Cell 1 Best Beam Index": modus,
    "NR Neighbor Cell 1 Cell Type": modus,
    "NR Phy Throughput Multi-RAT DL (kbps)": "mean",
    "NR Phy Throughput Multi-RAT UL (kbps)": "mean",
    "NR PDSCH Phy Throughput Total (Kbps)": "mean",
    "NR Pcell PDSCH Scheduled Throughput (Mbps)": "mean",
    "NR PDSCH Phy Throughput Serving Beam 1 (Kbps)": "mean",
    "NR PDSCH Modulation Serving Beam 1": modus,
    "NR PDSCH MCS Serving Beam 1": modus,
    "NR PDSCH BLER (%) Serving Beam 1": "mean",
    "NR PDSCH CQI Serving Beam 1": "mean",
    "NR PDSCH RI Serving Beam 1": "mean",
    "NR DL Pathloss Serving Beam 1": "mean",
    "NR PDSCH Phy Throughput Serving Beam 2 (Kbps)": "mean",
    "NR PDSCH Modulation Serving Beam 2": modus,
    "NR PDSCH MCS Serving Beam 2": modus,
    "NR PDSCH BLER (%) Serving Beam 2": "mean",
    "NR PDSCH CQI Serving Beam 2": "mean",
    "NR PDSCH RI Serving Beam 2": "mean",
    "NR DL Pathloss Serving Beam 2": "mean",
    "NR PUSCH Phy Throughput Total (kbps)": "mean",
    "NR Pcell PUSCH Scheduled Throughput (Mbps)": "mean",
    "NR PUSCH Phy Throughput Serving Beam 1 (Kbps)": "mean",
    "NR PUSCH Modulation Serving Beam 1": modus,
    "NR PUSCH MCS Serving Beam 1": modus,
    "NR PUSCH BLER (%) Serving Beam 1": "mean",
    "NR PUSCH Phy Throughput Serving Beam 2 (Kbps)": "mean",
    "NR PUSCH Modulation Serving Beam 2": modus,
    "NR PUSCH MCS Serving Beam 2": modus,
    "NR PUSCH BLER (%) Serving Beam 2": "mean",
    "NR MAC DL Throughput Total (kbps)": "sum",
    "NR MAC UL Throughput Total (kbps)": "sum",
    "NR RLC DL Throughput Total (kbps)": "sum",
    "NR RLC UL Throughput Total (kbps)": "sum",
    "NR RLC DL Throughput (Kbps)": "sum",
    "NR RLC UL Throughput (Kbps)": "sum",
    "NR BWP Center NR-ARFCN DL Serving Beam 1": modus,
    "NR BWP Bandwidth DL (Mhz) Serving Beam 1": modus,
    "NR BWP ID DL Serving Beam 1": modus,
    "NR BWP Initial Bandwidth DL Serving Beam 1 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 1": modus,
    "NR BWP Start Point NR-ARFCN DL Serving Beam 1": modus,
    "NR BWP Subcarrier Spacing DL Serving Beam 1": modus,
    "NR BWPs Configured Count DL serving Beam 1": "max",
    "NR BWP Center NR-ARFCN DL Serving Beam 2": modus,
    "NR BWP Bandwidth DL (Mhz) Serving Beam 2": modus,
    "NR BWP ID DL Serving Beam 2": modus,
    "NR BWP Initial Bandwidth DL Serving Beam 2 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 2": modus,
    "NR BWP Start Point NR-ARFCN DL Serving Beam 2": modus,
    "NR BWP Subcarrier Spacing DL Serving Beam 2": modus,
    "NR BWPs Configured Count DL serving Beam 2": "max",
    "NR BWP Center NR-ARFCN UL Serving Beam 1": modus,
    "NR BWP Bandwidth UL Serving Beam 1 (Mhz)": modus,
    "NR BWP ID UL Serving Beam 1": modus,
    "NR BWP Initial Bandwidth UL Serving Beam 1 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 1": modus,
    "NR BWP Start Point NR-ARFCN UL Serving Beam 1": modus,
    "NR BWP Subcarrier Spacing UL Serving Beam 1": modus,
    "NR BWPs Configured Count UL Serving Beam 1": "max",
    "NR BWP Center NR-ARFCN UL Serving Beam 2": modus,
    "NR BWP Bandwidth UL Serving Beam 2 (Mhz)": modus,
    "NR BWP ID UL Serving Beam 2": modus,
    "NR BWP Initial Bandwidth UL Serving Beam 2 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 2": modus,
    "NR BWP Start Point NR-ARFCN UL Serving Beam 2": modus,
    "NR BWP Subcarrier Spacing UL Serving Beam 2": modus,
    "NR BWPs Configured Count UL Serving Beam 2": "max",
    "RadioAccessTechnologyState": modus,
    "MR-DC Cell 1 SINR (dB)": "mean",
    "PDSCH Average RBs per Allocated Slot Serving Beam 1": "mean",
    "PDSCH Average RBs per Allocated Slot per TB Serving Beam 1": "mean",
    "PDSCH BWP ID Serving Beam 1": modus,
    "PDSCH RB Allocation Count Serving Beam 1": "sum",
    "PDSCH RB Allocation Count per TB Serving Beam 1": "sum",
    "PDSCH RB Allocation Usage Serving Beam 1 (%)": "mean",
    "PDSCH RBG Size Serving Beam 1": modus,
    "PDSCH Slot Allocation Count Serving Beam 1": "sum",
    "PDSCH Slot Allocation Count per TB Serving Beam 1": "sum",
    "PDSCH Slot Allocation TDD Serving Beam 1 (%)": "mean",
    "PDSCH Slot Allocation Total Serving Beam 1 (%)": "mean",
    "PDSCH Slot Utilization Serving Beam 1 (%)": "mean",
    "PDSCH RB Dist Current Count Serving Beam 1": "sum",
    "PDSCH RB Utillization Dist Current Count Serving Beam 1": "sum",
    "PDSCH Average RBs per Allocated Slot Serving Beam 2": "mean",
    "PDSCH Average RBs per Allocated Slot per TB Serving Beam 2": "mean",
    "PDSCH BWP ID Serving Beam 2": modus,
    "PDSCH RB Allocation Count Serving Beam 2": "sum",
    "PDSCH RB Allocation Count per TB Serving Beam 2": "sum",
    "PDSCH RB Allocation Usage Serving Beam 2 (%)": "mean",
    "PDSCH RBG Size Serving Beam 2": modus,
    "PDSCH Slot Allocation Count Serving Beam 2": "sum",
    "PDSCH Slot Allocation Count per TB Serving Beam 2": "sum",
    "PDSCH Slot Allocation TDD Serving Beam 2 (%)": "mean",
    "PDSCH Slot Allocation Total Serving Beam 2 (%)": "mean",
    "PDSCH Slot Utilization Serving Beam 2 (%)": "mean",
    "PDSCH RB Dist Current Count Serving Beam 2": "sum",
    "PDSCH RB Utillization Dist Current Count Serving Beam 2": "sum",
    "PUSCH Average RBs per Allocated Slot Serving Beam 1": "mean",
    "PUSCH BWP ID Serving Beam 1": modus,
    "PUSCH RB Allocation Count Serving Beam 1": "sum",
    "PUSCH RB Allocation Usage Serving Beam 1 (%)": "mean",
    "PUSCH RBG Size Serving Beam 1": modus,
    "PUSCH Slot Allocation Count Serving Beam 1": "sum",
    "PUSCH Slot Allocation TDD Serving Beam 1 (%)": "mean",
    "PUSCH Slot Allocation Total Serving Beam 1 (%)": "mean",
    "PUSCH Slot Utilization Serving Beam 1 (%)": "mean",
    "PUSCH RB Dist Current Count Serving Beam 1": "sum",
    "PUSCH RB Utillization Dist Current Count Serving Beam 1": "sum",
    "PUSCH Average RBs per Allocated Slot Serving Beam 2": "mean",
    "PUSCH BWP ID Serving Beam 2": modus,
    "PUSCH RB Allocation Count Serving Beam 2": "sum",
    "PUSCH RB Allocation Usage Serving Beam 2 (%)": "mean",
    "PUSCH RBG Size Serving Beam 2": modus,
    "PUSCH Slot Allocation Count Serving Beam 2": "sum",
    "PUSCH Slot Allocation TDD Serving Beam 2 (%)": "mean",
    "PUSCH Slot Allocation Total Serving Beam 2 (%)": "mean",
    "PUSCH Slot Utilization Serving Beam 2 (%)": "mean",
    "PUSCH RB Dist Current Count Serving Beam 2": "sum",
    "PUSCH RB Utillization Dist Current Count Serving Beam 2": "sum",
    "Radio Common Throughput DL (kbps)": "mean",
    "FirmwareVersion": modus
    }

# === Perform aggregation ===
agg_df = df.groupby(['Logfile Name', 'Test Id'], dropna=True).agg(agg_rules).reset_index()

agg_df["end_latitude"] = df.groupby(['Logfile Name', 'Test Id'])['Latitude'].agg(last_val).values
agg_df["end_longitude"] = df.groupby(['Logfile Name', 'Test Id'])['Longitude'].agg(last_val).values


agg_df['Sequence'] = agg_df.apply(
    lambda row: re.search(r"(TRP\d+_\d+)", str(row['Logfile Name'])).group(1)
    if row.get('Country') in ['Austria', 'Bremen'] and re.search(r"(TRP\d+_\d+)", str(row['Logfile Name'])) else None,
    axis=1
)

# === STEP 7: Map MCC/MNC to Operator ===
try:
    mcc_mnc_df = pd.read_excel(mcc_mnc_map_path)
    mcc_mnc_df[['MCC', 'MNC']] = mcc_mnc_df[['MCC', 'MNC']].astype(int)
    agg_df[['MCC', 'MNC']] = agg_df[['MCC', 'MNC']].astype(int)
    agg_df = agg_df.merge(mcc_mnc_df[['MCC', 'MNC', 'Operator']], on=['MCC', 'MNC'], how='left')
    agg_df['Operator'] = agg_df['Operator'].fillna('Unknown')
   
except Exception as e:
    print(f"⚠️ Could not load operator mapping: {e}")

desired_order = [
    "Date Time",
    "Test Id",
    "Test Name",
    "Type Mobility",
    "DeviceDescription",
    "Operator",
    "Country",
    "Sequence",
    "TWAMP Address",
    "TWAMP Start Time",
    "TWAMP End Time",
    "Latitude",
    "end_latitude",
    "Longitude",
    "end_longitude",
    "Logfile Name",
    "EventName",
    "IMEI",
    "IMSI",
    "MCC",
    "MNC",
    "SIM Operator",
    "Technology_Detail",
    "Multi RAT Connectivity Mode",
    "RadioAccessTechnologyState",
    "TWAMP Start Sessions",
    "TWAMP Start Sessions Acknowledgement",
    "TWAMP Stop Session",
    "TWAMP Operation Start",
    "TWAMP Operation End",
    "TWAMP Operation Attempt",
    "TWAMP Operation Error",
    "TWAMP Operation Success",
    "TWAMP_Chunk_Interactivity_Score",
    "TWAMP_Packet_Delay_Variation_Median_ms",
    "TWAMP_Packet_Delay_Variation_Standard_Deviation",
    "TWAMP_Packet_Delay_Variation_Score",
    "TWAMP_Chunk_Jitter_Average_ms",
    "TWAMP_Chunk_Jitter_Max_ms",
    "TWAMP_Chunk_Jitter_Median_ms",
    "TWAMP_Chunk_Jitter_Min_ms",
    "TWAMP_Chunk_Jitter_Standard_Deviation_ms",
    "TWAMP_Chunk_Jitter_Variance_ms",
    "TWAMP_Jitter_Average_ms",
    "TWAMP_Jitter_Max_ms",
    "TWAMP_Jitter_Median_ms",
    "TWAMP_Jitter_Min_ms",
    "TWAMP_Jitter_Standard_Deviation_ms",
    "TWAMP_Jitter_Variance_ms",
    "TWAMP_Latency_Score",
    "TWAMP_Chunk_Packet_Loss",
    "TWAMP_Packet_Loss",
    "TWAMP_Packet_Loss_Score",
    "TWAMP_Overall_Session_Packet_Loss",
    "TWAMP_Chunk_Rtt_Average_ms",
    "TWAMP_Chunk_Rtt_Max_ms",
    "TWAMP_Chunk_Rtt_Median_ms",
    "TWAMP_Chunk_Rtt_Min_ms",
    "TWAMP_Chunk_Rtt_Standard_Deviation_ms",
    "TWAMP_Chunk_Rtt_Variance_ms",
    "TWAMP_Overall_Session_Rtt_Average_ms",
    "TWAMP_Overall_Session_Rtt_Max_ms",
    "TWAMP_Overall_Session_Rtt_Median_ms",
    "TWAMP_Overall_Session_Rtt_Min_ms",
    "TWAMP_Overall_Session_Rtt_Standard_Deviation_ms",
    "TWAMP_Overall_Session_Rtt_Variance_ms",
    "TWAMP_Rtt_Average_ms",
    "TWAMP_Rtt_Max_ms",
    "TWAMP_Rtt_Median_ms",
    "TWAMP_Rtt_Min_ms",
    "TWAMP_Rtt_Standard_Deviation_ms",
    "TWAMP_Rtt_Variance_ms",
    "TWAMP_Interactivity_Score",
    "LTE Cell Identity(eNB Part)",
    "LTE Cell Identity(Cell Part)",
    "LTE Serving Cell Identity",
    "LTE Serving Cell DL EARFCN",
    "LTE Serving Cell Frequency Band",
    "LTE Serving Cell Channel RSSI(dBm)",
    "LTE Serving Cell RSRP(dBm)",
    "LTE Serving Cell RS SINR(dB)",
    "LTE Serving Cell RSRQ (dB)",
    "LTE_Serving_Cell_Count_Average",
    "LTE Secondary Serving Cell 1 Identity",
    "LTE Secondary Serving Cell 1 DL EARFCN",
    "LTE Secondary Serving Cell 1 Frequency Band",
    "LTE Secondary Serving Cell 1 Channel RSSI (dBm)",
    "LTE Secondary Serving Cell 1 RSRP (dBm)",
    "LTE Secondary Serving Cell 1 RS SINR (dB)",
    "LTE Secondary Serving Cell 1 RSRQ (dB)",
    "LTE Neighbor Cell 1 PCI",
    "LTE Neighbor Cell 1 DL EARFCN",
    "LTE Neighbor Cell 1 RSRP",
    "LTE Neighbor Cell 1 RSRQ",
    "LTE Serving Cell DL Pathloss Carrier 1 (dB)",
    "LTE MAC DL Throughput (kbps)",
    "LTE MAC DL Throughput Carrier 1 (kbps)",
    "LTE MAC DL Throughput Carrier 2 (kbps)",
    "LTE MAC DL Throughput Carrier 3 (kbps)",
    "LTE MAC DL Throughput Carrier 4 (kbps)",
    "LTE MAC UL Throughput (kbps)",
    "LTE MAC UL Throughput Carrier 1 (kbps)",
    "LTE MAC UL Throughput Carrier 2 (kbps)",
    "LTE MAC UL Throughput Carrier 3 (kbps)",
    "LTE MAC UL Throughput Carrier 4 (kbps)",
    "LTE PDSCH Modulation",
    "LTE PDSCH MCS",
    "LTE PDSCH BLER (%)",
    "LTE PDSCH Phy Throughput (kbps)",
    "LTE PDSCH Phy Throughput Total (kbps)",
    "LTE PDSCH Phy Throughput Carrier 1 (kbps)",
    "LTE PDSCH Phy Throughput Carrier 2 (kbps)",
    "LTE PDSCH Phy Throughput Carrier 3 (kbps)",
    "LTE PDSCH Phy Throughput Carrier 4 (kbps)",
    "LTE PUSCH Modulation ",
    "LTE PUSCH MCS ",
    "PUSCH BLER (%)",
    "LTE PUSCH Phy Throughput (kbps)",
    "LTE PUSCH Phy Throughput Total (kbps)",
    "LTE PUSCH Phy Throughput Carrier 1 (kbps)",
    "LTE PUSCH Phy Throughput Carrier 2 (kbps)",
    "LTE PUSCH Phy Throughput Carrier 3 (kbps)",
    "PUSCH Phy Throughput Carrier 4 (kbps)",
    "LTE RLC Throughput DL (Kbps)",
    "LTE RLC Throughput UL (Kbps)",
    "LTE Bearer Maximum Bitrate DL (kbit/s)",
    "LTE PDN Connection AMBR DL (kbps)",
    "NR Serving Beam 1 Cell Identity",
    "NR Serving Beam 1 NRARFCN DL",
    "NR Serving Beam 1 Band",
    "NR Serving Beam 1 Bandwidth DL",
    "NR Serving Beam 1 Bandwidth UL",
    "NR Serving Beam 1 SSB Index",
    "NR Serving Beam 1 Cell Type",
    "NR Serving Beam 1 GSCN",
    "NR Serving Beam 2 Cell Identity",
    "NR Serving Beam 2 NRARFCN DL",
    "NR Serving Beam 2 Band",
    "NR Serving Beam 2 Bandwidth DL",
    "NR Serving Beam 2 Bandwidth UL",
    "NR Serving Beam 2 SSB Index",
    "NR Serving Beam 2 Cell Type",
    "NR Serving Beam 2 GSCN",
    "NR Serving Cell Identity Top #1",
    "NR Serving Cell NRARFCN DL Top #1",
    "NR Serving Cell SS RSSI Top #1",
    "NR Serving Cell SS RSRP Top #1",
    "NR Serving Cell SS SINR Top #1",
    "NR Serving Cell SS RSRQ Top #1",
    "NR PCell SSB Serving Beam Index Top #1",
    "NR Neighbor Cell 1 Cell Identity",
    "NR Neighbor Cell 1 NRARFCN",
    "NR Neighbor Cell 1 SS RSRP (dBm)",
    "NR Neighbor Cell 1 SS SINR (dB)",
    "NR Neighbor Cell 1 SS RSRQ (dB)",
    "NR Neighbor Cell 1 Best Beam Index",
    "NR Neighbor Cell 1 Cell Type",
    "NR Phy Throughput Multi-RAT DL (kbps)",
    "NR Phy Throughput Multi-RAT UL (kbps)",
    "NR PDSCH Phy Throughput Total (Kbps)",
    "NR Pcell PDSCH Scheduled Throughput (Mbps)",
    "NR PDSCH Phy Throughput Serving Beam 1 (Kbps)",
    "NR PDSCH Modulation Serving Beam 1",
    "NR PDSCH MCS Serving Beam 1",
    "NR PDSCH BLER (%) Serving Beam 1",
    "NR PDSCH CQI Serving Beam 1",
    "NR PDSCH RI Serving Beam 1",
    "NR DL Pathloss Serving Beam 1",
    "NR PDSCH Phy Throughput Serving Beam 2 (Kbps)",
    "NR PDSCH Modulation Serving Beam 2",
    "NR PDSCH MCS Serving Beam 2",
    "NR PDSCH BLER (%) Serving Beam 2",
    "NR PDSCH CQI Serving Beam 2",
    "NR PDSCH RI Serving Beam 2",
    "NR DL Pathloss Serving Beam 2",
    "NR PUSCH Phy Throughput Total (kbps)",
    "NR Pcell PUSCH Scheduled Throughput (Mbps)",
    "NR PUSCH Phy Throughput Serving Beam 1 (Kbps)",
    "NR PUSCH Modulation Serving Beam 1",
    "NR PUSCH MCS Serving Beam 1",
    "NR PUSCH BLER (%) Serving Beam 1",
    "NR PUSCH Phy Throughput Serving Beam 2 (Kbps)",
    "NR PUSCH Modulation Serving Beam 2",
    "NR PUSCH MCS Serving Beam 2",
    "NR PUSCH BLER (%) Serving Beam 2",
    "NR MAC DL Throughput Total (kbps)",
    "NR MAC UL Throughput Total (kbps)",
    "NR RLC DL Throughput Total (kbps)",
    "NR RLC UL Throughput Total (kbps)",
    "NR RLC DL Throughput (Kbps)",
    "NR RLC UL Throughput (Kbps)",
    "NR BWP Center NR-ARFCN DL Serving Beam 1",
    "NR BWP Bandwidth DL (Mhz) Serving Beam 1",
    "NR BWP ID DL Serving Beam 1",
    "NR BWP Initial Bandwidth DL Serving Beam 1 (MHz)",
    "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 1",
    "NR BWP Start Point NR-ARFCN DL Serving Beam 1",
    "NR BWP Subcarrier Spacing DL Serving Beam 1",
    "NR BWPs Configured Count DL serving Beam 1",
    "NR BWP Center NR-ARFCN DL Serving Beam 2",
    "NR BWP Bandwidth DL (Mhz) Serving Beam 2",
    "NR BWP ID DL Serving Beam 2",
    "NR BWP Initial Bandwidth DL Serving Beam 2 (MHz)",
    "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 2",
    "NR BWP Start Point NR-ARFCN DL Serving Beam 2",
    "NR BWP Subcarrier Spacing DL Serving Beam 2",
    "NR BWPs Configured Count DL serving Beam 2",
    "NR BWP Center NR-ARFCN UL Serving Beam 1",
    "NR BWP Bandwidth UL Serving Beam 1 (Mhz)",
    "NR BWP ID UL Serving Beam 1",
    "NR BWP Initial Bandwidth UL Serving Beam 1 (MHz)",
    "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 1",
    "NR BWP Start Point NR-ARFCN UL Serving Beam 1",
    "NR BWP Subcarrier Spacing UL Serving Beam 1",
    "NR BWPs Configured Count UL Serving Beam 1",
    "NR BWP Center NR-ARFCN UL Serving Beam 2",
    "NR BWP Bandwidth UL Serving Beam 2 (Mhz)",
    "NR BWP ID UL Serving Beam 2",
    "NR BWP Initial Bandwidth UL Serving Beam 2 (MHz)",
    "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 2",
    "NR BWP Start Point NR-ARFCN UL Serving Beam 2",
    "NR BWP Subcarrier Spacing UL Serving Beam 2",
    "NR BWPs Configured Count UL Serving Beam 2",
    "RadioAccessTechnologyState",
    "MR-DC Cell 1 SINR (dB)",
    "PDSCH Average RBs per Allocated Slot Serving Beam 1",
    "PDSCH Average RBs per Allocated Slot per TB Serving Beam 1",
    "PDSCH BWP ID Serving Beam 1",
    "PDSCH RB Allocation Count Serving Beam 1",
    "PDSCH RB Allocation Count per TB Serving Beam 1",
    "PDSCH RB Allocation Usage Serving Beam 1 (%)",
    "PDSCH RBG Size Serving Beam 1",
    "PDSCH Slot Allocation Count Serving Beam 1",
    "PDSCH Slot Allocation Count per TB Serving Beam 1",
    "PDSCH Slot Allocation TDD Serving Beam 1 (%)",
    "PDSCH Slot Allocation Total Serving Beam 1 (%)",
    "PDSCH Slot Utilization Serving Beam 1 (%)",
    "PDSCH RB Dist Current Count Serving Beam 1",
    "PDSCH RB Utillization Dist Current Count Serving Beam 1",
    "PDSCH Average RBs per Allocated Slot Serving Beam 2",
    "PDSCH Average RBs per Allocated Slot per TB Serving Beam 2",
    "PDSCH BWP ID Serving Beam 2",
    "PDSCH RB Allocation Count Serving Beam 2",
    "PDSCH RB Allocation Count per TB Serving Beam 2",
    "PDSCH RB Allocation Usage Serving Beam 2 (%)",
    "PDSCH RBG Size Serving Beam 2",
    "PDSCH Slot Allocation Count Serving Beam 2",
    "PDSCH Slot Allocation Count per TB Serving Beam 2",
    "PDSCH Slot Allocation TDD Serving Beam 2 (%)",
    "PDSCH Slot Allocation Total Serving Beam 2 (%)",
    "PDSCH Slot Utilization Serving Beam 2 (%)",
    "PDSCH RB Dist Current Count Serving Beam 2",
    "PDSCH RB Utillization Dist Current Count Serving Beam 2",
    "PUSCH Average RBs per Allocated Slot Serving Beam 1",
    "PUSCH BWP ID Serving Beam 1",
    "PUSCH RB Allocation Count Serving Beam 1",
    "PUSCH RB Allocation Usage Serving Beam 1 (%)",
    "PUSCH RBG Size Serving Beam 1",
    "PUSCH Slot Allocation Count Serving Beam 1",
    "PUSCH Slot Allocation TDD Serving Beam 1 (%)",
    "PUSCH Slot Allocation Total Serving Beam 1 (%)",
    "PUSCH Slot Utilization Serving Beam 1 (%)",
    "PUSCH RB Dist Current Count Serving Beam 1",
    "PUSCH RB Utillization Dist Current Count Serving Beam 1",
    "PUSCH Average RBs per Allocated Slot Serving Beam 2",
    "PUSCH BWP ID Serving Beam 2",
    "PUSCH RB Allocation Count Serving Beam 2",
    "PUSCH RB Allocation Usage Serving Beam 2 (%)",
    "PUSCH RBG Size Serving Beam 2",
    "PUSCH Slot Allocation Count Serving Beam 2",
    "PUSCH Slot Allocation TDD Serving Beam 2 (%)",
    "PUSCH Slot Allocation Total Serving Beam 2 (%)",
    "PUSCH Slot Utilization Serving Beam 2 (%)",
    "PUSCH RB Dist Current Count Serving Beam 2",
    "PUSCH RB Utillization Dist Current Count Serving Beam 2",
    "Radio Common Throughput DL (kbps)",
    "FirmwareVersion"



]


# === STEP 13: Only reorder if all columns are present ===
agg_df = agg_df[[col for col in desired_order if col in agg_df.columns]]




agg_df = agg_df.sort_values(by=['Test Id', 'Date Time'])



def check_qualifier(row):
    TWAMPOpSucces = row.get("TWAMP Operation Succes") or 0
    TWAMP_Rtt_Min = row.get("TWAMP_Rtt_Min_ms") or 0
    if TWAMPOpSucces == "TWAMP Operation SuccessL" and TWAMP_Rtt_Min < 100 :
        return "Not Qualified"
    return "Qualified"

agg_df['Qualifier'] = agg_df.apply(check_qualifier, axis=1)


# === STEP 14: Export each Country to a separate Excel file in parallel ===
def export_country(country_group):
    country, group_df = country_group
    country_name = country.replace("/", "-").replace(" ", "_")
    output_file = os.path.join(output_path, f"Data_EGaming_{country_name}_clean.xlsx")
    group_df.to_excel(output_file, index=False)
    print(f"✅ Saved: {output_file}")



# ✅ Check Country column exists before grouping
if 'Country' not in agg_df.columns:
    raise ValueError("❌ 'Country' column is missing before exporting.")
    
with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(export_country, agg_df.groupby('Country'))