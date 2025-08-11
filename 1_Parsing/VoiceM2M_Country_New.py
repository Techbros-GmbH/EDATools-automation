import pandas as pd
import os
import re
from concurrent.futures import ThreadPoolExecutor

# === STEP 0: CONFIGURATION ===
input_folder = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Voice/M2M/Input"
output_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Voice/M2M/Output"
test_case_map_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/code/test case map.xlsx"
mcc_mnc_map_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/code/mncmcc_maping.xlsx"
os.makedirs(output_path, exist_ok=True)


# ===  Load all raw HTTP files in parallel and extract Country and Type Mobility from filename ===
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
        
        # Extract TestName
        df_part["Test Name"] = (
        parts[2][-5:] + "_" + parts[3]
        if len(parts) > 3 and parts[2].endswith("Voice")
        else "Unknown"
        )

        # === Extract IMSI and map to Side ===
        def extract_side(filename):
            match = re.search(r"IMSI[_\-]?\s*0*(\d+)", str(filename), flags=re.IGNORECASE)
            if match:
                number = match.group(1)
                return "Side A" if number == "1" else "Side B" if number == "2" else f"IMSI{number}"
            return None

        df_part["Side"] = extract_side(base_name)

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

file_list = [f for f in os.listdir(input_folder) if f.endswith(".xlsx") and "Voice_M2M" in f and "clean" not in f]
with ThreadPoolExecutor(max_workers=4) as executor:
    df_list = list(executor.map(load_file, file_list))
df_list = [df for df in df_list if df is not None]
if not df_list:
    raise ValueError("No VoiceM2M raw files loaded.")
df = pd.concat(df_list, ignore_index=True)


# === STEP 2: Segment sessions based on DeviceDescription and backfill VoiceLogfileName upward ===
df['VoiceLogfileName_filled'] = None
df['Test Id'] = None

for side_name, side_df in df.groupby('Side'):
    test_id_counter = 1
    for i in side_df.index:
        if pd.notnull(df.loc[i, 'VoiceLogfileName']):
            voicelog = df.loc[i, 'VoiceLogfileName']
            segment_rows = []
            j = i
            while j >= 0:
                if df.loc[j, 'Side'] != side_name:
                    break
                segment_rows.append(j)
                if pd.notnull(df.loc[j, 'DeviceDescription']):
                    break
                j -= 1
            else:
                continue  # Skip if DeviceDescription not found

            for idx in segment_rows:
                df.at[idx, 'VoiceLogfileName_filled'] = voicelog
                df.at[idx, 'Test Id'] = f"Test {test_id_counter}"

            test_id_counter += 1

