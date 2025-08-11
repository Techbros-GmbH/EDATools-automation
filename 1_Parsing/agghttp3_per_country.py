import pandas as pd
import os
import re
from concurrent.futures import ThreadPoolExecutor

# === STEP 0: CONFIGURATION ===
input_folder = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/HTTP/Input"
output_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/HTTP/Output"
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

file_list = [f for f in os.listdir(input_folder) if f.endswith(".xlsx") and "HTTP" in f and "clean" not in f]
with ThreadPoolExecutor(max_workers=4) as executor:
    df_list = list(executor.map(load_file, file_list))
df_list = [df for df in df_list if df is not None]
if not df_list:
    raise ValueError("No HTTP raw files loaded.")
df = pd.concat(df_list, ignore_index=True)

# === STEP 2: Forward-fill HTTP_URL and segment test sessions ===
segment = df['HttpServiceStatus'].notnull().cumsum()
df['HTTP_URL'] = df['HTTP_URL'].ffill()
df['HTTP_URL'] = df.groupby(segment)['HTTP_URL'].ffill()
df.loc[df['HttpServiceStatus'].notnull() & df['HTTP_URL'].isnull(), 'HTTP_URL'] = df['HTTP_URL'].ffill()

# === STEP 3: Assign Test Id ===
is_new_test = (df['HTTP_URL'] != df['HTTP_URL'].shift(1)) & df['HTTP_URL'].notnull()
df['Test Id'] = is_new_test.cumsum().where(df['HTTP_URL'].notnull())
df['Test Id'] = df['Test Id'].apply(lambda x: f"Test {int(x)}" if pd.notnull(x) else None)

