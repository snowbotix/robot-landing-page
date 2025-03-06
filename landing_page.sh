#!/bin/bash

#Run the flask web app
python3 $(pwd)/app.py > $(pwd)/app.log 2>&1 &

#Run the batterymonitor script
python3 $(pwd)/batterymonitor/batteryInfo.py > $(pwd)/batterymonitor/batteryInfo.log 2>&1 &

#print
echo "Landing page and battery monitor scripts are running."
