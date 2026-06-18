# Price Tracker Bot

Ein modular aufgebauter Discord-Bot zum Ueberwachen von Produktseiten. Der Bot speichert beim ersten Abruf einen Snapshot je URL und vergleicht bei spaeteren Pruefungen Preis, Verfuegbarkeit und weitere erkannte Produktdaten. Wenn sich etwas aendert, sendet der Bot eine Benachrichtigung in einen konfigurierten Discord-Kanal.

## Funktionen

- Ueberwachung beliebig vieler Produktlinks ueber eine Watchlist
- Automatische Pruefung in einem festen Intervall
- Speicherung des ersten Zustands als Snapshot
- Vergleich zwischen altem und neuem Zustand
- Oeffentliche Discord-Benachrichtigung bei Aenderungen
- Datei-Logging mit rotierenden Logfiles
- Retry-Logik bei Netzwerkfehlern und Serverfehlern
- Asynchrone HTTP-Requests mit `aiohttp`
- Playwright-Unterstuetzung fuer dynamische Seiten
- Shop-spezifische Parser in separaten Modulen
- Generischer Fallback-Parser fuer unbekannte Shops

## Projektstruktur

```text
price_tracker_bot/
├── .env.example
├── requirements.txt
├── main.py
├── parsers/
│   ├── __init__.py
│   ├── base.py
│   ├── common.py
│   ├── shopify_parser.py
│   ├── cardbuddys_parser.py
│   ├── generic_parser.py
│   └── registry.py
└── utils/
    ├── __init__.py
    ├── browser.py
    ├── config.py
    ├── helpers.py
    ├── http.py
    ├── logger.py
    └── storage.py
```

## Voraussetzungen

- Python 3.11 oder neuer empfohlen
- Ein Discord-Bot mit aktiviertem Bot-Token
- Rechte zum Einladen des Bots auf deinen Server
- Playwright Chromium fuer dynamisch geladene Seiten

## Installation

### 1. Projektordner vorbereiten

Lege die Projektstruktur wie oben beschrieben an oder uebernimm die erzeugten Dateien.

### 2. Abhaengigkeiten installieren

```bash
pip install -r requirements.txt
```

### 3. Playwright-Browser installieren

```bash
python -m playwright install chromium
```

## Konfiguration

Erstelle im Hauptordner eine Datei `.env` auf Basis von `.env.example`:

```env
DISCORD_BOT_TOKEN=dein_discord_bot_token
OWNER_USER_ID=123456789012345678
GUILD_ID=123456789012345678
CHECK_INTERVAL_MINUTES=10
```

### Bedeutung der Variablen

- `DISCORD_BOT_TOKEN`: Token deines Discord-Bots aus dem Discord Developer Portal.
- `OWNER_USER_ID`: Deine Discord User-ID. Diese ID darf geschuetzte Befehle wie `/setchannel` ausfuehren.
- `GUILD_ID`: Die Server-ID, in der die Slash-Commands schnell synchronisiert werden sollen.
- `CHECK_INTERVAL_MINUTES`: Intervall in Minuten fuer die automatische Pruefung aller Links.

## Starten

Starte den Bot im Projektordner mit:

```bash
python main.py
```

Beim ersten Start verbindet sich der Bot mit Discord, synchronisiert seine Slash-Commands und startet den Hintergrund-Checker.

## Arbeitsweise

Der Bot arbeitet in mehreren Schritten:

1. Ein Link wird per Slash-Command zur Watchlist hinzugefuegt.
2. Direkt beim Hinzufuegen wird ein erster Snapshot gespeichert.
3. Der Hintergrund-Task prueft alle Links alle X Minuten.
4. Die aktuellen Daten werden mit den gespeicherten Snapshots verglichen.
5. Bei Unterschieden wird eine Discord-Nachricht gesendet und der Snapshot aktualisiert.

## Gespeicherte Dateien

Der Bot legt automatisch mehrere Dateien im Projektordner an:

- `watchlist.json`: EnthaeIt alle ueberwachten URLs.
- `snapshot.json`: Speichert den letzten bekannten Zustand je URL.
- `config.json`: Speichert die Kanal-ID fuer oeffentliche Benachrichtigungen.
- `logs/price_tracker.log`: Laufende Logdatei des Bots.

## Slash-Commands

### `/add <url>`

Fuegt einen neuen Produktlink zur Watchlist hinzu und speichert sofort den ersten Snapshot.

### `/remove <url>`

Entfernt einen Produktlink aus der Watchlist und loescht den dazugehoerigen Snapshot.

### `/list`

Zeigt alle aktuell ueberwachten Produktlinks an.

### `/setchannel <kanal>`

Setzt den Discord-Kanal, in den oeffentliche Aenderungsbenachrichtigungen gepostet werden. Dieser Befehl ist auf die in `.env` definierte `OWNER_USER_ID` beschraenkt.

### `/checknow`

