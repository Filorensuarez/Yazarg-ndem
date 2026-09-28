from __future__ import annotations
import json,re,urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from html import unescape

TR=timezone(timedelta(hours=3))
OUT=Path("data/articles.json")
SOURCES=[
 ("Habertürk","https://www.haberturk.com/rss/kategori/yazarlar.xml"),
]

ECON=("ekonomi","piyasa","borsa","faiz","enflasyon","dolar","euro","tl","banka","kredi","yatırım","vergi","ihracat","ithalat","şirket","sermaye","fon","bitcoin","kripto","altın","enerji","sanayi","ticaret")
POL=("siyaset","seçim","meclis","tbmm","bakan","başkan","parti","chp","ak parti","akp","mhp","dem","cumhurbaşkanı","erdoğan","diplomasi","anayasa","belediye","milletvekili","iktidar","muhalefet")

def clean(s):
 s=unescape(re.sub(r"<[^>]+>"," ",s or ""))
 return re.sub(r"\s+"," ",s).strip()

def cat(text):
 t=text.casefold()
 e=sum(k in t for k in ECON); q=sum(k in t for k in POL)
 if e>q and e: return "Ekonomi"
 if q>e and q: return "Siyaset"
 return "Gündem"

def dt(raw):
 try:
  x=parsedate_to_datetime(raw)
  if x.tzinfo is None:x=x.replace(tzinfo=timezone.utc)
  return x.astimezone(TR)
 except:return None

def get(url):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 YazarGundem/2.0"})
 with urllib.request.urlopen(req,timeout=30) as r:return r.read()

def rss(source,url,today,yesterday):
 out=[]
 root=ET.fromstring(get(url))
 for i in root.findall(".//item"):
  title=clean(i.findtext("title")); link=clean(i.findtext("link")); desc=clean(i.findtext("description"))
  author=clean(i.findtext("author")) or clean(i.findtext("{http://purl.org/dc/elements/1.1/}creator"))
  d=dt(clean(i.findtext("pubDate")))
  if not title or not link or not d or d.date() not in (today,yesterday):continue
  out.append({"category":cat(title+" "+desc),"source":source,"author":author or source+" Yazarı",
   "title":title,"summary":desc[:350],"url":link,"day":"Bugün" if d.date()==today else "Dün",
   "publishedAt":d.isoformat()})
 return out

def main():
 now=datetime.now(TR); today=now.date(); yesterday=today-timedelta(days=1)
 rows=[]; seen=set()
 for source,url in SOURCES:
  try:
   for x in rss(source,url,today,yesterday):
    if x["url"] not in seen:seen.add(x["url"]);rows.append(x)
  except Exception as e:print(source,"atlanıyor:",e)
 rows.sort(key=lambda x:x["publishedAt"],reverse=True)
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
 print(len(rows),"yazı kaydedildi")

if __name__=="__main__":main()
