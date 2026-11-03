#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
UDEV_RULE_FILE="/etc/udev/rules.d/70-attack-shark-devices.rules"
OLD_UDEV_RULE_FILE="/etc/udev/rules.d/70-attack-shark-k86.rules"

echo "=========================================================="
echo "  Attack Shark K86 Screen Uploader - Instalador Linux"
echo "=========================================================="

# 1. Instalação do Ícone e Desktop Entry
mkdir -p "$APP_DIR"
mkdir -p "$ICON_DIR"

cp "$DIR/icon.png" "$ICON_DIR/attack-shark-k86.png"

DESKTOP_FILE="$APP_DIR/attack-shark-k86.desktop"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Attack Shark K86 Screen
Comment=Carregador de GIFs e imagens para a tela TFT do teclado Attack Shark K86
Exec=python3 "$DIR/k86_gif_uploader.py"
Icon=attack-shark-k86
Terminal=false
Categories=Utility;HardwareSettings;
Keywords=keyboard;attack shark;k86;tft;oled;gif;screen;teclado;
StartupNotify=true
StartupWMClass=k86_gif_uploader
EOF

chmod +x "$DESKTOP_FILE"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi
RULE_CONTENT='# Attack Shark K86 Keyboard
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="3151", ATTRS{idProduct}=="4015|5002", MODE="0660", TAG+="uaccess"
# Attack Shark X11 Mouse (Wireless Dongle & Wired)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1d57", ATTRS{idProduct}=="fa60|fa55", MODE="0660", TAG+="uaccess"'
echo "[✓] Atalho de aplicativo instalado em: $DESKTOP_FILE"
echo ""
if [ -f "$OLD_UDEV_RULE_FILE" ]; then
    if command -v sudo >/dev/null 2>&1; then
        sudo rm -f "$OLD_UDEV_RULE_FILE"
    fi
fi

if [ -f "$UDEV_RULE_FILE" ]; then
    echo "[✓] Atualizando regra udev em $UDEV_RULE_FILE..."
    if [ -t 0 ] && command -v sudo >/dev/null 2>&1; then
        echo "$RULE_CONTENT" | sudo tee "$UDEV_RULE_FILE" >/dev/null
        sudo udevadm control --reload-rules && sudo udevadm trigger
        echo "[✓] Regra udev atualizada!"
    fi
else
    if [ -t 0 ] && command -v sudo >/dev/null 2>&1; then
        echo "Instalando regra udev em $UDEV_RULE_FILE..."
        echo "$RULE_CONTENT" | sudo tee "$UDEV_RULE_FILE" >/dev/null
        sudo udevadm control --reload-rules && sudo udevadm trigger
        echo "[✓] Regra udev instalada com sucesso!"
    else
        echo "[*] Para instalar a regra udev e não precisar de sudo no futuro, rode manualmente:"
        echo "    printf '%s\n' '$RULE_CONTENT' | sudo tee $UDEV_RULE_FILE"
        echo "    sudo udevadm control --reload-rules && sudo udevadm trigger"
    fi
fi

echo ""
echo "=========================================================="
echo "  Instalação concluída com sucesso!"
echo "  Reconecte o cabo USB do teclado para aplicar as permissões."
echo "  Você já pode abrir 'Attack Shark K86 Screen' no seu menu."
echo "=========================================================="
