#!/bin/bash

#Activate the virtual environment
source /home/bms/Battery_Landing_Page/Landing_Page_v2/lpenv/bin/activate

#Run the flask web app
python3 /home/bms/Battery_Landing_Page/Landing_Page_v2/app.py > /home/bms/Battery_Landing_Page/Landing_Page_v2/app.log 2>&1 &


#Run the batterymonitor script
python3 /home/bms/Battery_Landing_Page/Landing_Page_v2/batterymonitor/batteryInfo.py
