import pandas as pd
import os
import re
from concurrent.futures import ThreadPoolExecutor

# === STEP 0: CONFIGURATION ===
input_folder = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/MOS/OTT/Input"
output_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/MOS/OTT/Output"
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
        df_part["Operator1"] = parts[3] if len(parts) > 3 else "Unknown" 
        
        # Extract TestName
        df_part["Test Name"] = (
        f"{parts[2][-3:]}_{parts[3]}"
        if len(parts) > 3
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

file_list = [f for f in os.listdir(input_folder) if f.endswith(".xlsx") and "MOS_OTT" in f and "clean" not in f]
with ThreadPoolExecutor(max_workers=4) as executor:
    df_list = list(executor.map(load_file, file_list))
df_list = [df for df in df_list if df is not None]
if not df_list:
    raise ValueError("No MOSOTT raw files loaded.")
df = pd.concat(df_list, ignore_index=True)



# === STEP 2: Segment sessions based on DeviceDescription and backfill VoiceLogfileName upward ===
df['Test Id'] = None
df['VoiceLogfileName_filled'] = None


for (side_name, operator), group in df.groupby(['Side', 'Operator1']):
    test_id_counter = 1
    for i in group.index:
        if pd.notnull(df.loc[i, 'VoiceLogfileName']):
            voicelog = df.loc[i, 'VoiceLogfileName']
            segment_rows = []
            j = i
            while j >= 0:
                if df.loc[j, 'Side'] != side_name or df.loc[j, 'Operator1'] != operator:
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


# === STEP: Assign index_id where AQM Score is not null ===
df['index_id'] = None
for (test_id, side), group in df.groupby(['Test Id', 'Side']):
    valid_mask = group['AQM Score'].notnull()
    idx = group[valid_mask].index
    df.loc[idx, 'index_id'] = range(1, len(idx) + 1)

# === STEP: Backfill index_id to null AQM rows in the same Test Id ===
for (test_id, side), group in df.groupby(['Test Id', 'Side']):
    group_idx = group.index
    df.loc[group_idx, 'index_id'] = df.loc[group_idx, 'index_id'].bfill()

# === STEP: Forward fill other key columns within each Test Id ===
columns_to_fill = [
    "DeviceDescription",
    "EventName",
    "Speech Codec",
    "Call_Status",
    "Call_Type",
    "PhoneNumber",
    "Dialed Number",
    "Multi RAT Connectivity Mode",
    "CodecUsed",
    "ConsecutivePacketsLost",
]

for col in columns_to_fill:
    if col in df.columns:
        df[col] = df.groupby(['Test Id','VoiceLogfileName_filled'])[col].ffill()
        
#Backward fill for IMEI and IMSI within Test Id
for col in ["IMEI", "IMSI","AQMDownlinkCallQuality","AverageAQMDownlinkCallQuality","VoiceEndTime","VoiceStartTime"]:
    if col in df.columns:
        df[col] = df.groupby(['Test Id','VoiceLogfileName_filled'])[col].bfill()


# Ensure numeric types for mean-aggregated columns ===
mean_cols = [
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
    "Date Time": last_val,
    "Test Name": first_val,
    "DeviceDescription": first_val,
    "Latitude": first_val,
    "Longitude": first_val,
    "Side": first_val,
    "Country": first_val,
    "Type Mobility": last_val,
    "EventName": modus,
    "IMEI": last_val,
    "IMSI": last_val,
    "MCC": first_val,
    "MNC": first_val,
    "Technology_Detail": last_val,
    "PhoneNumber": first_val,
    "Dialed Number": last_val,
    "Call_Status": modus,
    "Call_Type": last_val,
    "Call_Number": modus,
    "Multi RAT Connectivity Mode": modus,
    "RadioAccessTechnologyState": modus,
    "Is_Multi_RAB": modus,
    "AQM_RAT": last_val,
    "AQM Algorithm DL": last_val,
    "AQM Audio Channel Type DL": last_val,
    "AQM Score": last_val,
    "AQM Score DL": last_val,
    "MOS Calculator Version Downlink": last_val,
    "Speech Codec": last_val,
    "AMR_Codec_DL": modus,
    "AMR_Codec_UL": modus,
    "AMR Codec Name DL Top #1": modus,
    "AMR Codec Usage DL Top #1": modus,
    "AMR Codec Name UL Top #1": modus,
    "AMR Codec Usage UL Top #1": modus,
    "SQ_MOS": last_val,
    "MOS Calculator Version Downlink": modus,
    "AMR_Codec_DL": modus,
    "AMR_Codec_UL": modus,
    "MultiRABServiceType1": last_val,
    "MultiRABServiceType2": last_val,
    "AQMDownlinkCallQuality": last_val,
    "AverageAQMDownlinkCallQuality": last_val,
    "POLQA SWB Score DL": last_val,
    "POLQA Speech Codec": last_val,
    "RTP Jitter Audio RFC3550 (ms)": "mean",
    "RTP Lost Packets Rate Audio (%)": "mean",
    "RTP Relative Packet Delay Audio (ms)": "mean",
    "CodecUsed": modus,
    "ConsecutivePacketsLost": last_val,
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
    "RadioAccessTechnologyState": modus,
    "FirmwareVersion": modus,
    "VoiceStartTime": last_val,
    "VoiceEndTime": last_val




  
    }

# Perform aggregation ===
agg_rules = {k: v for k, v in agg_rules.items() if k in df.columns}

# === Perform aggregation ===
agg_df = df.groupby(['VoiceLogfileName_filled', 'Test Id', 'index_id'], dropna=True).agg(agg_rules).reset_index()




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
    lambda row: re.search(r"(OTT_\d+)", str(row['VoiceLogfileName_filled'])).group(1)
    if row.get('Country') in ['Austria', 'Bremen'] and re.search(r"(OTT_\d+)", str(row['VoiceLogfileName_filled'])) else None,
    axis=1
)

