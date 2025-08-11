import os

import numpy as np
import pandas as pd
from loguru import logger

# === KONFIGURASI PATH INPUT & OUTPUT ===

# TODO add Config from parent dir
input_folder = "/Users/daffaarifadilah/techbros/final_parsing/Result/Parsing"  # Folder tempat file .xlsx berada
output_folder = "/Users/daffaarifadilah/techbros/final_parsing/Result/KQI"  # Folder hasil output Excel

# === Buat folder output jika belum ada ===
os.makedirs(output_folder, exist_ok=True)

# === Nama File Input ===
ping_file = os.path.join(input_folder, "Ping_Bremen_clean.xlsx")
http_file = os.path.join(input_folder, "HTTP_Bremen_clean.xlsx")
streaming_file = os.path.join(input_folder, "Streaming_Bremen_clean.xlsx")
egaming_file = os.path.join(input_folder, "Data_EGaming_Bremen_clean.xlsx")
dns_file = os.path.join(input_folder, "DNS_Bremen_clean.xlsx")
videochat_file = os.path.join(input_folder, "Data_VideoChat_Bremen_clean.xlsx")
mos_m2m_file = os.path.join(input_folder, "MOS_M2M_Bremen_clean.xlsx")
mos_ott_file = os.path.join(input_folder, "MOS_OTT_Bremen_clean.xlsx")
voice_m2m_file = os.path.join(input_folder, "Voice_M2M_Bremen_clean.xlsx")
voice_ott_file = os.path.join(input_folder, "Voice_OTT_Bremen_clean.xlsx")
# === Nama File Output ===
output_file = os.path.join(output_folder, "All_KQI_Summary_final_v1.xlsx")

# === Baca File Excel ===
ping_df = pd.read_excel(ping_file)
http_df = pd.read_excel(http_file)
streaming_df = pd.read_excel(streaming_file)
egaming_df = pd.read_excel(egaming_file)
videochat_df = pd.read_excel(videochat_file)
dns_df = pd.read_excel(dns_file)
mos_m2m_df = pd.read_excel(mos_m2m_file)
mos_ott_df = pd.read_excel(mos_ott_file)
voice_m2m_df = pd.read_excel(voice_m2m_file)
voice_ott_df = pd.read_excel(voice_ott_file)

# === Daftar Teknologi ===
technology_keywords = [
    "GSM",
    "UMTS",
    "LTE",
    "EN-DC",
    "NR",
    "NR/UMTS",
    "GSM/NR",
    "NR/LTE",
    "NR/EN-DC",
    "LTE/EN-DC",
    "GSM/UMTS",
    "UMTS/LTE",
    "NR/LTE/EN-DC",
    "UMTS/NR/EN-DC",
    "UMTS/LTE/NR",
    "GSM/NR/EN-DC",
    "GSM/LTE/NR",
    "GSM/UMTS/NR",
    "UMTS/LTE/EN-DC",
    "GSM/LTE",
    "GSM/LTE/EN-DC",
    "GSM/UMTS/LTE",
    "NR/UMTS/LTE/EN-DC",
    "GSM/NR/LTE/EN-DC",
    "GSM/UMTS/NR/EN-DC",
    "GSM/UMTS/LTE/NR",
    "GSM/UMTS/LTE/EN-DC",
    "GSM/UMTS/LTE/EN-DC/NR",
]


# === Fungsi Ringkasan HTTP ===
def summarize_http_kpi(df):
    summary = []

    # === Kolom penting disederhanakan ===
    throughput_col = "HttpMeanDataRate"
    ulthroughput_col = "HTTP_Upload_Average_Throughput"
    status_col = "HttpServiceStatus"
    mobility_col = "Type Mobility"
    tech_col = "Technology_Detail"
    test_col = "Test Name"
    browsing_col = "HttpDataTransferTime"
    time = "HttpIpServiceSetupTime"
    # Bersihkan nama kolom dari spasi
    df.columns = df.columns.str.strip()

    for (operator, test_name, mobility), group in df.groupby(
        ["Operator", test_col, mobility_col]
    ):
        total = len(group)
        success = group[status_col].astype(str).eq("Succeeded").sum()
        failures = total - success
        success_ratio = round((success / total) * 100, 2) if total > 0 else 0

        row = {
            "Operator": operator,
            "Test Name": test_name,
            "Type Mobility": mobility,
            "Source": "HTTP",
            "Total": total,
            "Attempt": total,
            "Success": success,
            "Failures": failures,
            "Success Ratio [%]": success_ratio,
        }

        # === Hitung distribusi teknologi ===
        for tech in technology_keywords:
            row[tech] = group[tech_col].astype(str).str.contains(tech, na=False).sum()
            row[f"{tech} (%)"] = round(row[tech] / total, 4) if total > 0 else 0.0

        # === KALKULASI THROUGHPUT DL ===
        if test_name in ["HTTP FDFS DL", "HTTP FDTT DL", "HTTP FDTT UL"]:
            thp = group[throughput_col].dropna() / 1000  # konversi ke Mbps

            row["Average"] = round(thp.mean(), 2) if not thp.empty else None
            row["Median"] = round(thp.median(), 2) if not thp.empty else None
            row["P95"] = round(thp.quantile(0.95), 2) if not thp.empty else None
            row["Max"] = round(thp.max(), 2) if not thp.empty else None

            if test_name == "HTTP FDFS DL":
                row["Count > 1 Mbps"] = (thp > 1).sum()
                row["Count > 3 Mbps"] = (thp > 3).sum()

            elif test_name == "HTTP FDTT DL":
                row["Count > 100 Mbps"] = (thp > 100).sum()
                row["Count > 20 Mbps"] = (thp > 20).sum()

            elif test_name == "HTTP FDTT UL":
                row["Count > 5 Mbps"] = (thp > 5).sum()
                row["Count > 2 Mbps"] = (thp > 2).sum()

        # === KALKULASI THROUGHPUT UL (khusus FDFS UL) ===
        elif test_name == "HTTP FDFS UL":
            thp = group[ulthroughput_col].dropna() / 1000  # konversi ke Mbps

            row["Average"] = round(thp.mean(), 2) if not thp.empty else None
            row["Median"] = round(thp.median(), 2) if not thp.empty else None
            row["P95"] = round(thp.quantile(0.95), 2) if not thp.empty else None
            row["Max"] = round(thp.max(), 2) if not thp.empty else None
            row["Count > 1 Mbps"] = (thp > 1).sum()

        elif test_name in ["HTTP BROWSING LIVE", "HTTP BROSWING STATIC"]:
            # IP Service Setup Time
            setup_time = group[time].dropna()
            row["Average"] = (
                round(setup_time.mean(), 2) if not setup_time.empty else None
            )
            row["Median"] = (
                round(setup_time.median(), 2) if not setup_time.empty else None
            )
            row["P95"] = (
                round(setup_time.quantile(0.95), 2) if not setup_time.empty else None
            )
            row["Max"] = round(setup_time.max(), 2) if not setup_time.empty else None

            # Data Transfer Time
            data_rate = group[browsing_col].dropna()
            row["Avg Data Rate"] = (
                round(data_rate.mean(), 2) if not data_rate.empty else None
            )

        summary.append(row)

    return pd.DataFrame(summary)


