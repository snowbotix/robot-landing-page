#This python script is used to establish bluetooth connection 
#and read the data from BMS of Batteries
import asyncio #Asynchronous programming for concurrent coding (to not block the main program while waiting for I/O)
import sys  #Provides access to system specific parameters & functions
import os #file and directory operations
import socket #Creating sockets for UDP communication
import bleak #capable of connecting to BLE devices acting as GATT servers
from bleak import BleakClient #to connect to bluetooth devices 
import time #provides functions to work with time
from bms import BmsSample #importing BmsSample Class from bms.py file located in the directory which contains backend for Jdbbms
from bt import BtBms #importing BtBms Class from bt.py file located in the directory which contains functions required for backend connections
import json #json for serialising the data 
import RPi.GPIO as GPIO #GPIO pins for controlling the Raspberry Pi Pinouts
import sqlite3 #SQL database for storing the data such as bms data
import datetime #Datetime for database insertion
import subprocess #Subprocess to run terminal commands in python

#Function to construct JBD command frame with specific command byte
def _jbd_command(command: int):
    return bytes([0xDD, 0xA5, command, 0x00, 0xFF, 0xFF - (command - 1), 0x77])

#Class JBD BMS Battery which inherits from BtBms Library for effective connection & communication of BMS 
class JbdBt(BtBms):

    # UUIDs for RX (receive) and TX (transmit) GATT characteristics
    UUID_RX = '0000ff01-0000-1000-8000-00805f9b34fb' 
    UUID_TX = '0000ff02-0000-1000-8000-00805f9b34fb'
    TIMEOUT = 20 #Timeout for BMS response in seconds

    # Constructrer class to initialise the JDB BMS Class with device mac address and optional params
    def __init__(self, address, **kwargs):
        super().__init__(address, **kwargs)
        if kwargs.get('psk'):
            self.logger.warning('JBD usually does not use a pairing PIN')
        
        #Intialise buffer and state variables
        self._buffer = bytearray()
        self._switches = None
        self._last_response = None

    # Handler for GATT notifications from the RX characteristic    
    def _notification_handler(self, sender, data):
        
        #Append received data to buffer
        self._buffer += data

        # Check for a complete message (ends with 'w')
        if self._buffer.endswith(b'w'):
            
            # Check if the buffer is large enough before accessing the second byte
            if len(self._buffer) > 1:
                command = self._buffer[1]  # Extract command byte
                buf = self._buffer[:]  # Copy buffer
                self._buffer.clear()  # Clear buffer for the next message
                self._last_response = buf  # Store the last received message
                self._fetch_futures.set_result(command, buf)  # Signal response received
            
            else:
                # Handle the case where the buffer is too small
                print("Buffer is too small to extract command byte")
    
    # Connect to the BMS and start notifications
    async def connect(self, **kwargs):
        await super().connect(**kwargs)
        # Start listening to notifications on the RX characteristic
        await self.client.start_notify(self.UUID_RX, self._notification_handler)
        await asyncio.sleep(2)  # Added delay to stabilize the connection

    # Disconnect from the BMS and stop notifications
    async def disconnect(self):
        await self.client.stop_notify(self.UUID_RX)
        await super().disconnect()

    # Internal method to send a command and wait for the response
    async def _q(self, cmd):
        with self._fetch_futures.acquire(cmd):
            await self.client.write_gatt_char(self.UUID_TX, data=_jbd_command(cmd))
            return await self._fetch_futures.wait_for(cmd, self.TIMEOUT)
    
    # Fetch general BMS data and parse it into a BmsSample object with retry on timeout
    async def fetch(self) -> BmsSample:
        retries = 3 #no of retries in case the fetching fails
        for attempt in range(retries):
            try:
                buf = await self._q(cmd=0x03)  # Request general data
                buf = buf[4:]  # Skip header bytes
    
                # Parse relevant data fields
                num_cell = int.from_bytes(buf[21:22], 'big')
                num_temp = int.from_bytes(buf[22:23], 'big')
                mos_byte = int.from_bytes(buf[20:21], 'big')
    
                # Create a BmsSample object with parsed data
                sample = BmsSample(
                    voltage=int.from_bytes(buf[0:2], byteorder='big', signed=False) / 100,
                    current=-int.from_bytes(buf[2:4], byteorder='big', signed=True) / 100,
                    charge=int.from_bytes(buf[4:6], byteorder='big', signed=False) / 100,
                    capacity=int.from_bytes(buf[6:8], byteorder='big', signed=False) / 100,
                    soc=buf[19],
                    num_cycles=int.from_bytes(buf[8:10], byteorder='big', signed=False),
                    temperatures=[(int.from_bytes(buf[23 + i * 2:i * 2 + 25], 'big') - 2731) / 10 for i in range(num_temp)],
                    switches=dict(
                        discharge=mos_byte == 2 or mos_byte == 3,
                        charge=mos_byte == 1 or mos_byte == 3,
                    ),
                )
    
                self._switches = dict(sample.switches)
                return sample
    
            except asyncio.TimeoutError as e:
                print(f"Timeout on attempt {attempt + 1}: {e}. Retrying...")
                await asyncio.sleep(3)  # Delay before retrying
            except Exception as e:
                print(f"Fetch failed: {e}")
                await asyncio.sleep(3)  # Delay before retrying
    
        print("Failed to fetch data after multiple attempts.")
        return None  # Return None if all retry attempts fail


    # Fetch individual cell voltages from the BMS
    async def fetch_voltages(self):
        buf = await self._q(cmd=0x04) # Request cell voltage data
        num_cell = int(buf[3] / 2) # Number of cells
        voltages = [(int.from_bytes(buf[4 + i * 2:i * 2 + 6], 'big')) for i in range(num_cell)]
        return voltages

    # Set the state of charge or discharge switches
    async def set_switch(self, switch: str, state: bool):
        assert switch in {"charge", "discharge"}

        def jbd_checksum(cmd, data):
            crc = 0x10000
            for i in (data + bytes([len(data), cmd])):
                crc = crc - int(i)
            return crc.to_bytes(2, byteorder='big')

        def jbd_message(status_bit, cmd, data):
            return bytes([0xDD, status_bit, cmd, len(data)]) + data + jbd_checksum(cmd, data) + bytes([0x77])

        if not self._switches:
            await self.fetch()

        new_switches = {**self._switches, switch: state}
        switches_sum = sum(new_switches.values())
        if switches_sum == 2:
            tc = 0x00  # all on
        elif switches_sum == 0:
            tc = 0x03  # all off
        elif (switch == "charge" and not state) or (switch == "discharge" and state):
            tc = 0x01  # charge off
        else:
            tc = 0x02  # charge on, discharge off

        data = jbd_message(status_bit=0x5A, cmd=0xE1, data=bytes([0x00, tc]))  # all off
        self.logger.info("send switch msg: %s", data)
        await self.client.write_gatt_char(self.UUID_TX, data=data)
    
    # Debug utility to retrieve the last received response
    def debug_data(self):
        return self._last_response