# === STEP 3: Ensure numeric types for mean-aggregated columns ===
mean_cols = [
    "NR Serving Beam 1 SSB Index", "NR Serving Cell SS RSSI Top #1",
    "NR Serving Cell SS RSRP Top #1", "NR Serving Cell SS SINR Top #1",
    "NR Serving Cell SS RSRQ Top #1", "NR Neighbor Cell 1 SS RSRP (dBm)",
    "DNS_Host_Name_Resolution_Failure_Ratio","LTE PDSCH Phy Throughput Carrier 3 (kbps)",
    "DNS_Host_Name_Resolution_Time_sec","LTE PDSCH Phy Throughput Carrier 4 (kbps)",
    "DNS_Host_Name_Total_Resolution_Time_sec","PUSCH BLER (%)",
    "DNS Resolution Success Ratio (%)","LTE PUSCH Phy Throughput (kbps)",
    "First_DNS_Request_to_HTTP_Get_First_Chunk_Downloaded_ms","LTE PUSCH Phy Throughput Total (kbps)",
    "HttpDataTransferCutoff","LTE PUSCH Phy Throughput Carrier 1 (kbps)",
    "HttpDataTransferTime","LTE PUSCH Phy Throughput Carrier 2 (kbps)",
    "HttpIpServiceSetupTime","LTE PUSCH Phy Throughput Carrier 3 (kbps)",
    "HttpMeanDataRate","PUSCH Phy Throughput Carrier 4 (kbps)",
    "HTTP_Download_Service_Average_Throughput","LTE RLC Throughput DL (Kbps)",
    "HTTP_Download_Session_Failure_Ratio","LTE RLC Throughput UL (Kbps)",
    "HTTP_Download_Session_Success_Ratio","NR Neighbor Cell 1 SS SINR (dB)",
    "HTTP_Technical_Browsing_Time_sec","NR Neighbor Cell 1 SS RSRQ (dB)",
    "HTTP_User_Browsing_Time_sec","NR Phy Throughput Multi-RAT DL (kbps)",
    "Seconds_Start_to_End_HTTP","NR Phy Throughput Multi-RAT UL (kbps)",
    "HTTP_Download_Average_Throughput","NR PDSCH Phy Throughput Total (Kbps)",
    "HTTP Data Transfer Cutoff Ratio (%)","NR Pcell PDSCH Scheduled Throughput (Mbps)",
    "HTTP Download Throughput (kbps)","NR PDSCH Phy Throughput Serving Beam 1 (Kbps)",
    "HTTP_Download_Data_Transfer_Failure_Ratio_Method_A","NR PDSCH BLER (%) Serving Beam 1",
    "HTTP_Download_Data_Transfer_Success_Ratio_Method_A","NR PDSCH CQI Serving Beam 1",
    "HTTP_Download_Data_Transfer_Time_sec_Method_A","NR PDSCH RI Serving Beam 1",
    "HTTP_Download_IP_Service_Access_Failure_Ratio_Method_A","NR DL Pathloss Serving Beam 1",
    "HTTP_Download_IP_Service_Setup_Success_Ratio_Method_A","NR PDSCH Phy Throughput Serving Beam 2 (Kbps)",
    "HTTP_Download_IP_Service_Setup_Time_sec_Method_A","NR PDSCH BLER (%) Serving Beam 2",
    "HTTP_Download_Mean_Data_Rate_kbps_Method_A","NR PDSCH CQI Serving Beam 2",
    "HTTP_Download_Transfer_Start_Delay_Method_A","NR PDSCH RI Serving Beam 2",
    "HTTP_Download_Data_Transfer_Failure_Ratio_Method_B","NR DL Pathloss Serving Beam 2",
    "HTTP_Download_Data_Transfer_Success_Ratio_Method_B","NR PUSCH Phy Throughput Total (kbps)",
    "HTTP_Download_Data_Transfer_Time_sec_Method_B","NR Pcell PUSCH Scheduled Throughput (Mbps)",
    "HTTP_Download_IP_Service_Access_Failure_Ratio_Method_B","NR PUSCH Phy Throughput Serving Beam 1 (Kbps)",
    "HTTP_Download_IP_Service_Setup_Success_Ratio_Method_B","NR PUSCH BLER (%) Serving Beam 1",
    "HTTP_Download_IP_Service_Setup_Time_sec_Method_B","NR PUSCH Phy Throughput Serving Beam 2 (Kbps)",
    "HTTP_Download_Mean_Data_Rate_kbps_Method_B","NR PUSCH BLER (%) Serving Beam 2",
    "Seconds_Start_to_End_HTTP_Post","NR MAC DL Throughput Total (kbps)",
    "HTTP_Upload_Average_Throughput","NR MAC UL Throughput Total (kbps)",
    "First_DNS_Request_to_HTTP_Post_First_Chunk_Uploaded_ms","NR RLC DL Throughput Total (kbps)",
    "HTTP_Upload_Session_Failure_Ratio","NR RLC UL Throughput Total (kbps)",
    "HTTP_Upload_Session_Success_Ratio","NR RLC DL Throughput (Kbps)",
    "HTTP_Upload_Data_Transfer_Failure_Ratio_Method_A","NR RLC UL Throughput (Kbps)",
    "HTTP_Upload_Data_Transfer_Success_Ratio_Method_A","NR BWPs Configured Count DL serving Beam 1",
    "HTTP_Upload_Data_Transfer_Time_sec_Method_A","NR BWPs Configured Count DL serving Beam 2",
    "HTTP_Upload_IP_Service_Access_Failure_Ratio_Method_A","NR BWPs Configured Count UL Serving Beam 1",
    "HTTP_Upload_IP_Service_Setup_Success_Ratio_Method_A","NR BWPs Configured Count UL Serving Beam 2",
    "HTTP_Upload_IP_Service_Setup_Time_sec_Method_A","MR-DC Cell 1 SINR (dB)",
    "HTTP_Upload_Mean_Data_Rate_kbps_Method_A","PDSCH Average RBs per Allocated Slot Serving Beam 1",
    "HTTP_Upload_Data_Transfer_Failure_Ratio_Method_B","PDSCH Average RBs per Allocated Slot per TB Serving Beam 1",
    "HTTP_Upload_Data_Transfer_Success_Ratio_Method_B","PDSCH RB Allocation Count Serving Beam 1",
    "HTTP_Upload_Data_Transfer_Time_sec_Method_B","PDSCH RB Allocation Count per TB Serving Beam 1",
    "HTTP_Upload_IP_Service_Access_Failure_Ratio_Method_B","PDSCH RB Allocation Usage Serving Beam 1 (%)",
    "HTTP_Upload_IP_Service_Setup_Success_Ratio_Method_B","PDSCH Slot Allocation Count Serving Beam 1",
    "HTTP_Upload_IP_Service_Setup_Time_sec_Method_B","PDSCH Slot Allocation Count per TB Serving Beam 1",
    "HTTP_Upload_Mean_Data_Rate_kbps_Method_B","PDSCH Slot Allocation TDD Serving Beam 1 (%)",
    "IP_Interruption_Time_ms","PDSCH Slot Allocation Total Serving Beam 1 (%)",
    "TCP_Handshake_Time_sec","PDSCH Slot Utilization Serving Beam 1 (%)",
    "TLSHandshakeFailureRatio (%)","PDSCH RB Dist Current Count Serving Beam 1",
    "ThroughputCountOver1MBit","PDSCH RB Utillization Dist Current Count Serving Beam 1",
    "ThroughputCountOver3MBit","PDSCH Average RBs per Allocated Slot Serving Beam 2",
    "ThroughputPercentageOver3MBit","PDSCH Average RBs per Allocated Slot per TB Serving Beam 2",
    "IEBrowseDownloadTime(ms)","PDSCH RB Allocation Count Serving Beam 2",
    "IEBrowsePageSize(Bytes)","PDSCH RB Allocation Count per TB Serving Beam 2",
    "LTE Serving Cell Channel RSSI(dBm)","PDSCH RB Allocation Usage Serving Beam 2 (%)",
    "LTE Serving Cell RSRP(dBm)","PDSCH Slot Allocation Count Serving Beam 2",
    "LTE Serving Cell RS SINR(dB)","PDSCH Slot Allocation Count per TB Serving Beam 2",
    "LTE Serving Cell RSRQ (dB)","PDSCH Slot Allocation TDD Serving Beam 2 (%)",
    "LTE_Serving_Cell_Count_Average","PDSCH Slot Allocation Total Serving Beam 2 (%)",
    "LTE Secondary Serving Cell 1 Channel RSSI (dBm)","PDSCH Slot Utilization Serving Beam 2 (%)",
    "LTE Secondary Serving Cell 1 RSRP (dBm)","PDSCH RB Dist Current Count Serving Beam 2",
    "LTE Secondary Serving Cell 1 RS SINR (dB)","PDSCH RB Utillization Dist Current Count Serving Beam 2",
    "LTE Secondary Serving Cell 1 RSRQ (dB)","PUSCH Average RBs per Allocated Slot Serving Beam 1",
    "LTE Neighbor Cell 1 RSRP","PUSCH RB Allocation Count Serving Beam 1",
    "LTE Neighbor Cell 1 RSRQ","PUSCH RB Allocation Usage Serving Beam 1 (%)",
    "LTE Serving Cell DL Pathloss Carrier 1 (dB)","PUSCH Slot Allocation Count Serving Beam 1",
    "LTE MAC DL Throughput (kbps)","PUSCH Slot Allocation TDD Serving Beam 1 (%)",
    "LTE MAC DL Throughput Carrier 1 (kbps)","PUSCH Slot Allocation Total Serving Beam 1 (%)",
    "LTE MAC DL Throughput Carrier 2 (kbps)","PUSCH Slot Utilization Serving Beam 1 (%)",
    "LTE MAC DL Throughput Carrier 3 (kbps)","PUSCH RB Dist Current Count Serving Beam 1",
    "LTE MAC DL Throughput Carrier 4 (kbps)","PUSCH RB Utillization Dist Current Count Serving Beam 1",
    "LTE MAC UL Throughput (kbps)","PUSCH Average RBs per Allocated Slot Serving Beam 2",
    "LTE MAC UL Throughput Carrier 1 (kbps)","PUSCH RB Allocation Count Serving Beam 2",
    "LTE MAC UL Throughput Carrier 2 (kbps)","PUSCH RB Allocation Usage Serving Beam 2 (%)",
    "LTE MAC UL Throughput Carrier 3 (kbps)","PUSCH Slot Allocation Count Serving Beam 2",
    "LTE MAC UL Throughput Carrier 4 (kbps)","PUSCH Slot Allocation TDD Serving Beam 2 (%)",
    "LTE PDSCH BLER (%)","PUSCH Slot Allocation Total Serving Beam 2 (%)",
    "LTE PDSCH Phy Throughput (kbps)","PUSCH Slot Utilization Serving Beam 2 (%)",
    "LTE PDSCH Phy Throughput Total (kbps)","PUSCH RB Dist Current Count Serving Beam 2",
    "LTE PDSCH Phy Throughput Carrier 1 (kbps)","PUSCH RB Utillization Dist Current Count Serving Beam 2",
    "LTE PDSCH Phy Throughput Carrier 2 (kbps)","Radio Common Throughput DL (kbps)",
    "LTE Bearer Maximum Bitrate DL (kbit/s)","LTE PDN Connection AMBR DL (kbps)"

]
for col in mean_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')