# === Fungsi Ringkasan Streaming ===
def summarize_streaming_kpi(df):
    summary = []
    for (operator, test_name, mobility), group in df.groupby(
        ["Operator", "Test Name", "Type Mobility"]
    ):
        total = len(group)
        success = group["Streaming_Success_Rate"].astype(str).eq("100").sum()
        failures = total - success
        success_ratio = round((success / total) * 100, 2)
        row = {
            "Operator": operator,
            "Test Name": test_name,
            "Type Mobility": mobility,
            "Source": "Streaming",
            "Total": total,
            "Attempt": total,
            "Success": success,
            "Failures": failures,
            "Success Ratio [%]": success_ratio,
        }
        for tech in technology_keywords:
            row[tech] = (
                group["Technology_Detail"]
                .astype(str)
                .str.contains(tech, na=False)
                .sum()
            )
            row[f"{tech} (%)"] = round(row[tech] / total, 4)
        summary.append(row)
    return pd.DataFrame(summary)


# === Fungsi Ringkasan Ping ===
def summarize_ping_kpi(df):
    summary = []
    for (operator, test_name, mobility), group in df.groupby(
        ["Operator_New", "Test Name", "Type Mobility"]
    ):
        total = len(group)
        success = group["Ping_Packet_Success_Rate"].astype(str).eq("100").sum()
        failures = total - success
        success_ratio = round((success / total) * 100, 2) if total > 0 else 0
        trace_loss = (
            round(
                (group["Ping_Packet_Loss_Rate"].fillna(0).astype(float) > 0).sum()
                / total
                * 100,
                2,
            )
            if total > 0
            else 0
        )

        row = {
            "Operator": operator,
            "Test Name": test_name,
            "Type Mobility": mobility,
            "Source": "Ping",
            "Total Count": total,
            "Success": success,
            "Failures": failures,
            "Count Success Ratio [%]": success_ratio,
            "Trace Loss [%]": trace_loss,
        }

        for tech in technology_keywords:
            row[tech] = (
                group["Technology_Detail"]
                .astype(str)
                .str.contains(tech, na=False)
                .sum()
            )
            row[f"{tech} (%)"] = round(row[tech] / total, 4) if total > 0 else 0.0

        summary.append(row)
    return pd.DataFrame(summary)


# === Fungsi Ringkasan egaming ===
def summarize_egaming(df):
    summary = []
    for (operator, test_name, mobility), group in df.groupby(
        ["Operator", "Test Name", "Type Mobility"]
    ):
        attempt = group["TWAMP Operation Attempt"].count()
        success = group["TWAMP Operation Success"].count()
        status = "Success" if success > attempt else "Failed"

        latency = group["TWAMP_Latency_Score"].mean()
        packet_delay = group["TWAMP_Packet_Delay_Variation_Score"].mean()
        loss = group["TWAMP_Packet_Loss_Score"].mean()
        total = len(group)

        rttmin = group["TWAMP_Rtt_Min_ms"].min()
        rttavg = group["TWAMP_Rtt_Average_ms"].mean()
        rttMedian = group["TWAMP_Rtt_Median_ms"].median()
        rttmax = group["TWAMP_Rtt_Max_ms"].max()

        jitter_min = group["TWAMP_Jitter_Min_ms"].min()
        jitter_avg = group["TWAMP_Jitter_Average_ms"].mean()
        jitter_median = group["TWAMP_Jitter_Median_ms"].median()
        jitter_max = group["TWAMP_Jitter_Max_ms"].max()

        row = {
            "Operator": operator,
            "Test Name": test_name,
            "Type Mobility": mobility,
            "Source": "eGaming",
            "TWAMP Operation Attempt": attempt,
            "TWAMP Operation Success": success,
            "Operation Status": status,
            "Latency Score [Avg]": round(latency, 2) if pd.notna(latency) else None,
            "Packet Delay Variation Score [Avg]": round(packet_delay, 2)
            if pd.notna(packet_delay)
            else None,
            "Packet Loss Score [Avg]": round(loss, 2) if pd.notna(loss) else None,
            "Rtt Min (ms)": round(rttmin, 2) if pd.notna(rttmin) else None,
            "Rtt Average (ms)": round(rttavg, 2) if pd.notna(rttavg) else None,
            "Rtt Median (ms)": round(rttMedian, 2) if pd.notna(rttMedian) else None,
            "Rtt Max (ms)": round(rttmax, 2) if pd.notna(rttmax) else None,
            "Jitter Min (ms)": round(jitter_min, 2) if pd.notna(jitter_min) else None,
            "Jitter Average (ms)": round(jitter_avg, 2)
            if pd.notna(jitter_avg)
            else None,
            "Jitter Median (ms)": round(jitter_median, 2)
            if pd.notna(jitter_median)
            else None,
            "Jitter Max (ms)": round(jitter_max, 2) if pd.notna(jitter_max) else None,
        }

        for tech in technology_keywords:
            row[tech] = (
                group["Technology_Detail"]
                .astype(str)
                .str.contains(tech, na=False)
                .sum()
            )
            row[f"{tech} (%)"] = round(row[tech] / total, 4) if total > 0 else 0.0

        summary.append(row)

    return pd.DataFrame(summary)


