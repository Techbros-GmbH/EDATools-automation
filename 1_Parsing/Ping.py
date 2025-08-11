import pandas as pd
import os
import re
from concurrent.futures import ThreadPoolExecutor

# === STEP 0: CONFIGURATION ===
input_folder = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Ping/Input"
output_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Ping/Output"
test_case_map_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/code/test case map.xlsx"
mcc_mnc_map_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/code/mncmcc_maping.xlsx"
os.makedirs(output_path, exist_ok=True)


# === STEP 1: Load all raw Ping files in parallel and extract Country and Type Mobility from filename ===
def load_file(file):
    full_path = os.path.join(input_folder, file)
    try:
        df_part = pd.read_excel(full_path)

        df_part["IMSI"] = pd.to_numeric(df_part["IMSI"], errors="coerce")
        first_imsi = df_part["IMSI"].dropna().iloc[0] if not df_part["IMSI"].dropna().empty else None
        df_part["IMSI"] = df_part["IMSI"].fillna(first_imsi)
        
        first_Operator = df_part["Operator"].dropna().iloc[0] if not df_part["Operator"].dropna().empty else None
        df_part["Operator"] = df_part["Operator"].fillna(first_Operator)
        
        
        # === STEP 1C: Extract Country from filename ===
        base_name = os.path.splitext(file)[0]
        parts = base_name.split("_")
        df_part["Country"] = parts[1] if len(parts) > 1 else "Unknown"

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

file_list = [f for f in os.listdir(input_folder) if f.endswith(".xlsx") and "Ping" in f and "clean" not in f]
with ThreadPoolExecutor(max_workers=4) as executor:
    df_list = list(executor.map(load_file, file_list))
df_list = [df for df in df_list if df is not None]
if not df_list:
    raise ValueError("No Ping raw files loaded.")
df = pd.concat(df_list, ignore_index=True)





# Step 2: Upward fill PingLogfileName until MNC is found (do NOT overwrite MNC row)
for i in reversed(df.index):
    if pd.notnull(df.loc[i, 'PingLogfileName']):
        j = i - 1
        while j >= 0 and pd.isnull(df.loc[j, 'MNC']):
            if pd.isnull(df.loc[j, 'PingLogfileName']):
                df.loc[j, 'PingLogfileName'] = df.loc[i, 'PingLogfileName']
            j -= 1

# Step 3: Assign Segment ID (start at MNC, continue while PingLogfileName is filled)
df['Segment ID'] = None
segment_id = 1
inside_segment = False

for idx in df.index:
    if pd.notnull(df.loc[idx, 'MNC']):
        df.at[idx, 'Segment ID'] = segment_id
        inside_segment = True
    elif inside_segment and pd.notnull(df.loc[idx, 'PingLogfileName']):
        df.at[idx, 'Segment ID'] = segment_id
    elif inside_segment and pd.isnull(df.loc[idx, 'PingLogfileName']):
        inside_segment = False
        segment_id += 1

# Step 4: Assign Test ID using upward fill logic
df['Test ID'] = None

for segment_id, group in df.groupby('Segment ID', dropna=True):
    group = group.sort_index(ascending=True)
    test_id = 1
    indices = list(group.index)

    for i in range(len(indices)):
        idx = indices[i]
        current_time = df.loc[idx, 'PingStartTime']

        if pd.notnull(current_time):
            df.at[idx, 'Test ID'] = test_id

            # Fill upward into previous rows in same segment
            j = i - 1
            while j >= 0 and pd.isnull(df.loc[indices[j], 'PingStartTime']) and pd.isnull(df.loc[indices[j], 'Test ID']):
                df.at[indices[j], 'Test ID'] = test_id
                j -= 1

            test_id += 1
        elif pd.isnull(df.loc[idx, 'Test ID']):
            df.at[idx, 'Test ID'] = test_id

# === Step 4.5: Forward-fill MNC only when PingLogfileName is not blank and within Segment ID ===
for segment_id, group in df.groupby('Segment ID', dropna=True):
    indices = group.index.tolist()
    last_mnc = None
    for idx in indices:
        if pd.notnull(df.at[idx, 'MNC']):
            last_mnc = df.at[idx, 'MNC']
        elif pd.notnull(df.at[idx, 'PingLogfileName']) and last_mnc is not None:
            df.at[idx, 'MNC'] = last_mnc


# === STEP 5: Ensure numeric types for mean-aggregated columns ===
mean_cols = [
    "PingTotalCount",
    "Ping_Count_Attempts",
    "Ping_Count_Success",
    "PingSuccessCount",
    "Ping_Count_Failed",
    "PingFailedRate",
    "PingFailedCount",
    "PingRttAvg",
    "Seconds_Start_to_End_Ping",
    "Ping_Packet_Loss_Rate",
    "Ping_Packet_Success_Rate",
    "Ping_Delay_ms_Avg",
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
    "Radio Common Throughput DL (kbps)",
    "LTE Bearer Maximum Bitrate DL (kbit/s)",
    "LTE PDN Connection AMBR DL (kbps)"
    
    ]

