FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY govee_ble_bridge.py .

CMD ["python", "-u", "govee_ble_bridge.py"]
