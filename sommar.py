#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

BASE_URL = "https://www.sverigesradio.se"
PROGRAM_URL = BASE_URL + "/avsnitt?programid=2071"

def fetch_episodes():
    resp = requests.get(PROGRAM_URL)
    soup = BeautifulSoup(resp.content, "html.parser")
    episodes = []

    for item in soup.select("div.episode-list-item"):
        try:
            title_el = item.select_one(".audio-heading__title a")
            date_el = item.select_one(".audio-heading__meta time")
            desc_el = item.select_one(".episode-list-item__description p")
            mp3_el = item.select_one("a[href$='.mp3']")

            if not (title_el and date_el and mp3_el):
                continue

            title = title_el.text.strip()
            page_link = BASE_URL + title_el["href"]
            audio_url = "https:" + mp3_el["href"]
            pub_date = date_el["datetime"]
            description = desc_el.text.strip() if desc_el else ""

            episodes.append({
                "title": title,
                "link": page_link,
                "audio": audio_url,
                "date": pub_date,
                "description": description,
            })
        except Exception as e:
            print(f"Fel vid parsning av ett avsnitt: {e}")

    return episodes

def generate_rss(episodes, filename="podcast.xml"):
    fg = FeedGenerator()
    fg.title("Sommar & Vinter i P1 – inofficiellt RSS-flöde")
    fg.link(href=PROGRAM_URL)
    fg.description("Automatiskt RSS-flöde genererat från Sveriges Radios webbsida.")

    for ep in episodes:
        fe = fg.add_entry()
        fe.title(ep["title"])
        fe.link(href=ep["link"])
        fe.pubDate(ep["date"])
        fe.description(ep["description"])
        fe.enclosure(ep["audio"], 0, 'audio/mpeg')

    fg.rss_file(filename)
    print(f"✅ RSS-flöde sparat som {filename}")

if __name__ == "__main__":
    episodes = fetch_episodes()
    generate_rss(episodes)

