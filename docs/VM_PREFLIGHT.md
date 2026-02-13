# VM Preparation Checklist
## dpx-showsite-ops Quick Redeployment

**Purpose**: Get a clean Ubuntu VM ready for Docker deployment  
**Time**: 30-45 minutes  
**Use Case**: Fresh install or post-incident recovery

---

## Pre-Flight

### ☐ Downloads
- [ ] Ubuntu Server 24.04 LTS ISO (~2.5 GB)
  - URL: https://ubuntu.com/download/server
  - File: `ubuntu-24.04.X-live-server-amd64.iso`
  - Architecture: **amd64** (correct for Intel/AMD 64-bit)

### ☐ Hyper-V Setup
- [ ] Hyper-V Manager installed and accessible
- [ ] Virtual Switch created (see below)

---

## Step 1: Create Virtual Switch

**Why**: Gives VM direct access to your LAN/DHCP

1. Open **Hyper-V Manager**
2. Click **Virtual Switch Manager** (right sidebar)
3. Select **External** → Click **Create Virtual Switch**
4. Configure:
   - **Name**: `External Network` (or your preference)
   - **External network**: Select your physical network adapter
   - ☑ **Allow management OS to share this adapter**
5. Click **OK**

**Verify**: Switch appears in Virtual Switch Manager list

---

## Step 2: Create the VM

### VM Wizard Settings

**Right-click your machine → New → Virtual Machine**

| Step | Setting | Value |
|------|---------|-------|
| Name and Location | Name | `dpx-showsite-ops` |
| | Store in different location | ☐ Optional (check if using secondary SSD) |
| | Location | `D:\VMs\dpx-showsite-ops` (if using second drive) |
| **Generation** | Type | **Generation 2** ✓ |
| **Memory** | Startup memory | `4096 MB` (4 GB) |
| | Use Dynamic Memory | ☑ Check |
| **Networking** | Connection | **External Network** |
| **Hard Disk** | Action | ⦿ Create a virtual hard disk |
| | Size | `64 GB` (or 50 GB minimum) |
| | Location | Same as VM or secondary SSD |
| **Installation** | Options | ⦿ Install from bootable image |
| | ISO | Browse to Ubuntu Server ISO |

Click **Finish**

---

## Step 3: Tweak VM Settings

**Before first boot:**

1. Right-click VM → **Settings**
2. **Security** section:
   - ☐ **UNCHECK** "Enable Secure Boot"
   - (Or set template to "Microsoft UEFI Certificate Authority")
3. **Processor** section:
   - Number of virtual processors: `2`
4. Click **OK**

---

## Step 4: Boot & Install Ubuntu

1. Right-click VM → **Connect** (opens window)
2. Click **Start** (green play button)
3. Ubuntu installer starts

### Installer Answers

| Screen | Selection |
|--------|-----------|
| Language | English |
| Keyboard | English (US) |
| Install Type | Ubuntu Server (default) |
| Network | eth0 (should show DHCP IP) |
| Proxy | (leave blank) |
| Archive Mirror | (default) |
| Storage | Use entire disk → Continue |
| **Profile** | **Save these!** |
| - Name | `dpx` |
| - Server name | `dpx-showsite-ops` |
| - Username | `dubpixel` (or your choice) |
| - Password | **[WRITE THIS DOWN]** |
| SSH | ☑ Install OpenSSH server |
| Snaps | Don't select any |

Wait for install (5-10 min) → Click **Reboot Now**

If prompted about installation medium, press **Enter**

---

## Step 5: First Login & Updates

**Login prompt:**
```
dpx-showsite-ops login: dubpixel
Password: [your password - won't show]
```

**Update system:**
```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

Wait 30 seconds, log back in.

---

## Step 6: Set Static IP

**Find current IP:**
```bash
ip addr show eth0 | grep 'inet '
```

Example output: `inet 192.168.1.142/24`

**Edit netplan config:**
```bash
sudo nano /etc/netplan/50-cloud-init.yaml
```

**Replace with** (adjust IPs to match your network):
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

**Save**: `Ctrl+O`, `Enter`, `Ctrl+X`

**Apply:**
```bash
sudo netplan apply
```

**Verify:**
```bash
ip addr show eth0 | grep 'inet '
ping -c 3 google.com
```

---

## Step 7: Install Base Tools

```bash
sudo apt install -y git curl wget vim avahi-daemon
```

**Enable mDNS (optional):**
```bash
sudo systemctl enable avahi-daemon
sudo systemctl start avahi-daemon
```

Now accessible via: `dpx-showsite-ops.local`

---

## Step 8: Optional - Disable IPv6

**If you'll use govee2mqtt** (fixes AWS IoT timeout):

```bash
sudo sysctl -w net.ipv6.conf.eth0.disable_ipv6=1
echo "net.ipv6.conf.eth0.disable_ipv6=1" | sudo tee -a /etc/sysctl.conf
```

---

## ✅ VM Ready Checklist

Before proceeding to app deployment:

- [ ] VM boots successfully
- [ ] Can SSH from Windows host: `ssh dubpixel@192.168.1.X`
- [ ] Static IP set and verified
- [ ] Internet working: `ping google.com`
- [ ] Base tools installed: `git --version`
- [ ] (Optional) mDNS working: `ping dpx-showsite-ops.local`
- [ ] (Optional) IPv6 disabled if using govee2mqtt

---

## Next Steps

**Your VM is now ready for Docker deployment!**

Proceed to:
1. Install Docker (Part 4 in SETUP_GUIDE_COMPLETE.md)
2. Clone the repo and run `setup.sh`
3. Deploy the stack with `iot up`

---

## Quick Reference

**VM Access:**
- IP: `192.168.1.X` (your static IP)
- Hostname: `dpx-showsite-ops.local`
- User: `dubpixel`
- Pass: [your password]

**VM Resources:**
- RAM: 4 GB (dynamic)
- Disk: 64 GB
- CPUs: 2

**Network:**
- External Switch: Connected to your LAN
- Gets DHCP initially, then static

---

## Troubleshooting VM Prep

**Can't connect to VM from Windows:**
```bash
# On VM, check SSH is running
sudo systemctl status ssh

# Check firewall (should be off by default)
sudo ufw status
```

**Network not working:**
```bash
# Check interface
ip link show eth0

# Check if it's up
sudo ip link set eth0 up

# Reapply netplan
sudo netplan apply
```

**Forgot password:**
- Unfortunately requires VM rebuild
- No easy reset without console access
- **Prevention**: Write it down!

**VM won't boot:**
- Check Secure Boot is disabled in VM settings
- Verify ISO is correct architecture (amd64)
- Try removing ISO after install and rebooting

---

**Last Updated**: 2025-02-12  
**For**: dpx-showsite-ops redeployment  
**Guide**: VM preparation only (Docker deployment separate)
