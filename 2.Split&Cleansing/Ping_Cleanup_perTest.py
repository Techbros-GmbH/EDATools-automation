import pandas as pd
from pathlib import Path
from datetime import datetime


# === Load Excel ===
input_folder = Path("/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/Ping/Input")
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
    df[["PingDataRadioBearer"]].rename(columns={"PingDataRadioBearer": "Ping Data Radio Bearer"})
], axis=1)


# === Step 2: Rename columns globally
master_rename_map = {
    "Date Time": "Date",
    "Time": "Time",
    "Test Name": "Test Name",
    "Operator_New": "Operator ",
    "Sequence": "Sequence",
    "Type Mobility": "Type Mobility",
    "Country": "Route Name",
    "MNC": "MNC",
    "IMSI": "IMSI",
    "Technology_Detail": "Session Start Technology",
    "TAC": "Session Start TAC",
    "PingLogfileName": "Logfile Name",
    "PingAddress": "Ping Address",
    "PingStartLatitude": "Latitude",
    "PingStartLongitude": "Longitude",
    "PingEndLatitude": "Session End Latitude",
    "PingEndLongitude": "Session End Longitude",
    "PingDataRadioBearer": "Session Start Data Radio Bearer",
    "PingTotalCount": "Ping Total Count",
    "Ping_Count_Attempts": "Ping  Count  Attempts",
    "Ping_Count_Success": "Ping  Count  Success",
    "PingSuccessCount": "Ping Success Count",
    "Ping_Count_Failed": "Ping Count Failed",
    "PingFailedRate": "Ping Failed Rate",
    "PingFailedCount": "Ping Failed Count",
    "PingStartTime": "Session Start Time",
    "PingEndTime": "Session End Time",
    "PingStartRat": "Ping Start Rat",
    "PingEndRat": "Ping End Rat",
    "PingStartMultiRATConnectivityMode": "Session Start MultiRAT",
    "PingEndMultiRATConnectivityMode": "Session End MultiRAT",
    "PingTimeout": "Ping Timeout",
    "PingRttAvg": "Ping RTT Avg",
    "PingRttList": "Ping RTT List",
    "PingRttMax": "Ping RTT Max",
    "PingRttMin": "Ping RTT Min",
    "Ping_Size": "Ping Size",
    "Seconds_Start_to_End_Ping": "Seconds Start to End Ping",
    "Ping_Packet_Loss_Rate": "Ping Packet Loss Rate",
    "Ping_Packet_Success_Rate": "Ping Packet Success Rate",
    "Ping_Delay_ms_Avg": "Ping Delay (ms) Avg",
    "Ping_Delay_ms_Max": "Ping Delay (ms) Max",
    "Ping_Delay_ms_Min": "Ping Delay (ms) Min",
    "Ping_Client_IP_Address": "Ping Client IP Address",
    "Ping_Server_IP_Address": "Ping Server IP Address",
    "LTE Cell Identity(eNB Part)": "LTE Cell Identity(eNB Part)",
    "LTE Cell Identity(Cell Part)": "LTE Cell Identity(Cell Part)",
    "LTE Serving Cell Identity": "LTE Serving Cell Identity",
    "LTE Serving Cell DL EARFCN": "LTE Serving Cell DL EARFCN",
    "LTE Serving Cell Frequency Band": "LTE Serving Cell Frequency Band",
    "LTE Serving Cell Channel RSSI(dBm)": "LTE Serving Cell Channel RSSI(dBm)",
    "LTE Serving Cell RSRP(dBm)": "LTE Serving Cell RSRP(dBm)",
    "LTE Serving Cell RS SINR(dB)": "LTE Serving Cell RS SINR(dB)",
    "LTE Serving Cell RSRQ (dB)": "LTE Serving Cell RSRQ (dB)",
    "LTE_Serving_Cell_Count_Average": "LTE Serving Cell Count Average",
    "LTE Secondary Serving Cell 1 Identity": "LTE Secondary Serving Cell 1 Identity",
    "LTE Secondary Serving Cell 1 DL EARFCN": "LTE Secondary Serving Cell 1 DL EARFCN",
    "LTE Secondary Serving Cell 1 Frequency Band": "LTE Secondary Serving Cell 1 Frequency Band",
    "LTE Secondary Serving Cell 1 Channel RSSI (dBm)": "LTE Secondary Serving Cell 1 Channel RSSI (dBm)",
    "LTE Secondary Serving Cell 1 RSRP (dBm)": "LTE Secondary Serving Cell 1 RSRP (dBm)",
    "LTE Secondary Serving Cell 1 RS SINR (dB)": "LTE Secondary Serving Cell 1 RS SINR (dB)",
    "LTE Secondary Serving Cell 1 RSRQ (dB)": "LTE Secondary Serving Cell 1 RSRQ (dB)",
    "LTE Neighbor Cell 1 PCI": "LTE Neighbor Cell 1 PCI",
    "LTE Neighbor Cell 1 DL EARFCN": "LTE Neighbor Cell 1 DL EARFCN",
    "LTE Neighbor Cell 1 RSRP": "LTE Neighbor Cell 1 RSRP",
    "LTE Neighbor Cell 1 RSRQ": "LTE Neighbor Cell 1 RSRQ",
    "LTE Serving Cell DL Pathloss Carrier 1 (dB)": "LTE Serving Cell DL Pathloss Carrier 1 (dB)",
    "LTE MAC DL Throughput (kbps)": "LTE MAC DL Throughput (kbps)",
    "LTE MAC DL Throughput Carrier 1 (kbps)": "LTE MAC DL Throughput Carrier 1 (kbps)",
    "LTE MAC DL Throughput Carrier 2 (kbps)": "LTE MAC DL Throughput Carrier 2 (kbps)",
    "LTE MAC DL Throughput Carrier 3 (kbps)": "LTE MAC DL Throughput Carrier 3 (kbps)",
    "LTE MAC DL Throughput Carrier 4 (kbps)": "LTE MAC DL Throughput Carrier 4 (kbps)",
    "LTE MAC UL Throughput (kbps)": "LTE MAC UL Throughput (kbps)",
    "LTE MAC UL Throughput Carrier 1 (kbps)": "LTE MAC UL Throughput Carrier 1 (kbps)",
    "LTE MAC UL Throughput Carrier 2 (kbps)": "LTE MAC UL Throughput Carrier 2 (kbps)",
    "LTE MAC UL Throughput Carrier 3 (kbps)": "LTE MAC UL Throughput Carrier 3 (kbps)",
    "LTE MAC UL Throughput Carrier 4 (kbps)": "LTE MAC UL Throughput Carrier 4 (kbps)",
    "LTE PDSCH Modulation": "LTE PDSCH Modulation",
    "LTE PDSCH MCS": "LTE PDSCH MCS",
    "LTE PDSCH BLER (%)": "LTE PDSCH BLER (%)",
    "LTE PDSCH Phy Throughput (kbps)": "LTE PDSCH Phy Throughput (kbps)",
    "LTE PDSCH Phy Throughput Total (kbps)": "LTE PDSCH Phy Throughput Total (kbps)",
    "LTE PDSCH Phy Throughput Carrier 1 (kbps)": "LTE PDSCH Phy Throughput Carrier 1 (kbps)",
    "LTE PDSCH Phy Throughput Carrier 2 (kbps)": "LTE PDSCH Phy Throughput Carrier 2 (kbps)",
    "LTE PDSCH Phy Throughput Carrier 3 (kbps)": "LTE PDSCH Phy Throughput Carrier 3 (kbps)",
    "LTE PDSCH Phy Throughput Carrier 4 (kbps)": "LTE PDSCH Phy Throughput Carrier 4 (kbps)",
    "LTE PUSCH Modulation": "LTE PUSCH Modulation ",
    "LTE PUSCH MCS": "LTE PUSCH MCS ",
    "PUSCH BLER (%)": "PUSCH BLER (%)",
    "LTE PUSCH Phy Throughput (kbps)": "LTE PUSCH Phy Throughput (kbps)",
    "LTE PUSCH Phy Throughput Total (kbps)": "LTE PUSCH Phy Throughput Total (kbps)",
    "LTE PUSCH Phy Throughput Carrier 1 (kbps)": "LTE PUSCH Phy Throughput Carrier 1 (kbps)",
    "LTE PUSCH Phy Throughput Carrier 2 (kbps)": "LTE PUSCH Phy Throughput Carrier 2 (kbps)",
    "LTE PUSCH Phy Throughput Carrier 3 (kbps)": "LTE PUSCH Phy Throughput Carrier 3 (kbps)",
    "PUSCH Phy Throughput Carrier 4 (kbps)": "PUSCH Phy Throughput Carrier 4 (kbps)",
    "LTE RLC Throughput DL (Kbps)": "LTE RLC Throughput DL (Kbps)",
    "LTE RLC Throughput UL (Kbps)": "LTE RLC Throughput UL (Kbps)",
    "NR Serving Beam 1 Cell Identity": "NR Serving Beam 1 Cell Identity",
    "NR Serving Beam 1 NRARFCN DL": "NR Serving Beam 1 NRARFCN DL",
    "NR Serving Beam 1 Band": "NR Serving Beam 1 Band",
    "NR Serving Beam 1 Bandwidth DL": "NR Serving Beam 1 Bandwidth DL",
    "NR Serving Beam 1 Bandwidth UL": "NR Serving Beam 1 Bandwidth UL",
    "NR Serving Beam 1 SSB Index": "NR Serving Beam 1 SSB Index",
    "NR Serving Beam 1 Cell Type": "NR Serving Beam 1 Cell Type",
    "NR Serving Beam 1 GSCN": "NR Serving Beam 1 GSCN",
    "NR Serving Beam 2 Cell Identity": "NR Serving Beam 2 Cell Identity",
    "NR Serving Beam 2 NRARFCN DL": "NR Serving Beam 2 NRARFCN DL",
    "NR Serving Beam 2 Band": "NR Serving Beam 2 Band",
    "NR Serving Beam 2 Bandwidth DL": "NR Serving Beam 2 Bandwidth DL",
    "NR Serving Beam 2 Bandwidth UL": "NR Serving Beam 2 Bandwidth UL",
    "NR Serving Beam 2 SSB Index": "NR Serving Beam 2 SSB Index",
    "NR Serving Beam 2 Cell Type": "NR Serving Beam 2 Cell Type",
    "NR Serving Beam 2 GSCN": "NR Serving Beam 2 GSCN",
    "NR Serving Cell Identity Top #1": "NR Serving Cell Identity Top #1",
    "NR Serving Cell NRARFCN DL Top #1": "NR Serving Cell NRARFCN DL Top #1",
    "NR Serving Cell SS RSSI Top #1": "NR Serving Cell SS RSSI Top #1",
    "NR Serving Cell SS RSRP Top #1": "NR Serving Cell SS RSRP Top #1",
    "NR Serving Cell SS SINR Top #1": "NR Serving Cell SS SINR Top #1",
    "NR Serving Cell SS RSRQ Top #1": "NR Serving Cell SS RSRQ Top #1",
    "NR PCell SSB Serving Beam Index Top #1": "NR PCell SSB Serving Beam Index Top #1",
    "NR Neighbor Cell 1 Cell Identity": "NR Neighbor Cell 1 Cell Identity",
    "NR Neighbor Cell 1 NRARFCN": "NR Neighbor Cell 1 NRARFCN",
    "NR Neighbor Cell 1 SS RSRP (dBm)": "NR Neighbor Cell 1 SS RSRP (dBm)",
    "NR Neighbor Cell 1 SS SINR (dB)": "NR Neighbor Cell 1 SS SINR (dB)",
    "NR Neighbor Cell 1 SS RSRQ (dB)": "NR Neighbor Cell 1 SS RSRQ (dB)",
    "NR Neighbor Cell 1 Best Beam Index": "NR Neighbor Cell 1 Best Beam Index",
    "NR Neighbor Cell 1 Cell Type": "NR Neighbor Cell 1 Cell Type",
    "NR Phy Throughput Multi-RAT DL (kbps)": "NR Phy Throughput Multi-RAT DL (kbps)",
    "NR Phy Throughput Multi-RAT UL (kbps)": "NR Phy Throughput Multi-RAT UL (kbps)",
    "NR PDSCH Phy Throughput Total (Kbps)": "NR PDSCH Phy Throughput Total (Kbps)",
    "NR Pcell PDSCH Scheduled Throughput (Mbps)": "NR Pcell PDSCH Scheduled Throughput (Mbps)",
    "NR PDSCH Phy Throughput Serving Beam 1 (Kbps)": "NR PDSCH Phy Throughput Serving Beam 1 (Kbps)",
    "NR PDSCH Modulation Serving Beam 1": "NR PDSCH Modulation Serving Beam 1",
    "NR PDSCH MCS Serving Beam 1": "NR PDSCH MCS Serving Beam 1",
    "NR PDSCH BLER (%) Serving Beam 1": "NR PDSCH BLER (%) Serving Beam 1",
    "NR PDSCH CQI Serving Beam 1": "NR PDSCH CQI Serving Beam 1",
    "NR PDSCH RI Serving Beam 1": "NR PDSCH RI Serving Beam 1",
    "NR DL Pathloss Serving Beam 1": "NR DL Pathloss Serving Beam 1",
    "NR PDSCH Phy Throughput Serving Beam 2 (Kbps)": "NR PDSCH Phy Throughput Serving Beam 2 (Kbps)",
    "NR PDSCH Modulation Serving Beam 2": "NR PDSCH Modulation Serving Beam 2",
    "NR PDSCH MCS Serving Beam 2": "NR PDSCH MCS Serving Beam 2",
    "NR PDSCH BLER (%) Serving Beam 2": "NR PDSCH BLER (%) Serving Beam 2",
    "NR PDSCH CQI Serving Beam 2": "NR PDSCH CQI Serving Beam 2",
    "NR PDSCH RI Serving Beam 2": "NR PDSCH RI Serving Beam 2",
    "NR DL Pathloss Serving Beam 2": "NR DL Pathloss Serving Beam 2",
    "NR PUSCH Phy Throughput Total (kbps)": "NR PUSCH Phy Throughput Total (kbps)",
    "NR Pcell PUSCH Scheduled Throughput (Mbps)": "NR Pcell PUSCH Scheduled Throughput (Mbps)",
    "NR PUSCH Phy Throughput Serving Beam 1 (Kbps)": "NR PUSCH Phy Throughput Serving Beam 1 (Kbps)",
    "NR PUSCH Modulation Serving Beam 1": "NR PUSCH Modulation Serving Beam 1",
    "NR PUSCH MCS Serving Beam 1": "NR PUSCH MCS Serving Beam 1",
    "NR PUSCH BLER (%) Serving Beam 1": "NR PUSCH BLER (%) Serving Beam 1",
    "NR PUSCH Phy Throughput Serving Beam 2 (Kbps)": "NR PUSCH Phy Throughput Serving Beam 2 (Kbps)",
    "NR PUSCH Modulation Serving Beam 2": "NR PUSCH Modulation Serving Beam 2",
    "NR PUSCH MCS Serving Beam 2": "NR PUSCH MCS Serving Beam 2",
    "NR PUSCH BLER (%) Serving Beam 2": "NR PUSCH BLER (%) Serving Beam 2",
    "NR MAC DL Throughput Total (kbps)": "NR MAC DL Throughput Total (kbps)",
    "NR MAC UL Throughput Total (kbps)": "NR MAC UL Throughput Total (kbps)",
    "NR RLC DL Throughput Total (kbps)": "NR RLC DL Throughput Total (kbps)",
    "NR RLC UL Throughput Total (kbps)": "NR RLC UL Throughput Total (kbps)",
    "NR RLC DL Throughput (Kbps)": "NR RLC DL Throughput (Kbps)",
    "NR RLC UL Throughput (Kbps)": "NR RLC UL Throughput (Kbps)",
    "NR BWP Center NR-ARFCN DL Serving Beam 1": "NR BWP Center NR-ARFCN DL Serving Beam 1",
    "NR BWP Bandwidth DL (Mhz) Serving Beam 1": "NR BWP Bandwidth DL (Mhz) Serving Beam 1",
    "NR BWP ID DL Serving Beam 1": "NR BWP ID DL Serving Beam 1",
    "NR BWP Initial Bandwidth DL Serving Beam 1 (MHz)": "NR BWP Initial Bandwidth DL Serving Beam 1 (MHz)",
    "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 1": "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 1",
    "NR BWP Start Point NR-ARFCN DL Serving Beam 1": "NR BWP Start Point NR-ARFCN DL Serving Beam 1",
    "NR BWP Subcarrier Spacing DL Serving Beam 1": "NR BWP Subcarrier Spacing DL Serving Beam 1",
    "NR BWPs Configured Count DL serving Beam 1": "NR BWPs Configured Count DL serving Beam 1",
    "NR BWP Center NR-ARFCN DL Serving Beam 2": "NR BWP Center NR-ARFCN DL Serving Beam 2",
    "NR BWP Bandwidth DL (Mhz) Serving Beam 2": "NR BWP Bandwidth DL (Mhz) Serving Beam 2",
    "NR BWP ID DL Serving Beam 2": "NR BWP ID DL Serving Beam 2",
    "NR BWP Initial Bandwidth DL Serving Beam 2 (MHz)": "NR BWP Initial Bandwidth DL Serving Beam 2 (MHz)",
    "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 2": "NR BWP Initial Start Point NR-ARFCN DL Serving Beam 2",
    "NR BWP Start Point NR-ARFCN DL Serving Beam 2": "NR BWP Start Point NR-ARFCN DL Serving Beam 2",
    "NR BWP Subcarrier Spacing DL Serving Beam 2": "NR BWP Subcarrier Spacing DL Serving Beam 2",
    "NR BWPs Configured Count DL serving Beam 2": "NR BWPs Configured Count DL serving Beam 2",
    "NR BWP Center NR-ARFCN UL Serving Beam 1": "NR BWP Center NR-ARFCN UL Serving Beam 1",
    "NR BWP Bandwidth UL Serving Beam 1 (Mhz)": "NR BWP Bandwidth UL Serving Beam 1 (Mhz)",
    "NR BWP ID UL Serving Beam 1": "NR BWP ID UL Serving Beam 1",
    "NR BWP Initial Bandwidth UL Serving Beam 1 (MHz)": "NR BWP Initial Bandwidth UL Serving Beam 1 (MHz)",
    "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 1": "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 1",
    "NR BWP Start Point NR-ARFCN UL Serving Beam 1": "NR BWP Start Point NR-ARFCN UL Serving Beam 1",
    "NR BWP Subcarrier Spacing UL Serving Beam 1": "NR BWP Subcarrier Spacing UL Serving Beam 1",
    "NR BWPs Configured Count UL Serving Beam 1": "NR BWPs Configured Count UL Serving Beam 1",
    "NR BWP Center NR-ARFCN UL Serving Beam 2": "NR BWP Center NR-ARFCN UL Serving Beam 2",
    "NR BWP Bandwidth UL Serving Beam 2 (Mhz)": "NR BWP Bandwidth UL Serving Beam 2 (Mhz)",
    "NR BWP ID UL Serving Beam 2": "NR BWP ID UL Serving Beam 2",
    "NR BWP Initial Bandwidth UL Serving Beam 2 (MHz)": "NR BWP Initial Bandwidth UL Serving Beam 2 (MHz)",
    "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 2": "NR BWP Initial Start Point NR-ARFCN UL Serving Beam 2",
    "NR BWP Start Point NR-ARFCN UL Serving Beam 2": "NR BWP Start Point NR-ARFCN UL Serving Beam 2",
    "NR BWP Subcarrier Spacing UL Serving Beam 2": "NR BWP Subcarrier Spacing UL Serving Beam 2",
    "NR BWPs Configured Count UL Serving Beam 2": "NR BWPs Configured Count UL Serving Beam 2",
    "RadioAccessTechnologyState": "RadioAccessTechnologyState",
    "MR-DC Cell 1 SINR (dB)": "MR-DC Cell 1 SINR (dB)",
    "PDSCH Average RBs per Allocated Slot Serving Beam 1": "PDSCH Average RBs per Allocated Slot Serving Beam 1",
    "PDSCH Average RBs per Allocated Slot per TB Serving Beam 1": "PDSCH Average RBs per Allocated Slot per TB Serving Beam 1",
    "PDSCH BWP ID Serving Beam 1": "PDSCH BWP ID Serving Beam 1",
    "PDSCH RB Allocation Count Serving Beam 1": "PDSCH RB Allocation Count Serving Beam 1",
    "PDSCH RB Allocation Count per TB Serving Beam 1": "PDSCH RB Allocation Count per TB Serving Beam 1",
    "PDSCH RB Allocation Usage Serving Beam 1 (%)": "PDSCH RB Allocation Usage Serving Beam 1 (%)",
    "PDSCH RBG Size Serving Beam 1": "PDSCH RBG Size Serving Beam 1",
    "PDSCH Slot Allocation Count Serving Beam 1": "PDSCH Slot Allocation Count Serving Beam 1",
    "PDSCH Slot Allocation Count per TB Serving Beam 1": "PDSCH Slot Allocation Count per TB Serving Beam 1",
    "PDSCH Slot Allocation TDD Serving Beam 1 (%)": "PDSCH Slot Allocation TDD Serving Beam 1 (%)",
    "PDSCH Slot Allocation Total Serving Beam 1 (%)": "PDSCH Slot Allocation Total Serving Beam 1 (%)",
    "PDSCH Slot Utilization Serving Beam 1 (%)": "PDSCH Slot Utilization Serving Beam 1 (%)",
    "PDSCH RB Dist Current Count Serving Beam 1": "PDSCH RB Dist Current Count Serving Beam 1",
    "PDSCH RB Utillization Dist Current Count Serving Beam 1": "PDSCH RB Utillization Dist Current Count Serving Beam 1",
    "PDSCH Average RBs per Allocated Slot Serving Beam 2": "PDSCH Average RBs per Allocated Slot Serving Beam 2",
    "PDSCH Average RBs per Allocated Slot per TB Serving Beam 2": "PDSCH Average RBs per Allocated Slot per TB Serving Beam 2",
    "PDSCH BWP ID Serving Beam 2": "PDSCH BWP ID Serving Beam 2",
    "PDSCH RB Allocation Count Serving Beam 2": "PDSCH RB Allocation Count Serving Beam 2",
    "PDSCH RB Allocation Count per TB Serving Beam 2": "PDSCH RB Allocation Count per TB Serving Beam 2",
    "PDSCH RB Allocation Usage Serving Beam 2 (%)": "PDSCH RB Allocation Usage Serving Beam 2 (%)",
    "PDSCH RBG Size Serving Beam 2": "PDSCH RBG Size Serving Beam 2",
    "PDSCH Slot Allocation Count Serving Beam 2": "PDSCH Slot Allocation Count Serving Beam 2",
    "PDSCH Slot Allocation Count per TB Serving Beam 2": "PDSCH Slot Allocation Count per TB Serving Beam 2",
    "PDSCH Slot Allocation TDD Serving Beam 2 (%)": "PDSCH Slot Allocation TDD Serving Beam 2 (%)",
    "PDSCH Slot Allocation Total Serving Beam 2 (%)": "PDSCH Slot Allocation Total Serving Beam 2 (%)",
    "PDSCH Slot Utilization Serving Beam 2 (%)": "PDSCH Slot Utilization Serving Beam 2 (%)",
    "PDSCH RB Dist Current Count Serving Beam 2": "PDSCH RB Dist Current Count Serving Beam 2",
    "PDSCH RB Utillization Dist Current Count Serving Beam 2": "PDSCH RB Utillization Dist Current Count Serving Beam 2",
    "PUSCH Average RBs per Allocated Slot Serving Beam 1": "PUSCH Average RBs per Allocated Slot Serving Beam 1",
    "PUSCH BWP ID Serving Beam 1": "PUSCH BWP ID Serving Beam 1",
    "PUSCH RB Allocation Count Serving Beam 1": "PUSCH RB Allocation Count Serving Beam 1",
    "PUSCH RB Allocation Usage Serving Beam 1 (%)": "PUSCH RB Allocation Usage Serving Beam 1 (%)",
    "PUSCH RBG Size Serving Beam 1": "PUSCH RBG Size Serving Beam 1",
    "PUSCH Slot Allocation Count Serving Beam 1": "PUSCH Slot Allocation Count Serving Beam 1",
    "PUSCH Slot Allocation TDD Serving Beam 1 (%)": "PUSCH Slot Allocation TDD Serving Beam 1 (%)",
    "PUSCH Slot Allocation Total Serving Beam 1 (%)": "PUSCH Slot Allocation Total Serving Beam 1 (%)",
    "PUSCH Slot Utilization Serving Beam 1 (%)": "PUSCH Slot Utilization Serving Beam 1 (%)",
    "PUSCH RB Dist Current Count Serving Beam 1": "PUSCH RB Dist Current Count Serving Beam 1",
    "PUSCH RB Utillization Dist Current Count Serving Beam 1": "PUSCH RB Utillization Dist Current Count Serving Beam 1",
    "PUSCH Average RBs per Allocated Slot Serving Beam 2": "PUSCH Average RBs per Allocated Slot Serving Beam 2",
    "PUSCH BWP ID Serving Beam 2": "PUSCH BWP ID Serving Beam 2",
    "PUSCH RB Allocation Count Serving Beam 2": "PUSCH RB Allocation Count Serving Beam 2",
    "PUSCH RB Allocation Usage Serving Beam 2 (%)": "PUSCH RB Allocation Usage Serving Beam 2 (%)",
    "PUSCH RBG Size Serving Beam 2": "PUSCH RBG Size Serving Beam 2",
    "PUSCH Slot Allocation Count Serving Beam 2": "PUSCH Slot Allocation Count Serving Beam 2",
    "PUSCH Slot Allocation TDD Serving Beam 2 (%)": "PUSCH Slot Allocation TDD Serving Beam 2 (%)",
    "PUSCH Slot Allocation Total Serving Beam 2 (%)": "PUSCH Slot Allocation Total Serving Beam 2 (%)",
    "PUSCH Slot Utilization Serving Beam 2 (%)": "PUSCH Slot Utilization Serving Beam 2 (%)",
    "PUSCH RB Dist Current Count Serving Beam 2": "PUSCH RB Dist Current Count Serving Beam 2",
    "PUSCH RB Utillization Dist Current Count Serving Beam 2": "PUSCH RB Utillization Dist Current Count Serving Beam 2",
    "Radio Common Throughput DL (kbps)": "Radio Common Throughput DL (kbps)",
    "LTE Bearer Maximum Bitrate DL (kbit/s)": "LTE Bearer Maximum Bitrate DL (kbit/s)",
    "LTE PDN Connection AMBR DL (kbps)": "LTE PDN Connection AMBR DL (kbps)",
    "FirmwareVersion": "FirmwareVersion"
    


}
df.rename(columns=master_rename_map, inplace=True)



