import json
import time
import os
import traceback
import requests
import asyncio
import base64

import cv2 as cv
import numpy as np

from config.config import Configuration
from datetime import datetime
from packaging import version

from logs import logs

logs = logs.logger


def get_token(requestSession):
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
            req = post_url(requestSession=requestSession,url=url, headers=headers, data=loginDetails)
            token = 'Bearer ' + str(req['token'])
            return token
        except:
            traceback.print_exc()
            logs.error("Error in getting token")

def img2base64(frame):
    '''
    Converts .jpg image to base64 bytecode format.
    '''
    try:
        retval, buffer = cv.imencode('.jpg', frame)
        b64string = base64.b64encode(buffer).decode("utf-8")
        return b64string
    except:
        traceback.print_exc()
        logs.error("Error in converting image to base64")


def base64_2img(base64str):
    '''
    Converts bas64 bytecode to opencv format.
    '''
    try:
        frame = base64.b64decode(base64str)
        jpg_as_np = np.frombuffer(frame,dtype=np.uint8)
        frame =cv.imdecode(jpg_as_np,flags=1)
        return frame
    except:
        traceback.print_exc()
        logs.error("Error in converting base64 to image")

def appendResult(frame, check_for, detections, recommendations, cam_name):
    '''
    add timestamp, number of violations, and check for specific violations in the image.
    Add recommendations to the area where violations were found.
    '''
    try:
        font = cv.FONT_HERSHEY_SIMPLEX
        font_vio = cv.FONT_HERSHEY_DUPLEX
        font_rec = cv.FONT_HERSHEY_PLAIN
        dt = str (datetime.now())
        dy_line = 15
        dy = 12
        height,widht,_ = frame.shape
        cv.putText(frame, "TimeStamp :: " + dt, (2010, 880), font, .3, (200, 20, 200), 1, cv.LINE_4)
        cv.putText(frame, "Violations Found :: " + detections, (2015,750), font_vio, .3, (25,25,25),1,cv.LINE_4)

        cv.putText(frame, "Recommendations for AREA :: " + cam_name, (2015, 840+2*dy_line),font,0.3,(20,20,20),1,cv.LINE_4)
        ToRecommend = check_for.split(":")
        count = 0
        y0 = 755+3*dy_line
        for rec in ToRecommend:
            if rec in detections:
                count = count + 1
                y0 = y0 +dy_line
                dx=0
                for i, line in enumerate(recommendations[rec].split('\n')):
                    y0 = y0 + i*dy
                    cv.putText(frame, line, (2015+dx, y0), font, 0.35, (20,20,20),1,cv.LINE_4)
                    dx=10
                
        return frame 
    except:
        traceback.print_exc()
        logs.error("Error in appending result to frame")
        
def appendFrame(frame1, frame2):
    '''
    Add borders to two images and concatenates.
    '''
    try:
        frame1 = cv.copyMakeBorder(frame1,10,10,10,0,cv.BORDER_CONSTANT,value=[239,239,239])
        frame2 = cv.copyMakeBorder(frame2,10,10,10,0,cv.BORDER_CONSTANT,value=[239,239,239])
        frame = np.concatenate((np.array(frame1),np.array(frame2)),axis=1)
        return frame
    except:
        traceback.print_exc()
        logs.error("Error in appending frame")

def save_image_hapi(requestSession, url, headers, data):
    resp = requestSession.post(url=url, json=data, headers=headers, timeout=10)
    resp = resp.json()

    return resp


def post_cloud(requestSession, url, headers, data):
    '''
    Send detections to the AI - Cloud
    '''
    try:
        logs.debug("Inside post Cloud %s",url)

        resp = requestSession.post(url=url, json=data,headers=headers,timeout=10)
        print(resp)
        return resp
    except:
        traceback.print_exc()
        logs.error("Error in posting data to %s",url)


