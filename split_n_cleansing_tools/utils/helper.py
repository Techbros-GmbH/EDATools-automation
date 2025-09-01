import re

import pandas as pd


def safe_read_first_sheet(file_obj) -> pd.DataFrame:
    xls = pd.ExcelFile(file_obj)
    return xls.parse(xls.sheet_names[0])


def split_datetime(df: pd.DataFrame) -> pd.DataFrame:
    if "Date Time" in df.columns and not {"Date", "Time"}.issubset(df.columns):
        parts = df["Date Time"].astype(str).str.split(" ", n=1, expand=True)
        if parts.shape[1] == 2:
            parts.columns = ["Date", "Time"]
            df = pd.concat([df.drop(columns=["Date Time"]), parts], axis=1)
    return df


def safe_columns(df: pd.DataFrame, wanted: list[str]) -> list[str]:
    return [c for c in wanted if c in df.columns]


def safe_name(s: object) -> str:
    return (
        re.sub(r'[/\\:*?"<>| ]+', "_", str(s).strip() if s is not None else "")
        or "Unknown"
    )


def date_yyyymmdd(val) -> str:
    ts = pd.to_datetime(val, errors="coerce")
    return ts.strftime("%Y%m%d") if pd.notna(ts) else "UnknownDate"


def rename_columns(df, dns_rename_map) -> pd.DataFrame:
    usable = {k: v for k, v in dns_rename_map.items() if k in df.columns}
    return df.rename(columns=usable)


def generate_test_ids(df, test_name_codes, operator_codes) -> pd.DataFrame:
    df = df.copy()
    df["Test_IDs"] = None
    if not {"Test Name", "Operator"}.issubset(df.columns):
        return df

    for (tname, oper), g in df.groupby(["Test Name", "Operator"], dropna=False):
        tcode = test_name_codes.get(str(tname), 0)
        ocode = operator_codes.get(str(oper), 0)
        for n, idx in enumerate(g.index, start=1):
            df.at[idx, "Test_IDs"] = f"{tcode}{ocode}{n:04d}"
    return df

def mos_generate_test_ids(df, test_name_codes, operator_codes) -> pd.DataFrame:
        df = df.copy()
        df["Test_IDs"] = None

        for (test_name, operator), group in df.groupby(["Test Name", "Operator"]):
            test_code = test_name_codes.get(test_name, 0)
            operator_code = operator_codes.get(operator, 0)
            for i, idx in enumerate(group.index, start=1):
                df.at[idx, "Test_IDs"] = f"{test_code}{operator_code}{i:04d}"

        first_cols = ['Date', 'Time', 'Test_IDs']
        remaining = [c for c in df.columns if c not in first_cols]
        return df[first_cols + remaining]

def reorder_columns_strict(df, schema_groups, schema_key) -> pd.DataFrame:

        cols = schema_groups.get(schema_key, [])
        return df[[c for c in cols if c in df.columns]]
