"""Alle Texte, die ein Mensch zu sehen bekommt – auf Deutsch und Englisch.

Der Planer erklärt jede Entscheidung in einem Satz. Diese Sätze stehen auf den
Raumkacheln, im Protokoll, in den Benachrichtigungen und als Attribut an jeder
MQTT-Entität. Sie entstehen deshalb **hier**, nicht verstreut im Code – sonst
ist eine zweite Sprache nicht zu haben.

Die Sprache kommt von Home Assistant selbst (``/config`` → ``language``).
Alles, was nicht Deutsch ist, bekommt Englisch; eine dritte Sprache braucht
nur eine weitere Spalte in dieser Tabelle.

Aufbau: ``t("schluessel", raum="Büro", grad=1.5)``. Die Platzhalter sind in
beiden Sprachen dieselben, damit ein fehlender Wert sofort auffällt statt
still zu verschwinden.
"""
from __future__ import annotations

import logging

import einheit

_LOGGER = logging.getLogger(__name__)

# Die Ausweichkette: Wer eine Sprache nicht kennt, versucht Englisch und
# zuletzt Deutsch. So bleibt eine halb gepflegte Sprache benutzbar – ein
# fehlender Satz erscheint auf Englisch statt als leere Stelle.
AUSWEICH = ("en", "de")
_sprache = "de"


def sprachen() -> tuple[str, ...]:
    """Welche Sprachen die Tabelle hergibt – abgeleitet, nicht gepflegt.

    Eine neue Sprache ist damit eine Spalte in ``TEXTE`` und sonst nichts:
    Sie wird von selbst angeboten, sobald sie dort auftaucht.
    """
    vorhanden = set()
    for eintrag in TEXTE.values():
        vorhanden.update(eintrag)
    return tuple(sorted(vorhanden))


def sprache_setzen(sprache: str | None) -> str:
    """Sprache aus Home Assistant übernehmen (``de``, ``en-GB``, ``fr``, …)."""
    global _sprache
    kurz = (sprache or "de").split("-")[0].lower()
    _sprache = kurz if kurz in sprachen() else AUSWEICH[0]
    return _sprache


def sprache() -> str:
    return _sprache


def t(schluessel: str, **werte) -> str:
    """Einen Text in der eingestellten Sprache, mit eingesetzten Werten."""
    eintrag = TEXTE.get(schluessel)
    if eintrag is None:
        _LOGGER.warning("Unbekannter Text: %s", schluessel)
        return schluessel
    vorlage = eintrag.get(_sprache)
    if not vorlage:
        for ausweich in AUSWEICH:
            vorlage = eintrag.get(ausweich)
            if vorlage:
                break
    if not vorlage:
        _LOGGER.warning("Text %s fehlt in allen Sprachen", schluessel)
        return schluessel
    # Die Einheit steht in keinem Satz fest: Sie kommt aus dem Maßsystem von
    # Home Assistant und wird hier eingesetzt, ohne dass jeder Aufruf sie
    # mitgeben muss.
    werte.setdefault("einheit", einheit.einheit())
    # Eine Spanne heißt in Celsius „K“ (Kelvin) und in Fahrenheit schlicht
    # „°F“ – ein Kelvin-Abstand in einer Fahrenheit-Anzeige wäre falsch.
    werte.setdefault("spanne", "°F" if einheit.ist_fahrenheit() else "K")
    try:
        return vorlage.format(**werte)
    except (KeyError, IndexError) as fehler:
        _LOGGER.warning("Text %s: Platzhalter fehlt (%s)", schluessel, fehler)
        return vorlage


# ── Modi und Zustände ───────────────────────────────────────────────────────
#
# Die Schlüssel bleiben deutsch: Sie stehen so in der gespeicherten
# Konfiguration und in den MQTT-Zuständen, und ein Umbenennen würde jede
# bestehende Einrichtung brechen. Übersetzt wird nur, was angezeigt wird.

MODUS = {
    "komfort": {"de": "Komfort", "en": "comfort"},
    "eco": {"de": "Eco", "en": "eco"},
    "nacht": {"de": "Nacht", "en": "night"},
    "aus": {"de": "Aus", "en": "off"},
}

