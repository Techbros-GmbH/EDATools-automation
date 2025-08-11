import pandas as pd
from pathlib import Path
from datetime import datetime


# === Load Excel ===
input_folder = Path("/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/DNS/Input")
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


# === Step 2: Rename columns globally
master_rename_map = {
    "Date Time": "Date",
    "Time": "Time",
    "Test_Name_2": "Test Name",
    "Type Mobility": "Type of Mobility",
    "Longitude": "Longitude",
    "Latitude" : "Latitude",
    "Operator": "Operator",
    "Country": "Route Name",
    "Sequence": "Sequence",
    "MNC": "MNC",
    "Technology_Detail": "Session Start Technology",
    "HttpDataRadioBearer": "Session Start Data Radio Bearer",
    "HTTP_URL": "HTTP URL",
    "DNS_Client": "DNS Client",
    "DNS_Domain_Name": "DNS Domain Name",
    "DNS_Server_Address": "DNS Server Address",
    "DNS_Resolved_Address": "DNS Resolved Address",
    "First DNS Request": "First DNS Request",
    "DNS_First_In_Session": "DNS First In Session",
    "DNS_Host_Name_Resolution_Failure_Ratio": "DNS Host Name Resolution Failure Ratio",
    "DNS_Host_Name_Resolution_Time_sec": "DNS Host Name Resolution Time (sec)",
    "DNS_Host_Name_Total_Resolution_Time_sec": "DNS Host Name Total Resolution Time (sec)",
    "DNS Resolution Success Ratio (%)": "DNS Resolution Success Ratio (%)",
    "TAC": "Session Start TAC",
    "HttpLogfileName": "Logfile Name",
    "HttpImsi": "IMSI",
    "HttpStartTime": "Session Start Time",
    "HttpStartLatitude": "Session Start Latitude",
    "HttpStartLongitude": "Session Start Longitude",
    "HttpStartMultiRATConnectivityMode": "Session Start MultiRAT",
    "First_DNS_Request_to_HTTP_Get_First_Chunk_Downloaded_ms": "First DNS Request to HTTP Get First Chunk Downloaded (ms)",
    "First_DNS_Request_to_HTTP_Post_First_Chunk_Uploaded_ms": "First DNS Request to HTTP Post First Chunk Uploaded (ms)",
    "Seconds_Start_to_End_HTTP": "Seconds Start to End HTTP",
    "HttpEndTime": "Session End Time",
    "HttpEndMultiRATConnectivityMode": "Session End MultiRAT",
    "HttpEndLatitude": "Session End Latitude",
    "HttpEndLongitude": "Session End Longitude",
    "FirmwareVersion": "FirmwareVersion"

    }
    
df.rename(columns=master_rename_map, inplace=True)



# === Step 3: Define schema groups
schema_groups = {
    "DNS1": [
        "Date",
        "Time",
        "Test Name",
        "Sequence",
        "Logfile Name",
        "Longitude",
        "Latitude",
        "Route Name",
        "Operator",
        "Type of Mobility",
        "Session Start Time",
        "Session Start Latitude",
        "Session Start Longitude",
        "Session Start Technology",
        "Session Start Data Radio Bearer",
        "Session Start MultiRAT",
        "Session Start TAC",
        "DNS Client",
        "DNS Domain Name",
        "DNS Server Address",
        "DNS Resolved Address",
        "First DNS Request",
        "DNS First In Session",
        "DNS Host Name Resolution Failure Ratio",
        "DNS Host Name Resolution Time (sec)",
        "DNS Host Name Total Resolution Time (sec)",
        "DNS Resolution Success Ratio (%)",
        "First DNS Request to HTTP Get First Chunk Downloaded (ms)",
        "First DNS Request to HTTP Post First Chunk Uploaded (ms)",
        "Seconds Start to End HTTP",
        "Session End Time",
        "Session End MultiRAT",
        "Session End Longitude",
        "HTTP URL",
        "FirmwareVersion"


   ]
}

# === Step 4: Map each test name to schema group
testname_to_group = {
    "DNS": "DNS1",
    
    
    
}



# === Function to generate Test_IDs column ===
def generate_test_ids(df):
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

    }

    operator_codes = {
        "Vodafone DE": 1,
        "Telefonica DE": 2,
        "Deutsche Telekom": 3
    }

    df = df.copy()
    df["Test_IDs"] = None

    for (test_name, operator), group in df.groupby(["Test Name", "Operator"]):
        test_code = test_name_codes.get(test_name, 0)
        operator_code = operator_codes.get(operator, 0)

        for i, idx in enumerate(group.index, start=1):
            seq = f"{i:04d}"
            df.at[idx, "Test_IDs"] = f"{test_code}{operator_code}{seq}"

    return df

df = generate_test_ids(df)



# === Step 5: Setup output & log
output_dir = Path("/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/DNS/Output2")
output_dir.mkdir(exist_ok=True)
log_path = output_dir / "log.txt"


# === Step 6: Loop and export (one sheet per test_name)
for test_name, test_group in df.groupby("Test Name"):
    group_key = testname_to_group.get(test_name)
    if not group_key:
        continue

    selected_columns = schema_groups[group_key] + ["Test_IDs"]
    
    # Force Test_IDs to 3rd position
    if "Test_IDs" in selected_columns:
        selected_columns.remove("Test_IDs")
        selected_columns.insert(2, "Test_IDs")
    
    # Filter columns
    filtered_group = test_group[selected_columns]

    # === Get info for filename
    first_row = test_group.iloc[0]
    raw_date = pd.to_datetime(first_row.get("Date", pd.NaT), errors='coerce')
    date_str = raw_date.strftime("%Y%m%d") if not pd.isna(raw_date) else "UnknownDate"
    country = str(first_row.get("Route Name", "UnknownCountry")).replace(" ", "_")
    safe_test_name = test_name.replace("/", "-").replace("\\", "-").replace(":", "-").replace(" ", "_")

    output_file_name = f"{date_str}_{country}_BM_CDRData_{safe_test_name}.xlsx"
    file_path = output_dir / output_file_name

    # === Save all rows to a single sheet
    with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
        filtered_group.to_excel(writer, sheet_name="AllData", index=False)

    # === Log
    msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Saved: {output_file_name} using schema: {group_key}"
    print(msg)
    with open(log_path, "a") as log_file:
        log_file.write(msg + "\n")

