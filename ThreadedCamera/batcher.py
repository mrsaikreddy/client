import kthread
import traceback
import requests
import queue
import json
import threading
import time
import cv2
import redis

from ThreadedCamera import ImageOps
from itertools import cycle
from logs import logs

lock = threading.Lock
logs = logs.logger

r = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

class Batch():
    '''
    Batcher Class for handling all of the communication between cameras and server.

    Frames are picked from the frames dict and sent to server for processing, results are the updated to the results dict.
    '''
    def __init__(self, id, common_config, frames, results) -> None:
        self.id = id
        self.frames = frames
        self.results = results
        self.common_config = common_config
        self.serverIP = common_config["server_ip"]
        self.session = requests.Session()
        self.batch_size = common_config["batch_size"]

    # Adds image data to the data structure, process it using post_url and return the specified image to specified thread in json format
    # No need to handle the return format as post processing is already handled.
    def process(self, batched_data):
        '''
        post the results to the server, and update the detections which
        are received from the server
        '''
        try:
            detections = self.post(batched_data)
            self.update_results(detections)
        except:
            traceback.print_exc()
            logs.error("Failed to process batch")
    
    def update_results(self, detections):
        '''
        updates the detections to the Results dict.
        '''
        try:
            for cam_id in detections:
                
                self.results[cam_id] = detections[cam_id]
                logs.info(f"Updated results for cam_id : {cam_id}")
        except:
            traceback.print_exc()
            logs.error("Error in updating results")

    def _add_raw_b64_to_response(self, data, responses):
        """
        Response should be in dictionary format with camera id as the keys and results as values
        Adds raw base64 data to the json received from server
        """
        data = json.loads(data)
        responses = json.loads(responses)
        print(responses.keys())
        for key in data["batch"].keys():
            resp_j = responses[key]
            resp_j["img"] = data["batch"][key]['base64']
            responses[key] = resp_j
        return responses
        
    
    # Post batch of images to server, and receive the same.
    def post(self, data: str):
        """
        Post data to the server in batches

        data format :
        {"batch": {"cam_1": self.frames["cam_1"],
                    "cam_2": self.frames["cam_2"],
                    "cam_3": self.frames["cam_3"],
                    ...
                    ...
                    "cam_n": self.frames["cam_n"],}
        """
        try:
            headers = {'Content-Type':'application/json'}              
            r.set("batch", data)
            r.set("batch_status", '1')
            while r.get("result") != '1':
                time.sleep(0.001)
            
            try:
                responses = r.get("processed_batch")
                r.set("result", '0')
                logs.info("Received results from the server.")
            except:
                traceback.print_exc()
                logs.error("Error in fetching batch results from redis")
            responses = self._add_raw_b64_to_response(data, responses)
            return responses
        except:
            traceback.print_exc()
            logs.error("Failed to post response to the server.")

    def create_batch(self):
        """
        Create batch by iterating over the Camera frames from frames dict.
        After a frame is read, it is erased from the frames dict.
        """
        while True:
            try:    
                # Create list of cameras for every batcher, this list would be different for every batcher thread
                # number of batcher thread correspond to number of workers
                worker_cam_list = list(self.frames.keys())
                worker_cam_list = [worker_cam_list[i::int(self.common_config["workers"])] for i in range(int(self.common_config["workers"]))]
                worker_cam_list = worker_cam_list[self.id]
                keys = cycle(worker_cam_list)
                
                data = {"batch": {}}
                i = 0
                if self.batch_size > 1:
                    logs.debug("Starting to build batch")
                    while i < self.batch_size:
                        key = next(keys)
                        # Only add to data if the frame is not empty
                        # After adding to data, clear the frame
                        if self.frames[key]:
                            data["batch"][f"{self.frames[key]['name']}"] = self.frames[key]
                            self.frames[key] = None
                            i += 1
                            logs.debug("frame added to batch")
                    logs.info("Sending Batch for processing")
                    self.process(json.dumps(data))
                
                # Special case when batch size is 1 and camera is also 1.
                elif self.batch_size == 1 and len(worker_cam_list)==1:
                    key = worker_cam_list[0]
                    if self.frames[key] != None:
                        data["batch"][f"{self.frames[key]['name']}"] = self.frames[key]
                        self.frames[key] = None
                    logs.info("sending batch for processing")
                    self.process(json.dumps(data))

                time.sleep(0.1)

            except:
                traceback.print_exc()
                logs.error("Failed to create batch")

    def start_batch(self):
        '''
        Start batch thread
        '''
        logs.warning("Starting thread for Batcher")
        try:
            self.batch = kthread.KThread(target=self.create_batch, args=())
            self.batch.daemon = True
            self.batch.start()
        except:
            traceback.print_exc()
            logs.error("Error starting Batch thread")
