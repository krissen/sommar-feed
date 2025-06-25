#!/usr/bin/env python3
import random
import re
import time
import uuid

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

BASE_URL = "https://www.sverigesradio.se"
PROGRAM_URL = BASE_URL + "/avsnitt?programid=2071"
FALLBACK_ICON = (
    "https://static-cdn.sr.se/images/2071/138fda3c-4e35-48e0-8fdb-e2ea8ef44758.jpg"
)
FEED_TITLE = "Sommar & Vinter i P1 – inofficiellt RSS-flöde"
FEED_URL = "https://yourserv.er/podcast.xml"
OUTPUT_FILE = "podcast.xml"
IMAGE_SIZE = 2048


def fetch_program_image():
    try:
        resp = requests.get(PROGRAM_URL)
        soup = BeautifulSoup(resp.content, "html.parser")
        # Leta efter kvadratisk programikon
        img_el = soup.select_one(".program-menu__image-wrapper .image--square img")
        if img_el and img_el.get("src"):
            base_img = clean_image_url(img_el["src"])
            # return get_image_preset(base_img)
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
            pause = random.uniform(0.25, 1.5)
            time.sleep(pause)
        return length
    except Exception as e:
        print(f"⚠️ Fel vid hämtning av filstorlek: {e}")
        return 0


def generate_podcast_guid(feed_url):
    # Strip protocol and trailing slash
    url = feed_url.replace("https://", "").replace("http://", "").rstrip("/")
    namespace = uuid.UUID("ead4c236-bf58-58c6-a2c6-a6b28d128cb6")
    return str(uuid.uuid5(namespace, url))


def postprocess_images(xml_path, preset="2048x2048"):
    with open(xml_path, "r", encoding="utf-8") as f:
        xml = f.read()

    # Byt ut alla ...jpg eller ...png (utan ? och med valfria querys) mot ...jpg?preset=2048x2048
    # men undvik att lägga till preset två gånger
    def add_preset(m):
        url = m.group(1)
        if "preset=" not in url:
            return f'{url}?preset={preset}"'
        else:
            return m.group(0)

    # itunes:image
    xml = re.sub(
        r'(https://static-cdn\.sr\.se/images/[0-9]+/[a-f0-9\-]+\.(?:jpg|png))"',
        add_preset,
        xml,
    )
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)


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
    soup = BeautifulSoup(xml, "xml")

    channel = soup.find("channel")
    if channel:
        # Kontrollera om redan finns
        if not channel.find("podcast:guid"):
            tag = soup.new_tag("podcast:guid")
            tag.string = guid
            channel.insert(1, tag)  # Efter <title>
    # Spara tillbaka
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(str(soup))


def clean_image_url(url):
    """Returnerar endast .jpg/.png-delen av URL."""
    if not url:
        return url
    match = re.match(r"^(.*\.(?:jpg|png))", url, re.IGNORECASE)
    if match:
        return match.group(1)
    return url  # fallback: returnera som den är


def get_image_preset(img_base_url):
    size = IMAGE_SIZE
    url = f"{img_base_url}?preset={size}x{size}"
    r = requests.head(url)
    if r.status_code == 200:
        return url
    # fallback: använd orginal url utan preset
    return img_base_url


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
    resp = requests.get(PROGRAM_URL)
    soup = BeautifulSoup(resp.content, "html.parser")
    episodes = []
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
            pub_date = date_el["datetime"]
            description = desc_el.text.strip() if desc_el else ""

            audio_url = mp3_el["href"]
            if audio_url.startswith("//"):
                audio_url = "https:" + audio_url
            elif audio_url.startswith("/"):
                audio_url = BASE_URL + audio_url

            image_url = None
            if img_el:
                image_url = img_el.get("data-src") or img_el.get("src")
                if image_url:
                    if image_url.startswith("//"):
                        image_url = "https:" + image_url
                    elif image_url.startswith("/"):
                        image_url = BASE_URL + image_url
                # Rensa preset eller andra querystrings
                image_url = clean_image_url(image_url)
                # image_url = get_image_preset(image_url_clean)

            duration = None
            if abbr_el:
                duration = parse_duration(abbr_el.text.strip())

            episodes.append(
                {
                    "title": title,
                    "link": page_link,
                    "audio": audio_url,
                    "date": pub_date,
                    "description": description,
                    "image": image_url,
                    "duration": duration,
                }
            )
        except Exception as e:
            print(f"⚠️ Fel vid parsning: {e}")
    return episodes


def generate_rss(episodes, filename=OUTPUT_FILE):
    fg = FeedGenerator()
    fg.load_extension("podcast")

    fg.title(FEED_TITLE)
    fg.link(href=PROGRAM_URL, rel="alternate")
    fg.link(href=FEED_URL, rel="self", type="application/rss+xml")
    fg.language("sv-SE")
    fg.logo(fetch_program_image())
    fg.generator("python-feedgen")
    fg.description("Automatiskt RSS-flöde genererat från Sveriges Radios webbsida.")
    fg.id(FEED_URL)
    fg.podcast.itunes_author("Sveriges Radio")
    fg.podcast.itunes_category("Society & Culture")
    fg.podcast.itunes_explicit("no")
    fg.podcast.itunes_image(fetch_program_image())

    for ep in episodes:
        size = get_mp3_size(ep["audio"])
        fe = fg.add_entry()
        fe.title(ep["title"])
        fe.link(href=ep["link"])
        fe.podcast.itunes_duration(ep.get("duration", "00:00:00"))
        fe.podcast.itunes_image(ep["image"])
        fe.podcast.itunes_summary(ep["description"])
        fe.pubDate(ep["date"])
        fe.guid(ep["link"], permalink=True)
        fe.description(ep["description"])
        fe.enclosure(ep["audio"], size, "audio/mpeg")
        fe.podcast.itunes_subtitle(ep["description"])
        fe.podcast.itunes_explicit("no")
        html = (
            f'<p>{ep["description"]}</p><img src="{ep["image"]}" alt="{ep["title"]}"/>'
        )
        fe.content(content=html, type="CDATA")

    fg.rss_file(filename, pretty=True)
    guid = generate_podcast_guid(FEED_URL)
    ensure_podcast_namespace(filename)
    add_podcast_guid_to_rss(filename, guid)
    postprocess_images(filename)
    print(f"✅ RSS-flöde sparat som {filename}")


if __name__ == "__main__":
    episodes = fetch_episodes()
    generate_rss(episodes)
