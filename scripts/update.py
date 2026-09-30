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

TIMEOUT = 10


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


def clean(value):
    value = unescape(value or "")

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

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


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

    if economy_score > politics_score and economy_score:
        return "Ekonomi"

    if politics_score > economy_score and politics_score:
        return "Siyaset"

    return "Gündem"


def get(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 (Linux; Android 13) "
                "AppleWebKit/537.36 "
                "Chrome/120 Safari/537.36",

            "Accept-Language":
                "tr-TR,tr;q=0.9,en;q=0.7",
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT
    ) as response:
        return response.read()


def get_html(url):
    return get(url).decode(
        "utf-8",
        errors="ignore"
    )


def extract_links(html, base_url):
    links = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>',
        html,
        flags=re.I | re.S
    )

    return [
        urljoin(base_url, href)
        for href in links
    ]


def parse_rss_date(raw):
    try:
        value = parsedate_to_datetime(raw)

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(TR)

    except Exception:
        return None


def parse_iso_date(raw):
    if not raw:
        return None

    try:
        raw = raw.strip()

        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"

        value = datetime.fromisoformat(raw)

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=TR
            )

        return value.astimezone(TR)

    except Exception:
        return None


def find_meta(html, names):
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

    objects = []

    for block in blocks:
        try:
            data = json.loads(
                unescape(block)
            )

        except Exception:
            continue

        if isinstance(data, list):
            objects.extend(data)

        elif isinstance(data, dict):
            objects.append(data)

    index = 0

    while index < len(objects):
        obj = objects[index]
        index += 1

        if not isinstance(obj, dict):
            continue

        graph = obj.get("@graph")

        if isinstance(graph, list):
            objects.extend(
                x
                for x in graph
                if isinstance(x, dict)
            )

        obj_type = obj.get("@type", "")

        if isinstance(obj_type, list):
            obj_type = " ".join(obj_type)

        article_type = any(
            value in str(obj_type).lower()
            for value in (
                "article",
                "newsarticle",
                "opinionnewsarticle",
                "reportagenewsarticle",
            )
        )

        if not article_type:
            continue

        if not title:
            title = clean(
                obj.get("headline")
                or obj.get("name")
                or ""
            )

        if not description:
            description = clean(
                obj.get("description")
                or ""
            )

        if not published:
            published = clean(
                obj.get("datePublished")
                or ""
            )

        if not author:
            value = obj.get("author")

            if isinstance(value, dict):
                author = clean(
                    value.get("name")
                    or ""
                )

            elif isinstance(value, list):
                for person in value:
                    if isinstance(person, dict):
                        author = clean(
                            person.get("name")
                            or ""
                        )

                        if author:
                            break

            elif isinstance(value, str):
                author = clean(value)

    return (
        title,
        author,
        description,
        published
    )


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

        published = parse_rss_date(
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
                    "Bugün"
                    if published.date() == today
                    else "Dün",

                "publishedAt":
                    published.isoformat(),
            }
        )

    return articles


def discover_sozcu():
    page_url = (
        "https://www.sozcu.com.tr/yazarlar"
    )

    html = get_html(page_url)

    links = extract_links(
        html,
        page_url
    )

    found = []
    seen = set()

    for url in links:
        if "sozcu.com.tr" not in url:
            continue

        if url in seen:
            continue

        if not re.search(
            r"-p\d+(?:[/?#]|$)",
            url.lower()
        ):
            continue

        seen.add(url)
        found.append(url)

    print(
        "Sözcü aday:",
        len(found)
    )

    return found[:60]


