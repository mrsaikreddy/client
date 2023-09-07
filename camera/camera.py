import json
import time
import os
import ipaddress
import queue
import asyncio
import base64
import aiohttp
import aioping
import traceback
import requests
import math
import ffmpeg
import cv2 as cv
import numpy as np

from datetime import datetime

from ThreadedCamera.kthreadcam import KThreadedCamera

from logs import logs

logs = logs.logger

class Camera:
    '''
    Camera object, handles all the camera level configuration and testing
    '''
    def __init__(self, camconfig_, commonConfig_, threading_state, frames, results) -> None:
        try:
            assert camconfig_,commonConfig_
            self.threading_state = threading_state
            self.camconfig = camconfig_
            if self.threading_state is False:
                self.cap = cv.VideoCapture(self.address_)
                self.width  = self.cap.get(cv.CAP_PROP_FRAME_WIDTH)   # float `width`
                self.height = self.cap.get(cv.CAP_PROP_FRAME_HEIGHT)  # float `height`
            else:
                #self.threaded_camera = ThreadedCamera(self.address_, self.id_, queue)
                #self.threaded_camera = KThreadedCamera(camconfig_, commonConfig_, frames, results, roi_frames)
                self.threaded_camera = KThreadedCamera(camconfig_, commonConfig_, frames, results)
                #self.threaded_camera = KThreadedCamera(self.address_, self.id_, self.queue)

        except:
            traceback.print_exc()
            logs.error("Config parameters wrong. Please check settings again")
            
    def startcam(self):
        '''
        Start camera thread
        '''
        #self.threaded_camera.startCapture()
        self.threaded_camera.startThread()

    def members(self):
        all_members = self.__dict__.keys()
        return [ (item, self.__dict__[item]) for item in all_members if not item.startswith("_")]

    def checktime(self):
        
        current_epoch = int(time.time())
        if current_epoch-self.image_sample_time > self.cameraDelay:
            self.image_sample_time = current_epoch
            return True
        return False            

    def __str__(self):
        return self.camconfig['CamName']

    def get_token(self):
        try:
            url = 'https://app.trakr.live/api/auth/login'
            loginDetails = {
                "username": "testing@trakr.live",
                "password": "HACK@LAB"
            }
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            req = self.post_url(url=url, headers=headers, data=loginDetails)
            #req_data = await req.json()
            self.token = 'Bearer ' + str(req['token'])
        except:
            traceback.print_exc()
            logs.error("Error in getting token")

    def img2base64(self,frame):
        try:
            retval, buffer = cv.imencode('.jpg', frame)
            b64string = base64.b64encode(buffer).decode("utf-8")
            return b64string
        except:
            traceback.print_exc()
            logs.error("Error in converting image to base64")


    def base64_2img(self,base64str):
        try:
            frame = base64.b64decode(base64str)
            jpg_as_np = np.frombuffer(frame,dtype=np.uint8)
            frame =cv.imdecode(jpg_as_np,flags=1)
            return frame
        except:
            traceback.print_exc()
            logs.error("Error in converting base64 to image")
        

    def post_url(self,url,headers,data):
        try:
            logs.debug("Inside post url %s",url)
            #resp = requests.post(url=url, json=data,headers=headers,timeout=self.timeout)
            resp = self.requestSession.post(url=url, json=data,headers=headers,timeout=self.timeout)
            resp = resp.json()
            return resp
        except:
            traceback.print_exc()
            logs.error("Error in posting data to %s",url)

    def post_cloud(self,url,headers,data):
        try:
            logs.debug("Inside post url %s",url)

            resp = self.requestSession.post(url=url, json=data,headers=headers,timeout=self.timeout)
            return resp
        except:
            traceback.print_exc()
            logs.error("Error in posting data to %s",url)

    def read_from_file(self,filename):
        return cv.imread(filename)    


    def read_frame_as_jpg(self):
        #logs.info("reading image from stream -> %s",self.address_)
        if not self.threading_state:
            out, err = (
                ffmpeg
                .input(self.address_)
                .filter_('select', 'gte(n,{})'.format(1))
                .output('pipe:', vframes=1, format='image2', vcodec='mjpeg')
                .run(capture_stdout=True)
            )
            return out
        else:
            try:
                if int(time.time()) - self.threaded_camera.get_last_image_time() > 30:
                    try:
                        logs.error ("%s ->Timeout:: thread terminating  and restarting",self.id_)
                
                        self.threaded_camera.terminate()
                    except:
                        logs.error("Error in termicating camera")
                
                    logs.error("Threaded camera not present -> %s",self.id_)
                    try:
                        self.threaded_camera = KThreadedCamera(self.address_, self.id_, self.queue)
                    except:
                        logs.error("Error starting threaded camera -> %s",self.id_)
            except:    
                logs.error("error in setting up camera ")
                
            filename = self.threaded_camera.get_frame_file()
            frame = self.read_from_file(filename)
            return frame
    
    def image_resize(self,image, width = None, height = None, inter = cv.INTER_AREA):
        # initialize the dimensions of the image to be resized and
        # grab the image size
        dim = None
        (h, w) = image.shape[:2]

        # if both the width and height are None, then return the
        # original image
        if width is None and height is None:
            return image

        # check to see if the width is None
        if width is None:
            # calculate the ratio of the height and construct the
            # dimensions
            r = height / float(h)
            dim = (int(w * r), height)

        # otherwise, the height is None
        else:
            # calculate the ratio of the width and construct the
            # dimensions
            r = width / float(w)
            dim = (width, int(h * r))

        # resize the image
        resized = cv.resize(image, dim, interpolation = inter)

        # return the resized image
        return resized

    


    def ai_operation(self, img):
        try:
            if self.ROI_en and self.ROI_crop_en: 
                if self.ROI !="NA":
                    roi = self.ROI.replace(" ","").split(":")
                    #print(roi)
                    img = img[int(roi[1]):int(roi[1])+int(roi[3]), int(roi[0]):int(roi[0])+int(roi[2])]

            #img = await self.image_resize(img,height=720)
            #img = cv.resize(img,(1280,720),interpolation =Full cv.INTER_AREA)
            b64string = self.img2base64(img)
            height,width,channels = img.shape
                
            if self.enableSocialDistancing:
                if self.ROI_en and not self.ROI_crop_en:
                    ROI_points = self.ROI.split(":")
                else:
                    self.ROI = "0,0:0,"+str(height)+":"+str(width)+","+str(height)+":"+str(width)+",0"
                    ROI_points = self.ROI.split(":")
                logs.warning("%s, %s -> Full image ROI -> %s", self.id_,self.cam_name_, ROI_points)
                calibration_points = self.SDarea.split(":") 
                data = {
                    'base64':b64string,
                    'points':calibration_points,
                    'name':self.id_,
                    'imgID':str(self.input_image_count),
                    'checkfor':self.check_for,
                    'ROI':ROI_points
                    }
                headers = {'Content-Type':'application/json'}
                response = self.post_url(url=self.serverIP+"socialdist",headers=headers,data=data)
            else:
                if self.ROI_en and not self.ROI_crop_en:
                    ROI_points = self.ROI.split(":")
                else:
                    self.ROI = "0,0:0,"+str(height)+":"+str(width)+","+str(height)+":"+str(width)+",0"
                    ROI_points = self.ROI.split(":")
                logs.warning("%s, %s -> Full image ROI -> %s", self.id_,self.cam_name_, ROI_points)
                    #logs.warning("Full image ROI -> %s", ROI_points)
                data = {
                    'base64':b64string,
                    'name': self.id_,
                    'imgID':str(self.input_image_count),
                    'checkfor':self.check_for,
                    'ROI':ROI_points
                    }
                headers = {'Content-Type':'application/json'}
                response = self.post_url(url=self.serverIP+"detect", headers=headers,data=data)
            response_j = json.loads(response)
            response_j["img"]=b64string
            return response_j
        except:
            traceback.print_exc()
            logs.error("Error in ai operation handling")

    def retrieve_frame(self):
        return self.cap.retrieve()
        


    def get_cam_id(self):
        return self.id_

    def cam_delay(self):
        time.sleep(self.cameraDelay)



    def empty_queue(self,queue_):
        try:
            logs.info("%s -> Queue size -> %s", self.id_,queue_.qsize())
            while queue_.qsize() > 0:
                queue_.get()
            logs.info("%s -> Queue is empty -> %s",self.id_,queue_.qsize())
        except:
            traceback.print_exc()
            logs.error("Error in emptying queue")


    def in_save_frame(self, frame, name):
        try:
            if self.activateSaveAllInputImages:
                logs.info("save image -> %s",self.input_image_count )
                path = self.checkdir(self.cam_name_,"input")
                filename = path+"in"+name+"_"+str(self.input_image_count)+'.jpg'
                status = cv.imwrite(filename,frame)
                self.input_image_count = self.input_image_count + 1
                return status
            return False
        except:
            traceback.print_exc()
            logs.error("Error in saving input image")


    def checkdir(self, cam_id, type):
        try:
            now = datetime.now()
            path = "/app/Syslogs"+now.strftime("/%Y/%m/%d/")+str(cam_id)+"/"+type+"/"
            if not os.path.isdir(path):
                os.makedirs(path)
            return path
        except:
            traceback.print_exc()
            print("error in folder creation")
        
    def out_save_violation_frame(self, frame, name):    
        try:
            if self.activateSaveViolationImage:
                path = self.checkdir(self.cam_name_,"violations")
                filename = path+"violation"+name+"_"+str(self.violation_image_count)+'.jpg'
                status = cv.imwrite(filename,frame)
                self.violation_image_count = self.violation_image_count + 1
                logs.debug("saving violation image -> %s",filename)
                return status
        except:
            traceback.print_exc()
            logs.error("Error in saving violation image")
            
    def out_save_detection_frame(self, frame, name):
        try:
            if self.activateSaveDetectionImages:
                path = self.checkdir(self.cam_name_,"detections")
                filename = path+"detection"+name+"_"+str(self.detection_image_count)+'.jpg'
                status = cv.imwrite(filename,frame)
                self.detection_image_count = self.detection_image_count + 1
                logs.debug("saving detection image -> %s",filename)
                return status
            return False
        except:
            traceback.print_exc()
            logs.error("Error in saving detection image")

    def get_url(self,url):
        resp = self.requestSession.get(url=url)
        resp = resp.json()
            #print(resp)

   

    
    def speaker_alert(self,json):
        try:
            ToDetect = self.check_for.split(":")
            print(ToDetect)
            for det in ToDetect:
                if det in json:
                    logs.info("found %s violation",det)
                    if self.isSpeakerEnabled:
                        key = self.audioKey[det]
                        header_speaker = {'Content-type':'text/plain'}
                        response = self.requestSession.post(self.speakerLink, headers=header_speaker, data=key, timeout=2.5)
                        #response = await self.post_url(session=session,url=self.speakerLink,headers=header_speaker,data=key)
                        logs.info("speaker response -> %s",response)
                    return True
            return False
        except:
            traceback.print_exc()
            logs.error("Error in sending speaker alert")


    def violation_cloud_data(self,img_json,detection):
        try:
            if self.isAlertEnabled:
                current_time = int(time.time())
                if current_time - self.last_violation_cloud_sent > self.pauseTrainTime:
                    self.last_violation_cloud_sent = current_time
                    logs.info("alert is enabled")
                    if self.token=="NA":
                        self.get_token()
                    payload = {
                                'ClientName':self.clientName,
                                'cam_id':self.cam_name_,
                                'img':img_json,
                                'Detections':detection,
                                'checkFor':self.check_for
                    }
                    headers = {
                        'X-Authorization': self.token,
                        'Accept': '*/*',
                        'Accept': 'application/json'
                    }
                    self.post_cloud(url=self.alertUrl,headers=headers,data=payload)
                    return True
        except:
            traceback.print_exc()
            logs.error("Error in sending violation data to cloud")
        return False

    def train_cloud_data(self,img_json,detection):
        try:
            if self.isTrainingEnabled:
                current_time = int(time.time())
                if current_time - self.last_train_cloud_sent > self.pauseTrainTime:
                    self.last_train_cloud_sent = current_time
                    if self.token=="NA":
                        self.get_token()
                    payload = {
                                'ClientName':self.clientName,
                                'cam_id':self.cam_name_,
                                'img':img_json,
                                'Detections':detection,
                                'checkFor':self.check_for
                    }
                    headers = {
                        'X-Authorization': self.token,
                        'Accept': '*/*',
                        'Accept': 'application/json'
                    }
                    self.post_cloud(url=self.trainUrl,headers=headers,data=payload)
                    return True
        except:
            
            traceback.print_exc()
            logs.error("Error in sending training data to cloud")
        return False
