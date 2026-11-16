"""Réglages modifiables depuis l'écran du Pi (page /reglages), enregistrés dans settings.json.

Les valeurs par défaut viennent de config.py (donc aussi des variables PHOTOBOX_*) ;
settings.json ne contient que ce qui a été modifié dans la page de réglages.
"""
import json
import os
import re
import threading

from PIL import Image, ImageOps

import config

BG_MAX_SIZE = (2560, 1440)
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _int(lo, hi):
    def cast(v):
        v = int(v)
        if not lo <= v <= hi:
            raise ValueError(f"doit être entre {lo} et {hi}")
        return v
    return cast


def _text(maxlen):
    def cast(v):
        return str(v).strip()[:maxlen]
    return cast


def _choice(*opts):
    def cast(v):
        if v not in opts:
            raise ValueError(f"valeur inconnue : {v}")
        return v
    return cast


def _bool(v):
    return v in (True, "1", "on", "true", 1)


def _color(v):
    if not COLOR_RE.match(v):
        raise ValueError("couleur invalide")
    return v.lower()


# nom -> (conversion/validation, valeur par défaut)
SCHEMA = {
    # Accueil
    "title": (_text(60), config.TITLE),
    "bg_mode": (_choice("camera", "color", "image"), config.BG_MODE),
    "bg_color": (_color, config.BG_COLOR),
    "bg_dim": (_int(0, 80), config.BG_DIM),           # % d'assombrissement de l'image de fond
    "btn_color": (_color, config.BTN_COLOR),
    "btn2_color": (_color, config.BTN2_COLOR),
    "btn_text_color": (_color, config.BTN_TEXT_COLOR),
    # Prise de vue
    "countdown": (_int(1, 15), config.COUNTDOWN),
    "strip_countdown": (_int(1, 15), config.STRIP_COUNTDOWN),
    "default_mode": (_choice("single", "strip"), config.DEFAULT_MODE),
    "result_timeout": (_int(10, 600), config.RESULT_TIMEOUT),
    # Impression
    "print_enabled": (_bool, config.PRINT_ENABLED),
    "max_prints": (_int(1, 10), config.MAX_PRINTS_PER_PHOTO),
    "print_footer": (_text(80), config.PRINT_FOOTER),
}

_lock = threading.Lock()
_values: dict = {}


def _load():
    try:
        data = json.loads(config.SETTINGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        print(f"[settings] {config.SETTINGS_FILE} illisible ({e!r}) -> valeurs par défaut")
        return {}
    out = {}
    for k, v in data.items():
        if k in SCHEMA:
            try:
                out[k] = SCHEMA[k][0](v)
            except (TypeError, ValueError):
                pass
    return out


def _write(values):
    config.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, config.SETTINGS_FILE)  # écriture atomique


def get(key):
    with _lock:
        return _values.get(key, SCHEMA[key][1])


def all_values():
    with _lock:
        return {k: _values.get(k, d) for k, (_, d) in SCHEMA.items()}


def update(form) -> dict:
    """Valide et enregistre les champs du formulaire. Renvoie {champ: erreur} (vide si OK).
    Les cases à cocher absentes du formulaire valent False."""
    new, errors = {}, {}
    for key, (cast, default) in SCHEMA.items():
        if cast is _bool:
            raw = form.get(key, "0")
        elif key in form:
            raw = form.get(key)
        else:
            continue
        try:
            new[key] = cast(raw)
        except (TypeError, ValueError) as e:
            errors[key] = str(e)
    if errors:
        return errors
    with _lock:
        _values.update(new)
        # on ne garde dans le fichier que ce qui diffère des valeurs par défaut
        for k in list(_values):
            if _values[k] == SCHEMA[k][1]:
                del _values[k]
        _write(_values)
    return {}


def reset():
    with _lock:
        _values.clear()
        config.SETTINGS_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------------- image de fond
def background_path():
    return config.DATA_DIR / "background.jpg"


def background_version():
    """Change à chaque nouvelle image : évite que Chromium garde l'ancienne en cache."""
    p = background_path()
    return int(p.stat().st_mtime) if p.exists() else 0


def save_background(stream):
    """Vérifie que c'est bien une image, la réduit et l'enregistre en JPEG."""
    with Image.open(stream) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            flat = Image.new("RGB", img.size, "black")
            flat.paste(img, mask=img.getchannel("A"))
            img = flat
        img = img.convert("RGB")
        img.thumbnail(BG_MAX_SIZE, Image.LANCZOS)
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = background_path().with_suffix(".tmp")
        img.save(tmp, "JPEG", quality=90)
        os.replace(tmp, background_path())


def delete_background():
    background_path().unlink(missing_ok=True)


_values.update(_load())
