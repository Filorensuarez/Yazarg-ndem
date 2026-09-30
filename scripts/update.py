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
    "ekonomi", "piyasa", "borsa", "bist",
    "faiz", "enflasyon", "dolar", "euro",
    "döviz", "banka", "kredi", "yatırım",
    "vergi", "ihracat", "ithalat", "şirket",
    "sermaye", "fon", "bitcoin", "kripto",
    "altın", "enerji", "sanayi", "ticaret",
    "iş dünyası"
)


POL = (
    "siyaset", "seçim", "meclis", "tbmm",
    "bakan", "başkan", "parti", "chp",
    "ak parti", "akp", "mhp", "dem",
    "cumhurbaşkanı", "erdoğan", "diplomasi",
    "anayasa", "belediye", "milletvekili",
    "iktidar", "muhalefet"
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

    e = sum(
        word in text
        for word in ECON
    )

    p = sum(
        word in text
        for word in POL
    )

    if e > p and e:
        return "Ekonomi"

    if p > e and p:
        return "Siyaset"

    return "Gündem"


def get(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0 (Linux; Android 13) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36",

            "Accept-Language":
            "tr-TR,tr;q=0.9,en;q=0.7",
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:
        return response.read()


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

        articles.append({
            "category":
                category(
                    title + " " + speech_text
                ),

            "source":
                source,

            "author":
                author or source + " Yazarı",

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
        })

    return articles


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

        is_article = any(
            x in str(obj_type).lower()
            for x in (
                "article",
                "newsarticle",
                "reportagenewsarticle",
                "opinionnewsarticle"
            )
        )

        if not is_article:
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


def is_article_url(
    source,
    url
):
    low = url.lower()

    if source == "Cumhuriyet":

        # Profil:
        # /yazarlar/emre-kongar
        #
        # Gerçek yazı:
        # /yazarlar/mustafa-balbay/bu-kriz-iz-birakir-2541926

        return bool(
            re.search(
                r"/yazarlar/[^/]+/[^/?#]+-\d+(?:[/?#]|$)",
                low
            )
        )

    if source == "Sözcü":

        # Sözcü gerçek yazıları genellikle
        # sonlarında -p123456 benzeri kimlik taşır.
        return bool(
            re.search(
                r"-p\d+(?:[/?#]|$)",
                low
            )
        )

    return False


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

    # CUMHURİYET:
    # Önce yazar profillerini bul.
    # Sonra her profilin içinden gerçek yazıları çıkar.
    if source == "Cumhuriyet":

        profiles = []
        profile_seen = set()

        for href in links:

            full_url = urljoin(
                page_url,
                href
            )

            if domain not in full_url:
                continue

            path_match = re.search(
                r'https?://(?:www\.)?cumhuriyet\.com\.tr/yazarlar/([^/?#]+)/?$',
                full_url,
                flags=re.I
            )

            if not path_match:
                continue

            if full_url in profile_seen:
                continue

            profile_seen.add(
                full_url
            )

            profiles.append(
                full_url
            )

        print(
            "Cumhuriyet yazar profili:",
            len(profiles)
        )

        # Aşırı istek oluşmasını önle.
        profiles = profiles[:100]

        for profile_url in profiles:

            try:

                profile_raw = get(
                    profile_url
                ).decode(
                    "utf-8",
                    errors="ignore"
                )

                profile_links = re.findall(
                    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>',
                    profile_raw,
                    flags=re.I | re.S
                )

                for href in profile_links:

                    full_url = urljoin(
                        profile_url,
                        href
                    )

                    if domain not in full_url:
                        continue

                    if full_url in seen:
                        continue

                    # Cumhuriyet gerçek köşe yazıları:
                    # /yazarlar/yazar-adi/yazi-basligi-1234567

                    if not re.search(
                        r'/yazarlar/[^/?#]+/[^/?#]+-\d+(?:[/?#]|$)',
                        full_url,
                        flags=re.I
                    ):
                        continue

                    seen.add(
                        full_url
                    )

                    found.append(
                        full_url
                    )

            except Exception as error:

                print(
                    "Cumhuriyet profil atlandı:",
                    profile_url,
                    error
                )

        return found


    # SÖZCÜ:
    # Mevcut çalışan sistemi koru.

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
    ) = json_ld_values(raw)


    title = (
        ld_title
        or find_meta(
            raw,
            (
                "og:title",
                "twitter:title"
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
                "twitter:description"
            )
        )
    )


    author = (
        ld_author
        or find_meta(
            raw,
            (
                "author",
                "article:author"
            )
        )
    )


    published_raw = (
        ld_published
        or find_meta(
            raw,
            (
                "article:published_time",
                "datePublished"
            )
        )
    )


    published = parse_iso_date(
        published_raw
    )


    # Bazı sayfalarda JSON-LD tarihi yoksa
    # HTML içindeki YYYY-MM-DD tarihini dene.

    if not published:

        match = re.search(
            r'20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?',
            raw
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


    if author and (
        title.casefold()
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

    print(
        source,
        "aday yazı bağlantısı:",
        len(urls)
    )

    urls = urls[:100]

    for article_url in urls:

        try:

            article = read_article_page(
                source,
                article_url,
                today,
                yesterday
            )

            if article:
                articles.append(article)

        except Exception as error:

            print(
                source,
                "yazı atlandı:",
                article_url,
                error
            )

    return articles


def main():

    now = datetime.now(TR)

    today = now.date()

    yesterday = (
        today
        - timedelta(days=1)
    )

    rows = []
    seen = set()


    # HABERTÜRK RSS

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

                rows.append(article)

        except Exception as error:

            print(
                source,
                "RSS atlanıyor:",
                error
            )


    # SÖZCÜ + CUMHURİYET

    for item in WEB_SOURCES:

        source = item["name"]

        try:

            results = read_web_source(
                source,
                item["url"],
                item["domain"],
                today,
                yesterday
            )

            for article in results:

                if article["url"] in seen:
                    continue

                seen.add(
                    article["url"]
                )

                rows.append(article)

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


    counts = {}

    for article in rows:

        source = article["source"]

        counts[source] = (
            counts.get(source, 0)
            + 1
        )


    print(
        len(rows),
        "yazı kaydedildi"
    )


    for source in sorted(counts):

        print(
            source,
            ":",
            counts[source]
        )


if __name__ == "__main__":
    main()
