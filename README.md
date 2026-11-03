# Attack Shark Peripheral Hub (Linux)

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange.svg)](#requirements)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](#requirements)

> Native desktop and CLI utility for configuring **Attack Shark K86** mechanical keyboards (RGB lighting, hardware options, and 240×135 TFT screen GIF uploads) and **Attack Shark X11** gaming mice (DPI stages, polling rate, LOD, angle snap, debounce, battery telemetry) on Linux, without requiring Windows, Wine, or virtual machines.

[🇧🇷 Versão em Português disponível (README.pt-BR.md)](README.pt-BR.md)
---

## ⚡ Features

* **Native Desktop Window (GTK 3 + WebKit2GTK):** Clean desktop application running in your native desktop environment with full **Drag & Drop** support.
* **Direct IPC (Zero HTTP Server):** Completely eliminates local HTTP ports or CORS vulnerabilities; communication stays within an isolated process memory bridge.
* **Hardware Safety Verification:** Queries device identity via read-only command `0x8F` before transmitting any data packets, ensuring only verified Attack Shark K86 controllers receive screen writes.
* **Animated GIF & Screen Management:**
  * **Current Screen Saved on Keyboard:** Live status card displaying the animation currently stored in the keyboard's flash memory, including animated bezel preview, filename, upload date/time, frame count, playback speed (ms/FPS), fit mode, flash storage footprint, and onboard display firmware revision (`0xAD`).
  * **Real-time 240×135 bezel preview** with pixel-perfect aspect ratio scaling.
  * **Frame delay & playback speed slider** (fine-tuned from 5 to 150 ms).
  * **Smart frame downsampling** to safely fit the keyboard's SPI flash memory limit.
  * **Fit modes:** Crop to fill (default), Contain (letterbox), or Stretch.
  * **Standby Mode & History Reset:** Fallback dashboard view for factory default screens with quick clear option.
* **Hardware Settings (sharkfin-compatible):**
  * **OLED/TFT Clock Sync:** Synchronize the keyboard screen's onboard clock with the computer time in one click.
  * **Debounce Adjustment:** 1ms to 10ms key debounce response time.
  * **Hardware Toggles:** Win Lock, WASD / Arrow key swap, Backlight disable, Side LED disable.
  * **Battery Sleep Timers:** Independent 2.4 GHz and Bluetooth sleep and deep sleep timeouts.
* **Main Backlight RGB Control:**
  * 18 backlight animation modes (Static, Breathing, Wave, Ripple, Meteor, etc.).
  * Interactive HSV Color Wheel + 14 quick color presets or dynamic Rainbow mode.
  * Brightness (0-4) and Effect speed (0-4) sliders.
* **Side Strip RGB Control (SLEDPARAM):**
  * Dedicated control over left and right edge light bars.
  * 6 side lighting modes: Off, Static, Breathing, Neon, Wave, and Snake.
  * Dedicated brightness, speed, and color synchronization with the main backlight.
* **Attack Shark X11 Mouse Configuration:**
  * **Wireless 2.4G & Wired Support:** Fully compatible over the 2.4 GHz USB receiver (`1d57:fa60`) and USB-C cable (`1d57:fa55`).
  * **Live Battery Telemetry:** Real-time autonomous battery readout (`Report 0x03`).
  * **Sensor Tuning (PixArt PAW3311):** 6 configurable DPI stages (50 to 22,000 DPI) with hardware LED color matching, active stage switching, Angle Snapping, and Ripple Control.
  * **Polling Rate & LOD:** 125, 250, 500, and 1000 Hz polling rate switching, plus 1mm / 2mm Lift-Off Distance (LOD).
  * **Key Response & Sleep:** Adjustable switch debounce (1ms to 20ms) and inactivity sleep timer (1 to 15 min).
* **Unified Device Info Tab:**
  * Dual-panel system view cleanly separating K86 keyboard and X11 mouse telemetry, device nodes, firmware details, and USB identifiers.
* **Modular UI Architecture:**
  * Clean `ui/` directory (`index.html`, `style.css`, `app.js`, `keyboard_preview.js`) without external build tools or bundlers.
* **Factory Reset:** Send onboard reset command to restore factory defaults.
* **Dual Operation (GUI + CLI):** Launch without arguments for the visual window, or pass a file path directly for instant command-line uploads.
* **Dry-Run Mode:** Test image conversion and hardware communication without writing to flash (`--dry-run`).

## 🖥️ Compatibility

| Model | USB VID:PID | Device ID (`0x8F`) | Controller Lineage | Screen Draw Status |
|---|---|---|---|---|
| **Attack Shark K86 (Rev 1)** | `3151:4015` | `1168` | `yc3121` (yc500 family) | **Supported & Verified** |
| **Attack Shark K86 (Rev 2)** | `3151:5002` | `2730` | `yc3123` (gen2 family) | **Supported & Verified** |
| **Attack Shark K86 (Rev 3)** | `3151:5056` | `4094` | `ry6602` (gen2 family) | *Not supported* (separate display chip) |
| **Attack Shark X11 (Wireless)** | `1d57:fa60` | N/A | Beken BK3633 / PAW3311 | **Supported (DPI, Polling, Battery, LOD)** |
| **Attack Shark X11 (Wired)** | `1d57:fa55` | N/A | Beken BK3633 / PAW3311 | **Supported (DPI, Polling, LOD)** |

> **Note on K86 Screen Uploads:** Transferring GIFs and images to the K86 screen requires a **USB cable** connection; the keyboard's 2.4G and Bluetooth modes do not expose screen flash write endpoints. The X11 mouse configuration works both wirelessly (2.4G dongle) and wired.

---

## 📋 Requirements

* **Operating System:** Linux (Kernel 5.4+ with `hidraw` enabled).
* **Connection:** **USB Cable required**. Wireless 2.4 GHz receivers and Bluetooth do not expose the screen transfer endpoints.
* **Python Dependencies:** Python 3.10+ and Pillow:
  ```bash
  sudo apt install python3-pil
  # or: pip install pillow
  ```
* **Native GUI Dependencies (Default):**
  * Debian / Ubuntu / Zorin OS: `sudo apt install python3-gi gir1.2-webkit2-4.1` (usually pre-installed).
  * Arch Linux: `sudo pacman -S python-gobject webkit2gtk-4.1`
  * Fedora: `sudo dnf install python3-gobject webkit2gtk4.1`
  *(If WebKit2GTK is missing, a hardened fallback browser window with random-token authentication will be used).*

---

## 🚀 Installation & Usage

### 1. Automatic Install (Desktop Shortcut + Permissions)

Run the included installer:

```bash
./install.sh
```

This will:
1. Generate and install a localized `.desktop` application shortcut to `~/.local/share/applications/`.
2. Install the application icon into your user icon theme.
3. Configure the `udev` rules so you can configure both the K86 keyboard and the X11 mouse without `sudo`.

*After running `install.sh`, unplug and replug the keyboard's USB cable and the mouse receiver.*

### 2. Launching the GUI

* From your system's application menu: search for **"Attack Shark K86 Screen"**.
* Or from the terminal:
  ```bash
  ./k86_gif_uploader.py
  ```

### 3. Command Line Interface (CLI)

```bash
# Upload a GIF with default settings:
./k86_gif_uploader.py my_animation.gif

# Adjust frame delay (lower = faster; typical range 20 to 60):
./k86_gif_uploader.py my_animation.gif --delay 35

# Limit to 45 frames:
./k86_gif_uploader.py my_animation.gif --max-frames 45

# Preview local conversion without uploading:
./k86_gif_uploader.py my_animation.gif --preview

# Perform a dry-run test (verifies device ID and conversion without flashing):
./k86_gif_uploader.py my_animation.gif --dry-run
```

#### CLI Options Reference:
```
positional arguments:
  file                  Path to image or GIF file. If omitted, opens the GUI window.

options:
  -h, --help            Show help message and exit
  --gui                 Force native GUI window
  --dry-run             Run hardware handshake and conversion without flashing
  --version             Show program version
  --delay DELAY         Frame delay byte (0-255)
  --max-frames MAX      Maximum frame count cap (default: 60)
  --step STEP           Custom frame sampling step
  --fit {crop,contain,stretch}
                        Frame fitting mode (default: crop)
  --mode {vendor,stream}
                        Upload protocol mode (default: vendor)
  --preview             Save 'k86_preview_240x135.gif' locally before uploading
```

---

## 🎨 Where to Find GIFs for the K86

The K86 display has a native resolution of **240×135 pixels** (16:9 widescreen ratio). Horizontal animations and pixel art loops produce the best visual results:

* **[Pinterest - Attack Shark K86 GIFs](https://br.pinterest.com/mayssarf/gifs-for-attack-shark-k86):** Community-curated board of compatible animations.
* **[Pinterest - Keyboard OLED / TFT GIFs](https://www.pinterest.com/ideas/keyboard-oled-gifs/960337052007/):** General collection of small-screen animations.
* **[k86-screen-frames (Marcel Pietron)](https://github.com/marcel-pietron/k86-screen-frames):** Contains the green retro Unix terminal loop (`shell_240x135.gif`) designed for 240×135.
* **[GIPHY](https://giphy.com/) & [Tenor](https://tenor.com/):** Search for `pixel art loop`, `bongo cat loop`, `lofi pixel art`, or `cyberpunk pixel art`.

---

## 🔧 Troubleshooting

* **Permission denied on `/dev/hidrawX` (Keyboard or Mouse):**
  If you did not run `install.sh`, install the unified udev rule manually and reconnect your devices:
  ```bash
  printf '%s\n' \
    '# Attack Shark K86 Keyboard' \
    'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="3151", ATTRS{idProduct}=="4015|5002", MODE="0660", TAG+="uaccess"' \
    '# Attack Shark X11 Mouse (Wireless Receiver & Wired)' \
    'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1d57", ATTRS{idProduct}=="fa60|fa55", MODE="0660", TAG+="uaccess"' \
    | sudo tee /etc/udev/rules.d/70-attack-shark-devices.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```
  *Then unplug and replug the K86 USB cable and the X11 2.4G wireless receiver/dock.*
* **"Display did not accept announce handshake":**
  Ensure the keyboard is plugged in directly via USB cable (not via unpowered hub). Reconnect the cable. Make sure no other keyboard software (e.g., `sharkfin`) is open.
* **White horizontal band or corrupted frame:**
  Re-upload a single still frame (`.png`) to reset the frame buffer.

---

## 📜 Credits & Prior Art

This project relies on the reverse-engineered USB HID protocol documented by the keyboard community:

* **[sharkfin](https://github.com/dniminenn/sharkfin)** by JR Lanteigne (GPL-3.0-or-later) – Reverse-engineered ROYUAN HID protocol documentation and board registry.
* **[k86-screen-frames](https://github.com/marcel-pietron/k86-screen-frames)** by Marcel Pietron (GPL-3.0-or-later) – Multi-frame handshake research on real K86 revision 2730 hardware.

## ⚖️ Disclaimer & License

This is an independent open-source project and is **not affiliated with, endorsed by, or associated with Attack Shark, Shenzhen ROYUAN Technology, or their affiliates**. All product names and trademarks are property of their respective owners.

This software is distributed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. See [LICENSE](LICENSE) for details.
