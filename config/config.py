import json
import requests

from packaging import version
from logs import logs

logs = logs.logger


class Configuration:
    '''
    Loads json configuration file as a dictionary
    '''
    def __init__(self, config_file) -> None:
        assert config_file
        config = json.loads(open(config_file).read())
        self.com_config = config["common"]
        if self.com_config["TestingLevel"] == 2:
            self.cameras = config["sample_cameras"]
        else:
            self.cameras = config["cameras"]
        
               
    def get_camera_config(self):
        '''
        Return details about Camera
        '''
        return self.cameras

    def get_common_config(self):
        '''
        Return common config details
        '''
        return self.com_config

def get_config():
    token = '9c8zso5R3uGu3zDWn2HP'
    url = "https://dev.trakr.live/api/v1/" + token + "/attributes?sharedKeys=config"
    res = requests.get(url=url)
    return (res.json())["shared"]["config"]

def get_latest_config_path():
    cloud_config = get_config(flag=True)
    cloud_version = cloud_config['common']['config_version']
    with open(f"sysconfig/versions/{cloud_version}.json", "w") as file:
        json.dump(cloud_config, file, indent=4)
    with open(f"sysconfig/config.json", "w") as file:
        json.dump(cloud_config, file, indent=4)
    return f"sysconfig/config.json"


# config = Configuration("sysconfig/config.json")

# new_address = config.get_latest_config_path(config=config)
# print(new_address)
