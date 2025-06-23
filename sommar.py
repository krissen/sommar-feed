#!/usr/bin/env python3
from io import BytesIO
import re

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from lxml import etree as ET

BASE_URL = "https://www.sverigesradio.se"
PROGRAM_URL = BASE_URL + "/avsnitt?programid=2071"
FALLBACK_ICON = BASE_URL + "/static/img/sverigesradio-icon-192.png"
FEED_TITLE = "Sommar & Vinter i P1 – inofficiellt RSS-flöde"
OUTPUT_FILE = "podcast.xml"

def fetch_program_image():
    """Hämta kanalbild från <link rel='image_src'>"""
    try:
        resp = requests.get(PROGRAM_URL)
        soup = BeautifulSoup(resp.content, "html.parser")
        tag = soup.find("link", rel="image_src")
        if tag and tag.get("href"):
            return tag["href"]
    except Exception as e:
        print(f"⚠️ Kunde inte hämta kanalbild: {e}")
    return FALLBACK_ICON

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

            episodes.append(
                {
                    "title": title,
                    "link": page_link,
                    "audio": audio_url,
                    "date": pub_date,
                    "description": description,
                    "image": image_url,
                }
            )
        except Exception as e:
            print(f"⚠️ Fel vid parsning: {e}")

    return episodes

def generate_rss(episodes, filename=OUTPUT_FILE):
    fg = FeedGenerator()
    fg.title(FEED_TITLE)
    fg.link(href=PROGRAM_URL)
    fg.description("Automatiskt RSS-flöde genererat från Sveriges Radios webbsida.")

    channel_image = fetch_program_image()
    fg.image(url=channel_image, title=FEED_TITLE, link=PROGRAM_URL)

    for ep in episodes:
        fe = fg.add_entry()
        fe.title(ep["title"])
        fe.link(href=ep["link"])
        fe.pubDate(ep["date"])
        if ep["description"]:
            fe.description(ep["description"])
        if ep.get("audio"):
            fe.enclosure(ep["audio"], 0, "audio/mpeg")
        if ep.get("image"):
            html = f'<img src="{ep["image"]}" alt="{ep["title"]}"/><p>{ep["description"]}</p>'
            fe.content(content=html, type="CDATA")

    rss_bytes = fg.rss_str(pretty=True)

    # Registrera namespaces innan vi bygger vidare
    ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")
    ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")

    tree = ET.parse(BytesIO(rss_bytes))
    root = tree.getroot()
    channel = root.find("channel")

    # Lägg till kanalbild manuellt (itunes:image)
    ET.SubElement(
        channel,
        "{http://www.itunes.com/dtds/podcast-1.0.dtd}image",
        {"href": channel_image},
    )

    # Lägg till per-avsnitt itunes:image
    for ep, item in zip(episodes, channel.findall("item")):
        if ep.get("image"):
            ET.SubElement(
                item,
                "{http://www.itunes.com/dtds/podcast-1.0.dtd}image",
                {"href": ep["image"]},
            )

    # CDATA-wrap för content:encoded
    for encoded in root.findall(".//{http://purl.org/rss/1.0/modules/content/}encoded"):
        if encoded.text and not isinstance(encoded.text, ET.CDATA):
            encoded.text = ET.CDATA(encoded.text)

    # Skriv ut till fil (tillfälligt, ev. fortfarande med ns0)
    tree.write(filename, encoding="utf-8", xml_declaration=True, pretty_print=True)

    # Sista fix: byt ns0:itunes till xmlns:itunes och ta bort xmlns:ns0 om den finns
    with open(filename, "r", encoding="utf-8") as f:
        xml = f.read()
    xml = re.sub(r'ns\d+:itunes=', 'xmlns:itunes=', xml)
    xml = re.sub(r'xmlns:ns\d+="http://www.w3.org/2000/xmlns/" ?', '', xml)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(xml)
    # Sista fix
    with open(filename, "r", encoding="utf-8") as f:
        xml = f.read()
    xml = re.sub(r'ns\d+:itunes=', 'xmlns:itunes=', xml)
    xml = re.sub(r'xmlns:ns\d+="http://www.w3.org/2000/xmlns/" ?', '', xml)
    xml = re.sub(r'(<itunes:image) xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"', r'\1', xml)

    xml = re.sub(r'(</item>)', r'\1\n', xml)
    xml = re.sub(r'    <itunes', '      <itunes', xml)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"✅ RSS-flöde sparat som {filename}")

if __name__ == "__main__":
    episodes = fetch_episodes()
    generate_rss(episodes)

