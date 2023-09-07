#!/bin/bash


while getopts n: flag
do
    case "${flag}" in
        n) cams=${OPTARG};;
    esac
done

python3 tests/setup_cameras.py -n $cams

# s=$cams
s=5
for (( i=0; i<$s; i++ ));
do {
    ffmpeg -nostdin -re -stream_loop -1 -i rtsp_video.mp4 -c copy -f rtsp rtsp://172.17.0.1:8554/mystream$i &
} done