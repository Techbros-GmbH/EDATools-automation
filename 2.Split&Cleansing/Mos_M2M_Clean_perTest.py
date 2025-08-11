import pandas as pd
from pathlib import Path
from datetime import datetime


# === Load Excel ===
input_folder = Path("/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/MOS_M2M/Input")
all_files = list(input_folder.glob("*.xlsx"))

df_list = []

for file_path in all_files:
    xls = pd.ExcelFile(file_path)
    df_sheet = xls.parse(xls.sheet_names[0])
    df_sheet["SourceFile"] = file_path.stem  # Optional: keep track of where each row came from
    df_list.append(df_sheet)

# Combine all into one DataFrame
df = pd.concat(df_list, ignore_index=True)

date_split = df['Date Time'].astype(str).str.split(' ', expand=True)
date_split.columns = ['Date', 'Time']
df = pd.concat([df.drop(columns=['Date Time']), date_split], axis=1)

df = pd.concat([
    df,
    df[["Latitude"]].rename(columns={"Latitude": "End Latitude"})
], axis=1)

df = pd.concat([
    df,
    df[["Longitude"]].rename(columns={"Longitude": "End Longitude"})
], axis=1)

# Separate rows for Side A and Side B
side_a_df = df[df['Side'] == 'Side A'].reset_index(drop=True)
side_b_df = df[df['Side'] == 'Side B'].reset_index(drop=True)



# Merge Side A and Side B on 'Test Id' and 'index_id'
merged_df = pd.merge(
    side_a_df,
    side_b_df,
    on=['Test Id', 'index_id'],
    how='left',
    suffixes=('', '_B')
)

