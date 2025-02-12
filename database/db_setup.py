import sqlite3 #import sqlite3 for integrating a database

file = "smur1.2_data.db" #file name for storing the data into a database file

conn = sqlite3.connect(file) #Create or connect to the database file 

cursor = conn.cursor()  #Create a cursor object to allow you to execute SQL commands

#create a table for storing the data
cursor.execute("""
       CREATE TABLE IF NOT EXISTS smur_data (
       id INTEGER PRIMARY KEY AUTOINCREMENT, 
       timestamp DATETIME DEFUALT CURRENT_TIMESTAMP,
       
       -- 12V Battery Data
       voltage_12V REAL,
       current_12V REAL,
       soc_12V REAL,
       charge_switch_12V TEXT,
       discharge_switch_12V TEXT,
       temperature_12V REAL,
       
       -- 48V Battery Data
       voltage_48V REAL,
       current_48V REAL,
       soc_48V REAL,
       switches_48V TEXT,
       charge_switch_48V TEXT,
       discharge_switch_48V TEXT,
       temperature_48V_Cell1 REAL,
       temperature_48V_Cell2 REAL,
       temperature_48V_Cell3 REAL, 
       
       -- Relay States
       relay_heating_pad BOOLEAN,
       relay_dc_charger BOOLEAN,
       relay_12v_system BOOLEAN,
       relay_estop BOOLEAN,
       relay_nvidia BOOLEAN
       
    )
""")

#Commit and close connection
conn.commit()
conn.close()
