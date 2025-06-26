#!/usr/bin/env python3
import datetime
import json
import os
import random
import re
import time
import uuid
from email.utils import format_datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from feedgen.feed import FeedGenerator
from lxml import etree

BASE_URL = "https://www.sverigesradio.se"
PROGRAM_URL = BASE_URL + "/avsnitt?programid=2071"
CHANNEL_URL = "https://www.sverigesradio.se/sommar-i-p1"
API_IMAGE_URL = "https://static-cdn.sr.se/images/2071/138fda3c-4e35-48e0-8fdb-e2ea8ef44758.jpg?preset=api-itunes-presentation-image"
FEED_TITLE = "Sommar & Vinter i P1 – inofficiellt RSS-flöde"
FALLBACK_ICON = (
    "https://static-cdn.sr.se/images/2071/138fda3c-4e35-48e0-8fdb-e2ea8ef44758.jpg"
)


load_dotenv()

# Ställ in debug
debug_env = os.environ.get("DEBUG", "false").strip().lower()
DEBUG = debug_env in ("1", "true", "yes", "on")

# Ställ in output-fil
rss_env = os.environ.get("RSS_FILE", "sommar_i_p1.xml").strip()
OUTPUT_FILE = rss_env if rss_env else "sommar_i_p1.xml"

# Ställ in cache-fil
cache_env = os.environ.get("CACHE_FILE", "cache.json").strip()
CACHE_FILE = cache_env if cache_env else "cache.json"

# Ställ in feed url
feed_env = os.environ.get("FEED_URL", "localhost/sommar_i_p1.xml").strip()
FEED_URL = feed_env if feed_env else "localhost/sommar_i_p1.xml"


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def fetch_program_image():
    try:
        resp = requests.get(PROGRAM_URL)
        soup = BeautifulSoup(resp.content, "html.parser")
        # Leta efter kvadratisk programikon
        img_el = soup.select_one(".program-menu__image-wrapper .image--square img")
        if img_el and img_el.get("src"):
            base_img = clean_image_url(img_el["src"])
            return base_img
    except Exception as e:
        print(f"⚠️ Kunde inte hämta kanalbild: {e}")
    return FALLBACK_ICON


def get_mp3_size(url):
    try:
        for attempt in range(2):  # Testa max två gånger
            r = requests.get(url, stream=True, timeout=10)
            length = int(r.headers.get("Content-Length", 0))
            if length > 0:
                break
            pause = random.uniform(0.75, 2.5)
            time.sleep(pause)
        return length
    except Exception as e:
        print(f"⚠️ Fel vid hämtning av filstorlek: {e}")
        return 0


def fix_xml_declaration(xml_path):
    with open(xml_path, "r", encoding="utf-8") as f:
        xml = f.read()
    # Ta bort ev. gammal declaration
    xml = re.sub(r"^<\?xml.*?\?>\s*", "", xml)
    # Lägg in korrekt rad
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)


def generate_podcast_guid(feed_url):
    # Strip protocol and trailing slash
    url = feed_url.replace("https://", "").replace("http://", "").rstrip("/")
    namespace = uuid.UUID("ead4c236-bf58-58c6-a2c6-a6b28d128cb6")
    return str(uuid.uuid5(namespace, url))


def ensure_podcast_namespace(xml_path):
    with open(xml_path, "r", encoding="utf-8") as f:
        xml = f.read()

    if "xmlns:podcast=" not in xml:
        # Sätt in namespace-attributet i <rss ...>
        xml = re.sub(
            r"(<rss\b[^>]*?)>",
            r'\1 xmlns:podcast="https://podcastindex.org/namespace/1.0">',
            xml,
            count=1,
        )

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)


def add_podcast_guid_to_rss(xml_path, guid):
    with open(xml_path, "r", encoding="utf-8") as f:
        xml = f.read()
    # Kontrollera om redan finns
    if "<podcast:guid>" in xml:
        return  # Redan inlagd
    # Lägg in efter <channel> eller direkt efter <title>
    xml = re.sub(
        r"(<channel>\s*)",
        r"\1<podcast:guid>{}</podcast:guid>\n".format(guid),
        xml,
        count=1,
    )
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)


def clean_image_url(url):
    """Returnerar endast .jpg/.png-delen av URL."""
    if not url:
        return url
    match = re.match(r"^(.*\.(?:jpg|png))", url, re.IGNORECASE)
    if match:
        return match.group(1)
    return url  # fallback: returnera som den är


def parse_duration(abbr_text):
    abbr_text = abbr_text.lower().replace("–", "-")
    # "1 timme 2 min", "2 timmar 5 min", "59 min", "2 tim"
    h, m = 0, 0
    # Försök hitta timmar och minuter
    match = re.search(r"(\d+)\s*tim", abbr_text)
    if match:
        h = int(match.group(1))
    match = re.search(r"(\d+)\s*min", abbr_text)
    if match:
        m = int(match.group(1))
    total_sec = h * 3600 + m * 60
    return str(total_sec)


