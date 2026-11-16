"""Configuration de la photobox. Chaque valeur peut être surchargée par une variable
d'environnement PHOTOBOX_<NOM> (ex : PHOTOBOX_PORT=8000)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _env(name, default, cast=str):
    v = os.environ.get(f"PHOTOBOX_{name}")
    return default if v is None else cast(v)


# --- Serveur web ---
PORT = _env("PORT", 80, int)               # 80 => URL plus courte dans le QR code
HOTSPOT_IP = _env("HOTSPOT_IP", "10.42.0.1")  # IP du Pi sur le hotspot (défaut NetworkManager)

# --- Hotspot Wi-Fi (doit correspondre à deploy/hotspot.sh) ---
WIFI_SSID = _env("WIFI_SSID", "Photobox")
WIFI_PASSWORD = _env("WIFI_PASSWORD", "")  # "" => réseau ouvert (sinon 8 caractères min.)

# --- Réglages modifiables depuis l'écran (http://localhost/reglages) ---
# Les valeurs ci-dessous marquées « (réglage) » ne sont que des valeurs par défaut :
# celles enregistrées dans la page de réglages (settings.json) passent devant.
DATA_DIR = Path(_env("DATA_DIR", str(BASE_DIR / "data")))   # image de fond…
SETTINGS_FILE = DATA_DIR / "settings.json"

# --- Écran d'accueil ---
TITLE = _env("TITLE", "Photobox")              # (réglage) titre de l'accueil
BG_MODE = _env("BG_MODE", "camera")            # (réglage) fond : "camera", "color" ou "image"
BG_COLOR = _env("BG_COLOR", "#1b1b2f")         # (réglage) couleur de fond
BG_DIM = _env("BG_DIM", 20, int)               # (réglage) assombrissement de l'image de fond (%)
BTN_COLOR = _env("BTN_COLOR", "#ff4f7b")       # (réglage) bouton principal (mode par défaut, Imprimer)
BTN2_COLOR = _env("BTN2_COLOR", "#333333")     # (réglage) autres boutons (autre mode, Terminé)
BTN_TEXT_COLOR = _env("BTN_TEXT_COLOR", "#ffffff")  # (réglage) texte des boutons

# --- Photos ---
PHOTO_DIR = Path(_env("PHOTO_DIR", str(BASE_DIR / "photos")))
COUNTDOWN = _env("COUNTDOWN", 3, int)          # (réglage) secondes avant la 1re photo
STRIP_SHOTS = _env("STRIP_SHOTS", 4, int)      # nombre de photos du mode "4 photos"
STRIP_COUNTDOWN = _env("STRIP_COUNTDOWN", 2, int)  # (réglage) secondes entre deux photos du mode 4 photos
DEFAULT_MODE = _env("DEFAULT_MODE", "strip")   # (réglage) mode du bouton GPIO / barre d'espace : "single" ou "strip"
RESULT_TIMEOUT = _env("RESULT_TIMEOUT", 45, int)  # (réglage) retour à l'accueil (s)
PUBLIC_GALLERY = _env("PUBLIC_GALLERY", "1") == "1"  # page /galerie accessible aux invités
# Portail captif : à la connexion au Wi-Fi, le téléphone affiche « Se connecter au réseau »
# et ouvre directement la galerie. Nécessite deploy/hotspot.sh (DNS qui renvoie tout vers le Pi).
CAPTIVE_PORTAL = _env("CAPTIVE_PORTAL", "1") == "1"

# --- Caméra (Picamera2) ---
# 2304x1296 = mode binné de la Camera Module 3 : rapide, ~3 MP, largement assez pour un 10x15.
CAPTURE_SIZE = (2304, 1296)
PREVIEW_SIZE = (1280, 720)
JPEG_QUALITY = 92

# --- Impression (CUPS) ---
PRINT_ENABLED = _env("PRINT_ENABLED", "1") == "1"  # (réglage)
PRINTER = _env("PRINTER", "")          # "" => imprimante par défaut de CUPS (lpstat -d)
PRINT_OPTIONS = ["-o", "fit-to-page"]  # ex. Selphy + gutenprint : ["-o", "media=Postcard"]
PRINT_SIZE_PX = (1800, 1200)           # 10x15 cm (6x4") à 300 dpi, paysage
PRINT_FOOTER = _env("PRINT_FOOTER", "Photobox · {date}")  # (réglage) "" => pas de bandeau
MAX_PRINTS_PER_PHOTO = _env("MAX_PRINTS_PER_PHOTO", 2, int)  # (réglage)

# --- Bouton physique optionnel (GPIO, numérotation BCM) ---
GPIO_BUTTON_PIN = _env("GPIO_BUTTON_PIN", 17, int)  # -1 pour désactiver
