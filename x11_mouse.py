"""
Attack Shark X11 Mouse Driver & Protocol Handler for Linux.
Supports:
  - Attack Shark X11 2.4G Receiver (VID 0x1D57, PID 0xFA60)
  - Attack Shark X11 Wired (VID 0x1D57, PID 0xFA55)
  - PixArt PAW3311 sensor configuration (DPI stages, angle snap, ripple, LOD)
  - Polling rate (125, 250, 500, 1000 Hz)
  - Key response / debounce time
  - Sleep timer & deep sleep
  - Autonomous battery percentage telemetry (Input report 0x03)
"""

import os
import glob
import time
import fcntl
import select
import threading
from typing import Optional, Dict, Any, List, Tuple

# Supported Hardware
X11_VID = "1d57"
X11_WIRELESS_PID = "fa60"
X11_WIRED_PID = "fa55"
X11_MODEL_ID = 0x55  # 85 in decimal

# Report IDs
REPORT_BATTERY = 0x03
REPORT_DPI_CONFIG = 0x04
REPORT_LIGHTING_DEBOUNCE = 0x05
REPORT_POLLING_RATE = 0x06
REPORT_BUTTON_REMAP = 0x08

# Polling Rate Map
POLLING_HZ_TO_CODE = {
    1000: 0x01,
    500:  0x02,
    250:  0x04,
    125:  0x08,
}
POLLING_CODE_TO_HZ = {v: k for k, v in POLLING_HZ_TO_CODE.items()}

# Default DPI Stages for Attack Shark X11
DEFAULT_DPI_STAGES = [800, 1600, 2400, 3200, 5000, 22000]
DEFAULT_DPI_COLORS = [
    [255, 0, 0],     # Stage 1: Red
    [0, 255, 0],     # Stage 2: Green
    [0, 0, 255],     # Stage 3: Blue
    [255, 255, 0],   # Stage 4: Yellow
    [0, 255, 255],   # Stage 5: Cyan
    [255, 0, 255],   # Stage 6: Magenta
    [255, 255, 255], # Stage 7: White
    [255, 128, 0],   # Stage 8: Orange
]

def _ioc(nr: int, ln: int) -> int:
    return (3 << 30) | (ln << 16) | (ord("H") << 8) | nr

def find_x11_mouse_hidraw() -> Optional[Dict[str, Any]]:
    """
    Scans /sys/class/hidraw to find the Attack Shark X11 vendor configuration node (Interface 02).
    """
    for hidraw_dir in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        uevent_file = os.path.join(hidraw_dir, "device", "uevent")
        if not os.path.exists(uevent_file):
            continue
        try:
            with open(uevent_file, "r") as f:
                lines = f.read().splitlines()
            data = dict(l.split("=", 1) for l in lines if "=" in l)
            hid_id = data.get("HID_ID", "").lower()
            hid_name = data.get("HID_NAME", "")
        except Exception:
            continue

        is_match = False
        is_wireless = False
        if f"{X11_VID}:0000{X11_WIRELESS_PID}" in hid_id:
            is_match = True
            is_wireless = True
        elif f"{X11_VID}:0000{X11_WIRED_PID}" in hid_id:
            is_match = True
            is_wireless = False

        if not is_match:
            continue

        # Look up interface number in parent sysfs tree
        dev_dir = os.path.realpath(os.path.join(hidraw_dir, "device"))
        cur = dev_dir
        iface = None
        while cur and cur != "/":
            b_iface = os.path.join(cur, "bInterfaceNumber")
            if os.path.exists(b_iface):
                try:
                    with open(b_iface, "r") as bf:
                        iface = bf.read().strip()
                except Exception:
                    pass
                break
            cur = os.path.dirname(cur)

        # Interface 2 is the vendor config & telemetry channel
        if iface == "02":
            node_name = os.path.basename(hidraw_dir)
            dev_node = f"/dev/{node_name}"
            return {
                "node": dev_node,
                "interface": iface,
                "is_wireless": is_wireless,
                "name": "Attack Shark X11 Wireless" if is_wireless else "Attack Shark X11 Wired",
                "vid_pid": f"{X11_VID}:{X11_WIRELESS_PID if is_wireless else X11_WIRED_PID}"
            }

    return None