def fetch_episodes():
    cache = load_cache()
    resp = requests.get(PROGRAM_URL)
    soup = BeautifulSoup(resp.content, "html.parser")
    episodes = []
    current_audio_urls = set()
    for item in soup.select("div.episode-list-item"):
        try:
            title_el = item.select_one(".audio-heading__title a")
            date_el = item.select_one(".audio-heading__meta time")
            desc_el = item.select_one(".episode-list-item__description p")
            mp3_el = item.select_one("a[href*='topsy/ljudfil']")
            img_el = item.select_one("img")
            abbr_el = item.select_one(".audio-heading__meta abbr")

            if not (title_el and date_el and mp3_el):
                continue

            title = title_el.text.strip()
            page_link = BASE_URL + title_el["href"]
            pub_date_raw = date_el["datetime"]
            pub_date_dt = datetime.datetime.strptime(pub_date_raw, "%Y-%m-%d %H:%M:%SZ")
            pub_date_rfc = format_datetime(pub_date_dt)
            pub_date = pub_date_rfc

            description = desc_el.text.strip() if desc_el else ""

            audio_url = mp3_el["href"]
            if audio_url.startswith("//"):
                audio_url = "https:" + audio_url
            elif audio_url.startswith("/"):
                audio_url = BASE_URL + audio_url

            current_audio_urls.add(audio_url)

            if audio_url in cache:
                if DEBUG:
                    print(f"[CACHE] {title} ({audio_url})")
                episode = cache[audio_url]
            else:
                if DEBUG:
                    print(f"[FETCH] {title} ({audio_url})")
                # Bild-url
                image_url = None
                if img_el:
                    image_url = img_el.get("data-src") or img_el.get("src")
                    if image_url:
                        if image_url.startswith("//"):
                            image_url = "https:" + image_url
                        elif image_url.startswith("/"):
                            image_url = BASE_URL + image_url
                    image_url = clean_image_url(image_url)

                # Duration
                duration = None
                if abbr_el:
                    duration = parse_duration(abbr_el.text.strip())

                # Size
                size = get_mp3_size(audio_url)

                # Itunes subtitle och summary: samma som description, eller om du vill generera bättre (t.ex. extrahera första meningen)
                itunes_subtitle = description
                itunes_summary = description

                # Itunes author
                itunes_author = "Sveriges Radio"  # statiskt, kan ibland vara annorlunda i originalet

                episode = {
                    "title": title,
                    "link": page_link,
                    "audio": audio_url,
                    "date": pub_date,
                    "description": description,
                    "image": image_url,
                    "duration": duration,
                    "size": size,
                    "itunes_author": itunes_author,
                    "itunes_summary": itunes_summary,
                    "itunes_subtitle": itunes_subtitle,
                    # "guid": ...  # Om du vill särskilja från länk
                }
                cache[audio_url] = episode
            episodes.append(episode)
        except Exception as e:
            print(f"⚠️ Fel vid parsning: {e}")

    for cached_url in list(cache):
        if cached_url not in current_audio_urls:
            if DEBUG:
                print(f"[REMOVE] Tar bort cache för {cached_url}")
            del cache[cached_url]

    save_cache(cache)
    return episodes


def fix_channel_link(xml_path, program_url=CHANNEL_URL):
    with open(xml_path, "r", encoding="utf-8") as f:
        xml = f.read()
    xml = re.sub(
        r"<channel>\s*(<podcast:guid>.*?</podcast:guid>\s*)?<title>.*?</title>\s*<link>.*?</link>",
        lambda m: m.group(0).replace(
            re.search(r"<link>.*?</link>", m.group(0)).group(0),
            f"<link>{program_url}</link>",
        ),
        xml,
        flags=re.DOTALL,
    )
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)


def fix_channel_images(
    xml_path, channel_url, image_url, preset="api-itunes-presentation-image"
):
    with open(xml_path, "r", encoding="utf-8") as f:
        xml = f.read()

    # 1. Ersätt <image><link>...</link> med <image><link>{channel_url}</link>
    xml = re.sub(
        r"(<image>.*?<title>.*?</title>\s*<link>)(.*?)(</link>)",
        r"\1" + channel_url + r"\3",
        xml,
        flags=re.DOTALL,
    )
    # 2. Ersätt <image><url>...</url> med exakt image_url (med preset)
    xml = re.sub(
        r"(<image>\s*<url>)(.*?)(</url>)",
        r"\1" + image_url + r"\3",
        xml,
        flags=re.DOTALL,
    )

    # 3. Sätt preset på alla https://static-cdn.sr.se/images/...jpg eller png i itunes:image etc (om ej redan preset)
    def add_preset(m):
        url = m.group(1)
        if "preset=" not in url:
            return f'{url}?preset={preset}"'
        else:
            return m.group(0)

    xml = re.sub(
        r'(https://static-cdn\.sr\.se/images/[0-9]+/[a-f0-9\-]+\.(?:jpg|png))"',
        add_preset,
        xml,
    )

    # TA BORT preset för bilder i <content:encoded>
    # Ersätt t.ex. src="...jpg?pres...ion-image" med src="...jpg"
    xml = re.sub(
        r'(<content:encoded>.*?src="https://static-cdn\.sr\.se/images/[0-9]+/[a-f0-9\-]+\.jpg)\?preset=[^"]*(".*?</content:encoded>)',
        r"\1\2",
        xml,
        flags=re.DOTALL,
    )

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)


