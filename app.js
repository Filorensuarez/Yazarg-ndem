let category="Tümü",day="Bugün",articles=[];
const esc=s=>(s||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function load(){try{articles=await fetch("data/articles.json?"+Date.now()).then(r=>r.json())}catch(e){articles=[]}render()}
function render(){const rows=articles.filter(x=>(category==="Tümü"||x.category===category)&&x.day===day);document.querySelector("#list").innerHTML=rows.length?rows.map(x=>`<article class="card"><div class="meta">${esc(x.category)} · ${esc(x.source)}</div><h2>${esc(x.title)}</h2><div class="meta">${esc(x.author)}</div><div class="actions"><a href="${x.url}" target="_blank" rel="noopener">Yazıyı Oku</a><button onclick='speak(${JSON.stringify((x.title||"")+" — "+(x.summary||""))})'>Sesli Oku</button></div></article>`).join(""):`<div class="empty">Bu bölümde henüz yazı yok.</div>`}
let speechParts = [];
let speechPartIndex = 0;

function splitSpeechText(text, maxLength = 220) {
  const sentences = (text || "").match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [];
  const parts = [];
  let current = "";

  for (const sentence of sentences) {
    const s = sentence.trim();

    if ((current + " " + s).trim().length <= maxLength) {
      current = (current + " " + s).trim();
    } else {
      if (current) parts.push(current);
      current = s;
    }
  }

  if (current) parts.push(current);
  return parts;
}

function speakNextPart() {
  if (speechPartIndex >= speechParts.length) return;

  const utterance = new SpeechSynthesisUtterance(
    speechParts[speechPartIndex]
  );

  utterance.lang = "tr-TR";
  utterance.rate = 1;

  const voices = speechSynthesis.getVoices();
  const turkishVoice = voices.find(v =>
    (v.lang || "").toLowerCase().startsWith("tr")
  );

  if (turkishVoice) utterance.voice = turkishVoice;

  utterance.onend = function () {
    speechPartIndex++;
    speakNextPart();
  };

  utterance.onerror = function (event) {
    if (event.error !== "canceled" && event.error !== "interrupted") {
      speechPartIndex++;
      speakNextPart();
    }
  };

  speechSynthesis.speak(utterance);
}

function speak(text) {
  speechSynthesis.cancel();

  speechPartIndex = 0;
  speechParts = splitSpeechText(text);

  if (speechParts.length > 0) {
    speakNextPart();
  }
}
document.querySelectorAll("#cats button").forEach(b=>b.onclick=()=>{document.querySelectorAll("#cats button").forEach(x=>x.classList.remove("active"));b.classList.add("active");category=b.dataset.cat;render()});
document.querySelectorAll("#days button").forEach(b=>b.onclick=()=>{document.querySelectorAll("#days button").forEach(x=>x.classList.remove("active"));b.classList.add("active");day=b.dataset.day;render()});
load();