master_rename_map = {
    "VoiceStartTime": "VoiceStartTime A",
    "VoiceEndTime": "VoiceEndTime A",
    "Test Name": "Test Name",
    "Sequence": "Sequence A",
    "DeviceDescription": "DeviceDescription A",
    "Latitude": "Latitude",
    "Longitude": "Longitude",
    "Operator": "Operator",
    "Country": "Route Name",
    "Type Mobility": "Type of Mobility A",
    "VoiceLogfileName": "Logfile Name Side A",
    "EventName": "Event Name Side A",
    "IMEI": "IMEI Side A",
    "IMSI": "IMSI Side A",
    "MCC": "MCC",
    "MNC": "MNC",
    "Technology_Detail": "Technology Detail A",
    "PhoneNumber": "Phone Number A",
    "Dialed Number": "Dialed Number A",
    "Call_Status": "Call Status A",
    "Call_Type": "Call Type A",
    "Call_Number": "Call Number A",
    "Multi RAT Connectivity Mode": "Multi RAT Connectivity Mode A",
    "RadioAccessTechnologyState": "Radio Access Technology State A",
    "Is_Multi_RAB": "Is Multi RAB A",
    "AQM_RAT": "AQM RAT A",
    "AQM Algorithm DL": "AQM Algorithm DL A",
    "AQM Audio Channel Type DL": "AQM Audio Channel Type DL A",
    "AQM Score": "AQM Score A",
    "AQM Score DL": "AQM Score DL A",
    "MOS Calculator Version Downlink": "MOS Calculator Version Downlink A",
    "Speech Codec": "Speech Codec A",
    "AMR_Codec_DL": "AMR Codec DL A",
    "AMR_Codec_UL": "AMR Codec UL A",
    "AMR Codec Name DL Top #1": "AMR Codec Name DL Top #1 A",
    "AMR Codec Usage DL Top #1": "AMR Codec Usage DL Top #1 A",
    "AMR Codec Name UL Top #1": "AMR Codec Name UL Top #1 A",
    "AMR Codec Usage UL Top #1": "AMR Codec Usage UL Top #1 A",
    "SQ_MOS": "SQ MOS A",
    "MOS Calculator Version Downlink.1": "MOS Calculator Version Downlink A",
    "AMR_Codec_DL.1": "AMR Codec DL A",
    "AMR_Codec_UL.1": "AMR Codec UL A",
    "MultiRABServiceType1": "Multi RAB Service Type 1 A",
    "MultiRABServiceType2": "Multi RAB Service Type 2 A",
    "AQMDownlinkCallQuality": "AQM Downlink Call Quality A",
    "AverageAQMDownlinkCallQuality": "Average AQM Downlink Call Quality A",
    "POLQA SWB Score DL": "POLQA SWB Score DL A",
    "POLQA Speech Codec": "POLQA Speech Codec A",
    "RTP Jitter Audio RFC3550 (ms)": "RTP Jitter Audio RFC3550 (ms) A",
    "RTP Lost Packets Rate Audio (%)": "RTP Lost Packets Rate Audio (%) A",
    "RTP Relative Packet Delay Audio (ms)": "RTP Relative Packet Delay Audio (ms) A",
    "CodecUsed": "Codec Used A",
    "ConsecutivePacketsLost": "Consecutive Packets Lost A",
    "FERCombinedPacketLoss": "FER Combined Packet Loss A",
    "InterarrivalJitter": "Inter arrival Jitter A",
    "JitterBufferSizeIncrease": "Jitter Buffer Size Increase A",
    "JitterBufferUnderruns": "Jitter Buffer Under runs A",
    "MOSequenceNumberReceived": "MO Sequence Number Received A",
    "MOSequenceNumberSent": "MO Sequence Number Sent A",
    "NumberOfPacketsLost": "Number Of Packets Lost A",
    "PacketInterarrivalTime": "Packet Interarrival Time A",
    "PacketLossRatio": "Packet Loss Ratio A",
    "PayloadTypeAudio": "Payload Type Audio A",
    "RTPTimeGap": "RTP Time Gap A",
    "RadioAccessTechnologyState.1": "Radio Access Technology State A",
    "FirmwareVersion": "FirmwareVersion A",
    "Qualifier": "Qualifier (SQ MOS A)",
    "Date": "Date",
    "Time": "Time",
    "VoiceStartTime_B": "VoiceStartTime B",
    "VoiceEndTime_B": "VoiceEndTime B",
    "Test Name_B": "Test Name B",
    "Sequence_B": "Sequence B",
    "DeviceDescription_B": "DeviceDescription B",
    "Latitude_B": "Start Latitude B",
    "Longitude_B": "Start Longitude B",
    "Operator_B": "Operator B",
    "Country_B": "Route Name B",
    "Type Mobility_B": "Type of Mobility B",
    "VoiceLogfileName_B": "Logfile Name Side B",
    "EventName_B": "Event Name Side B",
    "IMEI_B": "IMEI Side B",
    "IMSI_B": "IMSI Side B",
    "MCC_B": "MCC B",
    "MNC_B": "MNC B",
    "Technology_Detail_B": "Technology Detail B",
    "PhoneNumber_B": "Phone Number B",
    "Dialed Number_B": "Dialed Number B",
    "Call_Status_B": "Call Status B",
    "Call_Type_B": "Call Type B",
    "Call_Number_B": "Call Number B",
    "Multi RAT Connectivity Mode_B": "Multi RAT Connectivity Mode B",
    "RadioAccessTechnologyState_B": "Radio Bccess Technology State B",
    "Is_Multi_RAB_B": "Is Multi RAB B",
    "AQM_RAT_B": "AQM RAT B",
    "AQM Algorithm DL_B": "AQM Blgorithm DL B",
    "AQM Audio Channel Type DL_B": "AQM Budio Channel Type DL B",
    "AQM Score_B": "AQM Score B",
    "AQM Score DL_B": "AQM Score DL B",
    "MOS Calculator Version Downlink_B": "MOS Calculator Version Downlink B",
    "Speech Codec_B": "Speech Codec B",
    "AMR_Codec_DL_B": "AMR Codec DL B",
    "AMR_Codec_UL_B": "AMR Codec UL B",
    "AMR Codec Name DL Top #1_B": "AMR Codec Name DL Top #1 B",
    "AMR Codec Usage DL Top #1_B": "AMR Codec Usage DL Top #1 B",
    "AMR Codec Name UL Top #1_B": "AMR Codec Name UL Top #1 B",
    "AMR Codec Usage UL Top #1_B": "AMR Codec Usage UL Top #1 B",
    "SQ_MOS_B": "SQ MOS B",
    "MOS Calculator Version Downlink.1_B": "MOS Calculator Version Downlink B",
    "AMR_Codec_DL.1_B": "AMR Codec DL B",
    "AMR_Codec_UL.1_B": "AMR Codec UL B",
    "MultiRABServiceType1_B": "Multi RAB Service Type 1 B",
    "MultiRABServiceType2_B": "Multi RAB Service Type 2 B",
    "AQMDownlinkCallQuality_B": "AQM Downlink Call Quality B",
    "AverageAQMDownlinkCallQuality_B": "Average BQM Downlink Call Quality B",
    "POLQA SWB Score DL_B": "POLQA SWB Score DL B",
    "POLQA Speech Codec_B": "POLQA Speech Codec B",
    "RTP Jitter Audio RFC3550 (ms)_B": "RTP Jitter Budio RFC3550 (ms) B",
    "RTP Lost Packets Rate Audio (%)_B": "RTP Lost Packets Rate Budio (%) B",
    "RTP Relative Packet Delay Audio (ms)_B": "RTP Relative Packet Delay Budio (ms) B",
    "CodecUsed_B": "Codec Used B",
    "ConsecutivePacketsLost_B": "Consecutive Packets Lost B",
    "FERCombinedPacketLoss_B": "FER Combined Packet Loss B",
    "InterarrivalJitter_B": "Inter Brrival Jitter B",
    "JitterBufferSizeIncrease_B": "Jitter Buffer Size Increase B",
    "JitterBufferUnderruns_B": "Jitter Buffer Under runs B",
    "MOSequenceNumberReceived_B": "MO Sequence Number Received B",
    "MOSequenceNumberSent_B": "MO Sequence Number Sent B",
    "NumberOfPacketsLost_B": "Number Of Packets Lost B",
    "PacketInterarrivalTime_B": "Packet Interarrival Time B",
    "PacketLossRatio_B": "Packet Loss Ratio B",
    "PayloadTypeAudio_B": "Payload Type Budio B",
    "RTPTimeGap_B": "RTP Time Gap B",
    "RadioAccessTechnologyState.1_B": "Radio Access Technology State B",
    "FirmwareVersion_B": "FirmwareVersion B",
    "Qualifier_B": "Qualifier (SQ MOS B)",
    "End Latitude": "End Latitude A",
    "End Longitude": "End Longitude A",
    "End Latitude_B": "End Latitude B",
    "End Longitude_B": "End Longitude B"


}
merged_df.rename(columns=master_rename_map, inplace=True)