def fix_itunes_explicit(xml_path):
    with open(xml_path, "r", encoding="utf-8") as f:
        xml = f.read()
    # Byt ut alla <itunes:explicit>no</itunes:explicit> till <itunes:explicit>false</itunes:explicit>
    xml = re.sub(
        r"<itunes:explicit>\s*no\s*</itunes:explicit>",
        r"<itunes:explicit>false</itunes:explicit>",
        xml,
        flags=re.IGNORECASE,
    )
    # (Om du skulle ha TRUE, byt ut eventuellt "yes" mot "true" också)
    xml = re.sub(
        r"<itunes:explicit>\s*yes\s*</itunes:explicit>",
        r"<itunes:explicit>true</itunes:explicit>",
        xml,
        flags=re.IGNORECASE,
    )
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)


def generate_rss(episodes, filename=OUTPUT_FILE):
    fg = FeedGenerator()
    fg.load_extension("podcast")

    fg.title(FEED_TITLE)
    fg.link(href=CHANNEL_URL, rel="alternate")
    fg.link(href=FEED_URL, rel="self", type="application/rss+xml")
    fg.language("sv")
    fg.logo(fetch_program_image())
    fg.generator("python-feedgen")
    desc_plain = "Inofficiellt RSS-flöde automatiskt genererat från Sveriges Radio. Alla Sommarprat finns att lyssna på i Sveriges Radio Play."
    fg.podcast.itunes_summary(desc_plain)
    fg.description(desc_plain)
    fg.copyright("Copyright Sveriges Radio 2025. All rights reserved.")

    fg.id(FEED_URL)
    fg.podcast.itunes_author("Sveriges Radio")
    fg.podcast.itunes_category("Society & Culture")
    fg.podcast.itunes_explicit("no")
    fg.podcast.itunes_image(fetch_program_image())

    for ep in episodes:
        fe = fg.add_entry()
        fe.title(ep["title"])
        fe.link(href=ep["link"])
        fe.podcast.itunes_duration(ep.get("duration", "00:00:00"))
        fe.podcast.itunes_image(ep["image"])
        fe.podcast.itunes_summary(ep.get("itunes_summary", ep["description"]))
        fe.podcast.itunes_author(ep.get("itunes_author", "Sveriges Radio"))
        fe.podcast.itunes_subtitle(ep.get("itunes_subtitle", ep["description"]))
        fe.pubDate(ep["date"])
        fe.guid(ep["link"], permalink=True)
        fe.description(ep["description"])
        fe.enclosure(ep["audio"], ep["size"], "audio/mpeg")
        fe.podcast.itunes_explicit("no")
        html = (
            f'<p>{ep["description"]}</p><img src="{ep["image"]}" alt="{ep["title"]}"/>'
        )
        fe.content(content=html, type="CDATA")

    fg.rss_file(filename, pretty=True)
    if DEBUG:
        print(f"[FEEDGEN] RSS-flöde genererat med {len(episodes)} avsnitt.")
    guid = generate_podcast_guid(FEED_URL)
    ensure_podcast_namespace(filename)
    if DEBUG:
        print(f"[GUID] Genererad podcast GUID: {guid}")
    add_podcast_guid_to_rss(filename, guid)
    fix_itunes_explicit(filename)
    if DEBUG:
        print(f"[ITUNES] Fixade explicit tag i {filename}")
    fix_channel_link(filename, CHANNEL_URL)
    if DEBUG:
        print(f"[ITUNES] Fixade channel link i {filename}")
    fix_channel_images(OUTPUT_FILE, CHANNEL_URL, API_IMAGE_URL)
    if DEBUG:
        print(f"[ITUNES] Fixade image link i {filename}")
    if DEBUG:
        print(f"[XML] XML-tidy utförd på {filename}")
    fix_xml_declaration(filename)
    if DEBUG:
        print(f"[XML] Fixade XML-deklaration i {filename}")
    print(f"✅ RSS-flöde sparat som {filename}")


if __name__ == "__main__":
    episodes = fetch_episodes()
    generate_rss(episodes)
