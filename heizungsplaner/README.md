# Heizungsplaner · Heating Planner

Ein Home-Assistant-Add-on, das Heizkörperthermostate vorausschauend stellt –
nach Zeitplan, Außentemperatur und Anwesenheit.

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-melle79-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/melle79)

> 📖 Full manual: **[DOCS.md](DOCS.md)** (English) · **[DOCS.de.md](DOCS.de.md)**
> (Deutsch). Im Add-on steht sie unter *Dokumentation*.

![Übersicht mit allen Räumen, Zielwert und Begründung](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/uebersicht.png)

Statt fester Uhrzeiten je Thermostat rechnet der Planer für jeden Raum in
jedem Takt einen Sollwert aus und begründet ihn: nicht nur, dass das
Wohnzimmer 21,5 °C bekommt, sondern warum.

## Was der Planer berücksichtigt

* **Zeitplan je Raum** – Komfort, Eco, Nacht und Aus. Zwei Paare von
  Tagesarten: *Schultag / schulfrei* und *Werktag / arbeitsfrei*
* **Außentemperatur** – Heizkurve und Sommerbetrieb, beides über eine
  geglättete Außentemperatur
* **Anwesenheit je Raum** – zuständige Personen und Präsenzmelder, mit
  Karenzzeit und Vorheizen bei Heimkehr
* **Fenster** – über Kontakte oder, wo es keine gibt, über den Temperatursturz
* **Urlaub, Freigabe je Raum und Partytaste**
* **Überwachung** – ein Thermostat, das sich nicht mehr meldet, wird gemeldet
* **Sprache und Einheit** – beides aus Home Assistant: Deutsch oder Englisch,
  Celsius oder Fahrenheit
* **Öltank** *(optional, ab Werk aus)* – Restmenge, Verbrauch, Reichweite und
  Leckagewache

## Erste Schritte

1. Add-on starten und die Oberfläche öffnen. Sie startet im **Trockenlauf**:
   Der Planer rechnet und protokolliert, stellt aber noch kein Thermostat.
2. **Räume aus Home Assistant übernehmen** – der Assistent legt je Bereich mit
   Thermostat einen Raum an.
3. Zeitpläne, Temperaturen und Personenzuordnung prüfen.
4. Einige Tage beobachten, das Protokoll gegen die tatsächlichen Zeiten
   halten. Laufen noch andere Zeitpläne oder Automationen auf dieselben
   Thermostate, diese vorher abschalten.
5. Stimmt das Ergebnis, in den Einstellungen den **Trockenlauf abschalten**.

## Lizenz

MIT
