"""Photobox : aperçu caméra, photo seule ou série de 4, impression CUPS,
partage par QR code et portail captif qui ouvre la galerie."""
import json
import queue
import re
import secrets
import string
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import wraps

import qrcode
import qrcode.image.svg
from flask import (Flask, Response, abort, jsonify, redirect, render_template, request,
                   send_from_directory)
from PIL import Image

import config
import settings
from camera import Camera
from printer import grid_layout, print_session

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # upload de l'image de fond
config.PHOTO_DIR.mkdir(parents=True, exist_ok=True)
camera = Camera()
encoder = ThreadPoolExecutor(max_workers=2)  # encodage JPEG en arrière-plan

ID_RE = re.compile(r"^[a-z0-9]{8}$")
NAME_RE = re.compile(r"^(\d|montage)\.jpg$")
THUMB_SIZE = (640, 640)

sessions: dict[str, dict] = {}       # séances en cours de prise de vue
print_counts: dict[str, int] = {}
listeners: list[queue.Queue] = []
portal_accepted: set[str] = set()    # IP des téléphones ayant fermé le portail
lock = threading.Lock()


# ---------------------------------------------------------------- utilitaires
def base_url():
    port = "" if config.PORT == 80 else f":{config.PORT}"
    return f"http://{config.HOTSPOT_IP}{port}"


def qr_svg(data: str) -> str:
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, border=1)
    return img.to_string(encoding="unicode")


def wifi_qr_payload():
    esc = lambda s: re.sub(r'([\;,":])', r"\\\1", s)  # noqa: E731
    if config.WIFI_PASSWORD:
        return f"WIFI:T:WPA;S:{esc(config.WIFI_SSID)};P:{esc(config.WIFI_PASSWORD)};;"
    return f"WIFI:T:nopass;S:{esc(config.WIFI_SSID)};;"


def find_session(pid):
    """Dossier d'une séance terminée : photos/<date>_<id>/ (1.jpg… montage.jpg thumb.jpg)."""
    if not ID_RE.match(pid):
        abort(404)
    for d in config.PHOTO_DIR.glob(f"*_{pid}"):
        if (d / "thumb.jpg").exists():
            return d
    abort(404)


def session_info(d):
    pid = d.name.rsplit("_", 1)[1]
    shots = sorted(p.name for p in d.glob("[0-9].jpg"))
    cover = "montage.jpg" if (d / "montage.jpg").exists() else "1.jpg"
    return {
        "id": pid,
        "cover": f"/photos/{d.name}/{cover}",
        "cover_name": cover,
        "thumb": f"/photos/{d.name}/thumb.jpg",
        "shots": [{"name": s, "src": f"/photos/{d.name}/{s}"} for s in shots],
    }


def all_sessions(limit=300):
    dirs = sorted((d for d in config.PHOTO_DIR.iterdir()
                   if d.is_dir() and (d / "thumb.jpg").exists()), reverse=True)
    return [session_info(d) for d in dirs[:limit]]


def local_only(f):
    """Commandes réservées à l'écran du Pi : les téléphones du hotspot n'y ont pas accès."""
    @wraps(f)
    def wrapper(*a, **kw):
        if request.remote_addr not in ("127.0.0.1", "::1"):
            abort(403)
        return f(*a, **kw)
    return wrapper


def broadcast(event):
    for q in list(listeners):
        q.put(event)


# ---------------------------------------------------------------- portail captif
# Le DNS du hotspot renvoie *tous* les domaines vers le Pi. Les tests de connectivité des
# téléphones (connectivitycheck.gstatic.com, captive.apple.com, msftconnecttest.com…) arrivent
# donc ici : on répond par une redirection, le téléphone conclut à un portail captif et
# affiche « Se connecter au réseau » → la galerie s'ouvre.
OWN_HOSTS = {config.HOTSPOT_IP, "localhost", "127.0.0.1", "photobox.lan"}


def probe_success():
    p = request.path.lower()
    if "generate_204" in p or "gen_204" in p:
        return "", 204
    if "hotspot-detect" in p or "success.html" in p or request.host.endswith("apple.com"):
        return "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"
    if p.endswith("connecttest.txt"):
        return "Microsoft Connect Test"
    if p.endswith("ncsi.txt"):
        return "Microsoft NCSI"
    if p.endswith("success.txt"):
        return "success\n"
    return "", 204


