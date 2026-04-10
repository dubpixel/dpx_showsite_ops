# NTP Server using chrony
# Syncs time from NIST servers and rebroadcasts to local network devices
FROM alpine:3.19

# Install chrony NTP server
RUN apk add --no-cache chrony tzdata

# Create directory for chrony runtime files
RUN mkdir -p /var/lib/chrony /run/chrony && \
    chown -R chrony:chrony /var/lib/chrony /run/chrony

# Expose NTP port (UDP 123)
# Note: When using host networking mode, this is informational only
EXPOSE 123/udp

# Run chronyd in foreground mode
# -d: foreground with logging to stderr
# -s: set system time from RTC if needed on startup
ENTRYPOINT ["/usr/sbin/chronyd", "-d", "-f", "/etc/chrony/chrony.conf"]
