import pandas as pd
import os
import re
from concurrent.futures import ThreadPoolExecutor

# === STEP 0: CONFIGURATION ===
input_folder = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Streaming/Input"
output_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Streaming/Output"
test_case_map_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/code/test case map.xlsx"
mcc_mnc_map_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/code/mncmcc_maping.xlsx"
os.makedirs(output_path, exist_ok=True)


# === STEP 1: Load all raw HTTP files in parallel and extract Country and Type Mobility from filename ===
def load_file(file):
    full_path = os.path.join(input_folder, file)
    try:
        df_part = pd.read_excel(full_path)

        # === STEP 1B: Fill MCC and MNC per file ===
      
        df_part["MNC"] = pd.to_numeric(df_part["MNC"], errors="coerce")
        first_mnc = df_part["MNC"].dropna().iloc[0] if not df_part["MNC"].dropna().empty else None
        df_part["MNC"] = df_part["MNC"].fillna(first_mnc)

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

file_list = [f for f in os.listdir(input_folder) if f.endswith(".xlsx") and "Streaming" in f and "clean" not in f]
with ThreadPoolExecutor(max_workers=4) as executor:
    df_list = list(executor.map(load_file, file_list))
df_list = [df for df in df_list if df is not None]
if not df_list:
    raise ValueError("No Streaming raw files loaded.")
df = pd.concat(df_list, ignore_index=True)


# === STEP 2: Forward-fill HTTP_URL and segment by HttpServiceStatus ===
df['Streaming_URL'] = df['Streaming_URL'].ffill()
segment = df['StreamingServiceStatus'].notnull().cumsum()
df['Streaming_URL'] = df.groupby(segment)['Streaming_URL'].ffill()
df.loc[df['StreamingServiceStatus'].notnull() & df['Streaming_URL'].isnull(), 'Streaming_URL'] = df['Streaming_URL'].ffill()

# === STEP 3: Assign Test Id per HTTP_URL segment ===
is_new_test = (df['Streaming_URL'] != df['Streaming_URL'].shift(1)) & df['Streaming_URL'].notnull()
df['Test Id'] = is_new_test.cumsum().where(df['Streaming_URL'].notnull())
df['Test Id'] = df['Test Id'].apply(lambda x: f"Test {int(x)}" if pd.notnull(x) else None)

