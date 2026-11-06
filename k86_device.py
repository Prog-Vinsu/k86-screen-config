#!/usr/bin/env python3
"""
Attack Shark K86 Hardware Protocol, Image Processing & Asynchronous Device Manager.
"""

import base64
import copy
import datetime
import fcntl
import glob
import io
import json
import os
import queue
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageOps, ImageSequence
except ImportError:
    sys.exit("Erro: Pillow não está instalado. Instale com: pip install pillow ou sudo apt install python3-pil")

# Constantes do display do K86
SCREEN_W = 240
SCREEN_H = 135
PAGE_DATA_LEN = 56
FRAME_RAW_LEN = SCREEN_W * SCREEN_H * 2  # 64.800 bytes (RGB565)
FRAME_STRIDE = 65536

SUPPORTED_VID_PIDS = [
    ("3151", "4015", "cable"),     # K86 Rev 1 Cable (yc3121 / yc500 - ID 1168)
    ("3151", "5002", "cable"),     # K86 Rev 2 Cable (yc3123 / gen2 - ID 2730)
    ("3151", "4011", "wireless"),  # K86 Rev 1 2.4G Wireless Dongle
    ("3151", "5006", "wireless"),  # K86 Rev 2 2.4G Wireless Dongle
]

VERIFIED_K86_DEVICE_IDS = [1168, 2730]
CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "attack-shark-k86")
CURRENT_SCREEN_FILE = os.path.join(CONFIG_DIR, "current_screen.json")


def _ioc(nr: int, ln: int) -> int:
    return (3 << 30) | (ln << 16) | (ord("H") << 8) | nr


HIDIOCSFEATURE_65 = _ioc(0x06, 65)
HIDIOCGFEATURE_65 = _ioc(0x07, 65)


def checksum7(packet: bytearray) -> None:
    packet[7] = (0xFF - (sum(packet[0:7]) & 0xFF)) & 0xFF


def checksum8(packet: bytearray) -> None:
    packet[8] = (0xFF - (sum(packet[0:8]) & 0xFF)) & 0xFF
_SAFE_PIDS = set()
_CONFLICT_TARGETS = {b"sharkfin\n", b"k86_screen\n", b"sharkfin", b"k86_screen"}
_SHELL_COMMS = {b"sh\n", b"bash\n", b"dash\n", b"zsh\n", b"fish\n"}


def check_conflicting_tools() -> Optional[str]:
    my_pid = str(os.getpid())
    try:
        entries = os.listdir("/proc")
    except OSError:
        return None
    current_pids = set()
    for entry in entries:
        if not entry.isdigit() or entry == my_pid:
            continue
        current_pids.add(entry)
        if entry in _SAFE_PIDS:
            continue
        try:
            fd = os.open(f"/proc/{entry}/comm", os.O_RDONLY)
            try:
                comm = os.read(fd, 32)
            finally:
                os.close(fd)
            if comm in _CONFLICT_TARGETS:
                return comm.decode("ascii", errors="ignore").strip()
            if comm not in _SHELL_COMMS:
                _SAFE_PIDS.add(entry)
        except OSError:
            continue
    _SAFE_PIDS.intersection_update(current_pids)
    return None


class HidrawDevice:
    def __init__(self, dev_path: str):
        self.dev_path = dev_path
        self.fd = os.open(dev_path, os.O_RDWR)

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None

    def send_feature(self, data: bytes):
        payload = b"\x00" + bytes(data)
        fcntl.ioctl(self.fd, HIDIOCSFEATURE_65, payload)

    def read_feature(self) -> bytes:
        buf = bytearray(65)
        fcntl.ioctl(self.fd, HIDIOCGFEATURE_65, buf)
        return bytes(buf[1:])

    def roundtrip(self, packet: bytes, timeout_s: float = 0.25) -> Optional[bytes]:
        self.send_feature(packet)
        start = time.perf_counter()
        first = True
        while time.perf_counter() - start < timeout_s:
            time.sleep(0.008 if first else 0.006)
            first = False
            try:
                reply = self.read_feature()
                if reply and reply[0] == packet[0]:
                    return reply
            except Exception:
                pass
        return None

    def read_device_id(self) -> Optional[int]:
        p = bytearray(64)
        p[0] = 0x8F
        checksum7(p)
        reply = self.roundtrip(p, timeout_s=0.2)
        if reply and reply[0] == 0x8F and len(reply) >= 5:
            if reply[3] == 0xFF and reply[1] == 0 and reply[2] == 0:
                return None
            return int.from_bytes(reply[1:5], "little")
        return None

    def read_display_firmware_version(self) -> Optional[str]:
        p = bytearray(64)
        p[0] = 0xAD
        checksum7(p)
        reply = self.roundtrip(bytes(p), timeout_s=0.15)
        if reply and reply[0] == 0xAD and len(reply) >= 3:
            if reply[1] == 0 and reply[2] == 0:
                return None
            return f"{reply[2]}.{reply[1]:02d}"
        return None