agg_df = agg_df.sort_values(by=['Side', 'Date Time'])
# Function Qualifier

def evaluate_qualification(row):
    call_type = str(row.get("Call_Status", "")).strip()
    mos_version = row.get("SQ_MOS")

    # Handle missing/blank values
    if (
        call_type == "Failed" or
        call_type == "" or pd.isna(call_type) or
        pd.isna(mos_version) or
        (isinstance(mos_version, (float, int)) and mos_version < 1.3)
    ):
        return "Not Qualified"

    if (
        call_type == "Success" and
        isinstance(mos_version, (float, int)) and mos_version > 1.3
    ):
        return "Qualified"

    return "Not Qualified"



agg_df["Qualifier"] = agg_df.apply(evaluate_qualification, axis=1)


# Reorder columns before saving ===
desired_order = [
    "Date Time",
    "VoiceStartTime",
    "VoiceEndTime",
    "Test Id",
    "index_id",
    "Test Name",
    "Sequence",
    "DeviceDescription",
    "Latitude",
    "Longitude",
    "Operator",
    "Side",
    "Country",
    "Type Mobility",
    "VoiceLogfileName",
    "EventName",
    "IMEI",
    "IMSI",
    "MCC",
    "MNC",
    "Technology_Detail",
    "PhoneNumber",
    "Dialed Number",
    "Call_Status",
    "Call_Type",
    "Call_Number",
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
    "RadioAccessTechnologyState",
    "FirmwareVersion",
    "Qualifier"


  
    ]

agg_df.rename(columns={'VoiceLogfileName_filled': 'VoiceLogfileName'}, inplace=True)

# === STEP 13: Only reorder if all columns are present ===
agg_df = agg_df[[col for col in desired_order if col in agg_df.columns]]


# === STEP 14: Export each Country to a separate Excel file in parallel ===
def export_country(country_group):
    country, group_df = country_group
    country_name = country.replace("/", "-").replace(" ", "_")
    output_file = os.path.join(output_path, f"MOS_OTT_{country_name}_clean.xlsx")
    group_df.to_excel(output_file, index=False)
    print(f"✅ Saved: {output_file}")



# ✅ Check Country column exists before grouping
if 'Country' not in agg_df.columns:
    raise ValueError("❌ 'Country' column is missing before exporting.")
    
with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(export_country, agg_df.groupby('Country'))