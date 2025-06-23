#!/usr/bin/env python3
import re
from io import BytesIO

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from lxml import etree as ET

BASE_URL = "https://www.sverigesradio.se"
PROGRAM_URL = BASE_URL + "/avsnitt?programid=2071"
FALLBACK_ICON = BASE_URL + "/static/img/sverigesradio-icon-192.png"
FEED_TITLE = "Sommar & Vinter i P1 – inofficiellt RSS-flöde"
OUTPUT_FILE = "podcast.xml"
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"

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
    ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
    ATOM_NS = "http://www.w3.org/2005/Atom"
    CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"

    fg = FeedGenerator()
    fg.title(FEED_TITLE)
    fg.link(href=PROGRAM_URL)
    fg.description("Automatiskt RSS-flöde genererat från Sveriges Radios webbsida.")

    channel_image = fetch_program_image()
    fg.image(url=channel_image, title=FEED_TITLE, link=PROGRAM_URL)
    fg.language('sv-SE')
    fg.generator('python-feedgen')
    fg.category(term="Society & Culture")

    # (itunes:explicit kräver hack, vi gör det i efterbearbetningen)
    # Samma för itunes:category och kanalbild

    # Skapa lookup för bild per guid (länk)
    guid_to_image = {}
    for ep in episodes:
        fe = fg.add_entry()
        fe.title(ep["title"])
        fe.link(href=ep["link"])
        fe.pubDate(ep["date"])
        fe.guid(ep["link"], permalink=True)
        if ep["description"]:
            fe.description(ep["description"])
        if ep.get("audio"):
            fe.enclosure(ep["audio"], 0, "audio/mpeg")
        if ep.get("image"):
            html = f'<img src="{ep["image"]}" alt="{ep["title"]}"/><p>{ep["description"]}</p>'
            fe.content(content=html, type="CDATA")
            guid_to_image[ep["link"]] = ep["image"]

    rss_bytes = fg.rss_str(pretty=True)

    # Registrera namespaces innan vi bygger vidare
    ET.register_namespace("content", CONTENT_NS)
    ET.register_namespace("itunes", ITUNES_NS)
    ET.register_namespace("atom", ATOM_NS)

    tree = ET.parse(BytesIO(rss_bytes))
    root = tree.getroot()
    channel = root.find("channel")

    # 1. <atom:link rel="self" ...>
    atom_link = ET.Element("{%s}link" % ATOM_NS, {
        "href": "https://yourserv.er/podcast.xml",
        "rel": "self",
        "type": "application/rss+xml"
    })
    channel.insert(0, atom_link)

    # 2. <language> om den inte finns
    if channel.find("language") is None:
        language = ET.Element("language")
        language.text = "sv-SE"
        channel.insert(1, language)

    # 3. <itunes:category>
    ET.SubElement(
        channel,
        "{%s}category" % ITUNES_NS,
        {"text": "Society & Culture"},
    )

    # 4. <itunes:explicit>
    ET.SubElement(
        channel,
        "{%s}explicit" % ITUNES_NS
    ).text = "no"

    # 5. <itunes:image> för kanal
    itunes_image = ET.Element("{%s}image" % ITUNES_NS, {"href": channel_image})
    channel.insert(len(channel.findall("./*")) - len(channel.findall("./item")), itunes_image)

    # 6. <itunes:image> per avsnitt, kopplat via GUID/LINK
    for item in channel.findall("item"):
        guid = item.find("guid")
        if guid is not None and guid.text in guid_to_image:
            ET.SubElement(
                item,
                "{%s}image" % ITUNES_NS,
                {"href": guid_to_image[guid.text]},
            )

    # 7. CDATA för <content:encoded>
    for encoded in root.findall(".//{%s}encoded" % CONTENT_NS):
        if encoded.text and not isinstance(encoded.text, ET.CDATA):
            encoded.text = ET.CDATA(encoded.text)

    # Skriv ut till fil (kan ge onödiga ns-prefix)
    tree.write(filename, encoding="utf-8", xml_declaration=True, pretty_print=True)

    # Sista fix: sanera namespace och snygga radbrytningar
    with open(filename, "r", encoding="utf-8") as f:
        xml = f.read()
    xml = re.sub(r'\s+xmlns:itunes="[^"]+"', '', xml)
    xml = re.sub(r'\s+ns\d+:itunes="[^"]+"', '', xml)
    xml = re.sub(r'\s+xmlns:ns\d+="[^"]+"', '', xml)
    xml = re.sub(
        r'(<rss [^>]+)',
        r'\1 xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"',
        xml,
        count=1
    )
    xml = re.sub(r'(<pubDate>.+?</pubDate>)(<itunes:image)', r'\1\n      \2', xml)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"✅ RSS-flöde sparat som {filename}")

if __name__ == "__main__":
    episodes = fetch_episodes()
    generate_rss(episodes)

