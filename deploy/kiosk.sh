#!/usr/bin/env bash
# Lance Chromium en plein écran sur l'interface de la photobox dès que le serveur répond.
URL="http://localhost/"
until curl -sf -o /dev/null "$URL"; do sleep 1; done
BROWSER=$(command -v chromium || command -v chromium-browser)
exec "$BROWSER" --kiosk --noerrdialogs --disable-infobars --incognito \
  --disable-session-crashed-bubble --disable-features=Translate \
  --overscroll-history-navigation=0 --disable-pinch \
  --check-for-update-interval=31536000 "$URL"