#Function to attempt bluetooth connections for multiple retries        
async def attempt_connect(bms, retries=5, delay= 3):
      for attempt in range(retries):
        try:
            print(f"Attempt to connect to {bms.address}, attempt {attempt + 1}")
            #Attempt to establish bluetooth connection asynchronously
            await bms.connect()
            print(f"Connected to {bms.address}")
            return #exit the function 
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in {delay} seconds...")
            await restart_bluetooth_service() #Restart the bluetooth service
            #wait for a delay before retrying
            await asyncio.sleep(delay)

      #If all attempts fail, log an error and exit the program
      print(f"Failed to connecpt to {bms.address} after {retries} attempts.")
      sys.exit(1) #exit with a failure status

#Function to restart bluetooth service when trying to reattempt connection
async def restart_bluetooth_service():
    try:
        #print to console 
        print("Restarting Bluetooth Service...")

        #stop the bluetooth service
        subprocess.run(['sudo','systemctl','stop','bluetooth'],check = True)

        #start the bluetooth service
        subprocess.run(['sudo','systemctl','start','bluetooth'], check = True)

        #print to console
        print("Bluetooth Restarted successfully")

    except subprocess.CalledProcessError as e:
        print(f"Error restarting bluetooth service: {e}")


#Function to continously monitor and maintain the connection with battery management system       
async def maintain_connection(bms):
      while True:
          try:
              #Check if the connection is lost
              if not bms.client.is_connected:
                print(f"Connection lost to {bms.address}. Reconnecting...")
                #Attempt to reconnect
                await attempt_connect(bms)
              #Wait before the next connection check
              await asyncio.sleep(5) 
          except Exception as e:
              #Handle unexpected errors and retry after a delay
              print(f"Error maintaining connection: {e}")
              await asyncio.sleep(5)