def summarize_dns_kpis(df):
    """
    Calculates DNS KPIs and returns a DataFrame summary.

    Args:
        df (pd.DataFrame): The DNS data DataFrame

    Returns:
        pd.DataFrame: Summary of DNS KPIs
    """
    try:
        if df is None or df.empty:
            return pd.DataFrame()

        # Clean column names from spaces
        df.columns = df.columns.str.strip()

        # Define required columns
        required_columns = [
            "Test_Name_2",
            "DNS Resolution Success Ratio (%)",
            "DNS_Host_Name_Resolution_Failure_Ratio",
            "DNS_Host_Name_Total_Resolution_Time_sec",
        ]

        # Check for required columns
        for col in required_columns:
            if col not in df.columns:
                logger.warning(
                    f"Warning: Missing column '{col}'. Available columns: {list(df.columns)}"
                )
                return pd.DataFrame()

        # Convert relevant columns to numeric, coercing errors to NaN
        df["DNS Resolution Success Ratio (%)"] = pd.to_numeric(
            df["DNS Resolution Success Ratio (%)"], errors="coerce"
        )
        df["DNS_Host_Name_Resolution_Failure_Ratio"] = pd.to_numeric(
            df["DNS_Host_Name_Resolution_Failure_Ratio"], errors="coerce"
        )
        df["DNS_Host_Name_Total_Resolution_Time_sec"] = pd.to_numeric(
            df["DNS_Host_Name_Total_Resolution_Time_sec"], errors="coerce"
        )

        # Filter data for DNS tests
        dns_data = df[df["Test_Name_2"] == "DNS"].copy()

        if dns_data.empty:
            logger.warning("Warning: No DNS test data found in the dataset")
            return pd.DataFrame()

        summary = []

        # Check if required grouping columns exist
        grouping_cols = []
        if "Operator" in dns_data.columns:
            grouping_cols.append("Operator")
        else:
            dns_data["Operator"] = "Unknown"
            grouping_cols.append("Operator")

        if "Test Name" in dns_data.columns:
            grouping_cols.append("Test Name")
        elif "Test_Name_2" in dns_data.columns:
            dns_data["Test Name"] = dns_data["Test_Name_2"]
            grouping_cols.append("Test Name")
        else:
            dns_data["Test Name"] = "DNS"
            grouping_cols.append("Test Name")

        if "Type Mobility" in dns_data.columns:
            grouping_cols.append("Type Mobility")
        else:
            dns_data["Type Mobility"] = "Unknown"
            grouping_cols.append("Type Mobility")

        # Technology column
        tech_col = "Technology_Detail"
        if tech_col not in dns_data.columns:
            dns_data[tech_col] = "Unknown"

        print("Calculating DNS KPIs...")

        for group_key, group in dns_data.groupby(grouping_cols):
            operator, test_name, mobility = (
                group_key
                if len(grouping_cols) == 3
                else (group_key[0], "DNS", "Unknown")
            )

            total = len(group)
            attempt_count = total

            # Calculate DNS success ratio
            dns_success_ratio = group["DNS Resolution Success Ratio (%)"].mean()
            dns_success_ratio = (
                round(dns_success_ratio, 2) if pd.notna(dns_success_ratio) else 0
            )

            # Calculate DNS failure ratio
            dns_failure_ratio = group["DNS_Host_Name_Resolution_Failure_Ratio"].mean()
            dns_failure_ratio = (
                round(dns_failure_ratio, 4) if pd.notna(dns_failure_ratio) else 0
            )

            # Count > 0.5s calculations
            valid_resolution_times = group[
                "DNS_Host_Name_Total_Resolution_Time_sec"
            ].dropna()
            count_above_0_5s = (valid_resolution_times > 0.5).sum()
            count_above_0_5s_percentage = (
                round((count_above_0_5s / attempt_count * 100), 2)
                if attempt_count > 0
                else 0
            )

            # Resolution time statistics
            min_resolution_time = (
                round(valid_resolution_times.min(), 3)
                if not valid_resolution_times.empty
                else None
            )
            avg_resolution_time = (
                round(valid_resolution_times.mean(), 3)
                if not valid_resolution_times.empty
                else None
            )
            max_resolution_time = (
                round(valid_resolution_times.max(), 3)
                if not valid_resolution_times.empty
                else None
            )

            # Create row dictionary
            row = {
                "Operator": operator,
                "Test Name": test_name,
                "Type Mobility": mobility,
                # 'Success': ,
                "Source": "DNS",
                "Total": total,
                "Attempt": attempt_count,
                "Success Ratio [%]": dns_success_ratio,
                "DNS Host Name Resolution Failure Ratio": dns_failure_ratio,
                "Count > 0.5s [#]": count_above_0_5s,
                "Count > 0.5s [%]": count_above_0_5s_percentage,
                "Min DNS Resolution Time (sec)": min_resolution_time,
                "Average DNS Resolution Time (sec)": avg_resolution_time,
                "Max DNS Resolution Time (sec)": max_resolution_time,
            }

            # Add technology distribution
            for tech in technology_keywords:
                tech_count = (
                    group[tech_col].astype(str).str.contains(tech, na=False).sum()
                )
                row[tech] = tech_count
                row[f"{tech} (%)"] = round(tech_count / total, 4) if total > 0 else 0.0

            summary.append(row)

        return pd.DataFrame(summary)

    except Exception as e:
        logger.warning(f"Error in summarize_dns_kpis: {e}")
        return pd.DataFrame()


