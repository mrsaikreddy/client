import os
import time
import json
import random
import queue
import asyncio
import requests
import traceback
import threading
import kthread
import cv2 as cv
from utils.add_datetime import run_fd_time
from datetime import datetime

from ThreadedCamera import ImageOps
from logs import logs

logs = logs.logger
lock = threading.Lock()

import numpy as np

class KThreadedCamera:
    def __init__ (self, camconfig_, commonConfig_, frames, results) -> None:
        try:
            
            assert camconfig_, commonConfig_

            self.id_ = camconfig_["CameraId"]
            logs.info("Setting up camera config %s",self.id_)
            self.cam_name_ = camconfig_["CamName"]
            self.address = camconfig_["Address"]
            self.requestSession = requests.Session()
            self.timeout = 3
         
            self.testLevel = commonConfig_["TestingLevel"]
            self.clientName = commonConfig_["ClientName"]
            self.globalEnableNotification = commonConfig_["enableAlert"]
            self.globalEnableTraining = commonConfig_["enableTraining"]
            self.globalEnableSpeaker = commonConfig_["enableSpeaker"]
            self.globalSaveViolationImage = commonConfig_["sav_vio_img"]
            self.globalSaveAllInputImages = commonConfig_["save_all_inp_img"]
            self.globalCameraDelay = int(commonConfig_["CamDelay"])
            self.dataFrame = cv.imread(commonConfig_["frameFile"])

            if self.testLevel == 1 or self.testLevel == 2:
                self.alertUrl = commonConfig_["test_url"]
            else:
                self.alertUrl = commonConfig_["alert_url"]
            
            self.audioKey = commonConfig_["audio_key"]
            self.enableGlobalROI = commonConfig_["ROI_en"]
            self.enableGlobalROIcrop = commonConfig_["ROI_crop_en"]
            self.alert2train = commonConfig_["Alert2Train"]
            self.recommendations = commonConfig_["recommendations"]


            self.check_for = camconfig_["Detection"]
            self.cameraDelay = max(int(camconfig_["CamDelay"]), self.globalCameraDelay)
            self.points = camconfig_['points']
            self.thresh_limit_x = camconfig_['sd_thresh_limit_x']
            self.thresh_limit_y = camconfig_['sd_thresh_limit_y']

            if "SocialDistancing" in camconfig_:
                self.SDarea=camconfig_["SocialDistancing"]
                self.enableSocialDistancing = True
            else:
                self.SDarea="NA"
                self.enableSocialDistancing = False       

            self.ROI = camconfig_["ROI"]
            self.ROI_crop_en = camconfig_["ROI_crop_en"] and self.enableGlobalROIcrop
            if self.ROI !="NA":
                self.ROI_en = True and self.enableGlobalROI
            else:
                self.ROI_en = False
            self.speakerLink = camconfig_["Speaker"]
            self.isSpeakerEnabled = camconfig_["en_spkr"] and self.globalEnableSpeaker and self.speakerLink != "NA"
            self.input_image_count = 0
            logs.debug(self.address)
            self.token = "hf4tNLYMVpdCtg6B8YJk" 
        except:
            traceback.print_exc()
            logs.error("Config parameters wrong. Please check settings again")


        self.activeStatus = True
        self.lastImage = None
        self.src = self.address
        self.id = str(self.id_)
        self.retryDelay = 10
        self.FPS = 1/100
        self.FPS_MS = int(self.FPS * 1000)
        self.count = 0
        self.count_save = 0
        
        self.capture = None 
        curTime = int(time.time())
        self.lastCheckTime = curTime
        
        self.lastImageTime = curTime
        self.cam_connected = False
        self.activeTimeout = 30
        #combined batch of frames has the latest information for each camera 
        self.combined_batch_of_frames = frames
        self.Results = results
    
    def startCapture(self):
        '''
        Starts buffering from the camera object using cv2 Video Capture
        Update time when frames are captured
        '''
        try:
            logs.debug("Starting camera -> %s",self.id)
            self.capture = cv.VideoCapture(self.src)
            self.capture.set(cv.CAP_PROP_BUFFERSIZE, 2)
            self.lastCheckTime = int(time.time())
        except:
            traceback.print_exc()
            logs.error("Unable to start the camera -> %s", self.id)

    def restartCapture(self):
        '''
        Try restarting the camera
        '''
        logs.warning("restarting camera -> %s",self.id)
        try:
            self.capture.release()
         
        except:
            traceback.print_exc()
            logs.error("unable to release the camera -> %s", self.id)
        time.sleep(1)
        try:
            self.startCapture()
        except:
            traceback.print_exc()
            logs.error("unable to restart the camera -> %s", self.id)

    def startThread(self):
        '''
        Initialize threads for both camera updates and camera operations.
        '''
        # Log that the thread is starting
        logs.warning("Starting thread for camera -> %s", self.id)
        try:
            # Create a new thread for camera updates
            self.thread = kthread.KThread(target=self.update, args=())
            self.thread.daemon = True
            self.thread.start()
        except:
            traceback.print_exc()
            logs.error("Error starting Update Thread for cam -> %s", self.id)
        time.sleep(1)
        try:
            # Create a new thread for camera operations
            self.thread3 = kthread.KThread(target=self.operationThread, args=())
            self.thread3.daemon = True
            self.thread3.start()
        except:
            traceback.print_exc()
            logs.error("Error starting Operate Thread for cam -> %s", self.id)
        time.sleep(1)

    def speaker_alert(self, json):
        '''
        Sends alert messages to the speaker system if any detected violations are found.
        '''
        # Split the detection criteria and loop through to find violations
        ToDetect = self.check_for.split(":")
        for det in ToDetect:
            if det in json:
                logs.info("found %s violation", det)
                if self.isSpeakerEnabled:
                    # API call to speaker system
                    key = self.audioKey[det]
                    header_speaker = {'Content-type':'text/plain'}
                    response = self.requestSession.post(self.speakerLink, headers=header_speaker, data=key, timeout=2.5)
                    logs.info("speaker response -> %s", response)
                return True
        return False

    def violation_alert(self, json):
        '''
        Checks for violations in the received data, returns True if a violation is found.
        '''
        # Split the detection criteria and loop through to find violations
        ToDetect = self.check_for.split(":")
        for det in ToDetect:
            if det in json:
                logs.info("found %s violation", det)
                return True
        return False

    def camAlive(self):
        '''
        Checks if the camera is alive and connected to the cloud, sends a message to the cloud if it is.
        '''
        try:
            # If token is not available, get a new one
            if self.token == "NA":
                ImageOps.get_token(self.requestSession)
            # Send a 'camera alive' message to the cloud
            payload = {
                'client_name': self.clientName,
                'cam_id': self.cam_name_,
                'alive': 'TRAKR-AI-CAM-ALIVE'
            }
            headers = {
                'X-Authorization': self.token,
                'Accept': 'application/json'
            }
            ImageOps._(requestSession=self.requestSession, url=self.alertUrl, headers=headers, data=payload)
            return True
        except:
            traceback.print_exc()
            logs.error("Error in sending camera not reachable data to cloud")
            return False

    def serverAlive(self):
        '''
        Check if TRAKR-AI-SERVER is alive or not
        '''
        try:
            #Camera not reachable
            if self.token=="NA":
                ImageOps.get_token(self.requestSession)
            payload = {
                'client_name':self.clientName,
                'alive':'TRAKR-AI-SERVER'
            }
            headers = {
                'X-Authorization': self.token,
                'Accept': '*/*',
                'Accept': 'application/json'
            }
            logs.debug("Server is working")
            ImageOps.post_cloud(requestSession=self.requestSession,url=self.alertUrl,headers=headers,data=payload)
            return True
            #Speaker not reachable
        except:
            traceback.print_exc()
            logs.error("Error in server not reachable data to cloud")
        return False

    def not_reachable(self,type):
        '''
        Send error message to cloud about whether cam or speaker are reachable or not
        '''
        try:
            #Camera not reachable
            if type=="CAM":
                if self.token=="NA":
                    ImageOps.get_token(self.requestSession)
                payload = {
                    'client_name':self.clientName,
                    'cam_id':self.cam_name_,
                    'status':'Camera:: '+self.cam_name_+' Not Reachable'
                }
                headers = {
                    'X-Authorization': self.token,
                    'Accept': '*/*',
                    'Accept': 'application/json'
                }
                logs.error("Camera is not reachable")
                ImageOps.post_cloud(requestSession=self.requestSession,url=self.alertUrl,headers=headers,data=payload)
                return True
            #Speaker not reachable
            elif type=="SPK":
                if self.token=="NA":
                    ImageOps.get_token(self.requestSession)
                payload = {
                    'client_name':self.clientName,
                    'cam_id':self.cam_name_,
                    'status':'Speaker for camera:: '+self.cam_name_+' Not Reachable'
                }
                headers = {
                    'X-Authorization': self.token,
                    'Accept': '*/*',
                    'Accept': 'application/json'
                }
                ImageOps.post_cloud(requestSession=self.requestSession,url=self.alertUrl,headers=headers,data=payload)
                return True
            
        except:
            traceback.print_exc()
            logs.error("Error in sending camera not reachable data to cloud")
        return False

    def violation_cloud_data(self, img_json, detection, aidata):
        '''
        Send violation-related data to a cloud service if alerting is enabled
        and enough time has passed since the last sent alert.
        '''
        try:
            if self.isAlertEnabled:
                current_time = int(time.time())
                # Check if enough time has passed since the last alert was sent
                if current_time - self.last_violation_cloud_sent > self.pauseAlertTime:
                    self.last_violation_cloud_sent = current_time
                    logs.info("alert is enabled")
                    if self.token == "NA":
                        ImageOps.get_token(self.requestSession)
                    
                    payload = {
                                'client_name': self.clientName,
                                'cam_id': self.cam_name_,
                                'system_detection_time': aidata['system_detection_time'],
                                'detection_img': img_json,
                                'raw_img': aidata['img'],
                                'bbox' :aidata['bbox'],
                                'check_for': self.check_for,
                    }
                    
                    headers = {
                        "accept": "application/json",
                        "Content-Type": "application/json"
                    }
                    
                    # Send the payload to cloud storage and get the response
                    resp = ImageOps.save_image_hapi(requestSession=self.requestSession, url=self.alert_storage_ip, headers=headers, data=payload)
                    
                    logs.info(f"CLOUD RESPONSE {resp}")
                    
                    # Save payload to a JSON file for debugging or reference
                    with open('sample_packet_violation.json', 'w') as json_file:
                        json.dump(payload, json_file, indent=4)

                    ImageOps.post_cloud(requestSession=self.requestSession, url=self.alertUrl, headers=headers, data=resp)
                    
                    return True
        except:
            traceback.print_exc()
            logs.error("Error in sending violation data to cloud")
        return False

    # Similar structure as above, but for training data
    def train_cloud_data(self, img_json, detection, aidata):
        '''
        Sends training data to a cloud service, subject to certain conditions.
        '''
        try:
            # Checks if the training feature is enabled
            if self.isTrainingEnabled:
                current_time = int(time.time())
                
                # Verifies if sufficient time has elapsed to send another training packet
                if current_time - self.last_train_cloud_sent > self.pauseTrainTime:
                    self.last_train_cloud_sent = current_time
                    
                    # Retrieves a new token if one doesn't exist
                    if self.token == "NA":
                        ImageOps.get_token(self.requestSession)

                    payload = {
                        'client_name': self.clientName,
                        'cam_id': self.cam_name_,
                        'system_detection_time': aidata['system_detection_time'],
                        'raw_img': img_json,
                    }
                
                    headers = {
                        'X-Authorization': self.token,
                        'Accept': 'application/json'
                    }

                    # Writes payload to a sample JSON file for reference
                    with open("sample_packet.json", "w") as outfile:
                        json.dump(payload, outfile, indent=4)
                    
                    # Saves the image to storage and receives an S3 key for the image
                    img_address = ImageOps.save_image_hapi(self.requestSession, self.train_storage_ip, headers, payload)
                    img_address = img_address['key']
                    
                    payload['raw_img'] = img_address
                    
                    ImageOps.post_cloud(self.requestSession, self.trainUrl, headers, payload)
                    
                    return True
        except:
            traceback.print_exc()
            logs.error("Error in sending training data to cloud")
        return False

    def out_save_detection_frame(self, frame, name):
        '''
        Saves detection frames to disk, if the save feature is enabled.
        '''
        try:
            if self.activateSaveDetectionImages:
                path = self.checkdir(self.cam_name_, "detections")
                filename = f"{path}detection{name}_{self.detection_image_count}.jpg"
                status = cv.imwrite(filename, frame)
                
               
                self.detection_image_count += 1
                logs.debug(f"saving detection image -> {filename}")
                return status
            return False
        except:
            traceback.print_exc()
            logs.error("Error in saving detection image")

    def checkdir(self, cam_id, type):
        '''
        Checks if the directory exists for a specific camera and type, 
        and creates it if it doesn't.
        '''
        try:
            now = datetime.now()
            path = f"/app/Syslogs{now.strftime('/%Y/%m/%d/')}{cam_id}/{type}/"
            if not os.path.isdir(path):
                os.makedirs(path)
            return path
        except:
            traceback.print_exc()
            print("error in folder creation")

    def out_save_violation_frame(self, frame, name):
        '''
        Saves frames where a violation was detected, if the feature is enabled.
        '''
        try:
            if self.activateSaveViolationImage:
                path = self.checkdir(self.cam_name_, "violations")
                filename = f"{path}violation{name}_{self.violation_image_count}.jpg"
                status = cv.imwrite(filename, frame)
                
            
                self.violation_image_count += 1
                logs.debug(f"saving violation image -> {filename}")
                return status
        except:
            traceback.print_exc()
            logs.error("Error in saving violation image")

    def operationThread(self):
        '''
        Continuously checks for violations and triggers alerts.
        '''
        self.lastOperatePrint = int(time.time())
        while True:
            try:
                self.check_violations_and_alert()
            except:
                traceback.print_exc()

    def check_violations_and_alert(self):
        '''Check for violations in the camera feed, log them, and alert as necessary.'''
        try:
            # Convert camera delay from milliseconds to seconds and sleep
            cam_delay_seconds = self.cameraDelay / 1000
            time.sleep(cam_delay_seconds)
            
           
            cur_time = int(time.time())
            in_active_time = cur_time - self.lastCheckTime
            
           
            if cur_time - self.lastOperatePrint > 10:
                self.lastOperatePrint = cur_time
                logs.debug("In the check_violations_and_alert thread -> %s", self.id)
            
            
            if self.activeStatus:
                logs.debug("Thread is active with status %d", self.activeStatus)
                
                # Check if there are any new results
                if self.Results.get(str(self.id_)):
                    # Retrieve AI results
                    aidata = self._check_results()
                    logs.info("Detections: %s -> %s", aidata["totalDetection"], aidata.keys())
                    
                    # If any violations detected, process them
                    if int(aidata["totalDetection"]) > 0:
                        self.process_violations(aidata)
                        
                   
                    if 'social_distancing' in aidata.keys():
                        self.process_social_distancing_violations(aidata)
                else:
                    time.sleep(0.1)
                    logs.debug("No result received")
                    
        except Exception as e:
            traceback.print_exc()
            logs.error(f"Error in check_violations_and_alert: {str(e)}")

    def process_violations(self, aidata):
        '''Handle regular violations.'''
     
        detections = aidata["DetectionPerClass"].lower()
    
        self.alert_and_save(detections, aidata)

    def process_social_distancing_violations(self, aidata):
        '''Handle social distancing violations.'''
      
        sd_detections = aidata["social_distancing"]['DetectionPerClass'].lower()
     
        self.alert_and_save(sd_detections, aidata, is_social_distancing=True)

    def alert_and_save(self, detections, aidata, is_social_distancing=False):
        '''Alert and save violations to the cloud.'''
       
        speaker_alert = self.speaker_alert(detections)
        violation_found = self.violation_alert(detections)

        # If violations found, prepare to send data to cloud
        if violation_found:
          
            frame = self.prepare_frame(aidata, is_social_distancing)
            frame_json = ImageOps.img2base64(frame)

            # Save violation data to cloud
            self.violation_cloud_data(frame_json, detections, aidata)
            
            # If set to alert the training system, do so
            if self.alert2train:
                raw_frame_json = aidata["img"]
                self.train_cloud_data(raw_frame_json, detections, aidata)
            
            self.out_save_violation_frame(frame, str(self.id))

    def prepare_frame(self, aidata, is_social_distancing=False):
        '''Prepare the frame for appending results and recommendations.'''
     
        if is_social_distancing:
            orig_frame = ImageOps.base64_2img(aidata['social_distancing']['outimage'])
        else:
            orig_frame = ImageOps.base64_2img(aidata["outimage"])
        resize_dataFrame = ImageOps.image_resize(self.dataFrame, height=orig_frame.shape[0])
        frame = ImageOps.appendFrame(orig_frame, resize_dataFrame)
        # Append results and recommendations to the frame for final presentation
        return ImageOps.appendResult(frame, self.check_for, detections, self.recommendations, self.cam_name_)


    def save_frame(self):
        '''
        Save frame if the camera is active, otherwise log that the camera is inactive.
        '''
        try:
            
            curTime = int(time.time())
            
           
            inActiveTime = curTime - self.lastCheckTime
            boolPrintStatus = False
            if curTime - self.lastSavePrint > 10:
                self.lastSavePrint = curTime
                boolPrintStatus = True
                logs.debug("In the Save thread -> %s", self.id)

            if self.activeStatus:
              
                if self.count_save % 15 == 0:
                    count = self.count
                    filename = "in_" + self.id + "_" + str(count) + '.jpg'
                
                    self.count += 1
                    if self.count > 100:
                        self.count = 0
                    
                    frame = self.lastImage
                    
                  
                    if frame is not None and frame.shape[1] > 200:
                        logs.info("Image saved %s", filename)
                        frame = run_fd_time(frame)
                        status = cv.imwrite(filename, frame)

            else:
                inActiveTime = curTime - self.lastImageTime
                if inActiveTime > self.activeTimeout:
                    time.sleep(1)
                    if boolPrintStatus:
                        logs.error("Camera %s is inactive for more than %s seconds", self.id, int(inActiveTime))

        except:
            logs.error("Error in saving frame")
    
    def _check_movement(self, img):
        '''
        Check for movement between consecutive frames.
        '''
        try:
            if self.lastImage is None:
                self.lastImage = img

            # Convert to grayscale and find absolute difference
            gray1, gray2 = cv2.cvtColor(self.lastImage, cv2.COLOR_BGR2GRAY), cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            difference = cv2.absdiff(gray1, gray2)
            self.lastImage = img

            thresh_frame = cv2.threshold(difference, thresh=20, maxval=255, type=cv2.THRESH_BINARY)[1]

            total_white_pixels = np.sum(thresh_frame == 255)

         
            if total_white_pixels > 20000:
                logs.info(f"Detected changes in {total_white_pixels} pixels in camera ID {self.id_}")
                return True
            else:
                return False
            
        except Exception as e:
            logs.exception(f"Couldn't check difference between frames: {e}")

    def _add_to_frames(self, img):
        try:
            # Uncomment this if you'd like to check for movement: if self._check_movement(img):
            if 1:  # Currently bypasses movement check
                img, data = self.prepare_img_and_data(img)
                
                with lock:
                    # Writes the current frame data to the shared dictionary
                    logs.warning("Data is populated in self. Frames")
                    self.combined_batch_of_frames[self.id_] = data
                    
                logs.info(f"Added image with ID: {data['imgID']} to frames.")
                
            else:
                logs.info(f"No difference in frames, not adding image from Camera ID: {self.id_}")
                with lock:
                    self.combined_batch_of_frames[self.id_] = None
                    
        except Exception as e:
            traceback.print_exc()
            logs.error("Error in adding new image to frames inside update thread.")
            
    def prepare_img_and_data(self, img):
        # Handle ROI and crop settings if enabled
        if self.ROI_en and self.ROI_crop_en and self.ROI != "NA":
            roi = self.ROI.replace(" ", "").split(":")
            img = img[int(roi[1]):int(roi[1]) + int(roi[3]), int(roi[0]):int(roi[0]) + int(roi[2])]
            
        b64string = ImageOps.img2base64(img)
        height, width, channels = img.shape
        
        ROI_points = self.initialize_ROI_points(height, width)
        
        # Prepare data dictionary to hold frame attributes
        data = {
            'base64': b64string,
            'name': self.id_,
            'imgID': str(self.input_image_count),
            'checkfor': self.check_for,
            'ROI': ROI_points,
            'enSave': 0,
            'points': self.prepare_points(),
            'sd_thresh_limit_x': self.thresh_limit_x,
            'sd_thresh_limit_y': self.thresh_limit_y
        }
        
        return img, data

    def initialize_ROI_points(self, height, width):
        if self.ROI_en and not self.ROI_crop_en:
            return self.ROI.split(":")
        else:
            self.ROI = f"0,0:0,{height}:{width},{height}:{width},0"
            return self.ROI.split(":")
            
    def prepare_points(self):
        return self.SDarea.split(":") if self.enableSocialDistancing else self.points

    

    def update(self):
        self.startCapture()
        self.lastUpdatePrint = int(time.time())
        logs.debug(f"Starting Update Thread -> {self.id}")

        while True:
            curTime = int(time.time())
            
           
            if curTime - self.lastUpdatePrint > 10:
                self.serverAlive()
                self.lastUpdatePrint = curTime

            if self.capture.isOpened():
                # Camera is active; grab and process frames
                if curTime - self.lastCheckTime < self.activeTimeout:
                    logs.info(f"Camera {self.id} is opened, count_save -> {self.count_save}")
                    
                    for i in range(10):  
                        self.capture.grab()
                    
                    (self.status, self.frame) = self.capture.retrieve()
                    
                    # Verify frame and add to queue if valid
                    if self.frame is not None and self.frame.shape[1] > 200 and self.status:
                        self.activeStatus = True
                        self.input_image_count += 1
                        self._add_to_frames(self.frame)
                        self.lastCheckTime = curTime
                        self.lastImageTime = curTime
                        self.cam_connected = True
                        self.count_save += 1
                        if self.count_save > 1200:
                            self.count_save = 0
                    
                    time.sleep(0.1) 
                else:
                    # Camera is not reachable; restart capture
                    self.activeStatus = False
                    self.cam_connected = False
                    self.restartCapture()
            else:
                # Capture is not opened; restart if camera is not reachable
                if curTime - self.lastCheckTime > self.activeTimeout:
                    self.activeStatus = False
                    self.cam_connected = False
                    self.restartCapture()



    def terminate(self):
        try:
            self.thread.terminate()
        except:
            logs.error("Error in terminating thread")
            
    def show_frame(self):
        cv.imshow('frame', self.frame)
        cv.waitKey(self.FPS_MS)

    def get_frame_file(self):
        count = self.count
        if self.count > 100:
            count = 0 
        filename = "in_"+self.id+"_"+str(count)+'.jpg'
        print("reading file:",filename)
        return filename

    def  set_last_image_time(self,time):
        self.lastImageTime = time

    def  get_last_image_time(self):
        return self.lastImageTime
    
if __name__ == '__main__':
    src = 'rtsp://172.17.0.1:8554/mystream'
    queue = queue.LifoQueue(maxsize=100)
    threaded_camera = KThreadedCamera(src,queue)
    while True:
        try:
            if int(time.time())-threaded_camera.get_last_image_time() >30:
                print ("Timeout:: thread terminating  and restarting")
                threaded_camera.terminate()
                threaded_camera = KThreadedCamera(src,queue)
            threaded_camera.save_frame()
            time.sleep(1)

        except AttributeError:
            pass