#Retry fetching the battery data with a retry loop
async def safe_fetch(bms, retries=5, delay=3):
    for attempt in range(retries):
        try:
            #Attempt to Fetch the battery data
            return await bms.fetch()  # Try fetching the data from the BMS
        except asyncio.TimeoutError as e:  # Handle timeouts specifically
            #Handle timeout errors separetly for debugging
            print(f"Fetch attempt {attempt + 1} failed due to TimeoutError: {e}. Retrying in {delay} seconds...")
        except Exception as e:  # Handle other types of exceptions
            #Catch and log any other exceptions
            print(f"Fetch attempt {attempt + 1} failed due to error: {e}. Retrying in {delay} seconds...")
        
        # Wait before retrying
        await asyncio.sleep(delay)

    print("Failed to fetch data after multiple attempts.")
    return None  # Return None if all retry attempts fail


	
#Function to connect & insert bms data to database
def insert_data(data_12V, data_48V):
    #define global variables for Solid State Relay Pins - BCM
    global RELAY_HEATING, RELAY_DC_CHARGER, RELAY_12V, ESTOP_GPIO_PIN, RELAY_NVIDIA
    #Connect to the SQLite database 
    conn = sqlite3.connect('database/smur1.2_data.db')  #Connect to the database path
    cursor = conn.cursor() #Create a cursor object to interact with the database
    
    #Get the current datetime
    current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    #Extract the neccessary bms data
    B_12V_Soc = data_12V.soc #12 V Battery State of Charge
    B_12V_switch_State_Charge = data_12V.switches['charge'] #12 V Battery Charge Switch State
    B_12V_switch_State_Discharge = data_12V.switches['discharge'] #12 V Battery Discharge Switch State
    B_12V_Volt = data_12V.voltage #12 V Battery Voltage 
    B_12V_Current = data_12V.current #12 V Battery Current Consumption
    B_12V_Temperature = data_12V.temperatures[0] #12 V Battery Temeperature
    B_48V_Soc = data_48V.soc #48 V Battery State of Charge
    B_48V_Switch_State_Charge = data_48V.switches['charge'] #48 V Battery Charge Switch State
    B_48V_Switch_State_Discharge = data_48V.switches['discharge'] #48 V Battery Discharge Switch State
    B_48V_Volt = data_48V.voltage #48 V Battery Voltage
    B_48V_Current = data_48V.current #48 V Battery Current
    B_48V_Temperature_Cell1 = data_48V.temperatures[0] if len(data_48V.temperatures)>0 else None #48 V Battery Cell 1 Temperature
    B_48V_Temperature_Cell2 = data_48V.temperatures[1] if len(data_48V.temperatures)>1 else None #48 V Battery Cell 2 Temperature
    B_48V_Temperature_Cell3 = data_48V.temperatures[2] if len(data_48V.temperatures)>2 else None #48 V Battery Cell 3 Temperature
    
    #Insert the data into database using cursor object for interaction 
    cursor.execute('''
           INSERT INTO smur_data (timestamp, voltage_12V, current_12V, soc_12V, charge_switch_12V, discharge_switch_12V, temperature_12V,
                                  voltage_48V, current_48V, soc_48V, charge_switch_48V, discharge_switch_48V, temperature_48V_Cell1, temperature_48V_Cell2, temperature_48V_Cell3, relay_heating_pad, relay_dc_charger, relay_12v_system, relay_estop, relay_nvidia)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''',
    (current_timestamp, B_12V_Volt, B_12V_Current, B_12V_Soc, B_12V_switch_State_Charge, B_12V_switch_State_Discharge, B_12V_Temperature,
     B_48V_Volt, B_48V_Current, B_48V_Soc, B_12V_switch_State_Charge, B_48V_Switch_State_Discharge, B_48V_Temperature_Cell1, B_48V_Temperature_Cell2, B_48V_Temperature_Cell3, GPIO.input(RELAY_HEATING), GPIO.input(RELAY_DC_CHARGER), GPIO.input(RELAY_12V), GPIO.input(ESTOP_GPIO_PIN), GPIO.input(RELAY_NVIDIA)
     ))
    
    #Save the commit
    conn.commit()
    #Close the connection
    conn.close()

              
