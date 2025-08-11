import pandas as pd
import os
import re
from concurrent.futures import ThreadPoolExecutor

# === STEP 0: CONFIGURATION ===
input_folder = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/DNS/Input"
output_path = "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/DNS/Output"
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
    "DNS_Host_Name_Resolution_Failure_Ratio",
    "DNS_Host_Name_Resolution_Time_sec",
    "DNS_Host_Name_Total_Resolution_Time_sec",
    "DNS Resolution Success Ratio (%)",
    "First_DNS_Request_to_HTTP_Get_First_Chunk_Downloaded_ms",
    "First_DNS_Request_to_HTTP_Post_First_Chunk_Uploaded_ms"
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
    "First_DNS_Request_to_HTTP_Get_First_Chunk_Downloaded_ms":"mean",
    "First_DNS_Request_to_HTTP_Post_First_Chunk_Uploaded_ms": "mean",
    "HttpDataRadioBearer": modus,
    "HttpEndTime": last_val,
    "HttpEndMultiRATConnectivityMode": modus,
    "HttpEndLatitude": last_val,
    "HttpEndLongitude": last_val,
    "Seconds_Start_to_End_HTTP":"sum",
    "FirmwareVersion": modus
}

# === STEP 6: Aggregate by HTTP_URL and Test Id ===
agg_df = df.groupby(['HTTP_URL', 'Test Id'], dropna=True).agg(agg_rules).reset_index()




# === STEP 12: Reorder columns before saving ===
desired_order = [
    "Date Time",
    "Test Id",
    "Test_Name_1",
    "Test_Name_2",
    "Type Mobility",
    "Operator",
    "Country",
    "Sequence",
    "Latitude",
    "Longitude",
    "MCC",
    "MNC",
    "Technology_Detail",
    "HttpDataRadioBearer",
    "HTTP_URL",
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
    "First_DNS_Request_to_HTTP_Post_First_Chunk_Uploaded_ms",
    "Seconds_Start_to_End_HTTP",
    "HTTP_Outcome",
    "HttpEndTime",
    "HttpEndMultiRATConnectivityMode",
    "HttpEndLatitude",
    "HttpEndLongitude",
    "FirmwareVersion"
   
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
        agg_df.rename(columns={"Test Name": "Test_Name_1"}, inplace=True)
        agg_df["Test_Name_2"] = "DNS"
        
except Exception as e:
    print(f"⚠️ Could not load test name mapping: {e}")
    
if "Test_Name_1" not in agg_df.columns:
    agg_df["Test_Name_1"] = "Not_found"
if "Test_Name_2" not in agg_df.columns:
    agg_df["Test_Name_2"] = "DNS"

# === STEP 9: Extract Sequence value for Austria only ===
agg_df['Sequence'] = agg_df.apply(
    lambda row: re.search(r"EQ1_Data_(TRP\d+_\d+)_MS\d+", str(row['HttpLogfileName'])).group(1)
    if row.get('Country') in ['Austria', 'Bremen'] and re.search(r"EQ1_Data_(TRP\d+_\d+)_MS\d+", str(row['HttpLogfileName'])) else None,
    axis=1
)





# === STEP 13: Only reorder if all columns are present ===
agg_df = agg_df[[col for col in desired_order if col in agg_df.columns]]


# === STEP 14: Export each Country to a separate Excel file in parallel ===
def export_country(country_group):
    country, group_df = country_group
    country_name = country.replace("/", "-").replace(" ", "_")
    output_file = os.path.join(output_path, f"DNS_{country_name}_clean.xlsx")
    group_df.to_excel(output_file, index=False)
    print(f"✅ Saved: {output_file}")

agg_df = agg_df.sort_values(by='Date Time')
with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(export_country, agg_df.groupby('Country'))


