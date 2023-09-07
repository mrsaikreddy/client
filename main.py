import time
import threading
import os
import argparse
import json

from camera.multi_camera import MultiCameraCapture
from config.config import Configuration, get_latest_config_path


from logs import logs
logs = logs.logger

# Initialize command-line argument parser
parser = argparse.ArgumentParser()
parser.add_argument("--cloud_config", help="1 for cloud config, 0 for local config")
parser.add_argument("--hapi_ip", help="IP address for HAPI")
parser.add_argument("--hacksboard_ip", help="IP address for Hacksboard")

args = parser.parse_args()

# Entry point for the script
if __name__ == "__main__":
    
    # Determine the source of the configuration: cloud or local
    if args.cloud_config == '1':
        latest_config_path = get_latest_config_path()
    else:
        latest_config_path = 'sysconfig/config.json'

    # If HAPI IP is provided, update the configuration file
    if args.hapi_ip:
        with open(f"sysconfig/config.json", "r") as file:
            config = json.load(file)
        config["common"]["train_storage_ip"] = f"{args.hapi_ip}/api/testimage/TrainImageData/"
        config["common"]["alert_storage_ip"] = f"{args.hapi_ip}/api/testimage/AlertImageData/"
        config["common"]["roi_storage_ip"] = f"{args.hapi_ip}/hapi/testimage/TrainImageData"
        with open(f"sysconfig/config.json", "w") as file:
            json.dump(config, file, indent=4)

    # If Hacksboard IP is provided, update the configuration file
    if args.hacksboard_ip:
        with open(f"sysconfig/config.json", "r") as file:
            config = json.load(file)
        config["common"]["roi_ip"] = f"{args.hacksboard_ip}/api/v1/O9tfwWn1fzlSVSQgtplU/telemetry"
        config["common"]["cloud_status_ip"] = f"{args.hacksboard_ip}/api/v1/O9tfwWn1fzlSVSQgtplU/attributes"
        config["common"]["alert_url"] = f"{args.hacksboard_ip}/api/v1/O9tfwWn1fzlSVSQgtplU/telemetry"
        config["common"]["train_url"] = f"{args.hacksboard_ip}/api/v1/O9tfwWn1fzlSVSQgtplU/telemetry"
        config["common"]["test_url"] = f"{args.hacksboard_ip}/api/v1/O9tfwWn1fzlSVSQgtplU/telemetry"
        with open(f"sysconfig/config.json", "w") as file:
            json.dump(config, file, indent=4)

    config = Configuration(config_file=latest_config_path)

    logs.debug(config.get_common_config())

    mul_cameras = MultiCameraCapture(config=config)

    # Start all cameras
    mul_cameras.startAllCameras()

    while True:
        logs.debug("Current Active Threads -> %s", threading.active_count())
        time.sleep(1)
