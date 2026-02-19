# The First Timer's Guide to dpx-showsite-ops
## From Bare Metal to Beautiful Graphs

**Target Audience**: Someone who has never touched Docker, Linux, or IoT before  
**Time Required**: 2-3 hours for initial setup  
**Skill Level**: Beginner (we assume nothing)

**testing a/o 2.16.26**

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
10. [Part 8: Public Dashboards (Optional)](#part-8-public-dashboards-optional)
11. [Part 9: Theengs Gateway for BLE (Optional)](#part-9-theengs-gateway-for-ble-optional)
12. [Part 10: ESP32 BLE Gateway Setup (Recommended)](#part-10-esp32-ble-gateway-setup-recommended)
13. [Part 11: Geist Watchdog Environmental Monitor (SNMP)](#part-11-geist-watchdog-environmental-monitor-snmp)
14. [Troubleshooting](#troubleshooting)
15. [Daily Operations](#daily-operations)

---

## What You're Building

By the end of this guide, you'll have:

- A Linux VM running on your Windows NUC
- Temperature and humidity data from sensors flowing into a database
- Beautiful Grafana dashboards showing your sensor data
- The ability to view dashboards from anywhere (phone, laptop, etc.)
- Automatic device discovery and mapping

**The data flow** (two parallel paths):

**Cloud Path** (10-20 min latency):
```
Govee Sensor → Govee Cloud → govee2mqtt → MQTT → Telegraf → InfluxDB → Grafana
```

**BLE Path** (<5 sec latency):
```
Govee Sensor → ESP32/Theengs Gateway → MQTT → BLE Decoder → InfluxDB → Grafana
```

---

## Hardware You Need

### Required
- **Windows NUC** (or any Windows PC with 8GB+ RAM)
- **Govee Sensors**: 
  - **H5075** (RECOMMENDED): BLE-only, Theengs decoder support, excellent reliability
  - **H5051**: Cloud + BLE capable, requires custom decoder, good option
  - ❌ **NOT H5074**: Poor BLE reliability (avoid this model)
  - See [sensor comparison table](context_public/CONTEXT.md#sensor-comparison) for details
- **Internet connection** (wired recommended)
- **Router** with ability to set static IP (most routers can do this)

### Optional but Recommended
- **Bluetooth USB dongle** (if your NUC doesn't have Bluetooth)
- **Smartphone** (for Govee app setup)

---

## Part 1: Windows NUC Setup

**Time Required**: 30-45 minutes

### Pre-Flight Checklist

Before you begin, make sure you have:

**Downloads**:
- [ ] Ubuntu Server 24.04 LTS ISO (~2.5 GB)
  - URL: https://ubuntu.com/download/server
  - File: `ubuntu-24.04.X-live-server-amd64.iso`
  - Architecture: **amd64** (correct for Intel/AMD 64-bit CPUs)

**Hyper-V Setup**:
- [ ] Hyper-V Manager installed and accessible
- [ ] Virtual Switch will be created in Step 1.2

---

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

**Quick Reference Table** for VM wizard:

| Step | Setting | Value |
|------|---------|-------|
| **Name and Location** | Name | `dpx-showsite-ops` |
| | Store in different location | ☐ Optional (check if using secondary SSD) |
| | Location | `D:\VMs\dpx-showsite-ops` (if using second drive) |
| **Generation** | Type | **Generation 2** ✓ |
| **Memory** | Startup memory | `4096 MB` (4 GB) |
| | Use Dynamic Memory | ☑ Check |
| **Networking** | Connection | **External Network** |
| **Hard Disk** | Action | ⦿ Create a virtual hard disk |
| | Size | `64 GB` (or **50 GB minimum**) |
| | Location | Same as VM or secondary SSD |
| **Installation** | Options | ⦿ Install from bootable image |
| | ISO | Browse to Ubuntu Server ISO |

**Note**: If you have a secondary SSD, you can store the VM files there for better performance. In "Name and Location" step, check "Store the virtual machine in a different location" and browse to your secondary drive (e.g., `D:\VMs\`).

Click **Finish** when done.

### 2.2: Adjust VM Settings

Before we start it, let's tweak a few things:

**Steps**:
1. In Hyper-V Manager, right-click **dpx-showsite-ops** → **Settings**
2. Go to **Security** on the left
3. **UNCHECK** "Enable Secure Boot" (important!)
   - **Alternative**: If you prefer to keep Secure Boot enabled, change template to "Microsoft UEFI Certificate Authority"
4. Go to **Processor** on the left
5. Set **Number of virtual processors** to `2`
6. Click **OK**

**Note**: The disk size must be at least 50 GB. If you specified less, you may run into space issues during setup or when deploying the stack.

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
        - 192.168.1.X/24
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

Should now show `192.168.1.X` (or whatever you set)

**Test internet**:
```bash
ping -c 3 google.com
```

You should see responses. Press `Ctrl + C` if it keeps going.

### 3.5: Install Helpful Tools

```bash
sudo apt install -y git curl wget vim avahi-daemon
```

**Install GitHub CLI** (makes git authentication and PRs easier):
```bash
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install -y gh
```

**Enable mDNS** (lets you use dpx-showsite-ops.local instead of IP):
```bash
sudo systemctl enable --now avahi-daemon
```

### 3.6: Set Up Tailscale

**Why now?** Tailscale enables remote SSH access immediately. After this step, you can close the Hyper-V console and do all remaining work via SSH from your comfortable main computer!

**Install Tailscale on VM**:
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

**Install Tailscale on your main computer**:
1. Go to https://tailscale.com/download
2. Download for your OS (Windows/Mac/Linux)
3. Install and log in with the same account

**Test remote access**:

From your main computer, open a terminal and try:
```bash
ssh dubpixel@dpx-showsite-ops
```

If it connects, **you're done with the Hyper-V console!** You can minimize it and work from your main computer for all remaining steps.

### 3.7: Set Up GitHub SSH Access

If you need to work with private GitHub repositories or push code changes, set up SSH keys now.

**Generate SSH key on VM**:
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

Press Enter 3 times (default location, no passphrase).

**Display your public key**:
```bash
cat ~/.ssh/id_ed25519.pub
```

**Copy the entire output** (starts with `ssh-ed25519 ...`).

**Add to GitHub**:
1. Go to https://github.com/settings/keys
2. Click **New SSH key**
3. Title: `dpx-showsite-ops VM`
4. Paste your public key
5. Click **Add SSH key**

**Test it**:
```bash
ssh -T git@github.com
```

Should see: `Hi username! You've successfully authenticated...`

**Note**: If you don't need private repos, you can skip this step and use HTTPS git URLs instead.

#### Alternative: GitHub CLI (Easier)

If you installed GitHub CLI in Part 3.5, you can use it instead of SSH keys:

**Authenticate**:
```bash
gh auth login
```

Follow the interactive prompts:
1. Select "GitHub.com"
2. Select "HTTPS"
3. Authenticate via web browser

**Test it**:
```bash
gh repo view dubpixel/dpx_showsite_ops
```

**Benefits**:
- No SSH key management required
- Works with HTTPS git URLs
- Can create pull requests from CLI: `gh pr create`
- Recommended for beginners

**Note**: SSH keys are still required for git submodules with private repos, but `gh` handles regular git operations via HTTPS.

### 3.8: Disable IPv6 (Required for Cloud Integration)

**Required if using govee2mqtt** (cloud Govee data path). This fixes AWS IoT timeout issues on Hyper-V VMs.

```bash
sudo sysctl -w net.ipv6.conf.eth0.disable_ipv6=1
echo "net.ipv6.conf.eth0.disable_ipv6=1" | sudo tee -a /etc/sysctl.conf
```

**Verify**:
```bash
ip addr show eth0 | grep inet6
```

Should show nothing (IPv6 disabled).

**If you're not using govee2mqtt**, you can skip this step.

### 3.9: VM Ready Checklist

Before proceeding to Docker deployment, verify everything is working:

- [ ] VM boots successfully
- [ ] Can log in locally (Hyper-V console)
- [ ] Can SSH remotely: `ssh dubpixel@192.168.1.X` (where X is your static IP)
- [ ] Can SSH via Tailscale: `ssh dubpixel@dpx-showsite-ops`
- [ ] Static IP is set and pingable: `ping 192.168.1.X`
- [ ] Internet working: `ping google.com`
- [ ] Base tools installed: `git --version`, `docker --version` (docker comes in Part 4)
- [ ] mDNS working: `ping dpx-showsite-ops.local` (from another computer)
- [ ] (Required for cloud) IPv6 disabled: `ip addr show eth0 | grep inet6` shows nothing
- [ ] (Optional) GitHub SSH access working

**If all checks pass, your VM is ready!**

### 3.10: Quick Reference

Keep this handy for future access:

**VM Access**:
- **Local IP**: `192.168.1.X` (your static IP)
- **Hostname**: `dpx-showsite-ops.local`
- **Tailscale**: `dpx-showsite-ops` (from any device on your Tailscale network)
- **User**: `dubpixel` (or whatever you chose)
- **Password**: [your password]

**VM Resources**:
- **RAM**: 4 GB (dynamic)
- **Disk**: 50-64 GB
- **CPUs**: 2 cores

**Network**:
- **Switch**: External Network (connected to your LAN)
- **IP Assignment**: Static (192.168.1.X/24)
- **Gateway**: 192.168.1.1
- **DNS**: 8.8.8.8, 8.8.4.4

**Next Steps**: Proceed to Part 4 to install Docker!

---

## Part 4: Install Docker

**Note**: Docker installation is manual (not part of setup.sh). Complete this section before proceeding to Part 5.

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

# Showsite name - must match MQTT Base Topic setting on ESP32 gateways
# This is used by BLE decoder to subscribe to the correct MQTT topics
SHOWSITE_NAME=my_venue

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

## Part 6: Grafana InfluxDB Connection (Auto-Configured)

The InfluxDB datasource should auto-provision when Grafana starts via the configuration in `grafana/provisioning/datasources/influxdb.yaml`.

**Verify auto-provisioning worked:**

### 6.1: Access Grafana

On your **main computer** (not the VM), open a web browser and go to:

```
http://192.168.1.X:3000
```

(Replace 192.168.1.X with your VM's IP if you used something different)

You should see the Grafana login page.

**Login**:
- Username: `admin`
- Password: `grafanapass123`

It will ask you to change the password. You can click "Skip" or set a new one.

### 6.2: Verify InfluxDB Datasource

**Check if auto-provisioning worked**:
1. On the left sidebar, click the **⚙️ gear icon** (Configuration)
2. Click **Data sources**
3. You should see **InfluxDB** listed with a green checkmark

If you see the InfluxDB datasource, you're done! Skip to Part 7.

If the datasource is missing or shows errors, continue with manual setup below.

### 6.3: Understanding Provisioning (Optional)

The datasource is configured in `grafana/provisioning/datasources/influxdb.yaml`:

```yaml
apiVersion: 1
datasources:
  - name: InfluxDB
    type: influxdb
    access: proxy
    url: http://influxdb:8086
    jsonData:
      version: Flux
      organization: home
      defaultBucket: sensors
    secureJsonData:
      token: my-super-secret-token
```

**Note**: The token must match your `.env` file's `INFLUXDB_TOKEN`. If you change the token, update both files and restart Grafana: `iot restart grafana`

### 6.4: Manual Configuration (Fallback Only)

**Only follow these steps if auto-provisioning failed.**

**Steps**:
1. On the left sidebar, click the **⚙️ gear icon** (Configuration)
2. Click **Data sources**
3. Click **Add data source** button
4. Scroll down and click **InfluxDB**

**Configure it**:
- **Name**: `InfluxDB`
- **Query Language**: Select **Flux** from dropdown
- **URL**: `http://influxdb:8086`
- **Access**: Leave as "Server (default)"
- **Auth**: Make sure ALL boxes are UNCHECKED
- Scroll down to **InfluxDB Details**:
  - **Organization**: `home`
  - **Token**: `my-super-secret-token`
  - **Default Bucket**: `sensors`

**Test it**:
- Scroll to bottom
- Click **Save & Test**
- You should see a green checkmark: "datasource is working. 1 buckets found"

If you see red errors, double-check your entries match the provisioning YAML.

---

## Part 7: Create Your First Dashboard

**Note**: A default temperature monitoring dashboard auto-loads from `grafana/provisioning/dashboards/dashboard-temperature-sensors.json` showing both cloud and BLE data paths. This section teaches you to create custom dashboards or modify the default.

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
3. Choose one of these queries based on your data source:

**Temperature - Cloud Data Only** (10-20 min latency):
```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.source == "gv_cloud")
  |> filter(fn: (r) => r.sensor_type == "temperature")
  |> filter(fn: (r) => r.device_name != "h5074_4e6f")
  |> filter(fn: (r) => r.device_name != "studio_5051_down")
  |> map(fn: (r) => ({r with _field: r.room + " - " + r.device_name}))
```

**Temperature - BLE Data Only** (<5 sec latency):
```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.source == "dpx_ops_decoder")
  |> filter(fn: (r) => r.sensor_type == "temperature")
  |> filter(fn: (r) => r.device_name != "h5074_4e6f")
  |> map(fn: (r) => ({r with _field: "|" + r.source_node + "| - " + r.room + " - " + r.device_name}))
```

**Temperature - Both Cloud & BLE** (compare latency):
```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.source == "gv_cloud" or r.source == "dpx_ops_decoder")
  |> filter(fn: (r) => r.sensor_type == "temperature")
  |> filter(fn: (r) => r.device_name != "h5074_4e6f")
  |> map(fn: (r) => ({r with _field: 
    r.source + 
    (if exists r.source_node then " -- |" + r.source_node + "| - " else " - ") + 
    r.room + " - " + r.device_name
  }))
```

**About these queries**:
- `device_name != "h5074_4e6f"` filters out H5074 sensors (unreliable BLE)
- `device_name != "studio_5051_down"` excludes a specific duplicate device (adjust for your setup)
- The `map()` function creates custom series names combining source, room, and device
- `${__field.name}` in panel settings references this custom name for legends/titles

**Customize the panel**:
1. On the right side, under "Panel options":
   - **Title**: Change to "Temperature"
2. Under "Standard options":
   - **Unit**: Select "Temperature" → "Fahrenheit (°F)" (or Celsius if you prefer)
   - **Display name**: Use `${__field.name}` to show the custom field names from the map() function
3. Click **Run query** button (top right) or wait a few seconds

You should see a graph appear!

**Save the panel**:
- Click **Apply** button (top right)

### 7.4: Add More Panels

**Add Humidity Panel**:
1. Click **Add** dropdown (top right) → **Visualization**
2. Select **InfluxDB**
3. Paste this query (adjust filters as needed):

```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.source == "gv_cloud" or r.source == "dpx_ops_decoder")
  |> filter(fn: (r) => r.sensor_type == "humidity")
  |> filter(fn: (r) => r.device_name != "h5074_4e6f")
  |> map(fn: (r) => ({r with _field: r.room + " - " + r.device_name}))
```

**Customize**:
- **Title**: "Humidity"
- **Unit**: "Misc" → "Percent (0-100)"
- **Display name**: `${__field.name}`

Click **Apply**

**Add Battery Level Panel** (BLE sensors only):
```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.device_name != "h5074_4e6f")
  |> filter(fn: (r) => r.source_node == "dpx_ops_1")
  |> filter(fn: (r) => r.sensor_type == "battery")
  |> map(fn: (r) => ({r with _field: "|" + r.device_name + "|"}))
  |> last()
```

**Customize**:
- **Title**: "Battery Levels"
- **Unit**: "Percent (0-100)"
- **Visualization**: Try "Gauge" or "Stat" panel type
- Note: `last()` shows only the most recent value

**Add Signal Strength (RSSI) Panel** (BLE sensors only):
```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.device_name != "h5074_4e6f")
  |> filter(fn: (r) => r.source_node == "dpx_ops_1")
  |> filter(fn: (r) => r.sensor_type == "rssi")
  |> map(fn: (r) => ({r with _field: "|" + r.device_name + "|"}))
  |> last()
```

**Customize**:
- **Title**: "Signal Strength"
- **Unit**: "Signal strength (dBm)"
- **Visualization**: "Gauge" or "Stat"
- Note: RSSI values are negative; closer to 0 is better (e.g., -50 is better than -80)

### 7.5: Save the Dashboard

1. Click the **Save dashboard** icon (floppy disk, top right)
2. Name it: "Room Monitoring" (or whatever you want)
3. Click **Save**

**You now have a working dashboard!** 🎉

---

## Part 8: Public Dashboards (Optional)

Want to share your dashboard with someone who doesn't have Tailscale? Use Cloudflare Tunnel.

### 8.1: Install Cloudflare Tunnel

**In your VM terminal**:
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
```

### 8.2: Start a Temporary Tunnel

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

## Part 9: Theengs Gateway for BLE (Optional)

Want faster updates? Instead of waiting 10 minutes for cloud sync, read sensors directly via Bluetooth.

### 9.1: Install Python on Windows

**On your Windows NUC**:

**Option A: GUI Installer** (recommended for first-timers)

1. Go to: https://www.python.org/downloads/
2. Download Python 3.11 or newer
3. Run the installer
4. ☑ **CHECK** "Add Python to PATH"
5. Click **Install Now**

**Option B: Command Line** (using winget)

Open **PowerShell** as Administrator and run:

```powershell
winget install Python.Python.3.11
```

This automatically adds Python to PATH. Verify installation:

```powershell
python --version
```

**Note**: If you already have Chocolatey installed, you can also use: `choco install python311`

### 9.2: Install Visual Studio Build Tools

Theengs needs C++ compiler tools.

**Option A: GUI Installer** (recommended for first-timers)

1. Go to: https://visualstudio.microsoft.com/downloads/
2. Scroll to "Tools for Visual Studio"
3. Download **Build Tools for Visual Studio 2022**
4. Run the installer
5. Select **Desktop development with C++**
6. Click **Install** and wait for completion (takes 5-10 minutes)

**Option B: Command Line** (using winget)

Open **PowerShell** as Administrator and run:

```powershell
winget install Microsoft.VisualStudio.2022.BuildTools --silent --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
```

This installs Build Tools with the C++ workload. Takes 5-10 minutes.

**Note**: If you already have Chocolatey: `choco install visualstudio2022buildtools --package-parameters "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`

### 9.3: Verify pip (Python Package Manager)

Python 3.11+ includes pip by default, but let's verify it's available.

**In PowerShell**:

```powershell
python -m pip --version
```

**If you see a version number** (e.g., `pip 23.x.x`): ✅ Skip to 9.4

**If you get "No module named pip"**, install it:

```powershell
python -m ensurepip --upgrade
```

Or download the pip installer:

```powershell
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py
```

**Verify pip works**:

```powershell
python -m pip --version
```

### 9.4: Install Theengs Gateway

**In PowerShell as Administrator**:

```powershell
python -m pip install TheengsGateway
```

**If you see "Defaulting to user installation"**: This means PowerShell isn't running as Administrator. Either:
- Close PowerShell and reopen **as Administrator** (right-click → Run as Administrator), OR
- Continue anyway - the warning is harmless, TheengsGateway will install to your user directory

Wait for installation to complete (takes 1-2 minutes).

**Verify installation**:

```powershell
python -m TheengsGateway --version
```

Should show the Theengs Gateway version number.

### 9.5: Run Theengs Gateway

**Start Theengs Gateway**:
```powershell
python -m TheengsGateway -H dpx-showsite-ops.local -P 1883 -ll DEBUG
```

**If mDNS isn't working**, use the VM's IP address instead:
```powershell
python -m TheengsGateway -H 192.168.1.X -P 1883 -ll DEBUG
```

**Key options**:
- `-ll DEBUG`: Show decoded sensor data in console (recommended for setup/testing)
- `-ll INFO`: Quieter - just connection status and message counts
- `-a hci0`: Specify Bluetooth adapter (auto-detected by default)

You should see output about discovering devices:
```
DEBUG: Discovered device: A4:C1:38:XX:XX:XX
DEBUG: Temperature: 72.5°F, Humidity: 45%
INFO: Published to home/TheengsGateway/BTtoMQTT/A4C138XXXXXX
```

**Note**: If you want to integrate Theengs with the dpx-showsite-ops ble_decoder.py (similar to ESP32 gateways), you may need to add the `--publish-advdata` flag. This publishes raw advertising data for custom decoding. Test without it first to see decoded data.

Leave this running.

**To stop it**: Press `Ctrl + C`

**Note**: The BLE decoder is now containerized and auto-starts with `iot up` (see docker-compose.yml). Theengs Gateway on Windows is still useful as a fallback gateway or for multi-location deployments, but is not required if you're using ESP32 gateways.

---

## Part 10: ESP32 BLE Gateway Setup (Recommended)

**For real-time BLE data (<5 sec latency)**, deploy ESP32 hardware gateways instead of or alongside Theengs on Windows.

### Why ESP32?
- **Dedicated hardware**: No PC required, low power
- **Multi-site ready**: Deploy at remote locations
- **Faster setup**: 5-10 min per gateway
- **Production proven**: OpenMQTTGateway firmware used worldwide

### 10.1: Hardware Requirements

- **Board**: ESP32-based hardware with WiFi (custom DPX boards or ESP32 DevKit)
- **USB Cable**: For initial firmware flash
- **Browser**: Chrome or Edge (for web installer)
- **Network**: WiFi credentials + MQTT broker IP

### 10.2: Flash Firmware

1. **Open web installer**: https://docs.openmqttgateway.com/upload/web-install.html

2. **Select firmware**: Choose **esp32feather-ble** (NOT esp32dev-ble)
   - For custom DPX boards: **esp32feather-ble**
   - For generic ESP32 DevKit: esp32dev-ble

3. **Connect ESP32**: Plug into computer via USB

4. **Click "Install"**: Browser will ask to select serial port
   - Select the ESP32 port (usually "/dev/cu.usbserial-*" on Mac, "COM*" on Windows)
   - Click "Connect"

5. **Wait for flash**: Takes 2-3 minutes
   - Progress bar shows upload status
   - Don't disconnect during flash!

6. **Flash complete**: Click "Next" when done

### 10.3: Configure Gateway

1. **Connect to ESP32 WiFi**:
   - Look for WiFi network: **"OpenMQTTGateway"**
   - Password: **"your_password"** (default)
   - Connect from your phone or laptop

2. **Open configuration portal**:
   - Browser should auto-open to 192.168.4.1
   - If not, manually open: http://192.168.4.1

3. **Configure WiFi**:
   - Click "Configure WiFi"
   - Select your network SSID
   - Enter WiFi password

4. **Configure MQTT**:
   - MQTT Server: `<your-vm-ip>` (e.g., 192.168.1.X)
   - MQTT Port: `1883`
   - MQTT User: (leave blank for anonymous)
   - MQTT Password: (leave blank for anonymous)

4a. **Configure Gateway Naming** (IMPORTANT):
   
   OpenMQTT has **three settings** you should configure:
   
   - **MQTT Base Topic**: Set this to your showsite name (e.g., `my_venue`)
     - Default is `home/` if not set
     - This must match `SHOWSITE_NAME` in your `.env` file
   
   - **Gateway Name**: Set this to a device identifier (e.g., `gateway_1`, `gateway_2`, `esp32_alpha`)
     - This identifies which physical ESP32 captured the data
     - Use simple device IDs, NOT location names
   
   - **MQTT Discovery Prefix** (optional but recommended): Set to `dpx_showsite_ops`
     - Default is `homeassistant` (for Home Assistant integration)
     - Keeps discovery metadata organized if you're not using Home Assistant
     - Not critical for basic operation
   
   **⚠️ Important**: Don't use location names (studio, stage, etc) for gateway names. Physical locations come from the Govee app and are added by the BLE decoder automatically.
   
   **Example configuration**:
   - MQTT Base Topic: `my_venue`
   - Gateway Name: `gateway_1`
   - MQTT Discovery Prefix: `dpx_showsite_ops`
   - Resulting topic: `my_venue/gateway_1/BTtoMQTT/#`

5. **Save & Reboot**:
   - Click "Save"
   - ESP32 reboots and connects to your WiFi

### 10.3a: Understanding MQTT Topic Structure

**IMPORTANT**: OpenMQTT uses two separate settings to build your MQTT topic path.

**How OpenMQTT topic structure works**:

OpenMQTT publishes to: `{MQTT_Base_Topic}/{Gateway_Name}/BTtoMQTT/{MAC_Address}`

Example: `my_venue/gateway_1/BTtoMQTT/B4FBE42F59EA`

**The two settings in OpenMQTT config portal (192.168.4.1)**:

1. **MQTT Base Topic** (defaults to `home/` if not set)
   - Set this to your showsite/venue name
   - Examples: `my_venue`, `festival_2026`, `warehouse_show`
   - Must match `SHOWSITE_NAME` in your `.env` file

2. **Gateway Name** (defaults to `OpenMQTTGateway` if not set)
   - Set this to a unique device identifier
   - Examples: `gateway_1`, `gateway_2`, `esp32_alpha`, `omg_01`
   - Use simple device IDs that identify the hardware
   - **Don't use location names** (studio, stage, lobby, etc)

**Why no location names for gateways?**

Physical locations are assigned to **sensors** in the Govee app and added by the BLE decoder. If you name a gateway "studio", you'll have confusing nested locations when the decoder adds the sensor's actual room assignment.

**Topic flow example**:

```
Raw BLE from ESP32:
my_venue/gateway_1/BTtoMQTT/B4FBE42F59EA
    ↓         ↓          ↓           ↓
 showsite   device    message   MAC address
            name       type

                ↓ BLE Decoder processes ↓

Decoded output:
my_venue/dpx_ops_decoder/gateway_1/living_room/temp_sensor_5051/temperature
    ↓         ↓            ↓           ↓              ↓              ↓
 showsite  decoder    source      room (from    device (from    metric
                     gateway     Govee API)     Govee API)
```

**How BLE decoder subscribes**:

The decoder subscribes to: `{SHOWSITE_NAME}/+/BTtoMQTT/#`
- `SHOWSITE_NAME` comes from your `.env` file
- `+` matches any gateway name
- `#` matches any MAC address

**Multi-gateway deployments**:
- All gateways use same **MQTT Base Topic**: `my_venue`
- Each gateway has unique **Gateway Name**: `gateway_1`, `gateway_2`, `gateway_3`
- BLE decoder automatically tracks which gateway saw which sensor
- You can filter by source gateway in Grafana queries

**Why this matters**:
- Clean separation between hardware (gateways) and physical layout (rooms)
- Allows you to move/add gateways without changing location mappings
- Sensor locations stay accurate even if you relocate an ESP32
- Multi-site deployments just need different `SHOWSITE_NAME` values

### 10.4: Verify Gateway

**On your VM**, check that ESP32 is publishing.

Replace `my_venue` and `gateway_1` with your actual MQTT Base Topic and Gateway Name:

```bash
iot mqtt "my_venue/gateway_1/BTtoMQTT/#" 10
```

Or use wildcard to see all gateways for your showsite:

```bash
iot mqtt "my_venue/+/BTtoMQTT/#" 10
```

You should see JSON messages with BLE device data:
```json
{"id":"B4FBE42F59EA","mac_type":1,"manufacturerdata":"88ec004e06f00864e00101","rssi":-65}
```

**If you see data**: ✅ Gateway is working!

**If no data**:
- Check ESP32 LEDs (should be on/blinking)
- Verify WiFi connection (ESP32 on same network as VM)
- Check MQTT broker IP is correct
- Try power cycling the ESP32

### 10.5: Multi-Gateway Deployment (Optional)

For larger venues or multiple rooms where a single ESP32 can't reach all sensors:

1. **Flash additional ESP32s**: Repeat steps 10.2-10.3 for each gateway

2. **Configure each gateway** in the config portal:
   - **All gateways**: Set MQTT Base Topic to same showsite name (e.g., `my_venue`)
   - **Each gateway**: Set unique Gateway Name (`gateway_1`, `gateway_2`, `gateway_3`)

3. **Example multi-gateway setup**:

| Device ID | MQTT Base Topic | Gateway Name | Resulting MQTT Topic | Notes |
|-----------|----------------|--------------|----------------------|-------|
| ESP32 #1 | `my_venue` | `gateway_1` | `my_venue/gateway_1/BTtoMQTT/#` | First floor ESP32 |
| ESP32 #2 | `my_venue` | `gateway_2` | `my_venue/gateway_2/BTtoMQTT/#` | Second floor ESP32 |
| ESP32 #3 | `my_venue` | `gateway_3` | `my_venue/gateway_3/BTtoMQTT/#` | Outdoor/remote area |

4. **Verify all gateways are publishing**:
   ```bash
   iot mqtt "my_venue/+/BTtoMQTT/#" 30
   ```
   
   You should see messages from different gateway names:
   ```
   my_venue/gateway_1/BTtoMQTT/B4FBE42F59EA {...}
   my_venue/gateway_2/BTtoMQTT/A1C3D5E7F9AB {...}
   my_venue/gateway_3/BTtoMQTT/1234ABCD5678 {...}
   ```

**Coverage planning tips**:
- BLE range is typically 30-50 feet through walls
- Multiple gateways can see the same sensor (decoder handles duplicates)
- Place gateways where you need coverage, not necessarily near sensors
- Use Grafana to see which gateway has best RSSI for each sensor

### 11.6: Troubleshooting

**Can't connect to OpenMQTTGateway WiFi**:
- Hold ESP32 BOOT button for 5 seconds to reset WiFi
- Power cycle ESP32
- Try from a different device (phone vs laptop)

**Configuration portal won't open**:
- Make sure connected to "OpenMQTTGateway" WiFi
- Try http://192.168.4.1 manually
- Clear browser cache
- Try different browser (Chrome recommended)

**ESP32 won't stay connected to WiFi**:
- Check WiFi signal strength (move closer to AP)
- Verify WiFi password is correct
- Check router doesn't block new devices
- Try 2.4GHz WiFi (ESP32 doesn't support 5GHz)

**No BLE data appearing**:
- BLE sensors must be within ~30 feet of ESP32
- Remove sensor batteries for 10 sec, reinsert
- Check sensor is broadcasting: should show in Govee app
- Verify ESP32 is publishing *something*: `iot mqtt "my_venue/+/BTtoMQTT/#"` (replace `my_venue` with your showsite name)

**Wrong firmware flashed**:
- Reflash with correct build: **esp32feather-ble** for DPX boards
- Use "Erase Flash" option in web installer first

### 10.7: Next Steps

With ESP32 gateway(s) deployed:

1. **BLE decoder already running**: Automatically started with `iot up`
2. **Check decoder logs**: `iot lb` or `iot ble-status`
3. **Telegraf**: Already configured to collect both cloud + BLE data
4. **Grafana**: Dashboards show both sources with source tags
5. **Monitor latency**: BLE should be <5 sec, cloud 10-20 min

**Windows Theengs Gateway**: Available as fallback option (see Part 10)

---

## Part 11: Geist Watchdog Environmental Monitor (SNMP)

**For infrastructure monitoring** (server rooms, network closets): Add SNMP-based environmental monitoring with Geist Watchdog 100 devices.

### What is the Geist Watchdog?

The Geist Watchdog 100 is a network-attached environmental monitor designed for data centers and server rooms. It monitors:

- **Temperature**: Built-in and remote sensors
- **Humidity**: Air moisture levels
- **Dew Point**: Condensation risk
- **Remote Sensors**: Supports external temp/humidity probes

**Key Features**:
- SNMP v1/v2c/v3 for polling
- SNMP traps for real-time alerts
- Web interface for configuration
- Multiple sensor support
- Network-based (Ethernet)

### 11.1: Pre-Flight Checks

**Before configuring Telegraf**, verify the Geist Watchdog is accessible and discover what sensors are connected.

**Install SNMP tools** (on your Mac/laptop, not the VM):

```bash
# macOS:
brew install net-snmp

# Linux:
sudo apt install snmp snmp-mibs-downloader
```

**Test basic connectivity**:

```bash
# Verify device responds (replace with your device IP):
snmpget -v2c -c public 10.0.10.162 1.3.6.1.2.1.1.5.0

# Should return: SNMPv2-MIB::sysName.0 = STRING: "Watchdog100"
```

**Discover connected sensors**:

```bash
# Internal sensors (built into Watchdog):
snmptable -v2c -c public 10.0.10.162 1.3.6.1.4.1.21239.5.1.2

# Remote temperature-only sensors:
snmptable -v2c -c public 10.0.10.162 1.3.6.1.4.1.21239.5.1.4

# Remote multi-sensors (temp + humidity):
snmptable -v2c -c public 10.0.10.162 1.3.6.1.4.1.21239.5.1.5

# Check temperature units (0=Celsius, 1=Fahrenheit):
snmpget -v2c -c public 10.0.10.162 1.3.6.1.4.1.21239.5.1.1.7.0
```

**What to look for**:
- Which sensor tables have data
- Sensor names (you can configure these in Geist web UI)
- Temperature values (will be 10x actual, e.g., 725 = 72.5°F)
- Availability status (1=connected, 0=disconnected)

### 11.2: Geist Configuration Already Complete

The Geist Watchdog integration is pre-configured in this repository:

**File created**: `telegraf/conf.d/geist-watchdog.conf`

**What it does**:
- Polls device every 30 seconds via SNMP
- Auto-discovers all connected sensors (internal + remote)
- Scales temperature from 0.1 degrees to readable values
- Filters out disconnected sensors automatically
- Tags data with sensor names from device
- Pulls location metadata from device configuration

**Review the configuration**:

```bash
cd ~/dpx_showsite_ops
cat telegraf/conf.d/geist-watchdog.conf
```

**Key settings**:
- **Device IP**: `10.0.10.162` (change if different)
- **Community string**: `public` (read-only)
- **Poll interval**: `30s`
- **Auto-discovery**: Walks all sensor tables
- **Scaling**: Temperature divided by 10 (725 → 72.5)

### 11.3: Customize Device IP (if needed)

If your Geist Watchdog has a different IP address:

**Edit the config file**:

```bash
nano telegraf/conf.d/geist-watchdog.conf
```

**Find this line** (near top):

```toml
agents = ["10.0.10.162:161"]
```

**Change to your device IP**:

```toml
agents = ["192.168.1.100:161"]  # Example
```

**Also update** the static tag further down:

```toml
[inputs.snmp.tags]
  source = "geist_watchdog"
  device_ip = "192.168.1.100"  # Match your IP
```

**Save**: `Ctrl+O`, `Enter`, `Ctrl+X`

### 11.4: Deploy and Verify

**Restart Telegraf** to activate the Geist integration:

```bash
iot restart telegraf
```

**Watch logs** for SNMP connection:

```bash
iot logs telegraf -f
```

Look for messages like:
```
gathered 6 metrics from 1 SNMP agents
```

Press `Ctrl+C` to stop log streaming.

**If you see errors**:
- `connection refused`: Check device IP and network connectivity
- `timeout`: Device may be on different subnet or firewall blocking
- `no such object`: OID doesn't exist (sensor type not connected)

### 11.5: Verify Data in InfluxDB

**Check that Geist data is flowing**:

```bash
iot query 2m 100 | grep sensor_name
```

You should see sensor names from your Geist device:
```
sensor_name=Internal
sensor_name=ServerRackIntake
sensor_name=Ambient
```

**Verify temperature scaling** (should be readable, NOT 10x):

```bash
iot query 2m 50 | grep "temperature="
```

Should show values like `temperature=72.5` not `temperature=725`

**Check humidity values**:

```bash
iot query 2m 50 | grep "humidity="
```

Should be 0-100 range (percentage).

### 11.6: Add Geist Metrics to Grafana

**Open Grafana**: `http://192.168.1.X:3000` (use your VM IP)

**Create a new panel** or add to existing dashboard:

1. Click **+ Add** → **Visualization**
2. Select **InfluxDB** datasource
3. Select **Flux** query language

**Temperature query** (all Geist sensors):

```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.source == "geist_watchdog")
  |> filter(fn: (r) => r._field == "temperature")
  |> map(fn: (r) => ({r with _field: r.sensor_name}))
```

**Customize the panel**:
- **Title**: "Geist Watchdog - Temperature"
- **Unit**: Temperature → Fahrenheit (°F) or Celsius (°C)
- **Display name**: `${__field.name}` (shows sensor name)
- **Legend**: Table or list view

**Humidity query** (where available):

```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.source == "geist_watchdog")
  |> filter(fn: (r) => r._field == "humidity")
  |> filter(fn: (r) => r._value > 0)
  |> map(fn: (r) => ({r with _field: r.sensor_name + " Humidity"}))
```

**Customize**:
- **Title**: "Geist Watchdog - Humidity"
- **Unit**: Percent (0-100)

**Set alert thresholds** (optional):
- Temperature > 85°F: Warning
- Temperature > 95°F: Critical
- Humidity > 70%: Warning

Click **Apply** to save the panel, then **Save dashboard**.

### 11.7: Configure SNMP Traps (Optional)

For real-time alerts when thresholds are exceeded, configure SNMP traps.

**On Geist web interface** (http://10.0.10.162):

1. Navigate to **Configuration** → **SNMP**
2. Scroll to **Traps** section
3. Click **Add** icon
4. Configure trap destination:
   - **Host**: Your VM IP address (e.g., `192.168.1.100`)
   - **Port**: `162`
   - **Version**: `v2c`
   - **Community**: `private` (default)
5. Click **Save**

**Update docker-compose.yml** to expose trap port:

```bash
cd ~/dpx_showsite_ops
nano docker-compose.yml
```

Find the `telegraf:` service section and add port mapping:

```yaml
  telegraf:
    image: telegraf:latest
    container_name: telegraf
    restart: unless-stopped
    ports:
      - "162:162/udp"  # Add this line for SNMP traps
    volumes:
      - ./telegraf/telegraf.conf:/etc/telegraf/telegraf.conf:ro
```

**Save**: `Ctrl+O`, `Enter`, `Ctrl+X`

**Restart stack**:

```bash
iot restart
```

**Test trap** (in Geist web UI):
- Click **Test** icon next to trap destination
- Check Telegraf logs: `iot logs telegraf | grep trap`

### 11.8: Troubleshooting Geist Integration

**No data in InfluxDB**:

```bash
# Check Telegraf can reach device:
snmpget -v2c -c public 10.0.10.162 1.3.6.1.2.1.1.5.0

# Verify Telegraf is polling:
iot logs telegraf | grep -i snmp

# Check for errors:
iot logs telegraf | grep -i error
```

**Temperature values look wrong**:

If you see `temperature=725` instead of `72.5`:
- Math processor may not be applied
- Check `telegraf/conf.d/geist-watchdog.conf` has `[[processors.math]]` section
- Restart Telegraf: `iot restart telegraf`

**Sensor shows as unavailable**:

The Starlark processor filters out sensors with `available=0`. This is normal for disconnected sensors.

To see all sensor states (including unavailable):
- Comment out the `[[processors.starlark]]` section in config
- Restart Telegraf

**SNMP timeout errors**:

```bash
# Check device is on same network:
ping 10.0.10.162

# Verify SNMP port is open:
nmap -sU -p 161 10.0.10.162

# Try from VM directly:
ssh dubpixel@dpx-showsite-ops.local
snmpget -v2c -c public 10.0.10.162 1.3.6.1.2.1.1.5.0
```

**Traps not received**:

```bash
# Verify port mapping:
docker ps | grep telegraf

# Check firewall:
sudo ufw status

# Test trap listener:
iot logs telegraf -f
# Then click Test in Geist UI
```

### 11.9: Next Steps

With Geist Watchdog integrated:

1. **Monitor infrastructure temps**: Critical for server room environments
2. **Set alert thresholds**: Temperature and humidity warnings
3. **Compare with room sensors**: Geist vs Govee BLE sensors
4. **Multiple locations**: Add more Geist units with unique IPs
5. **Historical trends**: Track environmental changes over time

**Data retention**: InfluxDB keeps sensor data based on retention policy (check `iot query` for details)

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

**Phase 4 - BLE Gateway** ✅ Complete:
- Local BLE reading deployed and operational (<5 second latency)
- ble-decoder service runs automatically with the stack
- Manage with: `iot ble-status`, `iot lb`, `iot ble-restart`
- See ROADMAP.md for details

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

## Appendix A: Grafana Quick Reference

Manual configuration steps and common operations after running `iot up`.

### Connect InfluxDB Datasource

1. Open Grafana: `http://<server-ip>:3000`
   - Username: `admin`
   - Password: `grafanapass123`

2. Go to: **Configuration** (⚙️) → **Data sources** → **Add data source**

3. Select: **InfluxDB**

4. Configure:
   - **Name**: InfluxDB
   - **Query Language**: Flux
   - **URL**: `http://influxdb:8086`
   - **Auth**: Toggle OFF all options
   - **Organization**: `home`
   - **Token**: `my-super-secret-token`
   - **Default Bucket**: `sensors`

5. Click: **Save & Test** (should show green checkmark)

---

### Find Your Room Names

Query to see available rooms:
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "mqtt_consumer")
  |> keep(columns: ["room"])
  |> distinct(column: "room")
```

Or from CLI:
```bash
iot query 1h 100 | grep room
```

---

### Common Query Templates

#### Temperature Query
```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.sensor_type == "temperature")
  |> filter(fn: (r) => r.room == "your_room_name")
```

#### Humidity Query
```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.sensor_type == "humidity")
  |> filter(fn: (r) => r.room == "your_room_name")
```

---

### Enable Public Dashboards

**Requirements**: Cloudflare Tunnel (`iot tunnel`) or port forwarding

1. Open your dashboard
2. Click: **Share** icon (top right)
3. Tab: **Public dashboard**
4. Toggle: **Enable public dashboard**
5. Click: **Save sharing configuration**
6. Copy: The public URL

---

### Backup Dashboards

```bash
# Backup entire Grafana volume
iot backup

# Export dashboard as JSON (manual)
# Dashboard → ⚙️ → JSON Model → Copy JSON
# Save to: grafana/my-dashboard.json
# Commit to git for version control
```

---

### Troubleshooting

**"Error reading InfluxDB"**
- Verify token: `iot env | grep TOKEN`
- Check InfluxDB running: `iot status`
- Test query: `iot query 1h 5`

**"No data points"**
- Check MQTT: `iot mqtt "gv2mqtt/#" 10`
- Devices MUST be assigned to rooms in Govee app
- Refresh mappings: `iot update`

**Dashboard won't save**
- Check disk space: `df -h`
- Verify volume: `docker volume ls | grep grafana`

---

**Last Updated**: 2025-02-05  
**Guide Version**: 1.0  
**For**: dpx-showsite-ops v1.0.1