def scan_keyboard_sysfs() -> Optional[Tuple[str, str, str, str]]:
    """
    Fast sysfs-only scan (~0.8 ms) without opening /dev/hidrawX or sending USB feature reports.
    Returns (node, vid_pid, name, conn_type) if found.
    """
    for hidraw_path in glob.glob("/sys/class/hidraw/hidraw*"):
        dev_dir = os.path.join(hidraw_path, "device")
        uevent_file = os.path.join(dev_dir, "uevent")
        if not os.path.exists(uevent_file):
            continue
        try:
            with open(uevent_file, "r", encoding="utf-8", errors="ignore") as f:
                uevent = f.read()
        except Exception:
            continue

        matched_id = None
        conn_type = "cable"
        for item in SUPPORTED_VID_PIDS:
            vid, pid = item[0], item[1]
            ctype = item[2] if len(item) > 2 else "cable"
            if f":{vid.upper()}:{pid.upper()}" in uevent or f"HID_ID=0003:0000{vid}:0000{pid}" in uevent:
                matched_id = f"{vid}:{pid}"
                conn_type = ctype
                break

        if not matched_id:
            continue

        desc_file = os.path.join(dev_dir, "report_descriptor")
        if os.path.exists(desc_file):
            try:
                with open(desc_file, "rb") as f:
                    desc = f.read(16)
                if desc.startswith(b"\x06\xff\xff\x09\x02"):
                    node = "/dev/" + os.path.basename(hidraw_path)
                    name = "Attack Shark K86"
                    for line in uevent.splitlines():
                        if line.startswith("HID_NAME="):
                            name = line.split("=", 1)[1]
                            break
                    return node, matched_id, name, conn_type
            except Exception:
                continue

    return None


def find_keyboard_hidraw() -> Optional[Tuple[str, str, str, Optional[int], str]]:
    sysfs_info = scan_keyboard_sysfs()
    if not sysfs_info:
        return None
    node, matched_id, name, conn_type = sysfs_info
    dev_id = None
    try:
        temp_dev = HidrawDevice(node)
        try:
            dev_id = temp_dev.read_device_id()
        finally:
            temp_dev.close()
    except Exception:
        pass
    return node, matched_id, name, dev_id, conn_type


def query_keyboard_display_fw(node: str) -> Optional[str]:
    try:
        temp_dev = HidrawDevice(node)
        try:
            return temp_dev.read_display_firmware_version()
        finally:
            temp_dev.close()
    except Exception:
        return None


