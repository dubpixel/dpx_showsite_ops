FROM python:3.11-slim

LABEL maintainer="DubPixel <i@dubpixel.tv>"
LABEL description="Guest Alert Button Controller - X410 button-to-lamp automation"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY button_controller.py .
COPY config.yaml .

# Create log directory
RUN mkdir -p /var/log/button-controller

# Run as non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /var/log/button-controller
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run controller (unbuffered output for Docker logs)
CMD ["python3", "-u", "button_controller.py"]