# === STEP 5: Define aggregation rules ===
def first_val(x): return x.dropna().iloc[0] if not x.dropna().empty else None
def last_val(x): return x.dropna().iloc[-1] if not x.dropna().empty else None
def modus(x): return x.mode().iloc[0] if not x.mode().empty else None

agg_rules = {
   "Date Time": first_val,
    "HTTP_Outcome": last_val,
    "HttpServiceStatus": last_val,
    "HttpLogfileName": last_val,
    "MCC": first_val,
    "MNC": first_val,
    "Country": first_val,
    "Type Mobility": first_val,
    "HttpStartMultiRATConnectivityMode": modus,
    "NR Serving Beam 1 Cell Identity": modus,
    "NR Serving Beam 1 NRARFCN DL": modus,
    "NR Serving Beam 1 Band": modus,
    "NR Serving Beam 1 Bandwidth DL": modus,
    "NR Serving Beam 1 Bandwidth UL": modus,
    "NR Serving Beam 1 SSB Index": "mean",
    "NR Serving Beam 1 Cell Type": modus,
    "NR Serving Beam 1 GSCN": modus,
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
    "Latitude": first_val,
    "Longitude": first_val,
    "Technology_Detail": modus,
    "DNS_Client": modus,
    "DNS_Domain_Name": modus,
    "DNS_Server_Address": modus,
    "DNS_Resolved_Address": first_val,
    "First DNS Request": modus,
    "DNS_First_In_Session": first_val,
    "DNS_Host_Name_Resolution_Failure_Ratio":"mean",
    "DNS_Host_Name_Resolution_Time_sec":"mean",
    "DNS_Host_Name_Total_Resolution_Time_sec":"mean",
    "DNS Resolution Success Ratio (%)":"mean",
    "TAC": modus,
    "HttpImsi": last_val,
    "HttpStartTime": first_val,
    "HttpStartLatitude": first_val,
    "HttpStartLongitude": first_val,
    "First_DNS_Request_to_HTTP_Get_First_Chunk_Downloaded_ms":"min",
    "HttpDataRadioBearer": modus,
    "HttpDataTransferCutoff":"sum",
    "HttpDataTransferTime":"sum",
    "HttpDirection": modus,
    "HttpErrorMessage": last_val,
    "HttpIPServiceAccessFailure": modus,
    "HttpIpServiceSetupTime":"mean",
    "HttpMeanDataRate":"mean",
    "HttpServiceStatus": modus,
    "HttpServiceBearer": modus,
    "HTTP_Download_Service_Average_Throughput":"mean",
    "HTTP_Download_Session_Failure_Ratio":"mean",
    "HTTP_Download_Session_Success_Ratio":"mean",
    "HTTP_Error_Cause": last_val,
    "HTTP_Technical_Browsing_Time_sec":"mean",
    "HTTP_User_Browsing_Time_sec":"mean",
    "Seconds_Start_to_End_HTTP":"sum",
    "HTTP_Download_Average_Throughput":"mean",
    "HTTP Data Transfer Cutoff Ratio (%)":"mean",
    "HTTP Download Throughput (kbps)":"mean",
    "HTTP_Download_Data_Transfer_Failure_Ratio_Method_A":"mean",
    "HTTP_Download_Data_Transfer_Success_Ratio_Method_A":"mean",
    "HTTP_Download_Data_Transfer_Time_sec_Method_A":"sum",
    "HTTP_Download_IP_Service_Access_Failure_Ratio_Method_A":"mean",
    "HTTP_Download_IP_Service_Setup_Success_Ratio_Method_A":"mean",
    "HTTP_Download_IP_Service_Setup_Time_sec_Method_A":"mean",
    "HTTP_Download_Mean_Data_Rate_kbps_Method_A":"mean",
    "HTTP_Download_Transfer_Start_Delay_Method_A":"min",
    "HTTP_Download_Data_Transfer_Failure_Ratio_Method_B":"mean",
    "HTTP_Download_Data_Transfer_Success_Ratio_Method_B":"mean",
    "HTTP_Download_Data_Transfer_Time_sec_Method_B":"sum",
    "HTTP_Download_IP_Service_Access_Failure_Ratio_Method_B":"mean",
    "HTTP_Download_IP_Service_Setup_Success_Ratio_Method_B":"mean",
    "HTTP_Download_IP_Service_Setup_Time_sec_Method_B":"mean",
    "HTTP_Download_Mean_Data_Rate_kbps_Method_B":"mean",
    "HTTP_Post_Outcome": modus,
    "Seconds_Start_to_End_HTTP_Post":"mean",
    "HTTP_Upload_Average_Throughput":"mean",
    "First_DNS_Request_to_HTTP_Post_First_Chunk_Uploaded_ms":"mean",
    "HTTP_Upload_Session_Failure_Ratio":"mean",
    "HTTP_Upload_Session_Success_Ratio":"mean",
    "HTTP_Upload_Data_Transfer_Failure_Ratio_Method_A":"mean",
    "HTTP_Upload_Data_Transfer_Success_Ratio_Method_A":"mean",
    "HTTP_Upload_Data_Transfer_Time_sec_Method_A":"mean",
    "HTTP_Upload_IP_Service_Access_Failure_Ratio_Method_A":"mean",
    "HTTP_Upload_IP_Service_Setup_Success_Ratio_Method_A":"mean",
    "HTTP_Upload_IP_Service_Setup_Time_sec_Method_A":"mean",
    "HTTP_Upload_Mean_Data_Rate_kbps_Method_A":"mean",
    "HTTP_Upload_Data_Transfer_Failure_Ratio_Method_B":"mean",
    "HTTP_Upload_Data_Transfer_Success_Ratio_Method_B":"mean",
    "HTTP_Upload_Data_Transfer_Time_sec_Method_B":"mean",
    "HTTP_Upload_IP_Service_Access_Failure_Ratio_Method_B":"mean",
    "HTTP_Upload_IP_Service_Setup_Success_Ratio_Method_B":"mean",
    "HTTP_Upload_IP_Service_Setup_Time_sec_Method_B":"mean",
    "HTTP_Upload_Mean_Data_Rate_kbps_Method_B":"mean",
    "HttpEndTime": last_val,
    "HttpEndMultiRATConnectivityMode": modus,
    "HttpEndLatitude": last_val,
    "HttpEndLongitude": last_val,
    "IP_Interruption_Time_ms":"sum",
    "TCP_Handshake_Time_sec":"mean",
    "TLSHandshakeFailureRatio (%)":"mean",
    "ThroughputCountOver1MBit":"sum",
    "ThroughputCountOver3MBit":"sum",
    "ThroughputPercentageOver3MBit":"mean",
    "IEBrowseDownloadTime(ms)":"mean",
    "IEBrowsePageSize(Bytes)":"sum",
    "LTE Cell Identity(eNB Part)": modus,
    "LTE Cell Identity(Cell Part)": modus,
    "LTE Serving Cell Identity": modus,
    "LTE Serving Cell DL EARFCN": modus,
    "LTE Serving Cell Frequency Band": modus,
    "LTE Serving Cell Channel RSSI(dBm)":"mean",
    "LTE Serving Cell RSRP(dBm)":"mean",
    "LTE Serving Cell RS SINR(dB)":"mean",
    "LTE Serving Cell RSRQ (dB)":"mean",
    "LTE_Serving_Cell_Count_Average":"mean",
    "LTE Secondary Serving Cell 1 Identity": modus,
    "LTE Secondary Serving Cell 1 DL EARFCN": modus,
    "LTE Secondary Serving Cell 1 Frequency Band": modus,
    "LTE Secondary Serving Cell 1 Channel RSSI (dBm)":"mean",
    "LTE Secondary Serving Cell 1 RSRP (dBm)":"mean",
    "LTE Secondary Serving Cell 1 RS SINR (dB)":"mean",
    "LTE Secondary Serving Cell 1 RSRQ (dB)":"mean",
    "LTE Neighbor Cell 1 PCI": modus,
    "LTE Neighbor Cell 1 DL EARFCN": modus,
    "LTE Neighbor Cell 1 RSRP":"mean",
    "LTE Neighbor Cell 1 RSRQ":"mean",
    "LTE Serving Cell DL Pathloss Carrier 1 (dB)":"mean",
    "LTE MAC DL Throughput (kbps)":"mean",
    "LTE MAC DL Throughput Carrier 1 (kbps)":"mean",
    "LTE MAC DL Throughput Carrier 2 (kbps)":"mean",
    "LTE MAC DL Throughput Carrier 3 (kbps)":"mean",
    "LTE MAC DL Throughput Carrier 4 (kbps)":"mean",
    "LTE MAC UL Throughput (kbps)":"mean",
    "LTE MAC UL Throughput Carrier 1 (kbps)":"mean",
    "LTE MAC UL Throughput Carrier 2 (kbps)":"mean",
    "LTE MAC UL Throughput Carrier 3 (kbps)":"mean",
    "LTE MAC UL Throughput Carrier 4 (kbps)":"mean",
    "LTE PDSCH Modulation": modus,
    "LTE PDSCH MCS": modus,
    "LTE PDSCH BLER (%)":"mean",
    "LTE PDSCH Phy Throughput (kbps)":"mean",
    "LTE PDSCH Phy Throughput Total (kbps)":"mean",
    "LTE PDSCH Phy Throughput Carrier 1 (kbps)":"mean",
    "LTE PDSCH Phy Throughput Carrier 2 (kbps)":"mean",
    "LTE PDSCH Phy Throughput Carrier 3 (kbps)":"mean",
    "LTE PDSCH Phy Throughput Carrier 4 (kbps)":"mean",
    "LTE PUSCH Modulation ": modus,
    "LTE PUSCH MCS ": modus,
    "PUSCH BLER (%)":"mean",
    "LTE PUSCH Phy Throughput (kbps)":"mean",
    "LTE PUSCH Phy Throughput Total (kbps)":"mean",
    "LTE PUSCH Phy Throughput Carrier 1 (kbps)":"mean",
    "LTE PUSCH Phy Throughput Carrier 2 (kbps)":"mean",
    "LTE PUSCH Phy Throughput Carrier 3 (kbps)":"mean",
    "PUSCH Phy Throughput Carrier 4 (kbps)":"mean",
    "LTE RLC Throughput DL (Kbps)":"mean",
    "LTE RLC Throughput UL (Kbps)":"mean",
    "NR Serving Beam 2 Cell Identity": modus,
    "NR Serving Beam 2 NRARFCN DL": modus,
    "NR Serving Beam 2 Band": modus,
    "NR Serving Beam 2 Bandwidth DL": modus ,
    "NR Serving Beam 2 Bandwidth UL": modus,
    "NR Serving Beam 2 SSB Index": modus,
    "NR Serving Beam 2 Cell Type": modus,
    "NR Serving Beam 2 GSCN": modus,
    "NR Neighbor Cell 1 SS SINR (dB)":"mean",
    "NR Neighbor Cell 1 SS RSRQ (dB)":"mean",
    "NR Neighbor Cell 1 Best Beam Index": modus,
    "NR Neighbor Cell 1 Cell Type": modus,
    "NR Phy Throughput Multi-RAT DL (kbps)":"mean",
    "NR Phy Throughput Multi-RAT UL (kbps)":"mean",
    "NR PDSCH Phy Throughput Total (Kbps)":"mean",
    "NR Pcell PDSCH Scheduled Throughput (Mbps)":"mean",
    "NR PDSCH Phy Throughput Serving Beam 1 (Kbps)":"mean",
    "NR PDSCH Modulation Serving Beam 1": modus,
    "NR PDSCH MCS Serving Beam 1": modus,
    "NR PDSCH BLER (%) Serving Beam 1":"mean",
    "NR PDSCH CQI Serving Beam 1":"mean",
    "NR PDSCH RI Serving Beam 1":"mean",
    "NR DL Pathloss Serving Beam 1":"mean",
    "NR PDSCH Phy Throughput Serving Beam 2 (Kbps)":"mean",
    "NR PDSCH Modulation Serving Beam 2": modus,
    "NR PDSCH MCS Serving Beam 2": modus,
    "NR PDSCH BLER (%) Serving Beam 2":"mean",
    "NR PDSCH CQI Serving Beam 2":"mean",
    "NR PDSCH RI Serving Beam 2":"mean",
    "NR DL Pathloss Serving Beam 2":"mean",
    "NR PUSCH Phy Throughput Total (kbps)":"mean",
    "NR Pcell PUSCH Scheduled Throughput (Mbps)":"mean",
    "NR PUSCH Phy Throughput Serving Beam 1 (Kbps)":"mean",
    "NR PUSCH Modulation Serving Beam 1": modus,
    "NR PUSCH MCS Serving Beam 1": modus,
    "NR PUSCH BLER (%) Serving Beam 1":"mean",
    "NR PUSCH Phy Throughput Serving Beam 2 (Kbps)":"mean",
    "NR PUSCH Modulation Serving Beam 2": modus,
    "NR PUSCH MCS Serving Beam 2": modus,
    "NR PUSCH BLER (%) Serving Beam 2":"mean",
    "NR MAC DL Throughput Total (kbps)":"sum",
    "NR MAC UL Throughput Total (kbps)":"sum",
    "NR RLC DL Throughput Total (kbps)":"sum",
    "NR RLC UL Throughput Total (kbps)":"sum",
    "NR RLC DL Throughput (Kbps)":"sum",
    "NR RLC UL Throughput (Kbps)":"sum",
    "NR BWP Center NR-ARFCN DL Serving Beam 1": modus,
    "NR BWP Bandwidth DL (Mhz) Serving Beam 1": modus,
    "NR BWP ID DL Serving Beam 1": modus,
    "NR BWP Initial Bandwidth DL Serving Beam 1 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 1": modus,
    "NR BWP Start Point NR-ARFCN DL Serving Beam 1": modus,
    "NR BWP Subcarrier Spacing DL Serving Beam 1": modus,
    "NR BWPs Configured Count DL serving Beam 1":"max",
    "NR BWP Center NR-ARFCN DL Serving Beam 2": modus,
    "NR BWP Bandwidth DL (Mhz) Serving Beam 2": modus,
    "NR BWP ID DL Serving Beam 2": modus,
    "NR BWP Initial Bandwidth DL Serving Beam 2 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 2": modus,
    "NR BWP Start Point NR-ARFCN DL Serving Beam 2": modus,
    "NR BWP Subcarrier Spacing DL Serving Beam 2": modus,
    "NR BWPs Configured Count DL serving Beam 2":"max",
    "NR BWP Center NR-ARFCN UL Serving Beam 1": modus,
    "NR BWP Bandwidth UL Serving Beam 1 (Mhz)": modus,
    "NR BWP ID UL Serving Beam 1": modus,
    "NR BWP Initial Bandwidth UL Serving Beam 1 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 1": modus,
    "NR BWP Start Point NR-ARFCN UL Serving Beam 1": modus,
    "NR BWP Subcarrier Spacing UL Serving Beam 1": modus,
    "NR BWPs Configured Count UL Serving Beam 1":"max",
    "NR BWP Center NR-ARFCN UL Serving Beam 2": modus,
    "NR BWP Bandwidth UL Serving Beam 2 (Mhz)": modus,
    "NR BWP ID UL Serving Beam 2": modus,
    "NR BWP Initial Bandwidth UL Serving Beam 2 (MHz)": modus,
    "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 2": modus,
    "NR BWP Start Point NR-ARFCN UL Serving Beam 2": modus,
    "NR BWP Subcarrier Spacing UL Serving Beam 2": modus,
    "NR BWPs Configured Count UL Serving Beam 2":"max",
    "RadioAccessTechnologyState": modus,
    "MR-DC Cell 1 SINR (dB)":"mean",
    "PDSCH Average RBs per Allocated Slot Serving Beam 1":"mean",
    "PDSCH Average RBs per Allocated Slot per TB Serving Beam 1":"mean",
    "PDSCH BWP ID Serving Beam 1": modus,
    "PDSCH RB Allocation Count Serving Beam 1":"sum",
    "PDSCH RB Allocation Count per TB Serving Beam 1":"sum",
    "PDSCH RB Allocation Usage Serving Beam 1 (%)":"mean",
    "PDSCH RBG Size Serving Beam 1": modus,
    "PDSCH Slot Allocation Count Serving Beam 1":"sum",
    "PDSCH Slot Allocation Count per TB Serving Beam 1":"sum",
    "PDSCH Slot Allocation TDD Serving Beam 1 (%)":"mean",
    "PDSCH Slot Allocation Total Serving Beam 1 (%)":"mean",
    "PDSCH Slot Utilization Serving Beam 1 (%)":"mean",
    "PDSCH RB Dist Current Count Serving Beam 1":"sum",
    "PDSCH RB Utillization Dist Current Count Serving Beam 1":"sum",
    "PDSCH Average RBs per Allocated Slot Serving Beam 2":"mean",
    "PDSCH Average RBs per Allocated Slot per TB Serving Beam 2":"mean",
    "PDSCH BWP ID Serving Beam 2": modus,
    "PDSCH RB Allocation Count Serving Beam 2":"sum",
    "PDSCH RB Allocation Count per TB Serving Beam 2":"sum",
    "PDSCH RB Allocation Usage Serving Beam 2 (%)":"mean",
    "PDSCH RBG Size Serving Beam 2": modus,
    "PDSCH Slot Allocation Count Serving Beam 2":"sum",
    "PDSCH Slot Allocation Count per TB Serving Beam 2":"sum",
    "PDSCH Slot Allocation TDD Serving Beam 2 (%)":"mean",
    "PDSCH Slot Allocation Total Serving Beam 2 (%)":"mean",
    "PDSCH Slot Utilization Serving Beam 2 (%)":"mean",
    "PDSCH RB Dist Current Count Serving Beam 2":"sum",
    "PDSCH RB Utillization Dist Current Count Serving Beam 2":"sum",
    "PUSCH Average RBs per Allocated Slot Serving Beam 1":"mean",
    "PUSCH BWP ID Serving Beam 1": modus,
    "PUSCH RB Allocation Count Serving Beam 1":"sum",
    "PUSCH RB Allocation Usage Serving Beam 1 (%)":"mean",
    "PUSCH RBG Size Serving Beam 1": modus,
    "PUSCH Slot Allocation Count Serving Beam 1":"sum",
    "PUSCH Slot Allocation TDD Serving Beam 1 (%)":"mean",
    "PUSCH Slot Allocation Total Serving Beam 1 (%)":"mean",
    "PUSCH Slot Utilization Serving Beam 1 (%)":"mean",
    "PUSCH RB Dist Current Count Serving Beam 1":"sum",
    "PUSCH RB Utillization Dist Current Count Serving Beam 1":"sum",
    "PUSCH Average RBs per Allocated Slot Serving Beam 2":"mean",
    "PUSCH BWP ID Serving Beam 2": modus,
    "PUSCH RB Allocation Count Serving Beam 2":"sum",
    "PUSCH RB Allocation Usage Serving Beam 2 (%)":"mean",
    "PUSCH RBG Size Serving Beam 2": modus,
    "PUSCH Slot Allocation Count Serving Beam 2":"sum",
    "PUSCH Slot Allocation TDD Serving Beam 2 (%)":"mean",
    "PUSCH Slot Allocation Total Serving Beam 2 (%)":"mean",
    "PUSCH Slot Utilization Serving Beam 2 (%)":"mean",
    "PUSCH RB Dist Current Count Serving Beam 2":"sum",
    "PUSCH RB Utillization Dist Current Count Serving Beam 2":"sum",
    "Radio Common Throughput DL (kbps)":"mean",
    "LTE Bearer Maximum Bitrate DL (kbit/s)":"mean",
    "LTE PDN Connection AMBR DL (kbps)":"mean",
    "FirmwareVersion": modus
}

