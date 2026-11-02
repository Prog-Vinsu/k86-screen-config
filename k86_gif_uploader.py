#!/usr/bin/env python3
"""
Attack Shark K86 Screen Uploader & Configurator
Native animated GIF uploader and full hardware settings configurator
for the Attack Shark K86 mechanical keyboard (Linux).

Modo GUI (Nativo): execute sem argumentos para abrir a janela nativa do sistema (GTK3 + WebKit2).
Modo CLI: execute com o caminho do arquivo para envio direto pelo terminal.
"""

import argparse
import base64
import datetime
import fcntl
import glob
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
from typing import List, Optional, Tuple

try:
    from PIL import Image, ImageOps, ImageSequence
except ImportError:
    sys.exit("Erro: Pillow não está instalado. Instale com: pip install pillow ou sudo apt install python3-pil")

__version__ = "1.1.0"

# Constantes do display do K86
SCREEN_W = 240
SCREEN_H = 135
PAGE_DATA_LEN = 56
FRAME_RAW_LEN = SCREEN_W * SCREEN_H * 2  # 64.800 bytes (RGB565)
FRAME_STRIDE = 65536

SUPPORTED_VID_PIDS = [
    ("3151", "4015"),  # K86 Rev 1 (yc3121 / yc500 - ID 1168)
    ("3151", "5002"),  # K86 Rev 2 (yc3123 / gen2 - ID 2730)
]

VERIFIED_K86_DEVICE_IDS = [1168, 2730]

def _ioc(nr: int, ln: int) -> int:
    return (3 << 30) | (ln << 16) | (ord("H") << 8) | nr

HIDIOCSFEATURE_65 = _ioc(0x06, 65)
HIDIOCGFEATURE_65 = _ioc(0x07, 65)


def checksum7(packet: bytearray) -> None:
    packet[7] = (0xFF - (sum(packet[0:7]) & 0xFF)) & 0xFF


def checksum8(packet: bytearray) -> None:
    packet[8] = (0xFF - (sum(packet[0:8]) & 0xFF)) & 0xFF


def check_conflicting_tools() -> Optional[str]:
    for proc in ["sharkfin", "k86_screen"]:
        try:
            res = subprocess.run(["pgrep", "-x", proc], capture_output=True, text=True)
            if res.returncode == 0:
                return proc
        except Exception:
            pass
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

    def roundtrip(self, packet: bytes, timeout_s: float = 0.5) -> Optional[bytes]:
        self.send_feature(packet)
        start = time.time()
        while time.time() - start < timeout_s:
            time.sleep(0.02)
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
        reply = self.roundtrip(p, timeout_s=0.3)
        if reply and reply[0] == 0x8F and len(reply) >= 5:
            if reply[3] == 0xFF and reply[1] == 0 and reply[2] == 0:
                return None
            return int.from_bytes(reply[1:5], "little")
        return None


