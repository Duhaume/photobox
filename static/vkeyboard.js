// Clavier virtuel AZERTY pour la page de réglages (écran tactile du Pi, sans clavier physique).
// S'ouvre au toucher d'un champ texte ou nombre ; pavé numérique pour les champs nombre.
(() => {
  const LETTERS = [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "⌫"],
    ["a", "z", "e", "r", "t", "y", "u", "i", "o", "p"],
    ["q", "s", "d", "f", "g", "h", "j", "k", "l", "m"],
    ["⇧", "w", "x", "c", "v", "b", "n", ",", ".", "'", "-"],
    ["é", "è", "ê", "à", "â", "ç", "ù", "ô", "î", "&", "!", "?", "·"],
    ["{date}", " ", "Masquer"],
  ];
  const DIGITS = [["7", "8", "9"], ["4", "5", "6"], ["1", "2", "3"], ["⌫", "0", "Masquer"]];
  const LABELS = { " ": "Espace", "{date}": "{date}" };

  const kb = document.createElement("div");
  kb.id = "vkb";
  kb.hidden = true;
  document.body.append(kb);

  let target = null;
  let shift = false;

  function render() {
    const numeric = target?.type === "number";
    kb.className = numeric ? "numeric" : "";
    kb.innerHTML = "";
    for (const row of numeric ? DIGITS : LETTERS) {
      const r = document.createElement("div");
      r.className = "vkb-row";
      for (const k of row) {
        const b = document.createElement("button");
        b.type = "button";
        b.dataset.key = k;
        b.textContent = LABELS[k] ?? (shift && k.length === 1 ? k.toUpperCase() : k);
        if (k === " ") b.className = "space";
        if (k === "⇧" && shift) b.className = "on";
        if (k.length > 1 && k !== "{date}") b.classList.add("wide");
        r.append(b);
      }
      kb.append(r);
    }
  }

  function insert(text) {
    if (target.type === "number") {
      target.value = (target.value + text).replace(/^0+(?=\d)/, "");
    } else {
      const max = target.maxLength > 0 ? target.maxLength : Infinity;
      const { selectionStart: s, selectionEnd: e, value } = target;
      if (value.length - (e - s) + text.length > max) return;
      target.setRangeText(text, s, e, "end");
    }
    target.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function backspace() {
    if (target.type === "number") {
      target.value = target.value.slice(0, -1);
    } else {
      let { selectionStart: s, selectionEnd: e } = target;
      if (s === e && s > 0) s -= 1;
      target.setRangeText("", s, e, "end");
    }
    target.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function open(input) {
    target = input;
    shift = false;
    render();
    kb.hidden = false;
    document.body.style.paddingBottom = kb.offsetHeight + "px";
    input.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  function close() {
    kb.hidden = true;
    document.body.style.paddingBottom = "";
    target?.blur();
    target = null;
  }

  // pointerdown + preventDefault : le champ garde le focus et le curseur
  kb.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    e.stopPropagation(); // sinon le clavier redessiné (⇧) passerait pour un toucher « ailleurs »
    const k = e.target.closest("button")?.dataset.key;
    if (!k || !target) return;
    if (k === "Masquer") return close();
    if (k === "⌫") return backspace();
    if (k === "⇧") { shift = !shift; return render(); }
    insert(shift && k.length === 1 ? k.toUpperCase() : k);
    if (shift) { shift = false; render(); }
  });

  document.addEventListener("focusin", (e) => {
    const el = e.target;
    if (el.matches("input[type=text], input[type=number]")) open(el);
  });
  // toucher ailleurs que dans un champ ou le clavier : on le ferme
  document.addEventListener("pointerdown", (e) => {
    if (!kb.hidden && !kb.contains(e.target) && !e.target.matches("input[type=text], input[type=number]")) close();
  });
})();
