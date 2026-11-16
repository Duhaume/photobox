#!/usr/bin/env bash
# Lance Chromium en plein écran sur l'interface de la photobox dès que le serveur répond.
# Argument optionnel : chemin de la page, ex. « kiosk.sh reglages » pour la page de réglages.
# (Pour quitter le plein écran : Alt+F4.)
URL="http://localhost/${1#/}"
until curl -sf -o /dev/null "http://localhost/"; do sleep 1; done
BROWSER=$(command -v chromium || command -v chromium-browser)
exec "$BROWSER" --kiosk --noerrdialogs --disable-infobars --incognito \
  --disable-session-crashed-bubble --disable-features=Translate \
  --overscroll-history-navigation=0 --disable-pinch \
  --check-for-update-interval=31536000 "$URL"