# === STEP 6: Aggregate by HTTP_URL and Test Id ===
agg_df = df.groupby(['HTTP_URL', 'Test Id'], dropna=True).agg(agg_rules).reset_index()

# === STEP 12: Reorder columns before saving ===
desired_order = [
    "Date Time",
    "Test Id",
    "Test Name",
    "Type Mobility",
    "Operator",
    "Country",
    "Sequence",
    "Latitude",
    "Longitude",
    "MCC",
    "MNC",
    "Technology_Detail",
    "DNS_Client",
    "DNS_Domain_Name",
    "DNS_Server_Address",
    "DNS_Resolved_Address",
    "First DNS Request",
    "DNS_First_In_Session",
    "DNS_Host_Name_Resolution_Failure_Ratio",
    "DNS_Host_Name_Resolution_Time_sec",
    "DNS_Host_Name_Total_Resolution_Time_sec",
    "DNS Resolution Success Ratio (%)",
    "TAC",
    "HttpLogfileName",
    "HttpImsi",
    "HttpStartTime",
    "HttpStartLatitude",
    "HttpStartLongitude",
    "HttpStartMultiRATConnectivityMode",
    "First_DNS_Request_to_HTTP_Get_First_Chunk_Downloaded_ms",
    "HttpDataRadioBearer",
    "HttpDataTransferCutoff",
    "HttpDataTransferTime",
    "HttpDirection",
    "HttpErrorMessage",
    "HttpIPServiceAccessFailure",
    "HttpIpServiceSetupTime",
    "HttpMeanDataRate",
    "HttpServiceStatus",
    "HttpServiceBearer",
    "HTTP_Download_Service_Average_Throughput",
    "HTTP_Download_Session_Failure_Ratio",
    "HTTP_Download_Session_Success_Ratio",
    "HTTP_Error_Cause",
    "HTTP_Outcome",
    "HTTP_Technical_Browsing_Time_sec",
    "HTTP_URL",
    "HTTP_User_Browsing_Time_sec",
    "Seconds_Start_to_End_HTTP",
    "HTTP_Download_Average_Throughput",
    "HTTP Data Transfer Cutoff Ratio (%)",
    "HTTP Download Throughput (kbps)",
    "HTTP_Download_Data_Transfer_Failure_Ratio_Method_A",
    "HTTP_Download_Data_Transfer_Success_Ratio_Method_A",
    "HTTP_Download_Data_Transfer_Time_sec_Method_A",
    "HTTP_Download_IP_Service_Access_Failure_Ratio_Method_A",
    "HTTP_Download_IP_Service_Setup_Success_Ratio_Method_A",
    "HTTP_Download_IP_Service_Setup_Time_sec_Method_A",
    "HTTP_Download_Mean_Data_Rate_kbps_Method_A",
    "HTTP_Download_Transfer_Start_Delay_Method_A",
    "HTTP_Download_Data_Transfer_Failure_Ratio_Method_B",
    "HTTP_Download_Data_Transfer_Success_Ratio_Method_B",
    "HTTP_Download_Data_Transfer_Time_sec_Method_B",
    "HTTP_Download_IP_Service_Access_Failure_Ratio_Method_B",
    "HTTP_Download_IP_Service_Setup_Success_Ratio_Method_B",
    "HTTP_Download_IP_Service_Setup_Time_sec_Method_B",
    "HTTP_Download_Mean_Data_Rate_kbps_Method_B",
    "HTTP_Post_Outcome",
    "Seconds_Start_to_End_HTTP_Post",
    "HTTP_Upload_Average_Throughput",
    "First_DNS_Request_to_HTTP_Post_First_Chunk_Uploaded_ms",
    "HTTP_Upload_Session_Failure_Ratio",
    "HTTP_Upload_Session_Success_Ratio",
    "HTTP_Upload_Data_Transfer_Failure_Ratio_Method_A",
    "HTTP_Upload_Data_Transfer_Success_Ratio_Method_A",
    "HTTP_Upload_Data_Transfer_Time_sec_Method_A",
    "HTTP_Upload_IP_Service_Access_Failure_Ratio_Method_A",
    "HTTP_Upload_IP_Service_Setup_Success_Ratio_Method_A",
    "HTTP_Upload_IP_Service_Setup_Time_sec_Method_A",
    "HTTP_Upload_Mean_Data_Rate_kbps_Method_A",
    "HTTP_Upload_Data_Transfer_Failure_Ratio_Method_B",
    "HTTP_Upload_Data_Transfer_Success_Ratio_Method_B",
    "HTTP_Upload_Data_Transfer_Time_sec_Method_B",
    "HTTP_Upload_IP_Service_Access_Failure_Ratio_Method_B",
    "HTTP_Upload_IP_Service_Setup_Success_Ratio_Method_B",
    "HTTP_Upload_IP_Service_Setup_Time_sec_Method_B",
    "HTTP_Upload_Mean_Data_Rate_kbps_Method_B",
    "HttpEndTime",
    "HttpEndMultiRATConnectivityMode",
    "HttpEndLatitude",
    "HttpEndLongitude",
    "IP_Interruption_Time_ms",
    "TCP_Handshake_Time_sec",
    "TLSHandshakeFailureRatio (%)",
    "ThroughputCountOver1MBit",
    "ThroughputCountOver3MBit",
    "ThroughputPercentageOver3MBit",
    "IEBrowseDownloadTime(ms)",
    "IEBrowsePageSize(Bytes)",
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
    "Qualifier",
    "Time to Transfer 1000 kB",
    "Overall Session Time (s) DNS Request to first 1000kb"
    ]