for col in mean_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
        
        
# === STEP 6: Aggregation functions ===
def first_val(x): return x.dropna().iloc[0] if not x.dropna().empty else None
def last_val(x): return x.dropna().iloc[-1] if not x.dropna().empty else None
def modus(x): return x.mode().iloc[0] if not x.mode().empty else None



# === STEP 7: Aggregation rules from Table Design ===
agg_rules = {
    "Date Time": first_val,
    "Latitude": first_val,
    "Longitude": first_val,
    "Type Mobility": first_val,
    "Country": first_val,
    "Operator": first_val,
    "MNC": first_val,
    "IMSI": first_val,
    "PingLogfileName": first_val,
    "Technology_Detail": modus,
    "TAC": modus,
    "PingAddress": modus,
    "PingStartLatitude": last_val,
    "PingStartLongitude": last_val,
    "PingEndLatitude": last_val,
    "PingEndLongitude": last_val,
    "PingDataRadioBearer": modus,
    "PingTotalCount": "sum",
    "Ping_Count_Attempts": "sum",
    "Ping_Count_Success": "sum",
    "PingSuccessCount": "sum",
    "Ping_Count_Failed": "sum",
    "PingFailedRate": "mean",
    "PingFailedCount": "sum",
    "PingStartTime": last_val,
    "PingEndTime": last_val,
    "PingStartRat": modus,
    "PingEndRat": modus,
    "PingStartMultiRATConnectivityMode": modus,
    "PingEndMultiRATConnectivityMode": modus,
    "PingTimeout": modus,
    "PingRttAvg": "mean",
    "PingRttList": last_val,
    "PingRttMax": last_val,
    "PingRttMin": last_val,
    "Ping_Size": modus,
    "Seconds_Start_to_End_Ping": "sum",
    "Ping_Packet_Loss_Rate": "mean",
    "Ping_Packet_Success_Rate": "mean",
    "Ping_Delay_ms_Avg": "mean",
    "Ping_Delay_ms_Max": last_val,
    "Ping_Delay_ms_Min": last_val,
    "Ping_Client_IP_Address": modus,
    "Ping_Server_IP_Address": modus,
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
    "NR BWPs Configured Count DL serving Beam 1": last_val,
    "NR BWP Center NR-ARFCN DL Serving Beam 2": modus,
    "NR BWP Bandwidth DL (Mhz) Serving Beam 2": modus,
    "NR BWP ID DL Serving Beam 2": modus,
    "NR BWP Initial Bandwidth DL Serving Beam 2 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 2": modus,
    "NR BWP Start Point NR-ARFCN DL Serving Beam 2": modus,
    "NR BWP Subcarrier Spacing DL Serving Beam 2": modus,
    "NR BWPs Configured Count DL serving Beam 2": last_val,
    "NR BWP Center NR-ARFCN UL Serving Beam 1": modus,
    "NR BWP Bandwidth UL Serving Beam 1 (Mhz)": modus,
    "NR BWP ID UL Serving Beam 1": modus,
    "NR BWP Initial Bandwidth UL Serving Beam 1 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 1": modus,
    "NR BWP Start Point NR-ARFCN UL Serving Beam 1": modus,
    "NR BWP Subcarrier Spacing UL Serving Beam 1": modus,
    "NR BWPs Configured Count UL Serving Beam 1": last_val,
    "NR BWP Center NR-ARFCN UL Serving Beam 2": modus,
    "NR BWP Bandwidth UL Serving Beam 2 (Mhz)": modus,
    "NR BWP ID UL Serving Beam 2": modus,
    "NR BWP Initial Bandwidth UL Serving Beam 2 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 2": modus,
    "NR BWP Start Point NR-ARFCN UL Serving Beam 2": modus,
    "NR BWP Subcarrier Spacing UL Serving Beam 2": modus,
    "NR BWPs Configured Count UL Serving Beam 2": last_val,
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
    "LTE Bearer Maximum Bitrate DL (kbit/s)": "mean",
    "LTE PDN Connection AMBR DL (kbps)": "mean",
    "FirmwareVersion": modus
    
    }

# === STEP 8: Perform aggregation ===
agg_df = df.groupby(['Segment ID', 'Test ID'], dropna=True).agg(agg_rules).reset_index()

#add Date Stop Time
stop_dates = df.groupby(['Segment ID', 'Test ID'], dropna=True)['Date Time'].last().reset_index()
stop_dates.rename(columns={'Date Time': 'Stop Date Time'}, inplace=True)
agg_df = agg_df.merge(stop_dates, on=['Segment ID', 'Test ID'], how='left')





