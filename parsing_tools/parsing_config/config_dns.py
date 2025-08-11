from typing import Any
import pandas as pd

def first_val(x: pd.Series) -> Any:
    return x.dropna().iloc[0] if not x.dropna().empty else None

def last_val(x: pd.Series) -> Any:
    return x.dropna().iloc[-1] if not x.dropna().empty else None

def modus(x: pd.Series) -> Any:
    return x.mode().iloc[0] if not x.mode().empty else None

DNS_MEAN_COLS = [
    "DNS_Host_Name_Resolution_Failure_Ratio",
    "DNS_Host_Name_Resolution_Time_sec",
    "DNS_Host_Name_Total_Resolution_Time_sec",
    "DNS Resolution Success Ratio (%)",
    "First_DNS_Request_to_HTTP_Get_First_Chunk_Downloaded_ms",
    "First_DNS_Request_to_HTTP_Post_First_Chunk_Uploaded_ms",
    "Seconds_Start_to_End_HTTP",
]

DNS_AGG_RULES = {
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
    "DNS_Host_Name_Resolution_Failure_Ratio": "mean",
    "DNS_Host_Name_Resolution_Time_sec": "mean",
    "DNS_Host_Name_Total_Resolution_Time_sec": "mean",
    "DNS Resolution Success Ratio (%)": "mean",
    "TAC": modus,
    "HttpImsi": last_val,
    "HttpStartTime": first_val,
    "HttpStartLatitude": first_val,
    "HttpStartLongitude": first_val,
    "First_DNS_Request_to_HTTP_Get_First_Chunk_Downloaded_ms": "mean",
    "First_DNS_Request_to_HTTP_Post_First_Chunk_Uploaded_ms": "mean",
    "HttpDataRadioBearer": modus,
    "HttpEndTime": last_val,
    "HttpEndMultiRATConnectivityMode": modus,
    "HttpEndLatitude": last_val,
    "HttpEndLongitude": last_val,
    "Seconds_Start_to_End_HTTP": "sum",
    "FirmwareVersion": modus,
}

DNS_DESIRED_ORDER = [
    "Date Time", "Test Id", "Test_Name_1", "Test_Name_2", "Type Mobility", "Operator",
    "Country", "Sequence", "Latitude", "Longitude", "MCC", "MNC", "Technology_Detail",
    "HttpDataRadioBearer", "HTTP_URL", "DNS_Client", "DNS_Domain_Name", "DNS_Server_Address",
    "DNS_Resolved_Address", "First DNS Request", "DNS_First_In_Session",
    "DNS_Host_Name_Resolution_Failure_Ratio", "DNS_Host_Name_Resolution_Time_sec",
    "DNS_Host_Name_Total_Resolution_Time_sec", "DNS Resolution Success Ratio (%)", "TAC",
    "HttpLogfileName", "HttpImsi", "HttpStartTime", "HttpStartLatitude", "HttpStartLongitude",
    "HttpStartMultiRATConnectivityMode", "First_DNS_Request_to_HTTP_Get_First_Chunk_Downloaded_ms",
    "First_DNS_Request_to_HTTP_Post_First_Chunk_Uploaded_ms", "Seconds_Start_to_End_HTTP",
    "HTTP_Outcome", "HttpEndTime", "HttpEndMultiRATConnectivityMode", "HttpEndLatitude",
    "HttpEndLongitude", "FirmwareVersion"
]
