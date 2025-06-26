# Inofficiellt RSS-flöde för "Sommar & Vinter i P1"

> ⚠️ **Vill du göra det enkelt för dig?  
> 💡 Gå till [sr-restored](https://www.sr-restored.se) istället.**  
> <https://github.com/lindell/sr-restored>


Vill du skapa RSS-flödet själv? *Read on, my friend, read on!*

Detta projekt skapar ett automatiserat, icke-officiellt RSS-flöde för programmet [Sommar & Vinter i P1](https://www.sverigesradio.se/avsnitt?programid=2071) från [Sveriges Radio](https://www.sverigesradio.se).

Projektet består av flera delar som tillsammans gör det enkelt att:

- Skrapa avsnittsdata direkt från Sveriges Radios publika webbplats ([Sommar & Vinter i P1](https://www.sverigesradio.se/avsnitt?programid=2071))
- Generera ett komplett podcast-RSS-flöde (`sommar_i_p1.xml`) som kan användas i valfri poddspelare. Antingen använder du den rakt av som den är (kopierar till din podd-spelare), eller så läser du vidare.
- Hosta podcast-feeden själv, inklusive HTTPS-stöd, med hjälp av en enkel Python-server
- Automatisera flödet så att det alltid är aktuellt, med hjälp av en systemd user-tjänst
- Hantera konfiguration och personliga inställningar via `.env`-filer för att separera privat information från kod
- Skydda personlig data i versionshanteringen (git) genom tydliga instruktioner och ignore-filer

Syftet är att du snabbt ska kunna köra igång flödet, anpassa det efter eget behov och vara trygg med att känslig information aldrig råkar hamna publikt.

## Projektstruktur

| Fil                   | Funktion                                              |
|-----------------------|------------------------------------------------------|
| `sommar.py`             | Skrapar och genererar `sommar_i_p1.xml`                  |
| `servera.py`            | Enkel HTTPS-server för att dela feeden               |
| `gen_service.py`        | Skapar systemd service-fil utifrån `.env`            |
| `requirements.txt`      | Lista av Python-beroenden                            |
| `.env` / `.env.example`   | Inställningsfil / exempel               |
| `cache.json`            | Lokal cache för snabba körningar (skapas av `sommar.py`)                     |
| `sommar_i_p1.xml`           | Genererat RSS-flöde (skapas av `sommar.py`)                        |
| `sommar-server.service` | Systemd-tjänstfil för att köra `servera.py` automatiskt (skapas av `gen_service.py`) |
| `server.log`          | Loggfil för `servera.py` (genereras av `servera.py`                            |

## Installation och konfiguration

### Förutsättningar

Projektet kräver Python >= 3.10 samt vissa Python-bibliotek.
Anvisningarna nedan (samt `gen_service.py` scriptet senare) är skrivna utifrån att du använder [Anaconda](https://www.anaconda.com/) eller [Miniconda](https://docs.conda.io/en/latest/miniconda.html) för att hantera Python-miljöer och beroenden; använder du systemets `python` hoppar du ju bara över steg 1 och 2, nedan (samt kommenterar bort `CONDA_ENV` från `.env`).

#### 1. Installera Anaconda eller Miniconda

Ladda ner och installera från <https://docs.conda.io/en/latest/miniconda.html> om du inte redan har conda.

#### 2. Skapa och aktivera miljön

```bash
conda create -n sommar python=3.11 -y
conda activate sommar
```

#### 3. Installera beroenden

```bash
pip install -r requirements.txt
```

Eller manuellt:

```bash
pip install beautifulsoup4 feedgen python-dotenv requests
```

Ovan är allt du behöver för att köra `sommar.py` och generera `sommar_i_p1.xml` -scriptet. För att använda `servera.py` och/eller `gen_service`, fortsätt läsa.

## Konfiguration: Miljövariabler med `.env`

Projektet använder en `.env`-fil för att hantera lokala inställningar som portnummer, webbadresser och paths.

Skapa din `.env`-fil
Kopiera exempel-filen:

```bash
cp .env.example .env
```

Redigera `.env` så att värdena passar din miljö:

```bash
DEBUG=False                    # print debug information

# sommar.py
FEED_URL=YOURFEEDADDRESS.xml    # https://server/sommar_i_p1.xml
RSS_FILE=sommar_i_p1.xml           # the name of the podcast-feed -file

# servera.py
PORT=443                        # port to serve from
SSL_CHAIN=ssl/fullchain.pem     # path to fullchain.pem
SSL_KEY=ssl/privkey.pem         # path to privkey.pem
LOG_FILE=server.log            # log file for servera.py

# gen_service.py
PYTHON=/opt/anaconda/bin/conda  # where conda OR system python can be found
CONDA_ENV=sommar                      # which conda environment, if any
# Commented CONDA_ENV (non-existent) or false means we will use system python
WORKDIR=/path/to/scriptdir      # where the script is located
```

Variablerna används för att styra skriptens och tjänstens beteende.

- Ifall du bara använder `sommar.py` och endast delar feeden som fil, och inte vill ändra output-fil eller dylikt, så behöver du inte ändra något.
- Ifall du kör `servera.py` själv (inte via `systemd` behöver du bara ställa in `FEED_URL` och `PORT`.

**OBS:**  
Alla vägar är relativa till projektets rot om inget annat anges.
Om du exponerar din feed mot nätet måste SSL_CHAIN och SSL_KEY peka på befintliga certifikat (se nedan för hur du genererar dessa).

## Hur det funkar

### Skapa podcast-feeden

#### Hämta information

All information om Sommar- och Vinterpratare hämtas automatiskt från den publika webbsidan hos Sveriges Radio.
Detta hanteras av Python-skriptet `sommar.py`, som:

- Laddar ner aktuell avsnittslista
- Plockar ut titlar, länkar, beskrivningar, bilder, ljudfiler och publiceringsdatum
- Cachar informationen lokalt för snabbare framtida körningar (`cache.json`), och för att inte belasta sverigesradio.se i onödan
- Säkerställer att bara nya eller uppdaterade avsnitt hämtas vid nästa körning; annars används cachad information (avsnitt som tagits bort från officiella sidan avlägsnas också från cachen)

Du behöver någon manuell hämtning; inga `mp3`-filer eller omslag lagras lokalt – allt sker automatiskt när du kör `sommar.py` och länkarna i `sommar_i_p1.xml` leder alla till sverigesradio.se.

#### Generera podcast RSS -filen (`sommar_i_p1.xml`)

När skrapningen är klar skapas ett fullständigt RSS-flöde enligt podcast-standard.
Detta RSS-flöde (`sommar_i_p1.xml`) kan importeras i valfri podcastspelare och fungerar likt den officiella feeden (men innehåller endast publika avsnitt). `MP3`-filen som poddcast-spelaren hämtar, laddas alltså ner direkt från sverigesradio.se.

Skriptet `sommar.py`:

- Kombinerar skrapad data och bygger upp RSS-filen
- Lägger till nödvändiga metadata (titel, bild, beskrivning etc.)
- Ser till att alla länkar, bilder och ljudfiler fungerar korrekt
- Formaterar RSS-filen så den är lättläst och validerbar

Exempel på körning:

```bash
python sommar.py
```

*Innan du kör scriptet bör du ha gjort de inställningar som beskrevs ovan.*

Efter körning finns `sommar_i_p1.xml` i projektkatalogen.

Exempel på innehåll:

<details>
<summary>sommar_i_p1.xml (klicka för att vika ut)</summary>

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <podcast:guid>e57e3ed2-3132-5068-a98d-7e0f81c99a25</podcast:guid>
<title>Sommar &amp; Vinter i P1 – inofficiellt RSS-flöde</title>
    <link>https://www.sverigesradio.se/sommar-i-p1</link>
    <description>Inofficiellt RSS-flöde automatiskt genererat från Sveriges Radio. Alla Sommarprat finns att lyssna på i Sveriges Radio Play.</description>
    <atom:link href="localhost/sommar_i_p1.xml" rel="self" type="application/rss+xml"/>
    <copyright>Copyright Sveriges Radio 2025. All rights reserved.</copyright>
    <docs>http://www.rssboard.org/rss-specification</docs>
    <generator>python-feedgen</generator>
    <image>
      <url>https://static-cdn.sr.se/images/2071/138fda3c-4e35-48e0-8fdb-e2ea8ef44758.jpg?preset=api-itunes-presentation-image</url>
      <title>Sommar &amp; Vinter i P1 – inofficiellt RSS-flöde</title>
      <link>https://www.sverigesradio.se/sommar-i-p1</link>
    </image>
    <language>sv</language>
    <lastBuildDate>Thu, 26 Jun 2025 17:30:03 +0000</lastBuildDate>
    <itunes:author>Sveriges Radio</itunes:author>
    <itunes:category text="Society &amp; Culture"/>
    <itunes:image href="https://static-cdn.sr.se/images/2071/138fda3c-4e35-48e0-8fdb-e2ea8ef44758.jpg?preset=api-itunes-presentation-image"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:summary>Inofficiellt RSS-flöde automatiskt genererat från Sveriges Radio. Alla Sommarprat finns att lyssna på i Sveriges Radio Play.</itunes:summary>
    <item>
      <title>Petra Mede</title>
      <link>https://www.sverigesradio.se/avsnitt/petra-mede-sommarpratare-2025</link>
      <description>Komikern om romantik, bröllop, terapi och mycket mycket mer.</description>
      <content:encoded><![CDATA[<p>Komikern om romantik, bröllop, terapi och mycket mycket mer.</p><img src="https://static-cdn.sr.se/images/2071/209d1e85-93ca-470f-8d37-f41a03a3fa7b.jpg" alt="Petra Mede"/>]]></content:encoded>
      <guid isPermaLink="true">https://www.sverigesradio.se/avsnitt/petra-mede-sommarpratare-2025</guid>
      <enclosure url="https://sverigesradio.se/topsy/ljudfil/srse/9804232.mp3" length="56774503" type="audio/mpeg"/>
      <pubDate>Sat, 21 Jun 2025 07:00:00 +0000</pubDate>
      <itunes:author>Sveriges Radio</itunes:author>
      <itunes:image href="https://static-cdn.sr.se/images/2071/209d1e85-93ca-470f-8d37-f41a03a3fa7b.jpg?preset=api-itunes-presentation-image"/>
      <itunes:duration>3540</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
      <itunes:subtitle>Komikern om romantik, bröllop, terapi och mycket mycket mer.</itunes:subtitle>
      <itunes:summary>Komikern om romantik, bröllop, terapi och mycket mycket mer.</itunes:summary>
    </item>
  </channel>
</rss>
```

</details>

### Dela podcast-flödet som webbtjänst (`servera.py`)

#### Prerequisites för att starta webbtjänsten

##### HTTPS och portar: Gör din podcast-feed publik

För att andra podcast-appar (eller du själv på distans) ska kunna läsa in din `podcast.xml` behöver du göra den tillgänglig via nätet. Detta görs med den medföljande servern `servera.py`, som enkelt levererar filen på valfri port.

##### 1. **Portval**

- Standardport för HTTP är **80** och för HTTPS **443**.
- Du kan välja valfri port (t.ex. 1234, 8443) i din `.env`-fil via raden:  
  `PORT=443`
- Tänk på att portar under 1024 kräver root-rättigheter (undantaget om du kör via t.ex. systemd med tillåtna capabilities).

##### 2. **SSL-certifikat**

För att din feed ska fungera i alla moderna poddspelare krävs HTTPS, dvs. ett giltigt SSL-certifikat. Så här gör du:

- Lägg dina certifikatfiler i en mapp `ssl/` i projektroten.
- Servern letar per default efter filerna:
  - `ssl/fullchain.pem`  *(certifikat + eventuella intermediates)*
  - `ssl/privkey.pem`    *(privat nyckel)*
- Har du en domän kan du gratis generera certifikat med t.ex. [Let's Encrypt](https://letsencrypt.org/).  

Fil- och katalognamn (`ssl/fullchain.pem`, `ssl/privkey.pem`) bör vara just så; ange annars faktiska filnamn i `.env`.

När certifikat och port är på plats; fortsätt läsa.

#### En enkel server för `podcast.xml`

För att göra `podcast.xml` tillgänglig över internet kan du använda det medföljande server-skriptet `servera.py`.

Detta skript:

- Startar en enkel HTTP(S)-server som levererar `podcast.xml` på angiven port (standard: 443)
- Hanterar SSL-certifikat för säker (https://) trafik — du behöver alltså skapa sådana för din server
- Visar tydlig loggning kring serverstatus och nästa automatiska uppdatering
- Kan köras antingen manuellt eller som systemtjänst (systemd) (beskrivs nedan)

Exempel på manuell körning:

```bash
python servera.py
```

Feeden blir nu åtkomlig på:
<https://din.domän.se:PORT/podcast.xml>
eller (bara lokalt)
<https://localhost:PORT/podcast.xml>

Glöm inte att öppna brandvägg/port på servern om du vill nås utifrån.

#### Automatisera `servera.py` genom `systemd`

För att slippa manuellt starta servern varje gång datorn startas, kan du installera och aktivera en systemd-användartjänst.
Projektet innehåller ett hjälpskript (`gen_service.py`) som genererar en färdig `sommar-server.service`-fil, utifrån miljövariabler som du ställer in i `.env` (se ovan).

Så här gör du:

Skapa service-filen:

```bash
python gen_service.py
```

Kopiera/aktivera filen:

```bash
systemctl --user daemon-reload
systemctl --user enable --now sommar-server.service
```

Loggar och övervakning:

```bash
journalctl --user -u sommar-server -f
systemctl --user status sommar-server
```

Tjänsten kör nu automatiskt, startar vid inloggning/omstart och levererar alltid senaste podcast.xml.
