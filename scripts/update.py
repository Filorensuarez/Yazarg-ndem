from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from html import unescape
from urllib.parse import urljoin


TR = timezone(timedelta(hours=3))
OUT = Path("data/articles.json")


RSS_SOURCES = [
    (
        "Habertürk",
        "https://www.haberturk.com/rss/kategori/yazarlar.xml"
    ),
]


WEB_SOURCES = [
    (
        "Sözcü",
        "https://www.sozcu.com.tr/yazarlar"
    ),
    (
        "Cumhuriyet",
        "https://www.cumhuriyet.com.tr/yazarlar"
    ),
]


ECON = (
    "ekonomi",
    "piyasa",
    "borsa",
    "faiz",
    "enflasyon",
    "dolar",
    "euro",
    "tl",
    "banka",
    "kredi",
    "yatırım",
    "vergi",
    "ihracat",
    "ithalat",
    "şirket",
    "sermaye",
    "fon",
    "bitcoin",
    "kripto",
    "altın",
    "enerji",
    "sanayi",
    "ticaret",
)


POL = (
    "siyaset",
    "seçim",
    "meclis",
    "tbmm",
    "bakan",
    "başkan",
    "parti",
    "chp",
    "ak parti",
    "akp",
    "mhp",
    "dem",
    "cumhurbaşkanı",
    "erdoğan",
    "diplomasi",
    "anayasa",
    "belediye",
    "milletvekili",
    "iktidar",
    "muhalefet",
)


def clean(value):
    value = unescape(
        re.sub(
            r"<[^>]+>",
            " ",
            value or ""
        )
    )

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


def category(text):
    text = text.casefold()

    economy_score = sum(
        word in text
        for word in ECON
    )

    politics_score = sum(
        word in text
        for word in POL
    )

    if economy_score > politics_score and economy_score:
        return "Ekonomi"

    if politics_score > economy_score and politics_score:
        return "Siyaset"

    return "Gündem"


def parse_date(raw):
    try:
        value = parsedate_to_datetime(raw)

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(TR)

    except Exception:
        return None


def get(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0 (Linux; Android 13) "
            "AppleWebKit/537.36 "
            "Chrome/120 Safari/537.36"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        return response.read()


def read_rss(
    source,
    url,
    today,
    yesterday
):
    articles = []

    root = ET.fromstring(
        get(url)
    )

    for item in root.findall(".//item"):

        title = clean(
            item.findtext("title")
        )

        link = clean(
            item.findtext("link")
        )

        description = clean(
            item.findtext("description")
        )

        content = clean(
            item.findtext(
                "{http://purl.org/rss/1.0/modules/content/}encoded"
            )
        )

        author = (
            clean(
                item.findtext("author")
            )
            or
            clean(
                item.findtext(
                    "{http://purl.org/dc/elements/1.1/}creator"
                )
            )
        )

        published = parse_date(
            clean(
                item.findtext("pubDate")
            )
        )

        if not title or not link or not published:
            continue

        if published.date() not in (
            today,
            yesterday
        ):
            continue

        speech_text = (
            content
            if len(content) > len(description)
            else description
        )

        speech_text = clean(
            speech_text
        )

        articles.append(
            {
                "category": category(
                    title + " " + speech_text
                ),
                "source": source,
                "author":
                    author
                    or source + " Yazarı",
                "title": title,
                "summary": speech_text,
                "speechText": speech_text,
                "url": link,
                "day":
                    "Bugün"
                    if published.date() == today
                    else "Dün",
                "publishedAt":
                    published.isoformat(),
            }
        )

    return articles


def read_web_source(
    source,
    url,
    today,
    yesterday
):
    articles = []

    try:
        raw = get(url).decode(
            "utf-8",
            errors="ignore"
        )

    except Exception:
        return articles

    links = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        raw,
        flags=re.I | re.S
    )

    seen_links = set()

    for href, label in links:

        text = clean(label)

        if not text:
            continue

        full_url = urljoin(
            url,
            href
        )

        if full_url in seen_links:
            continue

        if source == "Sözcü":

            if "sozcu.com.tr" not in full_url:
                continue

            if (
                "/yazar" not in full_url
                and
                "/kose-yazisi" not in full_url
            ):
                continue

        elif source == "Cumhuriyet":

            if "cumhuriyet.com.tr" not in full_url:
                continue

            if (
                "/yazarlar/" not in full_url
                and
                "/koseyazisi/" not in full_url
            ):
                continue

        if len(text) < 5:
            continue

        seen_links.add(
            full_url
        )

        articles.append(
            {
                "category":
                    category(text),

                "source":
                    source,

                "author":
                    source + " Yazarı",

                "title":
                    text,

                "summary":
                    "",

                "speechText":
                    "",

                "url":
                    full_url,

                "day":
                    "Bugün",

                "publishedAt":
                    datetime.now(TR).isoformat(),
            }
        )

    return articles


def main():

    now = datetime.now(TR)

    today = now.date()

    yesterday = (
        today - timedelta(days=1)
    )

    rows = []

    seen = set()


    # RSS KAYNAKLARI

    for source, url in RSS_SOURCES:

        try:

            results = read_rss(
                source,
                url,
                today,
                yesterday
            )

            for article in results:

                if article["url"] in seen:
                    continue

                seen.add(
                    article["url"]
                )

                rows.append(
                    article
                )

        except Exception as error:

            print(
                source,
                "RSS atlanıyor:",
                error
            )


    # WEB YAZAR SAYFALARI

    for source, url in WEB_SOURCES:

        try:

            results = read_web_source(
                source,
                url,
                today,
                yesterday
            )

            for article in results:

                if article["url"] in seen:
                    continue

                seen.add(
                    article["url"]
                )

                rows.append(
                    article
                )

        except Exception as error:

            print(
                source,
                "web atlanıyor:",
                error
            )


    rows.sort(
        key=lambda item:
        item["publishedAt"],
        reverse=True
    )


    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    OUT.write_text(
        json.dumps(
            rows,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


    print(
        len(rows),
        "yazı kaydedildi"
    )


if __name__ == "__main__":
    main()
