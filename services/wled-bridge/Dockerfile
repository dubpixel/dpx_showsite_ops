FROM python:3.11-slim

LABEL org.opencontainers.image.title="dpx-wled-bridge"
LABEL org.opencontainers.image.version="2.2.0"
LABEL org.opencontainers.image.description="MQTT sensor → WLED ropelight zone controller"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
