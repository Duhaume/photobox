#!/usr/bin/env bash
# Installation complète sur Raspberry Pi OS (Bookworm/Trixie, version Desktop).
# À lancer depuis le dossier du projet, en tant qu'utilisateur normal : ./deploy/install.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"

echo "==> Paquets"
sudo apt-get update
sudo apt-get install -y python3-picamera2 python3-flask python3-qrcode python3-pil \
  python3-gpiozero cups printer-driver-gutenprint curl fonts-dejavu-core
command -v chromium >/dev/null || command -v chromium-browser >/dev/null \
  || sudo apt-get install -y chromium || sudo apt-get install -y chromium-browser

echo "==> CUPS : droits d'administration pour $USER_NAME"
sudo usermod -aG lpadmin "$USER_NAME"

echo "==> Service systemd"
sudo tee /etc/systemd/system/photobox.service >/dev/null <<UNIT
[Unit]
Description=Photobox
After=network-online.target cups.service
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_DIR/app.py
# Permet d'écouter sur le port 80 sans être root
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=2
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now photobox.service

echo "==> Kiosque au démarrage de la session graphique"
chmod +x "$APP_DIR/deploy/kiosk.sh" "$APP_DIR/deploy/hotspot.sh"
mkdir -p ~/.config/autostart
# Entrée XDG : lue par labwc (via lxsession-xdg-autostart) et par Wayfire
cat > ~/.config/autostart/photobox-kiosk.desktop <<DESK
[Desktop Entry]
Type=Application
Name=Photobox kiosk
Exec=$APP_DIR/deploy/kiosk.sh
DESK

echo "==> Hotspot Wi-Fi"
read -rp "Créer le hotspot maintenant ? (coupe le Wi-Fi client actuel) [o/N] " r
if [[ "$r" =~ ^[oOyY]$ ]]; then
  read -rp "SSID [Photobox] : " ssid; read -rp "Mot de passe (8+ car., vide = ouvert) [souris123] : " psk
  sudo "$APP_DIR/deploy/hotspot.sh" "${ssid:-Photobox}" "${psk-souris123}"
  echo "⚠  Reportez SSID / mot de passe dans config.py (WIFI_SSID / WIFI_PASSWORD)."
fi

echo
echo "Terminé. Ajoutez l'imprimante sur http://localhost:631 (ou lpadmin), puis : sudo reboot"
