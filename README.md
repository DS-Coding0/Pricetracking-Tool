# Discord Price Tracker Bot

Ein Discord-Bot zum Ueberwachen von Produktseiten. Der Bot prueft gespeicherte URLs in einem festen Intervall, vergleicht den aktuellen Stand mit einem gespeicherten Snapshot und sendet bei Aenderungen eine Benachrichtigung in einen festgelegten Discord-Kanal.

## Funktionen

- Watchlist-Verwaltung per Slash-Commands.
- Automatische Pruefung aller Produkte alle X Minuten.
- Snapshot-basierter Vergleich von Preis, Verfuegbarkeit und Titel.
- Benachrichtigungen per Discord-Embed bei erkannten Aenderungen.
- Unterstuetzung fuer dynamische Seiten ueber Playwright.
- Shopify-Erkennung ueber `produkt-url.js`, wenn die Seite ein Shopify-Produkt ist.
- Kanal-Konfiguration fuer oeffentliche Aenderungsmeldungen.
- Schutz sensibler Werte ueber `.env`.
- Owner-Pruefung fuer administrative Commands wie `/setchannel`.

## Verwendete Technologien

- `discord.py`
- `requests`
- `beautifulsoup4`
- `playwright`
- `python-dotenv`
- JSON-Dateien fuer lokale Speicherung

## Projektstruktur

Der Bot arbeitet mit folgenden Dateien im Projektordner:

- `bot.py` – Hauptdatei des Bots
- `.env` – Umgebungsvariablen
- `watchlist.json` – gespeicherte ueberwachte URLs
- `snapshot.json` – letzter Snapshot pro URL
- `config.json` – Bot-Konfiguration, z. B. der Benachrichtigungskanal

## Voraussetzungen