#Main function which runs entire bms establish connection loop, receving data, sending data, inserting into database
async def main():

    #Define the global variables to call inside the function
    global RELAY_HEATING, RELAY_DC_CHARGER, RELAY_12V, ESTOP_GPIO_PIN, RELAY_NVIDIA
    
    #Define the mac address of both batteries for bluetooth connection
    JbdBms12VBatteryMacAddr = 'A5:C2:37:2B:BB:B1' #mac address of 12 V Battery (Jdb BMS) - PUPVWMHB LiFePO4 100 Ah
    #JbdBms48VBatteryMacAddr = 'A4:C1:37:41:B5:2D' #mac address of 48 V Battery (Jdb BMS) - SMUR-BAT1
    JbdBms48VBatteryMacAddr = '10:A5:62:0F:14:74' #mac address of 48 V Battery (Jdb BMS) - SMUR-BAT2 	
    
    #Define JBD Class with the MAC Address 
    Bms12V  = JbdBt(JbdBms12VBatteryMacAddr, name='jbd') #12V BMS JBD Class Variable
    Bms48V  = JbdBt(JbdBms48VBatteryMacAddr, name='jbd') #48V BMS JBD Class Variable

    #Attempt to connect to Bluetooth 
    await attempt_connect(Bms12V) #Attempt Connection to 12V Battery
    await attempt_connect(Bms48V) #Attempt Connection to 48V Battery
    
    #Maintain connection and fetching of data using a background task runner which will maintain in case of failure
    asyncio.create_task(maintain_connection(Bms12V)) #Maintain Connection to 12V Battery
    asyncio.create_task(maintain_connection(Bms48V)) #Maintain Connection to 48V Battery

    #UDP Settings for back & forth communication
    UDP_IP = "192.168.1.209" #Define the UDP IP
    UDP_PORT = 4124 #Define the UDP Port to Receive Data to app.py flask application 
    UDP_PORT2 = 4123 #Defne the UDP Port to Send & Receive Front End Data from HTML to Flask Application - App.py to this Script 

    #Socket Binidng 
    sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.bind((UDP_IP,UDP_PORT))

    #Initialize variables 
    switch = 'off'

    #Define the BCM Numbering of GPIO Pins of Raspberry Pi for Controlling High & Lows
    RELAY_HEATING = 26 #Set the Relay Heater SSR GPIO Pin Number - BCM
    RELAY_DC_CHARGER = 12 #Set the Relay DC Chaerger SSR GPIO Pin Number - BCM
    RELAY_12V = 18 #Set the Relay 12V SSR GPIO Pin Number
    ESTOP_GPIO_PIN = 17 #Set the E-Stop GPIO Pin Number
    RELAY_NVIDIA = 24 #Set the Relay NVIDIA SSR GPIO Pin Number
    GPIO.setmode(GPIO.BCM) # Set the GPIO Numbering as BCM
    GPIO.setwarnings(False) #Set the warnings as false

    # Configure the GPIO Pins
    GPIO.setup(RELAY_DC_CHARGER, GPIO.OUT) #Set the GPIO Pin of DC Charger
    GPIO.setup(RELAY_HEATING, GPIO.OUT) #Set the GPIO Pin of Heating
    GPIO.setup(RELAY_12V, GPIO.OUT) #Set the GPIO Pin of 12V System
    GPIO.setup(ESTOP_GPIO_PIN, GPIO.OUT) #Set the GPIO Pin of E Stop 
    GPIO.setup(RELAY_NVIDIA, GPIO.OUT) #Set the GPIO Pin of Nvidia Computer

    #Initialize the GPIO Pins as Off While starting the script
    GPIO.output(RELAY_DC_CHARGER, GPIO.LOW)  # Initialize DC Charger off
    GPIO.output(RELAY_HEATING, GPIO.LOW)  # Initialize Heater off

    #Initialize the Battery Switch States 
    await Bms48V.set_switch('charge',False) #Set the 48V Battery Charge as OFF
    await Bms12V.set_switch('charge',False) #Set the 12V Battery Charge as OFF
    await Bms12V.set_switch('discharge',True) #Set the 12V Battery Dicharge as ON

    #Enter into the loop for Data Extraction, Supply, Auto Charging & Storage of Data
    while True:

        #Fetch the battery data
        Data_12V = await safe_fetch(Bms12V) #Fetch the 12V Battery Data and store it in a Dict Vairable 
        Data_48V = await safe_fetch(Bms48V) #Fetch the 48V Battery Data and store it in a Dict Vairable 

        #Store the BMS Data into variables for auto charging logic
        B_12V_Soc = Data_12V.soc #Store the 12V Battery State of Charge into a variable
        B_12V_Switch_State = Data_12V.switches #Store the 12V Battery switch states into a variable
        B_12V_switch_State_charge = Data_12V.switches['charge'] #Store the 12V Battery charge switch state into a variable
        B_12V_switch_State_discharge = Data_12V.switches['discharge'] #Store the 48V Battery charge switch state into a variable
        B_12V_Volt = Data_12V.voltage #Store the 12V Battery Voltage into a variable
        B_12VTemp = Data_12V.temperatures #Store the 12V Battery Temperature into a variable
        B_48V_Soc = Data_48V.soc #Store the 48V Battery State of Charge into a variable
        B_48V_Switch_State = Data_48V.switches #Store the 48V Battery Switch states into a variable 
        B_48V_Switch_State_Discharge = Data_48V.switches['discharge'] #Store the 48V Battery discharge switch state into a variable
        
        #Insert/Store the data into database by calling the insert_data function 
        insert_data(Data_12V, Data_48V)
        
        # Print the fetched data to the console for debugging
        print("Battery 12V Data:")
        print(f"Voltage: {Data_12V.voltage} V")
        print(f"Current: {Data_12V.current} A")
        print(f"State of Charge (SOC): {Data_12V.soc}%")
        print(f"Capacity: {Data_12V.capacity} Ah")
        print(f"Temperature: {Data_12V.temperatures} °C")
        print(f"Cycles: {Data_12V.num_cycles}")
        print(f"Switches: {Data_12V.switches}")
        
        print("\nBattery 48V Data:")
        print(f"Voltage: {Data_48V.voltage} V")
        print(f"Current: {Data_48V.current} A")
        print(f"State of Charge (SOC): {Data_48V.soc}%")
        print(f"Capacity: {Data_48V.capacity} Ah")
        print(f"Temperature: {Data_48V.temperatures} °C")
        print(f"Cycles: {Data_48V.num_cycles}")
        print(f"Switches: {Data_48V.switches}")

        #store the data into a format like json dict variable to be sent over UDP
        battery_data =  {
            "12V": {
                "voltage": Data_12V.voltage,
                "current": Data_12V.current,
                "soc": Data_12V.soc,
                "temperatures": Data_12V.temperatures,
                "switches": Data_12V.switches,
            },
            "48V": {
                "voltage": Data_48V.voltage,
                "current": Data_48V.current,
                "soc": Data_48V.soc,
                "temperatures": Data_48V.temperatures,
                "switches": Data_48V.switches,
            },
        }
        
        #serialize the dat to JSON format
        message = json.dumps(battery_data)

        #send the data over UDP
        sock.sendto(message.encode('utf-8'),(UDP_IP,UDP_PORT2))
        print("Sent Battery Data over UDP:",message)#Log the Data sent over UDP Port to console for debugging
        
        #Recieve the Front End Data for 48V Battery Dicharge State for Control of the Switch
        received_data, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
        discharge_status_48v = received_data.decode('utf-8') #Decode from JSOn to UTF-8 for Python
        print("data received", discharge_status_48v) #print the data received from Front End to Console for debugging
        #Conditional Statements to Set the discharge switch of 48V Battery
        if (discharge_status_48v != switch):
          if(discharge_status_48v=='on' or B_48V_Switch_State_Discharge is False):
            switch_data = discharge_status_48v
            state=True
            await Bms48V.set_switch('discharge', state)
            switch = 'on'
          elif(discharge_status_48v=='off' or B_48V_Switch_State_Discharge is True):
            switch_data = discharge_status_48v
            state=False
            await Bms48V.set_switch('discharge', state)
            switch = 'off'
        
        # Auto Charging Algoritm
        # 12V Battery Charging using 48V Battery using a custom Logic
        #Check for 48V Battery SOC if it is more than 30% then only charge the 12V Battery
        if B_48V_Soc >= 25:

            #Charging Conditions Algo
            #Check if 12V Battery State of Charge is less than 20 or the voltage is less than 11.8
            if B_12V_Volt <= 12.5 or B_12V_Soc <= 20:
                
                # Temperature Control Algorithm
                # Check if the temperature of 12V Battery is less than 4
                if B_12VTemp[0] < 3:
                    #Set the heating pad on to raise the battery temperature for charging
                    GPIO.output(RELAY_HEATING, GPIO.HIGH) #GPIO High for Heater Pad to turn on 
                    print("Turned On Heating") #Print on console for debugging and monitoring
                #Check if the temeprature of 12V Battery is more than 5
                elif B_12VTemp[0] > 3.5:
                    #Set the heating pad off to lower the battery temperature for charging
                    GPIO.output(RELAY_HEATING, GPIO.LOW) #GPIO Low for Heater pad to turn off
                    print("Turned Off Heating") #Print on console for debugging and monitoring
                
                #Set the Charge Switch States of 12V Battery
                # Check current status of the 12V charge switch before setting it
                if not Data_12V.switches['charge']:  # Check if the 12V charge switch is off
                    await Bms12V.set_switch('charge', True)  # Turn on the 12V charge switch
                    print("Turned on 12V Charge") #Print on console for debugging and monitoring
                
                #Set the DC-DC Charger for Charging
                if GPIO.input(RELAY_DC_CHARGER) == GPIO.LOW: #If DC CHharger is not on
                    GPIO.output(RELAY_DC_CHARGER, GPIO.HIGH)  # Turn on the DC Charger
                    print("Turned on DC Charger") #Print on console for debugging and monitoring
                
                #Set the Dicharge Switch state of 48V Battery to disburse current to 12V 
                if not B_48V_Switch_State_Discharge: #If discharge of 48V Battery is not on
                    await Bms48V.set_switch('discharge', True)  # Turn on the 48V discharge switch
                    print("Turned on 48V Discharge") #Print on console for debugging and monitoring
            
            #Charging Conditions Off Algorithm
            #Before switching off the charging algo, Check if the 12V Battery State of Charge is more than equal to 99 or 12 V Battery Voltage is greater than 14
            elif B_12V_Volt >= 13.6 or B_12V_Soc >= 100:
                # Check current status of the 12V charge switch before setting it
                if Data_12V.switches['charge']:  # Check if the 12V charge switch is on
                    await Bms12V.set_switch('charge', False)  # Turn off the 12V charge switch
                    print("Turned off 12V Charge") #Print on console for debugging and monitoring
                
                #Set the DC-DC Charger as Off
                if GPIO.input(RELAY_DC_CHARGER) == GPIO.HIGH: #If the DC-DC Charge is On
                    GPIO.output(RELAY_DC_CHARGER, GPIO.LOW)  # Set the DC-DC Charger Off
                    print("Turned off DC Charger") #Print on console for debugging and monitoring
                
                #Set the discharge switch to off
                if B_48V_Switch_State_Discharge and discharge_status_48v != "on": #Check if 48V Battery Discharge is On and front end also says off 
                    await Bms48V.set_switch('discharge', False) #Set the discharge switch of 48V to off
                    print("Turned Off 48V Discharge")
        else:
            if B_48V_Soc < 25:
                #Turn off the 12v charge switch
                if Data_12V.switches['charge']:
                    await Bms12V.set_switch('charge', False)  # Turn off the 12V charge switch
                    print("Turned off 12V Charge due to low 48V SOC")
            
                # Turn off the DC charger if it is on
                if GPIO.input(RELAY_DC_CHARGER) == GPIO.HIGH:
                    GPIO.output(RELAY_DC_CHARGER, GPIO.LOW)  # DC Charger OFF
                    print("Turned off DC Charger due to low 48V SOC")

        #wait before sending the next update
        await asyncio.sleep(2)

#Run the script asynchronously
if __name__ == '__main__':
    asyncio.run(main())
