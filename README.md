# IoT Signature Monitor

Lightweight signature verification for MQTT messages, designed for resource-constrained IoT devices.

---

## Overview

IoT devices communicate heavily through the MQTT protocol. It is lightweight, efficient, and well-suited to unstable networks — but by default it guarantees neither the authenticity nor the integrity of the messages exchanged. Anyone can publish on a topic and impersonate a legitimate device, or modify a message in transit.

This project provides a concrete answer to that problem: a **lightweight electronic signature** based on HMAC-SHA256, complemented by an XOR cipher implemented in **Xtensa assembly** on an ESP32-CAM node.

The goal is twofold:

- Demonstrate that reliable signing is possible on a constrained microcontroller
- Measure the real benefit of a low-level implementation compared to an equivalent C implementation

---

## Architecture

```text
        ESP32-CAM                              PC
   ┌──────────────┐                 ┌────────────────────┐
   │              │                 │                    │
   │  Capture     │                 │  Mosquitto broker  │
   │  Signature   │──Wi-Fi────────▶ │  (port 1883)       │
   │  Cipher      │     MQTT        │                    │
   │  Publish     │                 │  Monitoring app    │
   │              │                 │  (Python/Tkinter)  │
   └──────────────┘                 └────────────────────┘
```

The flow is as follows:

1. The ESP32-CAM captures an image and base64-encodes it
2. It computes the HMAC-SHA256 signature of the message using a shared secret
3. It XOR-encrypts the signature through a function written in Xtensa assembly
4. It publishes the result on an MQTT topic
5. The PC application recomputes the signature, compares it, and decides whether to accept or reject the message
6. Every valid image is archived locally with its timestamp and verification time

---

## Project structure

| Folder | Contents |
|--------|----------|
| `app/` | Desktop monitoring application (Python + Tkinter) |
| `esp32_cam/` | Embedded code for the ESP32-CAM (C++ and Xtensa assembly) |
| `mesure/` | Scripts and results of the ASM vs C comparative measurements |
| `docs/` | Screenshots and diagrams |

---

## Features

- Real-time verification of HMAC-SHA256 signatures
- Automatic rejection of spoofed or tampered messages, even a single byte
- Persistent archiving of received images on disk
- Full history with timestamps and verification times
- Photo gallery with navigation and direct opening
- Activity log
- CSV export of the message history

---

## Installation

### Requirements

- Python 3.10 or higher
- Mosquitto (MQTT broker)
- Arduino IDE with ESP32 support
- Arduino libraries: PubSubClient, base64

### On the PC

Install the dependencies:

```bash
pip install paho-mqtt pillow
```

Run the Mosquitto broker (installed separately).

Launch the application:

```bash
python app/app_tkinter.py
```

### On the ESP32-CAM

1. Open `esp32_cam/esp32_cam.ino` in Arduino IDE
2. Make sure `crypto_asm.S` and `crypto_asm.h` are in the same folder
3. Set the Wi-Fi SSID and password in the code
4. Set the PC IP address in the `MQTT_SERVER` variable
5. Select the **AI Thinker ESP32-CAM** board
6. Connect GPIO0 to GND to enter flash mode
7. Compile and upload
8. Disconnect GPIO0 and press RESET

---

## Performance results

Comparison between the assembly version and the C version over 1000 iterations, with 256-byte buffers. Each value is an average measured over several cycles.

| Metric | Assembly | C | Gain |
|--------|----------|---|------|
| Processing time | 11.88 µs | 20.47 µs | 42 % |
| CPU cycles | 2,850 | 4,913 | 42 % |
| Energy | 0.001567 mJ | 0.002702 mJ | 42 % |
| Latency | 11.88 µs | 20.47 µs | 42 % |

### Methodological note

Three points must be clarified for an honest reading of these results.

**On the reference C version.** The C version used for comparison is a direct implementation, without specific optimization. A highly optimized C version targeting the 32-bit bus would reduce the gap. This reference version was chosen to represent what a developer naturally writes.

**On energy.** Energy consumption is computed from the measured time, the average current documented in the Espressif datasheet (40 mA at 240 MHz), and the standard supply voltage (3.3 V). It is therefore an estimate proportional to the time measurement, not a direct physical measurement.

**On RAM.** The encryption function performs no dynamic allocation. The memory used is identical in both versions and remains negligible.


Author

Marc Ndayishimiye

Master's student in Communication Systems and IoT

Interests:

IoT Cybersecurity
Embedded Security
MQTT Security
Network Security
Edge Computing
Performance Engineering
License

MIT License