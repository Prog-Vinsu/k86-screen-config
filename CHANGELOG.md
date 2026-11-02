# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