# === Step 3: Define schema groups
schema_groups = {
    "Ping": [
        "Date",
        "Time",
        "Test Name",
        "Sequence",
        "Logfile Name",
        "Route Name",
        "Operator ",
        "MNC",
        "Session Start Time",
        "Latitude",
        "Longitude",
        "Session Start Technology",
        "Session Start Data Radio Bearer",
        "Session Start MultiRAT",
        "Session Start TAC",
        "Ping Address",
        "Ping Data Radio Bearer",
        "Ping Total Count",
        "Ping  Count  Attempts",
        "Ping  Count  Success",
        "Ping Success Count",
        "Ping Count Failed",
        "Ping Failed Rate",
        "Ping Failed Count",
        "Ping Timeout",
        "Ping RTT Avg",
        "Ping RTT List",
        "Ping RTT Max",
        "Ping RTT Min",
        "Ping Size",
        "Seconds Start to End Ping",
        "Ping Packet Loss Rate",
        "Ping Packet Success Rate",
        "Ping Delay (ms) Avg",
        "Ping Delay (ms) Max",
        "Ping Delay (ms) Min",
        "Ping Client IP Address",
        "Ping Server IP Address",
        "Ping Start Rat",
        "Ping End Rat",
        "Session End Time",
        "Session End MultiRAT",
        "Session End Latitude",
        "Session End Longitude",
        "LTE Cell Identity(eNB Part)",
        "LTE Cell Identity(Cell Part)",
        "LTE Serving Cell Identity",
        "LTE Serving Cell DL EARFCN",
        "LTE Serving Cell Frequency Band",
        "LTE Serving Cell Channel RSSI(dBm)",
        "LTE Serving Cell RSRP(dBm)",
        "LTE Serving Cell RS SINR(dB)",
        "LTE Serving Cell RSRQ (dB)",
        "LTE Serving Cell Count Average",
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
        "LTE Bearer Maximum Bitrate DL (kbit/s)",
        "LTE PDN Connection AMBR DL (kbps)",
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
        "FirmwareVersion"


 

   ]
}

# === Step 4: Map each test name to schema group
testname_to_group = {
    "Ping 800": "Ping",
    "Ping 40": "Ping"
    
    
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
        "Ping 40": 14

    }

    operator_codes = {
        "Vodafone DE": 1,
        "Telefonica DE": 2,
        "Deutsche Telekom": 3
    }

    df = df.copy()
    df["Test_IDs"] = None

    for (test_name, operator), group in df.groupby(["Test Name", "Operator "]):
        test_code = test_name_codes.get(test_name, 0)
        operator_code = operator_codes.get(operator, 0)

        for i, idx in enumerate(group.index, start=1):
            seq = f"{i:04d}"
            df.at[idx, "Test_IDs"] = f"{test_code}{operator_code}{seq}"

    return df

df = generate_test_ids(df)




# === Step 5: Setup output & log
output_dir = Path("/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/Ping/Output2")
output_dir.mkdir(exist_ok=True)
log_path = output_dir / "log.txt"

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


    # === Save to Excel
    with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
        filtered_group.to_excel(writer, sheet_name="AllData", index=False)

    # === Log
    msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Saved: {output_file_name} using schema: {group_key}"
    print(msg)
    with open(log_path, "a") as log_file:
        log_file.write(msg + "\n")


