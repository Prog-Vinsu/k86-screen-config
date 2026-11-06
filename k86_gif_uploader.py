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
import hmac
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import urllib.parse
import time
from typing import List, Optional, Tuple, Dict, Any

import k86_device
from k86_device import *
import x11_mouse

try:
    from PIL import Image, ImageOps, ImageSequence
except ImportError:
    sys.exit("Erro: Pillow não está instalado. Instale com: pip install pillow ou sudo apt install python3-pil")

__version__ = "1.3.0"
def is_safe_external_url(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    u = url.strip()
    if u.startswith("-"):
        return False
    try:
        parsed = urllib.parse.urlparse(u)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def get_loopback_client_uid(client_port: int) -> Optional[int]:
    p_hex = f"{client_port:04X}"
    for proc_file in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(proc_file, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) > 7 and parts[1].endswith(f":{p_hex}"):
                        return int(parts[7])
        except Exception:
            pass
    return None


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

    k86_device.k86_manager.start()
    x11_mouse.mouse_manager.start()

    win = Gtk.Window(title="Attack Shark K86 & X11 Configurator")
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
                res = k86_device.k86_manager.get_status()
                eval_js(f"window.onDeviceStatus({json.dumps(res)});")

            elif action == "get_current_screen":
                info = k86_device.k86_manager.get_current_screen()
                eval_js(f"window.onCurrentScreenLoaded && window.onCurrentScreenLoaded({json.dumps(info)});")

            elif action == "clear_current_screen":
                info = k86_device.k86_manager.clear_saved_screen()
                eval_js(f"window.onCurrentScreenLoaded && window.onCurrentScreenLoaded({json.dumps(info)});")

            elif action == "get_settings":
                k86_device.k86_manager.get_settings(
                    force_refresh=bool(data.get("refresh", False)),
                    callback=lambda s: eval_js(f"window.onSettingsLoaded({json.dumps(s)});") if s else None,
                )

            elif action in (
                "set_clock",
                "set_debounce",
                "set_options",
                "set_sleep",
                "set_led",
                "set_side_led",
                "factory_reset",
            ):
                k86_device.k86_manager.submit_action(
                    action,
                    data,
                    callback=lambda res: eval_js(f"window.onFeedback({json.dumps(res)});"),
                )

            elif action == "inspect":
                b64_data = data.get("image", "").split(",", 1)[-1]

                def run_inspect_thread():
                    try:
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
                    except Exception as err:
                        eval_js(f"window.onInspectResult({json.dumps({'ok': False, 'error': str(err)})});")

                threading.Thread(target=run_inspect_thread, daemon=True).start()

            elif action == "upload":
                b64_data = data.get("image", "").split(",", 1)[-1]
                file_name = data.get("file_name", "animacao.gif")
                delay = int(data.get("delay", 40))
                max_frames = int(data.get("max_frames", 60))
                fit_mode = data.get("fit", "crop")

                def run_upload_thread():
                    def send_prog(pct, msg, status="progress"):
                        eval_js(f"window.onUploadProgress({json.dumps({'status': status, 'pct': pct, 'msg': msg})});")

                    k86_device.k86_manager.set_uploading(True)
                    try:
                        send_prog(2, "Decodificando arquivo...")
                        img_bytes = base64.b64decode(b64_data)
                        im = Image.open(io.BytesIO(img_bytes))

                        send_prog(6, "Formatando quadros em RGB565 (240x135)...")
                        raw_frames, resized_images, _ = process_frames_from_image(
                            im, max_frames=max_frames, fit_mode=fit_mode
                        )

                        send_prog(10, "Detectando teclado Attack Shark K86...")
                        status_info = k86_device.k86_manager.get_status()
                        hid_node = status_info.get("node") if status_info.get("connected") else None
                        if not hid_node or not os.path.exists(hid_node):
                            dev_info = find_keyboard_hidraw()
                            if not dev_info:
                                raise RuntimeError("Teclado K86 não encontrado. Conecte o cabo USB.")
                            hid_node = dev_info[0]

                        dev = HidrawDevice(hid_node)
                        try:
                            def on_step(pct, text):
                                scaled = 10.0 + (pct * 0.88)
                                send_prog(scaled, text)

                            execute_upload(
                                dev, raw_frames, delay=delay, mode="vendor", progress_cb=on_step, dry_run=dry_run
                            )
                            disp_fw = dev.read_display_firmware_version()
                            saved_info = k86_device.k86_manager.update_saved_screen(
                                file_name=file_name,
                                pil_frames=resized_images,
                                delay=delay,
                                fit_mode=fit_mode,
                                display_fw=disp_fw,
                            )
                            eval_js(
                                f"window.onCurrentScreenLoaded && window.onCurrentScreenLoaded({json.dumps(saved_info)});"
                            )
                            send_prog(100, "Concluído!", status="done")
                        finally:
                            dev.close()
                    except Exception as err:
                        send_prog(0, str(err), status="error")
                    finally:
                        k86_device.k86_manager.set_uploading(False)

                threading.Thread(target=run_upload_thread, daemon=True).start()

            elif action == "open_external":
                url = data.get("url")
                if url and is_safe_external_url(url):
                    subprocess.Popen(["xdg-open", url.strip()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            elif action == "mouse_status":
                m_status = x11_mouse.mouse_manager.get_status()
                eval_js(f"window.onMouseStatus && window.onMouseStatus({json.dumps(m_status)});")

            elif action == "mouse_apply_settings":
                cfg = data.get("settings", {})
                x11_mouse.mouse_manager.submit_apply_settings(
                    cfg,
                    lambda ok: eval_js(
                        f"window.onMouseFeedback && window.onMouseFeedback({json.dumps({'success': ok, 'message': 'Configurações do mouse aplicadas!' if ok else 'Erro ao aplicar configurações no mouse.'})});"
                    ),
                )
        except Exception as e:
            print("Erro no tratamento IPC:", e)

    ucm.connect("script-message-received::pybridge", on_ipc_message)
    win.connect("destroy", Gtk.main_quit)
    ui_path = os.path.join(SCRIPT_DIR, "ui", "index.html")
    if os.path.exists(ui_path):
        webview.load_uri(f"file://{os.path.abspath(ui_path)}")
    else:
        webview.load_html("<h1>Erro: ui/index.html não encontrado</h1>", "file:///")
    win.show_all()
    Gtk.main()


# ==============================================================================
# FALLBACK SEGURO COM AUTENTICAÇÃO POR TOKEN (CASO WEBKIT2GTK NÃO ESTEJA PRESENTE)
# ==============================================================================
def launch_fallback_browser_gui(dry_run: bool = False):
    import http.server

    k86_device.k86_manager.start()
    x11_mouse.mouse_manager.start()

    token = secrets.token_hex(24)
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/tmp/user_{os.getuid()}")
    app_runtime_dir = os.path.join(runtime_dir, "attack-shark-k86")
    try:
        os.makedirs(app_runtime_dir, mode=0o700, exist_ok=True)
        token_file = os.path.join(app_runtime_dir, "auth_token")
        with open(os.open(token_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600), "w") as f:
            f.write(token)
    except Exception:
        pass

    class SecureHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def verify_token(self) -> bool:
            auth_header = self.headers.get("X-Auth-Token")
            if auth_header and hmac.compare_digest(auth_header, token):
                return True
            cookie_header = self.headers.get("Cookie", "")
            if cookie_header:
                for c in cookie_header.split(";"):
                    k, _, v = c.strip().partition("=")
                    if k == "k86_auth_token" and hmac.compare_digest(v, token):
                        return True
            parsed = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(parsed.query)
            q_token = q.get("t", [""])[0]
            if q_token and hmac.compare_digest(q_token, token):
                return True
            return False

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path in ["/", "/index.html"]:
                client_port = self.client_address[1]
                client_uid = get_loopback_client_uid(client_port)
                same_user = (client_uid == os.getuid()) if client_uid is not None else False
                if not (same_user or self.verify_token()):
                    self.send_error(403, "Acesso não autorizado.")
                    return
                ui_path = os.path.join(SCRIPT_DIR, "ui", "index.html")
                with open(ui_path, "r", encoding="utf-8") as f:
                    content = f.read()
                injected = content.replace("</head>", f"<script>window.__AUTH_TOKEN__ = '{token}';</script></head>")
                body = injected.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Set-Cookie", f"k86_auth_token={token}; Path=/; SameSite=Strict; HttpOnly")
                self.end_headers()
                self.wfile.write(body)

            else:
                # Servir assets estáticos (CSS, JS, imagens) estritamente de ui/
                rel_path = path.lstrip("/")
                ui_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "ui"))
                target_file = os.path.abspath(os.path.join(ui_dir, rel_path))

                if rel_path == "icon.png" and not os.path.exists(target_file):
                    target_file = os.path.abspath(os.path.join(SCRIPT_DIR, "icon.png"))
                    allowed = True
                else:
                    allowed = os.path.commonpath([target_file, ui_dir]) == ui_dir

                if not allowed:
                    self.send_error(403, "Acesso negado.")
                    return
                if not os.path.isfile(target_file):
                    self.send_error(404, "Arquivo não encontrado.")
                    return

                import mimetypes
                ctype, _ = mimetypes.guess_type(target_file)
                if not ctype:
                    ctype = "application/octet-stream"

                with open(target_file, "rb") as f:
                    b = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

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
                send_json(k86_device.k86_manager.get_status())

            elif parsed.path == "/api/get_current_screen":
                send_json(k86_device.k86_manager.get_current_screen())

            elif parsed.path == "/api/clear_current_screen":
                send_json(k86_device.k86_manager.clear_saved_screen())

            elif parsed.path == "/api/get_settings":
                cached = k86_device.k86_manager.get_settings(force_refresh=bool(payload.get("refresh", False)))
                if cached is not None:
                    send_json(cached)
                else:
                    send_json({"error": "not connected"})

            elif parsed.path in (
                "/api/set_clock",
                "/api/set_debounce",
                "/api/set_options",
                "/api/set_sleep",
                "/api/set_led",
                "/api/set_side_led",
                "/api/factory_reset",
            ):
                act_name = parsed.path[len("/api/") :]
                done_evt = threading.Event()
                result_box = [{"success": False, "message": "Timeout"}]

                def _on_done(res):
                    result_box[0] = res
                    done_evt.set()

                k86_device.k86_manager.submit_action(act_name, payload, callback=_on_done)
                done_evt.wait(timeout=2.0)
                send_json(result_box[0])

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

            elif parsed.path == "/api/mouse_status":
                m_status = x11_mouse.mouse_manager.get_status()
                send_json(m_status)

            elif parsed.path == "/api/mouse_apply_settings":
                cfg = payload.get("settings", {})
                ok = x11_mouse.mouse_manager.apply_settings(cfg)
                send_json(
                    {
                        "success": ok,
                        "message": "Configurações do mouse aplicadas!"
                        if ok
                        else "Erro ao aplicar configurações no mouse.",
                    }
                )

            elif parsed.path == "/api/open_external":
                url = payload.get("url")
                if url and is_safe_external_url(url):
                    subprocess.Popen(["xdg-open", url.strip()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                send_json({"success": True})

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

                k86_device.k86_manager.set_uploading(True)
                try:
                    b64_data = payload.get("image", "").split(",", 1)[-1]
                    delay = int(payload.get("delay", 40))
                    max_frames = int(payload.get("max_frames", 60))
                    fit_mode = payload.get("fit", "crop")

                    sse_event("progress", 2, "Decodificando imagem...")
                    img_bytes = base64.b64decode(b64_data)
                    im = Image.open(io.BytesIO(img_bytes))

                    sse_event("progress", 6, "Formatando quadros em RGB565 (240x135)...")
                    raw_frames, resized_images, _ = process_frames_from_image(
                        im, max_frames=max_frames, fit_mode=fit_mode
                    )

                    sse_event("progress", 10, "Detectando teclado Attack Shark K86...")
                    status_info = k86_device.k86_manager.get_status()
                    hid_node = status_info.get("node") if status_info.get("connected") else None
                    if not hid_node or not os.path.exists(hid_node):
                        dev_info = find_keyboard_hidraw()
                        if not dev_info:
                            raise RuntimeError("Teclado K86 não encontrado. Conecte o cabo USB.")
                        hid_node = dev_info[0]

                    dev = HidrawDevice(hid_node)
                    try:
                        def on_step(pct, text):
                            scaled = 10.0 + (pct * 0.88)
                            sse_event("progress", scaled, text)

                        execute_upload(dev, raw_frames, delay=delay, mode="vendor", progress_cb=on_step, dry_run=dry_run)
                        disp_fw = dev.read_display_firmware_version()
                        k86_device.k86_manager.update_saved_screen(
                            file_name=payload.get("file_name", "animacao.gif"),
                            pil_frames=resized_images,
                            delay=delay,
                            fit_mode=fit_mode,
                            display_fw=disp_fw,
                        )
                        sse_event("done", 100, "Concluído!")
                    finally:
                        dev.close()
                except Exception as e:
                    sse_event("error", 0, str(e))
                finally:
                    k86_device.k86_manager.set_uploading(False)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SecureHandler)
    port = server.server_port
    url = f"http://127.0.0.1:{port}/"

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
    hid_node, vid_pid, prod_name, dev_id, _ = found
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
        if not args.dry_run:
            try:
                disp_fw = dev.read_display_firmware_version()
                save_current_screen_info(
                    file_name=args.file,
                    pil_frames=pil_frames,
                    delay=delay,
                    fit_mode=args.fit,
                    display_fw=disp_fw,
                )
            except Exception:
                pass
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
