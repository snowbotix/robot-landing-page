#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting installation process..."

# Step 1: Create a virtual environment and activate it
echo "Creating virtual environment..."
python3 -m venv lpenv
source lpenv/bin/activate

# Step 2: Install required Python libraries
echo "Installing required Python libraries..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 3: Locate to the database folder and run db_setup.py
echo "Setting up the database..."
cd database || { echo "Database folder not found!"; exit 1; }
python db_setup.py
cd ..

# Step 4: Modify and run landingpage.sh
echo "Configuring landing page script..."
chmod +x landingpage.sh
sed -i "s|PLACEHOLDER_PATH|$(pwd)|g" landingpage.sh
./landingpage.sh

# Step 5: Setup systemd services
echo "Setting up systemd services..."
sudo cp service1.service /etc/systemd/system/
sudo cp service2.service /etc/systemd/system/

sudo sed -i "s|PLACEHOLDER_PATH|$(pwd)|g" /etc/systemd/system/service1.service
sudo sed -i "s|PLACEHOLDER_PATH|$(pwd)|g" /etc/systemd/system/service2.service

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable service1.service
sudo systemctl enable service2.service
sudo systemctl start service1.service
sudo systemctl start service2.service

echo "Installation completed successfully!"
