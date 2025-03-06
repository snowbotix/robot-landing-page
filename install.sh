#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting installation process..."


cd /home/$USER/robot-landing-page

# Step 1: Create a virtual environment and activate it
echo "Creating virtual environment..."
python3 -m venv lpenv
source lpenv/bin/activate

# Step 2: Install required Python libraries
echo "Installing required Python libraries..."
pip install --upgrade pip
pip install -r requirement.txt

# Step 3: Locate to the database folder and run db_setup.py
echo "Setting up the database..."
cd database || { echo "Database folder not found!"; exit 1; }
python db_setup.py
cd ..

# Step 4: Configure & run the landingpage.sh
echo "Configuring landing page script..."
chmod +x landingpage.sh

# Run the landing page script
./landingpage.sh

# Step 6: Setup systemd services
echo "Setting up systemd services..."

# Copy the systemd service files from the repository to systemd directory
sudo cp ./landingpagewebapp.service /etc/systemd/system/
sudo cp ./snowbotix-tracker-app-tunnel.service /etc/systemd/system/

# Reload systemd and enable services
echo "Reloading systemd and enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable service1.service
sudo systemctl enable service2.service
sudo systemctl start service1.service
sudo systemctl start service2.service

echo "Installation completed successfully!"