# Ensure numeric types for mean-aggregated columns ===
mean_cols = [
    "MO_Call_Setup_Time_ms",
    "MO_Call_User_Setup_Time_ms",
    "MOCallDropRate",
    "MOCallSetupFailureRate",
    "MT_Call_Setup_Time_ms",
    "MT_Call_User_Setup_Time_ms",
    "MTCallDropRate",
    "MTCallSetupFailureRate",
    "Call_Duration",
    "Call_Setup_Duration",
    "Call_Setup_Time_sec",
    "Voice_Call_Setup_Time_sec",
    "Voice_Call_Success_Rate",
    "Voice_Call_Setup_Success_Rate",
    "Voice_Call_Setup_Failure_Rate",
    "Voice_Call_Completion_Rate",
    "Voice_Dropped_Call_Rate",
    "Voice_Speech_Quality_On_Call_Basis",
    "Call Drop Rate",
    "Call Dropped Count",
    "Call Dropped VoLTE Count",
    "Call Block Rate",
    "Call Blocked Count",
    "Call Blocked VoLTE Count",
    "Call Success Count",
    "Call Success Rate",
    "Call Success VoLTE Count",
    "CallInitiationDelay",
    "CallInitiationFailureRate",
    "CallInitiationSuccessRate",
    "AQM Score",
    "AQM Score DL",
    "SQ_MOS",
    "AQMDownlinkCallQuality",
    "AverageAQMDownlinkCallQuality",
    "POLQA SWB Score DL",
    "RTP Jitter Audio RFC3550 (ms)",
    "RTP Lost Packets Rate Audio (%)",
    "RTP Relative Packet Delay Audio (ms)",
    "ConsecutivePacketsLost",
    "FERCombinedPacketLoss",
    "InterarrivalJitter",
    "JitterBufferSizeIncrease",
    "JitterBufferUnderruns",
    "MOSequenceNumberReceived",
    "MOSequenceNumberSent",
    "NumberOfPacketsLost",
    "PacketInterarrivalTime",
    "PacketLossRatio",
    "RTPTimeGap",
    "Is CSFB Call Attempt",
    "MO CSFB Call Abnormal Release",
    "MO CSFB Call Attempt",
    "MO CSFB Call Dropped",
    "MO CSFB Call MS Release (Normal Cause)",
    "MO CSFB Call NW Release (Normal Cause)",
    "MO CSFB Call Setup Failure",
    "MO CSFB Call Setup Failure - No Alerting",
    "MO CSFB Call Setup Rejected",
    "MO CSFB Call Setup Success",
    "MT CSFB Call Abnormal Release",
    "MT CSFB Call Attempt",
    "MT CSFB Call Dropped",
    "MT CSFB Call MS Release (Normal Cause)",
    "MT CSFB Call NW Release (Normal Cause)",
    "MT CSFB Call Setup Failure",
    "MT CSFB Call Setup Rejected",
    "MT CSFB Call Setup Success",
    "LTE_MO_CSFB_Setup_Delay_ms",
    "LTE_MT_CSFB_Setup_Delay_ms",
    "LTE_PS_Data_Interrupt_Time_Due_to_CSFB_ms",
    "CSFB_Call_Setup_Time_sec",
    "MO_CSFB_Call_Setup_Time_ms",
    "MO_CSFB_Call_User_Setup_Time_ms",
    "MT_CSFB_Call_Setup_Time_ms",
    "Reselection_Time_After_CSFB_Call_Idle_to_LTE_ms",
    "Reselection_Time_After_CSFB_Call_SIB19_to_LTE",
    "Voice_CSFB_Setup_Failure_Rate",
    "Voice_CSFB_Setup_Success_Rate",
    "SRVCC_Handover_Interruption_Time_Control_Plane",
    "Reselection_Time_After_SRVCC_Call_Idle_to_LTE",
    "Reselection_Time_After_SRVCC_Call_SIB19_to_LTE",
    "SRVCC Handover",
    "SRVCC Handover (During On-going Call)",
    "SRVCC Handover (During Setup)",
    "SRVCC Handover Failure",
    "SRVCCHandoverInterruptionTimeUserPlane",
    "SRVCCUserPlaneDelay",
    "SRVCCUserPlaneInterruptionTime",
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
    "PUSCH BLER (%)",
    "LTE UE TX Power - PUSCH (dBm) Carrier 1",
    "LTE UE TX Power - PUCCH (dBm) Carrier 1",
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
    "NR Serving Beam 2 NRARFCN DL",
    "NR Serving Beam 2 Bandwidth DL",
    "NR Serving Beam 2 Bandwidth UL",
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
    "NR PUCCH Tx Power Serving Beam 1 (dBm) ",
    "NR PUSCH Tx Power Serving Beam 1 (dBm) ",
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
    "NR MAC UL Throughput Total (kbps)",
    "NR RLC DL Throughput Total (kbps)",
    "NR RLC UL Throughput Total (kbps)",
    "NR RLC UL Throughput (Kbps)"
    ]

for col in mean_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

# Aggregation functions ===
def first_val(x): return x.dropna().iloc[0] if not x.dropna().empty else None
def last_val(x): return x.dropna().iloc[-1] if not x.dropna().empty else None
def modus(x): return x.mode().iloc[0] if not x.mode().empty else None


