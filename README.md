# robot-landing-page
> Landing Page Web App which is used to control the Battery of the robot, toggle the systems and for auto charging of the Low Voltage Battery through High Voltage Battery.
> The Web App has two pages running one for customer front which displays robot location and robot status & other is for monitoring and control for operator

## Description:
- A web-based control panel built using Flask to manage and monitor a robot's key functionalities
- Runs on a Raspberry Pi as an entry point landing application and interacts with BMS of Battery and GPIO pins for controlling operations
- Displays location of robot via GPS and battery status
- Implements an auto charging logic for the low voltage battery system

## Features:
### Control Landing Page - Operator Side
- Display the current BMS Data (Battery Data) of High Volt (48V) & Low Volt (12V) Systems like Battery Voltage, State of Charge (SOC), Current Consumption, Temperature & Switch States (Charge & Discharge)
- Display the current states of the Solid State Relay which control the switching of Auxilarly Systems (Controller, On Board Computer, Relays, Plow/Mower etc), Heater Pad Status, Electronic Stop etc)
- Control the GPIO Pins for High & Low which is connected to Solid State Relays which are connected to Electronic Stop , 12V System (Auxilary System) & On Board Computer (Which is Nvidia AGX)
- The Heater SSR & DC Charger SSR are automatically trigged in the backend logic which is used for Auto Charging the Low Volt System