def generate_test_ids(merged_df):
    test_name_codes = {
        "HTTP FDFS DL": 5,
        "HTTP FDFS UL": 6,
        "HTTP FDTT DL": 7,
        "HTTP FDTT UL": 8,
        "HTTP BROWSING LIVE": 9,
        "HTTP BROSWING STATIC": 10,
        "YoutubeVOD": 11,
        "YoutubeLIVE": 11,
        "Ping 800": 14,
        "Ping 40": 14,
        "DNS": 15,
        "Data_VideoChat": 13,
        "Data_EGaming": 12,
        "MOS_M2M": 1
    }

    operator_codes = {
        "Vodafone DE": 1,
        "Telefonica DE": 2,
        "Deutsche Telekom": 3
    }

    df = merged_df.copy()
    df["Test_IDs"] = None

    for (test_name, operator), group in df.groupby(["Test Name", "Operator"]):
        test_code = test_name_codes.get(test_name, 0)
        operator_code = operator_codes.get(operator, 0)
        for i, idx in enumerate(group.index, start=1):
            df.at[idx, "Test_IDs"] = f"{test_code}{operator_code}{i:04d}"

    # Reorder: Move Test_IDs to third column (after 'Time')
    first_cols = ['Date', 'Time', 'Test_IDs']
    remaining_cols = [col for col in df.columns if col not in first_cols]
    df = df[first_cols + remaining_cols]

    return df

# === Apply and reorder ===
merged_df = generate_test_ids(merged_df)