Startet sofort eine manuelle Pruefung aller Links in der Watchlist.

### `/help`

Zeigt die wichtigsten Bot-Befehle direkt in Discord an.

## Parser-System

Die Parser sind modular aufgebaut.

### `parsers/shopify_parser.py`

Versucht Produktdaten direkt ueber den Shopify-JSON-Endpunkt `<produkt-url>.js` abzurufen. Das ist meist stabiler als ein HTML-Vergleich.

### `parsers/cardbuddys_parser.py`

Enthaelt shop-spezifische Logik fuer `cardbuddys.de`.

### `parsers/generic_parser.py`

Dient als allgemeiner HTML-Fallback fuer unbekannte Shops.

### `parsers/registry.py`

Steuert, welcher Parser fuer welche URL verwendet wird.

## Logging

Das Logging ist in `utils/logger.py` gekapselt und schreibt sowohl in die Konsole als auch in eine Datei:

- Datei: `logs/price_tracker.log`
- Rotierende Logfiles mit maximal 1 MB pro Datei
- Bis zu 5 Backup-Dateien

So kannst du Fehler, Timeouts oder erkannte Aenderungen auch spaeter noch nachvollziehen.

## Retry-Logik

Die Datei `utils/http.py` enthaelt eine Retry-Logik fuer Netzwerkfehler, Timeouts, HTTP 429 und HTTP 5xx.

Verhalten:

- Mehrere Wiederholungsversuche pro Request
- Kurze Wartezeit zwischen den Versuchen
- Logging jedes Fehlversuchs
- Sauberer Abbruch nach dem letzten Fehlversuch

## Dynamische Seiten

Einige Shops laden Preise oder Verfuegbarkeit erst per JavaScript nach. Fuer solche Faelle wird Playwright verwendet.

Die Datei `utils/browser.py`:

- startet einen headless Chromium-Browser,
- laedt die Produktseite,
- wartet kurz auf sichtbare Inhalte,
- liest den HTML-Inhalt aus,
- uebergibt diesen an die Parser.

## Erweiterung um neue Shops

Wenn du einen neuen Shop spezifisch unterstuetzen willst, gehst du so vor:

1. Neue Datei in `parsers/` anlegen, z. B. `myshop_parser.py`
2. Klasse von `BaseParser` ableiten
3. `can_handle()` fuer die Domain definieren
4. `parse()` mit den passenden CSS-Selektoren bauen
5. Parser in `parsers/registry.py` registrieren

Beispiel:

```python
from parsers.base import BaseParser

class MyShopParser(BaseParser):
    name = "myshop"

    def can_handle(self, url: str, html: str | None = None) -> bool:
        return "myshop.de" in url

    async def parse(self, url: str, session, html: str | None = None, title_from_page: str | None = None):
        return {
            "source": "myshop",
            "url": url,
            "title": "Produktname",
            "price": "99,99 €",
            "availability": "Vorbestellung moeglich",
        }
```

## Typischer Ablauf in Discord

1. Bot starten
2. `/setchannel` einmalig ausfuehren
3. Mit `/add <url>` Produkte hinzufuegen
4. Bot prueft automatisch im Intervall
5. Bei Preis- oder Statusaenderungen kommt eine oeffentliche Meldung im konfigurierten Kanal

## Hinweise

- Nicht jede Seite laesst sich problemlos scrapen. Manche Shops blockieren Bots aktiv.
- Ein kompletter HTML-Vergleich ist meist fehleranfaellig, daher werden gezielt relevante Daten extrahiert.
- Fuer manche Shops muessen CSS-Selektoren spaeter noch individuell angepasst werden.
- Wenn du viele Seiten gleichzeitig ueberwachst, solltest du das Intervall nicht zu aggressiv einstellen.

## Troubleshooting

### Slash-Commands erscheinen nicht

- Pruefe, ob `GUILD_ID` korrekt ist.
- Pruefe, ob der Bot auf dem richtigen Server ist.
- Starte den Bot neu.

### Playwright funktioniert nicht

- Stelle sicher, dass Chromium installiert wurde:

```bash
python -m playwright install chromium
```

### Der Bot erkennt keine Daten

- Teste die URL manuell im Browser.
- Pruefe die Logdatei unter `logs/price_tracker.log`.
- Passe gegebenenfalls den passenden Parser oder die Selektoren an.

### Keine oeffentlichen Benachrichtigungen

- Fuehre `/setchannel` aus.
- Pruefe, ob der Bot Schreibrechte im Zielkanal hat.
- Pruefe `config.json` und die Logs.

## Naechste sinnvolle Erweiterungen

- SQLite statt JSON-Dateien
- Telegram- oder E-Mail-Benachrichtigungen
- Eigene Parser pro Shop fuer bessere Erkennungsrate
- Diff-Ausgabe fuer konkrete Textaenderungen
- Weboberflaeche zum Verwalten der Watchlist