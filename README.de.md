# Heizungsplaner · Heating Planner

Ein Home-Assistant-Add-on, das Heizkörperthermostate vorausschauend stellt –
nach Zeitplan, Außentemperatur und Anwesenheit.

[![Repository zu Home Assistant hinzufügen](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FMelle79%2FHA-heizungsplaner-heating-planner)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-melle79-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/melle79)

> 📖 Ausführliche Anleitung: **[DOCS.de.md](heizungsplaner/DOCS.de.md)** ·
> 🇬🇧 In English: **[README.md](README.md)**

**Der Planer folgt Home Assistant.** Der Sprache – Deutsch und Englisch sind
eingebaut, alles andere zeigt Englisch – und der Temperatureinheit: Celsius
oder Fahrenheit, mitsamt Vorgaben, Grenzen und Schrittweite. Einzustellen ist
nichts; beides steht in `/config` und wird bei jedem Takt gelesen.

Statt fester Uhrzeiten je Thermostat rechnet der Planer für jeden Raum in
jedem Takt einen Sollwert aus und begründet ihn. In der Oberfläche steht nicht
nur, dass das Wohnzimmer 21,5 °C bekommt, sondern warum: „Vorheizen für
komfort um 12:30 Uhr (50 Minuten Vorlauf) · Heizkurve +0,6 K“.

![Übersicht mit allen Räumen, Zielwert und Begründung](heizungsplaner/doku/bilder/uebersicht.png)

## Was der Planer berücksichtigt

* **Zeitplan je Raum** – Umschaltpunkte für Komfort, Eco, Nacht und Aus. Ein
  Punkt kann für eine Tagesart gelten, und davon gibt es zwei Paare: *Schultag
  / schulfrei* für alle, die zur Schule gehen, und *Werktag / arbeitsfrei* für
  alle, die arbeiten. In den Sommerferien ist schulfrei – wer arbeitet, steht
  trotzdem um sechs auf.
* **Außentemperatur** – eine Heizkurve führt den Sollwert nach: je kälter
  draußen, desto höher der Sollwert. Bei milder Witterung geht die Anlage in
  den Sommerbetrieb und schließt die Ventile.
* **Anwesenheit je Raum** – jedem Raum lassen sich die zuständigen Personen
  zuordnen. Ist niemand von ihnen da, senkt der Planer nach einer Karenzzeit
  ab; nähert sich jemand dem Haus, heizt er wieder vor. Global lässt sich
  festlegen, wer überhaupt zum Haushalt zählt – wichtig, wenn in Home
  Assistant mehr Personen stehen als im Haus wohnen.
* **Vorheizen** – der Vorlauf richtet sich nach der Außentemperatur. Bei 12 °C
  reichen 30 Minuten, bei −10 °C sind es zwei Stunden.
* **Fenster** – über Fensterkontakte oder, wo es keine gibt, über den
  Temperatursturz im Raum. Nachgerüstete Kontakte meldet der Planer von selbst
  zur Zuordnung; fällt einer aus, gilt er nicht als „geschlossen“.
* **Urlaub** – ein Schalter in Home Assistant legt das ganze Haus auf die
  Urlaubstemperatur.
* **Überwachung** – meldet ein Thermostat sich nicht mehr, kommt eine
  Benachrichtigung. Weil die Geräte keinen Batteriestand liefern, wacht der
  Planer über das Lebenszeichen statt über die Batterie.
* **Handbetrieb je Raum** – wer einen Raum selbst stellen will, lässt den
  Planer nur zu festen Zeiten absenken. Dazwischen rührt er ihn nicht an.
* **Freigabe je Raum** – ein Gästezimmer wird nur geheizt, wenn ein Schalter
  in Home Assistant es freigibt.
* **Partytaste** – hebt die gewählten Räume für ein paar Stunden auf Komfort
  und stellt sich danach von selbst zurück.
* **Einheit** – Celsius oder Fahrenheit, aus dem Maßsystem übernommen. Spannen
  werden als Spannen umgerechnet: Aus 1,5 K Hysterese werden 2,7 °F, nicht
  34,7. Wechselt das Maßsystem, ziehen die gespeicherten Werte einmalig mit.
