import sqlite3

# Connect to the database
file = "smur1.2_data.db"
conn = sqlite3.connect(file)

# Create a cursor object
cursor = conn.cursor()

# Check if the table exists by querying the SQLite master table
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='smur_data';")

# Fetch the result
result = cursor.fetchone()

if result:
    print("Table 'smur_data' exists.")
    
    # Query all data from the table
    cursor.execute("SELECT * FROM smur_data;")
    
    # Fetch all rows
    rows = cursor.fetchall()

    # Print the data
    if rows:
        for row in rows:
            print(row)
    else:
        print("No data found in the table.")
else:
    print("Table 'smur_data' does not exist.")

# Optionally, print the schema of the table
cursor.execute("PRAGMA table_info(smur_data);")
columns = cursor.fetchall()

print("\nTable schema:")
for column in columns:
    print(column)

# Close the connection
conn.close()
