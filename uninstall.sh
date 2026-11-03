#!/usr/bin/env bash
set -e

APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
UDEV_RULE_FILE="/etc/udev/rules.d/70-attack-shark-devices.rules"
OLD_UDEV_RULE_FILE="/etc/udev/rules.d/70-attack-shark-k86.rules"
DESKTOP_FILE="$APP_DIR/attack-shark-k86.desktop"
OLD_DESKTOP_FILE="$APP_DIR/k86-screen-uploader.desktop"

echo "=========================================================="
echo "  Attack Shark K86 Screen Uploader - Desinstalador Linux"
echo "=========================================================="

# 1. Remover Desktop Entries
if [ -f "$DESKTOP_FILE" ]; then
    rm -f "$DESKTOP_FILE"
    echo "[✓] Removido: $DESKTOP_FILE"
fi

if [ -f "$OLD_DESKTOP_FILE" ]; then
    rm -f "$OLD_DESKTOP_FILE"
    echo "[✓] Removido: $OLD_DESKTOP_FILE"
fi

if [ -f "$ICON_DIR/attack-shark-k86.png" ]; then
    rm -f "$ICON_DIR/attack-shark-k86.png"
    echo "[✓] Removido ícone do sistema."
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

# 2. Pergunta sobre remoção da regra udev
if [ -f "$UDEV_RULE_FILE" ] || [ -f "$OLD_UDEV_RULE_FILE" ]; then
    echo ""
    read -r -p "Deseja remover as regras udev do Attack Shark? [s/N] " response
    case "$response" in
        [sS][iI][mM]|[sS]|[yY][eE][sS]|[yY])
            if command -v sudo >/dev/null 2>&1; then
                sudo rm -f "$UDEV_RULE_FILE" "$OLD_UDEV_RULE_FILE"
                sudo udevadm control --reload-rules && sudo udevadm trigger
                echo "[✓] Regras udev removidas."
            else
                echo "[!] Execute com permissão root para remover: rm $UDEV_RULE_FILE $OLD_UDEV_RULE_FILE"
            fi
            ;;
        *)
            echo "[*] Regra udev mantida."
            ;;
    esac
fi

echo ""
echo "=========================================================="
echo "  Desinstalação dos atalhos concluída!"
echo "=========================================================="
