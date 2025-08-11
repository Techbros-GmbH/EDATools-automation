import pandas as pd
import glob
import os

# === STEP 1: Define your folder path ===
folder_path = '/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Bremen Output/merge/Merge_clean/Data'  # change this
output_file = 'merged_output.xlsx'

# === STEP 2: Get all Excel files ===
excel_files = glob.glob(os.path.join(folder_path, "*.xlsx"))

# === STEP 3: Read and merge them ===
merged_df = pd.DataFrame()

for file in excel_files:
    try:
        df = pd.read_excel(file)

        # Normalize column names (optional, safer)
        df.columns = df.columns.str.strip()

        # Append with outer join to preserve all unique columns
        merged_df = pd.concat([merged_df, df], ignore_index=True, sort=False)
        print(f"✅ Merged: {file}")
    except Exception as e:
        print(f"⚠️ Failed to read {file}: {e}")

# === STEP 4: Save the result ===
merged_df.to_excel(output_file, index=False)
print(f"\n🎉 All files merged into: {output_file}")
