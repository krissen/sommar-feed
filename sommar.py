#!/usr/bin/env python3
import re

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

BASE_URL = "https://www.sverigesradio.se"
PROGRAM_URL = BASE_URL + "/avsnitt?programid=2071"
FALLBACK_ICON = BASE_URL + "/static/img/sverigesradio-icon-192.png"
FEED_TITLE = "Sommar & Vinter i P1 – inofficiellt RSS-flöde"
OUTPUT_FILE = "podcast.xml"

def fetch_program_image():
    try:
        resp = requests.get(PROGRAM_URL)
        soup = BeautifulSoup(resp.content, "html.parser")
        tag = soup.find("link", rel="image_src")
        if tag and tag.get("href"):
            return tag["href"]
    except Exception as e:
        print(f"⚠️ Kunde inte hämta kanalbild: {e}")
    return FALLBACK_ICON

def clean_image_url(url):
    """Returnerar endast .jpg/.png-delen av URL."""
    if not url:
        return url
    match = re.match(r"^(.*\.(?:jpg|png))", url, re.IGNORECASE)
    if match:
        return match.group(1)
    return url  # fallback: returnera som den är

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
                # Rensa preset eller andra querystrings
                image_url = clean_image_url(image_url)


            episodes.append({
                "title": title,
                "link": page_link,
                "audio": audio_url,
                "date": pub_date,
                "description": description,
                "image": image_url,
            })
        except Exception as e:
            print(f"⚠️ Fel vid parsning: {e}")
    return episodes

def generate_rss(episodes, filename=OUTPUT_FILE):
    fg = FeedGenerator()
    fg.load_extension('podcast')

    fg.title(FEED_TITLE)
    fg.link(href=PROGRAM_URL, rel="alternate")
    fg.link(href="https://yourserv.er/podcast.xml", rel="self", type="application/rss+xml")
    fg.language('sv-SE')
    fg.generator('python-feedgen')
    fg.description("Automatiskt RSS-flöde genererat från Sveriges Radios webbsida.")
    fg.podcast.itunes_author("Sveriges Radio")
    fg.podcast.itunes_category("Society & Culture")
    fg.podcast.itunes_explicit("no")
    fg.podcast.itunes_image(fetch_program_image())

    for ep in episodes:
        fe = fg.add_entry()
        fe.title(ep["title"])
        fe.link(href=ep["link"])
        fe.podcast.itunes_image(ep["image"])
        fe.podcast.itunes_summary(ep["description"])
        fe.pubDate(ep["date"])
        fe.guid(ep["link"], permalink=True)
        fe.description(ep["description"])
        fe.enclosure(ep["audio"], 0, "audio/mpeg")
        fe.podcast.itunes_subtitle(ep["description"])
        fe.podcast.itunes_explicit("no")
        html = f'<p>{ep["description"]}</p><img src="{ep["image"]}" alt="{ep["title"]}"/>'
        fe.content(content=html, type="CDATA")

    fg.rss_file(filename, pretty=True)
    print(f"✅ RSS-flöde sparat som {filename}")

if __name__ == "__main__":
    episodes = fetch_episodes()
    generate_rss(episodes)

