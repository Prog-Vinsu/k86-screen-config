# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-11-03

### Added
- **Painel de Tela Atual Salva no Teclado (Aba Tela & GIFs):**
  - Exibição visual da mídia atualmente gravada na memória flash SPI do teclado Attack Shark K86.
  - Pré-visualização animada em moldura de alta precisão 240×135 (TFT RGB565).
  - Painel com telemetria e metadados detalhados: nome do arquivo, data e hora da gravação, quantidade de quadros, delay (ms e FPS), modo de enquadramento (Crop, Contain, Stretch), uso estimado da memória flash e versão do firmware do display.
  - Consulta direta ao hardware via opcode `0xAD` para leitura da versão da controladora da tela TFT (`FW TFT v1.06`).
  - Modo Standby tático para teclados com padrões de fábrica ou sem mídia personalizada gravada nesta máquina.
  - Botão de ação rápida para esquecer/limpar o registro da tela gravada e retornar ao modo standby.
  - Persistência sincronizada em `~/.config/attack-shark-k86/current_screen.json`, sincronizando gravações realizadas tanto pela interface gráfica (GUI) quanto pela linha de comando (CLI).
  - Exibição da versão do firmware TFT e do status da tela salva na tabela da aba de Dispositivo (`#tab-info`).

## [1.2.0] - 2026-11-03

### Added
- **Unified Peripheral Hub:** Full support for configuring the **Attack Shark X11** wireless/wired gaming mouse alongside the K86 keyboard.
- **Attack Shark X11 Driver (`x11_mouse.py`):**
  - Dynamic hardware detection for both 2.4 GHz wireless receiver (`1D57:FA60`) and wired connection (`1D57:FA55`).
  - Real-time autonomous battery telemetry parsing from `Input Report 0x03` (`03 55 40 01 <pct>`).
  - PixArt PAW3311 sensor configuration: 6 independent DPI stages (50 to 22,000 DPI), active stage selection, Angle Snapping toggle, Ripple Control smoothing, and Lift-Off Distance (LOD: 1mm / 2mm).
  - Polling rate adjustment (125 Hz, 250 Hz, 500 Hz, 1000 Hz via `Report 0x06`).
  - Switch debounce / Key response time (1ms - 20ms) and sleep timer configuration via `Report 0x05`.
  - Wireless 2.4G pacing and dynamic report sizing (56 bytes on dongle, 52 bytes on wired cable).
- **Dedicated 'Mouse X11' UI Tab:**
  - Real-time battery indicator badge with custom SVG telemetry icon.
  - Balanced 6-column DPI stage grid with LED color dots corresponding to physical hardware indicators.
  - Direct click-to-activate stage selection and live value editing.
  - Tactical toggle switches for Angle Snapping and Ripple Control.
- **Reorganized 'Dispositivo' (Device Info) Tab:**
  - Symmetrical two-column dashboard cleanly separating Keyboard K86 and Mouse X11 hardware information (VID:PID, device node, firmware/family, battery, connection mode).
  - Dedicated and labeled Keyboard Factory Reset action.
- **Modular UI Architecture (`ui/`):**
  - Split monolithic `app_ui.html` into structured files: `ui/index.html`, `ui/css/style.css`, `ui/js/app.js`, and `ui/js/keyboard_preview.js`.
- **Updated udev Rules (`70-attack-shark-devices.rules`):**
  - Added non-root user permissions (`TAG+="uaccess"`) for Attack Shark X11 dongle and wired USB nodes.

## [1.1.0] - 2026-11-02

### Added
- Full hardware configuration tabs: Screen, Device, Lighting, and Info.
- Dedicated Side RGB lighting controls (SLEDPARAM opcode `0x08` / `0x88`) with 6 modes: Off, Static, Breathing, Neon, Wave, and Snake.
- Interactive HSV Color Wheel canvas replacing native legacy color picker.
- 14 quick color preset dots with single-click selection.
- Onboard TFT screen clock synchronization via opcode `0x28`.
- Key debounce latency adjustment (1ms - 10ms).
- Hardware switches for Win Lock, WASD/Arrow swap, Backlight disable, and Side LEDs disable.
- Sleep and Deep Sleep battery timeout controls for 2.4 GHz and Bluetooth.
- Factory reset command (opcode `0x02` / `0x01`).

### Fixed
- Fixed select dropdown text visibility in WebKit2GTK on dark themes.
- Fixed direct side light state synchronization when toggled from hardware options.

## [1.0.0] - 2026-11-02

### Added
- Native GTK 3 + WebKit2GTK graphical interface with Drag & Drop support.
- Direct IPC bridge between UI and Python without local HTTP server exposure.
- Safe fallback mode with token-based authentication and restricted origin when WebKit2GTK is unavailable.
- Hardware safety verification: reads device ID via `0x8F` identify command before sending screen upload packets.
- Support for Attack Shark K86 Revision 1 (`3151:4015`, ID 1168) and Revision 2 (`3151:5002`, ID 2730).
- Automatic image processing: conversion to 240x135 RGB565 column-major format.
- Aspect ratio preservation options: Crop (default), Contain (letterbox), and Stretch.
- Smart frame sampling to prevent flash memory overflow.
- CLI mode with `--preview`, `--dry-run`, `--delay`, and `--max-frames` options.
- Dynamic installation (`install.sh`) and uninstallation (`uninstall.sh`) scripts with udev rule setup.
- Issue templates for bug reports and new board compatibility requests.
