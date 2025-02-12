#Import Libraries
from flask import Flask, render_template, jsonify, request #import flask and it's dependencies for web app
import threading #Threading to lock safely the UDP connections
import socket #Socket programming to establish connection using UDP
import json #Json for serializing and decoding the data sent in UDP
import time #Time for asynchronous updates
import RPi.GPIO as GPIO #GPIO pinout for Raspberry Pi Relay Controlling & Monitoring

#Initialize Flask Apps into Class variables
app = Flask(__name__) #Intialize the main app which is used for control and monitoring
mobile_app = Flask(__name__) #Intialize the mobile app for customer end to monitor the robot stats

# Initialize variables 
battery_data = {} # Variable to store battery data 
latest_coordinates = {"latitude":None, "longitude": None} # Variable to store latest coordinates information
discharge_status_48v = "off" #Variable to store and update the discharge status of 48V Battery
discharge_status_12v = "off"#Variable to store and update the discharge status of 12V Battery
charge_status_48v = "off"#Variable to store and update the charge status of 48V Battery
charge_status_12v = "off"#Variable to store and update the charge status of 12V Battery

# Lock for thread safety
data_lock = threading.Lock()

#UDP Settings to communicate
UDP_IP = "192.168.1.209" #Define the UDP IP
UDP_PORT = 4123 #Defne the UDP Port to Send & Receive Front End Data from HTML to Flask Application - App.py to batteryInfo Script
UDP_PORT2 = 4124 #Define the UDP Port to Receive Data from batteryInfo script 
UDP_PORT_NMEA = 8501 #Define the UDP Port for listening the GPS NMEA message from Teltonika Network

#Define the BCM Numbering of GPIO Pins of Raspberry Pi for Controlling High & Lows
RELAY_12V = 18 #Set the Relay of 12V System SSR GPIO Pin Number - BCM
ESTOP_GPIO_PIN = 17 #Set the Relay of EStop SSR GPIO Pin Number - BCM
RELAY_NVIDIA = 24 #Set the Relay of Nvidia System On/OFF SSR GPIO Pin Number - BCM
RELAY_DC_CHARGER = 12  #Set the Relay DC-DC Charger SSR GPIO Pin Number - BCM
RELAY_HEATING = 26 #Set the Relay Heater SSR GPIO Pin Number - BCM
GPIO.setmode(GPIO.BCM) # Set the GPIO Numbering as BCM

#Configure the GPIO Pins
GPIO.setup(RELAY_12V, GPIO.OUT) #Set the GPIO Pin of 12V System
GPIO.setup(RELAY_DC_CHARGER, GPIO.OUT) #Set the GPIO Pin of DC-DC Charger
GPIO.setup(RELAY_NVIDIA, GPIO.OUT) #Set the GPIO Pin of Nvidia System
GPIO.setup(RELAY_HEATING, GPIO.OUT) #Set the GPIO Pin of Heater Pad
GPIO.setup(ESTOP_GPIO_PIN, GPIO.OUT) #Set the GPIO Pin of Estop

#Initial state of relays (assume they are OFF)
GPIO.output(RELAY_12V, GPIO.HIGH)  # 12V System off
GPIO.output(ESTOP_GPIO_PIN, GPIO.LOW) # Estop as Off

#Flask End Point Route API to Control the Discharge State of 48V Battery using the front end buttons
@app.route('/toggledischarge48v', methods=['POST'])
def toggledischarge48v():
    global discharge_status_48v
    status = request.json['status']
    if status == 'on':
        discharge_status_48v = "on"
        print("ON")
    else:
        discharge_status_48v = "off"
        print("OFF")
    print("48v discharge status is",discharge_status_48v)
    return jsonify(success=True)

#Flask End Point Route API to Control the SSR Relays connected to Raspberry PI
@app.route('/toggle_relay', methods=['POST'])
def toggle_relay():
    data = request.get_json()
    relay_name = data.get('relay')

    if relay_name == 'toggle12VSystem':
        current_state = GPIO.input(RELAY_12V)
        new_state = GPIO.HIGH if current_state == GPIO.LOW else GPIO.LOW
        GPIO.output(RELAY_12V, new_state)
        return jsonify({"success": True, "state": new_state == GPIO.HIGH})
    
    if relay_name == 'toggleNvidia':
        current_state = GPIO.input(RELAY_NVIDIA)
        new_state = GPIO.HIGH if current_state == GPIO.LOW else GPIO.LOW
        GPIO.output(RELAY_NVIDIA, new_state)
        return jsonify({"success": True, "state": new_state == GPIO.HIGH})

    return jsonify({"success": False})

#UDP Listener to receive the battery data from the batteryInfo script
def udp_listener():
    global battery_data
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Listening for UDP data on {UDP_IP}:{UDP_PORT}...")
    
    while True:
        data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes
        try:
            received_data = json.loads(data.decode('utf-8'))
            with data_lock:
                battery_data.update(received_data)
                print("Received Battery Data:", battery_data)  # Debug: after updating battery data
                discharge_status_48v_bytes = bytes(discharge_status_48v, 'utf-8')
                sock.sendto(discharge_status_48v_bytes, (UDP_IP, UDP_PORT2))
                print(discharge_status_48v,discharge_status_12v,charge_status_48v, charge_status_12v)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"Error decoding UDP data: {e}")

