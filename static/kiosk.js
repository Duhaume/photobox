const CFG = window.PHOTOBOX;
const $ = (s) => document.querySelector(s);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let state = "idle";
let current = null;
let backTimer = null;

function show(id) {
  for (const el of document.querySelectorAll(".layer")) el.hidden = el.id !== id;
}

function goIdle() {
  clearTimeout(backTimer);
  state = "idle";
  current = null;
  show("idle");
}

async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function countdown(seconds, label) {
  show("countdown");
  $("#shot-label").textContent = label;
  const c = $("#count");
  for (let n = seconds; n > 0; n--) {
    c.textContent = n;
    c.style.animation = "none"; c.offsetHeight; c.style.animation = ""; // relance l'anim
    await sleep(1000);
  }
  c.textContent = "";
}

function flash() {
  const f = $("#flash");
  f.hidden = true; f.offsetHeight; f.hidden = false;
  setTimeout(() => (f.hidden = true), 500);
}

async function run(mode) {
  if (state !== "idle") return;
  state = "shooting";
  try {
    const session = await post("/api/session", { mode });
    for (let i = 1; i <= session.shots; i++) {
      const label = session.shots > 1 ? `Photo ${i} / ${session.shots}` : "";
      await countdown(i === 1 ? CFG.countdown : CFG.stripCountdown, label);
      await post(`/api/session/${session.id}/shot`);  // capture d'abord, flash ensuite
      flash();
    }
    show("busy");
    current = await post(`/api/session/${session.id}/finish`);
  } catch (e) {
    console.error(e);
    goIdle();
    return;
  }
  $("#shot").src = current.image;
  $("#photo-qr").innerHTML = current.qr;
  $("#msg").textContent = "";
  const p = $("#btn-print");
  if (p) { p.disabled = false; p.textContent = "🖨️ Imprimer"; }
  state = "result";
  show("result");
  armTimeout();
}

function armTimeout() {
  clearTimeout(backTimer);
  backTimer = setTimeout(goIdle, CFG.resultTimeout * 1000);
}

async function printPhoto() {
  if (!current) return;
  const btn = $("#btn-print");
  btn.disabled = true;
  $("#msg").textContent = "Envoi à l'imprimante…";
  armTimeout();
  try {
    const data = await post(`/api/print/${current.id}`);
    $("#msg").textContent = "Impression lancée ! Patientez ~1 minute.";
    if (data.remaining > 0) setTimeout(() => (btn.disabled = false), 5000);
    else btn.textContent = "Impression envoyée ✔";
  } catch (e) {
    $("#msg").textContent = `Erreur : ${e.message}`;
    btn.disabled = false;
  }
}

// Déclencheur unique (barre d'espace, bouton GPIO) : mode par défaut, ou nouvelle séance.
function trigger(mode = CFG.defaultMode) {
  if (state === "result") goIdle();
  run(mode);
}

for (const b of document.querySelectorAll(".mode"))
  b.addEventListener("click", () => run(b.dataset.mode));
$("#btn-again").addEventListener("click", goIdle);
$("#btn-print")?.addEventListener("click", printPhoto);
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" || e.code === "Enter") { e.preventDefault(); trigger(); }
  else if (e.key === "1") trigger("single");
  else if (e.key === String(CFG.stripShots)) trigger("strip");
  else if (e.code === "KeyP" && state === "result") printPhoto();
  else if (e.code === "KeyR") openSettings();
});
new EventSource("/events").onmessage = (ev) => {
  if (JSON.parse(ev.data).type === "trigger") trigger();
};

// Réglages : appui long de 2 s dans le coin haut gauche (hors prise de vue), ou touche R.
function openSettings() {
  if (state !== "shooting") location.href = "/reglages";
}
const corner = $("#admin-corner");
let pressTimer = null;
corner.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  if (state === "shooting") return;
  corner.classList.add("pressing");
  pressTimer = setTimeout(openSettings, 2000);
});
for (const ev of ["pointerup", "pointerleave", "pointercancel"])
  corner.addEventListener(ev, () => { clearTimeout(pressTimer); corner.classList.remove("pressing"); });
corner.addEventListener("contextmenu", (e) => e.preventDefault());

// Si le flux MJPEG coupe (redémarrage du service), on le recharge.
$("#preview").addEventListener("error", () =>
  setTimeout(() => ($("#preview").src = `/stream.mjpg?t=${Date.now()}`), 2000));

goIdle();
