#!/usr/bin/env bash
# Crée un point d'accès Wi-Fi avec NetworkManager (Raspberry Pi OS Bookworm/Trixie).
# Le Pi prend l'IP 10.42.0.1 et distribue des adresses DHCP aux téléphones.
# Le DNS du hotspot renvoie tous les domaines vers le Pi : les téléphones détectent un
# « portail captif » et ouvrent directement la galerie (désactiver : CAPTIVE=0).
# Usage : sudo ./hotspot.sh [SSID] [MOT_DE_PASSE (8+ caractères, vide = réseau ouvert)] [PAYS]
set -euo pipefail
SSID="${1:-Photobox}"
PSK="${2-souris123}"
COUNTRY="${3:-FR}"
IFACE="${IFACE:-wlan0}"
CAPTIVE="${CAPTIVE:-1}"
CON="photobox-hotspot"

# Sans pays configuré, le Wi-Fi reste bloqué par rfkill.
command -v raspi-config >/dev/null && raspi-config nonint do_wifi_country "$COUNTRY" || true
rfkill unblock wifi || true

nmcli connection delete "$CON" >/dev/null 2>&1 || true
nmcli connection add type wifi ifname "$IFACE" con-name "$CON" ssid "$SSID" \
  autoconnect yes connection.autoconnect-priority 100 \
  802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
  ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled

if [[ -n "$PSK" ]]; then
  nmcli connection modify "$CON" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" \
    wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp
fi
# dnsmasq lancé par NetworkManager en mode "shared" lit ce dossier
DNS_CONF=/etc/NetworkManager/dnsmasq-shared.d/photobox.conf
mkdir -p "$(dirname "$DNS_CONF")"
if [[ "$CAPTIVE" == "1" ]]; then
  cat > "$DNS_CONF" <<CONF
# Photobox : tous les noms de domaine pointent vers le Pi (portail captif)
address=/#/10.42.0.1
CONF
else
  echo "address=/photobox.lan/10.42.0.1" > "$DNS_CONF"
fi

nmcli radio wifi on
nmcli connection up "$CON"
echo "Hotspot « $SSID » actif — le Pi répond sur http://10.42.0.1"
