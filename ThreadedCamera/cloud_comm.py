import kthread
import traceback
import requests
import queue
import json
import threading
import time
import cv2
import os
import base64
import shutil

from ThreadedCamera import ImageOps
from itertools import cycle
from logs import logs

lock = threading.Lock
logs = logs.logger

class Comms:
    def __init__(self, common_config, latest_frames) -> None:
        self.roi_url = common_config['roi_ip']
        self.roi_storage_url = common_config['roi_storage_ip']
        self.status_url = common_config['cloud_status_ip']

        self.server_add_face = "http://172.17.0.2:10230/add_face"

        self.test_level = common_config["TestingLevel"]
        if self.test_level == 1 or self.test_level == 2:
                self.camera_type = 'cameras'
        else:
            self.camera_type = 'cameras'

        self.session = requests.Session()
        self.combined_batch_of_frames = latest_frames

    def get_status(self):
        """Get latest status from cloud"""
        try:
            resp = self.session.get(url=self.status_url)
            print(resp.json().keys())
            return resp.json()['shared']
        except:
            traceback.print_exc()
            logs.error("Error in fetching status from Cloud")

    def register_face(self, face_id: str, name: str) -> None:
        """
        Register all the images for a person's face based on a given face_id.

        Parameters:
        -----------
        face_id: str  The identifier for a face.
        name: str  The name to associate with the face.
        """

        with open('sysconfig/config.json', 'r') as config_file:
            config = json.load(config_file)

        # Send a request to download face data based on face_id.
        headers = {'Content-Type': 'application/json'}
        data = json.dumps({
            "client_name": config["common"]["ClientName"],
            "face_id": face_id
        })
        face_address = ImageOps.post_url(self.session, url=self.get_face_address_url, headers=headers, data=data)

        shutil.copy(face_address, self.folder_path)
        logs.info("Copied face files successfully")

        # Read images from the folder related to the face_id.
        folder_path = os.path.join(self.folder_path, face_id)
        images = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

        # Register each image to the server.
        for face in images:
            img = cv2.imread(os.path.join(folder_path, face))
            retval, buffer = cv2.imencode('.jpg', img)
            base64_frame = base64.b64encode(buffer).decode('utf-8')
            ImageOps.add_face(self.session, self.server_add_face, base64_frame, name)

        logs.info(f"Added face for Person_id : {face_id}")


    def get_new_frame_path(self, config, cam):
        '''
        Retrieves the latest image from the specified camera and posts it for ROI update.
        Returns the storage path of the saved image.
        '''

        # Convert the camera ID to integer
        cam = int(cam)
        
        b64 = self.combined_batch_of_frames[cam]
        logs.info(f"Grabbed the image successfully from cam_id {cam} for posting to ROI update")
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        data = {
            "client_name": config["common"]["ClientName"],
            "cam_id": cam,
            "raw_img": b64['base64']
        }

        img_path_response = self.session.post(url=self.roi_storage_url, headers=headers, json=data)
        img_path = img_path_response.json()['key']
        logs.info(f"Saved image in HAPI, path: {img_path}")
        return img_path


    def post_image(self, cam):
        """Send the latest image for the requested camera to the cloud
        Receive the new ROI from the cloud and update in config.json

        Parameters:
        -----------
        cam:
            string 
        """
        with open('sysconfig/config.json', 'r') as config_file:
            config = json.loads(config_file.read())

        headers = {'Accept': 'application/json',
                   'Content-Type': 'application/json'}

        status = self.get_status()

        while status["is_roi_to_edit"] != False:
            
            img_path = self.get_new_frame_path(config, cam)
            
            json_data = json.dumps({
                "path_of_image": img_path,
                "prev_roi_json": config[self.camera_type][int(cam)]['roi_config'],
                "event": "submit_roi"
            }, indent=4)
            resp = self.session.post(url=self.roi_url, headers=headers, data=json_data)
            
            # Log response and wait 2 seconds.
            logs.info(f"Response code: {resp}")
            time.sleep(2)
            
            # Refresh status for new ROI.
            status = self.get_status()

        # Retrieve updated ROI from 'status'.
        updated_roi = status["updated_roi"]
        logs.info("Received the update ROI")
        config['cameras'][int(cam)]['roi_config'] = updated_roi 

        with open('sysconfig/config.json', 'w') as config_file:
            config_file.write(json.dumps(config, indent=4))

    def check_status(self):
        """Check various status, and perform operations according to need"""

        while True:
            try:
                # Get the latest status from cloud
                status = self.get_status()

                if status['is_img_to_send'] == True:

                    logs.info("Is_image_to_send is true")
                    # Capture Image and post to cloud
                    self.post_image(status['selected_cam'])

                logs.info("Completed an Iteration")
                time.sleep(5)
            except:
                traceback.print_exc()
                logs.error("Exception in checking status on cloud inside check_status in cloud_comms")

    def start_comms(self):
        logs.warning("Establishing Communication with Cloud")
        try:
            self.comm = kthread.KThread(target=self.check_status, args=())
            self.comm.daemon = True
            self.comm.start()
        except:
            traceback.print_exc()
            logs.error("Error in starting Communication Thread")