- Python 3.10 oder neuer
- Ein Discord-Bot im [Discord Developer Portal](https://discord.com/developers/applications)
- Ein Discord-Server, auf dem der Bot eingeladen ist
- Chromium fuer Playwright

## Installation

### 1. Abhaengigkeiten installieren

```bash
pip install -U discord.py requests beautifulsoup4 playwright python-dotenv
python -m playwright install chromium
```

### 2. `.env` Datei erstellen

Lege im Projektordner eine Datei namens `.env` an.

```env
DISCORD_BOT_TOKEN=dein_discord_bot_token
OWNER_USER_ID=123456789012345678
GUILD_ID=123456789012345678
CHECK_INTERVAL_MINUTES=10
```

## Bedeutung der `.env` Werte

| Variable | Pflicht | Beschreibung |
|---------|---------|--------------|
| `DISCORD_BOT_TOKEN` | Ja | Token deines Discord-Bots |
| `OWNER_USER_ID` | Ja | Discord-User-ID, die administrative Befehle wie `/setchannel` nutzen darf |
| `GUILD_ID` | Ja | ID des Discord-Servers fuer den Guild-spezifischen Slash-Command-Sync |
| `CHECK_INTERVAL_MINUTES` | Nein | Intervall in Minuten fuer automatische Pruefungen, Standard ist `10` |

Wenn `DISCORD_BOT_TOKEN`, `OWNER_USER_ID` oder `GUILD_ID` fehlen oder ungueltig sind, bricht der Bot beim Start mit einer klaren Fehlermeldung ab.

## Bot starten

```bash
python bot.py
```

Bei erfolgreichem Start erscheinen in der Konsole sinngemaess Meldungen wie:

```text
X Slash-Commands fuer Guild 123456789012345678 synchronisiert.
Bot online als DeinBot#1234
```

## Discord Bot einladen

Der Bot sollte mit mindestens diesen Scopes eingeladen werden:

- `bot`
- `applications.commands`

Sinnvolle Berechtigungen:

- View Channels
- Send Messages
- Embed Links
- Read Message History

## Slash-Commands

### `/add <url>`
Fuegt eine Produktseite zur Watchlist hinzu und speichert sofort den ersten Snapshot.

### `/remove <url>`
Entfernt eine URL aus der Watchlist und loescht den zugehoerigen Snapshot.

### `/list`
Zeigt alle aktuell ueberwachten URLs an.

### `/setchannel <kanal>`
Setzt den Kanal, in dem oeffentliche Aenderungsbenachrichtigungen gepostet werden.

Hinweis: Dieser Command ist durch `OWNER_USER_ID` geschuetzt.

### `/checknow`
Startet sofort eine manuelle Pruefung aller Produkte in der Watchlist.

### `/help`
Zeigt eine Uebersicht aller Befehle als Discord-Embed.

## Wie der Bot arbeitet

1. Eine URL wird mit `/add` in die Watchlist aufgenommen.
2. Der erste erkannte Zustand wird in `snapshot.json` gespeichert.
3. Der Background-Task startet automatisch nach dem Login des Bots.
4. Alle `CHECK_INTERVAL_MINUTES` werden die Links erneut geprueft.
5. Die neuen Daten werden mit dem alten Snapshot verglichen.
6. Bei Aenderungen wird ein Embed in den konfigurierten Kanal gesendet.
7. Anschliessend wird der neue Snapshot gespeichert.

## Erkennungslogik

Der Bot nutzt zwei Wege zum Auslesen von Produktdaten:

### 1. Shopify-Produkte

Wenn die URL auf eine Shopify-Produktseite hinweist, wird zunaechst versucht, die Produktdaten ueber die JSON-Endung `.js` abzurufen.

Beispiel:

```text
https://shop.de/products/beispielprodukt
->
https://shop.de/products/beispielprodukt.js
```

Dabei koennen unter anderem diese Werte direkt ausgelesen werden:

- Titel
- Anbieter
- Produkttyp
- Preis
- Min-/Max-Preis
- Verfuegbarkeit
- Varianten

### 2. HTML-Fallback mit Playwright und BeautifulSoup

Wenn keine Shopify-JSON verfuegbar ist, nutzt der Bot Playwright, um die Seite im Headless-Browser zu laden. Der Titel wird zuerst direkt im DOM ueber Playwright gesucht. Danach wird das HTML an BeautifulSoup uebergeben, um weitere Daten wie Preis und Verfuegbarkeit zu extrahieren.

Vorteile dieses Ansatzes:

- funktioniert besser bei JavaScript-lastigen Shops
- Titel kann direkt aus dem finalen DOM gelesen werden
- Fallback ueber klassische HTML-Selektoren bleibt erhalten

## Beispiel fuer Titel-Erkennung

Wenn ein Produkttitel etwa so aufgebaut ist:

```html
<h1 class="card-title col-md-10">Mega-Entwicklungen Wachsendes Chaos Top Trainer Box DE</h1>
```

Dann ist ein passender CSS-Selektor:

```python
"h1.card-title.col-md-10"
```

Mehrere Klassen auf demselben Element werden in CSS ohne Leerzeichen kombiniert.

## Gespeicherte Daten

### `watchlist.json`
Enthaelt alle ueberwachten Produktlinks als Liste.

### `snapshot.json`
Enthaelt den letzten bekannten Stand pro URL. Je nach Shop oder Quelle koennen unter anderem folgende Felder gespeichert werden:

- `title`
- `price`
- `availability`
- `body_text`
- `variants`
- `available`
- `price_min`
- `price_max`

### `config.json`
Enthaelt zurzeit vor allem:

- `notification_channel_id`

## Benachrichtigungen

Wenn eine Aenderung erkannt wird, sendet der Bot ein Discord-Embed mit:

- Produkttitel
- Produktlink
- altem und neuem Preis
- alter und neuer Verfuegbarkeit
- weiteren geaenderten Feldern, sofern vorhanden
- Zeitstempel

Slash-Command-Antworten bleiben dabei `ephemeral`, also nur fuer den ausloesenden Benutzer sichtbar. Die echten Produktwarnungen werden dagegen oeffentlich in den gesetzten Kanal gesendet.

## Schutz gegen haeufige Fehler

Der Code enthaelt bereits mehrere Schutzmechanismen:

- Validierung wichtiger `.env` Variablen beim Start
- Fallback, wenn Shopify-JSON nicht verfuegbar ist
- Schutz vor `None`-Werten bei Embed-Feldern ueber `safe_embed_value()`
- URL-Normalisierung ueber `normalize_url()`
- Erkennung moeglicher Block-Seiten ueber typische Marker wie `captcha` oder `Incapsula`

## Typische Fehlerquellen

### `DISCORD_BOT_TOKEN fehlt in der .env`
Die `.env` Datei fehlt, ist falsch benannt oder enthaelt den Schluessel nicht.

### `OWNER_USER_ID muss eine gueltige Integer-ID sein`
Die User-ID ist leer oder kein numerischer Discord-Wert.

### `GUILD_ID muss eine gueltige Integer-ID sein`
Die Server-ID in der `.env` ist ungueltig.

### `Die Seite konnte nicht gelesen werden oder ist blockiert`
Der Shop blockiert automatisierte Zugriffe oder die HTML-Struktur wurde geaendert.

### Keine Titel-, Preis- oder Verfuegbarkeits-Erkennung
Dann muessen die CSS-Selektoren in `title_selectors`, `price_selectors` oder `availability_selectors` an die Zielseite angepasst werden.

## Anpassbare Einstellungen

Diese Punkte kannst du leicht erweitern oder anpassen:

- `CHECK_INTERVAL_MINUTES`
- Preis-Selektoren
- Verfuegbarkeits-Selektoren
- Titel-Selektoren
- ignorierte Felder in `ignored_keys`
- Embed-Inhalt und Benachrichtigungsformat

## Empfehlung fuer spaetere Erweiterungen

Fuer eine groessere oder stabilere Version koennen folgende Erweiterungen sinnvoll sein:

- Wechsel von JSON zu SQLite
- Logging in Datei statt nur `print()`
- Retry-Logik bei Netzwerkfehlern
- Rollen-Pings bei bestimmten Produkten
- Trennung von Shop-spezifischen Parsern in eigene Module
- `aiohttp` statt `requests` fuer voll asynchrones HTTP

## Sicherheit

- Speichere niemals den Discord-Token direkt im Code.
- Committe `.env` nicht in ein oeffentliches Repository.
- Regeneriere den Bot-Token sofort, falls er jemals geleakt wurde.

## Lizenz

Dieses Projekt kann frei fuer private oder interne Zwecke angepasst und erweitert werden.