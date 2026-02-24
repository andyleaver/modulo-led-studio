# HUB75 + ESP32: WiFi Web Update (OTA) + NTP

Modulo can export ESP32 HUB75 firmware with optional WiFi features:

- **Web Update (OTA via browser)**
- **mDNS hostname** (e.g. `http://modulo-hub75.local/`)
- **Status endpoint**: `GET /info` (JSON)
- **AP fallback portal** when WiFi credentials are wrong or missing
- **NTP time sync** (for clock-driven effects)

## First flash vs WiFi updates

You must **flash once over USB** to put the firmware on the ESP32.
After that, you can update over WiFi.

## URLs

After the board joins WiFi:

- Updater page: `http://<device-ip>/`
- Upload endpoint: `http://<device-ip>/update`
- Status JSON: `http://<device-ip>/info`

If mDNS works on your network:

- `http://<hostname>.local/`

## AP fallback setup

If the board cannot connect to your WiFi, it starts an access point:

- SSID: `<hostname>-setup`
- Connect to that WiFi and open: `http://192.168.4.1/wifi`

Enter SSID + password, save, and it will reboot and join your network.

## NTP + Timezone

For clock effects on hardware, enable **NTP** and set a timezone string.
The default in the HUB75 demos is UK:

- `GMT0BST,M3.5.0/1,M10.5.0/2`

(That is a POSIX TZ string understood by ESP32 `configTzTime`.)

## Recommended validation demos

- **HUB75 WiFi + NTP Sanity**
- **HUB75 WiFi + NTP Clock Dot Overlay**
- **HUB75 HW Mapping Diagnostics**

These are designed to make first hardware bring-up fast and obvious.
