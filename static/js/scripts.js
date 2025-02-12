// DOMContent Loader for Leaflet Map Display
document.addEventListener("DOMContentLoaded", function () {
    var map = L.map('map').setView([42.328603025719126, -83.07517240740309], 13) ; //Setting map view to a coordinates

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
});

// Function to update the time display
function updateTime() {
    const timeDisplay = document.getElementById("time-display"); // Select the element
    const now = new Date(); // Get the current date and time

    // Format hours, minutes, and seconds with leading zero
    const hours = now.getHours().toString().padStart(2, "0");
    const minutes = now.getMinutes().toString().padStart(2, "0");
    const seconds = now.getSeconds().toString().padStart(2, "0");

    // Update the text content of the time display
    timeDisplay.textContent = `${hours}:${minutes}:${seconds}`;
}

// Function to update the robot time display
async function updateRobotTime() {

    const RobotTimeDisplay = document.getElementById("robot-time-display");
    const now = new Date(); // Get the current date and time

    // Format hours, minutes, and seconds with leading zero
    const hours = now.getHours().toString().padStart(2, "0");
    const minutes = now.getMinutes().toString().padStart(2, "0");
    const seconds = now.getSeconds().toString().padStart(2, "0");

    // Update the text content of the time display
    RobotTimeDisplay.textContent = `${hours}:${minutes}:${seconds}`;
}

// Update the time every second
setInterval(updateTime, 1000);
setInterval(updateRobotTime, 1000);

// Set the initial time immediately on page load
updateTime();
updateRobotTime();

document.addEventListener("DOMContentLoaded", function () {
    const updateBatteryData = async () => {
        try {
            const response = await fetch("/battery-data");
            const data = await response.json();

            // 48V System
            const data48V = data["48V"] || {};
            document.getElementById("48v-soc").textContent = `SOC: ${data48V.soc || "--"}%`;
            document.getElementById("48v-current").textContent = `Current: ${data48V.current || "--"}A`;
            document.getElementById("48v-temperature").textContent = `Temperature: ${data48V.temperatures || "--"} C`;
            document.getElementById("48v-voltage").textContent = `Voltage: ${data48V.voltage || "--"} W`;

            // 12V System
            const data12V = data["12V"] || {};
            document.getElementById("12v-soc").textContent = `SOC: ${data12V.soc || "--"}%`;
            document.getElementById("12v-current").textContent = `Current: ${data12V.current || "--"}A`;
            document.getElementById("12v-temperature").textContent = `Temperature: ${data12V.temperatures || "--"} C`;
            document.getElementById("12v-voltage").textContent = `Voltage: ${data12V.voltage || "--"} W`;
            document.getElementById('12v-discharge-switch-state').textContent = 
                `Discharge Switch State: ${battery12V.switches.discharge ? 'On' : 'Off'}`;
            document.getElementById('12v-charge-switch-state').textContent = 
                `Charge Switch State: ${battery12V.switches.charge ? 'On' : 'Off'}`;
        } catch (error) {
            console.error("Failed to fetch battery data:", error);
        }
    };

    // Update battery data every 5 seconds
    setInterval(updateBatteryData, 5000);

    // Initial fetch
    updateBatteryData();
});

function togglePin(status) {
    fetch('/toggle', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ status: status })
    }).then(response => response.json())
      .then(data => {
          if (data.success) {
              console.log('Pin toggled successfully');
          } else {
              console.error('Failed to toggle pin');
          }
      });
}