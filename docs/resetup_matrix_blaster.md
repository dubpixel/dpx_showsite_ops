# Matrix Display — Network Change Checklist

Run these steps any time the network changes (new venue, new router, IP reassignment).

---

## 1. Find the new IPs

On the server:
```bash
hostname -I
```
Note the server's IP. Also find the matrix WLED device's new IP — check your router's DHCP table or open the WLED web UI if you know the old IP.

---

## 2. Update the server `.env`

Edit the `.env` file in the stack directory:
```
WLED_MATRIX_HOST=<new matrix device IP>
```

---

## 3. Restart the containers

```bash
docker compose restart wled-bridge matrix-blast
```

---

## 4. Update the WLED matrix device

Open the matrix device's web UI in a browser (`http://<matrix IP>`):

1. **Config → Sync Interfaces → MQTT**
2. Set **Broker** to the server's new IP
3. Confirm **Device topic** is exactly: `coachella_26/wled-matrix`
4. Click **Save** then **Connect**

---

## 5. Verify

```bash
docker logs wled-bridge --tail=30
```

You should see:
```
Subscribed (matrix text): coachella_26/wled/matrix/text
Matrix device topic: coachella_26/wled-matrix  →  api: coachella_26/wled-matrix/api
```

Then send a test blast from the matrix-blast UI (`http://<server>:8090`) and confirm it shows up on the display. wled-bridge logs should show:
```
[matrix] text='your test message' ... → coachella_26/wled-matrix/api
```

---

**The two most commonly missed steps: #2 (update `.env` before restarting) and #4 (update broker IP on the WLED device itself).**