# === STEP 7: Aggregation rules from Table Design ===
agg_rules = {
    "Date Time": first_val,
    "Test Name": first_val,
    "DeviceDescription": first_val,
    "Latitude": first_val,
    "Longitude": first_val,
    "Side": first_val,
    "Country": first_val,
    "Type Mobility": first_val,
    "EventName": modus,
    "IMEI": last_val,
    "IMSI": last_val,
    "MCC": first_val,
    "MNC": first_val,
    "TAC": modus,
    "Technology_Detail": modus,
    "PhoneNumber": first_val,
    "Dialed Number": modus,
    "Call_Status": modus,
    "Call_Type": modus,
    "Call_Number": modus,
    "MO_Call_Domain": modus,
    "MO_Call_Setup_Time_ms": "mean",
    "MO_Call_User_Setup_Time_ms": "mean",
    "MOCallDropRate": "mean",
    "MOCallSetupFailureRate": "mean",
    "MT_Call_Domain": modus,
    "MT_Call_Setup_Time_ms": "mean",
    "MT_Call_User_Setup_Time_ms": "mean",
    "MTCallDropRate": "mean",
    "MTCallSetupFailureRate": "mean",
    "Call_Duration": "sum",
    "Call_Setup_Duration": "mean",
    "Call_Setup_Time_sec": "mean",
    "Voice_Call_Setup_Time_sec": "mean",
    "Voice_Call_Success_Rate": "mean",
    "Voice_Call_Setup_Success_Rate": "mean",
    "Voice_Call_Setup_Failure_Rate": "mean",
    "Voice_Call_Completion_Rate": "mean",
    "Voice_Dropped_Call_Rate": "mean",
    "Voice_Speech_Quality_On_Call_Basis": "mean",
    "Call Drop Rate": "mean",
    "Call Dropped Count": "sum",
    "Call Dropped VoLTE Count": "sum",
    "Call Block Rate": "mean",
    "Call Blocked Count": "sum",
    "Call Blocked VoLTE Count": "sum",
    "Call Success Count": "sum",
    "Call Success Rate": "mean",
    "Call Success VoLTE Count": "sum",
    "Call Initiation": modus,
    "Call Attempt": modus,
    "Call Attempt Retry": modus,
    "Call Setup": modus,
    "Call Established": modus,
    "Call End": modus,
    "Call_End_Initiator": modus,
    "CallInitiationDelay": "mean",
    "CallInitiationFailureRate": "mean",
    "CallInitiationSuccessRate": "mean",
    "Data Radio Bearer": modus,
    "Multi RAT Connectivity Mode": modus,
    "RadioAccessTechnologyState": modus,
    "Is_Multi_RAB": modus,
    "AQM_RAT": modus,
    "AQM Algorithm DL": modus,
    "AQM Audio Channel Type DL": modus,
    "AQM Score": "mean",
    "AQM Score DL": "mean",
    "MOS Calculator Version Downlink": modus,
    "Speech Codec": modus,
    "AMR_Codec_DL": modus,
    "AMR_Codec_UL": modus,
    "AMR Codec Name DL Top #1": modus,
    "AMR Codec Usage DL Top #1": modus,
    "AMR Codec Name UL Top #1": modus,
    "AMR Codec Usage UL Top #1": modus,
    "SQ_MOS": "mean",
    "MOS Calculator Version Downlink": modus,
    "AMR_Codec_DL": modus,
    "AMR_Codec_UL": modus,
    "MultiRABServiceType1": last_val,
    "MultiRABServiceType2": last_val,
    "AQMDownlinkCallQuality": "mean",
    "AverageAQMDownlinkCallQuality": "mean",
    "POLQA SWB Score DL": "mean",
    "POLQA Speech Codec": modus,
    "RTP Jitter Audio RFC3550 (ms)": "mean",
    "RTP Lost Packets Rate Audio (%)": "mean",
    "RTP Relative Packet Delay Audio (ms)": "mean",
    "CodecUsed": modus,
    "ConsecutivePacketsLost": "sum",
    "FERCombinedPacketLoss": "mean",
    "InterarrivalJitter": "mean",
    "JitterBufferSizeIncrease": "sum",
    "JitterBufferUnderruns": "sum",
    "MOSequenceNumberReceived": "max",
    "MOSequenceNumberSent": "max",
    "NumberOfPacketsLost": "sum",
    "PacketInterarrivalTime": "mean",
    "PacketLossRatio": "mean",
    "PayloadTypeAudio": modus,
    "RTPTimeGap": "mean",
    "Is CSFB Call Attempt": "sum",
    "Call Attempt CSFB": last_val,
    "MO CSFB Call Abnormal Release": "sum",
    "MO CSFB Call Attempt": "sum",
    "MO CSFB Call Dropped": "sum",
    "MO CSFB Call MS Release (Normal Cause)": "sum",
    "MO CSFB Call NW Release (Normal Cause)": "sum",
    "MO CSFB Call On-Call @ EOF": modus,
    "MO CSFB Call Setup Failure": "mean",
    "MO CSFB Call Setup Failure - No Alerting": "mean",
    "MO CSFB Call Setup Rejected": "mean",
    "MO CSFB Call Setup Success": "mean",
    "MT CSFB Call Abnormal Release": "sum",
    "MT CSFB Call Attempt": "sum",
    "MT CSFB Call Dropped": "sum",
    "MT CSFB Call MS Release (Normal Cause)": "sum",
    "MT CSFB Call NW Release (Normal Cause)": "sum",
    "MT CSFB Call On-Call @ EOF": modus,
    "MT CSFB Call Setup Failure": "mean",
    "MT CSFB Call Setup Rejected": "mean",
    "MT CSFB Call Setup Success": "mean",
    "LTE_MO_CSFB_Setup_Delay_ms": "mean",
    "LTE_MT_CSFB_Setup_Delay_ms": "mean",
    "LTE_PS_Data_Interrupt_Time_Due_to_CSFB_ms": "max",
    "CSFB_Call_Setup_Time_sec": "mean",
    "MO_CSFB_Call_Setup_Time_ms": "mean",
    "MO_CSFB_Call_User_Setup_Time_ms": "mean",
    "MT_CSFB_Call_Setup_Time_ms": "mean",
    "Reselection_Time_After_CSFB_Call_Idle_to_LTE_ms": "mean",
    "Reselection_Time_After_CSFB_Call_SIB19_to_LTE": "mean",
    "Voice_CSFB_Setup_Failure_Rate": "mean",
    "Voice_CSFB_Setup_Success_Rate": "mean",
    "Call Attempt EPSFB": last_val,
    "Call Blocked EPSFB": last_val,
    "Call Established EPSFB": last_val,
    "Call Setup EPSFB": last_val,
    "SRVCC_Handover_Interruption_Time_Control_Plane": "max",
    "Reselection_Time_After_SRVCC_Call_Idle_to_LTE": "mean",
    "Reselection_Time_After_SRVCC_Call_SIB19_to_LTE": "mean",
    "SRVCC Handover": "sum",
    "SRVCC Handover (During On-going Call)": "sum",
    "SRVCC Handover (During Setup)": "sum",
    "SRVCC Handover Failure": "sum",
    "SRVCCHandoverInterruptionTimeUserPlane": "max",
    "SRVCCUserPlaneDelay": "mean",
    "SRVCCUserPlaneInterruptionTime": "max",
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
    "LTE PUSCH Modulation ": modus,
    "LTE PUSCH MCS ": modus,
    "PUSCH BLER (%)": "mean",
    "LTE UE TX Power - PUSCH (dBm) Carrier 1": "mean",
    "LTE UE TX Power - PUCCH (dBm) Carrier 1": "mean",
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
    "NR Serving Beam 2 Cell Identity": modus,
    "NR Serving Beam 2 NRARFCN DL": "mean",
    "NR Serving Beam 2 Band": modus,
    "NR Serving Beam 2 Bandwidth DL": "mean",
    "NR Serving Beam 2 Bandwidth UL": "mean",
    "NR Serving Beam 2 SSB Index": modus,
    "NR Serving Beam 2 Cell Type": modus,
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
    "NR PUCCH Tx Power Serving Beam 1 (dBm) ": "mean",
    "NR PUSCH Tx Power Serving Beam 1 (dBm) ": "mean",
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
    "NR MAC UL Throughput Total (kbps)": "sum",
    "NR RLC DL Throughput Total (kbps)": "sum",
    "NR RLC UL Throughput Total (kbps)": "sum",
    "NR RLC UL Throughput (Kbps)": "sum",
    "RadioAccessTechnologyState": modus,
    "FirmwareVersion": modus,
    "VoiceStartTime": last_val,
    "VoiceEndTime": last_val

  
    }

