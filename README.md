# Photobox Raspberry Pi

Photobox autonome : aperçu caméra en plein écran, **photo seule ou série de 4 photos**,
impression CUPS, et récupération des photos sur téléphone via un hotspot Wi-Fi :
scan du QR code Wi-Fi → « Se connecter au réseau » → la galerie s'ouvre directement.

## Matériel
- Raspberry Pi 4 ou 5 avec Raspberry Pi OS **Desktop** (Bookworm ou Trixie)
- Camera Module (v3 conseillée) ou HQ Camera
- Écran tactile (ou écran + bouton d'arcade sur GPIO17 vers GND, ou bouton USB qui envoie Espace/Entrée)
- Imprimante photo reconnue par CUPS (ex. Canon Selphy CP1300/CP1500 via gutenprint, en USB)

## Installation
```bash
git clone https://github.com/Duhaume/photobox.git ~/photobox
cd ~/photobox
./deploy/install.sh      # paquets, service systemd, kiosque, hotspot
```
Ajoutez ensuite l'imprimante sur http://localhost:631 (Administration → Add Printer), définissez-la
par défaut (`lpoptions -d NOM`), puis faites un test : `lp -o fit-to-page photo.jpg`.

## Adresses d'accès
Le serveur écoute sur le **port 80** (`PHOTOBOX_PORT` pour changer ; ajouter alors `:PORT` aux adresses).

| Page | Adresse | Depuis |
|---|---|---|
| Page photos (accueil, prise de vue) | **http://localhost/** | l'écran du Pi uniquement |
| Réglages | **http://localhost/reglages** | l'écran du Pi uniquement |
| Galerie des invités | **http://10.42.0.1/galerie** (ou simplement http://10.42.0.1) | un téléphone connecté au Wi-Fi de la photobox |
| Page d'une séance | http://10.42.0.1/p/&lt;id&gt; (lien du QR code ②) | idem |
| Configuration de l'imprimante (CUPS) | http://localhost:631 | l'écran du Pi |

La page photos et les réglages refusent toute autre machine : depuis un téléphone ou un PC,
http://10.42.0.1/ redirige vers la galerie et http://10.42.0.1/reglages renvoie une erreur 403.
En développement sur PC (`PHOTOBOX_PORT=8000`) : http://localhost:8000/ et http://localhost:8000/reglages.

## Mise à jour
Le Wi-Fi du Pi sert de hotspot et n'a donc pas accès à Internet : branchez un **câble Ethernet**
(ou repassez temporairement le Wi-Fi en client) le temps de la mise à jour, puis sur le Pi :
```bash
cd ~/photobox
git pull
sudo systemctl restart photobox
```
Rechargez ensuite la page photos : appui long dans le coin haut gauche → « Ouvrir la page photos »,
ou touche F5, ou `sudo reboot`. Relancez `./deploy/install.sh` seulement si une mise à jour l'indique
(ex. pour créer les raccourcis « Photobox » et « Photobox – Réglages »). Les photos (`photos/`) et
les réglages (`data/`) ne sont pas touchés par `git pull`.

## Parcours d'un invité
1. Il choisit **1 photo** ou **4 photos** sur l'écran (le bouton GPIO ou la barre d'espace lancent
   le mode par défaut, `DEFAULT_MODE`). Mode 4 photos : 3 s avant la première, puis 2 s entre chaque.
2. Le résultat s'affiche (la planche 2x2 en mode 4 photos) avec deux QR codes : **① Wi-Fi** et **② photo**.
3. **Portail captif** : dès que le téléphone rejoint le Wi-Fi, il affiche « Se connecter au réseau »
   et ouvre la **galerie** (mise à jour en direct). Le bouton « Terminé » valide la connexion :
   le téléphone ferme la fenêtre et reste connecté.
4. Chaque séance a sa page : planche + photos séparées, toutes téléchargeables.
5. Bouton « Imprimer » sur l'écran : planche 10x15 ou photo seule (2 tirages max par défaut).

### À savoir sur le portail captif
- Le DNS du hotspot renvoie tous les noms de domaine vers le Pi (`/etc/NetworkManager/dnsmasq-shared.d/photobox.conf`).
  Pour le désactiver : `sudo CAPTIVE=0 ./deploy/hotspot.sh …` et `PHOTOBOX_CAPTIVE_PORTAL=0`.
- Sur iPhone, la fenêtre du portail ne permet pas toujours d'enregistrer les photos. Il vaut mieux
  scanner le QR code ② ou ouvrir `http://10.42.0.1` dans Safari.
- Sur Android, si les données mobiles sont actives, le téléphone peut préférer la 4G une fois
  le portail fermé. Le QR code ② passe en général quand même ; sinon, couper les données mobiles.

## Réglages (sur l'écran du Pi)
Page **http://localhost/reglages** (sur le Pi), accessible :
- depuis l'accueil de la photobox : **appui long (2 s) dans le coin haut gauche** (un ⚙️ apparaît), ou touche **R** ;
- depuis le menu des applications / le bureau : raccourci **« Photobox – Réglages »** (créé par `install.sh`,
  à côté de **« Photobox »** qui rouvre la page photos).

On y règle : titre et **fond de l'écran d'accueil** (aperçu caméra, couleur unie ou image, avec assombrissement),
**couleurs des boutons** (bouton principal, autres boutons, texte, avec aperçu),
comptes à rebours, mode du bouton physique, délai de retour à l'accueil, impression (activée, tirages max,
texte du bandeau). Le bouton **« Ouvrir la page photos »** ramène à l'accueil, qui prend les nouveaux réglages.
Les réglages sont enregistrés dans `data/settings.json` et l'image de fond dans `data/background.jpg`
(hors dépôt git). Comme le reste de l'administration, la page n'est accessible que depuis le Pi lui-même.

## Configuration
Voir `config.py` (surchargeable avec les variables d'environnement `PHOTOBOX_*`, dans le service systemd) :
les valeurs marquées « (réglage) » ne sont que des valeurs par défaut, la page de réglages passe devant.
SSID et mot de passe Wi-Fi (doivent correspondre au hotspot), comptes à rebours (`COUNTDOWN`,
`STRIP_COUNTDOWN`), nombre de photos (`STRIP_SHOTS`), mode par défaut, résolution,
imprimante et options `lp` (ex. `-o media=Postcard` pour une Selphy), texte du bandeau imprimé,
galerie publique `/galerie`, broche GPIO.

## Stockage
Une séance = un dossier `photos/<date>_<id>/` contenant `1.jpg`…`4.jpg`, `montage.jpg` (planche) et `thumb.jpg`.

## Sécurité
Seul l'écran du Pi (localhost) peut déclencher une capture ou une impression. Les téléphones n'ont accès
qu'aux pages de photos. Les identifiants de 8 caractères aléatoires ne se devinent pas. Pour masquer
les photos des autres invités, désactivez la galerie (`PHOTOBOX_PUBLIC_GALLERY=0`).

## Développement sur PC
```bash
pip install flask qrcode pillow   # (+ opencv-python pour utiliser la webcam)
PHOTOBOX_PORT=8000 PHOTOBOX_GPIO_BUTTON_PIN=-1 python3 app.py
```
Sans Picamera2, l'application utilise la webcam (si OpenCV est installé) ou une mire de test.

## Commandes utiles
```bash
journalctl -u photobox -f            # logs
sudo systemctl restart photobox
lpstat -p -d                         # état des imprimantes
nmcli con up photobox-hotspot        # (re)lancer le hotspot
```