def summarize_videochat_kqi(df):
    """
    Creates KQI summary for VideoChat test cases based on TWAMP measurements.

    Args:
        df (pd.DataFrame): The VideoChat data DataFrame

    Returns:
        pd.DataFrame: Summary of VideoChat KQIs
    """
    try:
        if df is None or df.empty:
            return pd.DataFrame()

        # Clean column names from spaces
        df.columns = df.columns.str.strip()

        required_columns = [
            "Test Name",
            "TWAMP Operation Attempt",
            "TWAMP Operation Success",
            "Logfile Name",
            "TWAMP_Latency_Score",
            "TWAMP Packet Delay Variation Score",
            "TWAMP Packet Loss Score",
            "TWAMP_Rtt_Min_ms",
            "TWAMP_Rtt_Average_ms",
            "TWAMP_Rtt_Median_ms",
            "TWAMP_Rtt_Max_ms",
            "TWAMP_Jitter_Min_ms",
            "TWAMP_Jitter_Average_ms",
            "TWAMP_Jitter_Median_ms",
            "TWAMP_Jitter_Max_ms",
        ]

        # Check for missing columns and provide alternatives
        column_mapping = {
            "TWAMP_Latency_Score": ["TWAMP_Latency_Score", "Latency Score", "AR"],
            "TWAMP Packet Delay Variation Score": [
                "TWAMP Packet Delay Variation Score",
                "TWAMP_Packet_Delay_Variation_Score",
                "AD",
            ],
            "TWAMP Packet Loss Score": [
                "TWAMP Packet Loss Score",
                "TWAMP_Packet_Loss_Score",
                "AU",
            ],
            "TWAMP_Rtt_Min_ms": ["TWAMP_Rtt_Min_ms", "BL", "Rtt Min"],
            "TWAMP_Rtt_Average_ms": ["TWAMP_Rtt_Average_ms", "Rtt Average"],
            "TWAMP_Rtt_Median_ms": ["TWAMP_Rtt_Median_ms", "Rtt Median"],
            "TWAMP_Rtt_Max_ms": ["TWAMP_Rtt_Max_ms", "Rtt Max"],
            "TWAMP_Jitter_Min_ms": ["TWAMP_Jitter_Min_ms", "Jitter Min"],
            "TWAMP_Jitter_Average_ms": ["TWAMP_Jitter_Average_ms", "Jitter Average"],
            "TWAMP_Jitter_Median_ms": ["TWAMP_Jitter_Median_ms", "Jitter Median"],
            "TWAMP_Jitter_Max_ms": ["TWAMP_Jitter_Max_ms", "Jitter Max"],
        }

        # Find the correct column names
        actual_columns = {}
        for standard_name, alternatives in column_mapping.items():
            found = False
            for alt in alternatives:
                if alt in df.columns:
                    actual_columns[standard_name] = alt
                    found = True
                    break
            if not found:
                logger.warning(f"Warning: Could not find column for {standard_name}")

        # Filter data for VideoChat tests
        videochat_data = df[df["Test Name"] == "Data_VideoChat"].copy()

        if videochat_data.empty:
            logger.warning("Warning: No VideoChat test data found in the dataset")
            return pd.DataFrame()

        summary = []

        # Check if required grouping columns exist
        grouping_cols = []
        if "Operator" in videochat_data.columns:
            grouping_cols.append("Operator")
        else:
            videochat_data["Operator"] = "Unknown"
            grouping_cols.append("Operator")

        # Add Test Name to grouping
        grouping_cols.append("Test Name")

        if "Type Mobility" in videochat_data.columns:
            grouping_cols.append("Type Mobility")
        else:
            videochat_data["Type Mobility"] = "Unknown"
            grouping_cols.append("Type Mobility")

        # Technology column for distribution
        tech_col = "Technology_Detail"
        if tech_col not in videochat_data.columns:
            videochat_data[tech_col] = "Unknown"

        logger.info("Calculating VideoChat KQIs...")

        for group_key, group in videochat_data.groupby(grouping_cols):
            if len(grouping_cols) == 3:
                operator, test_name, mobility = group_key
            else:
                operator = group_key[0] if len(grouping_cols) >= 1 else "Unknown"
                test_name = "VideoChat"
                mobility = "Unknown"

            # Operation Attempt Count - Count rows with "TWAMP Operation Attempt"
            attempt_count = group["TWAMP Operation Attempt"].notna().sum()

            # Operation Success Count - Count rows with "TWAMP Operation Success"
            success_count = group["TWAMP Operation Success"].notna().sum()

            # Operation Status - Success if success_count >= logfile_count
            logfile_count = group["Logfile Name"].notna().sum()
            operation_status = "Success" if success_count >= logfile_count else "Failed"

            # Qualified Session - Count "Qualified" entries (assuming there's a qualification column)
            qualified_session = 0
            if "Qualified" in group.columns:
                qualified_session = (group["Qualified"] == "Qualified").sum()
            else:
                qualified_session = success_count  # Fallback assumption

            # Latency Score [Avg]
            latency_col = actual_columns.get(
                "TWAMP_Latency_Score", "TWAMP_Latency_Score"
            )
            latency_score = (
                group[latency_col].mean() if latency_col in group.columns else None
            )

            # Packet Delay Variation Score [Avg]
            delay_var_col = actual_columns.get(
                "TWAMP Packet Delay Variation Score",
                "TWAMP Packet Delay Variation Score",
            )
            packet_delay_score = (
                group[delay_var_col].mean() if delay_var_col in group.columns else None
            )

            # Packet Loss Score [Avg]
            loss_col = actual_columns.get(
                "TWAMP Packet Loss Score", "TWAMP Packet Loss Score"
            )
            packet_loss_score = (
                group[loss_col].mean() if loss_col in group.columns else None
            )

            # TWAMP RTT Statistics
            rtt_min_col = actual_columns.get("TWAMP_Rtt_Min_ms", "TWAMP_Rtt_Min_ms")
            rtt_avg_col = actual_columns.get(
                "TWAMP_Rtt_Average_ms", "TWAMP_Rtt_Average_ms"
            )
            rtt_median_col = actual_columns.get(
                "TWAMP_Rtt_Median_ms", "TWAMP_Rtt_Median_ms"
            )
            rtt_max_col = actual_columns.get("TWAMP_Rtt_Max_ms", "TWAMP_Rtt_Max_ms")

            rtt_min = group[rtt_min_col].min() if rtt_min_col in group.columns else None
            rtt_avg = (
                group[rtt_avg_col].mean() if rtt_avg_col in group.columns else None
            )
            rtt_median = (
                group[rtt_median_col].median()
                if rtt_median_col in group.columns
                else None
            )
            rtt_max = group[rtt_max_col].max() if rtt_max_col in group.columns else None

            # TWAMP Jitter Statistics
            jitter_min_col = actual_columns.get(
                "TWAMP_Jitter_Min_ms", "TWAMP_Jitter_Min_ms"
            )
            jitter_avg_col = actual_columns.get(
                "TWAMP_Jitter_Average_ms", "TWAMP_Jitter_Average_ms"
            )
            jitter_median_col = actual_columns.get(
                "TWAMP_Jitter_Median_ms", "TWAMP_Jitter_Median_ms"
            )
            jitter_max_col = actual_columns.get(
                "TWAMP_Jitter_Max_ms", "TWAMP_Jitter_Max_ms"
            )

            jitter_min = (
                group[jitter_min_col].min() if jitter_min_col in group.columns else None
            )
            jitter_avg = (
                group[jitter_avg_col].mean()
                if jitter_avg_col in group.columns
                else None
            )
            jitter_median = (
                group[jitter_median_col].median()
                if jitter_median_col in group.columns
                else None
            )
            jitter_max = (
                group[jitter_max_col].max() if jitter_max_col in group.columns else None
            )

            row = {
                "Operator": operator,
                "Test Name": test_name,
                "Type Mobility": mobility,
                "Source": "VideoChat",
                "TWAMP Operation Attempt": attempt_count,
                "TWAMP Operation Success": success_count,
                "Operation Status": operation_status,
                "Qualified Session": qualified_session,
                "Latency Score [Avg]": round(latency_score, 2)
                if pd.notna(latency_score)
                else "N/A",
                "Packet Delay Variation Score [Avg]": round(packet_delay_score, 2)
                if pd.notna(packet_delay_score)
                else "N/A",
                "Packet Loss Score [Avg]": round(packet_loss_score, 2)
                if pd.notna(packet_loss_score)
                else "N/A",
                "Rtt Min (ms)": round(rtt_min, 2) if pd.notna(rtt_min) else "N/A",
                "Rtt Average (ms)": round(rtt_avg, 2) if pd.notna(rtt_avg) else "N/A",
                "Rtt Median (ms)": round(rtt_median, 2)
                if pd.notna(rtt_median)
                else "N/A",
                "Rtt Max (ms)": round(rtt_max, 2) if pd.notna(rtt_max) else "N/A",
                "Jitter Min (ms)": round(jitter_min, 3)
                if pd.notna(jitter_min)
                else "N/A",
                "Jitter Average (ms)": round(jitter_avg, 3)
                if pd.notna(jitter_avg)
                else "N/A",
                "Jitter Median (ms)": round(jitter_median, 3)
                if pd.notna(jitter_median)
                else "N/A",
                "Jitter Max (ms)": round(jitter_max, 3)
                if pd.notna(jitter_max)
                else "N/A",
            }
            total = len(group)
            for tech in technology_keywords:
                tech_count = (
                    group[tech_col].astype(str).str.contains(tech, na=False).sum()
                )
                row[tech] = tech_count
                row[f"{tech} (%)"] = round(tech_count / total, 4) if total > 0 else 0.0

            summary.append(row)

        return pd.DataFrame(summary)

    except Exception as e:
        logger.warning(f"Error in summarize_videochat_kqi: {e}")
        logger.warning(
            f"Available columns: {list(df.columns) if df is not None else 'None'}"
        )
        return pd.DataFrame()