# Perform aggregation ===
agg_rules = {k: v for k, v in agg_rules.items() if k in df.columns}

# === Perform aggregation ===
agg_df = df.groupby(['VoiceLogfileName_filled', 'Test Id'], dropna=True).agg(agg_rules).reset_index()




# === STEP 7: Map MCC/MNC to Operator ===
try:
    mcc_mnc_df = pd.read_excel(mcc_mnc_map_path)
    mcc_mnc_df[['MCC', 'MNC']] = mcc_mnc_df[['MCC', 'MNC']].astype(int)
    agg_df[['MCC', 'MNC']] = agg_df[['MCC', 'MNC']].astype(int)
    agg_df = agg_df.merge(mcc_mnc_df[['MCC', 'MNC', 'Operator']], on=['MCC', 'MNC'], how='left')
    agg_df['Operator'] = agg_df['Operator'].fillna('Unknown')
   
except Exception as e:
    print(f"⚠️ Could not load operator mapping: {e}")



# === STEP 9: Extract Sequence value for Austria only ===
agg_df['Sequence'] = agg_df.apply(
    lambda row: re.search(r"(M2MVoice_\d+)", str(row['VoiceLogfileName_filled'])).group(1)
    if row.get('Country') in ['Austria', 'Bremen'] and re.search(r"(M2MVoice_\d+)", str(row['VoiceLogfileName_filled'])) else None,
    axis=1
)

