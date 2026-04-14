# NTP Server using chrony
# Syncs time from NIST servers and rebroadcasts to local network devices
FROM ubuntu:22.04

# Install chrony NTP server
RUN apt-get update && \
    apt-get install -y chrony tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create directory for chrony runtime files
RUN mkdir -p /var/lib/chrony /run/chrony && \
    chown -R _chrony:_chrony /var/lib/chrony /run/chrony && \
    chmod 750 /run/chrony

# Ubuntu chrony expects config at /etc/chrony/chrony.conf
# Create symlink so we can mount to /etc/chrony.conf (Alpine location)
RUN ln -sf /etc/chrony.conf /etc/chrony/chrony.conf

# Expose NTP port (UDP 123)
# Note: When using host networking mode, this is informational only
EXPOSE 123/udp

# Run chronyd in foreground mode as root so it can bind to privileged port 123
# -d: foreground + log to stderr
# -f: explicitly specify config file
# -u root: keep root privileges (required to bind UDP port 123)
ENTRYPOINT ["/usr/sbin/chronyd", "-d", "-f", "/etc/chrony.conf", "-u", "root"]
