#!/bin/bash

#Activate the virtual environment
source $HOME/robot-landing-page/lpenv/bin/activate

#Run the flask web app
python3 $HOME/app.py > $HOME/app.log 2>&1 &

#Run the batterymonitor script
python3 $HOME/robot-landing-page/batterymonitor/batteryInfo.py 

#print
echo "Landing page and battery monitor scripts are running."
