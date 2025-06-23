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
    AUTHOR = "Sveriges Radio"

    fg = FeedGenerator()
    fg.title(FEED_TITLE)
    fg.link(href=PROGRAM_URL)
    fg.description("Automatiskt RSS-flöde genererat från Sveriges Radios webbsida.")

    channel_image = fetch_program_image()
    fg.image(url=channel_image, title=FEED_TITLE, link=PROGRAM_URL)
    fg.language('sv-SE')
    fg.generator('python-feedgen')
    fg.category(term="Society & Culture")

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

    # Registrera namespaces
    ET.register_namespace("content", CONTENT_NS)
    ET.register_namespace("itunes", ITUNES_NS)
    ET.register_namespace("atom", ATOM_NS)
    # podcastindex namespace, valfritt
    ET.register_namespace("podcast", "https://podcastindex.org/namespace/1.0")

    tree = ET.parse(BytesIO(rss_bytes))
    root = tree.getroot()
    channel = root.find("channel")

    # Bestäm position för första <item>
    first_item_pos = 0
    for idx, child in enumerate(channel):
        if child.tag == "item":
            first_item_pos = idx
            break
    else:
        first_item_pos = len(channel)

    # För in alla nödvändiga channel-element FÖRE första <item>
    insert_pos = first_item_pos

    # <language> (om ej redan finns)
    if channel.find("language") is None:
        lang_el = ET.Element("language")
        lang_el.text = "sv-SE"
        channel.insert(insert_pos, lang_el)
        insert_pos += 1

    # <itunes:category>
    itunes_cat = ET.Element("{%s}category" % ITUNES_NS, {"text": "Society & Culture"})
    channel.insert(insert_pos, itunes_cat)
    insert_pos += 1

    # <itunes:author>
    itunes_author = ET.Element("{%s}author" % ITUNES_NS)
    itunes_author.text = AUTHOR
    channel.insert(insert_pos, itunes_author)
    insert_pos += 1

    # <itunes:explicit>
    itunes_exp = ET.Element("{%s}explicit" % ITUNES_NS)
    itunes_exp.text = "no"
    channel.insert(insert_pos, itunes_exp)
    insert_pos += 1

    # <itunes:image>
    itunes_img = ET.Element("{%s}image" % ITUNES_NS, {"href": channel_image})
    channel.insert(insert_pos, itunes_img)
    insert_pos += 1

    # <atom:link rel="self" ...>
    atom_link = ET.Element("{%s}link" % ATOM_NS, {
        "href": "https://yourserv.er/podcast.xml",
        "rel": "self",
        "type": "application/rss+xml"
    })
    channel.insert(insert_pos, atom_link)
    insert_pos += 1

    # <author> (vanlig)
    author = ET.Element("author")
    author.text = AUTHOR
    channel.insert(insert_pos, author)
    insert_pos += 1

    # <itunes:image> per avsnitt
    for item in channel.findall("item"):
        guid = item.find("guid")
        if guid is not None and guid.text in guid_to_image:
            ET.SubElement(
                item,
                "{%s}image" % ITUNES_NS,
                {"href": guid_to_image[guid.text]},
            )

    # CDATA för <content:encoded>
    for encoded in root.findall(".//{%s}encoded" % CONTENT_NS):
        if encoded.text and not isinstance(encoded.text, ET.CDATA):
            encoded.text = ET.CDATA(encoded.text)

    # Skriv ut till fil (kan ge ns-prefix som fixas nedan)
    tree.write(filename, encoding="utf-8", xml_declaration=True, pretty_print=True)

    # Sanera namespaces och radbrytning för itunes:image
    with open(filename, "r", encoding="utf-8") as f:
        xml = f.read()
    xml = re.sub(r'\s+xmlns:itunes="[^"]+"', '', xml)
    xml = re.sub(r'\s+ns\d+:itunes="[^"]+"', '', xml)
    xml = re.sub(r'\s+xmlns:ns\d+="[^"]+"', '', xml)
    # podcastindex namespace (om du vill ha den)
    xml = re.sub(
        r'(<rss [^>]+)',
        r'\1 xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"',
        xml,
        count=1
    )
    xml = re.sub(
        r'(<rss [^>]+)',
        r'\1 xmlns:podcast="https://podcastindex.org/namespace/1.0"',
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