# === STEP 4: Ensure numeric types for mean-aggregated columns ===
mean_cols = [
    "Aborted_by_User","PUSCH Phy Throughput Carrier 4 (kbps)",
    "Streaming_Completion_Rate","LTE RLC Throughput DL (Kbps)",
    "Streaming_Setup_Success_Rate","LTE RLC Throughput UL (Kbps)",
    "Streaming_Success_Rate","NR Serving Cell SS RSSI Top #1",
    "StreamingSessionTime","NR Serving Cell SS RSRP Top #1",
    "Streaming_Session_Failure_Ratio","NR Serving Cell SS SINR Top #1",
    "Streaming_Number_Of_Video_Session_Interruptions","NR Serving Cell SS RSRQ Top #1",
    "Streaming_Total_Duration_Of_Video_Session_Interruptions","NR Neighbor Cell 1 SS RSRP (dBm)",
    "Streaming_Maximum_Duration_Of_Video_Session_Interruptions","NR Neighbor Cell 1 SS SINR (dB)",
    "Streaming_Session_Without_Interruption_Rate","NR Neighbor Cell 1 SS RSRQ (dB)",
    "Streaming_Duration","NR Phy Throughput Multi-RAT DL (kbps)",
    "Seconds_Start_to_End_Streaming","NR Phy Throughput Multi-RAT UL (kbps)",
    "Streaming_HD_Resolution_Ratio","NR PDSCH Phy Throughput Total (Kbps)",
    "Streaming_Average_Session_Resolution","NR Pcell PDSCH Scheduled Throughput (Mbps)",
    "Streaming_Average_Throughput","NR PDSCH Phy Throughput Serving Beam 1 (Kbps)",
    "StreamingThroughputAvg","NR PDSCH BLER (%) Serving Beam 1",
    "Streaming_Throughput_Filtered","NR PDSCH CQI Serving Beam 1",
    "StreamingPlayerDownloadDataTransferTime","NR PDSCH RI Serving Beam 1",
    "StreamingPlayerIpServiceAccessTime","NR DL Pathloss Serving Beam 1",
    "StreamingPlayerSessionTime","NR PDSCH Phy Throughput Serving Beam 2 (Kbps)",
    "StreamingReproductionStartDelay","NR PDSCH BLER (%) Serving Beam 2",
    "StreamingResolutionAvg","NR PDSCH CQI Serving Beam 2",
    "StreamingServiceAccessTime","NR PDSCH RI Serving Beam 2",
    "Streaming_Service_Access_Time_ms","NR DL Pathloss Serving Beam 2",
    "Streaming_Service_Access_Time_sec","NR PUSCH Phy Throughput Total (kbps)",
    "Streaming_Service_Non_Accessibility","NR Pcell PUSCH Scheduled Throughput (Mbps)",
    "StreamingInterruptionDurationTotal","NR PUSCH Phy Throughput Serving Beam 1 (Kbps)",
    "StreamingInterruptionDurationMax","NR PUSCH BLER (%) Serving Beam 1",
    "Streaming_State_Event_Source_Time","NR PUSCH Phy Throughput Serving Beam 2 (Kbps)",
    "Streaming_State_Prebuffering_to_Reproducing_Delay","NR PUSCH BLER (%) Serving Beam 2",
    "Streaming_State_Request_to_Prebuffering_Delay","NR MAC DL Throughput Total (kbps)",
    "Streaming_State_Request_to_Reproducing_Delay","NR MAC UL Throughput Total (kbps)",
    "StreamingStateRebufferingTime","NR RLC DL Throughput Total (kbps)",
    "StreamingTimeToFirstByte","NR RLC UL Throughput Total (kbps)",
    "StreamingVideoInterruptionCount","NR RLC DL Throughput (Kbps)",
    "StreamingVideoIpServiceAccessTime","NR RLC UL Throughput (Kbps)",
    "StreamingVideoPlayStartTime","NR BWPs Configured Count DL serving Beam 1",
    "StreamingVideoSessionTime","NR BWPs Configured Count DL serving Beam 2",
    "Streaming_Video_IP_Service_Access_Time_ms","NR BWPs Configured Count UL Serving Beam 1",
    "Streaming_Video_IP_Service_Access_Time_sec","NR BWPs Configured Count UL Serving Beam 2",
    "Streaming_Video_Play_Start_Failure_Ratio","MR-DC Cell 1 SINR (dB)",
    "Streaming_Video_Play_Start_Time_sec","PDSCH Average RBs per Allocated Slot Serving Beam 1",
    "Streaming_Video_Session_Cutoff_Ratio","PDSCH Average RBs per Allocated Slot per TB Serving Beam 1",
    "Streaming_Video_Session_Failure_Ratio","PDSCH RB Allocation Count Serving Beam 1",
    "Streaming_Video_Session_Success_Ratio","PDSCH RB Allocation Count per TB Serving Beam 1",
    "Streaming_Video_Session_Time_sec","PDSCH RB Allocation Usage Serving Beam 1 (%)",
    "Streaming_Reproduction_Cutoff_Ratio","PDSCH Slot Allocation Count Serving Beam 1",
    "Streaming_Reproduction_Start_Delay_sec","PDSCH Slot Allocation Count per TB Serving Beam 1",
    "Streaming_Reproduction_Start_Failure_Ratio","PDSCH Slot Allocation TDD Serving Beam 1 (%)",
    "Streaming_Impairment_Free_Video_Session_Ratio","PDSCH Slot Allocation Total Serving Beam 1 (%)",
    "LTE Serving Cell Channel RSSI(dBm)","PDSCH Slot Utilization Serving Beam 1 (%)",
    "LTE Serving Cell RSRP(dBm)","PDSCH RB Dist Current Count Serving Beam 1",
    "LTE Serving Cell RS SINR(dB)","PDSCH RB Utillization Dist Current Count Serving Beam 1",
    "LTE Serving Cell RSRQ (dB)","PDSCH Average RBs per Allocated Slot Serving Beam 2",
    "LTE_Serving_Cell_Count_Average","PDSCH Average RBs per Allocated Slot per TB Serving Beam 2",
    "LTE Secondary Serving Cell 1 Channel RSSI (dBm)","PDSCH RB Allocation Count Serving Beam 2",
    "LTE Secondary Serving Cell 1 RSRP (dBm)","PDSCH RB Allocation Count per TB Serving Beam 2",
    "LTE Secondary Serving Cell 1 RS SINR (dB)","PDSCH RB Allocation Usage Serving Beam 2 (%)",
    "LTE Secondary Serving Cell 1 RSRQ (dB)","PDSCH Slot Allocation Count Serving Beam 2",
    "LTE Neighbor Cell 1 RSRP","PDSCH Slot Allocation Count per TB Serving Beam 2",
    "LTE Neighbor Cell 1 RSRQ","PDSCH Slot Allocation TDD Serving Beam 2 (%)",
    "LTE Serving Cell DL Pathloss Carrier 1 (dB)","PDSCH Slot Allocation Total Serving Beam 2 (%)",
    "LTE MAC DL Throughput (kbps)","PDSCH Slot Utilization Serving Beam 2 (%)",
    "LTE MAC DL Throughput Carrier 1 (kbps)","PDSCH RB Dist Current Count Serving Beam 2",
    "LTE MAC DL Throughput Carrier 2 (kbps)","PDSCH RB Utillization Dist Current Count Serving Beam 2",
    "LTE MAC DL Throughput Carrier 3 (kbps)","PUSCH Average RBs per Allocated Slot Serving Beam 1",
    "LTE MAC DL Throughput Carrier 4 (kbps)","PUSCH RB Allocation Count Serving Beam 1",
    "LTE MAC UL Throughput (kbps)","PUSCH RB Allocation Usage Serving Beam 1 (%)",
    "LTE MAC UL Throughput Carrier 1 (kbps)","PUSCH Slot Allocation Count Serving Beam 1",
    "LTE MAC UL Throughput Carrier 2 (kbps)","PUSCH Slot Allocation TDD Serving Beam 1 (%)",
    "LTE MAC UL Throughput Carrier 3 (kbps)","PUSCH Slot Allocation Total Serving Beam 1 (%)",
    "LTE MAC UL Throughput Carrier 4 (kbps)","PUSCH Slot Utilization Serving Beam 1 (%)",
    "LTE PDSCH BLER (%)","PUSCH RB Dist Current Count Serving Beam 1",
    "LTE PDSCH Phy Throughput (kbps)","PUSCH RB Utillization Dist Current Count Serving Beam 1",
    "LTE PDSCH Phy Throughput Total (kbps)","PUSCH Average RBs per Allocated Slot Serving Beam 2",
    "LTE PDSCH Phy Throughput Carrier 1 (kbps)","PUSCH RB Allocation Count Serving Beam 2",
    "LTE PDSCH Phy Throughput Carrier 2 (kbps)","PUSCH RB Allocation Usage Serving Beam 2 (%)",
    "LTE PDSCH Phy Throughput Carrier 3 (kbps)","PUSCH Slot Allocation Count Serving Beam 2",
    "LTE PDSCH Phy Throughput Carrier 4 (kbps)","PUSCH Slot Allocation TDD Serving Beam 2 (%)",
    "PUSCH BLER (%)","PUSCH Slot Allocation Total Serving Beam 2 (%)",
    "LTE PUSCH Phy Throughput (kbps)","PUSCH Slot Utilization Serving Beam 2 (%)",
    "LTE PUSCH Phy Throughput Total (kbps)","PUSCH RB Dist Current Count Serving Beam 2",
    "LTE PUSCH Phy Throughput Carrier 1 (kbps)","PUSCH RB Utillization Dist Current Count Serving Beam 2",
    "LTE PUSCH Phy Throughput Carrier 2 (kbps)","Radio Common Throughput DL (kbps)",
    "LTE PUSCH Phy Throughput Carrier 3 (kbps)","LTE Bearer Maximum Bitrate DL (kbit/s)",
    "LTE PDN Connection AMBR DL (kbps)"
    ]
