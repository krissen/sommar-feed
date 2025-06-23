# 📻 Inofficiellt RSS-flöde för "Sommar & Vinter i P1"

Detta är ett Python-skript som automatiskt genererar ett RSS-flöde från Sveriges Radios webbsida för programmet **Sommar & Vinter i P1**.

🔗 Officiell sida: [sverigesradio.se/avsnitt?programid=2071](https://sverigesradio.se/avsnitt?programid=2071)  
🎧 Resultat: `podcast.xml` – ett RSS-flöde som kan importeras i valfri podcastspelare.

---

## 🚀 Kom igång

### 1. Klona eller ladda ner projektet

```bash
git clone https://example.com/din-repo.git
cd sr_rss
```

### 2. Skapa och aktivera conda-miljö

```bash
conda create -n sr_rss python=3.11 -y
conda activate sr_rss
```

### 3. Installera beroenden

```bash
pip install -r requirements.txt
```

Eller manuellt:

```bash
pip install requests beautifulsoup4 feedgen
```

## 🛠️ Användning

Kör skriptet för att skapa RSS-flödet:

```bash
python sommar.py
```

Resultatet sparas i `podcast.xml`. Lägg in den i din podcastspelare genom att importera filen lokalt eller tillhandahålla den via web/server.

## systemd user-tjänst för servera.py (med auto-uppdatering)

Det här projektet inkluderar en systemd-tjänst för att automatiskt starta och övervaka podcast-servern (servera.py). Tjänsten körs som vanlig användare (ingen root krävs).

### Förutsättningar

**Python-miljö:** /home/someuser/.conda/envs/sommar/bin/python3

**Katalog:** /yourpath/sommar-feed

**Användare:** someuser

**Certifikat:** Ligger i ssl/ i projektkatalogen.

### Installation & aktivering

Lägg till servicefilen (som exempel, se `./sommar-server.service`)

Se till att användarens tjänster startar oberoende av inloggning

```bash
loginctl enable-linger someuser
```

Ladda om user systemd och aktivera tjänsten

```bash
systemctl --user daemon-reload
systemctl --user enable --now sommar-server.service
```

### Loggar och övervakning

För att följa loggar:

```bash
journalctl --user -u sommar-server -f
```

För att kontrollera status:

```bash
systemctl --user status sommar-server
```

Automatisk start vid omstart. Så länge `loginctl enable-linger` är satt, kommer tjänsten alltid starta vid omstart av maskinen – även utan att någon loggar in.

## 📜 Licens

Detta projekt är inte affilierat med Sveriges Radio. Används endast för personligt bruk. Flödet genereras från publikt tillgänglig data.
