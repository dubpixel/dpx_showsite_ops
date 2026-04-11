# NTP Server using chrony
# Syncs time from NIST servers and rebroadcasts to local network devices
FROM alpine:3.19

# Install chrony NTP server
RUN apk add --no-cache chrony tzdata

# Create directory for chrony runtime files with correct permissions
# chronyd runs as the chrony user by default
RUN mkdir -p /var/lib/chrony /run/chrony && \
    chown -R chrony:chrony /var/lib/chrony /run/chrony && \
    chmod 750 /run/chrony

# Create empty config file for Docker volume mount
# Without this, Docker creates /etc/chrony.conf as a directory
RUN touch /etc/chrony.conf && chmod 644 /etc/chrony.conf

# Expose NTP port (UDP 123)
# Note: When using host networking mode, this is informational only
EXPOSE 123/udp

# Run chronyd in foreground mode (for Docker)
# -d: foreground with logging to stderr
# -s: set system time from RTC if offset is large on startup
ENTRYPOINT ["/usr/sbin/chronyd", "-d", "-s"]