def discover_cumhuriyet():
    page_url = (
        "https://www.cumhuriyet.com.tr/yazarlar"
    )

    html = get_html(page_url)

    links = extract_links(
        html,
        page_url
    )

    profiles = []
    profile_seen = set()

    for url in links:

        if not re.search(
            r'https?://(?:www\.)?cumhuriyet\.com\.tr/yazarlar/[^/?#]+/?$',
            url,
            flags=re.I
        ):
            continue

        if url in profile_seen:
            continue

        profile_seen.add(url)
        profiles.append(url)

    print(
        "Cumhuriyet profil:",
        len(profiles)
    )

    all_articles = []
    article_seen = set()

    for profile_url in profiles[:100]:

        try:
            profile_html = get_html(
                profile_url
            )

            profile_links = extract_links(
                profile_html,
                profile_url
            )

            per_author = []

            for url in profile_links:

                if url in article_seen:
                    continue

                if not re.search(
                    r'/yazarlar/[^/?#]+/[^/?#]+-\d+(?:[/?#]|$)',
                    url,
                    flags=re.I
                ):
                    continue

                article_seen.add(url)
                per_author.append(url)

                # Her yazar için yalnızca
                # en fazla 5 aday yazı.
                if len(per_author) >= 5:
                    break

            all_articles.extend(
                per_author
            )

            # Toplam aday sayısı için de
            # üst sınır.
            if len(all_articles) >= 250:
                break

        except Exception as error:
            print(
                "Cumhuriyet profil atlandı:",
                profile_url,
                error
            )

    all_articles = all_articles[:250]

    print(
        "Cumhuriyet aday:",
        len(all_articles)
    )

    return all_articles


def read_article(
    source,
    url,
    today,
    yesterday
):
    html = get_html(url)

    (
        ld_title,
        ld_author,
        ld_description,
        ld_published
    ) = json_ld_values(html)


    title = (
        ld_title
        or find_meta(
            html,
            (
                "og:title",
                "twitter:title",
            )
        )
    )


    author = (
        ld_author
        or find_meta(
            html,
            (
                "author",
                "article:author",
            )
        )
    )


    description = (
        ld_description
        or find_meta(
            html,
            (
                "og:description",
                "description",
                "twitter:description",
            )
        )
    )


    published_raw = (
        ld_published
        or find_meta(
            html,
            (
                "article:published_time",
                "datePublished",
            )
        )
    )


    published = parse_iso_date(
        published_raw
    )


    if not published:
        match = re.search(
            r'20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?',
            html
        )

        if match:
            published = parse_iso_date(
                match.group(0)
            )


    if not published:
        return None


    if published.date() not in (
        today,
        yesterday
    ):
        return None


    title = clean(title)
    author = clean(author)
    description = clean(description)


    if not title:
        return None


    if (
        author
        and title.casefold()
        == author.casefold()
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
            "Bugün"
            if published.date() == today
            else "Dün",

        "publishedAt":
            published.isoformat(),
    }


def collect_web(
    source,
    urls,
    today,
    yesterday
):
    results = []

    for index, url in enumerate(
        urls,
        start=1
    ):
        try:
            article = read_article(
                source,
                url,
                today,
                yesterday
            )

            if article:
                results.append(article)

        except Exception as error:
            print(
                source,
                "yazı atlandı:",
                error
            )

    return results


def main():
    now = datetime.now(TR)

    today = now.date()

    yesterday = (
        today
        - timedelta(days=1)
    )

    rows = []
    seen = set()


    # HABERTÜRK

    try:
        haberturk = read_rss(
            "Habertürk",
            RSS_SOURCES[0][1],
            today,
            yesterday
        )

        rows.extend(haberturk)

    except Exception as error:
        print(
            "Habertürk hata:",
            error
        )


    # SÖZCÜ

    try:
        sozcu_urls = discover_sozcu()

        rows.extend(
            collect_web(
                "Sözcü",
                sozcu_urls,
                today,
                yesterday
            )
        )

    except Exception as error:
        print(
            "Sözcü hata:",
            error
        )


    # CUMHURİYET

    try:
        cumhuriyet_urls = (
            discover_cumhuriyet()
        )

        rows.extend(
            collect_web(
                "Cumhuriyet",
                cumhuriyet_urls,
                today,
                yesterday
            )
        )

    except Exception as error:
        print(
            "Cumhuriyet hata:",
            error
        )


    # TEKRARLARI TEMİZLE

    clean_rows = []

    for article in rows:

        url = article["url"]

        if url in seen:
            continue

        seen.add(url)

        clean_rows.append(
            article
        )


    clean_rows.sort(
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
            clean_rows,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


    counts = {}

    for article in clean_rows:

        source = article["source"]

        counts[source] = (
            counts.get(source, 0)
            + 1
        )


    print(
        "TOPLAM:",
        len(clean_rows)
    )


    for source in sorted(counts):

        print(
            source,
            ":",
            counts[source]
        )


if __name__ == "__main__":
    main()