* **Übersteuerung je Raum** – Regeln aus mehreren Bedingungen setzen den
  Zeitplan außer Kraft: „Werktag, keine Ferien, Isabel ist zu Hause“ hält das
  Wohnzimmer auf Komfort, statt es vormittags abzusenken. Als Bedingung taugt
  alles, was an oder aus sein kann – Schalter, Melder, Kalender und Personen.

* **Kesselregelung** *(optional, ab Werk aus)* – der Planer kann auch die
  Programmwahl der Heizungsregelung stellen, damit die Anlage nicht mehr ihr
  eigenes Zeitprogramm gegen den Plan fährt: Nenn, sobald ein Raum Komfort
  will, Reduziert, wenn alle abgesenkt sind, Sommer im Sommerbetrieb. Braucht
  das Add-on *Heizungsanlagenmanager*. Wer die Übernahme dort aufhebt, behält
  sie aufgehoben – der Planer meldet sich nicht von selbst neu an.

* **Öltank** *(optional, ab Werk aus)* – Restmenge, Tagesverbrauch,
  Reichweite und eine Leckagewache. Der Füllstand kommt ohne Sensor im Tank
  aus: die geeichte Liefermenge vom Lieferschein als Anker, die Brennerlaufzeit
  mal Düsendurchsatz als Auflösung dazwischen.

## Die Oberfläche

Vier Reiter: **Übersicht**, **Räume**, **Einstellungen**, **Protokoll** – dazu
**Öltank**, wenn er eingeschaltet ist.

Die **Übersicht** (Bild oben) zeigt je Raum den Zielwert, die gemessene
Temperatur und in einem Satz, warum gerade dieser Wert gilt. Oben stehen
Außentemperatur, Partytaste und der Knopf *Jetzt prüfen*.

Unter **Räume** wird eingerichtet:

![Raumliste mit Betriebsart und Zahl der Thermostate](heizungsplaner/doku/bilder/raeume.png)

Jeder Raum öffnet sich in einem Dialog mit fünf Reitern – Grundlagen,
Temperaturen, Zeitplan, Belegung, Fühler und Melder:

![Grundlagen eines Raumes: Betriebsart und zugeordnete Thermostate](heizungsplaner/doku/bilder/raum-grundlagen.png)

Der **Zeitplan** besteht aus Umschaltpunkten, nicht aus Zeitfenstern: Jeder
Punkt gilt, bis der nächste kommt – wahlweise immer, nur an Schultagen oder
nur an schulfreien Tagen:

![Zeitplan mit Umschaltpunkten für Schultage und schulfreie Tage](heizungsplaner/doku/bilder/raum-zeitplan.png)

Darunter stehen die **Übersteuerungsregeln**: Solange alle Bedingungen einer
Regel zutreffen und die Uhrzeit im Fenster liegt, gilt ihr Modus statt des
Zeitplans. So entsteht eine Homeoffice-Regelung ohne Schalter – Werktag, keine
Ferien, jemand ist zu Hause. Die Regel sagt selbst, ob sie greift, und wenn
nicht, woran es liegt:

![Übersteuerungsregel mit Bedingungen und Zeitfenster](heizungsplaner/doku/bilder/uebersteuerung.png)

Unter **Belegung** steht, wer den Raum benutzt: zuständige Personen, ein
Präsenzmelder, eine eigene Karenzzeit – und ob der Raum bei der Partytaste
mitmacht:

![Belegung: Freigabeschalter, zuständige Personen, Karenzzeit](heizungsplaner/doku/bilder/raum-belegung.png)

Unter **Fühler und Melder** hängen Temperaturfühler, Präsenzmelder und
Fensterkontakte am Raum. Geräte werden angehakt, und eine Filterzeile über
jeder Liste zeigt auf Wunsch nur, was zu diesem Raum gehört – sonst stünde im
Wohnzimmer auch der Briefkastenkontakt zur Auswahl:

![Fühler und Melder mit Filterzeile über jeder Auswahlliste](heizungsplaner/doku/bilder/raum-melder.png)

