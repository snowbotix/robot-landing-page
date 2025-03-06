#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting installation process..."

# Step 1: Clone the Git repository containing the service files and landing page
echo "Cloning the Git repository containing system service files..."
git clone <your-repository-url> /home/$USER/robot-landing-page

cd /home/$USER/robot-landing-page

# Step 2: Create a virtual environment and activate it
echo "Creating virtual environment..."
python3 -m venv lpenv
source lpenv/bin/activate

# Step 3: Install required Python libraries
echo "Installing required Python libraries..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 4: Locate to the database folder and run db_setup.py
echo "Setting up the database..."
cd database || { echo "Database folder not found!"; exit 1; }
python db_setup.py
cd ..

# Step 5: Modify and run landingpage.sh
echo "Configuring landing page script..."
chmod +x landingpage.sh

# Run the landing page script
./landingpage.sh

# Step 6: Setup systemd services
echo "Setting up systemd services..."

# Copy the systemd service files from the repository to systemd directory
sudo cp /home/$USER/robot-landing-page/landingpagewebapp.service /etc/systemd/system/
sudo cp /home/$USER/robot-landing-page/snowbotix-tracker-app-tunnel.service /etc/systemd/system/

# Reload systemd and enable services
echo "Reloading systemd and enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable service1.service
sudo systemctl enable service2.service
sudo systemctl start service1.service
sudo systemctl start service2.service

echo "Installation completed successfully!"