schema_groups = {
    "MOSM2M": [
        "Date",
        "Time",
        "Test_IDs",
        "Route Name",
        "Type of Mobility",
        "Test Name",
        "Operator",
        "MCC",
        "MNC",
        "Logfile Name Side A",
        "Sequence A",
        "Test ID A",
        "Technology Detail A",
        "DeviceDescription A",
        "Latitude",
        "End Latitude A",
        "Longitude",
        "End Longitude A",
        "IMEI Side A",
        "IMSI Side A",
        "Event Name Side A",
        "Phone Number A",
        "Dialed Number A",
        "Call Status A",
        "Call Type A",
        "Call Number A",
        "Multi RAT Connectivity Mode A",
        "Radio Access Technology State A",
        "Is Multi RAB A",
        "AQM RAT A",
        "AQM Algorithm DL A",
        "AQM Audio Channel Type DL A",
        "AQM Score A",
        "AQM Score DL A",
        "Speech Codec A",
        "AMR Codec DL A",
        "AMR Codec UL A",
        "AMR Codec Name DL Top #1 A",
        "AMR Codec Usage DL Top #1 A",
        "AMR Codec Name UL Top #1 A",
        "AMR Codec Usage UL Top #1 A",
        "SQ MOS A",
        "MOS Calculator Version Downlink A",
        "Multi RAB Service Type 1 A",
        "Multi RAB Service Type 2 A",
        "AQM Downlink Call Quality A",
        "Average AQM Downlink Call Quality A",
        "POLQA SWB Score DL A",
        "POLQA Speech Codec A",
        "RTP Jitter Audio RFC3550 (ms) A",
        "RTP Lost Packets Rate Audio (%) A",
        "RTP Relative Packet Delay Audio (ms) A",
        "Codec Used A",
        "Consecutive Packets Lost A",
        "FER Combined Packet Loss A",
        "Inter arrival Jitter A",
        "Jitter Buffer Size Increase A",
        "Jitter Buffer Under runs A",
        "MO Sequence Number Received A",
        "MO Sequence Number Sent A",
        "Number Of Packets Lost A",
        "Packet Interarrival Time A",
        "Packet Loss Ratio A",
        "Payload Type Audio A",
        "RTP Time Gap A",
        "FirmwareVersion A",
        "Logfile Name Side B",
        "Sequence B",
        "Test ID B",
        "Technology Detail B",
        "DeviceDescription B",
        "Start Latitude B",
        "End Latitude B",
        "Start Longitude B",
        "End Longitude B",
        "IMEI Side B",
        "IMSI Side B",
        "Event Name Side B",
        "Phone Number B",
        "Dialed Number B",
        "Call Status B",
        "Call Type B",
        "Call Number B",
        "Multi RAT Connectivity Mode B",
        "Radio Access Technology State B",
        "Is Multi RAB B",
        "AQM RAT B",
        "AQM Blgorithm DL B",
        "AQM Budio Channel Type DL B",
        "AQM Score B",
        "AQM Score DL B",
        "Speech Codec B",
        "AMR Codec DL B",
        "AMR Codec UL B",
        "AMR Codec Name DL Top #1 B",
        "AMR Codec Usage DL Top #1 B",
        "AMR Codec Name UL Top #1 B",
        "AMR Codec Usage UL Top #1 B",
        "SQ MOS B",
        "MOS Calculator Version Downlink B",
        "Multi RAB Service Type 1 B",
        "Multi RAB Service Type 2 B",
        "AQM Downlink Call Quality B",
        "Average BQM Downlink Call Quality B",
        "POLQA SWB Score DL B",
        "POLQA Speech Codec B",
        "RTP Jitter Budio RFC3550 (ms) B",
        "RTP Lost Packets Rate Budio (%) B",
        "RTP Relative Packet Delay Budio (ms) B",
        "Codec Used B",
        "Consecutive Packets Lost B",
        "FER Combined Packet Loss B",
        "Inter Brrival Jitter B",
        "Jitter Buffer Size Increase B",
        "Jitter Buffer Under runs B",
        "MO Sequence Number Received B",
        "MO Sequence Number Sent B",
        "Number Of Packets Lost B",
        "Packet Interarrival Time B",
        "Packet Loss Ratio B",
        "Payload Type Budio B",
        "RTP Time Gap B",
        "FirmwareVersion B",
        "Qualifier (SQ MOS A)",
        "Qualifier (SQ MOS B)"


   ]
}



def reorder_columns_strict(df, group_key="MOSM2M"):
    desired_columns = schema_groups.get(group_key, [])
    # Ambil hanya kolom yang benar-benar ada di dataframe
    selected_columns = [col for col in desired_columns if col in df.columns]
    return df[selected_columns]


merged_df = reorder_columns_strict(merged_df, group_key="MOSM2M")

merged_df = merged_df[
    merged_df["Qualifier (SQ MOS A)"].notna() & (merged_df["Qualifier (SQ MOS A)"].astype(str).str.strip() != "") &
    merged_df["Qualifier (SQ MOS B)"].notna() & (merged_df["Qualifier (SQ MOS B)"].astype(str).str.strip() != "")
]

# === Step 5: Setup output & log ===
output_dir = Path("/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/MOS_M2M/Output2")
output_dir.mkdir(exist_ok=True)
log_path = output_dir / "log.txt"

# === Step 6: Extract metadata for file naming ===
first_row = merged_df.iloc[0]
raw_date = pd.to_datetime(first_row.get("Date", pd.NaT), errors='coerce')
date_str = raw_date.strftime("%Y%m%d") if not pd.isna(raw_date) else "UnknownDate"
country = str(first_row.get("Route Name", "UnknownCountry")).replace(" ", "_")
output_file_name = f"{date_str}_{country}_BM_CDRMOS_M2M.xlsx"
output_file_path = output_dir / output_file_name

# === Step 7: Write to Excel with operator-based sheets ===
with pd.ExcelWriter(output_file_path, engine="openpyxl") as writer:
     merged_df.to_excel(writer, sheet_name="AllData", index=False)

# === Step 8: Logging ===
log_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Saved: {output_file_name} with all operators in Single sheets"
print(log_msg)
with open(log_path, "a") as log_file:
    log_file.write(log_msg + "\n")