Die **Einstellungen** gelten fürs ganze Haus: Heizkurve, Sommerbetrieb,
Vorheizen, Anwesenheit, Fenstererkennung, Überwachung und Meldewege:

![Einstellungen mit Heizkurve und Sommerbetrieb](heizungsplaner/doku/bilder/einstellungen.png)

Das **Protokoll** hält jede Änderung mit Begründung fest – Störungen rot,
Warnungen gelb:

![Protokoll der Schaltvorgänge mit Begründung](heizungsplaner/doku/bilder/protokoll.png)

## Installation

1. In Home Assistant unter **Einstellungen → Add-ons → Add-on-Store** über das
   Dreipunktmenü **Repositories** öffnen und diese Adresse hinzufügen:

   ```
   https://github.com/Melle79/HA-heizungsplaner-heating-planner
   ```

   Oder den Knopf oben im Dokument benutzen.

2. Das Add-on **Heizungsplaner** installieren und starten.
3. Die Oberfläche öffnen. Sie startet im **Trockenlauf**: Der Planer rechnet
   und protokolliert, stellt aber noch kein Thermostat.
4. Über **Räume aus Home Assistant übernehmen** die Räume anlegen lassen,
   Zeitpläne und Temperaturen prüfen.
5. Wenn das Ergebnis stimmt: in den Einstellungen den Trockenlauf abschalten.

Die ausführliche Anleitung steht in [DOCS.md](heizungsplaner/DOCS.md).

## Entitäten in Home Assistant

Über MQTT legt das Add-on ein Gerät „Heizungsplaner“ an:

| Entität | Bedeutung |
|---|---|
| `sensor.heizungsplaner_status` | Kurzfassung des Betriebszustands |
| `sensor.heizungsplaner_aussentemperatur_gedaempft` | geglättete Außentemperatur |
| `binary_sensor.heizungsplaner_sommerbetrieb` | Sommerbetrieb aktiv |
| `binary_sensor.heizungsplaner_trockenlauf` | Trockenlauf aktiv |
| `sensor.heizungsplaner_raum_<name>` | Zielwert je Raum; Attribute: `zustand`, `begruendung`, `ist_temperatur`, `naechster_wechsel` sowie `uebersteuerung`, `uebersteuerung_greift`, `uebersteuerung_lage` und `uebersteuerung_bis` |
| `switch.heizungsplaner_party` | Partytaste, mit Restzeit als Attribut |
| `binary_sensor.heizungsplaner_stoerung` | ein Thermostat meldet sich nicht mehr; Meldungen nach Schwere getrennt als Attribute |
| `sensor.heizungsplaner_stoerungen` | Zahl der ausgefallenen Thermostate |
| `sensor.heizungsplaner_kessel` | Betriebsart der Regelung, solange die Kesselregelung läuft |

## Karten fürs Dashboard

Unter [`heizungsplaner/dashboard/`](heizungsplaner/dashboard/) liegt eine
fertige Übersicht zum Einfügen: Partytaste, Störungsanzeige und eine Tabelle
aller Räume mit Zielwert, Ist-Temperatur und nächstem Schaltpunkt. Sie kommt
mit den MQTT-Entitäten aus und funktioniert damit auch von unterwegs.

Dazu `regelkarte(sensor)` – eine Kachel, die **nur erscheint, solange eine
Übersteuerungsregel greift**, und zeigt, bis wann. Sie gehört dorthin, wo man
den Raum ohnehin ansieht, nicht in den Planer-Abschnitt.

## Prüflauf

Die Regellogik lässt sich ohne Home Assistant und ohne Fremdpakete prüfen:

```
python3 heizungsplaner/tests/test_logik.py
```

Geprüft werden Zeitplan über Tagesgrenzen, Heizkurve und Sommerhysterese,
Anwesenheit samt Heimkehr, Fenstererkennung, die Betriebsart „nur absenken“
und das Schreiben auf Flanke. Etliche Fälle stehen dort, weil sie einmal
falsch waren – etwa eine Schule in einem Kilometer Entfernung, die das
Kinderzimmer den ganzen Vormittag als „auf dem Heimweg“ gelten ließ.

## Lizenz

MIT
