"""Caméra : Picamera2 sur le Raspberry Pi, sinon webcam OpenCV, sinon mire de test."""
import io
import threading
import time
from datetime import datetime

import config


class FrameBuffer(io.BufferedIOBase):
    """Reçoit les JPEG du flux d'aperçu et réveille les clients MJPEG."""

    def __init__(self):
        self.frame = None
        self.cond = threading.Condition()

    def write(self, buf):
        with self.cond:
            self.frame = bytes(buf)
            self.cond.notify_all()
        return len(buf)

    def wait(self, timeout=2.0):
        with self.cond:
            self.cond.wait(timeout)
            return self.frame


class PiCamera:
    name = "picamera2"

    def __init__(self, buffer):
        from picamera2 import Picamera2
        from picamera2.encoders import MJPEGEncoder
        from picamera2.outputs import FileOutput

        self.cam = Picamera2()
        # Flux "main" pleine définition pour la photo, "lores" encodé en MJPEG pour l'aperçu.
        cfg = self.cam.create_video_configuration(
            main={"size": config.CAPTURE_SIZE},
            lores={"size": config.PREVIEW_SIZE},
            encode="lores",
            buffer_count=4,
        )
        self.cam.configure(cfg)
        if "AfMode" in self.cam.camera_controls:  # Camera Module 3 : autofocus continu
            self.cam.set_controls({"AfMode": 2})
        self.cam.start_recording(MJPEGEncoder(), FileOutput(buffer))

    def capture_image(self):
        # make_image copie le buffer : on rend la main à la caméra en quelques ms,
        # l'encodage JPEG se fait ensuite en arrière-plan.
        request = self.cam.capture_request()
        try:
            return request.make_image("main").convert("RGB")
        finally:
            request.release()


class FallbackCamera:
    """Pour développer sur un PC : webcam si OpenCV est dispo, sinon mire générée."""

    def __init__(self, buffer):
        from PIL import Image, ImageDraw  # noqa: F401  (vérifie la dépendance)

        self.buffer = buffer
        self.cv = None
        try:
            import cv2

            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                self.cv, self.cap = cv2, cap
        except ImportError:
            pass
        self.name = "webcam" if self.cv else "mire de test"
        self.last = None
        self.lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _frame(self):
        from PIL import Image, ImageDraw

        if self.cv:
            ok, arr = self.cap.read()
            if ok:
                return Image.fromarray(self.cv.cvtColor(arr, self.cv.COLOR_BGR2RGB))
        w, h = config.PREVIEW_SIZE
        t = time.time()
        img = Image.new("RGB", (w, h), (int(80 + 60 * (t % 3)), 40, 120))
        d = ImageDraw.Draw(img)
        x = int((t * 200) % w)
        d.ellipse((x - 60, h // 2 - 60, x + 60, h // 2 + 60), fill=(255, 200, 0))
        d.text((20, 20), f"MIRE DE TEST  {datetime.now():%H:%M:%S}", fill="white")
        return img

    def _loop(self):
        while True:
            img = self._frame()
            with self.lock:
                self.last = img
            out = io.BytesIO()
            img.save(out, "JPEG", quality=75)
            self.buffer.write(out.getvalue())
            time.sleep(1 / 15)

    def capture_image(self):
        while self.last is None:
            time.sleep(0.05)
        with self.lock:
            return self.last.copy()


class Camera:
    def __init__(self):
        self.buffer = FrameBuffer()
        self.lock = threading.Lock()
        try:
            self.impl = PiCamera(self.buffer)
        except Exception as e:  # pas de Pi / pas de caméra
            print(f"[camera] Picamera2 indisponible ({e!r}) -> mode secours")
            self.impl = FallbackCamera(self.buffer)
        print(f"[camera] source : {getattr(self.impl, 'name', '?')}")

    def frames(self):
        while True:
            frame = self.buffer.wait()
            if frame:
                yield frame

    def capture_image(self):
        """Renvoie une image PIL (RGB) pleine définition."""
        with self.lock:
            return self.impl.capture_image()
