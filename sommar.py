#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from xml.dom import minidom

BASE_URL = "https://www.sverigesradio.se"
PROGRAM_URL = BASE_URL + "/avsnitt?programid=2071"
FEED_ICON = BASE_URL + "/static/img/sverigesradio-icon-192.png"
FEED_TITLE = "Sommar & Vinter i P1 – inofficiellt RSS-flöde"
OUTPUT_FILE = "podcast.xml"

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

            # Beskrivning
            description = ""
            if desc_el:
                description = desc_el.text.strip()

            # Ljudfil
            audio_url = mp3_el["href"]
            if audio_url.startswith("//"):
                audio_url = "https:" + audio_url
            elif audio_url.startswith("/"):
                audio_url = BASE_URL + audio_url

            # Bild
            image_url = None
            if img_el:
                image_url = img_el.get("data-src") or img_el.get("src")
                if image_url and image_url.startswith("//"):
                    image_url = "https:" + image_url
                elif image_url and image_url.startswith("/"):
                    image_url = BASE_URL + image_url

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
    fg.title(FEED_TITLE)
    fg.link(href=PROGRAM_URL)
    fg.description("Automatiskt RSS-flöde genererat från Sveriges Radios webbsida.")
    fg.image(url=FEED_ICON, title=FEED_TITLE, link=PROGRAM_URL)

    for ep in episodes:
        fe = fg.add_entry()
        fe.title(ep["title"])
        fe.link(href=ep["link"])
        fe.pubDate(ep["date"])

        if ep["description"]:
            fe.description(ep["description"])
        
        # ✅ Ljudfil måste vara först och vara av type='audio/mpeg'
        if ep.get("audio"):
            fe.enclosure(ep["audio"], 0, 'audio/mpeg')
        
        # 💡 Alternativt: lägg bild som extra HTML i content (för vissa läsare)
        if ep.get("image"):
            html = f'<img src="{ep["image"]}" alt="{ep["title"]}"/>'
            fe.content(content=html, type="CDATA")

    # Vackert format
    rss_str = fg.rss_str(pretty=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(rss_str.decode("utf-8"))
        print(f"✅ RSS-flöde sparat som {filename}")

if __name__ == "__main__":
    episodes = fetch_episodes()
    generate_rss(episodes)

