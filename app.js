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


let speechRetryCount = 0;
let speechSessionId = 0;
let speechWatchdog = null;

function clearSpeechWatchdog() {
    if (speechWatchdog) {
        clearTimeout(speechWatchdog);
        speechWatchdog = null;
    }
}

function finishSpeech() {
    clearSpeechWatchdog();
    currentUtterance = null;
    speechParts = [];
    speechPartIndex = 0;
    speechRetryCount = 0;
}

function speakNextPart(sessionId) {

    if (sessionId !== speechSessionId) {
        return;
    }

    clearSpeechWatchdog();

    if (
        speechPartIndex >= speechParts.length
    ) {
        finishSpeech();
        return;
    }

    const text =
        (speechParts[speechPartIndex] || "").trim();

    if (!text) {
        speechPartIndex++;
        speechRetryCount = 0;

        setTimeout(
            () => speakNextPart(sessionId),
            80
        );

        return;
    }

    const utterance =
        new SpeechSynthesisUtterance(text);

    currentUtterance = utterance;

    utterance.lang = "tr-TR";
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;

    const turkishVoice =
        getTurkishVoice();

    if (turkishVoice) {
        utterance.voice = turkishVoice;
    }

    let completed = false;

    const continueToNext = () => {

        if (completed) {
            return;
        }

        completed = true;
        clearSpeechWatchdog();

        if (sessionId !== speechSessionId) {
            return;
        }

        speechPartIndex++;
        speechRetryCount = 0;
        currentUtterance = null;

        setTimeout(
            () => speakNextPart(sessionId),
            120
        );
    };

    utterance.onend = function () {
        continueToNext();
    };

    utterance.onerror = function (event) {

        if (completed) {
            return;
        }

        clearSpeechWatchdog();

        if (sessionId !== speechSessionId) {
            return;
        }

        const error =
            event && event.error
                ? event.error
                : "";

        /*
         * Android bazı uzun okumalarda
         * "interrupted" hatası verebilir.
         * Aynı parçayı en fazla iki kez
         * yeniden deniyoruz.
         */
        if (
            error === "interrupted" ||
            error === "network" ||
            error === "synthesis-failed"
        ) {
            completed = true;
            currentUtterance = null;

            if (speechRetryCount < 2) {
                speechRetryCount++;

                setTimeout(
                    () => speakNextPart(sessionId),
                    300
                );

                return;
            }

            speechRetryCount = 0;
            speechPartIndex++;

            setTimeout(
                () => speakNextPart(sessionId),
                150
            );

            return;
        }

        /*
         * cancel() kullanıcı yeni bir
         * okuma başlattığında oluşabilir.
         */
        if (error === "canceled") {
            completed = true;
            return;
        }

        completed = true;
        currentUtterance = null;

        speechPartIndex++;
        speechRetryCount = 0;

        setTimeout(
            () => speakNextPart(sessionId),
            150
        );
    };

    /*
     * Bazı Android tarayıcılarında TTS
     * çalışırken onend olayı kaybolabiliyor.
     * Bu kontrol motorun tamamen takılı
     * kalmasını önlemeye yardımcı olur.
     */
    speechWatchdog = setTimeout(
        function () {

            if (
                sessionId !== speechSessionId ||
                completed
            ) {
                return;
            }

            /*
             * Motor hâlâ konuşuyorsa
             * müdahale etme.
             */
            if (
                speechSynthesis.speaking ||
                speechSynthesis.pending
            ) {
                clearSpeechWatchdog();

                speechWatchdog = setTimeout(
                    arguments.callee,
                    5000
                );

                return;
            }

            /*
             * Konuşma durmuş ama onend
             * gelmemişse sıradaki parçaya geç.
             */
            continueToNext();
        },
        8000
    );

    speechSynthesis.speak(
        utterance
    );
}


function speak(text) {

    /*
     * Önceki okumayı geçersiz kıl.
     */
    speechSessionId++;

    const sessionId =
        speechSessionId;

    clearSpeechWatchdog();

    speechSynthesis.cancel();

    currentUtterance = null;
    speechParts = [];
    speechPartIndex = 0;
    speechRetryCount = 0;

    const cleanText =
        (text || "")
            .replace(/\s+/g, " ")
            .trim();

    if (!cleanText) {
        return;
    }

    speechParts =
        splitSpeechText(
            cleanText
        );

    if (
        !speechParts ||
        speechParts.length === 0
    ) {
        return;
    }

    /*
     * cancel() sonrasında Android TTS
     * motoruna kısa süre ver.
     */
    setTimeout(
        () => {

            if (
                sessionId === speechSessionId
            ) {
                speakNextPart(
                    sessionId
                );
            }

        },
        200
    );
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