def summarize_m2m_mos_kqi(df, test_type):
    """
    Creates KQI summary for M2M MOS test cases based on voice quality measurements.
    """
    try:
        if df is None or df.empty:
            return pd.DataFrame()

        df.columns = df.columns.str.strip()
        mos_data = (
            df[df["Test Type"] == "MOS_M2M"].copy()
            if "Test Type" in df.columns
            else df.copy()
        )

        if mos_data.empty:
            logger.warning("Warning: No MOS_M2M test data found in the dataset")
            return pd.DataFrame()

        summary = []

        if "Operator" not in mos_data.columns:
            mos_data["Operator"] = "Unknown"

        if "Side" not in mos_data.columns and "Test Side" in mos_data.columns:
            mos_data["Side"] = mos_data["Test Side"]
        elif "Side" not in mos_data.columns:
            mos_data["Side"] = "Unknown"

        if "Type Mobility" not in mos_data.columns:
            mos_data["Type Mobility"] = "Unknown"

        tech_col = "Technology_Detail"
        if tech_col not in mos_data.columns:
            if "RadioAccessTechnologyState" in mos_data.columns:
                mos_data[tech_col] = mos_data["RadioAccessTechnologyState"]
            else:
                mos_data[tech_col] = "Unknown"

        if "Qualifier" not in mos_data.columns:
            mos_data["Qualifier"] = "Unknown"

        logger.info("Calculating M2M MOS KQIs...")
        test_name = ""
        for (operator, side), group in mos_data.groupby(["Operator", "Side"]):
            total_samples = len(group)
            qualified_sessions = (group["Qualifier"] == "Qualified").sum()

            # Choose MOS column based on side
            if side == "A":
                main_mos_col = "POLQA SWB Score DL A"
            elif side == "B":
                main_mos_col = "POLQA SWB Score DL B"
            else:
                main_mos_col = "POLQA SWB Score DL"

            mos_scores = pd.Series(dtype=float)
            if main_mos_col and main_mos_col in group.columns:
                mos_scores = pd.to_numeric(
                    group[main_mos_col], errors="coerce"
                ).dropna()

            mos_less_1_3 = (mos_scores < 1.3).sum() if not mos_scores.empty else 0
            mos_less_1_3_ratio = (
                round((mos_less_1_3 / total_samples) * 100, 1)
                if total_samples > 0
                else 0
            )

            polqa_min = round(mos_scores.min(), 2) if not mos_scores.empty else None
            polqa_avg = round(mos_scores.mean(), 2) if not mos_scores.empty else None
            polqa_max = round(mos_scores.max(), 2) if not mos_scores.empty else None
            polqa_10_pctl = (
                round(mos_scores.quantile(0.10), 2) if not mos_scores.empty else None
            )
            polqa_median = (
                round(mos_scores.median(), 2) if not mos_scores.empty else None
            )
            polqa_90_pctl = (
                round(mos_scores.quantile(0.90), 2) if not mos_scores.empty else None
            )

            aqm_cols = [
                col
                for col in group.columns
                if "aqm" in col.lower() and "score" in col.lower()
            ]
            aqm_min, aqm_avg, aqm_max = None, None, None
            if aqm_cols:
                aqm_data = pd.to_numeric(group[aqm_cols[0]], errors="coerce").dropna()
                if not aqm_data.empty:
                    aqm_min = round(aqm_data.min(), 2)
                    aqm_avg = round(aqm_data.mean(), 2)
                    aqm_max = round(aqm_data.max(), 2)
            else:
                aqm_min, aqm_avg, aqm_max = polqa_min, polqa_avg, polqa_max

            if test_type == "m2m":
                test_name = "M2M"
            elif test_type == "ott":
                test_name = "OTT"

            row = {
                "Operator": operator,
                "Operator Side": side,
                "Test Name": f"MOS {test_name}",
                "Type Mobility": group["Type Mobility"].iloc[0],
                "Source": "MOS",
                "Samples Count": total_samples,
                "Qualified Session": qualified_sessions,
                "MOS <= 1.3 COUNT": mos_less_1_3,
                "MOS <= 1.3 RATIO": f"{mos_less_1_3_ratio}%",
                "POLQA MIN MOS": polqa_min,
                "POLQA AVG MOS": polqa_avg,
                "POLQA MAX MOS": polqa_max,
                "POLQA 10 PCTL MOS": polqa_10_pctl,
                "POLQA Median MOS": polqa_median,
                "POLQA 90 PCTL MOS": polqa_90_pctl,
                "AQM Score MIN": aqm_min,
                "AQM Score AVG": aqm_avg,
                "AQM Score MAX": aqm_max,
            }

            if tech_col in group.columns:
                for tech in technology_keywords:
                    tech_count = (
                        group[tech_col].astype(str).str.contains(tech, na=False).sum()
                    )
                    row[tech] = tech_count
                    row[f"{tech} (%)"] = (
                        round(tech_count / total_samples, 4)
                        if total_samples > 0
                        else 0.0
                    )

            summary.append(row)

        return pd.DataFrame(summary)

    except Exception as e:
        logger.warning(f"Error in summarize_m2m_mos_kqi: {e}")
        logger.warning(
            f"Available columns: {list(df.columns) if df is not None else 'None'}"
        )
        return pd.DataFrame()