@app.before_request
def captive_portal():
    if not config.CAPTIVE_PORTAL:
        return None
    host = request.host.split(":")[0].lower()
    if host in OWN_HOSTS:
        return None
    if request.remote_addr in portal_accepted:
        return probe_success()
    return redirect(f"{base_url()}/portail", 302)


@app.get("/portail")
def portal():
    return render_template("gallery.html", items=all_sessions(), portal=True)


@app.post("/portail/ok")
def portal_ok():
    # Après ça, les tests de connectivité réussissent : iOS affiche « OK »,
    # Android ferme la fenêtre du portail. Le téléphone reste connecté au Wi-Fi.
    portal_accepted.add(request.remote_addr)
    return jsonify(ok=True)


# ---------------------------------------------------------------- kiosque (écran du Pi)
@app.get("/")
def kiosk():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return redirect("/galerie")  # un téléphone qui ouvre http://10.42.0.1/
    st = settings.all_values()
    return render_template(
        "kiosk.html",
        cfg={
            "countdown": st["countdown"],
            "stripCountdown": st["strip_countdown"],
            "stripShots": config.STRIP_SHOTS,
            "defaultMode": st["default_mode"],
            "resultTimeout": st["result_timeout"],
        },
        st=st,
        bg_version=settings.background_version(),
        strip_shots=config.STRIP_SHOTS,
        print_enabled=st["print_enabled"],
        wifi_qr=qr_svg(wifi_qr_payload()),
        ssid=config.WIFI_SSID,
        password=config.WIFI_PASSWORD,
        captive=config.CAPTIVE_PORTAL,
    )


@app.get("/stream.mjpg")
@local_only
def stream():
    def gen():
        for frame in camera.frames():
            yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                   + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-cache"})


@app.post("/api/session")
@local_only
def api_session():
    mode = (request.get_json(silent=True) or {}).get("mode") or settings.get("default_mode")
    total = config.STRIP_SHOTS if mode == "strip" else 1
    pid = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    folder = config.PHOTO_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_{pid}"
    folder.mkdir()
    with lock:
        sessions[pid] = {"dir": folder, "mode": mode, "total": total, "images": [], "jobs": []}
    return jsonify(id=pid, shots=total)


def _save(img, path, **kw):
    img.save(path, "JPEG", quality=config.JPEG_QUALITY, **kw)


@app.post("/api/session/<pid>/shot")
@local_only
def api_shot(pid):
    s = sessions.get(pid) or abort(404)
    if len(s["images"]) >= s["total"]:
        abort(409)
    img = camera.capture_image()            # quelques ms : on rend la main tout de suite
    s["images"].append(img)
    n = len(s["images"])
    s["jobs"].append(encoder.submit(_save, img, s["dir"] / f"{n}.jpg"))
    return jsonify(n=n, total=s["total"])


@app.post("/api/session/<pid>/finish")
@local_only
def api_finish(pid):
    with lock:
        s = sessions.pop(pid, None)
    if not s or not s["images"]:
        abort(404)
    folder, images = s["dir"], s["images"]
    if s["mode"] == "strip" and len(images) > 1:
        cover = grid_layout(images)
        _save(cover, folder / "montage.jpg", dpi=(300, 300))
    else:
        cover = images[0]
    thumb = cover.copy()
    thumb.thumbnail(THUMB_SIZE, Image.BICUBIC)
    for job in s["jobs"]:
        job.result()                        # attend la fin de l'encodage des photos
    _save(thumb, folder / "thumb.jpg")      # en dernier : marque la séance comme terminée
    info = session_info(folder)
    url = f"{base_url()}/p/{pid}"
    return jsonify(id=pid, image=info["cover"], url=url, qr=qr_svg(url))