agg_df = agg_df.sort_values(by=['Side', 'Date Time'])
# Function Qualifier

def apply_momt_qualification(df):
    df = df.copy()
    df["Side_Group_Index"] = df.groupby("Side").cumcount()
    df["Pair_ID"] = None
    df["Qualifier"] = None

    # Rename temp columns
    df["W"] = df["Call_Type"]
    df["V"] = df["Call_Status"]
    df["AK"] = pd.to_numeric(df["Call_Setup_Time_sec"], errors="coerce")
    df["AU"] = pd.to_numeric(df["Call Dropped VoLTE Count"], errors="coerce")
    df["CC"] = pd.to_numeric(df["SQ_MOS"], errors="coerce")

    pair_id = 1
    used_indexes = set()

    for i, row in df.iterrows():
        if i in used_indexes:
            continue

        current_side = row["Side"]
        current_operator = row["Operator"]
        #current_sequence = row["Sequence"]
        call_type = row["W"]

        # Define opposite side
        opposite_side = "Side B" if current_side == "Side A" else "Side A"

        # Find match based on:
        # - Opposite call type (MO ↔ MT)
        # - Same Sequence
        # - Same Operator
        # - Opposite Side
        if call_type == "MO":
            candidates = df[
                (df["W"] == "MT") &
                (df["Side"] == opposite_side) &
                (df["Operator"] == current_operator) &
               # (df["Sequence"] == current_sequence) &
                (~df.index.isin(used_indexes))
            ]
        elif call_type == "MT":
            candidates = df[
                (df["W"] == "MO") &
                (df["Side"] == opposite_side) &
                (df["Operator"] == current_operator) &
               # (df["Sequence"] == current_sequence) &
                (~df.index.isin(used_indexes))
            ]
        else:
            continue

        if not candidates.empty:
            match_idx = candidates.index[0]
            match_row = df.loc[match_idx]

            # Qualification
            def get_qual(r1, r2):
                return "Not Qualified" if (
                    pd.isna(r1["V"]) or r1["V"] == "Failed" or
                    pd.isna(r1["AK"]) or r1["AK"] > 15 or
                    pd.isna(r1["AU"]) or r1["AU"] == 1 or
                    pd.isna(r1["CC"]) or r1["CC"] < 2.7 or
                    (r1["CC"] < 1.3 and pd.notna(r2["CC"]) and r2["CC"] < 1.3)
                ) else "Qualified"

            qual_i = get_qual(row, match_row)
            qual_m = get_qual(match_row, row)

            df.at[i, "Qualifier"] = qual_i
            df.at[match_idx, "Qualifier"] = qual_m
            df.at[i, "Pair_ID"] = pair_id
            df.at[match_idx, "Pair_ID"] = pair_id
            used_indexes.update({i, match_idx})
            pair_id += 1
        else:
            df.at[i, "Qualifier"] = "Incomplete"

    # Clean up temp columns
    df.drop(columns=["W", "V", "AK", "AU", "CC"], inplace=True)
    return df