class X11MouseDevice:
    """
    Handles bidirectional HID communication with the Attack Shark X11 mouse.
    """
    def __init__(self, dev_path: str):
        self.dev_path = dev_path
        self.fd: Optional[int] = None
        self._open()

    def _open(self):
        try:
            self.fd = os.open(self.dev_path, os.O_RDWR | os.O_NONBLOCK)
        except OSError as e:
            self.fd = None
            raise RuntimeError(f"Não foi possível abrir {self.dev_path}: {e}")

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None

    def send_feature(self, data: bytes):
        """
        Sends a HID feature report using HIDIOCSFEATURE ioctl.
        data starts with the report ID byte.
        """
        if self.fd is None:
            raise RuntimeError("Dispositivo não está aberto.")
        length = len(data)
        ioc_cmd = _ioc(0x06, length)
        fcntl.ioctl(self.fd, ioc_cmd, data)
    def read_input_report(self, timeout_s: float = 0.5) -> Optional[bytes]:
        """
        Reads pending raw input report (e.g. Report 0x03 for battery telemetry).
        """
        if self.fd is None:
            return None
        r, _, _ = select.select([self.fd], [], [], timeout_s)
        if r:
            data = os.read(self.fd, 64)
            if not data:
                raise OSError("Dispositivo desconectado (EOF)")
            return data
        return None

    def set_polling_rate(self, hz: int) -> bool:
        """
        Sends Report 0x06 (9 bytes) to set polling rate.
        [0x06, 0x09, 0x01, rate_code, ~rate_code, 0, 0, 0, 0]
        """
        rate_code = POLLING_HZ_TO_CODE.get(hz, 0x01)
        comp = (0xFF - rate_code) & 0xFF
        packet = bytes([REPORT_POLLING_RATE, 0x09, 0x01, rate_code, comp, 0x00, 0x00, 0x00, 0x00])
        try:
            self.send_feature(packet)
            return True
        except Exception as e:
            print("Erro ao definir polling rate do X11:", e)
            return False

    def set_dpi_config(
        self,
        stages: List[int],
        active_stage: int,
        angle_snap: bool = False,
        ripple_control: bool = False,
        lod: int = 0, # 0 = 1mm, 1 = 2mm
        colors: Optional[List[List[int]]] = None,
        is_wireless: bool = True
    ) -> bool:
        """
        Sends Report 0x04.
        Declared length on 2.4G dongle descriptor is 55 data bytes + 1 report ID = 56 bytes.
        On wired path it is 51 data bytes + 1 report ID = 52 bytes.
        """
        packet_len = 56 if is_wireless else 52
        packet = bytearray(packet_len)
        packet[0] = REPORT_DPI_CONFIG
        packet[1] = 0x38  # protocol field (56)
        packet[2] = 0x01  # fixed
        packet[3] = 0x01 if angle_snap else 0x00
        packet[4] = 0x01 if ripple_control else 0x00
        packet[5] = 0x3F  # Stage enable mask (bits 0-5 = 6 stages enabled)
        packet[6] = 0x01 if angle_snap else 0x00  # duplicate of angle control
        packet[7] = 0x01 if lod else 0x00

        # Stages DPI values (up to 8 stages, PAW3311 uses (DPI / 50 - 1))
        # bytes 8..15 = low bytes, bytes 16..23 = high bytes
        for i in range(8):
            dpi_val = stages[i] if i < len(stages) else (stages[-1] if stages else 1600)
            encoded = max(0, min(65535, int(dpi_val // 50) - 1))
            packet[8 + i] = encoded & 0xFF
            packet[16 + i] = (encoded >> 8) & 0xFF

        packet[24] = max(1, min(len(stages) if stages else 6, active_stage))

        # Per-stage RGB colors (bytes 25..48, 8 stages x 3 bytes)
        palette = colors or DEFAULT_DPI_COLORS
        for i in range(8):
            rgb = palette[i] if i < len(palette) else [255, 255, 255]
            packet[25 + (i * 3)] = rgb[0]
            packet[26 + (i * 3)] = rgb[1]
            packet[27 + (i * 3)] = rgb[2]

        packet[49] = 0x01  # fixed

        # 16-bit additive checksum of bytes[3..49]
        chk = sum(packet[3:50]) & 0xFFFF
        packet[50] = (chk >> 8) & 0xFF
        packet[51] = chk & 0xFF

        try:
            self.send_feature(bytes(packet))
            return True
        except Exception as e:
            print("Erro ao enviar configuração DPI do X11:", e)
            return False

    def set_lighting_and_debounce(
        self,
        mode: int = 0x10,  # 0x00 = Off, 0x10 = Steady, 0x20 = Breathing, 0x50 = Startup/Static DPI
        speed: int = 4,    # 1 to 8 (stored as 9 - speed)
        brightness: int = 8,
        color_rgb: Tuple[int, int, int] = (0, 255, 255),
        sleep_minutes: float = 5.0,
        debounce_ms: int = 4,
        deep_sleep_minutes: int = 30
    ) -> bool:
        """
        Sends Report 0x05 (13 bytes) for lighting mode, debounce, and sleep timers.
        """
        packet = bytearray(13)
        packet[0] = REPORT_LIGHTING_DEBOUNCE
        packet[1] = 0x0F  # length (15)
        packet[2] = 0x01  # fixed
        packet[3] = mode & 0xFF

        # Byte 4: high nibble = deep-sleep min bits 4-7, low nibble = (9 - speed)
        speed_nibble = max(1, min(8, 9 - speed))
        packet[4] = ((deep_sleep_minutes & 0xF0)) | (speed_nibble & 0x0F)

        # Byte 5: high nibble = deep-sleep min bits 0-3, low nibble = brightness
        packet[5] = (((deep_sleep_minutes << 4) & 0xF0)) | (brightness & 0x0F)

        # Bytes 6..8: Color RGB
        packet[6] = color_rgb[0]
        packet[7] = color_rgb[1]
        packet[8] = color_rgb[2]

        # Byte 9: Sleep timer = minutes * 2
        packet[9] = max(1, min(120, int(round(sleep_minutes * 2))))

        # Byte 10: Debounce response time (direct ms)
        packet[10] = max(1, min(25, debounce_ms))

        # Checksum: 16-bit sum of bytes[3..10]
        chk = sum(packet[3:11]) & 0xFFFF
        packet[11] = (chk >> 8) & 0xFF
        packet[12] = chk & 0xFF

        try:
            self.send_feature(bytes(packet))
            return True
        except Exception as e:
            print("Erro ao enviar iluminação/debounce do X11:", e)
            return False


class X11MouseManager:
    """
    Singleton-like monitor thread keeping telemetry (battery, connection status) up to date.
    """
    def __init__(self):
        self.dev_info: Optional[Dict[str, Any]] = None
        self.device: Optional[X11MouseDevice] = None
        self.battery_level: Optional[int] = None
        self.polling_rate: int = 1000
        self.dpi_stages: List[int] = list(DEFAULT_DPI_STAGES)
        self.active_stage: int = 2
        self.angle_snap: bool = False
        self.ripple_control: bool = False
        self.lod: int = 0
        self.debounce_ms: int = 4
        self.sleep_minutes: float = 5.0
        self.light_mode: int = 0x10  # Steady
        self.light_color: List[int] = [0, 255, 255]

        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self.device:
            self.device.close()
            self.device = None

    def _monitor_loop(self):
        while self._running:
            if not self.device:
                info = find_x11_mouse_hidraw()
                if info:
                    try:
                        self.device = X11MouseDevice(info["node"])
                        self.dev_info = info
                    except Exception:
                        self.device = None
                        self.dev_info = None

            if self.device:
                # Read incoming input reports (such as battery status 0x03)
                try:
                    raw = self.device.read_input_report(timeout_s=0.5)
                    if raw and len(raw) >= 5 and raw[0] == REPORT_BATTERY:
                        # [0x03, 0x55, 0x40, 0x01, battery_percent]
                        if raw[1] == X11_MODEL_ID and raw[2] == 0x40:
                            level = raw[4]
                            if 0 <= level <= 100:
                                self.battery_level = level
                except Exception:
                    # Device disconnected
                    if self.device:
                        try:
                            self.device.close()
                        except Exception:
                            pass
                        self.device = None
                        self.dev_info = None
                    time.sleep(1.0)
                time.sleep(1.0)

    def get_status(self) -> Dict[str, Any]:
        info = find_x11_mouse_hidraw()
        connected = bool(info)
        return {
            "connected": connected,
            "name": info["name"] if info else "Attack Shark X11",
            "node": info["node"] if info else None,
            "is_wireless": info.get("is_wireless", True) if info else True,
            "battery": self.battery_level,
            "polling_rate": self.polling_rate,
            "dpi_stages": self.dpi_stages,
            "active_stage": self.active_stage,
            "angle_snap": self.angle_snap,
            "ripple_control": self.ripple_control,
            "lod": self.lod,
            "debounce_ms": self.debounce_ms,
            "sleep_minutes": self.sleep_minutes,
            "light_mode": self.light_mode,
            "light_color": self.light_color
        }

    def apply_settings(self, settings: Dict[str, Any]) -> bool:
        if not self.device:
            info = find_x11_mouse_hidraw()
            if not info:
                return False
            self.device = X11MouseDevice(info["node"])
            self.dev_info = info
        is_wireless = self.dev_info.get("is_wireless", True) if self.dev_info else True
        success = True

        # Polling rate
        if "polling_rate" in settings:
            new_hz = int(settings["polling_rate"])
            if self.device.set_polling_rate(new_hz):
                self.polling_rate = new_hz
            else:
                success = False
            time.sleep(0.3)  # Intervalo de segurança para o firmware sem fio do dongle

        # DPI config
        dpi_changed = any(k in settings for k in ["dpi_stages", "active_stage", "angle_snap", "ripple_control", "lod"])
        if dpi_changed:
            stages = settings.get("dpi_stages", self.dpi_stages)
            act_stage = int(settings.get("active_stage", self.active_stage))
            ang = bool(settings.get("angle_snap", self.angle_snap))
            rip = bool(settings.get("ripple_control", self.ripple_control))
            lod_val = int(settings.get("lod", self.lod))

            if self.device.set_dpi_config(stages, act_stage, ang, rip, lod_val, is_wireless=is_wireless):
                self.dpi_stages = stages
                self.active_stage = act_stage
                self.angle_snap = ang
                self.ripple_control = rip
                self.lod = lod_val
            else:
                success = False
            time.sleep(0.3)

        # Lighting & Debounce
        light_changed = any(k in settings for k in ["light_mode", "light_color", "debounce_ms", "sleep_minutes"])
        if light_changed:
            mode = int(settings.get("light_mode", self.light_mode))
            color = settings.get("light_color", self.light_color)
            deb = int(settings.get("debounce_ms", self.debounce_ms))
            slp = float(settings.get("sleep_minutes", self.sleep_minutes))

            if self.device.set_lighting_and_debounce(
                mode=mode,
                color_rgb=(color[0], color[1], color[2]),
                sleep_minutes=slp,
                debounce_ms=deb
            ):
                self.light_mode = mode
                self.light_color = color
                self.debounce_ms = deb
                self.sleep_minutes = slp
            else:
                success = False

        return success


# Global Manager Instance
mouse_manager = X11MouseManager()