# TODO Combine into one method
def summarize_m2m_mos_combined(df, test_type):
    """
    Alternative function that creates a combined summary similar to Excel format
    with separate sections for Side A and Side B.
    """
    try:
        if df is None or df.empty:
            return pd.DataFrame()

        # Get individual summaries for each side
        df_side_a = (
            df[df["Side"] == "Side A"].copy() if "Side" in df.columns else df.copy()
        )
        df_side_b = (
            df[df["Side"] == "Side B"].copy()
            if "Side" in df.columns
            else pd.DataFrame()
        )

        summary_a = (
            summarize_m2m_mos_kqi(df_side_a, test_type)
            if not df_side_a.empty
            else pd.DataFrame()
        )
        summary_b = (
            summarize_m2m_mos_kqi(df_side_b, test_type)
            if not df_side_b.empty
            else pd.DataFrame()
        )

        # Combine both summaries
        combined = pd.concat([summary_a, summary_b], ignore_index=True)

        return combined

    except Exception as e:
        logger.warning(f"Error in summarize_m2m_mos_combined: {e}")
        return pd.DataFrame()


# TODO Standarize Columns
def summarize_voice_mot_kqi(df, test_type):
    """
    Creates KQI summary for Voice MOT test cases, grouped by Operator and Side,
    with simpler if-else column mapping.
    """
    try:
        if df is None or df.empty:
            return pd.DataFrame()

        df.columns = df.columns.str.strip()
        summary = []
        test_name = ""

        for (operator, side), group in df.groupby(["Operator", "Side"]):
            # Call Attempt column mapping
            call_attempt_col = None
            if f"Call Attempt {side}" in group.columns:
                call_attempt_col = f"Call Attempt {side}"
            elif "Call Attempt" in group.columns:
                call_attempt_col = "Call Attempt"

            # Qualifier column mapping
            qualifier_col = None
            if f"Qualifier {side}" in group.columns:
                qualifier_col = f"Qualifier {side}"
            elif "Qualifier" in group.columns:
                qualifier_col = "Qualifier"

            # Setup Success Rate column mapping
            setup_success_rate_col = None
            if f"Call Setup Success Rate {side}" in group.columns:
                setup_success_rate_col = f"Call Setup Success Rate {side}"
            elif "Voice_Call_Setup_Success_Rate" in group.columns:
                setup_success_rate_col = "Voice_Call_Setup_Success_Rate"

            # Completion Rate column mapping
            completion_rate_col = None
            if f"Call Completion Rate {side}" in group.columns:
                completion_rate_col = f"Call Completion Rate {side}"
            elif "Voice_Call_Completion_Rate" in group.columns:
                completion_rate_col = "Voice_Call_Completion_Rate"

            # Success Rate column mapping
            success_rate_col = None
            if f"Call Success Rate {side}" in group.columns:
                success_rate_col = f"Call Success Rate {side}"
            elif "Voice_Call_Success_Rate" in group.columns:
                success_rate_col = "Voice_Call_Success_Rate"

            # Drop Rate column mapping
            drop_rate_col = None
            if f"Call Drop Rate {side}" in group.columns:
                drop_rate_col = f"Call Drop Rate {side}"
            elif "Voice_Dropped_Call_Rate" in group.columns:
                drop_rate_col = "Voice_Dropped_Call_Rate"

            # Block Rate column mapping
            block_rate_col = None
            if f"Call Block Rate {side}" in group.columns:
                block_rate_col = f"Call Block Rate {side}"
            elif "Call Block Rate" in group.columns:
                block_rate_col = "Call Block Rate"

            # Setup Failure Rate column mapping
            setup_fail_rate_col = None
            if f"Call Setup Failure Rate {side}" in group.columns:
                setup_fail_rate_col = f"Call Setup Failure Rate {side}"
            elif "Voice_Call_Setup_Failure_Rate" in group.columns:
                setup_fail_rate_col = "Voice_Call_Setup_Failure_Rate"

            # Call Duration column mapping
            call_duration_col = None
            if f"Call Duration {side}" in group.columns:
                call_duration_col = f"Call Duration {side}"
            elif "Call_Duration" in group.columns:
                call_duration_col = "Call_Duration"

            # Setup Time column mapping
            setup_time_col = None
            if f"Call Setup Time (sec) {side}" in group.columns:
                setup_time_col = f"Call Setup Time (sec) {side}"
            elif "Call_Setup_Time_sec" in group.columns:
                setup_time_col = "Call_Setup_Time_sec"

            multi_rab_col = None
            if f"Is_Multi_RAB {side}" in group.columns:
                multi_rab_col = f"Is_Multi_RAB {side}"
            elif "Is_Multi_RAB" in group.columns:
                multi_rab_col = "Is_Multi_RAB"

            sq_mos_col = None
            if f"SQ MOS {side}" in group.columns:
                sq_mos_col = f"SQ MOS {side}"
            elif "SQ_MOS" in group.columns:
                sq_mos_col = "SQ_MOS"

            polqa_col = None
            if f"POLQA SWB Score DL {side}" in group.columns:
                polqa_col = f"POLQA SWB Score DL {side}"
            elif "POLQA SWB Score DL" in group.columns:
                polqa_col = "POLQA SWB Score DL"

            # New AQM Score column mappings
            aqm_col = None
            if f"AQM Score {side}" in group.columns:
                aqm_col = f"AQM Score {side}"
            elif "AQM Score" in group.columns:
                aqm_col = "AQM Score"

            # Helper function for safe column access
            def safe_col(col_name):
                return (
                    group[col_name]
                    if col_name and col_name in group.columns
                    else pd.Series(dtype="float")
                )

            # Calculate metrics
            call_attempts = safe_col(call_attempt_col).eq("Call Attempt").sum()
            qualified_sessions = safe_col(qualifier_col).eq("Qualified").sum()
            setup_success_count = safe_col(setup_success_rate_col).eq(100).sum()

            def safe_mean_percent(col_name):
                col = safe_col(col_name).astype(float)
                return (
                    round(col.mean() / 100, 4)
                    if not col.empty and not col.isna().all()
                    else "Null"
                )

            setup_success_rate = safe_mean_percent(setup_success_rate_col)
            completed_calls = safe_col(completion_rate_col).eq(100).sum()
            completion_rate = safe_mean_percent(completion_rate_col)
            success_rate = safe_mean_percent(success_rate_col)
            dropped_calls = safe_col(drop_rate_col).eq(100).sum()
            dropped_ratio = safe_mean_percent(drop_rate_col)
            blocked_calls = safe_col(block_rate_col).eq(100).sum()
            blocked_ratio = safe_mean_percent(block_rate_col)
            setup_fail_rate = safe_mean_percent(setup_fail_rate_col)
            overall_failed = call_attempts - completed_calls

            # Duration stats
            durations = pd.to_numeric(
                safe_col(call_duration_col), errors="coerce"
            ).dropna()
            min_duration = round(durations.min(), 2) if not durations.empty else "Null"
            avg_duration = round(durations.mean(), 2) if not durations.empty else "Null"
            max_duration = round(durations.max(), 2) if not durations.empty else "Null"

            # Setup time stats
            setup_times = pd.to_numeric(
                safe_col(setup_time_col), errors="coerce"
            ).dropna()
            min_setup_time = (
                round(setup_times.min(), 2) if not setup_times.empty else "Null"
            )
            avg_setup_time = (
                round(setup_times.mean(), 2) if not setup_times.empty else "Null"
            )
            max_setup_time = (
                round(setup_times.max(), 2) if not setup_times.empty else "Null"
            )
            pctl_10 = (
                round(np.percentile(setup_times, 10), 2)
                if len(setup_times) > 0
                else "Null"
            )
            pctl_50 = (
                round(np.percentile(setup_times, 50), 2)
                if len(setup_times) > 0
                else "Null"
            )
            pctl_90 = (
                round(np.percentile(setup_times, 90), 2)
                if len(setup_times) > 0
                else "Null"
            )
            setup_time_gt_4s = (setup_times > 4).sum()
            setup_time_lte_4s = (setup_times <= 4).sum()
            multi_rab_series = safe_col(multi_rab_col).astype(str)
            multi_rab_status = (
                "True"
                if multi_rab_series.str.contains("True", case=False, na=False).any()
                else "False"
            )
            multi_rab_success = multi_rab_series.str.contains(
                "True", case=False, na=False
            ).sum()
            multi_rab_ratio = (
                round(multi_rab_success / len(multi_rab_series), 4)
                if len(multi_rab_series) > 0
                else 0
            )

            # Calculate POLQA metrics
            polqa_scores = pd.to_numeric(safe_col(polqa_col), errors="coerce").dropna()
            polqa_min = (
                round(polqa_scores.min(), 2) if not polqa_scores.empty else "Null"
            )
            polqa_avg = (
                round(polqa_scores.mean(), 2) if not polqa_scores.empty else "Null"
            )
            polqa_max = (
                round(polqa_scores.max(), 2) if not polqa_scores.empty else "Null"
            )
            polqa_10 = (
                round(np.percentile(polqa_scores, 10), 2)
                if len(polqa_scores) > 0
                else "Null"
            )
            polqa_median = (
                round(np.percentile(polqa_scores, 50), 2)
                if len(polqa_scores) > 0
                else "Null"
            )
            polqa_90 = (
                round(np.percentile(polqa_scores, 90), 2)
                if len(polqa_scores) > 0
                else "Null"
            )

            # SQ Mos
            sq_mos = pd.to_numeric(safe_col(sq_mos_col), errors="coerce")
            sample_count = sq_mos.count()
            poor_count = (sq_mos <= 1.3).sum() if not sq_mos.empty else 0
            mos_less_1_3_ratio = (
                round((poor_count / sample_count) * 100, 1) if sample_count > 0 else 0
            )

            # Calculate AQM Score metrics
            aqm_scores = pd.to_numeric(safe_col(aqm_col), errors="coerce").dropna()
            aqm_min = round(aqm_scores.min(), 2) if not aqm_scores.empty else "Null"
            aqm_avg = round(aqm_scores.mean(), 2) if not aqm_scores.empty else "Null"
            aqm_max = round(aqm_scores.max(), 2) if not aqm_scores.empty else "Null"

            # Technology column mapping
            tech_col = None
            if "Technology_Detail" in group.columns:
                tech_col = "Technology_Detail"

            if test_type == "m2m":
                test_name = "M2M"
            elif test_type == "ott":
                test_name = "OTT"

            row = {
                "Operator": operator,
                "Operator Side": side,
                "Test Name": f"Voice {test_name}",
                "Type Mobility": group["Type Mobility"].iloc[0],
                "Source": "Voice",
                # TODO Combine Side A and Side B KQI
                "Samples Count": sample_count,
                "Call Attempts": call_attempts,
                "Qualified Session": qualified_sessions,
                "Call Setup Success Count": setup_success_count,
                "Voice Call setup success rate (%)": f"{setup_success_rate * 100:.1f}%"
                if setup_success_rate != "Null"
                else "Null",
                "Completed Calls Count": completed_calls,
                "Voice Call completion rate (%)": f"{completion_rate * 100:.1f}%"
                if completion_rate != "Null"
                else "Null",
                "Voice Call success rate (%)": f"{success_rate * 100:.1f}%"
                if success_rate != "Null"
                else "Null",
                "Dropped Calls Count": dropped_calls,
                "Dropped Calls Ratio": f"{dropped_ratio * 100:.1f}%"
                if dropped_ratio != "Null"
                else "Null",
                "Blocked Calls Count": blocked_calls,
                "Blocked Calls Ratio": f"{blocked_ratio * 100:.1f}%"
                if blocked_ratio != "Null"
                else "Null",
                "Overall Failed": overall_failed,
                "Voice Call setup failure rate (%)": f"{setup_fail_rate * 100:.1f}%"
                if setup_fail_rate != "Null"
                else "Null",
                "MIN Call duration (s)": min_duration,
                "Avg Call duration (s)": avg_duration,
                "MAX Call duration (s)": max_duration,
                "MIN Call Setup time sec": min_setup_time,
                "Avg Call Setup time sec": avg_setup_time,
                "MAX Call Setup Time sec": max_setup_time,
                "10 PCTL Call setup time sec": pctl_10,
                "Median Call setup time sec": pctl_50,
                "90 PCTL Call setup time sec": pctl_90,
                "Call Setup Time > 4 s count": setup_time_gt_4s,
                "Call Setup Time <= 4 s count": setup_time_lte_4s,
                # TODO Combine Side A and Side B KQI
                "MultiRAB Status": multi_rab_status,
                "MultiRAB Success Count": multi_rab_success,
                "MultiRAB Ratio": f"{multi_rab_ratio * 100:.1f}%"
                if multi_rab_ratio != "Null"
                else "Null",
                "POLQA MIN MOS": polqa_min,
                "POLQA AVG MOS": polqa_avg,
                "POLQA MAX MOS": polqa_max,
                "POLQA 10 PCTL MOS": polqa_10,
                "POLQA Median MOS": polqa_median,
                "POLQA 90 PCTL MOS": polqa_90,
                "MOS <= 1.3 COUNT": poor_count,
                "MOS <= 1.3 RATIO": mos_less_1_3_ratio,
                "AQM Score MIN": aqm_min,
                "AQM Score AVG": aqm_avg,
                "AQM Score MAX": aqm_max,
            }

            if tech_col and tech_col in group.columns:
                total_samples = len(group)

                for tech in technology_keywords:
                    tech_count = (
                        group[tech_col]
                        .astype(str)
                        .str.contains(tech, na=False, case=False)
                        .sum()
                    )
                    row[tech] = tech_count
                    row[f"{tech} (%)"] = (
                        round((tech_count / total_samples) * 100, 1)
                        if total_samples > 0
                        else 0.0
                    )

            summary.append(row)

        return pd.DataFrame(summary)

    except Exception as e:
        logger.warning(f"Error in summarize_voice_mot_kqi: {e}")
        return pd.DataFrame()


# === Proses Semua Data ===
http_summary = summarize_http_kpi(http_df)
streaming_summary = summarize_streaming_kpi(streaming_df)
ping_summary = summarize_ping_kpi(ping_df)
egaming_summary = summarize_egaming(egaming_df)
dns_summary = summarize_dns_kpis(dns_df)
videochat_summary = summarize_videochat_kqi(videochat_df)
mos_m2m_summary = summarize_m2m_mos_combined(mos_m2m_df, "m2m")
mos_ott_summary = summarize_m2m_mos_combined(mos_ott_df, "ott")
voice_m2m_summary = summarize_voice_mot_kqi(voice_m2m_df, "m2m")
voice_ott_summary = summarize_voice_mot_kqi(voice_ott_df, "ott")

# === Gabungkan Semua ===
combined_summary = pd.concat(
    [
        http_summary,
        streaming_summary,
        ping_summary,
        egaming_summary,
        videochat_summary,
        dns_summary,
        mos_m2m_summary,
        mos_ott_summary,
        voice_m2m_summary,
        voice_ott_summary,
    ],
    ignore_index=True,
)

# === Simpan ke Excel ===
combined_summary.to_excel(output_file, index=False)
logger.success(f"kqi has been save in: {output_file}")
