import datetime
import cv2 as cv
import asyncio
import traceback

from logs import logs

logs = logs.logger

async def add_timestamp_to_frame(input):
    try:
        font = cv.FONT_HERSHEY_SCRIPT_COMPLEX

        # Get date and time and
        # save it inside a variable
        dt = str(datetime.datetime.now())
        frame = input
        # put the dt variable over the
        # video frame
        cv.putText(frame, dt,
                        (10, 100),
                        font, 1,
                        (210, 155, 155),
                        4, cv.LINE_8)

        await asyncio.sleep(0.01)
    except:
        traceback.print_exc()
        logs.error("Error in reading frame")
    return frame

def run_fd_time(input):
    """    
    Adding timestamp on the images
    """
    frame = add_timestamp_to_frame(input)
    return frame