#Function to parse the NMEA GPGGA message to extract coordinates 
def parse_gpgga_message(message): 
    try:
        parts = message.split(',')
        if parts[0] != "$GPGGA" or len(parts) < 6:
            return None, None
        
        # Parse latitude
        lat = float(parts[2]) if parts[2] else 0
        lat_dir = parts[3]
        lat_degrees = int(lat // 100)
        lat_minutes = lat % 100
        latitude = lat_degrees + (lat_minutes / 60.0)
        if lat_dir == 'S':
            latitude = -latitude
        
        # Parse longitude
        lon = float(parts[4]) if parts[4] else 0
        lon_dir = parts[5]
        lon_degrees = int(lon // 100)
        lon_minutes = lon % 100
        longitude = lon_degrees + (lon_minutes / 60.0)
        if lon_dir == 'W':
            longitude = -longitude
        
        return latitude, longitude
        
    except Exception as e:
        print(f"Failed to parse GPGGA: {e}")
        return None, None

#UDP Listener to listen to GPGGA NMEA messages from the teltonika service
def nmea_udp_listener(host, port):
    global latest_coordinates
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host,port))
    print(f"Listening for UDP messages on {host}:{port}")
    
    while True:
        data, _ = sock.recvfrom(1024)
        message = data.decode('ascii', errors = 'ignore').strip()
        #print(f"Received message: {message}")
        latitude, longitude = parse_gpgga_message (message)
        if latitude and longitude:
            latest_coordinates["latitude"] = latitude
            latest_coordinates["longitude"] = longitude
            #print(f"Parsed coordinates: {latitude}, {longitude}")

#Flask End Point Route API to call the coordinates to display on map for Mobile App Customer Side App
@mobile_app.route('/get_coordinates')
def get_coordinates():
    print(f"Coordinates Endpoint Called: {latest_coordinates}")
    return jsonify(latest_coordinates)

#Render template app for BMS monitoring and control
@app.route('/')
def index():
    with data_lock:
        data = battery_data
        print(f"Battery data sent to the template: {data}")
    return render_template('indexmvp.html', data=data)

#Render template mobile app for Robot Status Update for Customer Side App
@mobile_app.route('/')
def mobile_index():
    with data_lock:
        data = battery_data
        print(f"Battery data sent to the template: {data}")
    return render_template('mobile_index.html', data=data)

#Flask End Point Route API to get the battery data for the main app
@app.route('/get_battery_data', methods=['GET'])
def get_battery_data():
    with data_lock:
        return jsonify(battery_data)

#Flask End Point Route API to get the battery data for the mobile app  
@mobile_app.route('/get_battery_data', methods=['GET'])
def get_battery_data():
    with data_lock:
        return jsonify(battery_data)

#Flask End Point Route API to get the SSR relay status for Main App
@app.route('/relay_status', methods=['GET'])
def relay_status():
    status = {
        "toggle12VSystem": GPIO.input(RELAY_12V) == GPIO.HIGH,
        "toggleDCCharger": GPIO.input(RELAY_DC_CHARGER) == GPIO.HIGH,
        "toggleEStop" : GPIO.input(ESTOP_GPIO_PIN) == GPIO.HIGH,
        "toggleNvidia" : GPIO.input(RELAY_NVIDIA) == GPIO.HIGH,
        "toggleHeater" : GPIO.input(RELAY_HEATING) == GPIO.HIGH,
     }
    return jsonify(status)

#Flask End Point Route API to get the SSR relay status for Mobile App
@mobile_app.route('/relay_status', methods=['GET'])
def relay_status():
    status = {
        "toggleEStop" : GPIO.input(ESTOP_GPIO_PIN) == GPIO.HIGH,
    }
    return jsonify(status)

# Estop Relay Toggle Function API End Point Route 
@app.route('/toggle_estop', methods=['POST'])
def toggle_estop():
    try:
        # Read the action sent in the request body
        data = request.get_json()
        action = data.get('action')

        # Toggle the GPIO pin based on the action
        if action == 'toggle':
            # Get current state of the GPIO pin
            current_state = GPIO.input(ESTOP_GPIO_PIN)
            new_state = GPIO.HIGH if current_state == GPIO.LOW else GPIO.LOW

            # Set the new state to the GPIO pin
            GPIO.output(ESTOP_GPIO_PIN, new_state)

            return jsonify({"success": True, "new_state": "ON" if new_state == GPIO.HIGH else "OFF"})
        else:
            return jsonify({"success": False, "error": "Invalid action"}), 400
    except Exception as e:
        print(f"Error toggling E-Stop: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

#Main function to run the app.py script
if __name__ == '__main__':
    threading.Thread(target=udp_listener, daemon=True).start() #Start a seperate thread to receive the battery data and send commands to batteryinfo script
    threading.Thread(target=nmea_udp_listener, args=(UDP_IP, UDP_PORT_NMEA), daemon=True).start() #Start a seperate thread for receiving and parsing the GPGGA NMEA messages from Teltonika Service
    threading.Thread(target=lambda: app.run(host=UDP_IP, port=5001, debug=True, use_reloader=False)).start() #Run the flask main app in an IP and Port
    threading.Thread(target=lambda: mobile_app.run(host=UDP_IP, port=5002, debug=False, use_reloader=False)).start() #Run the flask mobile app in an Ip and different port