def find_keyboard_hidraw() -> Optional[Tuple[str, str, str, Optional[int]]]:
    for hidraw_path in glob.glob("/sys/class/hidraw/hidraw*"):
        dev_dir = os.path.join(hidraw_path, "device")
        uevent_file = os.path.join(dev_dir, "uevent")
        if not os.path.exists(uevent_file):
            continue
        try:
            with open(uevent_file, "r") as f:
                uevent = f.read()
        except Exception:
            continue

        matched_id = None
        for vid, pid in SUPPORTED_VID_PIDS:
            if f":{vid.upper()}:{pid.upper()}" in uevent or f"HID_ID=0003:0000{vid}:0000{pid}" in uevent:
                matched_id = f"{vid}:{pid}"
                break

        if not matched_id:
            continue

        desc_file = os.path.join(dev_dir, "report_descriptor")
        if os.path.exists(desc_file):
            try:
                with open(desc_file, "rb") as f:
                    desc = f.read()
                if desc.startswith(b"\x06\xff\xff\x09\x02"):
                    node = "/dev/" + os.path.basename(hidraw_path)
                    name = "Attack Shark K86"
                    for line in uevent.splitlines():
                        if line.startswith("HID_NAME="):
                            name = line.split("=", 1)[1]

                    dev_id = None
                    try:
                        temp_dev = HidrawDevice(node)
                        dev_id = temp_dev.read_device_id()
                        temp_dev.close()
                    except Exception:
                        pass

                    return node, matched_id, name, dev_id
            except Exception:
                continue

    return None


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
    r_deb = dev.roundtrip(bytes(p))
    deb = (r_deb[2] if dev_id == 1168 else r_deb[1]) if r_deb else 3

    # 2. Options
    p = bytearray(64)
    p[0] = 0x86 if dev_id == 1168 else 0x89
    checksum7(p)
    r_opt = dev.roundtrip(bytes(p))
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
    r_slp = dev.roundtrip(bytes(p))
    if r_slp:
        bt_sleep = int.from_bytes(r_slp[1:3], 'little')
        rf_sleep = int.from_bytes(r_slp[3:5], 'little')
        bt_deep = int.from_bytes(r_slp[5:7], 'little')
        rf_deep = int.from_bytes(r_slp[7:9], 'little')
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
    r_led = dev.roundtrip(bytes(p))
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
    r_sled = dev.roundtrip(bytes(p))
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
    r = dev.roundtrip(bytes(p))
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
    img_rgb = img.convert("RGB")
    px = img_rgb.load()
    out = bytearray(FRAME_RAW_LEN)
    idx = 0
    for x in range(SCREEN_W):
        for y in range(SCREEN_H):
            r, g, b = px[x, y]
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
    if dev_id is not None and dev_id not in VERIFIED_K86_DEVICE_IDS:
        raise RuntimeError(
            f"Dispositivo incompatível detectado (ID {dev_id}). "
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
# JANELA NATIVA GTK 3 + WEBKIT2
# ==============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def launch_native_gui(dry_run: bool = False):
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import Gtk, WebKit2, GLib
    except Exception as e:
        print(f"[!] Não foi possível carregar GTK3 / WebKit2GTK nativo: {e}")
        print("[*] Abrindo no modo alternativo seguro de navegador...")
        launch_fallback_browser_gui(dry_run=dry_run)
        return

    ucm = WebKit2.UserContentManager()
    ucm.register_script_message_handler("pybridge")

    win = Gtk.Window(title="Attack Shark K86 Configurator")
    win.set_default_size(700, 840)
    win.set_position(Gtk.WindowPosition.CENTER)

    icon_path = os.path.join(SCRIPT_DIR, "icon.png")
    if os.path.exists(icon_path):
        try:
            win.set_icon_from_file(icon_path)
        except Exception:
            pass

    webview = WebKit2.WebView.new_with_user_content_manager(ucm)
    win.add(webview)

    def eval_js(code: str):
        GLib.idle_add(lambda: webview.evaluate_javascript(code, -1, None, None, None, None, None))

    def on_ipc_message(manager, js_result):
        try:
            raw_val = js_result.get_js_value().to_string()
            data = json.loads(raw_val)
            action = data.get("action")

            if action == "status":
                conflict = check_conflicting_tools()
                dev_info = find_keyboard_hidraw()
                if dev_info:
                    node, vid_pid, name, dev_id = dev_info
                    id_label = f" [ID: {dev_id}]" if dev_id else ""
                    res = {
                        "connected": True,
                        "node": node,
                        "vid_pid": vid_pid,
                        "name": f"{name}{id_label}",
                        "dev_id": dev_id or 1168,
                        "conflict": conflict,
                    }
                else:
                    res = {"connected": False, "conflict": conflict}
                eval_js(f"window.onDeviceStatus({json.dumps(res)});")

            elif action == "get_settings":
                dev_info = find_keyboard_hidraw()
                if not dev_info:
                    eval_js(f"window.onFeedback({json.dumps({'success': False, 'message': 'Teclado não conectado'})});")
                    return
                node, _, _, dev_id = dev_info
                dev = HidrawDevice(node)
                try:
                    settings = read_keyboard_settings(dev, dev_id or 1168)
                    eval_js(f"window.onSettingsLoaded({json.dumps(settings)});")
                finally:
                    dev.close()

            elif action == "set_clock":
                dev_info = find_keyboard_hidraw()
                if not dev_info:
                    eval_js(f"window.onFeedback({json.dumps({'success': False, 'message': 'Teclado não conectado'})});")
                    return
                node, _, _, _ = dev_info
                dev = HidrawDevice(node)
                try:
                    sync_clock(dev)
                    now_str = datetime.datetime.now().strftime("%H:%M:%S")
                    eval_js(f"window.onFeedback({json.dumps({'success': True, 'message': f'Relógio da telinha sincronizado ({now_str})!'})});")
                finally:
                    dev.close()

            elif action == "set_debounce":
                dev_info = find_keyboard_hidraw()
                if not dev_info:
                    eval_js(f"window.onFeedback({json.dumps({'success': False, 'message': 'Teclado não conectado'})});")
                    return
                val = int(data.get("value", 3))
                node, _, _, dev_id = dev_info
                dev = HidrawDevice(node)
                try:
                    write_debounce(dev, dev_id or 1168, val)
                    eval_js(f"window.onFeedback({json.dumps({'success': True, 'message': f'Debounce configurado para {val} ms.'})});")
                finally:
                    dev.close()

            elif action == "set_options":
                dev_info = find_keyboard_hidraw()
                if not dev_info:
                    eval_js(f"window.onFeedback({json.dumps({'success': False, 'message': 'Teclado não conectado'})});")
                    return
                node, _, _, dev_id = dev_info
                dev = HidrawDevice(node)
                try:
                    write_options(dev, dev_id or 1168, data)
                    # Sincroniza também o estado físico das barras laterais via SLEDPARAM 0x08
                    if "side_led_off" in data:
                        write_side_light(dev, dev_id or 1168, enabled=not data.get("side_led_off"))
                    eval_js(f"window.onFeedback({json.dumps({'success': True, 'message': 'Interruptores de hardware atualizados!'})});")
                finally:
                    dev.close()

            elif action == "set_sleep":
                dev_info = find_keyboard_hidraw()
                if not dev_info:
                    eval_js(f"window.onFeedback({json.dumps({'success': False, 'message': 'Teclado não conectado'})});")
                    return
                node, _, _, dev_id = dev_info
                dev = HidrawDevice(node)
                try:
                    rf = int(data.get("rf_sleep", 180))
                    bt = int(data.get("bt_sleep", 180))
                    drf = int(data.get("rf_deep", 1200))
                    dbt = int(data.get("bt_deep", 1200))
                    write_sleep_times(dev, dev_id or 1168, bt, rf, dbt, drf)
                    eval_js(f"window.onFeedback({json.dumps({'success': True, 'message': 'Temporizadores de suspensão salvos!'})});")
                finally:
                    dev.close()

            elif action == "set_led":
                dev_info = find_keyboard_hidraw()
                if not dev_info:
                    eval_js(f"window.onFeedback({json.dumps({'success': False, 'message': 'Teclado não conectado'})});")
                    return
                node, _, _, dev_id = dev_info
                dev = HidrawDevice(node)
                try:
                    mode = int(data.get("mode", 4))
                    speed = int(data.get("speed", 2))
                    brightness = int(data.get("brightness", 4))
                    rainbow = bool(data.get("rainbow", False))
                    rgb = data.get("rgb", [0, 255, 255])
                    write_led_param(dev, dev_id or 1168, mode, speed, brightness, rainbow, rgb)
                    eval_js(f"window.onFeedback({json.dumps({'success': True, 'message': 'Iluminação RGB aplicada!'})});")
                finally:
                    dev.close()
            elif action == "set_side_led":
                dev_info = find_keyboard_hidraw()
                if not dev_info:
                    eval_js(f"window.onFeedback({json.dumps({'success': False, 'message': 'Teclado não conectado'})});")
                    return
                node, _, _, dev_id = dev_info
                dev = HidrawDevice(node)
                try:
                    mode = int(data.get("mode", 1))
                    speed = int(data.get("speed", 2))
                    brightness = int(data.get("brightness", 4))
                    rainbow = bool(data.get("rainbow", False))
                    rgb = data.get("rgb", [0, 255, 255])
                    write_sled_param(dev, dev_id or 1168, mode, speed, brightness, rainbow, rgb)
                    eval_js(f"window.onFeedback({json.dumps({'success': True, 'message': 'LEDs laterais atualizados!'})});")
                finally:
                    dev.close()


            elif action == "factory_reset":
                dev_info = find_keyboard_hidraw()
                if not dev_info:
                    eval_js(f"window.onFeedback({json.dumps({'success': False, 'message': 'Teclado não conectado'})});")
                    return
                node, _, _, dev_id = dev_info
                dev = HidrawDevice(node)
                try:
                    write_factory_reset(dev, dev_id or 1168)
                    eval_js(f"window.onFeedback({json.dumps({'success': True, 'message': 'Comando de restauração de fábrica enviado!'})});")
                finally:
                    dev.close()

            elif action == "inspect":
                b64_data = data.get("image", "").split(",", 1)[-1]
                img_bytes = base64.b64decode(b64_data)
                im = Image.open(io.BytesIO(img_bytes))

                frames = sum(1 for _ in ImageSequence.Iterator(im))
                im.seek(0)
                durations = [f.info.get("duration", 100) for f in ImageSequence.Iterator(im)]
                avg_dur = int(sum(durations) / len(durations)) if durations else 100
                suggested_delay = max(5, min(255, int(avg_dur * 0.5)))

                resp = {
                    "ok": True,
                    "width": im.width,
                    "height": im.height,
                    "frames": frames,
                    "duration": avg_dur,
                    "suggested_delay": suggested_delay,
                }
                eval_js(f"window.onInspectResult({json.dumps(resp)});")

            elif action == "upload":
                b64_data = data.get("image", "").split(",", 1)[-1]
                delay = int(data.get("delay", 40))
                max_frames = int(data.get("max_frames", 60))
                fit_mode = data.get("fit", "crop")

                def run_upload_thread():
                    def send_prog(pct, msg, status="progress"):
                        eval_js(f"window.onUploadProgress({json.dumps({'status': status, 'pct': pct, 'msg': msg})});")

                    try:
                        send_prog(2, "Decodificando arquivo...")
                        img_bytes = base64.b64decode(b64_data)
                        im = Image.open(io.BytesIO(img_bytes))

                        send_prog(6, "Formatando quadros em RGB565 (240x135)...")
                        raw_frames, _, _ = process_frames_from_image(im, max_frames=max_frames, fit_mode=fit_mode)

                        send_prog(10, "Detectando teclado Attack Shark K86...")
                        dev_info = find_keyboard_hidraw()
                        if not dev_info:
                            raise RuntimeError("Teclado K86 não encontrado. Conecte o cabo USB.")

                        hid_node, _, _, _ = dev_info
                        dev = HidrawDevice(hid_node)
                        try:
                            def on_step(pct, text):
                                scaled = 10.0 + (pct * 0.88)
                                send_prog(scaled, text)

                            execute_upload(
                                dev, raw_frames, delay=delay, mode="vendor", progress_cb=on_step, dry_run=dry_run
                            )
                            send_prog(100, "Concluído!", status="done")
                        finally:
                            dev.close()
                    except Exception as err:
                        send_prog(0, str(err), status="error")

                threading.Thread(target=run_upload_thread, daemon=True).start()

            elif action == "open_external":
                url = data.get("url")
                if url:
                    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        except Exception as e:
            print("Erro no tratamento IPC:", e)

    ucm.connect("script-message-received::pybridge", on_ipc_message)
    win.connect("destroy", Gtk.main_quit)

    ui_path = os.path.join(SCRIPT_DIR, "app_ui.html")
    if os.path.exists(ui_path):
        webview.load_uri(f"file://{os.path.abspath(ui_path)}")
    else:
        webview.load_html("<h1>Erro: app_ui.html não encontrado</h1>", "file:///")

    win.show_all()
    Gtk.main()


# ==============================================================================
# FALLBACK SEGURO COM AUTENTICAÇÃO POR TOKEN (CASO WEBKIT2GTK NÃO ESTEJA PRESENTE)
# ==============================================================================
def launch_fallback_browser_gui(dry_run: bool = False):
    import http.server
    import urllib.parse

    token = secrets.token_hex(24)

    class SecureHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def verify_token(self) -> bool:
            auth_header = self.headers.get("X-Auth-Token")
            if auth_header and auth_header == token:
                return True
            parsed = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(parsed.query)
            return q.get("t", [""])[0] == token

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path in ["/", "/index.html"]:
                if not self.verify_token():
                    self.send_error(403, "Token de autenticação inválido.")
                    return
                ui_path = os.path.join(SCRIPT_DIR, "app_ui.html")
                with open(ui_path, "r", encoding="utf-8") as f:
                    content = f.read()
                injected = content.replace("</head>", f"<script>window.__AUTH_TOKEN__ = '{token}';</script></head>")
                body = injected.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            elif path == "/icon.png":
                icon_path = os.path.join(SCRIPT_DIR, "icon.png")
                if os.path.exists(icon_path):
                    with open(icon_path, "rb") as f:
                        b = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                else:
                    self.send_error(404)
            else:
                self.send_error(404)

        def do_POST(self):
            if not self.verify_token():
                self.send_error(403, "Acesso não autorizado.")
                return

            parsed = urllib.parse.urlparse(self.path)
            content_len = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_len)
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}

            def send_json(data):
                b = json.dumps(data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            if parsed.path == "/api/status":
                dev_info = find_keyboard_hidraw()
                conflict = check_conflicting_tools()
                if dev_info:
                    node, vid_pid, name, dev_id = dev_info
                    id_label = f" [ID: {dev_id}]" if dev_id else ""
                    send_json({"connected": True, "node": node, "vid_pid": vid_pid, "name": f"{name}{id_label}", "dev_id": dev_id or 1168, "conflict": conflict})
                else:
                    send_json({"connected": False, "conflict": conflict})

            elif parsed.path == "/api/get_settings":
                dev_info = find_keyboard_hidraw()
                if dev_info:
                    node, _, _, dev_id = dev_info
                    dev = HidrawDevice(node)
                    try:
                        s = read_keyboard_settings(dev, dev_id or 1168)
                        send_json(s)
                    finally:
                        dev.close()
                else:
                    send_json({"error": "not connected"})

            elif parsed.path == "/api/set_clock":
                dev_info = find_keyboard_hidraw()
                if dev_info:
                    dev = HidrawDevice(dev_info[0])
                    try:
                        sync_clock(dev)
                        send_json({"success": True, "message": "Relógio sincronizado!"})
                    finally:
                        dev.close()

            elif parsed.path == "/api/set_debounce":
                dev_info = find_keyboard_hidraw()
                if dev_info:
                    dev = HidrawDevice(dev_info[0])
                    try:
                        write_debounce(dev, dev_info[3] or 1168, int(payload.get("value", 3)))
                        send_json({"success": True, "message": "Debounce salvo!"})
                    finally:
                        dev.close()

            elif parsed.path == "/api/set_options":
                dev_info = find_keyboard_hidraw()
                if dev_info:
                    dev = HidrawDevice(dev_info[0])
                    try:
                        write_options(dev, dev_info[3] or 1168, payload)
                        if "side_led_off" in payload:
                            write_side_light(dev, dev_info[3] or 1168, enabled=not payload.get("side_led_off"))
                        send_json({"success": True, "message": "Opções salvas!"})
                    finally:
                        dev.close()

            elif parsed.path == "/api/set_sleep":
                dev_info = find_keyboard_hidraw()
                if dev_info:
                    dev = HidrawDevice(dev_info[0])
                    try:
                        write_sleep_times(dev, dev_info[3] or 1168, payload.get("bt_sleep", 180), payload.get("rf_sleep", 180), payload.get("bt_deep", 1200), payload.get("rf_deep", 1200))
                        send_json({"success": True, "message": "Temporizadores salvos!"})
                    finally:
                        dev.close()

            elif parsed.path == "/api/set_led":
                dev_info = find_keyboard_hidraw()
                if dev_info:
                    dev = HidrawDevice(dev_info[0])
                    try:
                        write_led_param(dev, dev_info[3] or 1168, payload.get("mode", 4), payload.get("speed", 2), payload.get("brightness", 4), payload.get("rainbow", False), payload.get("rgb", [0, 255, 255]))
                        send_json({"success": True, "message": "Iluminação aplicada!"})
                    finally:
                        dev.close()
            elif parsed.path == "/api/set_side_led":
                dev_info = find_keyboard_hidraw()
                if dev_info:
                    dev = HidrawDevice(dev_info[0])
                    try:
                        write_sled_param(
                            dev,
                            dev_info[3] or 1168,
                            payload.get("mode", 1),
                            payload.get("speed", 2),
                            payload.get("brightness", 4),
                            payload.get("rainbow", False),
                            payload.get("rgb", [0, 255, 255]),
                        )
                        send_json({"success": True, "message": "LEDs laterais aplicados!"})
                    finally:
                        dev.close()


            elif parsed.path == "/api/factory_reset":
                dev_info = find_keyboard_hidraw()
                if dev_info:
                    dev = HidrawDevice(dev_info[0])
                    try:
                        write_factory_reset(dev, dev_info[3] or 1168)
                        send_json({"success": True, "message": "Restauração de fábrica enviada!"})
                    finally:
                        dev.close()

            elif parsed.path == "/api/inspect":
                try:
                    b64_data = payload.get("image", "").split(",", 1)[-1]
                    img_bytes = base64.b64decode(b64_data)
                    im = Image.open(io.BytesIO(img_bytes))
                    frames = sum(1 for _ in ImageSequence.Iterator(im))
                    im.seek(0)
                    durations = [f.info.get("duration", 100) for f in ImageSequence.Iterator(im)]
                    avg_dur = int(sum(durations) / len(durations)) if durations else 100
                    resp = {
                        "ok": True,
                        "width": im.width,
                        "height": im.height,
                        "frames": frames,
                        "duration": avg_dur,
                        "suggested_delay": max(5, min(255, int(avg_dur * 0.5))),
                    }
                except Exception as e:
                    resp = {"ok": False, "error": str(e)}
                send_json(resp)

            elif parsed.path == "/api/upload":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                def sse_event(status: str, pct: float, msg: str):
                    d = json.dumps({"status": status, "pct": pct, "msg": msg})
                    try:
                        self.wfile.write(f"data: {d}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except Exception:
                        pass

                try:
                    b64_data = payload.get("image", "").split(",", 1)[-1]
                    delay = int(payload.get("delay", 40))
                    max_frames = int(payload.get("max_frames", 60))
                    fit_mode = payload.get("fit", "crop")

                    sse_event("progress", 2, "Decodificando imagem...")
                    img_bytes = base64.b64decode(b64_data)
                    im = Image.open(io.BytesIO(img_bytes))

                    sse_event("progress", 6, "Formatando quadros em RGB565 (240x135)...")
                    raw_frames, _, _ = process_frames_from_image(im, max_frames=max_frames, fit_mode=fit_mode)

                    sse_event("progress", 10, "Detectando teclado Attack Shark K86...")
                    dev_info = find_keyboard_hidraw()
                    if not dev_info:
                        raise RuntimeError("Teclado K86 não encontrado. Conecte o cabo USB.")

                    hid_node, _, _, _ = dev_info
                    dev = HidrawDevice(hid_node)
                    try:
                        def on_step(pct, text):
                            scaled = 10.0 + (pct * 0.88)
                            sse_event("progress", scaled, text)

                        execute_upload(dev, raw_frames, delay=delay, mode="vendor", progress_cb=on_step, dry_run=dry_run)
                        sse_event("done", 100, "Concluído!")
                    finally:
                        dev.close()
                except Exception as e:
                    sse_event("error", 0, str(e))

    server = http.server.HTTPServer(("127.0.0.1", 0), SecureHandler)
    port = server.server_port
    url = f"http://127.0.0.1:{port}/?t={token}"

    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/tmp/user_{os.getuid()}")
    profile_dir = os.path.join(runtime_dir, "k86_uploader_browser")

    chrome_bin = shutil.which("google-chrome") or shutil.which("brave-browser") or shutil.which("chromium")
    if chrome_bin:
        subprocess.Popen([
            chrome_bin,
            f"--app={url}",
            "--window-size=700,840",
            f"--user-data-dir={profile_dir}"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        import webbrowser
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


# ==============================================================================
# MODO CLI
# ==============================================================================
def run_cli(args):
    print("=" * 60)
    print("  Attack Shark K86 - Carregador & Configurador (Modo CLI)")
    print("=" * 60)

    found = find_keyboard_hidraw()
    if not found:
        sys.exit("[!] Teclado K86 não encontrado via cabo USB.")
    hid_node, vid_pid, prod_name, dev_id = found
    id_info = f" [ID: {dev_id}]" if dev_id else ""
    print(f"[+] Teclado detectado : {prod_name}{id_info} ({vid_pid}) em {hid_node}")

    if not os.path.exists(args.file):
        sys.exit(f"[!] Arquivo não encontrado: {args.file}")

    im = Image.open(args.file)
    raw_frames, pil_frames, avg_duration = process_frames_from_image(
        im, max_frames=args.max_frames, fit_mode=args.fit, target_step=args.step
    )

    count = len(raw_frames)
    print(f"[+] Total de quadros a enviar : {count}")
    delay = args.delay if args.delay is not None else max(5, min(255, int(avg_duration * 0.5)))
    print(f"[+] Delay por quadro          : {delay}")

    if args.preview:
        out_preview = "k86_preview_240x135.gif" if count > 1 else "k86_preview_240x135.png"
        if count > 1:
            pil_frames[0].save(out_preview, save_all=True, append_images=pil_frames[1:], duration=avg_duration, loop=0)
        else:
            pil_frames[0].save(out_preview)
        print(f"[+] Pré-visualização salva em : {os.path.abspath(out_preview)}")

    dev = HidrawDevice(hid_node)
    try:
        def cli_progress(pct, msg):
            sys.stdout.write(f"\rProgresso: {pct:5.1f}% | {msg}     ")
            sys.stdout.flush()

        execute_upload(dev, raw_frames, delay=delay, mode=args.mode, progress_cb=cli_progress, dry_run=args.dry_run)
        print("\n\n[✓] Sucesso! Operação concluída.")
    finally:
        dev.close()


def main():
    parser = argparse.ArgumentParser(
        description="Attack Shark K86 Screen Uploader & Hardware Configurator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", nargs="?", default=None, help="Caminho do arquivo de imagem/GIF. Se omitido, abre a janela (GUI nativa).")
    parser.add_argument("--gui", action="store_true", help="Força a abertura da interface gráfica nativa.")
    parser.add_argument("--dry-run", action="store_true", help="Executa todo o processamento e verificação de hardware sem gravar na flash.")
    parser.add_argument("--version", action="version", version=f"Attack Shark K86 Configurator {__version__}")
    parser.add_argument("--delay", type=int, default=None, help="Delay/velocidade entre quadros (0-255).")
    parser.add_argument("--max-frames", type=int, default=60, help="Limite máximo de quadros (padrão: 60).")
    parser.add_argument("--step", type=int, default=None, help="Amostragem de quadros.")
    parser.add_argument("--fit", choices=["crop", "contain", "stretch"], default="crop", help="Modo de enquadramento (padrão: crop).")
    parser.add_argument("--mode", choices=["vendor", "stream"], default="vendor", help="Modo de envio (vendor ou stream).")
    parser.add_argument("--preview", action="store_true", help="Gera arquivo de pré-visualização.")

    args = parser.parse_args()

    if args.gui or args.file is None:
        launch_native_gui(dry_run=args.dry_run)
    else:
        run_cli(args)


if __name__ == "__main__":
    main()
