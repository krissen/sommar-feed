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

## 📜 Licens

Detta projekt är inte affilierat med Sveriges Radio. Används endast för personligt bruk. Flödet genereras från publikt tillgänglig data.