for col in mean_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
   

   
# === STEP 5: Aggregation functions ===
def first_val(x): return x.dropna().iloc[0] if not x.dropna().empty else None
def last_val(x): return x.dropna().iloc[-1] if not x.dropna().empty else None
def modus(x): return x.mode().iloc[0] if not x.mode().empty else None

# === STEP 6: Aggregation rules from Table Design ===
agg_rules = {
    "Date Time": first_val,
    "Streaming_Outcome_Type": last_val,
    "StreamingServiceStatus": last_val,
    "StreamingLogfileName": last_val,
    "MNC": first_val,
    "Type Mobility": first_val,
    "Country": first_val,
    "Latitude": first_val,
    "Longitude": first_val,
    "Technology_Detail": modus,
    "StreamingDevice": last_val,
    "StreamingOperator": last_val,
    "StreamingImsi": last_val,
    "TAC": modus,
    "StreamingStartLongitude": first_val,
    "StreamingStartLatitude": first_val,
    "StreamingEndLongitude": last_val,
    "StreamingEndLatitude": last_val,
    "StreamingStartRat": modus,
    "StreamingEndRat": modus,
    "StreamingStartMultiRATConnectivityMode": modus,
    "StreamingEndMultiRATConnectivityMode": modus,
    "StreamingStartTime": last_val,
    "StreamingEndTime": last_val,
    "Aborted_by_User": "sum",
    "Streaming_Completion_Rate": "mean",
    "Streaming_Setup_Success_Rate": "mean",
    "Streaming_Success_Rate": "mean",
    "StreamingDataRadioBearer": modus,
    "StreamingServiceBearer": modus,
    "StreamingSessionIdentity": last_val,
    "StreamingSessionTime": "mean",
    "Streaming_Session_Failure_Ratio": "mean",
    "Streaming_Number_Of_Video_Session_Interruptions": "sum",
    "Streaming_Total_Duration_Of_Video_Session_Interruptions": "sum",
    "Streaming_Maximum_Duration_Of_Video_Session_Interruptions": "max",
    "Streaming_Session_Without_Interruption_Rate": "mean",
    "Streaming_Duration": "mean",
    "Seconds_Start_to_End_Streaming": "mean",
    "Streaming_HD_Resolution": modus,
    "Streaming_HD_Resolution_Ratio": "mean",
    "Streaming_Average_Session_Resolution": "mean",
    "Streaming_Average_Throughput": "mean",
    "StreamingThroughputAvg": "mean",
    "Streaming_Throughput_Filtered": "mean",
    "StreamingPlayerDownloadDataTransferTime": "mean",
    "StreamingPlayerIpServiceAccessTime": "mean",
    "StreamingPlayerSessionTime": "mean",
    "StreamingProbeName": last_val,
    "StreamingProbeVersion": last_val,
    "StreamingReproductionStartDelay": "mean",
    "StreamingResolutionAvg": "mean",
    "StreamingServiceAccessTime": "mean",
    "Streaming_Service_Access_Time_ms": "mean",
    "Streaming_Service_Access_Time_sec": "mean",
    "Streaming_Service_Non_Accessibility": "mean",
    "StreamingInterruptionDurationTotal": "sum",
    "StreamingInterruptionDurationMax": "max",
    "Streaming_State_Event_Source_Time": "mean",
    "Streaming_State_Prebuffering_to_Reproducing_Delay": "mean",
    "Streaming_State_Request_to_Prebuffering_Delay": "mean",
    "Streaming_State_Request_to_Reproducing_Delay": "mean",
    "StreamingStateBufferingCompleteTime": last_val,
    "StreamingStateDoneTime": last_val,
    "StreamingStatePlayerDownloadEndTime": last_val,
    "StreamingStatePlayerDownloadStartTime": last_val,
    "StreamingStatePlayerRequestTime": last_val,
    "StreamingStatePrebufferingTime": last_val,
    "StreamingStateRebufferingTime": "mean",
    "StreamingStateReproducingTime": last_val,
    "StreamingStateVideoRequestTime": last_val,
    "StreamingTimeToFirstByte": "mean",
    "StreamingVideoInterruptionCount": "mean",
    "StreamingVideoIpServiceAccessTime": "mean",
    "StreamingVideoPlayStartTime": "mean",
    "StreamingVideoSessionTime": "mean",
    "Streaming_Video_IP_Service_Access_Time_ms": "mean",
    "Streaming_Video_IP_Service_Access_Time_sec": "mean",
    "Streaming_Video_Play_Start_Failure_Ratio": "mean",
    "Streaming_Video_Play_Start_Time_sec": "mean",
    "Streaming_Video_Session_Cutoff_Ratio": "mean",
    "Streaming_Video_Session_Failure_Ratio": "mean",
    "Streaming_Video_Session_Success_Ratio": "mean",
    "Streaming_Video_Session_Time_sec": "mean",
    "Streaming_Reproduction_Cutoff_Ratio": "mean",
    "Streaming_Reproduction_Start_Delay_sec": "mean",
    "Streaming_Reproduction_Start_Failure_Ratio": "mean",
    "Streaming_Impairment_Free": modus,
    "Streaming_Impairment_Free_Video_Session_Ratio": "mean",
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
    "NR Serving Beam 1 NRARFCN DL": modus,
    "NR Serving Beam 1 Band": modus,
    "NR Serving Beam 1 Bandwidth DL": modus,
    "NR Serving Beam 1 Bandwidth UL": modus,
    "NR Serving Beam 1 SSB Index": modus,
    "NR Serving Beam 1 Cell Type": modus,
    "NR Serving Beam 1 GSCN": modus,
    "NR Serving Beam 2 Cell Identity": modus,
    "NR Serving Beam 2 NRARFCN DL": modus,
    "NR Serving Beam 2 Band": modus,
    "NR Serving Beam 2 Bandwidth DL": modus,
    "NR Serving Beam 2 Bandwidth UL": modus,
    "NR Serving Beam 2 SSB Index": modus,
    "NR Serving Beam 2 Cell Type": modus,
    "NR Serving Beam 2 GSCN": modus,
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
    "LTE Bearer Maximum Bitrate DL (kbit/s)": "mean",
    "LTE PDN Connection AMBR DL (kbps)": "mean",
    "FirmwareVersion": modus
    }

