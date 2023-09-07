import queue
import logging
import aiohttp

from logs import logs
from camera.camera import Camera
from ThreadedCamera.batcher import Batch
from ThreadedCamera.cloud_comm import Comms

log = logs.logger

class MultiCameraCapture:
    '''
    Object for handling Camera and Batch threads
    '''
    def __init__(self, config) -> None:
        assert config
        self.cameras = {}
        self.config = config
        self.batcher = {}

        # All the output and results would be stored in frame_dict and result_dict respectively.
        frame_dict = {}
        result_dict = {}
        roi_config_dict = {}

        # Get camera config
        common_config = config.get_common_config()
        debug_Level = common_config["LoggingLevel"]
        if debug_Level == "INFO":
            log.setLevel(logging.INFO)
        elif debug_Level == "WARNING":
            log.setLevel(logging.WARNING)
        elif debug_Level == "ERROR":
            log.setLevel(logging.ERROR)
        else:
            log.setLevel(logging.DEBUG)
        for cam_config in config.get_camera_config():
            log.info("Camera id starting -> %s",cam_config["CameraId"])
            frame_dict[cam_config['CameraId']] = None
            result_dict[str(cam_config['CameraId'])] = None

            # Camera will setup two threads 
            # 1. Update thread to capture images from the cameras and add to frames data
            #    which is then sent to batcher to form the batch
            # 2. Operate Thread to get the results from the server 
            self.cameras[cam_config["CameraId"]] = Camera(cam_config,
                                                        common_config,
                                                        threading_state=True,
                                                        frames=frame_dict,
                                                        results=result_dict,
                                                        )

        # Start batch threads 
        # corresponding to the number of workers in server, specified here inside common_config.
        for worker in range(int(common_config["workers"])):
            self.batcher[worker] = Batch(id=worker,
                                        common_config=common_config,
                                        frames=frame_dict,
                                        results=result_dict)
        # Start the cloud communincation thread
        self.cloud_comm = Comms(common_config=common_config,
                                latest_frames = frame_dict
                                )

    def startAllCameras(self):
        '''
        Start camera, batch and cloud_communication threads
        '''
        for cam_config in self.config.get_camera_config():
            self.cameras[cam_config["CameraId"]].startcam()

        for worker in range(int(self.config.get_common_config()["workers"])):
            self.batcher[worker].start_batch()

        self.cloud_comm.start_comms()
  

    def get_cameras(self):
        '''
        Return the number of cameras
        '''
        return self.cameras