# === STEP 7: Map MCC/MNC to Operator ===
try:
    mcc_mnc_df = pd.read_excel(mcc_mnc_map_path)
    mcc_mnc_df[['MCC', 'MNC']] = mcc_mnc_df[['MCC', 'MNC']].astype(int)
    agg_df[['MCC', 'MNC']] = agg_df[['MCC', 'MNC']].astype(int)
    agg_df = agg_df.merge(mcc_mnc_df[['MCC', 'MNC', 'Operator']], on=['MCC', 'MNC'], how='left')
    agg_df['Operator'] = agg_df['Operator'].fillna('Unknown')
except Exception as e:
    print(f"⚠️ Could not load operator mapping: {e}")

# === STEP 8: Map Test Case Name ===
try:
    test_case_df = pd.read_excel(test_case_map_path)
    if {'HTTP_URL', 'Test Name', 'Country'}.issubset(test_case_df.columns):
        agg_df = agg_df.merge(test_case_df[['HTTP_URL', 'Country', 'Test Name']], on=['HTTP_URL', 'Country'], how='left')
        agg_df['Test Name'] = agg_df['Test Name'].fillna('Not_found')
except Exception as e:
    print(f"⚠️ Could not load test name mapping: {e}")

# === STEP 9: Extract Sequence value for Austria only ===
agg_df['Sequence'] = agg_df.apply(
    lambda row: re.search(r"EQ1_Data_(TRP\d+_\d+)_MS\d+", str(row['HttpLogfileName'])).group(1)
    if row.get('Country') in ['Austria', 'Bremen'] and re.search(r"EQ1_Data_(TRP\d+_\d+)_MS\d+", str(row['HttpLogfileName'])) else None,
    axis=1
)


