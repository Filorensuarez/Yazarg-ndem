from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin


TR = timezone(timedelta(hours=3))
OUT = Path("data/articles.json")

HTTP_TIMEOUT = 6

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}


ECON = (
    "ekonomi", "piyasa", "borsa", "bist",
    "faiz", "enflasyon", "dolar", "euro",
    "döviz", "banka", "kredi", "yatırım",
    "vergi", "ihracat", "ithalat", "şirket",
    "sermaye", "fon", "bitcoin", "kripto",
    "altın", "enerji", "sanayi", "ticaret",
    "iş dünyası",
)

POL = (
    "siyaset", "seçim", "meclis", "tbmm",
    "bakan", "başkan", "parti", "chp",
    "ak parti", "akp", "mhp", "dem",
    "cumhurbaşkanı", "erdoğan", "diplomasi",
    "anayasa", "belediye", "milletvekili",
    "iktidar", "muhalefet",
)


def get_bytes(url):
    req = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(
        req,
        timeout=HTTP_TIMEOUT
    ) as response:
        return response.read()


def get_html(url):
    return get_bytes(url).decode(
        "utf-8",
        errors="ignore"
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


def classify(text):
    text = (text or "").casefold()

    economy = sum(
        word in text
        for word in ECON
    )

    politics = sum(
        word in text
        for word in POL
    )

    if economy > politics and economy:
        return "Ekonomi"

    if politics > economy and politics:
        return "Siyaset"

    return "Gündem"


def extract_links(html, base_url):
    hrefs = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\']',
        html,
        flags=re.I
    )

    result = []
    seen = set()

    for href in hrefs:
        url = urljoin(base_url, href)

        if url in seen:
            continue

        seen.add(url)
        result.append(url)

    return result


def parse_iso(raw):
    if not raw:
        return None

    raw = raw.strip()

    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"

        value = datetime.fromisoformat(raw)

        if value.tzinfo is None:
            value = value.replace(tzinfo=TR)

        return value.astimezone(TR)

    except Exception:
        return None


def meta_value(html, keys):
    for key in keys:
        patterns = (
            rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(key)}["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(key)}["\']',
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                html,
                flags=re.I | re.S
            )

            if match:
                value = clean(match.group(1))

                if value:
                    return value

    return ""


def jsonld_article(html):
    result = {
        "title": "",
        "author": "",
        "description": "",
        "date": "",
    }

    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.I | re.S
    )

    queue = []

    for block in blocks:
        try:
            data = json.loads(
                unescape(block)
            )
        except Exception:
            continue

        if isinstance(data, list):
            queue.extend(data)

        elif isinstance(data, dict):
            queue.append(data)

    i = 0

    while i < len(queue):
        obj = queue[i]
        i += 1

        if not isinstance(obj, dict):
            continue

        graph = obj.get("@graph")

        if isinstance(graph, list):
            queue.extend(
                x for x in graph
                if isinstance(x, dict)
            )

        obj_type = obj.get("@type", "")

        if isinstance(obj_type, list):
            obj_type = " ".join(obj_type)

        if "article" not in str(obj_type).lower():
            continue

        if not result["title"]:
            result["title"] = clean(
                obj.get("headline")
                or obj.get("name")
                or ""
            )

        if not result["description"]:
            result["description"] = clean(
                obj.get("description")
                or ""
            )

        if not result["date"]:
            result["date"] = clean(
                obj.get("datePublished")
                or ""
            )

        if not result["author"]:
            author = obj.get("author")

            if isinstance(author, dict):
                result["author"] = clean(
                    author.get("name")
                    or ""
                )

            elif isinstance(author, list):
                for person in author:
                    if isinstance(person, dict):
                        name = clean(
                            person.get("name")
                            or ""
                        )

                        if name:
                            result["author"] = name
                            break

            elif isinstance(author, str):
                result["author"] = clean(author)

    return result


def read_article(
    source,
    url,
    today,
    yesterday
):
    html = get_html(url)

    ld = jsonld_article(html)

    title = (
        ld["title"]
        or meta_value(
            html,
            ("og:title", "twitter:title")
        )
    )

    description = (
        ld["description"]
        or meta_value(
            html,
            (
                "og:description",
                "description",
                "twitter:description",
            )
        )
    )

    author = (
        ld["author"]
        or meta_value(
            html,
            ("author", "article:author")
        )
    )

    date_raw = (
        ld["date"]
        or meta_value(
            html,
            (
                "article:published_time",
                "datePublished",
            )
        )
    )

    published = parse_iso(date_raw)

    if not published:
        match = re.search(
            r'20\d{2}-\d{2}-\d{2}T'
            r'\d{2}:\d{2}'
            r'(?::\d{2})?'
            r'(?:Z|[+-]\d{2}:\d{2})?',
            html
        )

        if match:
            published = parse_iso(
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
    description = clean(description)
    author = clean(author)

    if not title:
        return None

    return {
        "category": classify(
            title + " " + description
        ),
        "source": source,
        "author": (
            author
            or source + " Yazarı"
        ),
        "title": title,
        "summary": description,
        "speechText": description,
        "url": url,
        "day": (
            "Bugün"
            if published.date() == today
            else "Dün"
        ),
        "publishedAt":
            published.isoformat(),
    }


# -------------------------------------------------
# HABERTÜRK
# -------------------------------------------------

def collect_haberturk(
    today,
    yesterday
):
    url = (
        "https://www.haberturk.com/"
        "rss/kategori/yazarlar.xml"
    )

    root = ET.fromstring(
        get_bytes(url)
    )

    rows = []

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
                "{http://purl.org/rss/1.0/"
                "modules/content/}encoded"
            )
        )

        author = (
            clean(item.findtext("author"))
            or clean(
                item.findtext(
                    "{http://purl.org/dc/"
                    "elements/1.1/}creator"
                )
            )
        )

        raw_date = clean(
            item.findtext("pubDate")
        )

        try:
            published = (
                parsedate_to_datetime(
                    raw_date
                )
            )

            if published.tzinfo is None:
                published = published.replace(
                    tzinfo=timezone.utc
                )

            published = (
                published.astimezone(TR)
            )

        except Exception:
            continue

        if published.date() not in (
            today,
            yesterday
        ):
            continue

        text = (
            content
            if len(content) > len(description)
            else description
        )

        rows.append({
            "category":
                classify(title + " " + text),

            "source":
                "Habertürk",

            "author":
                author or "Habertürk Yazarı",

            "title":
                title,

            "summary":
                text,

            "speechText":
                text,

            "url":
                link,

            "day":
                "Bugün"
                if published.date() == today
                else "Dün",

            "publishedAt":
                published.isoformat(),
        })

    print(
        "Habertürk:",
        len(rows)
    )

    return rows


