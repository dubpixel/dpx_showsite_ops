# NTP Server - Network Time Protocol Service

Docker-based NTP server using **chrony** that synchronizes time from NIST servers and provides time services to all network devices.

## Overview

- **Upstream Time Source**: NIST (time.nist.gov) via round-robin DNS
- **Network Mode**: Host networking (accessible on all physical network interfaces)
- **Port**: UDP 123 (standard NTP port)
- **Implementation**: chrony (modern, lightweight NTP daemon)

## Architecture

The NTP server operates as a **stratum 2** server:
1. Syncs time with NIST stratum 1 servers (via internet-connected network)
2. Rebroadcasts accurate time to local network devices (via all VLANs)
3. Allows queries from RFC1918 private networks (192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12)

## Usage

### Start the NTP Server

```bash
docker compose up -d ntp-server
```

### Check Synchronization Status

```bash
# View chrony tracking status (offset from NIST, stratum, etc.)
docker compose exec ntp-server chronyc tracking

# View configured time sources
docker compose exec ntp-server chronyc sources

# View detailed source statistics
docker compose exec ntp-server chronyc sourcestats
```

### Test from Client Device

From any device on your network:

```bash
# Quick test (requires ntpdate package)
ntpdate -q <ntp-server-ip>

# Using chronyc (if installed on client)
chronyc -h <ntp-server-ip> tracking

# Using standard NTP query
sntp -d <ntp-server-ip>
```

### Configure Network Devices

Point your switches, routers, and other infrastructure to the NTP server IP address.

**Example for Netgear switches:**
1. Navigate to System > Time Configuration
2. Set NTP Server: `<host-ip>` (your Docker host's IP address)
3. Verify synchronization status

**Example for UniFi devices:**
```
set system ntp server <host-ip>
commit
save
```

## Monitoring

### View Logs

```bash
# Real-time logs
docker compose logs -f ntp-server

# Last 100 lines
docker compose logs --tail 100 ntp-server
```

### Health Check

Chrony daemon health can be verified by checking:
- Container status: `docker compose ps ntp-server` (should show "Up")
- Sync status: `docker compose exec ntp-server chronyc tracking` (should show valid system time offset)
- NIST reachability: Check "Reach" column in `chronyc sources` (should show 377 octal = all polls successful)

## Configuration

Configuration is managed via `/config/ntp.conf` (mounted read-only from host).

To customize:
1. Copy `config/ntp.conf.example` to `config/ntp.conf`
2. Edit upstream pool servers or network ACLs as needed
3. Restart service: `docker compose restart ntp-server`

## Troubleshooting

### Port Conflict

If UDP port 123 is already in use on the host:

```bash
# Check what's using port 123
sudo lsof -i :123
sudo netstat -tulpn | grep :123

# On macOS, disable system NTP daemon if needed
sudo launchctl unload -w /System/Library/LaunchDaemons/org.ntp.ntpd.plist
```

### Time Not Syncing

```bash
# Check if container can reach NIST servers
docker compose exec ntp-server ping -c 3 time.nist.gov

# Verify firewall allows UDP 123 outbound (for NIST sync)
# Verify firewall allows UDP 123 inbound (for client queries)

# Check chrony is tracking upstream servers
docker compose exec ntp-server chronyc sources -v
```

### Clients Can't Reach NTP Server

- Verify host networking mode is enabled (service should not be on `iot` bridge network)
- Check firewall rules on Docker host allow UDP 123
- Verify client devices have network route to Docker host IP
- Test connectivity: `ping <docker-host-ip>` from client device

## Security Notes

- NTP operates over UDP (stateless protocol)
- Server allows queries only from RFC1918 private networks
- No authentication required for time queries (standard NTP behavior)
- Consider firewall rules to restrict access if needed

## Performance

- Chrony is lightweight (~8MB container image)
- CPU usage: negligible (<1%)
- Memory usage: ~4-8 MB
- Network bandwidth: <1 KB/min per client

## References

- [Chrony Documentation](https://chrony.tuxfamily.org/documentation.html)
- [NIST Time Servers](https://tf.nist.gov/tf-cgi/servers.cgi)
- [NTP Pool Project](https://www.pool.ntp.org/)
- [RFC 5905 - Network Time Protocol v4](https://tools.ietf.org/html/rfc5905)