#Add Qualifier column based on Test Name ===
def check_qualifier(row):
    dns = row.get("DNS_Host_Name_Total_Resolution_Time_sec") or 0
    setup = row.get("HttpIpServiceSetupTime") or 0
    dl_tp = row.get("HTTP Download Throughput (kbps)")
    dl_avg = row.get("HTTP_Download_Average_Throughput")
    dl_dur = row.get("Seconds_Start_to_End_HTTP")
    ul_avg = row.get("HTTP_Upload_Average_Throughput")
    ul_dur = row.get("Seconds_Start_to_End_HTTP_Post")
    ip_intr = row.get("IP_Interruption_Time_ms")
    
    name = str(row.get("Test Case", "")).upper()

    if name == "HTTP BROWSING LIVE" or name == "HTTP BROSWING STATIC":
        if (dns + setup) > 10 or (dl_tp is None or dl_tp < 1000) or (dl_avg is not None and dl_avg < 1000):
            return "Not Qualified"
    elif name == "HTTP FDFS DL":
        if (dns + setup) > 10 or (dl_avg is None or dl_avg < 1000) or (dl_dur is not None and dl_dur > 80000):
            return "Not Qualified"
    elif name == "HTTP FDTT DL":
        if (dns + setup) > 10 or (dl_avg is not None and dl_avg < 1000) or (ip_intr is None or ip_intr > 2000):
            return "Not Qualified"
    elif name == "HTTP FDFS UL":
        if (dns + setup) > 10 or (ul_avg is None or ul_avg < 500) or (ul_dur is not None and ul_dur > 40):
            return "Not Qualified"
    elif name == "HTTP FDTT UL":
        if (dns + setup) > 10 or (ul_avg is not None and ul_avg < 500) or (ip_intr is None or ip_intr > 2000):
            return "Not Qualified"
    return "Qualified"