agg_df = apply_momt_qualification(agg_df)

# Reorder columns before saving ===
desired_order = [
    "Date Time",
    "VoiceStartTime",
    "VoiceEndTime",
    "Test Id",
    "Test Name",
    "Type Mobility",
    "Side",
    "Side_Group_Index",
    "Pair_ID",
    "DeviceDescription",
    "Operator",
    "Country",
    "Sequence",
    "Latitude",
    "Longitude",
    "VoiceLogfileName",
    "EventName",
    "IMEI",
    "IMSI",
    "MCC",
    "MNC",
    "TAC",
    "Technology_Detail",
    "PhoneNumber",
    "Dialed Number",
    "Call_Status",
    "Call_Type",
    "Call_Number",
    "MO_Call_Domain",
    "MO_Call_Setup_Time_ms",
    "MO_Call_User_Setup_Time_ms",
    "MOCallDropRate",
    "MOCallSetupFailureRate",
    "MT_Call_Domain",
    "MT_Call_Setup_Time_ms",
    "MT_Call_User_Setup_Time_ms",
    "MTCallDropRate",
    "MTCallSetupFailureRate",
    "Call_Duration",
    "Call_Setup_Duration",
    "Call_Setup_Time_sec",
    "Voice_Call_Setup_Time_sec",
    "Voice_Call_Success_Rate",
    "Voice_Call_Setup_Success_Rate",
    "Voice_Call_Setup_Failure_Rate",
    "Voice_Call_Completion_Rate",
    "Voice_Dropped_Call_Rate",
    "Voice_Speech_Quality_On_Call_Basis",
    "Call Drop Rate",
    "Call Dropped Count",
    "Call Dropped VoLTE Count",
    "Call Block Rate",
    "Call Blocked Count",
    "Call Blocked VoLTE Count",
    "Call Success Count",
    "Call Success Rate",
    "Call Success VoLTE Count",
    "Call Initiation",
    "Call Attempt",
    "Call Attempt Retry",
    "Call Setup",
    "Call Established",
    "Call End",
    "Call_End_Initiator",
    "CallInitiationDelay",
    "CallInitiationFailureRate",
    "CallInitiationSuccessRate",
    "Data Radio Bearer",
    "Multi RAT Connectivity Mode",
    "RadioAccessTechnologyState",
    "Is_Multi_RAB",
    "AQM_RAT",
    "AQM Algorithm DL",
    "AQM Audio Channel Type DL",
    "AQM Score",
    "AQM Score DL",
    "MOS Calculator Version Downlink",
    "Speech Codec",
    "AMR_Codec_DL",
    "AMR_Codec_UL",
    "AMR Codec Name DL Top #1",
    "AMR Codec Usage DL Top #1",
    "AMR Codec Name UL Top #1",
    "AMR Codec Usage UL Top #1",
    "SQ_MOS",
    "MOS Calculator Version Downlink",
    "AMR_Codec_DL",
    "AMR_Codec_UL",
    "MultiRABServiceType1",
    "MultiRABServiceType2",
    "AQMDownlinkCallQuality",
    "AverageAQMDownlinkCallQuality",
    "POLQA SWB Score DL",
    "POLQA Speech Codec",
    "RTP Jitter Audio RFC3550 (ms)",
    "RTP Lost Packets Rate Audio (%)",
    "RTP Relative Packet Delay Audio (ms)",
    "CodecUsed",
    "ConsecutivePacketsLost",
    "FERCombinedPacketLoss",
    "InterarrivalJitter",
    "JitterBufferSizeIncrease",
    "JitterBufferUnderruns",
    "MOSequenceNumberReceived",
    "MOSequenceNumberSent",
    "NumberOfPacketsLost",
    "PacketInterarrivalTime",
    "PacketLossRatio",
    "PayloadTypeAudio",
    "RTPTimeGap",
    "Is CSFB Call Attempt",
    "Call Attempt CSFB",
    "MO CSFB Call Abnormal Release",
    "MO CSFB Call Attempt",
    "MO CSFB Call Dropped",
    "MO CSFB Call MS Release (Normal Cause)",
    "MO CSFB Call NW Release (Normal Cause)",
    "MO CSFB Call On-Call @ EOF",
    "MO CSFB Call Setup Failure",
    "MO CSFB Call Setup Failure - No Alerting",
    "MO CSFB Call Setup Rejected",
    "MO CSFB Call Setup Success",
    "MT CSFB Call Abnormal Release",
    "MT CSFB Call Attempt",
    "MT CSFB Call Dropped",
    "MT CSFB Call MS Release (Normal Cause)",
    "MT CSFB Call NW Release (Normal Cause)",
    "MT CSFB Call On-Call @ EOF",
    "MT CSFB Call Setup Failure",
    "MT CSFB Call Setup Rejected",
    "MT CSFB Call Setup Success",
    "LTE_MO_CSFB_Setup_Delay_ms",
    "LTE_MT_CSFB_Setup_Delay_ms",
    "LTE_PS_Data_Interrupt_Time_Due_to_CSFB_ms",
    "CSFB_Call_Setup_Time_sec",
    "MO_CSFB_Call_Setup_Time_ms",
    "MO_CSFB_Call_User_Setup_Time_ms",
    "MT_CSFB_Call_Setup_Time_ms",
    "Reselection_Time_After_CSFB_Call_Idle_to_LTE_ms",
    "Reselection_Time_After_CSFB_Call_SIB19_to_LTE",
    "Voice_CSFB_Setup_Failure_Rate",
    "Voice_CSFB_Setup_Success_Rate",
    "Call Attempt EPSFB",
    "Call Blocked EPSFB",
    "Call Established EPSFB",
    "Call Setup EPSFB",
    "SRVCC_Handover_Interruption_Time_Control_Plane",
    "Reselection_Time_After_SRVCC_Call_Idle_to_LTE",
    "Reselection_Time_After_SRVCC_Call_SIB19_to_LTE",
    "SRVCC Handover",
    "SRVCC Handover (During On-going Call)",
    "SRVCC Handover (During Setup)",
    "SRVCC Handover Failure",
    "SRVCCHandoverInterruptionTimeUserPlane",
    "SRVCCUserPlaneDelay",
    "SRVCCUserPlaneInterruptionTime",
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
    "LTE PUSCH Modulation ",
    "LTE PUSCH MCS ",
    "PUSCH BLER (%)",
    "LTE UE TX Power - PUSCH (dBm) Carrier 1",
    "LTE UE TX Power - PUCCH (dBm) Carrier 1",
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
    "NR Serving Beam 2 Cell Identity",
    "NR Serving Beam 2 NRARFCN DL",
    "NR Serving Beam 2 Band",
    "NR Serving Beam 2 Bandwidth DL",
    "NR Serving Beam 2 Bandwidth UL",
    "NR Serving Beam 2 SSB Index",
    "NR Serving Beam 2 Cell Type",
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
    "NR PUCCH Tx Power Serving Beam 1 (dBm) ",
    "NR PUSCH Tx Power Serving Beam 1 (dBm) ",
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
    "NR MAC UL Throughput Total (kbps)",
    "NR RLC DL Throughput Total (kbps)",
    "NR RLC UL Throughput Total (kbps)",
    "NR RLC UL Throughput (Kbps)",
    "RadioAccessTechnologyState",
    "FirmwareVersion",
    "Qualifier"

  
    ]



agg_df.rename(columns={'VoiceLogfileName_filled': 'VoiceLogfileName'}, inplace=True)
# === STEP 13: Only reorder if all columns are present ===
agg_df = agg_df[[col for col in desired_order if col in agg_df.columns]]

agg_df = agg_df[agg_df["Qualifier"].isin(["Qualified", "Not Qualified"])]


# === STEP 14: Export each Country to a separate Excel file in parallel ===
def export_country(country_group):
    country, group_df = country_group
    country_name = country.replace("/", "-").replace(" ", "_")
    output_file = os.path.join(output_path, f"Voice_M2M_{country_name}_clean.xlsx")
    group_df.to_excel(output_file, index=False)
    print(f"✅ Saved: {output_file}")



# ✅ Check Country column exists before grouping
if 'Country' not in agg_df.columns:
    raise ValueError("❌ 'Country' column is missing before exporting.")
    
with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(export_country, agg_df.groupby('Country'))