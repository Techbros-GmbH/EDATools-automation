# EDA Tools Automation API

A comprehensive FastAPI application for automating telecommunications test data processing and analysis. This API handles multiple test types including DNS, HTTP, e-gaming, ping, streaming, video chat, voice, and MOS (Mean Opinion Score) data through a multi-stage processing pipeline.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Usage Examples](#usage-examples)
- [Swagger Documentation](#swagger-documentation)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## Features

- **Multi-stage Processing Pipeline**: Aggregation → Cleaning → KQI Summarization
- **Parallel Processing**: Utilizes ProcessPoolExecutor for optimal performance
- **Multiple Test Type Support**: DNS, HTTP, e-gaming, ping, streaming, video chat, voice (M2M/OTT), MOS (M2M/OTT)
- **Flexible Endpoints**: Choose from individual stages or complete pipelines
- **Excel File Processing**: Input and output in Excel format with ZIP compression
- **Automatic Type Detection**: Infers test type from filename
- **Interactive API Documentation**: Built-in Swagger UI

## Prerequisites

- Python 3.8 or higher
- pip package manager
- Sufficient system memory for processing large Excel files

## Installation

### 1. Clone the Repository

```bash
git clone -b feature-fastapi https://github.com/Techbros-GmbH/EDATools-automation.git
cd eda-tools-automation
```

### 1.1 Pull the Repository (if it has an update)

```bash
git pull
```

### 2. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Verify Installation

Check if all required packages are installed:

```bash
pip list
```

Required packages should include:
- fastapi
- uvicorn
- pandas
- loguru
- python-multipart (for file uploads)

## Configuration

### 1. Configuration File

Create or verify the `config.ini` file in the project root:

```ini
[default]
mcc_mnc_path = Mapping/mncmcc_maping.xlsx
test_case_path = Mapping/test_case_map.xlsx
```

### 2. Required Mapping Files

Ensure these files exist in the `Mapping/` directory:
- `mncmcc_maping.xlsx` - Mobile Country Code and Mobile Network Code mappings
- `test_case_map.xlsx` - Test case configuration mappings

## Running the Application

### Method 1: Using the Runner Script (Recommended)

```bash
python services/eda_tools_runner.py -p 4720 --host 0.0.0.0 -w 1
```

**Parameters:**
- `-p, --port`: Port number (default: 4720)
- `-H, --host`: Host address (default: 0.0.0.0)
- `-w, --workers`: Number of worker processes (default: 0 for single process)

### Method 2: Using Uvicorn Directly

```bash
uvicorn services.eda_tools_api:app --host 0.0.0.0 --port 4720 --reload
```

### Method 3: Direct Python Execution

```bash
cd services
python eda_tools_api.py
```

## API Endpoints

### Core Processing Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/v1/aggregator` | POST | Raw data aggregation only |
| `/v1/cleaner` | POST | Data cleaning (expects pre-aggregated data) |
| `/v1/pipeline_cleaner` | POST | Complete aggregation + cleaning pipeline |
| `/v1/pipeline_kqi` | POST | Full pipeline: Aggregation → Cleaning → KQI |
| `/v1/kqi_clean` | POST | KQI generation from clean data |
| `/v1/excel_merger` | POST | Excel file merging utility |

### Utility Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI documentation |


## Usage Examples

### 1. Complete Pipeline Processing

For raw CDR data that needs full processing:

```bash
curl -X POST "http://localhost:4720/v1/pipeline_kqi" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@dns_raw_data.xlsx" \
  -F "files=@http_raw_data.xlsx" \
  --output kqi_results.zip
```

### 2. Aggregation Only

For raw data that only needs aggregation:

```bash
curl -X POST "http://localhost:4720/v1/aggregator" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@dns_test_singapore.xlsx" \
  --output aggregated_results.zip
```

### 3. Cleaning Pre-aggregated Data

For data that's already aggregated:

```bash
curl -X POST "http://localhost:4720/v1/cleaner" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@DNS_Singapore_clean.xlsx" \
  --output cleaned_results.zip
```

### 4. Excel File Merging

To merge multiple Excel files:

```bash
curl -X POST "http://localhost:4720/v1/excel_merger" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@file1.xlsx" \
  -F "files=@file2.xlsx" \
  -F "output_name=merged_data.xlsx" \
  --output merged_result.xlsx
```

## Swagger Documentation

### Accessing the Interactive API Documentation

Once the server is running, access the Swagger UI at:

```
http://localhost:4720/docs
```

### Key Swagger Features

1. **Interactive Testing**: Test all endpoints directly from the browser
2. **File Upload Interface**: Easy drag-and-drop file uploads
3. **Response Examples**: See expected request/response formats
4. **Parameter Documentation**: Detailed parameter descriptions
5. **Error Code Reference**: Complete HTTP status code documentation

### Using Swagger UI

1. **Navigate to the endpoint** you want to test
2. **Click "Try it out"** to enable the interface
3. **Upload your Excel files** using the file picker
4. **Adjust parameters** as needed
5. **Click "Execute"** to run the request
6. **Download results** from the response section

## File Naming Conventions

The API automatically detects test types from filenames. Ensure your files contain these keywords:

| Test Type | Required Keywords | Example Filename |
|-----------|------------------|------------------|
| DNS | `dns` | `dns_test_singapore.xlsx` |
| HTTP | `http` | `HTTP_Performance_Austria.xlsx` |
| E-gaming | `egaming` | `egaming_latency_test.xlsx` |
| Ping | `ping` | `ping_results_bremen.xlsx` |
| Streaming | `streaming` | `streaming_quality_data.xlsx` |
| Video Chat | `videochat` or `video_chat` | `videochat_session_logs.xlsx` |
| Voice M2M | `voice_m2m` | `voice_m2m_call_data.xlsx` |
| Voice OTT | `voice_ott` | `voice_ott_quality.xlsx` |
| MOS M2M | `mos_m2m` | `mos_m2m_scores.xlsx` |
| MOS OTT | `mos_ott` | `mos_ott_analysis.xlsx` |

## Project Structure

```
.
├── config.ini                          # Configuration file
├── kqix/                               # KQI summarization modules
├── Mapping/                            # MCC/MNC and test case mappings
├── merge_testcase/                     # Excel merging functionality
├── parsing_tools/                      # Data aggregation modules
├── services/                           # API service files
│   ├── eda_tools_api.py               # Main FastAPI application
│   └── eda_tools_runner.py            # Application runner script
├── split_n_cleansing_tools/           # Data cleaning modules
├── requirements.txt                    # Python dependencies
└── test-results/                      # Sample outputs
```

## Troubleshooting

### Common Issues

#### 1. Import Errors

```bash
ModuleNotFoundError: No module named 'xyz'
```

**Solution:** Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

#### 2. Configuration File Not Found

```bash
FileNotFoundError: config.ini not found
```

**Solution:** Verify `config.ini` exists in the project root with correct paths.

#### 3. Mapping Files Missing

```bash
FileNotFoundError: mncmcc_maping.xlsx not found
```

**Solution:** Ensure mapping files exist in the `Mapping/` directory.

#### 4. Port Already in Use

```bash
OSError: [Errno 48] Address already in use
```

**Solution:** Use a different port:
```bash
python services/eda_tools_runner.py -p 4721
```

#### 5. File Type Not Recognized

```bash
HTTPException: Could not infer type_test from filename
```

**Solution:** Ensure filenames contain required keywords (see File Naming Conventions).

### Performance Optimization

#### Memory Issues
- Process large files in smaller batches
- Increase system memory if possible
- Use fewer worker processes for memory-intensive operations

#### Processing Speed
- Increase worker count for CPU-bound operations:
```bash
python services/eda_tools_runner.py -w 4
```

### Logging

Check application logs for detailed error information. The application uses structured logging with timestamps and detailed error messages.

### Health Check

Verify the service is running:

```bash
curl http://localhost:4720/health
```

Expected response:
```json
{"ok": true}
```

## Sample Data

For testing and examples, refer to the sample CDR data:
[RAW CDR new format](https://techbrosgmbhduesseldorf.sharepoint.com/sites/BackofficeCDRPhase3/Freigegebene%20Dokumente/Forms/AllItems.aspx?id=%2Fsites%2FBackofficeCDRPhase3%2FFreigegebene%20Dokumente%2FBackoffice%20CDR%20Phase%203%2FRepository%20EDATools%202025%2FSample%20CDR%20%28Sing%20%26%20Austria%20New%20Format%29%2FRAW%20CDR%20New%20Format&viewid=69e60144%2D9189%2D45cb%2D85bf%2D9042cb52ce53&p=true&ga=1)

## Support

For technical issues or questions about the EDA Tools Automation API, please refer to the project documentation or contact the development team.