# -------------------------------------------------
# SÖZCÜ
# -------------------------------------------------

def collect_sozcu(
    today,
    yesterday
):
    page = (
        "https://www.sozcu.com.tr/yazarlar"
    )

    html = get_html(page)

    links = extract_links(
        html,
        page
    )

    candidates = []
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
        candidates.append(url)

    # Ana yazar sayfasındaki ilk 40 aday
    # bugünkü/dünkü yazılar için yeterli.
    candidates = candidates[:40]

    print(
        "Sözcü aday:",
        len(candidates)
    )

    rows = []

    for url in candidates:
        try:
            article = read_article(
                "Sözcü",
                url,
                today,
                yesterday
            )

            if article:
                rows.append(article)

        except Exception:
            continue

    print(
        "Sözcü:",
        len(rows)
    )

    return rows


# -------------------------------------------------
# CUMHURİYET
# -------------------------------------------------

def collect_cumhuriyet(
    today,
    yesterday
):
    page = (
        "https://www.cumhuriyet.com.tr/"
        "yazarlar"
    )

    html = get_html(page)

    links = extract_links(
        html,
        page
    )

    profiles = []
    seen_profiles = set()

    for url in links:

        if not re.search(
            r'https?://(?:www\.)?'
            r'cumhuriyet\.com\.tr/'
            r'yazarlar/[^/?#]+/?$',
            url,
            flags=re.I
        ):
            continue

        if url in seen_profiles:
            continue

        seen_profiles.add(url)
        profiles.append(url)

    print(
        "Cumhuriyet profil:",
        len(profiles)
    )

    candidates = []
    seen_articles = set()

    # Her profilden yalnızca ilk 2
    # gerçek köşe yazısını al.
    for profile in profiles:

        try:
            profile_html = get_html(
                profile
            )

        except Exception:
            continue

        profile_links = extract_links(
            profile_html,
            profile
        )

        author_count = 0

        for url in profile_links:

            if url in seen_articles:
                continue

            if not re.search(
                r'/yazarlar/'
                r'[^/?#]+/'
                r'[^/?#]+-\d+'
                r'(?:[/?#]|$)',
                url,
                flags=re.I
            ):
                continue

            seen_articles.add(url)
            candidates.append(url)

            author_count += 1

            if author_count >= 2:
                break

        # Sert toplam sınır:
        # 80 adaydan fazlasını
        # hiçbir durumda açma.
        if len(candidates) >= 80:
            break

    candidates = candidates[:80]

    print(
        "Cumhuriyet aday:",
        len(candidates)
    )

    rows = []

    for url in candidates:

        try:
            article = read_article(
                "Cumhuriyet",
                url,
                today,
                yesterday
            )

            if article:
                rows.append(article)

        except Exception:
            continue

    print(
        "Cumhuriyet:",
        len(rows)
    )

    return rows


# -------------------------------------------------
# ANA PROGRAM
# -------------------------------------------------

def main():

    now = datetime.now(TR)

    today = now.date()

    yesterday = (
        today
        - timedelta(days=1)
    )

    rows = []


    try:
        rows.extend(
            collect_haberturk(
                today,
                yesterday
            )
        )

    except Exception as error:
        print(
            "Habertürk hata:",
            error
        )


    try:
        rows.extend(
            collect_sozcu(
                today,
                yesterday
            )
        )

    except Exception as error:
        print(
            "Sözcü hata:",
            error
        )


    try:
        rows.extend(
            collect_cumhuriyet(
                today,
                yesterday
            )
        )

    except Exception as error:
        print(
            "Cumhuriyet hata:",
            error
        )


    # Aynı URL iki kere varsa temizle.

    final_rows = []

    seen = set()

    for article in rows:

        url = article["url"]

        if not url:
            continue

        if url in seen:
            continue

        seen.add(url)

        final_rows.append(article)


    final_rows.sort(
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
            final_rows,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


    print(
        "TOPLAM:",
        len(final_rows)
    )


if __name__ == "__main__":
    main()