# === STEP 8: Perform aggregation ===
agg_df = df.groupby(['Streaming_URL', 'Test Id'], dropna=True).agg(agg_rules).reset_index()

#add Date Stop Time
stop_dates = df.groupby(['Streaming_URL', 'Test Id'], dropna=True)['Date Time'].last().reset_index()
stop_dates.rename(columns={'Date Time': 'Stop Date Time'}, inplace=True)
agg_df = agg_df.merge(stop_dates, on=['Streaming_URL', 'Test Id'], how='left')

# === STEP 9: Reorder columns before saving ===
desired_order = [
    "Date Time",
    "Stop Date Time",
    "Test Id",
    "Test Name",
    "Type Mobility",
    "Operator",
    "Country",
    "Sequence",
    "Latitude",
    "Longitude",
    "MNC",
    "Technology_Detail",
    "StreamingDevice",
    "StreamingOperator",
    "StreamingImsi",
    "TAC",
    "StreamingStartLongitude",
    "StreamingStartLatitude",
    "StreamingEndLongitude",
    "StreamingEndLatitude",
    "StreamingStartRat",
    "StreamingEndRat",
    "Play Request to 1st Picture",
    "StreamingStartMultiRATConnectivityMode",
    "StreamingEndMultiRATConnectivityMode",
    "StreamingStartTime",
    "StreamingEndTime",
    "StreamingLogfileName",
    "Streaming_URL",
    "Streaming_Outcome_Type",
    "Aborted_by_User",
    "Streaming_Completion_Rate",
    "Streaming_Setup_Success_Rate",
    "Streaming_Success_Rate",
    "StreamingDataRadioBearer",
    "StreamingServiceBearer",
    "StreamingSessionIdentity",
    "StreamingSessionTime",
    "Streaming_Session_Failure_Ratio",
    "Streaming_Number_Of_Video_Session_Interruptions",
    "Streaming_Total_Duration_Of_Video_Session_Interruptions",
    "Streaming_Maximum_Duration_Of_Video_Session_Interruptions",
    "Streaming_Session_Without_Interruption_Rate",
    "Streaming_Duration",
    "Seconds_Start_to_End_Streaming",
    "Streaming_HD_Resolution",
    "Streaming_HD_Resolution_Ratio",
    "Streaming_Average_Session_Resolution",
    "Streaming_Average_Throughput",
    "StreamingThroughputAvg",
    "Streaming_Throughput_Filtered",
    "StreamingPlayerDownloadDataTransferTime",
    "StreamingPlayerIpServiceAccessTime",
    "StreamingPlayerSessionTime",
    "StreamingProbeName",
    "StreamingProbeVersion",
    "StreamingReproductionStartDelay",
    "StreamingResolutionAvg",
    "StreamingServiceStatus",
    "StreamingServiceAccessTime",
    "Streaming_Service_Access_Time_ms",
    "Streaming_Service_Access_Time_sec",
    "Streaming_Service_Non_Accessibility",
    "StreamingInterruptionDurationTotal",
    "StreamingInterruptionDurationMax",
    "Streaming_State_Event_Source_Time",
    "Streaming_State_Prebuffering_to_Reproducing_Delay",
    "Streaming_State_Request_to_Prebuffering_Delay",
    "Streaming_State_Request_to_Reproducing_Delay",
    "StreamingStateBufferingCompleteTime",
    "StreamingStateDoneTime",
    "StreamingStatePlayerDownloadEndTime",
    "StreamingStatePlayerDownloadStartTime",
    "StreamingStatePlayerRequestTime",
    "StreamingStatePrebufferingTime",
    "StreamingStateRebufferingTime",
    "StreamingStateReproducingTime",
    "StreamingStateVideoRequestTime",
    "StreamingTimeToFirstByte",
    "StreamingVideoInterruptionCount",
    "StreamingVideoIpServiceAccessTime",
    "StreamingVideoPlayStartTime",
    "StreamingVideoSessionTime",
    "Streaming_Video_IP_Service_Access_Time_ms",
    "Streaming_Video_IP_Service_Access_Time_sec",
    "Streaming_Video_Play_Start_Failure_Ratio",
    "Streaming_Video_Play_Start_Time_sec",
    "Streaming_Video_Session_Cutoff_Ratio",
    "Streaming_Video_Session_Failure_Ratio",
    "Streaming_Video_Session_Success_Ratio",
    "Streaming_Video_Session_Time_sec",
    "Streaming_Reproduction_Cutoff_Ratio",
    "Streaming_Reproduction_Start_Delay_sec",
    "Streaming_Reproduction_Start_Failure_Ratio",
    "Streaming_Impairment_Free",
    "Streaming_Impairment_Free_Video_Session_Ratio",
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
    "FirmwareVersion",
    "Qualifier"

    ]
    