ZUSTAND = {
    "komfort": {"de": "Komfort", "en": "Comfort"},
    "eco": {"de": "Eco", "en": "Eco"},
    "nacht": {"de": "Nacht", "en": "Night"},
    "aus": {"de": "Aus", "en": "Off"},
    "abwesend": {"de": "Abwesend", "en": "Away"},
    "heimkehr": {"de": "Heimkehr", "en": "Coming home"},
    "vorheizen": {"de": "Vorheizen", "en": "Preheating"},
    "fenster": {"de": "Fenster offen", "en": "Window open"},
    "urlaub": {"de": "Urlaub", "en": "Holiday"},
    "sommer": {"de": "Sommer", "en": "Summer"},
    "gesperrt": {"de": "Gesperrt", "en": "Blocked"},
    "manuell": {"de": "Von Hand", "en": "Manual"},
    "party": {"de": "Party", "en": "Party"},
    "absenkung": {"de": "Absenkung", "en": "Setback"},
    "uebersteuert": {"de": "Übersteuert", "en": "Overridden"},
}


def _aus_tabelle(tabelle: dict, name: str) -> str:
    eintrag = tabelle.get(name)
    if not eintrag:
        return name
    for sprache in (_sprache, *AUSWEICH):
        if eintrag.get(sprache):
            return eintrag[sprache]
    return name


def modus(name: str) -> str:
    return _aus_tabelle(MODUS, name)


def zustand(name: str) -> str:
    return _aus_tabelle(ZUSTAND, name)


# ── Begründungen ────────────────────────────────────────────────────────────

