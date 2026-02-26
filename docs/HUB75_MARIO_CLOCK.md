# HUB75 Mario-Style Clock (OTA)

This demo is designed to feel familiar to people who have used popular “Mario clock / Clockwise” HUB75 builds,
while showcasing the *Modulo* approach: layered effects + rules + real firmware export.

## Credits

The original “Clockwise / Mario Bros Clock” concept and popular open-source implementation is by:
- **Jonathas Barbosa (jnthas)** — MIT license (see `../THIRD_PARTY_NOTICES.md`)

This Modulo demo is an independent implementation intended to be edited, remixed, and extended in Modulo.

## Install once, then OTA forever (recommended)

1. In Modulo: open the demo **HUB75 Mario-Style Clock (HH:MM)**.
2. In Export:
   - Select an **ESP32 HUB75 I2S-DMA** target that matches your panel setup
   - Enable **WiFi Web Update**
   - Enable **NTP** and set your timezone
3. Export firmware.
4. Flash once over USB (Arduino IDE / PlatformIO).
5. After the device joins WiFi:
   - Open `http://<hostname>.local/` (or your router’s device IP)
   - Upload updates via the web updater page

## Safety notes

- Start with low brightness and increase slowly.
- Ensure your HUB75 panels have an adequate power supply.

## Trademarks & assets

“Nintendo”, “Mario”, and related names/characters are trademarks of their respective owners.
This project does not claim affiliation with Nintendo.

Pixel art tables used by this showcase are included under their original license (see `../THIRD_PARTY_NOTICES.md`).
