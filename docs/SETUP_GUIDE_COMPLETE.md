# The First Timer's Guide to dpx-showsite-ops
## From Bare Metal to Beautiful Graphs

**Target Audience**: Someone who has never touched Docker, Linux, or IoT before  
**Time Required**: 2-3 hours for initial setup  
**Skill Level**: Beginner (we assume nothing)

**THIS DOCUMENT CURRENTLY UNTESTED OR EDITED AS OF 2.5.26**

---

## Table of Contents

1. [What You're Building](#what-youre-building)
2. [Hardware You Need](#hardware-you-need)
3. [Part 1: Windows NUC Setup](#part-1-windows-nuc-setup)
4. [Part 2: Create Ubuntu VM](#part-2-create-ubuntu-vm)
5. [Part 3: Ubuntu First Boot](#part-3-ubuntu-first-boot)
6. [Part 4: Install Docker](#part-4-install-docker)
7. [Part 5: Deploy the Stack](#part-5-deploy-the-stack)
8. [Part 6: Connect Grafana to InfluxDB](#part-6-connect-grafana-to-influxdb)
9. [Part 7: Create Your First Dashboard](#part-7-create-your-first-dashboard)
10. [Part 8: Remote Access (Optional)](#part-8-remote-access-optional)
11. [Part 9: Public Dashboards (Optional)](#part-9-public-dashboards-optional)
12. [Part 10: Theengs Gateway for BLE (Optional)](#part-10-theengs-gateway-for-ble-optional)
13. [Troubleshooting](#troubleshooting)
14. [Daily Operations](#daily-operations)

---

## What You're Building

By the end of this guide, you'll have:

- A Linux VM running on your Windows NUC
- Temperature and humidity data from sensors flowing into a database every 10 minutes
- Beautiful Grafana dashboards showing your sensor data
- The ability to view dashboards from anywhere (phone, laptop, etc.)
- Automatic device discovery and mapping

**The data flow**:
```
Govee Sensor → Govee Cloud → Your VM → Database → Pretty Graphs
```

---

## Hardware You Need

### Required
- **Windows NUC** (or any Windows PC with 8GB+ RAM)
- **Govee Sensors** (H5051 or similar Bluetooth temperature/humidity sensors)
- **Internet connection** (wired recommended)
- **Router** with ability to set static IP (most routers can do this)

### Optional but Recommended
- **Bluetooth USB dongle** (if your NUC doesn't have Bluetooth)
- **Smartphone** (for Govee app setup)

---

## Part 1: Windows NUC Setup

### 1.1: Enable Hyper-V

Hyper-V is Windows' built-in virtualization tool. It lets you run Linux on your Windows machine.

**Steps**:
1. Press `Windows + X`, click **Apps and Features**
2. Click **Programs and Features** on the right
3. Click **Turn Windows features on or off**
4. Check these boxes:
   - ☑ Hyper-V
   - ☑ Hyper-V Management Tools
   - ☑ Hyper-V Platform
5. Click **OK**
6. **Restart your computer** when prompted

**Verification**: After restart, search for "Hyper-V Manager" in Start menu. It should open.

### 1.2: Create Virtual Network Switch

This lets your VM talk to your home network.

**Steps**:
1. Open **Hyper-V Manager**
2. Click your computer name on the left
3. On the right, click **Virtual Switch Manager**
4. Click **New virtual network switch**
5. Select **External**
6. Click **Create Virtual Switch**
7. Name it: `External Network`
8. Select your **Ethernet adapter** (usually "Ethernet" or "Local Area Connection")
9. Check **Allow management operating system to share this network adapter**
10. Click **OK**

**Verification**: You should see "External Network" in the Virtual Switch Manager list.

### 1.3: Download Ubuntu Server

**Steps**:
1. Go to: https://ubuntu.com/download/server
2. Click **Download Ubuntu Server 24.04 LTS**
3. Save the .iso file (it's about 2GB)
4. Remember where you saved it (probably Downloads folder)

---

## Part 2: Create Ubuntu VM

### 2.1: Create the Virtual Machine

**Steps**:
1. Open **Hyper-V Manager**
2. Right-click your computer name → **New** → **Virtual Machine**
3. Click **Next** on the wizard welcome screen

**Specify Name and Location**:
- Name: `dpx-showsite-ops`
- Click **Next**

**Specify Generation**:
- Select **Generation 2**
- Click **Next**

**Assign Memory**:
- Startup memory: `4096` MB (4GB)
- ☑ Check **Use Dynamic Memory**
- Click **Next**

**Configure Networking**:
- Connection: Select **External Network** (the one you created)
- Click **Next**

**Connect Virtual Hard Disk**:
- ⦿ Create a virtual hard disk
- Name: `dpx-showsite-ops.vhdx`
- Location: (leave default)
- Size: `50` GB
- Click **Next**

**Installation Options**:
- ⦿ Install an operating system from a bootable image file
- Click **Browse**
- Navigate to your Downloads folder
- Select the Ubuntu Server .iso file you downloaded
- Click **Next**

**Summary**:
- Review everything
- Click **Finish**

### 2.2: Adjust VM Settings

Before we start it, let's tweak a few things:

**Steps**:
1. In Hyper-V Manager, right-click **dpx-showsite-ops** → **Settings**
2. Go to **Security** on the left
3. **UNCHECK** "Enable Secure Boot" (important!)
4. Go to **Processor** on the left
5. Set **Number of virtual processors** to `2`
6. Click **OK**

### 2.3: Start the VM

**Steps**:
1. In Hyper-V Manager, right-click **dpx-showsite-ops**
2. Click **Connect** (opens a window)
3. Click **Start** button (green play button)

You'll see the Ubuntu installer boot up.

---

## Part 3: Ubuntu First Boot

### 3.1: Ubuntu Installation

The installer will walk you through. Here's what to pick:

**Language**: English (or your preference)

**Keyboard**: English (US) (or your preference)

**Type of Install**: 
- ⦿ Ubuntu Server (default)
- Click **Done**

**Network Connections**:
- You should see `eth0` with an IP address (like 192.168.1.x)
- If you see "DHCPv4" that's perfect
- Click **Done**

**Configure Proxy**: 
- Leave blank
- Click **Done**

**Ubuntu Archive Mirror**:
- Leave default
- Click **Done**

**Guided Storage Configuration**:
- ⦿ Use an entire disk
- Select the disk shown
- Click **Done**
- Confirm by clicking **Continue**

**Profile Setup** (IMPORTANT - remember these):
- Your name: `dpx` (or whatever you want)
- Your server's name: `dpx-showsite-ops`
- Username: `dubpixel` (or whatever you want)
- Password: (pick a strong password - you'll need this a LOT)
- Confirm password
- Click **Done**

**SSH Setup**:
- ☑ Check **Install OpenSSH server**
- Click **Done**

**Featured Server Snaps**:
- Don't check anything
- Click **Done**

**Installation will run** (takes 5-10 minutes)

When you see "Installation complete!", click **Reboot Now**

If it says "Please remove installation medium", just press **Enter**

### 3.2: First Login

After reboot, you'll see a login prompt:

```
dpx-showsite-ops login: _
```

**Steps**:
1. Type your username (e.g., `dubpixel`)
2. Press **Enter**
3. Type your password (you won't see it typing)
4. Press **Enter**

You should see something like:
```
dubpixel@dpx-showsite-ops:~$
```

**You're in!** This is the command line. Everything from here is typing commands.

### 3.3: Update the System

Copy these commands one at a time (press Enter after each):

```bash
sudo apt update
```
(It will ask for your password)

```bash
sudo apt upgrade -y
```
(This might take 5-10 minutes)

```bash
sudo reboot
```

The VM will restart. Wait 30 seconds, then log in again.

### 3.4: Set a Static IP

Right now your VM has a dynamic IP (it can change). Let's make it permanent.

**Find your current IP**:
```bash
ip addr show eth0 | grep 'inet '
```

You'll see something like: `inet 192.168.1.142/24`

**The parts**:
- `192.168.1.142` = your IP (remember this)
- `192.168.1.1` = your router (usually gateway is .1)

**Edit the network config**:
```bash
sudo nano /etc/netplan/50-cloud-init.yaml
```

You'll see something like:
```yaml
network:
  ethernets:
    eth0:
      dhcp4: true
```

**Change it to** (use YOUR IP addresses):
```yaml
network:
  ethernets:
    eth0:
      dhcp4: no
      addresses:
        - 192.168.1.100/24
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
```

**Save the file**:
- Press `Ctrl + O` (that's the letter O)
- Press `Enter`
- Press `Ctrl + X`

**Apply the changes**:
```bash
sudo netplan apply
```

**Verify**:
```bash
ip addr show eth0 | grep 'inet '
```

Should now show `192.168.1.100` (or whatever you set)

**Test internet**:
```bash
ping -c 3 google.com
```

You should see responses. Press `Ctrl + C` if it keeps going.

### 3.5: Install Helpful Tools

```bash
sudo apt install -y git curl wget vim avahi-daemon
```

**Enable mDNS** (lets you use dpx-showsite-ops.local instead of IP):
```bash
sudo systemctl enable --now avahi-daemon
```

---

## Part 4: Install Docker

Docker runs all our services in containers (like tiny virtual machines).

### 4.1: Install Docker

Run these commands one at a time:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
```

```bash
sudo sh get-docker.sh
```
(Takes 2-3 minutes)

```bash
sudo usermod -aG docker $USER
```

**Log out and back in** for this to take effect:
```bash
exit
```

Then log back in with your username and password.

**Verify Docker works**:
```bash
docker --version
```

Should show something like: `Docker version 24.0.7`

```bash
docker compose version
```

Should show: `Docker Compose version v2.x.x`

---

## Part 5: Deploy the Stack

### 5.1: Clone the Repository

```bash
cd ~
git clone https://github.com/dubpixel/dpx_showsite_ops.git
cd dpx_showsite_ops
```

### 5.2: Run Setup Script

```bash
chmod +x setup.sh
./setup.sh
```

The script will:
- Check if Docker is installed ✓
- Create directories
- Create a `.env` file
- Ask if you want to edit it now

**When it asks "Open .env in nano now?"**, press `Y` and Enter.

### 5.3: Configure .env File

You need a Govee API key. Let's get one:

**On your phone**:
1. Open Govee Home app
2. Go to **My Account** (bottom right)
3. Click **Apply for API Key**
4. Follow the instructions
5. You'll receive an email with your API key (looks like: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

**Back in the terminal**, fill in:

```bash
GOVEE_API_KEY='your-api-key-here'
GOVEE_EMAIL='your-govee-email@example.com'
GOVEE_PASSWORD='your-govee-password'

# Leave these as-is:
GOVEE_MQTT_HOST=127.0.0.1
GOVEE_MQTT_PORT=1883

# Set your timezone (find yours at: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)
TZ=America/New_York

# Leave these as-is:
RUST_LOG=govee=info
GOVEE_TEMPERATURE_SCALE=F
```

**Save**:
- Press `Ctrl + O`
- Press `Enter`
- Press `Ctrl + X`

### 5.4: Start the Stack

```bash
iot up
```

You'll see a bunch of "Pulling" messages as it downloads images (takes 2-5 minutes first time).

When it's done, you'll see:
```
✔ Container influxdb     Started
✔ Container grafana      Started
✔ Container mosquitto    Started
✔ Container telegraf     Started
✔ Container govee2mqtt   Started
```

**Verify everything is running**:
```bash
iot status
```

You should see 5 containers all "Up".

### 5.5: Update Device Mappings

This tells the system about your Govee devices:

```bash
iot update
```

Wait 30 seconds, then:

```bash
iot lg
```

You should see logs about connecting to AWS IoT. If you see "timeout" errors, see [Troubleshooting](#troubleshooting).

---

## Part 6: Connect Grafana to InfluxDB

Grafana shows graphs. InfluxDB stores data. Let's connect them.

### 6.1: Access Grafana

On your **main computer** (not the VM), open a web browser and go to:

```
http://192.168.1.100:3000
```

(Replace 192.168.1.100 with your VM's IP if you used something different)

You should see the Grafana login page.

**Login**:
- Username: `admin`
- Password: `grafanapass123`

It will ask you to change the password. You can click "Skip" or set a new one.

### 6.2: Add InfluxDB Data Source

**Steps**:
1. On the left sidebar, click the **⚙️ gear icon** (Configuration)
2. Click **Data sources**
3. Click **Add data source** button
4. Scroll down and click **InfluxDB**

**Configure it**:
- **Name**: `InfluxDB` (already filled)
- **Query Language**: Select **Flux** from dropdown
- **URL**: `http://influxdb:8086`
- **Access**: Leave as "Server (default)"
- **Auth**: Make sure ALL boxes are UNCHECKED
- Scroll down to **InfluxDB Details**:
  - **Organization**: `home`
  - **Token**: `my-super-secret-token`
  - **Default Bucket**: `govee`

**Test it**:
- Scroll to bottom
- Click **Save & Test**
- You should see a green checkmark: "datasource is working. 1 buckets found"

If you see red errors, double-check your entries.

---

## Part 7: Create Your First Dashboard

### 7.1: Find Your Room Names

First, we need to know what rooms your sensors are in.

**Back in the VM terminal**, run:
```bash
iot mqtt "gv2mqtt/#" 10
```

You'll see messages like:
```
gv2mqtt/sensor/sensor-33FA4381ECA1010A-sensortemperature/state 72.5
gv2mqtt/sensor/sensor-33FA4381ECA1010A-sensorhumidity/state 45.2
```

If you see these, your sensors are working! Press `Ctrl + C` to stop.

**Check what rooms are set up**:
```bash
iot query 1h 100 | grep room
```

You'll see something like: `room=studown` or `room=bedroom`

Remember your room name(s).

### 7.2: Create a Dashboard

**In Grafana** (in your browser):

1. On the left sidebar, hover over **Dashboards** (looks like 4 squares)
2. Click **+ New** → **New Dashboard**
3. Click **+ Add visualization**
4. Select **InfluxDB** as the data source

### 7.3: Add a Temperature Panel

In the query editor at the bottom:

1. Make sure "Query Language" shows **Flux**
2. Delete any existing query text
3. Paste this (replace `your_room_name` with your actual room):

```flux
from(bucket: "govee")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.sensor_type == "temperature")
  |> filter(fn: (r) => r.room == "studown")
```

**Customize the panel**:
1. On the right side, under "Panel options":
   - **Title**: Change to "Temperature"
2. Under "Standard options":
   - **Unit**: Select "Temperature" → "Fahrenheit (°F)" (or Celsius if you prefer)
3. Click **Run query** button (top right) or wait a few seconds

You should see a graph appear!

**Save the panel**:
- Click **Apply** button (top right)

### 7.4: Add a Humidity Panel

1. Click **Add** dropdown (top right) → **Visualization**
2. Select **InfluxDB**
3. Paste this query (replace room name):

```flux
from(bucket: "govee")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.sensor_type == "humidity")
  |> filter(fn: (r) => r.room == "studown")
```

**Customize**:
- **Title**: "Humidity"
- **Unit**: "Misc" → "Percent (0-100)"

Click **Apply**

### 7.5: Save the Dashboard

1. Click the **Save dashboard** icon (floppy disk, top right)
2. Name it: "Room Monitoring" (or whatever you want)
3. Click **Save**

**You now have a working dashboard!** 🎉

---

## Part 8: Remote Access (Optional)

Want to check your sensors from your phone or while away from home? Install Tailscale.

### 8.1: Install Tailscale on VM

**In your VM terminal**:
```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

```bash
sudo tailscale up
```

It will give you a URL like: `https://login.tailscale.com/a/abc123xyz`

**Copy that URL** and paste it in your browser. Log in with:
- Google account
- Microsoft account
- Or create a Tailscale account

After you authorize it, go back to the terminal. It should say "Success."

### 8.2: Install Tailscale on Your Phone/Computer

**On your phone**:
1. Download **Tailscale** from App Store or Google Play
2. Open it and log in with the same account
3. Turn it ON

**On your laptop**:
1. Go to https://tailscale.com/download
2. Download for your OS
3. Install and log in

### 8.3: Access Grafana Remotely

With Tailscale running on your phone:

Open your browser and go to:
```
http://dpx-showsite-ops:3000
```

Or use the Tailscale IP (check in Tailscale app under your VM's name).

**You can now access your dashboard from anywhere!**

---

## Part 9: Public Dashboards (Optional)

Want to share your dashboard with someone who doesn't have Tailscale? Use Cloudflare Tunnel.

### 9.1: Install Cloudflare Tunnel

**In your VM terminal**:
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
```

### 9.2: Start a Temporary Tunnel

```bash
iot tunnel
```

You'll see output like:
```
https://random-words-example.trycloudflare.com
```

**Copy that URL** and give it to anyone. They can view your dashboard without logging in.

**Important**: 
- This URL changes every time you run the command
- It stops working when you close the terminal or press `Ctrl + C`
- For permanent URLs, see Cloudflare's documentation on setting up a named tunnel

---

## Part 10: Theengs Gateway for BLE (Optional)

Want faster updates? Instead of waiting 10 minutes for cloud sync, read sensors directly via Bluetooth.

### 10.1: Install Python on Windows

**On your Windows NUC**:

1. Go to: https://www.python.org/downloads/
2. Download Python 3.11 or newer
3. Run the installer
4. ☑ **CHECK** "Add Python to PATH"
5. Click **Install Now**

### 10.2: Install Visual Studio Build Tools

Theengs needs C++ compiler tools.

1. Go to: https://visualstudio.microsoft.com/downloads/
2. Scroll to "Tools for Visual Studio"
3. Download **Build Tools for Visual Studio 2022**
4. Run the installer
5. Select **Desktop development with C++**
6. Click **Install** (takes 10-15 minutes)

### 10.3: Install Theengs Gateway

Open **PowerShell** (right-click Start → Windows PowerShell):

```powershell
pip install TheengsGateway
```

### 10.4: Run Theengs Gateway

```powershell
python -m TheengsGateway -H 192.168.1.100 -P 1883
```

(Replace 192.168.1.100 with your VM's IP)

You should see output about discovering devices. Leave this running.

**To stop it**: Press `Ctrl + C`

**Note**: This is Phase 4 of the project. Full integration requires additional setup (ble_decoder.py service). See the main documentation for details.

---

## Troubleshooting

### govee2mqtt Shows Timeout Errors

**Symptom**: `iot lg` shows "timeout connecting to AWS IoT"

**Fix** - Disable IPv6:
```bash
sudo sysctl -w net.ipv6.conf.eth0.disable_ipv6=1
echo "net.ipv6.conf.eth0.disable_ipv6=1" | sudo tee -a /etc/sysctl.conf
iot restart govee2mqtt
```

Wait 30 seconds, then check:
```bash
iot lg
```

Should see "Connected to AWS IoT" messages.

### No Data in Grafana

**Check devices are assigned to rooms**:
- Open Govee Home app
- Tap each sensor
- Make sure "Room" is set (not "Unassigned")
- Run `iot update` on VM

**Check data is flowing**:
```bash
iot mqtt "gv2mqtt/#" 20
```

Should see temperature/humidity messages every few seconds.

**Check InfluxDB has data**:
```bash
iot query 1h 10
```

Should see rows with values.

### Can't Access Grafana from Browser

**Check the IP**:
```bash
iot ip
```

Make sure you're using the correct IP in your browser.

**Check Grafana is running**:
```bash
iot status
```

Grafana should show "Up".

**Try from VM itself**:
```bash
curl http://localhost:3000
```

Should see HTML output (not "connection refused").

**Check firewall** (if on Windows host computer):
- Windows Firewall might be blocking
- Try accessing from the Windows NUC itself first

### Docker Won't Start

**Check if Docker service is running**:
```bash
sudo systemctl status docker
```

Should say "active (running)".

If not:
```bash
sudo systemctl start docker
```

**Check if your user is in docker group**:
```bash
groups
```

Should see "docker" in the list.

If not:
```bash
sudo usermod -aG docker $USER
```

Then log out and back in.

### Forgot Your VM Password

Unfortunately, you'll need to recreate the VM from scratch. There's no easy password reset on Ubuntu Server without console access.

**Prevention**: Write down your password somewhere safe!

---

## Daily Operations

### Check Everything is Running

```bash
iot status
```

All containers should show "Up".

### View Recent Data

```bash
iot query 30m 10
```

Shows last 30 minutes of data, 10 rows.

### Check Logs

If something seems wrong:

```bash
iot la 30
```

Shows last 30 lines from all services.

### Backup Your Data

Run this weekly:

```bash
iot backup
```

Backups are stored in `~/backups/`

To copy backups to your Windows host, use WinSCP or similar file transfer tool.

### Add New Sensors

1. Add sensor in Govee Home app
2. Assign it to a room
3. Run: `iot update`
4. Wait 1 minute
5. Check: `iot mqtt "gv2mqtt/#" 20`
6. New sensor should appear in the messages

### Restart After Power Outage

The stack will auto-start. Just verify:

```bash
iot status
```

If anything is down:

```bash
iot up
```

### Update the Stack

When new features are added to the GitHub repo:

```bash
cd ~/dpx_showsite_ops
git pull origin master
iot restart
```

---

## What's Next?

You now have a working IoT monitoring system! Here are some ideas for what to do next:

**Customize Grafana**:
- Add more panels (min/max, averages, alerts)
- Change time ranges (24 hours, 7 days, etc.)
- Set up email alerts when temperature goes above/below thresholds

**Add More Sensors**:
- Buy more Govee sensors for different rooms
- They automatically get discovered

**Phase 4 - BLE Gateway**:
- Set up local Bluetooth reading for faster updates (<5 seconds instead of 10 minutes)
- See the main repository documentation

**Phase 5 - Network Backups**:
- Automate backups of your network switches and routers
- See the main repository documentation

---

## Getting Help

**Check the documentation**:
- Main README: https://github.com/dubpixel/dpx_showsite_ops
- Architecture docs: https://github.com/dubpixel/dpx_showsite_ops/blob/main/docs/ARCHITECTURE.md
- Grafana setup: https://github.com/dubpixel/dpx_showsite_ops/blob/main/docs/GRAFANA_SETUP.md

**Open an issue**:
- https://github.com/dubpixel/dpx_showsite_ops/issues

**Check logs**:
- Most problems can be diagnosed with `iot la 50` (last 50 lines of all logs)

---

## Congratulations!

You've successfully deployed a production-grade IoT monitoring system. You now understand:

- Linux basics (command line, editing files)
- Docker containers
- MQTT messaging
- Time-series databases
- Data visualization
- Networking (static IPs, mDNS)
- Remote access (VPNs, tunnels)

These are valuable skills that apply to many other projects!

---

**Last Updated**: 2025-02-05  
**Guide Version**: 1.0  
**For**: dpx-showsite-ops v1.0.1
