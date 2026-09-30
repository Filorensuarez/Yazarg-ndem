let category = "Tümü";
let day = "Bugün";
let articles = [];

const esc = s =>
  (s || "").replace(
    /[&<>"']/g,
    c => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[c])
  );

async function load() {
  try {
    articles = await fetch(
      "data/articles.json?" + Date.now()
    ).then(r => r.json());
  } catch (e) {
    articles = [];
  }

  render();
}

function render() {
  const rows = articles.filter(
    x =>
      (category === "Tümü" || x.category === category) &&
      x.day === day
  );

  document.querySelector("#list").innerHTML = rows.length
    ? rows.map(x => `
      <article class="card">

        <div class="meta">
          ${esc(x.category)} · ${esc(x.source)}
        </div>

        <h2>${esc(x.title)}</h2>

        <div class="meta">
          ${esc(x.author)}
        </div>

        <div class="actions">

          <a
            href="${x.url}"
            target="_blank"
            rel="noopener"
          >
            Yazıyı Oku
          </a>

          <button
            onclick='speak(${JSON.stringify(
              (x.title || "") +
              " — " +
              (x.speechText || x.summary || "")
            )})'
          >
            Sesli Oku
          </button>

        </div>

      </article>
    `).join("")
    : `<div class="empty">
         Bu bölümde henüz yazı yok.
       </div>`;
}


/* -------------------------
   SESLİ OKUMA
-------------------------- */

let speechParts = [];
let speechPartIndex = 0;
let currentUtterance = null;


function splitSpeechText(
  text,
  maxLength = 220
) {

  const sentences =
    (text || "").match(
      /[^.!?…]+[.!?…]+|[^.!?…]+$/g
    ) || [];

  const parts = [];

  let current = "";

  for (const sentence of sentences) {

    const s = sentence.trim();

    if (!s) continue;

    if (
      (current + " " + s)
        .trim()
        .length <= maxLength
    ) {

      current =
        (current + " " + s).trim();

    } else {

      if (current) {
        parts.push(current);
      }

      /*
       Çok uzun tek cümle varsa
       kelimelerden güvenli biçimde böl.
      */

      if (s.length > maxLength) {

        const words = s.split(/\s+/);

        current = "";

        for (const word of words) {

          const candidate =
            (current + " " + word).trim();

          if (
            candidate.length >
            maxLength
          ) {

            if (current) {
              parts.push(current);
            }

            current = word;

          } else {

            current = candidate;

          }
        }

      } else {

        current = s;

      }
    }
  }

  if (current) {
    parts.push(current);
  }

  return parts;
}


function getTurkishVoice() {

  const voices =
    speechSynthesis.getVoices();

  return (
    voices.find(
      v =>
        (v.lang || "")
          .toLowerCase()
          .startsWith("tr")
    ) ||
    null
  );
}


function speakNextPart() {

  if (
    speechPartIndex >=
    speechParts.length
  ) {

    currentUtterance = null;
    return;
  }

  const text =
    speechParts[speechPartIndex];

  const utterance =
    new SpeechSynthesisUtterance(text);

  currentUtterance = utterance;

  utterance.lang = "tr-TR";

  utterance.rate = 1;

  const turkishVoice =
    getTurkishVoice();

  if (turkishVoice) {
    utterance.voice =
      turkishVoice;
  }

  utterance.onend = function () {

    speechPartIndex++;

    /*
      Android tarayıcılarında
      arka arkaya uzun TTS işlemlerini
      daha kararlı hâle getirir.
    */

    setTimeout(
      speakNextPart,
      50
    );
  };

  utterance.onerror =
    function (event) {

      if (
        event.error === "canceled" ||
        event.error === "interrupted"
      ) {
        return;
      }

      speechPartIndex++;

      setTimeout(
        speakNextPart,
        50
      );
    };

  speechSynthesis.speak(
    utterance
  );
}


function speak(text) {

  speechSynthesis.cancel();

  speechParts = [];
  speechPartIndex = 0;
  currentUtterance = null;

  const cleanText =
    (text || "").trim();

  if (!cleanText) {
    return;
  }

  speechParts =
    splitSpeechText(
      cleanText
    );

  if (
    speechParts.length > 0
  ) {

    /*
      cancel() işleminden hemen sonra
      yeni sesi başlatmak yerine
      çok kısa bekle.
    */

    setTimeout(
      speakNextPart,
      100
    );
  }
}


/* -------------------------
   KATEGORİLER
-------------------------- */

document
  .querySelectorAll("#cats button")
  .forEach(b => {

    b.onclick = () => {

      document
        .querySelectorAll(
          "#cats button"
        )
        .forEach(
          x =>
            x.classList.remove(
              "active"
            )
        );

      b.classList.add(
        "active"
      );

      category =
        b.dataset.cat;

      render();
    };
  });


/* -------------------------
   BUGÜN / DÜN
-------------------------- */

document
  .querySelectorAll("#days button")
  .forEach(b => {

    b.onclick = () => {

      document
        .querySelectorAll(
          "#days button"
        )
        .forEach(
          x =>
            x.classList.remove(
              "active"
            )
        );

      b.classList.add(
        "active"
      );

      day =
        b.dataset.day;

      render();
    };
  });


/* -------------------------
   BAŞLAT
-------------------------- */

load();