@app.post("/api/print/<pid>")
@local_only
def api_print(pid):
    if not settings.get("print_enabled"):
        abort(404)
    folder = find_session(pid)
    max_prints = settings.get("max_prints")
    if print_counts.get(pid, 0) >= max_prints:
        return jsonify(ok=False, error="Nombre maximum d'impressions atteint"), 429
    try:
        job = print_session(folder)
    except Exception as e:
        app.logger.exception("impression")
        return jsonify(ok=False, error=str(e)), 500
    print_counts[pid] = print_counts.get(pid, 0) + 1
    return jsonify(ok=True, job=job, remaining=max_prints - print_counts[pid])


@app.get("/events")
@local_only
def events():
    """Server-Sent Events : le bouton GPIO déclenche la photo sur le kiosque."""
    q = queue.Queue()
    listeners.append(q)

    def gen():
        try:
            while True:
                try:
                    yield f"data: {json.dumps(q.get(timeout=15))}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            listeners.remove(q)
    return Response(gen(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------- réglages (écran du Pi)
@app.get("/reglages")
@local_only
def settings_page():
    return render_template("settings.html", st=settings.all_values(),
                           bg_version=settings.background_version(),
                           strip_shots=config.STRIP_SHOTS,
                           saved=request.args.get("ok") == "1", errors={})


@app.post("/reglages")
@local_only
def settings_save():
    errors = settings.update(request.form)
    upload = request.files.get("bg_image")
    if not errors and upload and upload.filename:
        try:
            settings.save_background(upload.stream)
        except Exception as e:
            errors["bg_image"] = f"image illisible ({e.__class__.__name__})"
    if not errors and request.form.get("bg_delete") == "1":
        settings.delete_background()
    if errors:
        # on réaffiche ce qui a été saisi pour ne rien perdre
        st = settings.all_values() | {k: v for k, v in request.form.items() if k in settings.SCHEMA}
        st["print_enabled"] = "print_enabled" in request.form
        return render_template("settings.html", st=st, errors=errors, saved=False,
                               bg_version=settings.background_version(),
                               strip_shots=config.STRIP_SHOTS), 400
    return redirect("/reglages?ok=1", 303)


@app.post("/reglages/reset")
@local_only
def settings_reset():
    settings.reset()
    return redirect("/reglages?ok=1", 303)


@app.get("/reglages/fond.jpg")
@local_only
def settings_background():
    p = settings.background_path()
    if not p.exists():
        abort(404)
    return send_from_directory(p.parent, p.name, max_age=31536000)  # URL versionnée ?v=


# ---------------------------------------------------------------- invités (téléphones)
@app.get("/p/<pid>")
def photo_page(pid):
    info = session_info(find_session(pid))
    return render_template("photo.html", s=info, gallery=config.PUBLIC_GALLERY)


@app.get("/dl/<pid>/<name>")
def download(pid, name):
    folder = find_session(pid)
    if not NAME_RE.match(name):
        abort(404)
    return send_from_directory(folder, name, as_attachment=True,
                               download_name=f"photobox-{folder.name}-{name}")


@app.get("/photos/<folder>/<name>")
def photo_file(folder, name):
    return send_from_directory(config.PHOTO_DIR / folder, name, max_age=3600)


@app.get("/galerie")
def gallery():
    if not config.PUBLIC_GALLERY:
        abort(404)
    return render_template("gallery.html", items=all_sessions(), portal=False)


@app.get("/api/gallery")
def api_gallery():
    if not config.PUBLIC_GALLERY:
        abort(404)
    return jsonify(all_sessions())


# ---------------------------------------------------------------- bouton GPIO
def start_gpio():
    if config.GPIO_BUTTON_PIN < 0:
        return
    try:
        from gpiozero import Button
        btn = Button(config.GPIO_BUTTON_PIN, bounce_time=0.15)
    except Exception as e:
        print(f"[gpio] bouton désactivé ({e!r})")
        return
    btn.when_pressed = lambda: broadcast({"type": "trigger"})
    app.config["gpio_button"] = btn  # garder une référence
    print(f"[gpio] bouton sur GPIO{config.GPIO_BUTTON_PIN}")


if __name__ == "__main__":
    start_gpio()
    print(f"[photobox] kiosque : http://localhost:{config.PORT}/  —  invités : {base_url()}/galerie")
    app.run(host="0.0.0.0", port=config.PORT, threaded=True)