TEXTE: dict[str, dict[str, str]] = {
    # Rangfolge der Regelung
    "raum_aus": {
        "de": "Raum ist im Planer abgeschaltet",
        "en": "Room is switched off in the planner"},
    "gesperrt": {
        "de": "„{name}“ ist aus – der Raum wird nicht geheizt",
        "en": "“{name}” is off – this room is not heated"},
    "fenster_kontakt": {
        "de": "{name} ist offen",
        "en": "{name} is open"},
    "fenster_geraet": {
        "de": "{name} meldet ein offenes Fenster",
        "en": "{name} reports an open window"},
    "fenster_sturz": {
        "de": "Temperatursturz um {grad} {spanne} in {minuten} Minuten",
        "en": "Temperature dropped {grad} {spanne} in {minuten} minutes"},
    "fenster_sperre": {
        "de": "Fenster war offen – Sperrzeit bis {uhrzeit} Uhr",
        "en": "Window was open – locked until {uhrzeit}"},
    "fenster_stumm": {
        "de": "{anzahl} Fensterkontakt(e) melden nichts – ersatzweise Temperatursturz",
        "en": "{anzahl} window contact(s) report nothing – falling back to temperature drop"},
    "party": {
        "de": "Partytaste – noch {minuten} Minuten{hinweis}",
        "en": "Party button – {minuten} minutes left{hinweis}"},
    "party_sommer": {
        "de": " · Achtung: Sommerbetrieb, die Anlage heizt womöglich nicht",
        "en": " · note: summer mode, the system may not be heating"},
    "urlaub": {
        "de": "Urlaub ist eingeschaltet",
        "en": "Holiday mode is on"},
    "sommer": {
        "de": "Sommerbetrieb – Außentemperatur liegt im Mittel bei {grad} {einheit}",
        "en": "Summer mode – outdoor temperature averages {grad} {einheit}"},
    "sommer_ohne_wert": {
        "de": "Sommerbetrieb",
        "en": "Summer mode"},
    "zeitplan": {
        "de": "Zeitplan: {modus} ab {uhrzeit} Uhr",
        "en": "Schedule: {modus} from {uhrzeit}"},
    "zeitplan_leer": {
        "de": "Kein Zeitplan hinterlegt – Eco-Temperatur",
        "en": "No schedule set – eco temperature"},
    "vorheizen": {
        "de": "Vorheizen für {modus} um {uhrzeit} Uhr ({minuten} Minuten Vorlauf)",
        "en": "Preheating for {modus} at {uhrzeit} ({minuten} minutes lead time)"},
    "uebersteuerung": {
        "de": "{name}{fenster} – {modus} statt Zeitplan",
        "en": "{name}{fenster} – {modus} instead of schedule"},
    "uebersteuerung_bis": {
        "de": " (bis {uhrzeit} Uhr)",
        "en": " (until {uhrzeit})"},
    "abwesend": {
        "de": "{wer} ist nicht zu Hause, seit {minuten} Minuten leer",
        "en": "{wer} is not at home, empty for {minuten} minutes"},
    "abwesend_niemand": {
        "de": "Niemand Zuständiges zu Hause, seit {minuten} Minuten leer",
        "en": "Nobody responsible at home, empty for {minuten} minutes"},
    "heimkehr": {
        "de": "Heimkehr erwartet – {wer} kommt näher, noch {km} km",
        "en": "Return expected – {wer} is approaching, {km} km to go"},
    "praesenz": {
        "de": "Präsenzmelder meldet Bewegung",
        "en": "Presence sensor reports movement"},
    "heizkurve": {
        "de": " · Heizkurve {vorzeichen}{grad} {spanne}",
        "en": " · heating curve {vorzeichen}{grad} {spanne}"},
    "handbetrieb": {
        "de": "Von Hand gestellt – nächste Absenkung {uhrzeit} Uhr",
        "en": "Set manually – next setback at {uhrzeit}"},
    "handbetrieb_ohne": {
        "de": "Von Hand gestellt – kein Absenkpunkt im Plan",
        "en": "Set manually – no setback point in the schedule"},
    "manuell_erkannt": {
        "de": "Von Hand verstellt – der Planer hält sich bis {uhrzeit} Uhr zurück",
        "en": "Adjusted by hand – the planner stands back until {uhrzeit}"},

    # Anwesenheit
    "praesenz_bewegung": {"de": "Präsenzmelder meldet Bewegung",
                          "en": "Presence sensor reports movement"},
    "praesenz_stumm": {"de": "kein Präsenzmelder meldet sich",
                       "en": "no presence sensor is reporting"},
    "praesenz_niemand": {"de": "Präsenzmelder meldet niemanden",
                         "en": "presence sensor reports nobody"},
    "person_zuhause": {"de": "{name} ist zu Hause", "en": "{name} is at home"},
    "niemand_zuhause": {"de": "niemand zu Hause", "en": "nobody at home"},
    "heimkehr_erwartet": {"de": "Heimkehr erwartet – {grund}",
                          "en": "Return expected – {grund}"},
    "heimkehr_naehert": {"de": "{name} kommt näher, noch {km} km",
                         "en": "{name} is approaching, {km} km to go"},
    "leer_seit_grund": {"de": "{grund}, seit {minuten} Minuten leer",
                        "en": "{grund}, empty for {minuten} minutes"},
    "absenkung_in": {"de": " – {grund}, Absenkung in {minuten} Minuten",
                     "en": " – {grund}, setback in {minuten} minutes"},

    # Übersteuerung: Lage
    "regel_greift": {"de": "greift gerade", "en": "active now"},
    "regel_heute_nicht": {"de": "greift heute nicht – {grund}",
                          "en": "not active today – {grund}"},
    "regel_gerade_nicht": {"de": "greift gerade nicht – {grund}",
                           "en": "not active right now – {grund}"},
    "regel_ausserhalb": {
        "de": "greift gerade nicht – außerhalb {von}–{bis} Uhr",
        "en": "not active right now – outside {von}–{bis}"},
    "regel_ruht": {"de": "ruht", "en": "idle"},
    "regel_laeuft": {"de": "läuft", "en": "running"},
    "grund_meldet_nichts": {"de": "{name} meldet nichts",
                            "en": "{name} reports nothing"},
    "grund_zuhause": {"de": "{name} ist zu Hause", "en": "{name} is at home"},
    "grund_nicht_zuhause": {"de": "{name} ist nicht zu Hause",
                            "en": "{name} is not at home"},
    "grund_laeuft": {"de": "{name} läuft", "en": "{name} is on"},
    "grund_laeuft_nicht": {"de": "{name} läuft nicht", "en": "{name} is not on"},
    "grund_an": {"de": "{name} ist an", "en": "{name} is on"},
    "grund_aus": {"de": "{name} ist aus", "en": "{name} is off"},

    # Überwachung
    "wach_fehlt": {"de": "gibt es in Home Assistant nicht mehr",
                   "en": "no longer exists in Home Assistant"},
    "wach_unerreichbar": {"de": "ist nicht erreichbar", "en": "is unavailable"},
    "wach_stumm": {"de": "meldet sich nicht mehr", "en": "has stopped reporting"},
    "wach_batterie": {"de": "hat eine schwache Batterie", "en": "has a low battery"},
    "wach_verweigert": {"de": "nimmt keine Sollwerte an",
                        "en": "refuses to accept setpoints"},
    "wach_sommerpause": {
        "de": "steht in der Sommerpause und heizt deshalb nicht",
        "en": "is in summer pause and therefore does not heat"},
    "wach_seit": {"de": "zuletzt vor {stunden} Stunden",
                  "en": "last seen {stunden} hours ago"},
    "wach_versuche": {"de": "{anzahl} Versuche vergeblich",
                      "en": "{anzahl} attempts failed"},
    "wach_sommerpause_zusatz": {
        "de": ", das Gerät steht in der Sommerpause",
        "en": ", the device is in summer pause"},
    "wach_fritzbox": {"de": "in der FRITZ!Box beenden",
                      "en": "end it in the FRITZ!Box"},
    "wach_batterie_stand": {"de": "{prozent} %, Stand {uhrzeit} Uhr",
                            "en": "{prozent} %, as of {uhrzeit}"},
    "wach_meldung_titel": {
        "de": "Heizung: {anzahl} Thermostat{mehrzahl} ausgefallen",
        "en": "Heating: {anzahl} thermostat{mehrzahl} failed"},
    "wach_meldung_batterie": {"de": "Heizung: Batterie wird schwach",
                              "en": "Heating: battery running low"},
    "wach_wieder_titel": {"de": "Heizung: wieder in Ordnung",
                          "en": "Heating: back to normal"},
    "wach_wieder_zeile": {"de": "Wieder in Ordnung: {name}",
                          "en": "Back to normal: {name}"},
    "wach_meldet_wieder": {"de": "meldet sich wieder", "en": "is reporting again"},

    # Handbetrieb „nur absenken“
    "hand_ohne_punkt": {
        "de": "Von Hand gestellt – kein Absenkzeitpunkt hinterlegt",
        "en": "Set manually – no setback point defined"},
    "hand_ausblick": {
        "de": " – nächste Absenkung {uhrzeit} Uhr",
        "en": " – next setback at {uhrzeit}"},
    "hand_gestellt": {"de": "Von Hand gestellt{ausblick}",
                      "en": "Set manually{ausblick}"},
    "hand_absenkung": {
        "de": "Absenkung um {uhrzeit} Uhr auf {modus}",
        "en": "Setback at {uhrzeit} to {modus}"},
    "hand_verpasst": {
        "de": "Absenkung um {uhrzeit} Uhr verpasst, nicht nachgeholt{ausblick}",
        "en": "Setback at {uhrzeit} missed, not made up{ausblick}"},
    "hand_zurueck": {
        "de": "Sonderzustand vorbei – die Handeinstellung von {grad} {einheit} gilt wieder",
        "en": "Special state over – the manual setting of {grad} {einheit} applies again"},
    "hand_erkannt": {
        "de": "Von Hand auf {grad} {einheit} gestellt – der Planer hält sich bis zum "
              "nächsten Zeitplanwechsel zurück",
        "en": "Set to {grad} {einheit} by hand – the planner stands back until the "
              "next scheduled change"},
    "sperre_rest": {
        "de": "Fenster war offen – Sperre noch {minuten} Minuten",
        "en": "Window was open – locked for another {minuten} minutes"},
    "fehlt_entity": {
        "de": "{entity} ist in Home Assistant nicht vorhanden",
        "en": "{entity} does not exist in Home Assistant"},
    "nicht_uebernommen": {
        "de": "{name} nimmt das Ausschalten nicht an – von nun an schließt der "
              "Planer das Ventil über den Frostschutzwert",
        "en": "{name} refuses to switch off – from now on the planner closes "
              "the valve via the frost protection value"},
    "nicht_bestaetigt": {
        "de": "{grad} {einheit} bestätigt, steht aber weiter auf dem alten Wert",
        "en": "confirmed {grad} {einheit} but is still on the old value"},
    "sollwert_abgelehnt": {
        "de": "{name} nimmt den Sollwert {grad} {einheit} nicht an{grund}",
        "en": "{name} does not accept the setpoint of {grad} {einheit}{grund}"},
    "zurueck_auf": {"de": "zurück auf {grad} {einheit}", "en": "back to {grad} {einheit}"},
    "absenkung_leer": {
        "de": "{grund}, Absenkung in {minuten} Minuten",
        "en": "{grund}, setback in {minuten} minutes"},
    "leer_seit": {"de": "{minuten} Minuten leer", "en": "empty for {minuten} minutes"},

    # Protokoll
    "log_aus": {"de": "aus", "en": "off"},
    "log_stoerung": {"de": "Störung", "en": "fault"},
    "log_fehlgeschlagen": {"de": "fehlgeschlagen", "en": "failed"},
    "log_wieder_da": {"de": "wieder da", "en": "back"},
    "log_sommer_ein": {"de": "Sommerbetrieb ein", "en": "Summer mode on"},
    "log_sommer_aus": {"de": "Sommerbetrieb aus", "en": "Summer mode off"},
    "log_party_an": {"de": "Party an", "en": "Party on"},
    "log_party_aus": {"de": "Party aus", "en": "Party off"},
    "log_alle_raeume": {"de": "Alle Räume", "en": "All rooms"},
    "log_anlauf": {"de": "Anlauf", "en": "Warm-up"},
    "log_einrichtung": {"de": "Einrichtung", "en": "Setup"},
    "log_nicht_angenommen": {
        "de": "{entity} hat den Sollwert {grad} {einheit} nicht angenommen",
        "en": "{entity} did not accept the setpoint of {grad} {einheit}"},
    "log_gedaempft_uebernommen": {
        "de": "Gedämpfte Außentemperatur aus der Historie übernommen: {grad} {einheit}",
        "en": "Damped outdoor temperature taken from history: {grad} {einheit}"},
    "log_gedaempft_zurueck": {
        "de": "Gedämpfte Außentemperatur zurückgesetzt",
        "en": "Damped outdoor temperature reset"},
    "log_party_vorbei": {"de": "Der Zeitplan führt wieder",
                         "en": "The schedule is back in charge"},
    "log_party_beendet": {"de": "Vorzeitig beendet – der Zeitplan führt wieder",
                          "en": "Ended early – the schedule is back in charge"},
    "log_aussen_unbekannt": {"de": "Außentemperatur unbekannt",
                             "en": "Outdoor temperature unknown"},
    "log_gedaempft": {"de": "Gedämpfte Außentemperatur {grad} {einheit}",
                      "en": "Damped outdoor temperature {grad} {einheit}"},

    "log_fehlt": {"de": "fehlt", "en": "missing"},
    "log_bleibt_an": {"de": "bleibt an", "en": "stays on"},
    "log_nicht_bestaetigt": {"de": "nicht übernommen", "en": "not applied"},
    "log_manuell": {"de": "manuell", "en": "manual"},
    "log_party_vorbei_was": {"de": "Party vorbei", "en": "Party over"},

    # MQTT: Zustand des Planers
    "mq_trockenlauf": {"de": "Trockenlauf", "en": "Dry run"},
    "mq_automatik_aus": {"de": "Automatik aus", "en": "Automatic off"},
    "mq_sommer": {"de": "Sommerbetrieb", "en": "Summer mode"},
    "mq_urlaub": {"de": "Urlaub", "en": "Holiday"},
    "mq_aktiv": {"de": "{aktive} von {gesamt} Räumen aktiv",
                 "en": "{aktive} of {gesamt} rooms active"},

    # Hinweisbalken
    "hin_startet": {
        "de": "Home Assistant startet gerade – der Planer setzt aus, bis alle "
              "Geräte geladen sind.",
        "en": "Home Assistant is starting – the planner waits until all devices "
              "are loaded."},
    "hin_keine_raeume": {
        "de": "Noch keine Räume eingerichtet – der Assistent übernimmt sie aus "
              "Home Assistant.",
        "en": "No rooms set up yet – the assistant can import them from Home "
              "Assistant."},
    "hin_trockenlauf": {
        "de": "Trockenlauf ist aktiv: Der Planer rechnet, stellt aber kein "
              "Thermostat.",
        "en": "Dry run is active: the planner calculates but sets no thermostat."},
    "hin_automatik_aus": {"de": "Die Automatik ist ausgeschaltet.",
                          "en": "The automatic control is switched off."},
    "hin_entity_fehlt": {
        "de": "{feld}: {entity} gibt es in Home Assistant nicht.",
        "en": "{feld}: {entity} does not exist in Home Assistant."},
    "hin_kontakt_stumm": {
        "de": "Fensterkontakt {entity} (Raum „{raum}“) meldet nichts – der Raum "
              "fällt auf die Temperatursturz-Erkennung zurück.",
        "en": "Window contact {entity} (room “{raum}”) reports nothing – the room "
              "falls back to temperature-drop detection."},
    "hin_freigabe_fehlt": {
        "de": "Der Freigabeschalter {entity} (Raum „{raum}“) gibt es in Home "
              "Assistant nicht – der Raum wird deshalb normal geregelt.",
        "en": "The release switch {entity} (room “{raum}”) does not exist in Home "
              "Assistant – the room is therefore controlled normally."},
    "hin_melder_stumm": {
        "de": "Präsenzmelder {entity} (Raum „{raum}“) meldet nichts.",
        "en": "Presence sensor {entity} (room “{raum}”) reports nothing."},
    "hin_nur_praesenz_stumm": {
        "de": "Raum „{raum}“ soll allein dem Präsenzmelder folgen, aber keiner "
              "meldet sich – er gilt darum immer als belegt.",
        "en": "Room “{raum}” should follow its presence sensor alone, but none is "
              "reporting – it therefore always counts as occupied."},
    "hin_kein_thermostat": {"de": "Raum „{raum}“ hat kein Thermostat.",
                            "en": "Room “{raum}” has no thermostat."},
    "hin_kein_zeitplan": {
        "de": "Raum „{raum}“ hat keinen Zeitplan – es gilt dauerhaft die "
              "Eco-Temperatur.",
        "en": "Room “{raum}” has no schedule – the eco temperature applies "
              "permanently."},
    "hin_thermostat_weg": {
        "de": "{entity} (Raum „{raum}“) gibt es in Home Assistant nicht mehr.",
        "en": "{entity} (room “{raum}”) no longer exists in Home Assistant."},
    "hin_doppelt": {
        "de": "{entity} steht in „{a}“ und in „{b}“ – zwei Räume würden dasselbe "
              "Thermostat gegeneinander stellen.",
        "en": "{entity} is listed in “{a}” and in “{b}” – two rooms would set the "
              "same thermostat against each other."},
    "feld_aussen": {"de": "Außentemperatur", "en": "Outdoor temperature"},
    "feld_urlaub": {"de": "Urlaubsschalter", "en": "Holiday switch"},
    "feld_schulfrei": {"de": "Schulfrei-Schalter", "en": "Day-off switch"},
    "api_raum_fehlt": {"de": "Raum nicht gefunden", "en": "Room not found"},
    "api_keine_entitaet": {"de": "Keine Entität angegeben",
                           "en": "No entity given"},
    "api_dauer": {"de": "Ungültige Dauer", "en": "Invalid duration"},
    "api_kein_meldeweg": {"de": "Es ist kein Meldeweg eingestellt.",
                          "en": "No notification target is configured."},

    # Validierung
    "fehler_name": {"de": "Der Raum braucht einen Namen",
                    "en": "The room needs a name"},
    "fehler_kein_thermostat": {"de": "{entity} ist kein Thermostat",
                               "en": "{entity} is not a thermostat"},
    "fehler_max_min": {"de": "Das Maximum muss über dem Minimum liegen",
                       "en": "The maximum must be above the minimum"},
    "fehler_betriebsart": {"de": "Unbekannte Betriebsart {wert}",
                           "en": "Unknown operating mode {wert}"},
    "fehler_modus": {"de": "Unbekannter Modus {wert} in der Übersteuerung",
                     "en": "Unknown mode {wert} in the override"},
    "fehler_bedingung": {"de": "Unbekannte Bedingung {wert}",
                         "en": "Unknown condition {wert}"},
    "fehler_uhrzeit": {"de": "Ungültige Uhrzeit {wert} (erwartet HH:MM)",
                       "en": "Invalid time {wert} (expected HH:MM)"},
    "fehler_fenster_paar": {
        "de": "Übersteuerung: Zeitfenster braucht Anfang und Ende",
        "en": "Override: the time window needs a start and an end"},
    "fehler_fenster_gleich": {
        "de": "Übersteuerung: Anfang und Ende sind gleich",
        "en": "Override: start and end are the same"},
    "fehler_zahl": {"de": "{feld}: Zahl erwartet", "en": "{feld}: number expected"},
    "fehler_bereich": {"de": "{feld} muss zwischen {min} und {max} liegen",
                       "en": "{feld} must be between {min} and {max}"},

    # Kesselregelung
    "kessel_hinweis": {
        "de": "Der Heizungsplaner führt die Programmwahl nach dem Wärmebedarf "
              "der Räume.",
        "en": "The heating planner sets the program selection according to the "
              "rooms' demand for heat."},
    "kessel_wahl_nenn": {"de": "Nennbetrieb", "en": "nominal"},
    "kessel_wahl_reduziert": {"de": "Reduziert", "en": "reduced"},
    "kessel_wahl_sommer": {"de": "Sommerbetrieb", "en": "summer"},
    "kessel_wahl_standby": {"de": "Standby", "en": "standby"},
    "kessel_gestellt": {"de": "Kessel auf {wahl}", "en": "Boiler to {wahl}"},
    "kessel_gestellt_warum": {
        "de": "Die Programmwahl der Regelung steht jetzt auf {wahl} – so weit "
              "reicht der Wärmebedarf der Räume.",
        "en": "The controller's program selection is now {wahl} – that is as "
              "far as the rooms' demand for heat goes."},
    "kessel_freigegeben": {"de": "Kessel wieder freigegeben",
                           "en": "Boiler released again"},
    "kessel_freigegeben_warum": {
        "de": "Die Übernahme wurde im Heizungsanlagenmanager aufgehoben. Der "
              "Planer stellt die Programmwahl nicht mehr; einschalten lässt "
              "sie sich hier unter Einstellungen.",
        "en": "The takeover was released in the heating system manager. The "
              "planner no longer sets the program selection; you can switch "
              "it on again here under Settings."},
    "kessel_keine_wahl": {
        "de": "Der Heizungsanlagenmanager hat in dieser Regelung keine "
              "Programmwahl gefunden. Erst den Parameterkatalog aufbauen.",
        "en": "The heating system manager found no program selection in this "
              "controller. Build the parameter catalogue first."},
    "kessel_unbekannt": {
        "de": "Diese Regelung kennt keinen passenden Wert für {wahl}.",
        "en": "This controller has no matching value for {wahl}."},
    "kessel_gesperrt": {
        "de": "Der Heizungsanlagenmanager lässt das Stellen noch nicht zu. "
              "Dort unter Einstellungen freigeben.",
        "en": "The heating system manager does not permit setting yet. "
              "Release it there under Settings."},
    "kessel_fremd": {
        "de": "Die Programmwahl wird bereits von {quelle} geführt.",
        "en": "The program selection is already held by {quelle}."},
}
