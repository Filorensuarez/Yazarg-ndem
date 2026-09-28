from __future__ import annotations
import json, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from html import unescape

RSS_URL = "https://www.haberturk.com/rss/kategori/yazarlar.xml"
OUT = Path("data/articles.json")
TR = timezone(timedelta(hours=3))

ECON = ("ekonomi","piyasa","borsa","faiz","enflasyon","dolar","euro","tl","banka","kredi",
        "yatırım","vergi","ihracat","ithalat","şirket","sermaye","fon","bitcoin","kripto","altın")
POL = ("siyaset","seçim","meclis","tbmm","bakan","başkan","parti","chp","ak parti","mhp","dem",
       "cumhurbaşkanı","erdoğan","diplomasi","kıbrıs","anayasa","belediye","milletvekili")

def clean(s):
    s = unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()

def category(text):
    t = text.casefold()
    if any(k in t for k in ECON): return "Ekonomi"
    if any(k in t for k in POL): return "Siyaset"
    return "Gündem"

def parse_date(raw):
    try:
        d = parsedate_to_datetime(raw)
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(TR)
    except Exception:
        return None

def fetch():
    req=urllib.request.Request(RSS_URL, headers={"User-Agent":"YazarGundem/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def main():
    now=datetime.now(TR)
    today=now.date()
    yesterday=today-timedelta(days=1)
    root=ET.fromstring(fetch())
    rows=[]
    seen=set()
    for item in root.findall(".//item"):
        title=clean(item.findtext("title"))
        link=clean(item.findtext("link"))
        desc=clean(item.findtext("description"))
        author=clean(item.findtext("author"))
        if not author:
            author=clean(item.findtext("{http://purl.org/dc/elements/1.1/}creator"))
        d=parse_date(clean(item.findtext("pubDate")))
        if not title or not link or not d or d.date() not in (today,yesterday) or link in seen:
            continue
        seen.add(link)
        rows.append({
            "category": category(title+" "+desc),
            "source": "Habertürk",
            "author": author or "Habertürk Yazarı",
            "title": title,
            "summary": desc[:350],
            "url": link,
            "day": "Bugün" if d.date()==today else "Dün",
            "publishedAt": d.isoformat()
        })
    rows.sort(key=lambda x:x["publishedAt"], reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"{len(rows)} yazı kaydedildi.")

if __name__=="__main__":
    main()
