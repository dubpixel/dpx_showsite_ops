# The First Timer's Guide to dpx-showsite-ops
## From Bare Metal to Beautiful Graphs

**Target Audience**: Someone who has never touched Docker, Linux, or IoT before  
**Time Required**: 2-3 hours for initial setup  
**Skill Level**: Beginner (we assume nothing)

**Guide Version**: 2.1 (Updated for dpx-showsite-ops v2.1.0)  
**Last Updated**: March 6, 2026  
**License**: This project is licensed under [GNU GPL-3.0](../LICENSE.txt) as of v2.0.0

**🆕 v2.1.0**: Interactive setup wizard added - no more vim/vi editing required!

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
14. [Part 12: M4300 Network Switch Backups](#part-12-m4300-network-switch-backups)
15. [Troubleshooting](#troubleshooting)
16. [Daily Operations](#daily-operations)
17. [What's Next?](#whats-next)
18. [Appendix A: Grafana Quick Reference](#appendix-a-grafana-quick-reference)
19. [Appendix B: Complete iot Command Reference](#appendix-b-complete-iot-command-reference)

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

**Troubleshooting: Can't ping from VM to Windows host?**

If you can ping **from Windows to the VM** but **not from the VM to Windows**, this is a Windows Firewall issue.

**On the Windows host**, run PowerShell as Administrator:

```powershell
New-NetFirewallRule -DisplayName "Allow ICMPv4-In" -Protocol ICMPv4 -IcmpType 8 -Enabled True -Direction Inbound -Action Allow
```

**Alternative (GUI method)**:
1. Open **Windows Defender Firewall with Advanced Security**
2. **Inbound Rules** → **New Rule**
3. Rule Type: **Custom**
4. Protocol: **ICMPv4** → Customize → **Echo Request**
5. Scope: **Any IP** (or restrict to 192.168.1.0/24)
6. Action: **Allow**
7. Name: "Allow Ping" → Finish

**Test from VM**:
```bash
ping <windows-ip>  # e.g., ping 192.168.1.31
```

Should now respond successfully.

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

**🆕 v2.1.0**: The interactive setup wizard (Part 5) can now auto-install Docker for you!

**You can either:**
- **Option A**: Skip this section and let the wizard install Docker (recommended for beginners)
- **Option B**: Follow these steps to install Docker manually first

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

**🆕 Two ways to deploy** - Choose the one that sounds easier:

- **Option A: One-Liner Install** (Recommended for beginners - fully automated!)
- **Option B: Manual Clone + Interactive Wizard** (More control over install location)

Both methods use the same interactive wizard - Option A just clones the repo first.

---

### Option A: One-Liner Install (Recommended)

**This is the fastest way** - one command does everything:

```bash
curl -fsSL https://raw.githubusercontent.com/dubpixel/dpx_showsite_ops/master/install.sh | bash
```

What happens:
1. Checks prerequisites (curl, git, internet)
2. Clones repository to `~/dpx_showsite_ops`
3. Runs interactive setup wizard (see Step 5.2 below for what to expect)

**Skip to Section 5.2** to see what the wizard will ask you.

---

### Option B: Manual Clone + Interactive Wizard

If you prefer to clone manually or choose a different directory:

**5.1: Clone the Repository**

```bash
cd ~
git clone https://github.com/dubpixel/dpx_showsite_ops.git
cd dpx_showsite_ops
```

**5.2: Run Interactive Setup Wizard**

```bash
chmod +x setup.sh
./setup.sh
```

---

### 5.2: Interactive Setup Wizard

The wizard will guide you through 7 steps with colored progress indicators:

**What the wizard does** (no vim/vi required!):

**Step 1: Check Docker**
- Detects if Docker is installed
- **Offers to auto-install Docker** if missing (via get.docker.com)
- Adds you to docker group automatically

**Step 2: Check Configuration**
- Looks for existing `.env` file
- Offers to reconfigure if one exists

**Step 3: Govee Credentials** (Interactive Prompts)
- Prompts for your **Govee email** (validates format)
- Prompts for your **Govee password** (hidden input for security)
- Prompts for your **Govee API key** (validates length)

> **Need an API key?** Get it from your phone:
> 1. Open Govee Home app
> 2. Go to **My Account** (bottom right)
> 3. Click **Apply for API Key**
> 4. You'll receive an email with your API key (looks like: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

**Step 4: Timezone & Display**
- Auto-detects your timezone (asks to confirm or override)
- Prompts for showsite name (defaults to hostname)
- Asks for temperature scale preference (F or C)

**Step 5: Grafana Setup**
- Prompts for Grafana admin password (hidden input)

**Step 6: System Optimizations** (Optional - you can skip any)
- **Disable IPv6** (fixes govee2mqtt connectivity on some systems)
- **Install avahi-daemon** (enables .local hostname like `http://dpx-stack.local:3000`)
- **Install Tailscale** (secure VPN for remote access)
- **Install cloudflared** (enables `iot tunnel` commands for public URLs)

**Step 7: Install Dependencies**
- Installs Python dependencies
- Initializes git submodule (set-schedule)
- Installs `iot` command system-wide
- Offers to enable hourly device-map updates via cron

**Final Step: Deploy Stack**
- Asks if you want to deploy immediately
- Runs `docker compose up -d` to start all 6 services

**The wizard validates all inputs** so you can't accidentally enter a bad email or API key!

---

### 5.3: What Wizards Configure Automatically

The interactive wizard creates your `.env` file with these settings:

```bash
# Govee Credentials (from your prompts)
GOVEE_API_KEY='your-api-key-here'
GOVEE_EMAIL='your-govee-email@example.com'
GOVEE_PASSWORD='your-govee-password'

# MQTT (auto-configured)
GOVEE_MQTT_HOST=127.0.0.1
GOVEE_MQTT_PORT=1883

# Timezone (auto-detected or your choice)
TZ=America/New_York

# Display (your choice)
GOVEE_TEMPERATURE_SCALE=F

# Showsite name (your choice or hostname)
SHOWSITE_NAME=my_venue

# Auto-configured defaults
RUST_LOG=govee=info
```

**To edit later**: Just run `nano ~/dpx_showsite_ops/.env` or use the wizard again: `./setup.sh`

---

### 5.4: Verify Stack is Running

If you said "yes" to deploying in the wizard, the stack is already running! If not:

```bash
iot up
```

You'll see a bunch of "Pulling" messages as it downloads images (takes 2-5 minutes first time).

When it's done, you'll see:
```
✔ Container influxdb      Started
✔ Container grafana       Started
✔ Container mosquitto     Started
✔ Container telegraf      Started
✔ Container govee2mqtt    Started
✔ Container ble-decoder   Started
```

**What just started:**
- **influxdb**: Time-series database for sensor data
- **grafana**: Dashboard and visualization
- **mosquitto**: MQTT message broker
- **telegraf**: Data pipeline (MQTT → InfluxDB)
- **govee2mqtt**: Cloud API polling (10-20 min latency)
- **ble-decoder**: BLE data decoder (auto-processes ESP32 gateway data)

**Verify everything is running**:
```bash
iot status
```

You should see 6 containers all "Up".

**Note**: The BLE decoder is now containerized and starts automatically. It will process BLE data from ESP32 gateways once you set them up in Part 10. No manual Python script needed!

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

1. **BLE decoder already running**: Automatically started with `iot up` (containerized as of v2.0.0)
2. **Check decoder status**: 
   ```bash
   iot ble-status    # Check if container is running
   iot lb            # View last 30 lines of BLE decoder logs
   iot ble-follow    # Follow logs in real-time (Ctrl+C to exit)
   ```
3. **BLE decoder management commands**:
   - `iot ble-restart` — Restart the BLE decoder container
   - `iot ble-rebuild` — Rebuild and restart (for code updates)
   - `iot ble-up` / `iot ble-down` — Start/stop just the BLE decoder
4. **Telegraf**: Already configured to collect both cloud + BLE data
5. **Grafana**: Dashboards show both sources with `source` tags (filter by `dpx_ops_decoder` for BLE data)
6. **Monitor latency**: BLE should be <5 sec, cloud 10-20 min

**BLE Decoder Features** (v2.0.0+):
- Auto-processes BLE advertisements from ESP32 gateways
- Enriches data with Govee API metadata (device names, rooms)
- Supports device override system for persistent renaming (see Daily Operations)
- Handles multiple gateways automatically
- Runs in Docker container (no manual Python script)

**Windows Theengs Gateway**: Available as fallback option (see Part 9 or Appendix)

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

**Files created:**
- `telegraf/conf.d/geist-watchdog.conf` - SNMP polling configuration
- `Dockerfile.telegraf` - Custom Telegraf image with SNMP tools
- `telegraf/mibs/geist/` - Geist MIB files
- `docker-compose.yml` - Updated to build custom Telegraf image

**What it does**:
- **Automatically installs SNMP packages**: The Dockerfile builds a custom Telegraf image with `snmp`, `libsnmp-dev`, and `snmp-mibs-downloader` pre-installed (no manual installation needed)
- **Mounts MIB files**: Standard IETF/IANA MIBs + Geist-specific MIB for OID resolution
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
cat Dockerfile.telegraf  # Custom image with SNMP support
```

**Key settings**:
- **Device IP**: `10.0.10.162` (change if different)
- **Community string**: `public` (read-only)
- **Poll interval**: `30s`
- **Auto-discovery**: Walks all sensor tables
- **Scaling**: Temperature divided by 10 (725 → 72.5)

### 11.3: Update Device IP When It Changes

The Geist Watchdog is configured to use hostname `dpx-geist.local` instead of a hardcoded IP address. This allows the device IP to change without editing multiple config files.

**Why use a hostname?**
- mDNS `.local` addresses don't resolve inside Docker containers by default
- Using `extra_hosts` in docker-compose.yml maps the hostname to the current IP
- When the IP changes, you only update one file instead of hunting through telegraf configs

**If the Geist device IP changes:**

1. **Edit docker-compose.yml**:

```bash
nano docker-compose.yml
```

2. **Find the telegraf service's `extra_hosts` section**:

```yaml
telegraf:
  # ... other settings ...
  extra_hosts:
    - "dpx-geist.local:192.168.1.214"  # <-- Update this IP
```

3. **Change to the new IP address**:

```yaml
  extra_hosts:
    - "dpx-geist.local:192.168.1.XXX"  # Your new IP
```

4. **Save and restart Telegraf**:

```bash
iot restart telegraf
```

**If the device hostname changes** (unlikely, but possible):

Edit both `docker-compose.yml` (extra_hosts) and `telegraf/conf.d/geist-watchdog.conf` (agents line) to use the new hostname.

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

## Part 12: M4300 Network Switch Backups

**For network infrastructure management**: Automate configuration backups of Netgear M4300 managed switches via TFTP.

### What is M4300 Backup?

The M4300 backup service automates configuration snapshots of Netgear M4300 series managed switches. This protects against configuration loss from hardware failure, accidental changes, or network incidents.

**Key Features**:
- **Automated TFTP backups**: Pushes configuration files from switches to VM storage
- **Multiple switches**: Backup entire network infrastructure in one command
- **Timestamped archives**: Each backup run creates a dated folder
- **InfluxDB metrics**: Track backup success/failure rates and timing
- **Mock mode**: Test configuration without real switches
- **Containerized**: Runs in Docker with isolated TFTP server

### 12.1: M4300 Service Already Deployed

The M4300 backup integration is included in the docker-compose stack:

**Services**:
- `netgear-backup` — Python automation script (on-demand execution)
- `tftp-server` — Lightweight TFTP server for receiving config files

**Files**:
- `services/netgear-backup/` — Service code and configuration
- `config/switches.conf.example` — Switch inventory template
- `docker-compose.yml` — Service definitions

**What it does**:
- Connects to each switch via SSH
- Triggers TFTP upload from switch to server
- Stores configs in timestamped folders
- Writes metrics to InfluxDB for monitoring
- Handles network routing for Hyper-V VM environments

### 12.2: Configure Your Switches

**Create switch inventory**:

```bash
cd ~/dpx_showsite_ops
cp config/switches.conf.example config/switches.conf
nano config/switches.conf
```

**Format** (one switch per line):
```
# Format: IP_ADDRESS,SWITCH_NAME,SSH_USERNAME,SSH_PASSWORD
192.168.1.200,core-switch-01,admin,password123
192.168.1.201,access-switch-02,admin,password123
192.168.1.202,distribution-switch-03,admin,password123
```

**Important**:
- Use actual switch management IPs (must be reachable from VM)
- SSH must be enabled on switches (Netgear M4300 default port 22)
- Passwords stored in plain text (keep `config/` excluded from git)
- Comment lines with `#` are ignored

**Save**:
- Press `Ctrl + O`, `Enter`, `Ctrl + X`

### 12.3: TFTP Server Setup

The TFTP server is already configured in `docker-compose.yml` and starts automatically with `iot up`.

**How it works**:
1. TFTP server listens on port 69 (UDP)
2. Backup script SSHes into switch
3. Switch sends config file to TFTP server
4. Files stored in `/app/backups/` (mapped to `services/netgear-backup/backups/`)

**Verify TFTP server is running**:

```bash
docker ps | grep tftp-server
```

Should show container as "Up".

**TFTP Configuration**:
- Port: `69/udp` (standard TFTP port)
- Directory: `/tftpboot` (container) → `services/netgear-backup/backups` (host)
- File creation: Enabled (`-c` flag)
- Logging: Verbose mode for debugging

**If TFTP server isn't running**:

```bash
docker compose up -d tftp-server
```

### 12.4: Network Routing for Hyper-V VMs

**Important**: If running on a Hyper-V VM, switches may not be able to route to the TFTP server's Docker network. A helper service automatically configures host routes.

**Check if network fix is active**:

```bash
sudo systemctl status network-route-fix.service
```

Should show "active (running)".

**If route fix isn't installed**, run the setup script:

```bash
~/dpx_showsite_ops/scripts/setup-m4300-network.sh
```

This creates a systemd service that:
- Runs on boot
- Adds routes from VM's physical interface to Docker's TFTP container
- Enables switches to reach TFTP server at VM's IP address

**Manual route verification** (troubleshooting):

```bash
ip route | grep 172.25
```

Should show routes to Docker bridge network.

### 12.5: Run Your First Backup

**Test with mock mode** (no real switches required):

```bash
iot m4300-backup-mock
```

This simulates a backup run and creates mock files in `services/netgear-backup/backups/mock_backups/`.

**Run real backup**:

```bash
iot m4300-backup
```

You'll see output like:
```
Starting Netgear M4300 backup...
[2026-03-06 14:30:15] Connecting to 192.168.1.200 (core-switch-01)...
[2026-03-06 14:30:18] Config saved: /backups/2026-03-06T14-30-15/core-switch-01.cfg
[2026-03-06 14:30:20] Connecting to 192.168.1.201 (access-switch-02)...
[2026-03-06 14:30:23] Config saved: /backups/2026-03-06T14-30-15/access-switch-02.cfg
✓ Backup complete
```

**View backup files**:

```bash
iot m4300-list
```

Shows recent backups with timestamps and file sizes.

### 12.6: M4300 Management Commands

**Backup operations**:
- `iot m4300-backup` — Run full backup of all switches
- `iot m4300-backup-mock` — Test run with mock data (no real switches)
- `iot m4300-list` — Show recent backups (last 10 folders)
- `iot m4300-list-all` — Show all backup files across all timestamps
- `iot m4300-clean` — Remove empty backup folders (failed attempts)

**Logs and debugging**:
- `iot m4300-logs` — View recent log files (last 10)
- `iot m4300-log-view <filename>` — Display full log file contents
- `iot m4300-list-switches` — Show configured switches from switches.conf

**Maintenance**:
- `iot m4300-rebuild` — Rebuild netgear-backup Docker image (for code updates)
- `iot m4300-network-fix` — Reinstall network routing fix (if routes break)
- `iot tftp-rebuild` — Recreate TFTP server container

**Examples**:

```bash
# Weekly backup
iot m4300-backup

# Check if backups succeeded
iot m4300-logs

# View specific log
iot m4300-log-view backup_log_2026-03-06.txt

# List all switches in inventory
iot m4300-list-switches

# Clean up failed backup attempts
iot m4300-clean
```

### 12.7: Automate with Cron

**Set up weekly backups** (every Sunday at 2 AM):

```bash
crontab -e
```

Add this line:
```cron
0 2 * * 0 cd ~/dpx_showsite_ops && ./scripts/manage.sh m4300-backup >> ~/logs/m4300-cron.log 2>&1
```

**Daily backups** (every day at 3 AM):
```cron
0 3 * * * cd ~/dpx_showsite_ops && ./scripts/manage.sh m4300-backup >> ~/logs/m4300-cron.log 2>&1
```

**Verify cron job**:
```bash
crontab -l
```

**Check cron log**:
```bash
tail -50 ~/logs/m4300-cron.log
```

### 12.8: Backup Storage and Retention

**Backup location**:
```
~/dpx_showsite_ops/services/netgear-backup/backups/
  ├── 2026-03-01T14-30-00/
  │   ├── core-switch-01.cfg
  │   ├── access-switch-02.cfg
  │   └── distribution-switch-03.cfg
  ├── 2026-03-08T14-30-00/
  │   ├── core-switch-01.cfg
  │   └── access-switch-02.cfg
  └── logs/
      ├── backup_log_2026-03-01.txt
      └── backup_log_2026-03-08.txt
```

**Space management**:

Each config file is typically 50-200 KB. Weekly backups = ~2 MB/year per switch.

**Manual cleanup** (remove backups older than 90 days):
```bash
find ~/dpx_showsite_ops/services/netgear-backup/backups/ -maxdepth 1 -type d -mtime +90 -exec rm -rf {} \;
```

**Git tracking**: `backups/` folder is excluded via `.gitignore` (local-only storage).

### 12.9: Troubleshooting M4300 Backups

**"Connection refused" or "Connection timed out"**:
- Verify switch IP is reachable: `ping 192.168.1.200`
- Check SSH is enabled on switch (Web UI → Maintenance → Remote Management)
- Verify SSH port (default 22): `nc -zv 192.168.1.200 22`
- Check firewall: `sudo ufw status`

**"TFTP timeout" or "TFTP transfer failed"**:
- Verify TFTP server running: `docker ps | grep tftp-server`
- Check network routing: `ip route | grep 172.25`
- Run network fix: `iot m4300-network-fix`
- Test TFTP manually from switch CLI: `copy running-config tftp://<VM_IP>/test.cfg`

**"Authentication failed"**:
- Double-check username/password in `config/switches.conf`
- Try SSH manually from VM: `ssh admin@192.168.1.200`
- Verify switch hasn't changed credentials

**Empty backup folders created**:
- Indicates connection succeeded but TFTP transfer failed
- Run `iot m4300-clean` to remove empty folders
- Check `iot m4300-log-view` for detailed error messages

**Permissions errors**:
- Ensure `services/netgear-backup/backups/` is writable by docker user
- Fix: `sudo chown -R $USER:$USER ~/dpx_showsite_ops/services/netgear-backup/backups/`

### 12.10: Next Steps

With M4300 backups configured:

1. **Test restore procedure**: Verify you can load a .cfg file to a switch (manual process via Web UI)
2. **Schedule regular backups**: Use cron for automated weekly snapshots
3. **Monitor in Grafana**: Create dashboard using InfluxDB metrics (backup success rate, duration)
4. **Expand to other devices**: Adapt scripts for different switch models or routers
5. **Off-site storage**: Copy backups to external NAS or cloud storage for disaster recovery

**Documentation**:
- Full README: `services/netgear-backup/README.md`
- Standalone deployment: [dpx-netgear-backup GitHub repo](https://github.com/dubpixel/dpx-netgear-backup)

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

### Rename Devices and Rooms

If Govee auto-generates bad device names (e.g., `h5075_5a9`) or you want to override room assignments, use the device override system:

**Interactive device renaming**:
```bash
iot rename-device
```

This opens an interactive menu showing all devices. Select the device you want to rename, enter a new friendly name, and the system updates both BLE decoder and Telegraf automatically.

**Interactive room assignment**:
```bash
iot set-room
```

Select a device and assign it to a different room. Useful for correcting Govee app mistakes or organizing devices differently.

**Clear an override** (revert to Govee API data):
```bash
iot clear-override
```

Select a device to remove its override, restoring the original name/room from Govee Cloud API.

**How it works**:
- Overrides stored in `device-overrides.json` (local file, not tracked in git)
- Both BLE decoder and Telegraf read overrides on startup
- Changes survive `iot update` and service restarts
- Works offline if Govee Cloud API is unavailable

**Manual override file editing** (advanced):

```bash
nano ~/dpx_showsite_ops/device-overrides.json
```

Format:
```json
{
  "A4:C1:38:AB:CD:EF": {
    "device_name": "Studio Main Sensor",
    "room": "Recording Studio"
  }
}
```

After editing, restart services:
```bash
iot restart ble-decoder telegraf
```

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
- Backup dashboards with `iot backup-dashboards`
- Set up automated dashboard backups with `iot setup-dashboard-cron`

**Add More Sensors**:
- Buy more Govee sensors for different rooms
- They automatically get discovered
- H5075 recommended (BLE-only, excellent reliability)
- Avoid H5074 (poor BLE performance)

**Completed Features** (v2.0.2):
- ✅ **Phase 4 - BLE Gateway**: Local BLE reading deployed and operational (<5 second latency)
  - BLE decoder service runs automatically with the stack
  - Manage with: `iot ble-status`, `iot lb`, `iot ble-restart`
  - ESP32 OpenMQTTGateway as primary hardware platform
- ✅ **Phase 4.5 - Geist Watchdog**: SNMP-based environmental monitoring for infrastructure
  - Automatic sensor discovery and SNMP polling
  - Temperature, humidity, and dew point tracking
- ✅ **Phase 2.8 - Device Override System**: Persistent local device renaming
  - Interactive rename commands: `iot rename-device`, `iot set-room`
  - Works offline, survives Govee API outages
- ✅ **M4300 Network Backups**: Automated switch configuration backups via TFTP
  - Schedule with cron for weekly/daily snapshots
  - Manage with `iot m4300-*` commands

**Upcoming Features** (see ROADMAP.md):
- **Phase 6**: Art-Net DMX monitoring integration (in progress)
- **Phase 8**: Meat probe/food temperature monitoring (H5194 proof-of-concept)
- **Phase 9**: Industrial temperature probe evaluation (feasibility test)
- **Phase 10**: LTC timecode monitoring (production priority, awaiting repo access)
- **Phase 11**: VLAN isolation for production Art-Net networks

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

**Last Updated**: March 6, 2026  
**Guide Version**: 2.0  
**For**: dpx-showsite-ops v2.0.2

---

## Appendix B: Complete iot Command Reference

Comprehensive reference for all `iot` management commands.

### Stack Management

| Command | Description |
|---------|-------------|
| `iot up` | Start all containers in the stack |
| `iot down` | Stop all containers |
| `iot restart [service]` | Restart all containers or specific service |
| `iot status` | Show container status (running/stopped) |

**Examples**:
```bash
iot up                    # Start entire stack
iot restart telegraf      # Restart just Telegraf
iot down                  # Stop everything
```

---

### BLE Decoder Management (v2.0.0+)

| Command | Description |
|---------|-------------|
| `iot ble-status` | Show BLE decoder container status |
| `iot ble-logs [N]` | Show last N lines of logs (default: 30) |
| `iot ble-follow` | Follow logs in real-time (Ctrl+C to exit) |
| `iot ble-restart` | Restart BLE decoder container |
| `iot ble-rebuild` | Rebuild and restart (for code updates) |
| `iot ble-up` | Start BLE decoder only |
| `iot ble-down` | Stop BLE decoder only |
| `iot lb [N]` | Shorthand for `iot ble-logs` |

**Examples**:
```bash
iot ble-status           # Check if running
iot lb 50                # Last 50 lines of logs
iot ble-follow           # Watch logs live
iot ble-restart          # Restart after config change
```

---

### Service Logs

| Command | Description |
|---------|-------------|
| `iot lg [N]` | govee2mqtt logs (last N lines, default: 30) |
| `iot lt [N]` | Telegraf logs |
| `iot lm [N]` | Mosquitto (MQTT broker) logs |
| `iot li [N]` | InfluxDB logs |
| `iot lf [N]` | Grafana logs |
| `iot lb [N]` | BLE decoder logs |
| `iot la [N]` | All services logs (last N lines per service) |

**Examples**:
```bash
iot lg                   # Last 30 lines of govee2mqtt
iot la 50                # Last 50 lines from ALL services
iot lt 100               # Last 100 lines of Telegraf
```

---

### Data Queries

| Command | Description |
|---------|-------------|
| `iot query [time] [limit]` | Query recent data from InfluxDB |
| `iot query-tags [time] [limit]` | Query with full tag visibility |
| `iot mqtt [topic] [count]` | Subscribe to MQTT topic (count messages) |
| `iot watch-gv2 [count]` | Watch govee2mqtt sensor state messages |

**Examples**:
```bash
iot query 1h 10          # Last hour, 10 rows
iot query 30m 5          # Last 30 min, 5 rows
iot mqtt "gv2mqtt/#" 20  # 20 messages from govee2mqtt
iot watch-gv2            # Monitor cloud sensor updates
```

---

### Device Management

| Command | Description |
|---------|-------------|
| `iot update` | Refresh device mappings from Govee API |
| `iot list-devices` | Show all discovered devices |
| `iot rename-device` | Interactive device renaming (override system) |
| `iot set-room` | Interactive room assignment (override system) |
| `iot clear-override` | Remove device override (revert to API data) |
| `iot delete-device-data` | Delete specific device data from InfluxDB |

**Examples**:
```bash
iot update               # Sync with Govee Cloud API
iot list-devices         # Show all sensors
iot rename-device        # Opens interactive menu
iot set-room             # Assign device to different room
```

---

### M4300 Network Backups

| Command | Description |
|---------|-------------|
| `iot m4300-backup` | Run full backup of all configured switches |
| `iot m4300-backup-mock` | Test backup with mock data (no real switches) |
| `iot m4300-list` | Show recent backups (last 10 folders) |
| `iot m4300-list-all` | Show all backup files across all timestamps |
| `iot m4300-logs` | View recent log files |
| `iot m4300-log-view <file>` | Display full log file contents |
| `iot m4300-clean` | Remove empty backup folders (failed attempts) |
| `iot m4300-list-switches` | Show configured switches from switches.conf |
| `iot m4300-rebuild` | Rebuild netgear-backup Docker image |
| `iot m4300-network-fix` | Reinstall network routing fix |
| `iot tftp-rebuild` | Recreate TFTP server container |

**Examples**:
```bash
iot m4300-backup                        # Weekly backup
iot m4300-list                          # Check recent backups
iot m4300-log-view backup_log_2026.txt  # View specific log
iot m4300-clean                         # Clean up failed attempts
```

---

### Backup & Restore

| Command | Description |
|---------|-------------|
| `iot backup` | Backup Grafana and InfluxDB volumes to ~/backups/ |
| `iot backup-dashboards` | Export all Grafana dashboards via API |
| `iot provision-dashboard [file]` | Convert dashboard for provisioning (read-only) |
| `iot deprovision-dashboard [uid]` | Remove provisioned dashboard |
| `iot restore-dashboard [file]` | Restore backed-up dashboard as editable |
| `iot setup-dashboard-cron` | Enable daily automated dashboard backups |
| `iot remove-dashboard-cron` | Disable automated dashboard backups |

**Examples**:
```bash
iot backup                              # Full backup
iot backup-dashboards                   # Export all dashboards
iot provision-dashboard my-dash.json    # Make read-only
iot restore-dashboard my-dash.json      # Restore as editable
```

---

### Cloudflare Tunnels (Public Access)

| Command | Description |
|---------|-------------|
| `iot tunnel` | Start Grafana tunnel (port 3000) |
| `iot tunnel-grafana` | Start Grafana tunnel |
| `iot tunnel-influxdb` | Start InfluxDB tunnel (port 8086) |
| `iot tunnel-schedule` | Start Set-Schedule tunnel (port 8000) |
| `iot tunnel-stop` | Stop all tunnels |
| `iot tunnel-stop-grafana` | Stop Grafana tunnel only |
| `iot tunnel-stop-influxdb` | Stop InfluxDB tunnel only |
| `iot tunnel-stop-schedule` | Stop Set-Schedule tunnel only |
| `iot tunnel-status` | Show running tunnels and their URLs |
| `iot tunnel-logs <service>` | View tunnel logs |

**Examples**:
```bash
iot tunnel               # Start Grafana public access
iot tunnel-status        # Check active tunnels
iot tunnel-stop          # Stop all tunnels
```

---

### Set-Schedule Service (Production)

| Command | Description |
|---------|-------------|
| `iot schedule-up` | Start Set-Schedule container |
| `iot schedule-down` | Stop Set-Schedule container |
| `iot schedule-restart` | Restart Set-Schedule container |
| `iot schedule-status` | Show container status |
| `iot schedule-logs [N]` | View logs (last N lines) |
| `iot schedule-follow` | Follow logs in real-time |
| `iot schedule-rebuild` | Rebuild and restart |
| `iot schedule-shell` | Open bash shell in container |

**Examples**:
```bash
iot schedule-up          # Start schedule app
iot schedule-logs 50     # Check logs
iot schedule-follow      # Watch live requests
```

---

### Development Set-Schedule (Standalone)

| Command | Description |
|---------|-------------|
| `iot schedule-dev-up` | Start dev server (standalone folder) |
| `iot schedule-dev-down` | Stop dev server |
| `iot schedule-dev-restart` | Restart dev server |
| `iot schedule-dev-logs` | View dev logs |
| `iot schedule-dev-rebuild` | Rebuild dev image |

---

### Cron Management

| Command | Description |
|---------|-------------|
| `iot cron-on` | Enable hourly device mapping updates |
| `iot cron-off` | Disable automatic updates |

---

### Utilities

| Command | Description |
|---------|-------------|
| `iot ip` | Show VM's IP address |
| `iot env` | Display .env file contents |
| `iot conf` | Display telegraf.conf |
| `iot edit [file]` | Edit .env or specified file with vim |
| `iot web` | Show URLs for all web services |
| `iot fixnet` | Restart network route fix service |
| `iot nuke` | **DANGEROUS**: Delete ALL data from InfluxDB sensors bucket |
| `iot nuke-geist` | Delete Geist measurements only (for schema resets) |
| `iot clear-retained` | Clear retained MQTT messages (troubleshooting) |

**Examples**:
```bash
iot ip                   # Get VM IP for browser access
iot web                  # Show all service URLs
iot env                  # Check configuration
iot edit .env            # Edit config file
```

---

### ESP32 Configuration (Advanced)

| Command | Description |
|---------|-------------|
| `iot esp32-enable` | Enable ESP32-specific debugging |
| `iot esp32-verbose` | Enable verbose ESP32 logging |

---

### Command Help

```bash
iot                      # Show all available commands
iot [command] --help     # Some commands have detailed help
```

---

**Tips**:
- Most commands support optional arguments (check command reference above)
- Log commands default to 30 lines, but you can specify more: `iot lg 100`
- Use `iot la 50` for troubleshooting (shows recent logs from all services)
- Commands output is designed for both human reading and script parsing

**Common Workflows**:

**Daily health check**:
```bash
iot status && iot query 1h 5
```

**Troubleshooting**:
```bash
iot la 50                # Check all recent logs
iot status               # Verify containers running
iot mqtt "gv2mqtt/#" 10  # Verify MQTT messages
```

**After config changes**:
```bash
iot edit .env            # Modify config
iot restart              # Apply changes
iot lg                   # Verify restart successful
```

---

**Last Updated**: March 6, 2026  
**dpx-showsite-ops**: v2.0.2
