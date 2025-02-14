#!/bin/bash

#Activate the virtual environment
source robot-landing-page/lpenv/bin/activate

#Run the flask web app
python3 robot-landing-page/app.py > robot-landing-page/app.log 2>&1 &


#Run the batterymonitor script
python3 robot-landing-page/batterymonitor/batteryInfo.py
