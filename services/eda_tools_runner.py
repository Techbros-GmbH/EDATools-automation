import argparse
import uvicorn
from uvicorn.config import LOGGING_CONFIG

# python /home/daffa/dataset_maker/services/cge_runner.py

def get_args():
    parser = argparse.ArgumentParser(
        description='Run Head Counter Service'
    )

    parser.add_argument(
        '-p', '--port',
        help='Port to listen on',
        type=int,
        default=4720
    )

    parser.add_argument(
        '-H', '--host',
        help='Host to bind to',
        default='0.0.0.0'
    )

    parser.add_argument(
        "-w", "--workers",
        help="Number of workers",
        type=int,
        default=0
    )

    return parser.parse_args()

if __name__ == "__main__":
    args = get_args()
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s [%(name)s] %(levelprefix)s  %(message)s"
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = "%(asctime)s [%(name)s] %(levelprefix)s %(client_addr)s - \"%(request_line)s\" %(status_code)s"
    uvicorn.run("eda_tools_api:app", host=args.host, port=args.port, workers=args.workers, log_level="info", reload=False)