# === STEP 9: Reorder columns before saving ===
desired_order = [
    "Date Time",
    "Stop Date Time",
    "Segment ID",
    "Test ID",
    "Test Name",
    "Sequence",
    "Type Mobility",
    "Country",
    "Latitude",
    "Longitude",
    "MNC",
    "IMSI",
    "Operator_New",
    "Operator",
    "Technology_Detail",
    "TAC",
    "PingLogfileName",
    "PingAddress",
    "PingStartLatitude",
    "PingStartLongitude",
    "PingEndLatitude",
    "PingEndLongitude",
    "PingDataRadioBearer",
    "PingTotalCount",
    "Ping_Count_Attempts",
    "Ping_Count_Success",
    "PingSuccessCount",
    "Ping_Count_Failed",
    "PingFailedRate",
    "PingFailedCount",
    "PingStartTime",
    "PingEndTime",
    "PingStartRat",
    "PingEndRat",
    "PingStartMultiRATConnectivityMode",
    "PingEndMultiRATConnectivityMode",
    "PingTimeout",
    "PingRttAvg",
    "PingRttList",
    "PingRttMax",
    "PingRttMin",
    "Ping_Size",
    "Seconds_Start_to_End_Ping",
    "Ping_Packet_Loss_Rate",
    "Ping_Packet_Success_Rate",
    "Ping_Delay_ms_Avg",
    "Ping_Delay_ms_Max",
    "Ping_Delay_ms_Min",
    "Ping_Client_IP_Address",
    "Ping_Server_IP_Address",
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
    "LTE Bearer Maximum Bitrate DL (kbit/s)",
    "LTE PDN Connection AMBR DL (kbps)",
    "FirmwareVersion"
    
    
    ]





# Extract Sequence value for Country ===
agg_df['Sequence'] = agg_df.apply(
    lambda row: re.search(r"(TRP\d+_\d+)", str(row['PingLogfileName'])).group(1)
    if row.get('Country') in ['Austria', 'Bremen'] and re.search(r"(TRP\d+_\d+)", str(row['PingLogfileName'])) else None,
    axis=1
)

# === Add 'Test Name' based on Ping_Size ===
def map_test_name(size):
    try:
        size = int(size)
        if size == 800:
            return "Ping 800"
        elif size == 1000:
            return "Ping 1000"
        elif size == 40:
            return "Ping 40"
        elif size == 100:
            return "Ping 100"
        else:
            return f"Ping {size}"
    except:
        return "Ping Unknown"

agg_df['Test Name'] = agg_df['Ping_Size'].apply(map_test_name)


#Only reorder if all columns are present ===
agg_df = agg_df[[col for col in desired_order if col in agg_df.columns]]

#Remove rows where PingLogfileName is blank
agg_df = agg_df[agg_df['PingLogfileName'].notna()]

print("📌 Loading MCC-MNC mapping...")
try:
    mcc_mnc_df = pd.read_excel(mcc_mnc_map_path)
    mcc_mnc_df.columns = mcc_mnc_df.columns.str.strip()
    agg_df.columns = agg_df.columns.str.strip()

    # Pastikan format MNC sama: 3 digit string
    mcc_mnc_df['MNC'] = pd.to_numeric(mcc_mnc_df['MNC'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)
    agg_df['MNC'] = pd.to_numeric(agg_df['MNC'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)

    mcc_mnc_df['Country'] = mcc_mnc_df['Country'].astype(str).str.strip()
    agg_df['Country'] = agg_df['Country'].astype(str).str.strip()

    # Merge untuk mendapatkan Operator_New
    agg_df = agg_df.merge(
        mcc_mnc_df[['Country', 'MNC', 'Operator']].rename(columns={'Operator': 'Operator_New'}),
        on=['Country', 'MNC'],
        how='left'
    )
    
    if 'Test Name' in agg_df.columns and 'Operator_New' in agg_df.columns:
        cols = list(agg_df.columns)
        cols.remove('Operator_New')
        cols.insert(cols.index('Test Name') + 1, 'Operator_New')
        agg_df = agg_df[cols]


    print("✅ Operator_New successfully mapped.")
except Exception as e:
    print(f"⚠️ Could not load operator mapping: {e}")
    agg_df['Operator_New'] = 'Unknown'


# === STEP 14: Export each Country to a separate Excel file in parallel ===
def export_country(country_group):
    country, group_df = country_group
    country_name = country.replace("/", "-").replace(" ", "_")
    output_file = os.path.join(output_path, f"Ping_{country_name}_clean.xlsx")
    group_df.to_excel(output_file, index=False)
    print(f"✅ Saved: {output_file}")

agg_df = agg_df.sort_values(by='Date Time')
with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(export_country, agg_df.groupby('Country'))