def load_current_screen_info(dev_display_fw: Optional[str] = None) -> dict:
    data = None
    if os.path.exists(CURRENT_SCREEN_FILE):
        try:
            with open(CURRENT_SCREEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print("Erro ao carregar current_screen.json:", e)

    if not data or not isinstance(data, dict):
        data = {
            "has_saved": False,
            "file_name": None,
            "width": SCREEN_W,
            "height": SCREEN_H,
            "color_format": "RGB565 (16 bits)",
            "max_recommended_frames": 60,
        }

    if dev_display_fw:
        data["display_fw"] = dev_display_fw

    return data


def save_current_screen_info(
    file_name: str,
    pil_frames: List[Image.Image],
    delay: int,
    fit_mode: str = "crop",
    display_fw: Optional[str] = None,
) -> dict:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    count = len(pil_frames)
    buf = io.BytesIO()
    if count > 1:
        pil_frames[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=pil_frames[1:],
            duration=delay,
            loop=0,
            optimize=True,
        )
        mime = "image/gif"
    else:
        pil_frames[0].save(buf, format="PNG", optimize=True)
        mime = "image/png"

    b64_preview = f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"

    now = datetime.datetime.now()
    now_iso = now.isoformat()
    now_display = now.strftime("%d/%m/%Y às %H:%M")

    fit_labels = {
        "crop": "Preencher (Crop)",
        "contain": "Conter (Barras)",
        "stretch": "Esticar",
    }

    fps = round(1000.0 / max(1, delay), 1)
    raw_bytes = count * FRAME_RAW_LEN
    raw_mb = f"{raw_bytes / (1024 * 1024):.2f} MB"

    data = {
        "has_saved": True,
        "file_name": os.path.basename(file_name) if file_name else "animacao.gif",
        "uploaded_at": now_iso,
        "uploaded_at_display": now_display,
        "frames_count": count,
        "delay": delay,
        "fps": fps,
        "fit_mode": fit_mode,
        "fit_mode_label": fit_labels.get(fit_mode, fit_mode),
        "width": SCREEN_W,
        "height": SCREEN_H,
        "color_format": "RGB565 (16 bits)",
        "raw_size_bytes": raw_bytes,
        "raw_size_mb": raw_mb,
        "display_fw": display_fw or "1.06",
        "preview_data_url": b64_preview,
    }

    try:
        with open(CURRENT_SCREEN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Erro ao salvar current_screen.json:", e)

    return data


def clear_current_screen_info() -> bool:
    try:
        if os.path.exists(CURRENT_SCREEN_FILE):
            os.remove(CURRENT_SCREEN_FILE)
            return True
    except Exception as e:
        print("Erro ao remover current_screen.json:", e)
    return False


# ==============================================================================
# OPERAÇÕES DE CONFIGURAÇÃO DE HARDWARE (SHARKFIN COMPATIBLE)
# ==============================================================================
def sync_clock(dev: HidrawDevice, dt: Optional[datetime.datetime] = None) -> bool:
    if dt is None:
        dt = datetime.datetime.now()
    p = bytearray(64)
    p[0] = 0x28
    checksum7(p)
    p[8] = (dt.year >> 8) & 0xFF
    p[9] = dt.year & 0xFF
    p[10] = dt.month
    p[11] = dt.day
    p[12] = dt.hour
    p[13] = dt.minute
    p[14] = dt.second
    dev.send_feature(bytes(p))
    return True


def read_keyboard_settings(dev: HidrawDevice, dev_id: int) -> dict:
    # 1. Debounce
    p = bytearray(64)
    p[0] = 0x91 if dev_id == 1168 else 0x86
    checksum7(p)
    r_deb = dev.roundtrip(bytes(p), timeout_s=0.15)
    deb = (r_deb[2] if dev_id == 1168 else r_deb[1]) if r_deb else 3

    # 2. Options
    p = bytearray(64)
    p[0] = 0x86 if dev_id == 1168 else 0x89
    checksum7(p)
    r_opt = dev.roundtrip(bytes(p), timeout_s=0.15)
    flags = r_opt[2] if r_opt else 0
    options = {
        "win_lock": bool(flags & 1),
        "mac_mode": bool(flags & 2),
        "wasd_swap": bool(flags & 8),
        "led_off": bool(flags & 16),
        "side_led_off": bool(flags & 32),
    }

    # 3. Sleep Times
    p = bytearray(64)
    p[0] = 0x92 if dev_id == 1168 else 0x91
    checksum7(p)
    r_slp = dev.roundtrip(bytes(p), timeout_s=0.15)
    if r_slp:
        bt_sleep = int.from_bytes(r_slp[1:3], "little")
        rf_sleep = int.from_bytes(r_slp[3:5], "little")
        bt_deep = int.from_bytes(r_slp[5:7], "little")
        rf_deep = int.from_bytes(r_slp[7:9], "little")
    else:
        bt_sleep, rf_sleep, bt_deep, rf_deep = 180, 180, 1200, 1200
    sleep = {
        "bt_sleep": bt_sleep,
        "rf_sleep": rf_sleep,
        "bt_deep": bt_deep,
        "rf_deep": rf_deep,
    }

    # 4. LED Parameters
    p = bytearray(64)
    p[0] = 0x87
    checksum7(p)
    r_led = dev.roundtrip(bytes(p), timeout_s=0.15)
    if r_led:
        mode = r_led[1]
        speed = max(0, min(4, 5 - r_led[2] if dev_id == 1168 else r_led[2]))
        brightness = max(0, min(4, r_led[3]))
        flags4 = r_led[4]
        rainbow = (flags4 & 0x0F) == 8
        rgb = [r_led[5], r_led[6], r_led[7]]
    else:
        mode, speed, brightness, rainbow, rgb = 4, 2, 4, False, [0, 255, 255]
    led = {
        "mode": mode,
        "speed": speed,
        "brightness": brightness,
        "rainbow": rainbow,
        "rgb": rgb,
    }

    # 5. Side Light (SLEDPARAM 0x88)
    p = bytearray(64)
    p[0] = 0x88
    checksum7(p)
    r_sled = dev.roundtrip(bytes(p), timeout_s=0.10)
    if r_sled and r_sled[0] == 0x88:
        smode = r_sled[1]
        sspeed = max(0, min(4, r_sled[2]))
        sbrightness = max(0, min(4, r_sled[3]))
        sflags4 = r_sled[4]
        srainbow = (sflags4 & 0x0F) == 8 or smode == 3
        srgb = [r_sled[5], r_sled[6], r_sled[7]]
    else:
        smode, sspeed, sbrightness, srainbow, srgb = 1, 2, 4, False, [0, 255, 255]
    sled = {
        "mode": smode,
        "speed": sspeed,
        "brightness": sbrightness,
        "rainbow": srainbow,
        "rgb": srgb,
    }

    if brightness == 0:
        options["led_off"] = True
    if smode == 0 or sbrightness == 0:
        options["side_led_off"] = True
    return {"debounce": deb, "options": options, "sleep": sleep, "led": led, "sled": sled}


def write_debounce(dev: HidrawDevice, dev_id: int, val_ms: int) -> bool:
    val_ms = max(1, min(10, val_ms))
    p = bytearray(64)
    if dev_id == 1168:
        p[0] = 0x11
        p[1] = 0
        p[2] = val_ms
    else:
        p[0] = 0x06
        p[1] = val_ms
    checksum7(p)
    dev.send_feature(bytes(p))
    return True


def write_options(dev: HidrawDevice, dev_id: int, opts: dict) -> bool:
    p = bytearray(64)
    p[0] = 0x86 if dev_id == 1168 else 0x89
    checksum7(p)
    r = dev.roundtrip(bytes(p), timeout_s=0.15)
    preserved = r[2] if r else 0
    fn_matrix = r[3] if r else 0
    power_save = r[4] if r else 0

    flags = (
        (preserved & 0b11000000)
        | (1 if opts.get("win_lock") else 0)
        | (8 if opts.get("wasd_swap") else 0)
        | (16 if opts.get("led_off") else 0)
        | (32 if opts.get("side_led_off") else 0)
    )

    p_set = bytearray(64)
    p_set[0] = 0x06 if dev_id == 1168 else 0x09
    p_set[1] = 0
    p_set[2] = flags
    p_set[3] = fn_matrix
    p_set[4] = power_save
    checksum7(p_set)
    dev.send_feature(bytes(p_set))
    return True


def write_sleep_times(dev: HidrawDevice, dev_id: int, bt: int, rf: int, dbt: int, drf: int) -> bool:
    p = bytearray(64)
    p[0] = 0x12 if dev_id == 1168 else 0x11
    checksum7(p)
    p[8:10] = bt.to_bytes(2, "little")
    p[10:12] = rf.to_bytes(2, "little")
    p[12:14] = dbt.to_bytes(2, "little")
    p[14:16] = drf.to_bytes(2, "little")
    dev.send_feature(bytes(p))
    return True


def write_led_param(
    dev: HidrawDevice, dev_id: int, mode: int, speed: int, brightness: int, rainbow: bool, rgb: list
) -> bool:
    p = bytearray(64)
    p[0] = 0x07
    p[1] = max(1, min(19, mode))
    p[2] = max(1, 5 - speed) if dev_id == 1168 else max(0, min(4, speed))
    p[3] = max(0, min(4, brightness))
    p[4] = 0x08 if rainbow else 0x07
    p[5] = rgb[0] & 0xFF
    p[6] = rgb[1] & 0xFF
    p[7] = rgb[2] & 0xFF
    checksum8(p)
    dev.send_feature(bytes(p))
    return True


def write_sled_param(
    dev: HidrawDevice, dev_id: int, mode: int, speed: int, brightness: int, rainbow: bool, rgb: list
) -> bool:
    p = bytearray(64)
    p[0] = 0x08
    p[1] = max(0, min(5, mode))
    p[2] = max(0, min(4, speed))
    p[3] = max(0, min(4, brightness))
    p[4] = 0x08 if rainbow or mode == 3 else 0x07
    p[5] = rgb[0] & 0xFF
    p[6] = rgb[1] & 0xFF
    p[7] = rgb[2] & 0xFF
    checksum8(p)
    dev.send_feature(bytes(p))
    return True


def write_side_light(dev: HidrawDevice, dev_id: int, enabled: bool) -> bool:
    if enabled:
        return write_sled_param(dev, dev_id, mode=1, speed=2, brightness=4, rainbow=False, rgb=[0, 255, 255])
    else:
        return write_sled_param(dev, dev_id, mode=0, speed=2, brightness=0, rainbow=False, rgb=[0, 0, 0])


def write_main_light(
    dev: HidrawDevice, dev_id: int, enabled: bool, cached_led: Optional[Dict[str, Any]] = None
) -> bool:
    if cached_led is not None:
        cur_led = cached_led
    else:
        s = read_keyboard_settings(dev, dev_id)
        cur_led = s.get("led", {})
    mode = cur_led.get("mode", 1)
    speed = cur_led.get("speed", 2)
    rainbow = cur_led.get("rainbow", False)
    rgb = cur_led.get("rgb", [0, 255, 255])
    brightness = 4 if enabled else 0
    return write_led_param(dev, dev_id, mode=mode, speed=speed, brightness=brightness, rainbow=rainbow, rgb=rgb)


def write_factory_reset(dev: HidrawDevice, dev_id: int) -> bool:
    p = bytearray(64)
    p[0] = 0x02 if dev_id == 1168 else 0x01
    checksum7(p)
    dev.send_feature(bytes(p))
    return True


# ==============================================================================
# PROCESSAMENTO DE IMAGEM & PROTOCOLO DE TELA
# ==============================================================================
def convert_image_to_rgb565_column_major(img: Image.Image) -> bytes:
    raw_rgb = img.convert("RGB").transpose(Image.Transpose.TRANSPOSE).tobytes()
    out = bytearray(FRAME_RAW_LEN)
    idx = 0
    for i in range(0, len(raw_rgb), 3):
        r = raw_rgb[i]
        g = raw_rgb[i + 1]
        b = raw_rgb[i + 2]
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        out[idx] = v >> 8
        out[idx + 1] = v & 0xFF
        idx += 2
    return bytes(out)


def process_frames_from_image(
    im: Image.Image,
    max_frames: int = 60,
    fit_mode: str = "crop",
    target_step: Optional[int] = None,
) -> Tuple[List[bytes], List[Image.Image], int]:
    durations = []
    extracted = []

    for frame in ImageSequence.Iterator(im):
        durations.append(frame.info.get("duration", 100))
        frame_rgba = frame.convert("RGBA")
        bg = Image.new("RGBA", frame_rgba.size, (0, 0, 0, 255))
        frame_composite = Image.alpha_composite(bg, frame_rgba).convert("RGB")
        extracted.append(frame_composite)

    total_frames = len(extracted)
    if total_frames == 0:
        raise ValueError("Nenhum quadro válido encontrado na imagem.")

    if target_step is not None and target_step > 1:
        step = target_step
    elif total_frames > max_frames:
        step = max(1, total_frames // max_frames)
    else:
        step = 1

    selected_frames = extracted[::step]
    if len(selected_frames) > max_frames:
        selected_frames = selected_frames[:max_frames]

    resized_images = []
    raw_frames = []

    for f in selected_frames:
        if fit_mode == "contain":
            f_fitted = ImageOps.pad(f, (SCREEN_W, SCREEN_H), method=Image.Resampling.LANCZOS, color=(0, 0, 0))
        elif fit_mode == "stretch":
            f_fitted = f.resize((SCREEN_W, SCREEN_H), Image.Resampling.LANCZOS)
        else:
            f_fitted = ImageOps.fit(f, (SCREEN_W, SCREEN_H), method=Image.Resampling.LANCZOS)

        resized_images.append(f_fitted)
        raw_frames.append(convert_image_to_rgb565_column_major(f_fitted))

    avg_duration = int(sum(durations) / len(durations)) if durations else 100
    effective_duration = avg_duration * step

    return raw_frames, resized_images, effective_duration


def build_announce_packet(frame_idx: int, total_frames: int, delay: int, length: int) -> bytes:
    p = bytearray(64)
    p[0] = 0xA5
    p[1] = frame_idx
    p[2] = total_frames
    p[3] = delay & 0xFF
    p[4] = length & 0xFF
    p[5] = (length >> 8) & 0xFF
    p[6] = 0
    checksum7(p)
    p[8] = 0
    p[9] = 0
    p[10] = SCREEN_W & 0xFF
    p[11] = SCREEN_H & 0xFF
    p[12] = 0
    p[13] = 0
    p[14] = (SCREEN_W >> 8) & 0xFF
    p[15] = (SCREEN_H >> 8) & 0xFF
    p[16] = (length >> 16) & 0xFF
    p[17] = (length >> 24) & 0xFF
    p[18] = 0
    return bytes(p)


def build_page_packet(frame_idx: int, total_frames: int, delay: int, page_idx: int, chunk: bytes) -> bytes:
    p = bytearray(64)
    p[0] = 0x25
    p[1] = frame_idx
    p[2] = total_frames
    p[3] = delay & 0xFF
    p[4] = page_idx & 0xFF
    p[5] = (page_idx >> 8) & 0xFF
    p[6] = len(chunk)
    checksum7(p)
    p[8 : 8 + len(chunk)] = chunk
    return bytes(p)


def execute_upload(
    dev: HidrawDevice,
    frames: List[bytes],
    delay: int,
    mode: str = "vendor",
    progress_cb=None,
    dry_run: bool = False,
) -> bool:
    dev_id = dev.read_device_id()
    if dev_id not in VERIFIED_K86_DEVICE_IDS:
        raise RuntimeError(
            f"Dispositivo incompatível ou não reconhecido (ID {dev_id}). "
            f"Este carregador é restrito ao Attack Shark K86 (IDs verificados: {VERIFIED_K86_DEVICE_IDS})."
        )

    if dry_run:
        if progress_cb:
            progress_cb(50, "[DRY-RUN] Simulação concluída (nenhum dado enviado à flash).")
            progress_cb(100, "[DRY-RUN] Pronto.")
        return True

    conflict = check_conflicting_tools()
    if conflict:
        raise RuntimeError(f"O processo '{conflict}' está em execução. Feche-o antes de enviar dados.")

    total_frames = len(frames)
    frame_len = len(frames[0])

    if progress_cb:
        progress_cb(1, "Enviando anúncio (0xA5) para a controladora...")

    if mode == "stream":
        stream_data = b"".join(f.ljust(FRAME_STRIDE, b"\x00") for f in frames)
        ann_pkt = build_announce_packet(0, total_frames, delay, len(stream_data))
    else:
        ann_pkt = build_announce_packet(0, total_frames, delay, frame_len)

    ready = False
    for _ in range(12):
        reply = dev.roundtrip(ann_pkt, timeout_s=0.2)
        if reply and reply[0] == 0xA5 and reply[1] == 1:
            ready = True
            break
        time.sleep(0.1)

    if not ready:
        raise RuntimeError("A tela do teclado não respondeu com o sinal de confirmação (ready).")

    if mode == "stream":
        total_pages = (len(stream_data) + PAGE_DATA_LEN - 1) // PAGE_DATA_LEN
        pages_sent = 0
        for i in range(0, len(stream_data), PAGE_DATA_LEN):
            chunk = stream_data[i : i + PAGE_DATA_LEN]
            page_idx = i // PAGE_DATA_LEN
            pkt = build_page_packet(0, total_frames, delay, page_idx, chunk)
            dev.send_feature(pkt)
            pages_sent += 1
            time.sleep(0.004)
            if progress_cb:
                pct = (pages_sent / total_pages) * 98.0
                progress_cb(pct, f"Transmitindo dados ({pages_sent}/{total_pages} pacotes)...")
    else:
        total_pages = total_frames * ((frame_len + PAGE_DATA_LEN - 1) // PAGE_DATA_LEN)
        pages_sent = 0
        for frame_idx, frame_data in enumerate(frames):
            frame_pages = (len(frame_data) + PAGE_DATA_LEN - 1) // PAGE_DATA_LEN
            for p in range(frame_pages):
                chunk = frame_data[p * PAGE_DATA_LEN : (p + 1) * PAGE_DATA_LEN]
                pkt = build_page_packet(frame_idx, total_frames, delay, p, chunk)
                dev.send_feature(pkt)
                pages_sent += 1
                time.sleep(0.004)

            if progress_cb:
                pct = (pages_sent / total_pages) * 98.0
                progress_cb(pct, f"Gravando quadro {frame_idx + 1} de {total_frames}...")

    if progress_cb:
        progress_cb(99, "Sincronizando memória flash do teclado...")
    time.sleep(1.2)
    if progress_cb:
        progress_cb(100, "Concluído com sucesso!")
    return True


# ==============================================================================
# GERENCIADOR ASSÍNCRONO EM BACKGROUND (K86DeviceManager)
# ==============================================================================
class K86DeviceManager:
    """
    Singleton-style background worker that caches K86 status, saved screen metadata,
    and hardware settings in memory so UI/IPC calls return in < 0.1 ms without blocking on USB I/O.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._status: Dict[str, Any] = {
            "connected": False,
            "node": None,
            "vid_pid": None,
            "name": "Attack Shark K86",
            "dev_id": 1168,
            "conflict": None,
            "conn_type": "cable",
            "display_fw": None,
        }
        self._last_sysfs: Optional[Tuple[str, str, str, str]] = None
        self._settings: Optional[Dict[str, Any]] = None
        self._screen_info: Dict[str, Any] = load_current_screen_info()
        self._is_uploading: bool = False
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._cmd_queue: "queue.Queue[Tuple[str, Dict[str, Any], Optional[Callable[[Dict[str, Any]], None]]]]" = (
            queue.Queue()
        )

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def set_uploading(self, uploading: bool) -> None:
        with self._lock:
            self._is_uploading = uploading

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def get_current_screen(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._screen_info)

    def update_saved_screen(
        self,
        file_name: str,
        pil_frames: List[Image.Image],
        delay: int,
        fit_mode: str,
        display_fw: Optional[str],
    ) -> Dict[str, Any]:
        saved = save_current_screen_info(
            file_name=file_name,
            pil_frames=pil_frames,
            delay=delay,
            fit_mode=fit_mode,
            display_fw=display_fw,
        )
        with self._lock:
            self._screen_info = saved
            return dict(self._screen_info)

    def clear_saved_screen(self) -> Dict[str, Any]:
        clear_current_screen_info()
        with self._lock:
            fw = self._status.get("display_fw")
            self._screen_info = load_current_screen_info(dev_display_fw=fw)
            return dict(self._screen_info)

    def get_settings(
        self,
        force_refresh: bool = False,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            cached = copy.deepcopy(self._settings) if self._settings is not None else None

        if cached is not None and not force_refresh:
            if callback:
                callback(cached)
            return cached

        self._cmd_queue.put(("get_settings", {}, callback))
        return cached

    def submit_action(
        self,
        action: str,
        data: Dict[str, Any],
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self._cmd_queue.put((action, data, callback))

    def _poll_device_once(self) -> None:
        with self._lock:
            if self._is_uploading:
                return
            prev_sysfs = self._last_sysfs
            prev_connected = self._status.get("connected", False)

        conflict = check_conflicting_tools()
        sysfs_info = scan_keyboard_sysfs()

        if sysfs_info is None:
            with self._lock:
                self._last_sysfs = None
                self._settings = None
                self._status = {
                    "connected": False,
                    "node": None,
                    "vid_pid": None,
                    "name": "Attack Shark K86",
                    "dev_id": 1168,
                    "conflict": conflict,
                    "conn_type": "cable",
                    "display_fw": None,
                }
            return

        node, vid_pid, name, conn_type = sysfs_info

        # If already connected to the exact same sysfs node and the device node still exists,
        # avoid reopening /dev/hidrawX or sending USB feature reports on routine status polls.
        if prev_connected and prev_sysfs == sysfs_info and os.path.exists(node):
            with self._lock:
                self._status["conflict"] = conflict
            return

        dev_id = 1168
        display_fw = None
        settings = None
        try:
            dev = HidrawDevice(node)
            try:
                read_id = dev.read_device_id()
                if read_id:
                    dev_id = read_id
                if conn_type == "cable":
                    display_fw = dev.read_display_firmware_version()
                settings = read_keyboard_settings(dev, dev_id)
            finally:
                dev.close()
        except Exception:
            pass

        id_label = f" [ID: {dev_id}]" if dev_id else ""
        with self._lock:
            self._last_sysfs = sysfs_info
            if settings is not None:
                self._settings = settings
            self._status = {
                "connected": True,
                "node": node,
                "vid_pid": vid_pid,
                "name": f"{name}{id_label}",
                "dev_id": dev_id,
                "conflict": conflict,
                "conn_type": conn_type,
                "display_fw": display_fw,
            }
            if display_fw:
                self._screen_info["display_fw"] = display_fw

    def _execute_command(
        self,
        action: str,
        data: Dict[str, Any],
        callback: Optional[Callable[[Dict[str, Any]], None]],
    ) -> None:
        with self._lock:
            connected = self._status.get("connected", False)
            node = self._status.get("node")
            dev_id = self._status.get("dev_id") or 1168
            cached_settings = copy.deepcopy(self._settings)

        if not connected or not node or not os.path.exists(node):
            self._poll_device_once()
            with self._lock:
                connected = self._status.get("connected", False)
                node = self._status.get("node")
                dev_id = self._status.get("dev_id") or 1168
                cached_settings = copy.deepcopy(self._settings)

        if action == "get_settings":
            if not connected or not node:
                return
            try:
                dev = HidrawDevice(node)
                try:
                    settings = read_keyboard_settings(dev, dev_id)
                finally:
                    dev.close()
                with self._lock:
                    self._settings = settings
                if callback:
                    callback(copy.deepcopy(settings))
            except Exception:
                if cached_settings is not None and callback:
                    callback(cached_settings)
            return

        if not connected or not node:
            if callback:
                callback({"success": False, "message": "Teclado não conectado"})
            return

        try:
            dev = HidrawDevice(node)
            try:
                if action == "set_clock":
                    sync_clock(dev)
                    now_str = datetime.datetime.now().strftime("%H:%M:%S")
                    if callback:
                        callback({"success": True, "message": f"Relógio da telinha sincronizado ({now_str})!"})

                elif action == "set_debounce":
                    val = int(data.get("value", 3))
                    write_debounce(dev, dev_id, val)
                    with self._lock:
                        if self._settings is not None:
                            self._settings["debounce"] = val
                    if callback:
                        callback({"success": True, "message": f"Debounce configurado para {val} ms."})

                elif action == "set_options":
                    write_options(dev, dev_id, data)
                    time.sleep(0.04)
                    if "led_off" in data:
                        led_cache = cached_settings.get("led") if cached_settings else None
                        write_main_light(dev, dev_id, enabled=not data.get("led_off"), cached_led=led_cache)
                        time.sleep(0.04)
                    if "side_led_off" in data:
                        write_side_light(dev, dev_id, enabled=not data.get("side_led_off"))
                    with self._lock:
                        if self._settings is not None and "options" in self._settings:
                            for k in ("win_lock", "mac_mode", "wasd_swap", "led_off", "side_led_off"):
                                if k in data:
                                    self._settings["options"][k] = bool(data[k])
                    if callback:
                        callback({"success": True, "message": "Interruptores de hardware atualizados!"})

                elif action == "set_sleep":
                    rf = int(data.get("rf_sleep", 180))
                    bt = int(data.get("bt_sleep", 180))
                    drf = int(data.get("rf_deep", 1200))
                    dbt = int(data.get("bt_deep", 1200))
                    write_sleep_times(dev, dev_id, bt, rf, dbt, drf)
                    with self._lock:
                        if self._settings is not None:
                            self._settings["sleep"] = {
                                "bt_sleep": bt,
                                "rf_sleep": rf,
                                "bt_deep": dbt,
                                "rf_deep": drf,
                            }
                    if callback:
                        callback({"success": True, "message": "Temporizadores de suspensão salvos!"})

                elif action == "set_led":
                    mode = int(data.get("mode", 4))
                    speed = int(data.get("speed", 2))
                    brightness = int(data.get("brightness", 4))
                    rainbow = bool(data.get("rainbow", False))
                    rgb = list(data.get("rgb", [0, 255, 255]))
                    write_led_param(dev, dev_id, mode, speed, brightness, rainbow, rgb)
                    with self._lock:
                        if self._settings is not None:
                            self._settings["led"] = {
                                "mode": mode,
                                "speed": speed,
                                "brightness": brightness,
                                "rainbow": rainbow,
                                "rgb": rgb,
                            }
                            if "options" in self._settings:
                                self._settings["options"]["led_off"] = brightness == 0
                    if callback:
                        callback({"success": True, "message": "Iluminação RGB aplicada!"})

                elif action == "set_side_led":
                    mode = int(data.get("mode", 1))
                    speed = int(data.get("speed", 2))
                    brightness = int(data.get("brightness", 4))
                    rainbow = bool(data.get("rainbow", False))
                    rgb = list(data.get("rgb", [0, 255, 255]))
                    write_sled_param(dev, dev_id, mode, speed, brightness, rainbow, rgb)
                    with self._lock:
                        if self._settings is not None:
                            self._settings["sled"] = {
                                "mode": mode,
                                "speed": speed,
                                "brightness": brightness,
                                "rainbow": rainbow,
                                "rgb": rgb,
                            }
                            if "options" in self._settings:
                                self._settings["options"]["side_led_off"] = mode == 0 or brightness == 0
                    if callback:
                        callback({"success": True, "message": "LEDs laterais atualizados!"})

                elif action == "factory_reset":
                    write_factory_reset(dev, dev_id)
                    with self._lock:
                        self._settings = None
                    if callback:
                        callback({"success": True, "message": "Comando de restauração de fábrica enviado!"})
            finally:
                dev.close()
        except Exception as e:
            if callback:
                callback({"success": False, "message": f"Erro de comunicação USB: {e}"})

    def _worker_loop(self) -> None:
        self._poll_device_once()
        last_poll = time.perf_counter()

        while True:
            with self._lock:
                if not self._running:
                    break
                uploading = self._is_uploading

            if uploading:
                time.sleep(0.1)
                continue

            try:
                action, data, callback = self._cmd_queue.get(timeout=0.4)
                self._execute_command(action, data, callback)
            except queue.Empty:
                pass

            now = time.perf_counter()
            if now - last_poll >= 2.0:
                self._poll_device_once()
                last_poll = time.perf_counter()


k86_manager = K86DeviceManager()
