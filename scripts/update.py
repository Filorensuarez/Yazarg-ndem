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


# =========================================================
# KAYNAKLAR
# =========================================================

RSS_SOURCES = [
    (
        "Habertürk",
        "https://www.haberturk.com/rss/kategori/yazarlar.xml"
    ),
]


WEB_SOURCES = [
    {
        "name": "Sözcü",
        "url": "https://www.sozcu.com.tr/yazarlar",
        "domain": "sozcu.com.tr",
    },
    {
        "name": "Cumhuriyet",
        "url": "https://www.cumhuriyet.com.tr/yazarlar",
        "domain": "cumhuriyet.com.tr",
    },
]


# =========================================================
# KATEGORİ KELİMELERİ
# =========================================================

ECON = (
    "ekonomi",
    "piyasa",
    "borsa",
    "bist",
    "faiz",
    "enflasyon",
    "dolar",
    "euro",
    "döviz",
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
    "iş dünyası",
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


# =========================================================
# TEMİZLEME
# =========================================================

def clean(value):

    value = value or ""

    value = unescape(value)

    value = re.sub(
        r"<script.*?</script>",
        " ",
        value,
        flags=re.I | re.S
    )

    value = re.sub(
        r"<style.*?</style>",
        " ",
        value,
        flags=re.I | re.S
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# =========================================================
# KATEGORİ
# =========================================================

def category(text):

    text = (text or "").casefold()

    economy_score = sum(
        word in text
        for word in ECON
    )

    politics_score = sum(
        word in text
        for word in POL
    )

    if (
        economy_score >
        politics_score
        and economy_score
    ):
        return "Ekonomi"

    if (
        politics_score >
        economy_score
        and politics_score
    ):
        return "Siyaset"

    return "Gündem"


# =========================================================
# TARİH
# =========================================================

def parse_date(raw):

    try:

        value = parsedate_to_datetime(
            raw
        )

        if value.tzinfo is None:

            value = value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(TR)

    except Exception:

        return None


# =========================================================
# HTTP
# =========================================================

def get(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0 "
            "(Linux; Android 13) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120 Safari/537.36",

            "Accept-Language":
            "tr-TR,tr;q=0.9,en;q=0.7",
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        return response.read()


# =========================================================
# RSS
# =========================================================

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

    for item in root.findall(
        ".//item"
    ):

        title = clean(
            item.findtext("title")
        )

        link = clean(
            item.findtext("link")
        )

        description = clean(
            item.findtext(
                "description"
            )
        )

        content = clean(
            item.findtext(
                "{http://purl.org/rss/1.0/modules/content/}encoded"
            )
        )

        author = (
            clean(
                item.findtext(
                    "author"
                )
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
                item.findtext(
                    "pubDate"
                )
            )
        )

        if not title:
            continue

        if not link:
            continue

        if not published:
            continue

        if published.date() not in (
            today,
            yesterday
        ):
            continue

        speech_text = (
            content
            if len(content) >
            len(description)
            else description
        )

        speech_text = clean(
            speech_text
        )

        articles.append(
            {
                "category":
                    category(
                        title
                        + " "
                        + speech_text
                    ),

                "source":
                    source,

                "author":
                    author
                    or source + " Yazarı",

                "title":
                    title,

                "summary":
                    speech_text,

                "speechText":
                    speech_text,

                "url":
                    link,

                "day":
                    (
                        "Bugün"
                        if published.date()
                        == today
                        else "Dün"
                    ),

                "publishedAt":
                    published.isoformat(),
            }
        )

    return articles


# =========================================================
# META ETİKETİ BUL
# =========================================================

def find_meta(
    html,
    names
):

    for name in names:

        patterns = [

            rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',

            rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',

            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(name)}["\']',

            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(name)}["\']',
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                flags=re.I | re.S
            )

            if match:

                value = clean(
                    match.group(1)
                )

                if value:
                    return value

    return ""


# =========================================================
# JSON-LD ALANLARI
# =========================================================

def json_ld_values(html):

    title = ""
    author = ""
    description = ""
    published = ""

    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.I | re.S
    )

    for block in blocks:

        try:

            data = json.loads(
                unescape(block)
            )

        except Exception:

            continue

        objects = (
            data
            if isinstance(data, list)
            else [data]
        )

        for obj in objects:

            if not isinstance(
                obj,
                dict
            ):
                continue

            graph = obj.get(
                "@graph"
            )

            if isinstance(
                graph,
                list
            ):
                objects.extend(
                    x
                    for x in graph
                    if isinstance(x, dict)
                )

            if not title:

                title = clean(
                    obj.get(
                        "headline"
                    )
                    or obj.get(
                        "name"
                    )
                    or ""
                )

            if not description:

                description = clean(
                    obj.get(
                        "description"
                    )
                    or ""
                )

            if not published:

                published = clean(
                    obj.get(
                        "datePublished"
                    )
                    or ""
                )

            if not author:

                value = obj.get(
                    "author"
                )

                if isinstance(
                    value,
                    dict
                ):

                    author = clean(
                        value.get(
                            "name"
                        )
                        or ""
                    )

                elif isinstance(
                    value,
                    list
                ):

                    for person in value:

                        if isinstance(
                            person,
                            dict
                        ):

                            author = clean(
                                person.get(
                                    "name"
                                )
                                or ""
                            )

                            if author:
                                break

                elif isinstance(
                    value,
                    str
                ):

                    author = clean(
                        value
                    )

    return (
        title,
        author,
        description,
        published
    )


# =========================================================
# ISO TARİH
# =========================================================

def parse_iso_date(raw):

    if not raw:
        return None

    try:

        value = raw.strip()

        if value.endswith("Z"):

            value = (
                value[:-1]
                + "+00:00"
            )

        result = datetime.fromisoformat(
            value
        )

        if result.tzinfo is None:

            result = result.replace(
                tzinfo=TR
            )

        return result.astimezone(TR)

    except Exception:

        return None


# =========================================================
# GERÇEK YAZI BAĞLANTISI MI?
# =========================================================

def is_article_url(
    source,
    url
):

    low = url.lower()

    # Profil/listeler kesinlikle alınmasın.

    blocked = (
        "/yazarlar",
        "/yazar/",
        "/authors",
        "/author/",
        "/kategori/",
        "/arama",
        "/etiket/",
    )

    if any(
        item in low
        for item in blocked
    ):

        # Cumhuriyet'te gerçek yazı yolu
        # /koseyazisi/ olabilir.
        if (
            source == "Cumhuriyet"
            and "/koseyazisi/" in low
        ):
            return True

        return False


    if source == "Cumhuriyet":

        return (
            "/koseyazisi/" in low
            or
            "/yazi/" in low
        )


    if source == "Sözcü":

        # Sözcü'de gerçek içerik
        # bağlantılarının profil
        # bağlantılarından ayrılması.
        return (
            "-p" in low
            or
            "/kose-yazisi/" in low
        )


    return False


# =========================================================
# YAZAR SAYFASINDAN ADAY URL BUL
# =========================================================

def discover_article_urls(
    source,
    page_url,
    domain
):

    raw = get(
        page_url
    ).decode(
        "utf-8",
        errors="ignore"
    )

    links = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>',
        raw,
        flags=re.I | re.S
    )

    found = []

    seen = set()

    for href in links:

        full_url = urljoin(
            page_url,
            href
        )

        if domain not in full_url:
            continue

        if full_url in seen:
            continue

        if not is_article_url(
            source,
            full_url
        ):
            continue

        seen.add(
            full_url
        )

        found.append(
            full_url
        )

    return found


# =========================================================
# GERÇEK MAKALE SAYFASINI OKU
# =========================================================

def read_article_page(
    source,
    url,
    today,
    yesterday
):

    raw = get(
        url
    ).decode(
        "utf-8",
        errors="ignore"
    )

    (
        ld_title,
        ld_author,
        ld_description,
        ld_published
    ) = json_ld_values(
        raw
    )


    title = (
        ld_title
        or find_meta(
            raw,
            (
                "og:title",
                "twitter:title",
            )
        )
    )


    description = (
        ld_description
        or find_meta(
            raw,
            (
                "og:description",
                "description",
                "twitter:description",
            )
        )
    )


    author = (
        ld_author
        or find_meta(
            raw,
            (
                "author",
                "article:author",
            )
        )
    )


    published_raw = (
        ld_published
        or find_meta(
            raw,
            (
                "article:published_time",
                "datePublished",
            )
        )
    )


    published = parse_iso_date(
        published_raw
    )


    # Tarihi doğrulanamayan içeriği
    # "bugün" diye uydurma.

    if not published:
        return None


    if published.date() not in (
        today,
        yesterday
    ):
        return None


    title = clean(
        title
    )

    author = clean(
        author
    )

    description = clean(
        description
    )


    if not title:
        return None


    # Yazar profilinin yanlışlıkla
    # makale olarak girmesine karşı
    # ikinci güvenlik kontrolü.

    if (
        title.casefold()
        == author.casefold()
        and author
    ):
        return None


    return {
        "category":
            category(
                title
                + " "
                + description
            ),

        "source":
            source,

        "author":
            author
            or source + " Yazarı",

        "title":
            title,

        "summary":
            description,

        "speechText":
            description,

        "url":
            url,

        "day":
            (
                "Bugün"
                if published.date()
                == today
                else "Dün"
            ),

        "publishedAt":
            published.isoformat(),
    }


# =========================================================
# WEB KAYNAĞINI OKU
# =========================================================

def read_web_source(
    source,
    url,
    domain,
    today,
    yesterday
):

    articles = []

    urls = discover_article_urls(
        source,
        url,
        domain
    )


    # Güvenlik:
    # yanlış bir sayfa yüzlerce URL
    # üretirse sınırsız istek yapma.

    urls = urls[:80]


    for article_url in urls:

        try:

            article = read_article_page(
                source,
                article_url,
                today,
                yesterday
            )

            if article:

                articles.append(
                    article
                )

        except Exception as error:

            print(
                source,
                "yazı atlandı:",
                article_url,
                error
            )

    return articles


# =========================================================
# ANA PROGRAM
# =========================================================

def main():

    now = datetime.now(TR)

    today = now.date()

    yesterday = (
        today
        - timedelta(days=1)
    )


    rows = []

    seen = set()


    # -----------------------------------------------------
    # RSS
    # -----------------------------------------------------

    for source, url in RSS_SOURCES:

        try:

            results = read_rss(
                source,
                url,
                today,
                yesterday
            )

            for article in results:

                key = article["url"]

                if key in seen:
                    continue

                seen.add(
                    key
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


    # -----------------------------------------------------
    # WEB
    # -----------------------------------------------------

    for item in WEB_SOURCES:

        source = item["name"]

        url = item["url"]

        domain = item["domain"]

        try:

            results = read_web_source(
                source,
                url,
                domain,
                today,
                yesterday
            )

            for article in results:

                key = article["url"]

                if key in seen:
                    continue

                seen.add(
                    key
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


    # -----------------------------------------------------
    # SIRALA
    # -----------------------------------------------------

    rows.sort(
        key=lambda item:
        item["publishedAt"],
        reverse=True
    )


    # -----------------------------------------------------
    # KAYDET
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # RAPOR
    # -----------------------------------------------------

    counts = {}

    for article in rows:

        source = article[
            "source"
        ]

        counts[source] = (
            counts.get(
                source,
                0
            )
            + 1
        )


    print(
        len(rows),
        "gerçek yazı kaydedildi"
    )


    for source in sorted(
        counts
    ):

        print(
            source,
            ":",
            counts[source]
        )


if __name__ == "__main__":
    main()