agg_df['Qualifier'] = agg_df.apply(check_qualifier, axis=1)

# Add calculated columns ===
agg_df['Time to Transfer 1000 kB'] = agg_df['HTTP Download Throughput (kbps)'].apply(
    lambda x: round(1000 / x, 3) if pd.notnull(x) and x > 0 else "N/A"
)

agg_df['Overall Session Time (s) DNS Request to first 1000kb'] = agg_df.apply(
    lambda row: round((row['DNS_Host_Name_Total_Resolution_Time_sec'] + row['Time to Transfer 1000 kB']), 3)
    if pd.api.types.is_number(row.get('DNS_Host_Name_Total_Resolution_Time_sec')) and
       pd.api.types.is_number(row.get('Time to Transfer 1000 kB'))
    else "N/A",
    axis=1
)





# === STEP 13: Only reorder if all columns are present ===
agg_df = agg_df[[col for col in desired_order if col in agg_df.columns]]


# === STEP 14: Export each Country to a separate Excel file in parallel ===
def export_country(country_group):
    country, group_df = country_group
    country_name = country.replace("/", "-").replace(" ", "_")
    output_file = os.path.join(output_path, f"HTTP_{country_name}_clean.xlsx")
    group_df.to_excel(output_file, index=False)
    print(f"✅ Saved: {output_file}")

agg_df = agg_df.sort_values(by='Date Time')
with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(export_country, agg_df.groupby('Country'))