#=== Map Country and MNC to find Operator  ===
try:
    mcc_mnc_df = pd.read_excel(mcc_mnc_map_path)

    if {'Country', 'MNC', 'Operator'}.issubset(mcc_mnc_df.columns):
       # Convert MNC safely from float-like string to zero-padded string
        mcc_mnc_df['MNC'] = pd.to_numeric(mcc_mnc_df['MNC'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)
        agg_df['MNC'] = pd.to_numeric(agg_df['MNC'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)

        # Clean up Country fields
        mcc_mnc_df['Country'] = mcc_mnc_df['Country'].astype(str).str.strip()
        agg_df['Country'] = agg_df['Country'].astype(str).str.strip()

        # Merge
        agg_df = agg_df.merge(
            mcc_mnc_df[['Country', 'MNC', 'Operator']],
            on=['Country', 'MNC'],
            how='left'
        )
        agg_df['Operator'] = agg_df['Operator'].fillna('Unknown')
        print("✅ Operator mapping applied.")
    else:
        print("⚠️ Required columns 'Country', 'MNC', 'Operator' not found in operator mapping file.")
except Exception as e:
    print(f"⚠️ Could not load operator mapping: {e}")
    
    
# === Map HTTP_URL and Country to Test Name ===
try:
    test_case_df = pd.read_excel(test_case_map_path)
    agg_df.rename(columns={'Streaming_URL': 'HTTP_URL'}, inplace=True)

    if {'HTTP_URL', 'Country', 'Test Name'}.issubset(test_case_df.columns) and {'HTTP_URL', 'Country'}.issubset(agg_df.columns):
        agg_df = agg_df.merge(test_case_df[['HTTP_URL', 'Country', 'Test Name']], on=['HTTP_URL', 'Country'], how='left')
        agg_df['Test Name'] = agg_df['Test Name'].fillna('Not_found')
        print("✅ Test Name mapping (by URL & Country) applied.")
    else:
        print("⚠️ Columns 'HTTP_URL', 'Country', or 'Test Name' not found in test case mapping file or main data.")
except Exception as e:
    print(f"⚠️ Could not load test case mapping: {e}")
    
# === Add Play Request to 1st Picture column === note :Need add on reorder column
from datetime import datetime, date, time

def convert_time_to_datetime(t):
    if pd.isnull(t):
        return None
    if isinstance(t, datetime):
        return t
    if isinstance(t, time):
        return datetime.combine(date(2000, 1, 1), t)
    return pd.to_datetime(t, errors='coerce')

try:
    agg_df['Play Request to 1st Picture'] = agg_df.apply(
        lambda row: round(
            (convert_time_to_datetime(row['StreamingStatePlayerRequestTime']) - 
             convert_time_to_datetime(row['StreamingStartTime'])).total_seconds(), 3)
        if pd.notnull(row['StreamingStatePlayerRequestTime']) and pd.notnull(row['StreamingStartTime'])
        else 'N/A',
        axis=1
    )
except Exception as e:
    agg_df['Play Request to 1st Picture'] = 'N/A'
    print(f"⚠️ Could not compute 'Play Request to 1st Picture': {e}")
    
    
# Add Sequence based on country
# === Extract Sequence from HttpLogfileName if Country == Austria ===

def extract_sequence(filename):
    match = re.search(r"EQ1_Data_(TRP\d+_\d+)_MS\d+", str(filename))
    if match:
        return match.group(1)
    return None

agg_df['Sequence'] = agg_df.apply(
    lambda row: extract_sequence(row['StreamingLogfileName']) if row.get('Country') in ['Austria', 'Bremen'] else None,
    axis=1
)


#Add Qualifier column based on Test Name ===
def check_qualifier(row):
    play_pic = row.get("Play Request to 1st Picture") or 0
    stream_acc = row.get("Streaming_Service_Access_Time_sec") or 0
    interruptions = row.get("Streaming_Number_Of_Video_Session_Interruptions") or 0
    
    name = str(row.get("Test Case", "")).upper()
    if name == "YOUTUBELIVE" or name == "YOUTUBE VOD":
        if stream_acc > 10 or play_pic > 10 or interruptions > 0:
            return "Not Qualified"
    return "Qualified"


agg_df['Qualifier'] = agg_df.apply(check_qualifier, axis=1)

agg_df.rename(columns={'HTTP_URL': 'Streaming_URL'}, inplace=True)


# === STEP 13: Only reorder if all columns are present ===
agg_df = agg_df[[col for col in desired_order if col in agg_df.columns]]


# === STEP 14: Export each Country to a separate Excel file in parallel ===
def export_country(country_group):
    country, group_df = country_group
    country_name = country.replace("/", "-").replace(" ", "_")
    output_file = os.path.join(output_path, f"Streaming_{country_name}_clean.xlsx")
    group_df.to_excel(output_file, index=False)
    print(f"✅ Saved: {output_file}")

agg_df = agg_df.sort_values(by='Date Time')
with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(export_country, agg_df.groupby('Country'))





