#!/usr/bin/env python3
"""Trockenprüfung der Regellogik – ohne Home Assistant, ohne Fremdpakete.

Aufruf aus dem Repo:

    python3 heizungsplaner/tests/test_logik.py

Geprüft wird alles, was ohne laufende Anlage prüfbar ist: Zeitplan über
Tagesgrenzen, Heizkurve und Sommerhysterese, Anwesenheit samt Heimkehr,
Fenstererkennung, die Betriebsart „nur absenken“ und das Schreiben auf Flanke.
Mehrere dieser Fälle stehen hier, weil sie in der Praxis einmal falsch waren –
etwa die Schule in einem Kilometer Entfernung, die das Kinderzimmer den ganzen
Vormittag als „auf dem Heimweg“ gelten ließ.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "backend"))

import anwesenheit
import regelung
import json
import einheit
import store
import texte
import witterung
import zeitplan as zp

fehler = []


def pruefe(bedingung, text):
    if bedingung:
        print(f"  ok   {text}")
    else:
        print(f"  FEHL {text}")
        fehler.append(text)


print("\n=== Zeitplan ===")
plan = zp.standardplan("wohnraum")
# Montag, 25.08.2026 ist ein Dienstag -> nehmen wir einen echten Montag
montag = datetime(2026, 8, 24, 6, 0)      # Montag 06:00
pruefe(zp.aktueller_eintrag(plan, montag, False)["modus"] == "komfort",
       "Montag 06:00 Schultag -> komfort (05:30-Punkt)")
pruefe(zp.aktueller_eintrag(plan, montag.replace(hour=8), False)["modus"] == "eco",
       "Montag 08:00 Schultag -> eco")
pruefe(zp.aktueller_eintrag(plan, montag.replace(hour=14), False)["modus"] == "komfort",
       "Montag 14:00 Schultag -> komfort")
pruefe(zp.aktueller_eintrag(plan, montag.replace(hour=22), False)["modus"] == "nacht",
       "Montag 22:00 -> nacht")
nacht = zp.aktueller_eintrag(plan, montag.replace(hour=2), False)
pruefe(nacht and nacht["modus"] == "nacht",
       "Montag 02:00 -> nacht von gestern Abend (über Mitternacht)")
sonntag = datetime(2026, 8, 23, 10, 0)
pruefe(zp.aktueller_eintrag(plan, sonntag, True)["modus"] == "komfort",
       "Sonntag 10:00 schulfrei -> komfort (09:00-Punkt)")
pruefe(zp.aktueller_eintrag(plan, sonntag.replace(hour=7), True)["modus"] == "nacht",
       "Sonntag 07:00 schulfrei -> noch nacht")

wechsel = zp.naechster_wechsel(plan, montag.replace(hour=8), False)
pruefe(wechsel and wechsel[1]["start"] == "12:30", "nächster Wechsel nach 08:00 ist 12:30")

raum = dict(store.STANDARD_RAUM, name="Test", zeitplan=plan,
            komfort=23.0, eco=19.0, nacht=19.0, abwesend=17.0)
waermer = zp.naechster_waermerer_wechsel(raum, montag.replace(hour=4), False, 19.0, 8.0)
pruefe(waermer and waermer[1]["start"] == "05:30", "nächster wärmerer Wechsel ab 04:00 = 05:30")

print("\n=== Witterung ===")
pruefe(witterung.korrektur(-10, {"aktiv": True, "basis_aussen": 15, "steilheit": 0.06,
                                 "max_korrektur": 1.5}) == 1.5,
       "-10 °C -> Deckel +1.5 K")
pruefe(witterung.korrektur(15, {"aktiv": True, "basis_aussen": 15, "steilheit": 0.06,
                                "max_korrektur": 1.5}) == 0.0,
       "15 °C -> keine Korrektur")
pruefe(witterung.korrektur(0, {"aktiv": True, "basis_aussen": 15, "steilheit": 0.06,
                               "max_korrektur": 1.5}) == 0.9,
       "0 °C -> +0.9 K")
sommer = {"aktiv": True, "grenze": 16.0, "hysterese": 1.5}
pruefe(witterung.sommerbetrieb(18.0, sommer, False) is True, "18 °C -> Sommer an")
pruefe(witterung.sommerbetrieb(15.0, sommer, True) is True, "15 °C bleibt Sommer (Hysterese)")
pruefe(witterung.sommerbetrieb(14.0, sommer, True) is False, "14.4 °C -> Sommer aus")
pruefe(witterung.sommerbetrieb(15.0, sommer, False) is False, "15 °C startet nicht neu")
g = witterung.daempfen(10.0, 20.0, 3600, 6.0)
pruefe(9.0 < g < 12.0, f"Dämpfung über eine Stunde bleibt träge ({g:.2f})")
pruefe(witterung.vorlaufminuten(0, {"aktiv": True, "grund_min": 30,
                                    "min_pro_grad": 2.0, "max_min": 120}) == 60,
       "0 °C -> 60 Minuten Vorlauf")
pruefe(witterung.vorlaufminuten(20, {"aktiv": True, "grund_min": 30,
                                     "min_pro_grad": 2.0, "max_min": 120}) == 30,
       "20 °C -> Grundvorlauf")

print("\n=== Anwesenheit ===")
personen = {
    "person.sven": {"name": "Sven", "zuhause": False, "entfernung_km": 5.0, "zustand": "StatZon1"},
    "person.luna": {"name": "Luna", "zuhause": True, "entfernung_km": None, "zustand": "home"},
}
r_luna = dict(store.STANDARD_RAUM, name="Luna", personen=["person.luna"])
r_sven = dict(store.STANDARD_RAUM, name="Büro", personen=["person.sven"])
besetzt, grund = anwesenheit.raum_besetzt(r_luna, {}, personen)
pruefe(besetzt, f"Lunas Zimmer besetzt ({grund})")
besetzt, grund = anwesenheit.raum_besetzt(r_sven, {}, personen)
pruefe(not besetzt, f"Büro leer ({grund})")
# Heimkehr setzt voraus, dass die Person sich auch naehert
personen["person.sven"]["naehert_sich"] = True
heim, grund = anwesenheit.kommt_heim(r_sven, personen, 8.0)
pruefe(heim, f"Sven auf dem Heimweg erkannt ({grund})")
heim, _ = anwesenheit.kommt_heim(r_sven, personen, 2.0)
pruefe(not heim, "bei 2 km Schwelle noch keine Heimkehr")

print("\n--- Schule in Sichtweite ---")
# Nele ist in der Realschule, 1 km Luftlinie. Ohne weitere Pruefung waere sie
# den ganzen Schultag \"auf dem Heimweg\".
schulkind = {"person.nele": {"name": "Nele", "zuhause": False, "entfernung_km": 1.0,
                             "zustand": "Realschule", "in_zone": "Realschule",
                             "naehert_sich": False}}
r_nele = dict(store.STANDARD_RAUM, name="Nele Zimmer", personen=["person.nele"])
heim, grund = anwesenheit.kommt_heim(r_nele, schulkind, 8.0)
pruefe(not heim, "Kind in der Schulzone gilt nicht als heimkehrend")

# Auch ohne Zonenmeldung darf blosse Naehe nicht genuegen
ohne_zone = {"person.nele": {**schulkind["person.nele"], "in_zone": None,
                             "naehert_sich": False}}
heim, grund = anwesenheit.kommt_heim(r_nele, ohne_zone, 8.0)
pruefe(not heim, "blosse Naehe ohne Annaeherung genuegt nicht")

# Auf dem Heimweg: Zone verlassen und Entfernung nimmt ab
unterwegs = {"person.nele": {**schulkind["person.nele"], "in_zone": None,
                             "naehert_sich": True, "entfernung_km": 0.6}}
heim, grund = anwesenheit.kommt_heim(r_nele, unterwegs, 8.0)
pruefe(heim, f"auf dem Heimweg erkannt ({grund})")

print("\n--- Annaeherung aus dem Verlauf ---")
from datetime import timedelta
def lauf(werte, mindest=0.3):
    """werte: Liste (minuten_vor_jetzt, km) -> naehert_sich beim letzten Takt"""
    jetzt = datetime(2026, 8, 25, 12, 0)
    gedaechtnis = {}
    ergebnis = None
    for minuten, km in werte:
        zeitpunkt = jetzt + timedelta(minutes=minuten)
        p = {"person.x": {"name": "X", "zuhause": False, "entfernung_km": km,
                          "zustand": "not_home", "in_zone": None,
                          "naehert_sich": False}}
        anwesenheit.bewegung_fortschreiben(p, gedaechtnis, zeitpunkt, mindest)
        ergebnis = p["person.x"]["naehert_sich"]
    return ergebnis

pruefe(lauf([(0, 1.0), (5, 1.0), (10, 1.0), (16, 1.0), (21, 1.0)]) is False,
       "gleichbleibende Entfernung (Schule) -> keine Annaeherung")
pruefe(lauf([(0, 5.0), (5, 4.0), (10, 3.0), (16, 2.0), (21, 1.0)]) is True,
       "abnehmende Entfernung -> Annaeherung")
pruefe(lauf([(0, 1.0), (5, 2.0), (10, 3.0), (16, 4.0), (21, 5.0)]) is False,
       "zunehmende Entfernung -> keine Annaeherung")
pruefe(lauf([(0, 1.0), (5, 1.05), (10, 0.95), (16, 1.0), (21, 0.9)]) is False,
       "GPS-Rauschen um 100 m loest nichts aus")
pruefe(lauf([(0, 1.0), (5, 1.0), (10, 1.0), (16, 1.0), (21, 0.5)]) is True,
       "Aufbruch nach Hause wird erkannt")
alle = dict(store.STANDARD_RAUM, name="Wohnzimmer", personen=[])
besetzt, _ = anwesenheit.raum_besetzt(alle, {}, personen)
pruefe(besetzt, "Raum ohne Personenzuordnung folgt der ganzen Familie")

print("\n=== Modulverweise ===")
# Der Anlass: mqtt_publisher rief seit v1.15.0 `einheit.einheit()` auf, ohne
# das Modul zu importieren. Auffallen konnte das nicht, weil der Aufruf im
# Discovery-Pfad steckt, der seinen Fehler nur in den Log schreibt - die
# MQTT-Entitaeten fehlten sechs Tage lang stillschweigend.
#
# Diese Pruefung faengt die ganze Fehlerklasse: Wer `modul.funktion()` schreibt,
# muss `modul` auch importiert haben.
import ast as _ast
import pathlib as _pl

_be = _pl.Path(__file__).resolve().parent.parent / "backend"
_module = {d.stem for d in _be.glob("*.py")}
_fehlend = []
for _datei in sorted(_be.glob("*.py")):
    _baum = _ast.parse(_datei.read_text(encoding="utf-8"))
    _bekannt, _zugewiesen = set(), set()
    for _k in _ast.walk(_baum):
        if isinstance(_k, _ast.Import):
            _bekannt.update((a.asname or a.name).split(".")[0] for a in _k.names)
        elif isinstance(_k, _ast.ImportFrom):
            _bekannt.update(a.asname or a.name for a in _k.names)
        elif isinstance(_k, _ast.Name) and isinstance(_k.ctx, _ast.Store):
            _zugewiesen.add(_k.id)
        elif isinstance(_k, _ast.arg):
            _zugewiesen.add(_k.arg)
    for _k in _ast.walk(_baum):
        # Nur `modul.attribut` zaehlt, und nur wenn der Name nirgends im
        # Modul zugewiesen wird - sonst meldet eine gleichnamige Variable.
        if (isinstance(_k, _ast.Attribute) and isinstance(_k.value, _ast.Name)
                and _k.value.id in _module and _k.value.id != _datei.stem
                and _k.value.id not in _bekannt and _k.value.id not in _zugewiesen):
            _fehlend.append(f"{_datei.name}:{_k.lineno} benutzt "
                            f"{_k.value.id}.{_k.attr}, importiert {_k.value.id} aber nicht")
pruefe(not _fehlend, "jedes benutzte Modul ist auch importiert"
       + ("" if not _fehlend else " -> " + "; ".join(_fehlend[:3])))

print("\n=== Werktag und arbeitsfrei ===")
# Finn arbeitet: In den Schulferien hat er Dienst, an einem Feiertag nicht.
# Das Wochenende steckt schon in den Wochentag-Haken, hier zaehlt nur der
# Feiertag.
plan_finn = [
    {"start": "06:00", "modus": "komfort", "gilt": "werktag",
     "tage": ["mon", "tue", "wed", "thu", "fri"]},
    {"start": "09:00", "modus": "komfort", "gilt": "arbeitsfrei",
     "tage": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]},
]
montag = datetime(2026, 9, 7, 7, 0)      # Montag, bayerische Sommerferien
# Der Arbeitstag-Schalter ist "an", wenn gearbeitet wird - Wochenende und
# Feiertage also "aus". Genau so liefert es die Workday-Integration.
e = zp.aktueller_eintrag(plan_finn, montag, True, True)
pruefe(e is not None and e["gilt"] == "werktag",
       "in den Schulferien gilt fuer Finn der Werktag-Punkt")
e = zp.aktueller_eintrag(plan_finn, montag, True, False)
pruefe(e is None or e["gilt"] != "werktag",
       "an einem arbeitsfreien Tag greift der Werktag-Punkt nicht")
mittag = datetime(2026, 9, 7, 12, 0)
e = zp.aktueller_eintrag(plan_finn, mittag, True, False)
pruefe(e is not None and e["gilt"] == "arbeitsfrei",
       "am Feiertag oder Wochenende gilt der arbeitsfrei-Punkt")
# Ohne Arbeitstag-Quelle darf keine der beiden Haelften greifen, sonst gaelten
# sie gleichzeitig.
e = zp.aktueller_eintrag(plan_finn, mittag, True, None)
pruefe(e is None, "ohne Arbeitstag-Quelle bleiben Werktag und arbeitsfrei stumm")

# Die Schul-Punkte duerfen davon voellig unberuehrt bleiben.
plan_luna = [{"start": "06:00", "modus": "komfort", "gilt": "schultag",
              "tage": ["mon"]}]
e = zp.aktueller_eintrag(plan_luna, montag, False, None)
pruefe(e is not None, "Schultag funktioniert weiterhin ohne Arbeitstag-Quelle")
e = zp.aktueller_eintrag(plan_luna, montag, True, None)
pruefe(e is None, "in den Ferien greift der Schultag-Punkt nicht")

pruefe("werktag" in store.GELTUNG and "arbeitsfrei" in store.GELTUNG,
       "die Pruefung kennt die neuen Geltungen")
try:
    store.validate_zeitplan([{"start": "06:00", "modus": "komfort",
                              "gilt": "montags", "tage": ["mon"]}])
    pruefe(False, "eine erfundene Geltung wird abgelehnt")
except store.ValidationError:
    pruefe(True, "eine erfundene Geltung wird abgelehnt")

print("\n=== Wer zum Haushalt zaehlt ===")
# Der Fall, der die Absenkung lautlos toetet: eine Person ohne Geraetetracker.
# Sie steht dauerhaft auf "home" und hielte jeden Raum fuer besetzt.
haus_index = {
    "person.sven": {"state": "not_home", "attributes": {"friendly_name": "Sven"}},
    "person.gast": {"state": "home", "attributes": {"friendly_name": "Gastkonto"}},
    "zone.home": {"state": "1", "attributes": {}},
}
alle = anwesenheit.personen_status(haus_index, None, set())
pruefe(len(alle) == 2, "ohne Angabe zaehlen alle Personen (bisheriges Verhalten)")
pruefe(alle["person.gast"]["zuhause"], "das Gastkonto gilt als zu Hause")

eng = anwesenheit.personen_status(haus_index, None, set(), ["person.sven"])
pruefe(list(eng) == ["person.sven"], "mit Haushaltsliste bleibt nur, wer darin steht")
leer = anwesenheit.personen_status(haus_index, None, set(), [])
pruefe(len(leer) == 2, "eine leere Liste heisst weiterhin: alle")

e_haus = store.validate_einstellungen({"haushalt": ["person.sven", "  ", "sensor.unfug"]})
pruefe(e_haus["haushalt"] == ["person.sven"],
       "die Pruefung wirft Leerzeichen und Nicht-Personen heraus")
pruefe(store.standard_einstellungen()["haushalt"] == [],
       "ab Werk ist die Liste leer, es zaehlen also alle")

print("\n=== Regelkette ===")
einst = store.validate_einstellungen({})
einst["trockenlauf"] = True


def umgebung(jetzt, **extra):
    basis = {
        "jetzt": jetzt, "einstellungen": einst, "states_index": {},
        "aussen": 5.0, "aussen_gedaempft": 6.0, "sommerbetrieb": False,
        "urlaub": False, "schulfrei": False, "personen": personen,
        "raum_wechsel": {},
    }
    basis.update(extra)
    return basis


wohnzimmer = store.validate_raum({
    "name": "Wohnzimmer", "thermostate": ["climate.a"], "personen": [],
    "komfort": 23.0, "eco": 19.0, "nacht": 19.0, "abwesend": 17.0,
    "min": 5.0, "max": 26.0, "zeitplan": plan,
})

rz = {}
e = regelung.entscheide(wohnzimmer, rz, umgebung(montag.replace(hour=14)))
pruefe(e["zustand"] == "komfort" and e["ziel"] == 23.5,
       f"Montag 14:00, 5 °C außen -> komfort 23.5 ({e['ziel']}, {e['begruendung']})")

e = regelung.entscheide(wohnzimmer, {}, umgebung(montag.replace(hour=14), urlaub=True))
pruefe(e["zustand"] == "urlaub" and e["ziel"] == 12.0, "Urlaub schlägt den Zeitplan")

e = regelung.entscheide(wohnzimmer, {}, umgebung(montag.replace(hour=14), sommerbetrieb=True))
pruefe(e["zustand"] == "sommer" and e.get("ventil_zu"), "Sommerbetrieb schließt das Ventil")

# Abwesenheit: Raum seit zwei Stunden leer, niemand in der Nähe
leer_personen = {"person.sven": {"name": "Sven", "zuhause": False,
                                 "entfernung_km": 40.0, "zustand": "StatZon1",
                                 "in_zone": None, "naehert_sich": False}}
rz_leer = {"leer_seit": (montag.replace(hour=12)).isoformat(timespec="seconds")}
e = regelung.entscheide(wohnzimmer, rz_leer,
                        umgebung(montag.replace(hour=14), personen=leer_personen))
pruefe(e["zustand"] == "abwesend" and e["ziel"] == 17.0,
       f"leeres Haus -> Abwesenheitstemperatur ({e['ziel']}, {e['begruendung']})")

# Heimkehr hebt die Absenkung auf - naeher kommend und in keiner Zone
nah = {"person.sven": {"name": "Sven", "zuhause": False, "entfernung_km": 4.0,
                       "zustand": "not_home", "in_zone": None,
                       "naehert_sich": True}}
e = regelung.entscheide(wohnzimmer, dict(rz_leer),
                        umgebung(montag.replace(hour=14), personen=nah))
pruefe(e["zustand"] == "heimkehr" and e["ziel"] > 20,
       f"Heimkehr hebt die Absenkung auf ({e['ziel']}, {e['begruendung']})")

# Karenzzeit: gerade erst gegangen -> noch keine Absenkung
rz_frisch = {"leer_seit": (montag.replace(hour=13, minute=50)).isoformat(timespec="seconds")}
e = regelung.entscheide(wohnzimmer, rz_frisch,
                        umgebung(montag.replace(hour=14), personen=leer_personen))
pruefe(e["zustand"] == "komfort", f"innerhalb der Karenzzeit bleibt es warm ({e['begruendung']})")

# Vorheizen: 05:00 Uhr, Wechsel auf komfort um 05:30, bei 5 °C = 50 min Vorlauf
e = regelung.entscheide(wohnzimmer, {}, umgebung(montag.replace(hour=5, minute=0)))
pruefe(e["ziel"] > 22, f"05:00 Uhr wird für 05:30 vorgeheizt ({e['ziel']}, {e['begruendung']})")

# Fenstersturz
rz_fenster = {"temperaturquelle": "thermostate", "verlauf": [
    [(montag.replace(hour=13, minute=55)).isoformat(timespec="seconds"), 22.5],
    [(montag.replace(hour=13, minute=58)).isoformat(timespec="seconds"), 21.6],
]}
states_index = {"climate.a": {"entity_id": "climate.a", "state": "heat",
                              "attributes": {"current_temperature": 20.9,
                                             "temperature": 23.0,
                                             "min_temp": 5, "max_temp": 30,
                                             "hvac_modes": ["off", "heat"]}}}
e = regelung.entscheide(wohnzimmer, rz_fenster,
                        umgebung(montag.replace(hour=14), states_index=states_index))
pruefe(e["zustand"] == "fenster" and e["ziel"] == 8.0,
       f"Temperatursturz erkannt ({e['begruendung']})")

# Sperre wirkt nach
rz_sperre = {"temperaturquelle": "thermostate", "fenster_bis": (montag.replace(hour=14, minute=20)).isoformat(timespec="seconds")}
e = regelung.entscheide(wohnzimmer, rz_sperre, umgebung(montag.replace(hour=14)))
pruefe(e["zustand"] == "fenster", f"Fenstersperre läuft nach ({e['begruendung']})")

# Grenzen des Raumes werden eingehalten: Komfort 20.0 plus Heizkurve wäre 20.6
eng = store.validate_raum({**wohnzimmer, "max": 20.0, "komfort": 20.0,
                           "eco": 19.0, "nacht": 19.0, "abwesend": 17.0})
e = regelung.entscheide(eng, {}, umgebung(montag.replace(hour=14)))
pruefe(e["ziel"] == 20.0, f"Obergrenze des Raumes deckelt die Heizkurve ({e['ziel']})")

# Ein Komfortwert außerhalb der Raumgrenzen ist ein Konfigurationsfehler
try:
    store.validate_raum({**wohnzimmer, "max": 20.0, "komfort": 23.0})
    pruefe(False, "Komfort über dem Raum-Maximum wird abgelehnt")
except store.ValidationError:
    pruefe(True, "Komfort über dem Raum-Maximum wird abgelehnt")

print("\n=== Übersteuerung durch einen Schalter ===")

# Ein Homeoffice-Schalter soll das Buero auf Komfort halten, statt es
# vormittags nach Plan abzusenken.
def lage_uebersteuert(schalter_an, modus="komfort", niemand_da=False, sommer=False):
    r = store.validate_raum({**wohnzimmer, "anwesenheit": not niemand_da,
                             "uebersteuerung": [{"entity": "input_boolean.homeoffice",
                                                 "modus": modus}],
                             "zeitplan": [{"start": "07:30", "modus": "eco",
                                           "gilt": "immer",
                                           "tage": ["mon","tue","wed","thu","fri","sat","sun"]}]})
    idx = {"climate.a": {"entity_id": "climate.a", "state": "heat",
                         "attributes": {"current_temperature": 20.0, "temperature": 19.0,
                                        "min_temp": 5, "max_temp": 30,
                                        "hvac_modes": ["off", "heat"]}},
           "input_boolean.homeoffice": {
               "entity_id": "input_boolean.homeoffice",
               "state": "on" if schalter_an else "off",
               "attributes": {"friendly_name": "Homeoffice"}}}
    return regelung.entscheide(r, {"temperaturquelle": "thermostate"},
                               umgebung(montag.replace(hour=9), states_index=idx,
                                        sommerbetrieb=sommer))

aus = lage_uebersteuert(False)
pruefe(aus["zustand"] == "eco", f"ohne Schalter fuehrt der Zeitplan ({aus['zustand']})")

an = lage_uebersteuert(True)
pruefe(an["zustand"] == "komfort" and "Homeoffice" in an["begruendung"],
       f"eingeschaltet uebersteuert der Schalter den Plan ({an['begruendung']})")

# Der Schalter hebelt weder Sommerbetrieb noch ein offenes Fenster aus.
sommer = lage_uebersteuert(True, sommer=True)
pruefe(sommer["zustand"] == "sommer",
       f"im Sommerbetrieb bleibt der Schalter wirkungslos ({sommer['zustand']})")

# Die eigentliche Homeoffice-Regelung braucht keinen Schalter: Werktag, keine
# Ferien und Isabel zu Hause - alle drei Bedingungen zusammen.
def lage_homeoffice(werktag=True, ferien=False, isabel="home"):
    r = store.validate_raum({**wohnzimmer, "uebersteuerung": [{
        "modus": "komfort",
        "wenn": [{"entity": "binary_sensor.workday", "zustand": "an"},
                 {"entity": "calendar.ferien", "zustand": "aus"},
                 {"entity": "person.isabel", "zustand": "an"}]}],
        "zeitplan": [{"start": "07:30", "modus": "eco", "gilt": "immer",
                      "tage": ["mon","tue","wed","thu","fri","sat","sun"]}]})
    idx = {"climate.a": {"entity_id": "climate.a", "state": "heat",
                         "attributes": {"current_temperature": 20.0, "temperature": 19.0,
                                        "min_temp": 5, "max_temp": 30,
                                        "hvac_modes": ["off", "heat"]}},
           "binary_sensor.workday": {"entity_id": "binary_sensor.workday",
                                     "state": "on" if werktag else "off",
                                     "attributes": {"friendly_name": "Werktag"}},
           "calendar.ferien": {"entity_id": "calendar.ferien",
                               "state": "on" if ferien else "off",
                               "attributes": {"friendly_name": "Ferien"}},
           "person.isabel": {"entity_id": "person.isabel", "state": isabel,
                             "attributes": {"friendly_name": "Isabel"}}}
    return regelung.entscheide(r, {"temperaturquelle": "thermostate"},
                               umgebung(montag.replace(hour=9), states_index=idx))

# Ohne Zeitfenster liefe eine Homeoffice-Regel auch nachts um drei weiter -
# die Bedingungen treffen ja weiter zu.
def lage_fenster(stunde, von="08:00", bis="18:00"):
    r = store.validate_raum({**wohnzimmer, "uebersteuerung": [{
        "name": "Homeoffice", "modus": "komfort", "von": von, "bis": bis,
        "wenn": [{"entity": "person.isabel", "zustand": "an"}]}],
        "zeitplan": [{"start": "21:00", "modus": "nacht", "gilt": "immer",
                      "tage": ["mon","tue","wed","thu","fri","sat","sun"]}]})
    idx = {"climate.a": {"entity_id": "climate.a", "state": "heat",
                         "attributes": {"current_temperature": 20.0, "temperature": 19.0,
                                        "min_temp": 5, "max_temp": 30,
                                        "hvac_modes": ["off", "heat"]}},
           "person.isabel": {"entity_id": "person.isabel", "state": "home",
                             "attributes": {"friendly_name": "Isabel"}}}
    return regelung.entscheide(r, {"temperaturquelle": "thermostate"},
                               umgebung(montag.replace(hour=stunde), states_index=idx))

# Die Lage-Auskunft, die auch ueber MQTT aufs Dashboard geht
def lage_auskunft(isabel="home", ferien="off", stunde=10):
    r = store.validate_raum({**wohnzimmer, "uebersteuerung": [{
        "name": "Homeoffice", "modus": "komfort", "von": "08:00", "bis": "18:00",
        "wenn": [{"entity": "calendar.ferien", "zustand": "aus"},
                 {"entity": "person.isabel", "zustand": "an"}]}]})
    idx = {"calendar.ferien": {"entity_id": "calendar.ferien", "state": ferien,
                               "attributes": {"friendly_name": "Ferien & Feiertage"}},
           "person.isabel": {"entity_id": "person.isabel", "state": isabel,
                             "attributes": {"friendly_name": "Isabel"}}}
    return regelung.uebersteuerung_lage(r, idx, montag.replace(hour=stunde))

a = lage_auskunft()
pruefe(a["greift"] and a["name"] == "Homeoffice", f"Lage: greift ({a})")
pruefe(a["bis"] == "bis 18:00 Uhr",
       f"Lage: nennt das Ende fuer die Kachel ({a.get('bis')!r})")
# Ein leeres Attribut lässt eine Tile-Karte auf den Zustand zurückfallen –
# dann stuende dort der Zielwert. Deshalb ist "bis" nie leer.
a = lage_auskunft(ferien="on")
pruefe(a["bis"] == "ruht", f"Lage: „bis“ bleibt gefuellt ({a.get('bis')!r})")
a = lage_auskunft(ferien="on")
pruefe(not a["greift"] and a["lage"] == "greift heute nicht – Ferien & Feiertage läuft",
       f"Lage: Ferientag wird als heute benannt ({a['lage']})")
a = lage_auskunft(isabel="not_home")
pruefe(a["lage"] == "greift gerade nicht – Isabel ist nicht zu Hause",
       f"Lage: abwesende Person ist eine Frage des Augenblicks ({a['lage']})")
a = lage_auskunft(stunde=3)
pruefe("außerhalb 08:00–18:00" in a["lage"],
       f"Lage: das Zeitfenster wird benannt ({a['lage']})")

pruefe(lage_fenster(10)["zustand"] == "komfort",
       "im Fenster greift die Regel")
pruefe(lage_fenster(3)["zustand"] == "nacht",
       f"nachts greift sie nicht ({lage_fenster(3)['zustand']})")
pruefe(lage_fenster(20)["zustand"] == "nacht",
       f"nach Feierabend greift sie nicht ({lage_fenster(20)['zustand']})")
pruefe("bis 18:00 Uhr" in lage_fenster(10)["begruendung"],
       f"die Begruendung nennt das Ende ({lage_fenster(10)['begruendung']})")
# Ein Fenster ueber Mitternacht - fuer ein Schlafzimmer etwa
pruefe(lage_fenster(23, von="22:00", bis="06:00")["zustand"] == "komfort",
       "ein Fenster ueber Mitternacht greift abends")
pruefe(lage_fenster(3, von="22:00", bis="06:00")["zustand"] == "komfort",
       "und noch am naechsten Morgen")
pruefe(lage_fenster(12, von="22:00", bis="06:00")["zustand"] != "komfort",
       "tagsueber aber nicht")

e = lage_homeoffice()
pruefe(e["zustand"] == "komfort" and "Isabel" in e["begruendung"],
       f"Werktag + keine Ferien + Isabel daheim -> komfort ({e['begruendung']})")
e = lage_homeoffice(ferien=True)
pruefe(e["zustand"] == "eco", f"in den Ferien greift die Regel nicht ({e['zustand']})")
e = lage_homeoffice(werktag=False)
pruefe(e["zustand"] == "eco", f"am Wochenende greift die Regel nicht ({e['zustand']})")
e = lage_homeoffice(isabel="not_home")
pruefe(e["zustand"] == "eco", f"ohne Isabel greift die Regel nicht ({e['zustand']})")
e = lage_homeoffice(isabel="Arbeit")
pruefe(e["zustand"] == "eco",
       f"in einer anderen Zone zaehlt Isabel nicht als daheim ({e['zustand']})")

print("\n=== Fensterkontakte ===")

def fensterlage(kontakte, zustaende, verlauf_sturz=True, zusatz=False):
    """Hilfskonstrukt: Raum mit Kontakten, dazu ein Temperatursturz im Verlauf."""
    r = store.validate_raum({**wohnzimmer, "fenster": kontakte,
                             "sturz_auch_mit_kontakten": zusatz})
    idx = {"climate.a": {"entity_id": "climate.a", "state": "heat",
                         "attributes": {"current_temperature": 20.9, "temperature": 23.0,
                                        "min_temp": 5, "max_temp": 30,
                                        "hvac_modes": ["off", "heat"]}}}
    for eid, zustand in zustaende.items():
        idx[eid] = {"entity_id": eid, "state": zustand,
                    "attributes": {"friendly_name": eid.split(".")[-1]}}
    rz = {"temperaturquelle": "thermostate", "verlauf": [
        [(montag.replace(hour=13, minute=55)).isoformat(timespec="seconds"), 22.5],
    ]} if verlauf_sturz else {"temperaturquelle": "thermostate"}
    return regelung.entscheide(r, rz, umgebung(montag.replace(hour=14),
                                               states_index=idx))

e = fensterlage(["binary_sensor.fenster_wz"], {"binary_sensor.fenster_wz": "on"})
pruefe(e["zustand"] == "fenster" and "offen" in e["begruendung"],
       f"offener Kontakt schlaegt an ({e['begruendung']})")

e = fensterlage(["binary_sensor.fenster_wz"], {"binary_sensor.fenster_wz": "off"})
pruefe(e["zustand"] != "fenster",
       f"geschlossener Kontakt unterdrueckt die Sturzerkennung ({e['zustand']})")

e = fensterlage(["binary_sensor.fenster_wz"], {"binary_sensor.fenster_wz": "off"},
                zusatz=True)
pruefe(e["zustand"] == "fenster",
       "mit Zusatzoption greift der Sturz auch bei geschlossenem Kontakt")

e = fensterlage(["binary_sensor.fenster_wz"], {"binary_sensor.fenster_wz": "unavailable"})
pruefe(e["zustand"] == "fenster",
       f"ausgefallener Kontakt faellt auf den Sturz zurueck ({e['begruendung']})")

e = fensterlage(["binary_sensor.fenster_wz"], {"binary_sensor.fenster_wz": "unavailable"},
                verlauf_sturz=False)
pruefe("melden nichts" in e["begruendung"],
       f"ausgefallener Kontakt wird benannt ({e['begruendung']})")

# Die geraeteeigene Fenstererkennung eines Thermostats ist kein Kontakt: Sie
# loest aus, verdraengt die Sturzerkennung aber nicht. Sonst stuende ein Raum,
# dessen einziger "Kontakt" eine solche Meldung ist, ohne Fenstererkennung da,
# sobald das Geraet abgeschaltet ist - so war es in der Gaestetoilette.
GERAETEEIGEN = "binary_sensor.heizung_gaeste_offenes_fenster_erkannt"

e = fensterlage([GERAETEEIGEN], {GERAETEEIGEN: "on"})
pruefe(e["zustand"] == "fenster" and "meldet ein offenes Fenster" in e["begruendung"],
       f"geraeteeigene Erkennung schlaegt an ({e['begruendung']})")

e = fensterlage([GERAETEEIGEN], {GERAETEEIGEN: "off"})
pruefe(e["zustand"] == "fenster" and "Temperatursturz" in e["begruendung"],
       f"geraeteeigene Erkennung verdraengt den Sturz nicht ({e['begruendung']})")

e = fensterlage([GERAETEEIGEN], {GERAETEEIGEN: "unavailable"}, verlauf_sturz=False)
pruefe("melden nichts" not in e["begruendung"],
       f"stumme geraeteeigene Erkennung wird nicht angemahnt ({e['begruendung']!r})")

# Ein echter Kontakt daneben behaelt seine Wirkung.
e = fensterlage([GERAETEEIGEN, "binary_sensor.fenster_wz"],
                {GERAETEEIGEN: "off", "binary_sensor.fenster_wz": "off"})
pruefe(e["zustand"] != "fenster",
       f"echter Kontakt unterdrueckt den Sturz weiterhin ({e['zustand']})")

e = fensterlage(["binary_sensor.a", "binary_sensor.b"],
                {"binary_sensor.a": "off", "binary_sensor.b": "on"})
pruefe(e["zustand"] == "fenster", "ein offener unter mehreren genuegt")

e = fensterlage([], {})
pruefe(e["zustand"] == "fenster", "ohne Kontakte greift weiterhin der Sturz")

# Ein Wechsel des Raumfuehlers darf keinen Fensteralarm ausloesen: Zwei Fuehler
# in einem Raum zeigen selten dasselbe, und der Sprung saehe aus wie ein Sturz.
r_fuehler = store.validate_raum({**wohnzimmer, "raumtemp": "sensor.neu"})
idx_neu = {"climate.a": {"entity_id": "climate.a", "state": "heat",
                         "attributes": {"current_temperature": 20.9,
                                        "temperature": 23.0, "min_temp": 5,
                                        "max_temp": 30,
                                        "hvac_modes": ["off", "heat"]}},
           "sensor.neu": {"entity_id": "sensor.neu", "state": "20.9",
                          "attributes": {}}}
rz_alt = {"temperaturquelle": "thermostate",
          "verlauf": [[montag.replace(hour=13, minute=55).isoformat(
              timespec="seconds"), 24.5]]}
e = regelung.entscheide(r_fuehler, rz_alt,
                        umgebung(montag.replace(hour=14), states_index=idx_neu))
pruefe(e["zustand"] != "fenster",
       f"Fuehlerwechsel loest keinen Fensteralarm aus ({e['zustand']})")
pruefe(rz_alt["verlauf"] and len(rz_alt["verlauf"]) == 1,
       "das alte Gedaechtnis wurde verworfen")
pruefe(rz_alt["temperaturquelle"] == "sensor.neu", "die neue Quelle ist vermerkt")

print("\n=== Erkennung von Fensterkontakten ===")
import ha_api
# Die Namen stammen aus dem echten Bestand dieses Hauses.
faelle = [
    ("binary_sensor.fenster_kueche", "Küche Fenster", None, True),
    ("binary_sensor.wz_kontakt", "Wohnzimmer", "window", True),
    ("binary_sensor.heizung_luna_offenes_fenster_erkannt",
     "Heizung Gästetoilette Offenes Fenster erkannt", None, True),
    ("binary_sensor.haustur_tur", "Haustür Cloud Tür", "door", True),
    ("binary_sensor.terrassentuer_kontakt", "Terrassentür", "door", True),
    # Nebenmelder eines Thermostats, dessen Gerät „Eingangstür“ heißt
    ("binary_sensor.heizung_eingangstuer_sommermodus",
     "Heizung Eingangstür Sommermodus", None, False),
    ("binary_sensor.heizung_eingangstuer_tastensperre_am_gerat",
     "Heizung Eingangstür Tastensperre am Gerät", None, False),
    ("binary_sensor.haustur_cloud_calibration", "Haustür Cloud Calibration",
     None, False),
    # Öffnungszeiten von Tankstellen: device_class opening, aber kein Kontakt
    ("binary_sensor.aral_an_der_westumgehung_1_status",
     "ARAL An der Westumgehung  1 Status", "opening", False),
    ("binary_sensor.shell_rosenheimer_landstr_81_status",
     "Shell Rosenheimer Landstr. 81 Status", "opening", False),
    # Diagnosemelder eines Rolladens, die das Fenster nur im Namen führen
    ("binary_sensor.rollo_fenster_luna_obstacle_detection",
     "Rollo Fenster Luna Obstacle Detection", None, False),
    ("binary_sensor.rollo_balkontur_luna_blocking_detection",
     "Rollo Balkontür Luna Blocking Detection", None, False),
    ("binary_sensor.rollo_terrassentur_sun_program_active",
     "Rollo Terrassentür Sun Program Active", None, False),
    ("binary_sensor.bewegung_flur", "Bewegung Flur", "motion", False),
    ("binary_sensor.tv_aufnahme", "65PUS6412/12 Aufnahme läuft", None, False),
]
for eid, name, klasse, erwartet in faelle:
    treffer = ha_api.ist_fensterkontakt(eid, name, klasse)
    pruefe(treffer == erwartet,
           f"{name!r} -> {'Fenster' if erwartet else 'kein Fenster'}")

print("\n=== Praesenzsteuerung und Freigabe ===")

melder = {"binary_sensor.buero": {"entity_id": "binary_sensor.buero",
                                  "state": "off", "attributes": {}}}
buero = store.validate_raum({
    "name": "Buero", "thermostate": ["climate.b"], "personen": [],
    "praesenz": ["binary_sensor.buero"], "nur_praesenz": True, "karenz_min": 20,
    "komfort": 21.0, "eco": 18.0, "nacht": 17.0, "abwesend": 16.0,
    "min": 5.0, "max": 26.0, "zeitplan": plan,
})

# Melder aus, Familie zu Hause -> trotzdem leer
besetzt, grund = anwesenheit.raum_besetzt(buero, melder, personen)
pruefe(not besetzt, f"nur_praesenz: Familie daheim zaehlt nicht ({grund})")

melder_an = {"binary_sensor.buero": {"entity_id": "binary_sensor.buero",
                                     "state": "on", "attributes": {}}}
besetzt, grund = anwesenheit.raum_besetzt(buero, melder_an, personen)
pruefe(besetzt, f"Melder an -> besetzt ({grund})")

# Ohne hinterlegten Melder waere der Raum sonst fuer immer leer
ohne = store.validate_raum({**buero, "praesenz": []})
besetzt, grund = anwesenheit.raum_besetzt(ohne, {}, personen)
pruefe(besetzt, f"nur_praesenz ohne Melder friert den Raum nicht ein ({grund})")

# Ein falsch eingetragener oder ausgefallener Melder darf nicht dauerhaft
# absenken - genau der Fehler, der beim Einrichten des Bueros passiert ist
besetzt, grund = anwesenheit.raum_besetzt(buero, {}, personen)
pruefe(besetzt, f"fehlender Melder gilt nicht als leer ({grund})")
tot = {"binary_sensor.buero": {"entity_id": "binary_sensor.buero",
                               "state": "unavailable", "attributes": {}}}
besetzt, grund = anwesenheit.raum_besetzt(buero, tot, personen)
pruefe(besetzt, f"ausgefallener Melder gilt nicht als leer ({grund})")

# Zwei Melder, einer tot, einer meldet niemanden -> Raum ist leer
zwei = store.validate_raum({**buero,
                            "praesenz": ["binary_sensor.buero", "binary_sensor.tot"]})
gemischt = {"binary_sensor.buero": {"entity_id": "binary_sensor.buero",
                                    "state": "off", "attributes": {}},
            "binary_sensor.tot": {"entity_id": "binary_sensor.tot",
                                  "state": "unavailable", "attributes": {}}}
besetzt, grund = anwesenheit.raum_besetzt(zwei, gemischt, personen)
pruefe(not besetzt, f"ein antwortender Melder genuegt fuer die Aussage ({grund})")

# Raumeigene Karenzzeit: nach 25 Minuten leer wird abgesenkt (global waeren 45)
rz_b = {"leer_seit": montag.replace(hour=13, minute=35).isoformat(timespec="seconds")}
e = regelung.entscheide(buero, rz_b, umgebung(montag.replace(hour=14),
                                              states_index=melder))
pruefe(e["zustand"] == "abwesend",
       f"raumeigene Karenzzeit von 20 Minuten greift ({e['begruendung']})")

# Mit globaler Karenzzeit waere es noch zu frueh
buero_global = store.validate_raum({**buero, "karenz_min": None})
e = regelung.entscheide(buero_global, dict(rz_b),
                        umgebung(montag.replace(hour=14), states_index=melder))
pruefe(e["zustand"] != "abwesend",
       f"ohne eigene Karenzzeit gilt weiter die globale ({e['begruendung']})")

# Freigabeschalter
gast = store.validate_raum({
    "name": "Gaestezimmer", "thermostate": ["climate.g"], "personen": [],
    "freigabe_entity": "input_boolean.gaeste", "anwesenheit": False,
    "komfort": 21.0, "eco": 18.0, "nacht": 17.0, "abwesend": 16.0,
    "min": 5.0, "max": 26.0, "zeitplan": plan,
})
aus = {"input_boolean.gaeste": {"entity_id": "input_boolean.gaeste",
                                "state": "off",
                                "attributes": {"friendly_name": "Gaeste da"}}}
e = regelung.entscheide(gast, {}, umgebung(montag.replace(hour=14), states_index=aus))
pruefe(e["zustand"] == "gesperrt" and e.get("ventil_zu"),
       f"Freigabe aus -> Raum gesperrt ({e['begruendung']})")

an = {"input_boolean.gaeste": {"entity_id": "input_boolean.gaeste",
                               "state": "on",
                               "attributes": {"friendly_name": "Gaeste da"}}}
e = regelung.entscheide(gast, {}, umgebung(montag.replace(hour=14), states_index=an))
pruefe(e["zustand"] == "komfort" and e["ziel"] > 20,
       f"Freigabe an -> normaler Zeitplan ({e['ziel']}, {e['begruendung']})")

# Fehlender Schalter darf den Raum nicht kalt stellen
e = regelung.entscheide(gast, {}, umgebung(montag.replace(hour=14), states_index={}))
pruefe(e["zustand"] != "gesperrt",
       f"fehlender Freigabeschalter sperrt nicht ({e['zustand']})")

print("\n=== Betriebsart: nur absenken ===")

wc = store.validate_raum({
    "name": "Gästetoilette", "betriebsart": "nur_absenken",
    "thermostate": ["climate.wc"], "personen": [],
    "komfort": 21.0, "eco": 18.0, "nacht": 18.0, "abwesend": 16.0,
    "min": 5.0, "max": 26.0,
    "zeitplan": [{"start": "21:00", "modus": "nacht", "gilt": "immer",
                  "tage": [t[0] for t in [("mon",), ("tue",), ("wed",), ("thu",),
                                          ("fri",), ("sat",), ("sun",)]]}],
})

def wc_umgebung(jetzt, soll=21.0, **extra):
    idx = {"climate.wc": {"entity_id": "climate.wc", "state": "heat",
                          "attributes": {"current_temperature": 22.0,
                                         "temperature": soll, "min_temp": 5,
                                         "max_temp": 30,
                                         "hvac_modes": ["off", "heat"]}}}
    return umgebung(jetzt, states_index=idx, **extra)

# Erster Lauf: nur vermerken, nichts nachholen
rz_wc = {}
e = regelung.entscheide(wc, rz_wc, wc_umgebung(montag.replace(hour=22)))
pruefe(e["zustand"] == "manuell" and e.get("nicht_schreiben"),
       f"erster Lauf holt die Absenkung nicht nach ({e['begruendung']})")
pruefe(rz_wc.get("zuletzt_ausgeloest", "").endswith("21:00:00"),
       "der verpasste Zeitpunkt wird vermerkt")
pruefe(e["ziel"] == 21.0, f"angezeigt wird der von Hand gestellte Wert ({e['ziel']})")

# Nächster Tag, 21:05 -> Absenkung faellig
e = regelung.entscheide(wc, rz_wc, wc_umgebung(
    montag.replace(day=25, hour=21, minute=5)))
pruefe(e["zustand"] == "absenkung" and e["ziel"] == 18.0 and e.get("erzwingen"),
       f"Absenkung wird ausgeloest ({e['ziel']}, {e['begruendung']})")

# Mitten am Tag: keine Einmischung, auch wenn jemand hochgedreht hat
e = regelung.entscheide(wc, dict(rz_wc), wc_umgebung(
    montag.replace(day=25, hour=14), soll=24.0))
pruefe(e["zustand"] == "manuell" and e.get("nicht_schreiben") and e["ziel"] == 24.0,
       f"tagsueber keine Einmischung ({e['begruendung']})")

# Weit nach dem Zeitpunkt: nicht nachholen
rz_alt = {"zuletzt_ausgeloest": montag.replace(day=24, hour=21).isoformat(
    timespec="seconds")}
e = regelung.entscheide(wc, rz_alt, wc_umgebung(montag.replace(day=25, hour=23)))
pruefe(e["zustand"] == "manuell" and "verpasst" in e["begruendung"],
       f"laengst vergangener Zeitpunkt wird nicht nachgeholt ({e['begruendung']})")

# Im Zeitfenster nach dem Zeitpunkt wird weiter versucht
rz_fenster_zeit = {"zuletzt_ausgeloest": montag.replace(day=24, hour=21).isoformat(
    timespec="seconds")}
e = regelung.entscheide(wc, rz_fenster_zeit, wc_umgebung(
    montag.replace(day=25, hour=21, minute=25)))
pruefe(e["zustand"] == "absenkung",
       "innerhalb des Ausloesefensters wird weiter versucht")

# Sonderzustand: Urlaub greift durch, merkt sich aber den Handwert
e = regelung.entscheide(wc, dict(rz_wc), wc_umgebung(
    montag.replace(day=25, hour=14), urlaub=True))
pruefe(e["zustand"] == "urlaub" and e.get("merken") and e.get("erzwingen"),
       "Urlaub greift auch im Handbetrieb und merkt sich den Wert")

# Wiederherstellung nach dem Sonderzustand
zustand_wc = {"thermostate": {"climate.wc": {"vor_sonderzustand": 21.0}},
              "raeume": {}}
protokolliert_wc = []
umg_wc = wc_umgebung(montag.replace(day=25, hour=14), soll=12.0)
umg_wc["raum_wechsel"] = {wc["id"]: montag.replace(day=25, hour=21)}
einst["trockenlauf"] = True
aktionen = regelung.anwenden(
    wc, {"zustand": "manuell", "ziel": 21.0, "begruendung": "x",
         "nicht_schreiben": True, "wiederherstellen": True},
    zustand_wc, umg_wc, lambda *a, **k: protokolliert_wc.append(a))
pruefe(len(aktionen) == 1 and aktionen[0]["aktion"] == "zurück"
       and aktionen[0]["wert"] == 21.0,
       f"nach dem Sonderzustand wird die Handeinstellung zurueckgegeben ({aktionen})")
pruefe(zustand_wc["thermostate"]["climate.wc"]["vor_sonderzustand"] is None,
       "der gemerkte Wert wird danach verworfen")

# Ohne gemerkten Wert passiert im Ruhezustand gar nichts
zustand_leer = {"thermostate": {}, "raeume": {}}
aktionen = regelung.anwenden(
    wc, {"zustand": "manuell", "ziel": 21.0, "begruendung": "x",
         "nicht_schreiben": True, "wiederherstellen": True},
    zustand_leer, umg_wc, lambda *a, **k: None)
pruefe(not aktionen, "ohne gemerkten Wert bleibt der Raum unangetastet")

print("\n=== Flankenschreiben ===")
zustand = {"thermostate": {}, "raeume": {}}
protokolliert = []


def protokoll(raum, was, warum, entity_id=""):
    protokolliert.append((raum, was, warum))


umg = umgebung(montag.replace(hour=14), states_index=states_index)
umg["raum_wechsel"] = {wohnzimmer["id"]: montag.replace(hour=21)}
entscheidung = {"zustand": "komfort", "ziel": 23.0, "begruendung": "Test"}
aktionen = regelung.anwenden(wohnzimmer, entscheidung, zustand, umg, protokoll)
pruefe(not aktionen, "Sollwert steht schon richtig -> kein Schreibvorgang")

entscheidung = {"zustand": "komfort", "ziel": 21.0, "begruendung": "Test"}
aktionen = regelung.anwenden(wohnzimmer, entscheidung, zustand, umg, protokoll)
pruefe(len(aktionen) == 1 and aktionen[0]["trocken"],
       "abweichender Sollwert -> im Trockenlauf nur gemeldet")

print("\n=== Home Assistant startet gerade ===")
# Beobachtet nach einem HA-Neustart: `/states` liefert eine wachsende
# Teilliste. Wer darauf rechnet, meldet ein Dutzend Ausfaelle, die keine sind.
import ha_api as _ha
_echt_bereit, _echt_states = _ha.ist_bereit, _ha.get_states
_ha.ist_bereit = lambda: False
cfg_start = {"raeume": [wohnzimmer], "einstellungen": einst}
bericht = regelung.takt(cfg_start, {"thermostate": {}, "raeume": {}},
                        lambda *a, **k: None)
pruefe(bericht.get("startet") is True and not bericht["raeume"],
       f"waehrend des Starts wird ausgesetzt ({bericht.get('fehler')})")
pruefe(not bericht.get("stoerungen"),
       "und keine Stoerung gemeldet")
_ha.ist_bereit, _ha.get_states = _echt_bereit, _echt_states

print("\n=== Befehl bestaetigt, aber nicht umgesetzt ===")
# Beobachtet an einem SwitchBot-Thermostat: Es quittiert den Sollwert und
# steht danach unveraendert da. Wird das als Handeingriff gewertet, zieht sich
# der Planer zurueck - und der Raum bleibt auf einem Wert, den niemand wollte.
zust_nu = {"thermostate": {"climate.n": {
    "soll": 23.0,                 # das haben wir geschickt
    "vor_schreiben": 13.5,        # das stand vorher da
    "gesetzt_am": montag.replace(hour=12).isoformat(timespec="seconds")}},
    "raeume": {}}
protokoll_nu = []
raum_nu = store.validate_raum({
    "name": "Wohnzimmer", "thermostate": ["climate.n"], "personen": [],
    "komfort": 23.0, "eco": 19.0, "nacht": 19.0, "abwesend": 17.0,
    "min": 5.0, "max": 26.0, "zeitplan": plan})

def umg_nu(steht_auf):
    idx = {"climate.n": {"entity_id": "climate.n", "state": "heat",
                         "attributes": {"friendly_name": "Essbereich",
                                        "temperature": steht_auf,
                                        "current_temperature": 24.0,
                                        "min_temp": 5, "max_temp": 30,
                                        "hvac_modes": ["off","heat"]}}}
    u = umgebung(montag.replace(hour=14), states_index=idx)
    u["raum_wechsel"] = {raum_nu["id"]: montag.replace(hour=21)}
    return u

import ha_api
gesendet_nu = []
ha_api.set_temperature = lambda e, t: (gesendet_nu.append((e, t)), True)[1]
ha_api.set_hvac_mode = lambda e, m: True
einst["trockenlauf"] = False

# Das Geraet steht noch auf dem alten Wert -> kein Handeingriff, neuer Versuch
regelung.anwenden(raum_nu, {"zustand": "komfort", "ziel": 23.0, "begruendung": "x"},
                  zust_nu, umg_nu(13.5),
                  lambda r, w, g, e="": protokoll_nu.append((w, g)))
gedaechtnis = zust_nu["thermostate"]["climate.n"]
pruefe(gedaechtnis.get("manuell_bis") is None,
       "kein Handeingriff, wenn der Wert unveraendert blieb")
pruefe(gedaechtnis.get("schreib_fehler") == 1, "der Fehlschlag wird gezaehlt")
pruefe(any("nicht übernommen" in w for w, _ in protokoll_nu),
       f"und benannt ({protokoll_nu[0][1][:60] if protokoll_nu else '-'})")
pruefe(gesendet_nu == [("climate.n", 23.0)], "es wird erneut geschickt")

# Hat dagegen jemand von Hand auf einen dritten Wert gedreht, gilt weiter
# der Handeingriff
zust_h = {"thermostate": {"climate.n": {
    "soll": 23.0, "vor_schreiben": 13.5,
    "gesetzt_am": montag.replace(hour=12).isoformat(timespec="seconds")}},
    "raeume": {}}
gesendet_nu.clear()
regelung.anwenden(raum_nu, {"zustand": "komfort", "ziel": 23.0, "begruendung": "x"},
                  zust_h, umg_nu(19.5), lambda *a, **k: None)
pruefe(zust_h["thermostate"]["climate.n"].get("manuell_bis") is not None,
       "ein dritter Wert gilt weiterhin als Handeingriff")
pruefe(not gesendet_nu, "und wird nicht ueberschrieben")

# Kommt der Wert an, ist der Zaehler wieder bei null
zust_ok = {"thermostate": {"climate.n": {"soll": 23.0, "schreib_fehler": 2}},
           "raeume": {}}
regelung.anwenden(raum_nu, {"zustand": "komfort", "ziel": 23.0, "begruendung": "x"},
                  zust_ok, umg_nu(23.0), lambda *a, **k: None)
pruefe(zust_ok["thermostate"]["climate.n"]["schreib_fehler"] == 0,
       "ein angekommener Wert loescht den Fehlerzaehler")
einst["trockenlauf"] = True

print("\n=== Partytaste ===")
party_raum = store.validate_raum({
    "name": "Wohnzimmer", "thermostate": ["climate.a"], "personen": [],
    "komfort": 23.0, "eco": 19.0, "nacht": 19.0, "abwesend": 17.0,
    "min": 5.0, "max": 26.0, "zeitplan": plan})
bis = montag.replace(hour=23)

def party_umgebung(**extra):
    u = umgebung(montag.replace(hour=22), **extra)   # 22 Uhr: Plan sagt nacht
    return u

ohne = regelung.entscheide(party_raum, {"temperaturquelle": "thermostate"},
                           party_umgebung())
pruefe(ohne["ziel"] < 21,
       f"ohne Party gilt um 22 Uhr die Nachtabsenkung ({ohne['ziel']})")

e = regelung.entscheide(party_raum, {"temperaturquelle": "thermostate"},
                        party_umgebung(party_bis=bis))
pruefe(e["zustand"] == "party" and e["ziel"] == 23.0,
       f"Party hebt auf Komfort ({e['ziel']}, {e['begruendung']})")
pruefe("Minuten" in e["begruendung"] and "noch" in e["begruendung"],
       f"die Restzeit steht dabei ({e['begruendung']})")

# Urlaub und Sommerbetrieb treten zurueck - wer drueckt, ist da
e = regelung.entscheide(party_raum, {"temperaturquelle": "thermostate"},
                        party_umgebung(party_bis=bis, urlaub=True))
pruefe(e["zustand"] == "party", "Party schlaegt den Urlaub")
e = regelung.entscheide(party_raum, {"temperaturquelle": "thermostate"},
                        party_umgebung(party_bis=bis, sommerbetrieb=True))
pruefe(e["zustand"] == "party" and "Sommerbetrieb" in e["begruendung"],
       f"Party schlaegt den Sommer, weist aber darauf hin ({e['begruendung'][:60]})")

# Ein offenes Fenster bleibt staerker
idx_fenster = {"binary_sensor.f": {"entity_id": "binary_sensor.f", "state": "on",
                                   "attributes": {"friendly_name": "Fenster"}}}
r_fenster = store.validate_raum({**party_raum, "fenster": ["binary_sensor.f"]})
e = regelung.entscheide(r_fenster, {"temperaturquelle": "thermostate"},
                        party_umgebung(party_bis=bis, states_index=idx_fenster))
pruefe(e["zustand"] == "fenster",
       f"gegen ein offenes Fenster heizt auch die Party nicht ({e['zustand']})")

# Ein abgeschalteter Raum bleibt aus, und wer nicht mitfeiert, bleibt im Plan
r_aus = store.validate_raum({**party_raum, "aktiv": False})
e = regelung.entscheide(r_aus, {"temperaturquelle": "thermostate"},
                        party_umgebung(party_bis=bis))
pruefe(e["zustand"] == "aus", "ein abgeschalteter Raum feiert nicht mit")
r_ohne_party = store.validate_raum({**party_raum, "party": False})
e = regelung.entscheide(r_ohne_party, {"temperaturquelle": "thermostate"},
                        party_umgebung(party_bis=bis))
pruefe(e["zustand"] != "party" and e["ziel"] < 21,
       f"ein ausgenommener Raum bleibt beim Plan ({e['zustand']}, {e['ziel']})")

print("\n=== Raum mit blosser Mindesttemperatur ===")
# Muster fuer das Schlafzimmer: ein einziger Schaltpunkt haelt den Sollwert
# dauerhaft. Das Thermostat heizt dann nur, wenn der Raum darunter faellt.
schlaf = store.validate_raum({
    "name": "Schlafzimmer", "thermostate": ["climate.sz"], "personen": [],
    "komfort": 20.0, "eco": 18.0, "nacht": 18.0, "abwesend": 18.0,
    "min": 5.0, "max": 22.0, "heizkurve": False, "anwesenheit": False,
    "zeitplan": [{"start": "00:00", "modus": "eco", "gilt": "immer",
                  "tage": ["mon","tue","wed","thu","fri","sat","sun"]}],
})

def sz_umgebung(stunde, soll=18.0, ist=19.0):
    idx = {"climate.sz": {"entity_id": "climate.sz", "state": "heat",
                          "attributes": {"friendly_name": "Schlafzimmer",
                                         "temperature": soll,
                                         "current_temperature": ist,
                                         "min_temp": 5, "max_temp": 30,
                                         "hvac_modes": ["off","heat"]}}}
    u = umgebung(montag.replace(hour=stunde), states_index=idx)
    treffer = zp.naechster_wechsel(schlaf["zeitplan"], montag.replace(hour=stunde), None)
    u["raum_wechsel"] = {schlaf["id"]: treffer[0]}
    return u

for stunde in (3, 11, 20):
    e = regelung.entscheide(schlaf, {"temperaturquelle": "thermostate"},
                            sz_umgebung(stunde))
    pruefe(e["ziel"] == 18.0,
           f"{stunde:02d} Uhr: Sollwert bleibt 18 °C ({e['ziel']}, {e['begruendung'][:40]})")

# Auch bei Kaelte draussen keine Anhebung - die Heizkurve ist fuer den Raum aus
e = regelung.entscheide(schlaf, {"temperaturquelle": "thermostate"},
                        {**sz_umgebung(20), "aussen": -12.0})
pruefe(e["ziel"] == 18.0, f"auch bei -12 °C draussen bleibt es 18 °C ({e['ziel']})")

# Und wenn niemand zu Hause ist, wird nicht zusaetzlich abgesenkt
e = regelung.entscheide(schlaf, {"temperaturquelle": "thermostate",
                                 "leer_seit": montag.replace(hour=2).isoformat(
                                     timespec="seconds")},
                        {**sz_umgebung(20), "personen": leer_personen})
pruefe(e["ziel"] == 18.0, f"leeres Haus senkt nicht weiter ab ({e['ziel']})")

print("\n--- Handeingriff haelt bis zum naechsten Schaltpunkt ---")
zustand_sz = {"thermostate": {"climate.sz": {
    "soll": 18.0,
    "gesetzt_am": montag.replace(hour=10).isoformat(timespec="seconds")}},
    "raeume": {}}
protokoll_sz = []
def merke(raum, was, warum, entity_id=""):
    protokoll_sz.append((was, warum))

einst["trockenlauf"] = False
import ha_api
geschrieben = []
ha_api.set_temperature = lambda e, t: (geschrieben.append((e, t)), True)[1]
ha_api.set_hvac_mode = lambda e, m: True

# Jemand dreht von 18 auf 22 hoch
umg = sz_umgebung(20, soll=22.0)
regelung.anwenden(schlaf, {"zustand": "eco", "ziel": 18.0, "begruendung": "Zeitplan"},
                  zustand_sz, umg, merke)
pruefe(not geschrieben, f"der Planer stellt nicht zurueck ({geschrieben})")
pruefe(zustand_sz["thermostate"]["climate.sz"].get("manuell_bis") is not None,
       "die Handeinstellung ist vermerkt")
pruefe(any("Von Hand" in warum for _, warum in protokoll_sz),
       f"und steht im Protokoll ({protokoll_sz[0][1][:50] if protokoll_sz else '-'})")

# Solange der Vermerk gilt, bleibt es dabei
geschrieben.clear()
regelung.anwenden(schlaf, {"zustand": "eco", "ziel": 18.0, "begruendung": "Zeitplan"},
                  zustand_sz, sz_umgebung(22, soll=22.0), merke)
pruefe(not geschrieben, "auch zwei Stunden spaeter kein Eingriff")

# Nach Mitternacht - der Schaltpunkt ist vorbei - fuehrt wieder der Plan
zustand_sz["thermostate"]["climate.sz"]["manuell_bis"] = \
    montag.replace(hour=23, minute=59).isoformat(timespec="seconds")
geschrieben.clear()
umg_neu = sz_umgebung(20, soll=22.0)
umg_neu["jetzt"] = montag.replace(day=25, hour=0, minute=5)
regelung.anwenden(schlaf, {"zustand": "eco", "ziel": 18.0, "begruendung": "Zeitplan"},
                  zustand_sz, umg_neu, merke)
pruefe(geschrieben == [("climate.sz", 18.0)],
       f"nach dem Schaltpunkt stellt der Planer zurueck ({geschrieben})")
einst["trockenlauf"] = True

print("\n=== Thermostat, das sich nicht abschalten laesst ===")
# Beobachtet an einem SwitchBot-Thermostat: Es nimmt das \"aus\" an und steht
# eine Minute spaeter wieder auf \"heat\". Ohne Gegenmassnahme schickt der
# Planer bei jedem Takt ein neues \"aus\" - Dauerfeuer auf Kosten der Batterie.
zust = {"thermostate": {}, "raeume": {}}
protokoll_aus = []
def sammle(raum, was, warum, entity_id=""):
    protokoll_aus.append((was, warum))

raum_sommer = store.validate_raum({
    "name": "Testraum", "thermostate": ["climate.stur"], "personen": [],
    "zeitplan": plan})

def umgebung_stur(zustand, minuten_her=60):
    idx = {"climate.stur": {"entity_id": "climate.stur", "state": zustand,
                            "attributes": {"friendly_name": "Sturer",
                                           "hvac_modes": ["off", "heat"],
                                           "temperature": 20.0,
                                           "current_temperature": 21.0,
                                           "min_temp": 5, "max_temp": 30}}}
    u = umgebung(montag.replace(hour=14), states_index=idx)
    u["raum_wechsel"] = {raum_sommer["id"]: montag.replace(hour=21)}
    return u

einst["trockenlauf"] = False
sommer_entscheidung = {"zustand": "sommer", "ziel": 8.0, "ventil_zu": True,
                       "begruendung": "Sommerbetrieb"}

# Damit kein echter Aufruf hinausgeht, wird das Schalten hier abgefangen.
import ha_api
gesendet = []
ha_api.set_hvac_mode = lambda e, m: (gesendet.append((e, m)), True)[1]
ha_api.set_temperature = lambda e, t: (gesendet.append((e, t)), True)[1]

# 1. Versuch: Gerät steht auf heat -> wir schalten aus
regelung.anwenden(raum_sommer, sommer_entscheidung, zust, umgebung_stur("heat"), sammle)
pruefe(gesendet == [("climate.stur", "off")], f"erstes Ausschalten ({gesendet})")

# Gerät springt zurück auf heat, Schreibvorgang liegt zurueck -> zweiter Versuch
zust["thermostate"]["climate.stur"]["gesetzt_am"] = \
    montag.replace(hour=12).isoformat(timespec="seconds")
gesendet.clear()
regelung.anwenden(raum_sommer, sommer_entscheidung, zust, umgebung_stur("heat"), sammle)
pruefe(gesendet == [("climate.stur", "off")], "zweiter Versuch")

# Dritter Anlauf: der Planer gibt das Ausschalten auf und stellt den Sollwert
zust["thermostate"]["climate.stur"]["gesetzt_am"] = \
    montag.replace(hour=12).isoformat(timespec="seconds")
gesendet.clear()
regelung.anwenden(raum_sommer, sommer_entscheidung, zust, umgebung_stur("heat"), sammle)
pruefe(zust["thermostate"]["climate.stur"].get("aus_vergeblich") is True,
       "nach zwei Fehlversuchen wird aufgegeben")
pruefe(gesendet == [("climate.stur", 8.0)],
       f"stattdessen wird der Frostschutzwert gestellt ({gesendet})")
pruefe(any("nimmt das Ausschalten nicht an" in w for _, w in protokoll_aus),
       "der Verzicht steht im Protokoll")

# Kein weiteres Dauerfeuer: der Sollwert steht schon
gesendet.clear()
idx_kalt = umgebung_stur("heat")
idx_kalt["states_index"]["climate.stur"]["attributes"]["temperature"] = 8.0
regelung.anwenden(raum_sommer, sommer_entscheidung, zust, idx_kalt, sammle)
pruefe(gesendet == [], "danach wird nichts mehr geschickt")

# Ein Gerät, das sich abschalten laesst, wird weiter abgeschaltet
zust2 = {"thermostate": {}, "raeume": {}}
gesendet.clear()
regelung.anwenden(raum_sommer, sommer_entscheidung, zust2, umgebung_stur("heat"), sammle)
regelung.anwenden(raum_sommer, sommer_entscheidung, zust2, umgebung_stur("off"), sammle)
pruefe(zust2["thermostate"]["climate.stur"].get("aus_fehlversuche", 0) == 0,
       "ein folgsames Geraet sammelt keine Fehlversuche")

einst["trockenlauf"] = True

print("\n=== Wachhund ===")
import wachhund
from datetime import timezone

jetzt_w = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
# Der Planer arbeitet mit zeitzonenloser Ortszeit; die Prüfung muss auch damit
# stimmen, sonst verschiebt der Zeitzonenversatz jede Altersangabe.
jetzt_ortszeit = datetime(2026, 8, 25, 14, 0)   # dieselbe Sekunde in Berlin
cfg = {"raeume": [store.validate_raum({
    "name": "Wohnzimmer", "thermostate": ["climate.a", "climate.b"],
    "personen": [], "zeitplan": plan})]}
einst_w = store.validate_einstellungen({})

def lage(a_zustand="heat", a_gemeldet="2026-08-25T11:58:00+00:00",
         b_zustand="heat", b_gemeldet="2026-08-25T11:58:00+00:00",
         batterie=None, b_fehlt=False):
    idx = {"climate.a": {"entity_id": "climate.a", "state": a_zustand,
                         "last_reported": a_gemeldet,
                         "attributes": {"friendly_name": "Thermostat A"}}}
    if not b_fehlt:
        idx["climate.b"] = {"entity_id": "climate.b", "state": b_zustand,
                            "last_reported": b_gemeldet,
                            "attributes": {"friendly_name": "Thermostat B"}}
    if batterie is not None:
        idx["sensor.a_batterie"] = {"entity_id": "sensor.a_batterie",
                                    "state": str(batterie), "attributes": {}}
    batterien = {"climate.a": "sensor.a_batterie"} if batterie is not None else {}
    # Ein schweigendes Geraet wird erst angestupst und beim naechsten Mal
    # gemeldet. Die Hilfe macht deshalb beide Laeufe - sonst pruefte sie nur
    # den Weckruf.
    merker = {}
    wachhund.pruefen(cfg, idx, jetzt_w, einst_w, batterien, merker)
    spaeter = jetzt_w + wachhund.WECK_SCHONFRIST + timedelta(minutes=1)
    return wachhund.pruefen(cfg, idx, spaeter, einst_w, batterien, merker)

pruefe(lage() == [], "alles in Ordnung -> keine Stoerung")

st = lage(b_fehlt=True)
pruefe(len(st) == 1 and st[0]["art"] == "fehlt", f"verschwundenes Geraet ({st})")

st = lage(a_zustand="unavailable")
pruefe(len(st) == 1 and st[0]["art"] == "unerreichbar",
       f"nicht erreichbar erkannt ({st[0]['text'] if st else '-'})")

# Der eigentliche Urlaubsfall: Das Geraet meldet sich einfach nicht mehr
st = lage(a_gemeldet="2026-08-24T09:00:00+00:00")
pruefe(len(st) == 1 and st[0]["art"] == "stumm",
       f"stilles Verstummen erkannt ({st[0]['text'] if st else '-'})")
pruefe(st and "27 Stunden" in st[0]["text"],
       f"Dauer wird benannt ({st[0]['text'] if st else '-'})")

st = lage(batterie=15)
pruefe(len(st) == 1 and st[0]["art"] == "batterie",
       f"schwache Batterie gemeldet ({st[0]['text'] if st else '-'})")
pruefe(lage(batterie=80) == [], "volle Batterie meldet nichts")

# Im Sommerbetrieb schweigen die Geraete regulaer stundenlang - gemessen bis zu
# 13 Stunden. Die Schweigefrist gilt dort deshalb doppelt, sonst meldet der
# Wachhund reihenweise Ausfaelle, die keine sind.
def lage_stumm(stunden, sommerbetrieb):
    gemeldet = (jetzt_w - timedelta(hours=stunden)).isoformat()
    idx = {"climate.a": {"entity_id": "climate.a", "state": "off",
                         "last_reported": gemeldet,
                         "attributes": {"friendly_name": "Thermostat A"}},
           "climate.b": {"entity_id": "climate.b", "state": "off",
                         "last_reported": jetzt_w.isoformat(),
                         "attributes": {"friendly_name": "Thermostat B"}}}
    merker = {}
    wachhund.pruefen(cfg, idx, jetzt_w, einst_w, {}, merker,
                     sommerbetrieb=sommerbetrieb)
    return wachhund.pruefen(cfg, idx, jetzt_w + wachhund.WECK_SCHONFRIST
                            + timedelta(minutes=1), einst_w, {}, merker,
                            sommerbetrieb=sommerbetrieb)

pruefe(not lage_stumm(30, True),
       "im Sommer sind dreissig stille Stunden kein Ausfall")
pruefe(len(lage_stumm(30, False)) == 1,
       "im Heizbetrieb sind dreissig stille Stunden ein Ausfall")
pruefe(len(lage_stumm(50, True)) == 1,
       "auch im Sommer wird ein Geraet nach der doppelten Frist gemeldet")

# Die Sommerpause eines FRITZ!-Thermostats lehnt jeden Sollwert ab. Gemeldet
# wird sie erst, wenn der Planer wieder heizen will - im Sommer waere sie nur
# eine Nachricht ueber den Sommer.
def lage_sommerpause(sommerbetrieb):
    idx = {"climate.a": {"entity_id": "climate.a", "state": "off",
                         "last_reported": "2026-08-25T11:58:00+00:00",
                         "attributes": {"friendly_name": "Thermostat A",
                                        "preset_mode": "summer"}},
           "climate.b": {"entity_id": "climate.b", "state": "heat",
                         "last_reported": "2026-08-25T11:58:00+00:00",
                         "attributes": {"friendly_name": "Thermostat B"}}}
    merker = {}
    wachhund.pruefen(cfg, idx, jetzt_w, einst_w, {}, merker,
                     sommerbetrieb=sommerbetrieb)
    return wachhund.pruefen(cfg, idx, jetzt_w + wachhund.WECK_SCHONFRIST
                            + timedelta(minutes=1), einst_w, {}, merker,
                            sommerbetrieb=sommerbetrieb)

still = lage_sommerpause(True)
pruefe(not still, f"im Sommerbetrieb schweigt die Sommerpause ({still})")
laut = lage_sommerpause(False)
pruefe(len(laut) == 1 and laut[0]["art"] == "sommerpause"
       and "FRITZ" in laut[0]["text"],
       f"zur Heizperiode wird die Sommerpause gemeldet "
       f"({laut[0]['text'] if laut else '-'})")

# Der Weckruf: Ein Geraet, das lange schweigt, wird erst angestupst. Meldet es
# sich daraufhin, war es nur still - im Sommerbetrieb der Normalfall, weil der
# Planer dann gar nicht mehr schreibt.
_still = "2026-08-24T09:00:00+00:00"
_idx_still = {"climate.a": {"entity_id": "climate.a", "state": "off",
                            "last_reported": _still,
                            "attributes": {"friendly_name": "Thermostat A"}},
              "climate.b": {"entity_id": "climate.b", "state": "off",
                            "last_reported": jetzt_w.isoformat(),
                            "attributes": {"friendly_name": "Thermostat B"}}}
_merker = {}
_erst = wachhund.pruefen(cfg, _idx_still, jetzt_w, einst_w, {}, _merker)
pruefe(_erst == [] and "geweckt_am" in _merker.get("climate.a", {}),
       f"erster Verdacht stupst an, statt zu melden ({_erst})")

# Das Geraet antwortet - keine Meldung, der Merker ist weg.
_idx_antwort = json.loads(json.dumps(_idx_still))
_idx_antwort["climate.a"]["last_reported"] = (
    jetzt_w + timedelta(minutes=1)).isoformat()
_zweit = wachhund.pruefen(cfg, _idx_antwort,
                          jetzt_w + timedelta(minutes=13), einst_w, {}, _merker)
pruefe(_zweit == [] and "geweckt_am" not in _merker.get("climate.a", {}),
       f"wer antwortet, gilt nicht als ausgefallen ({_zweit})")

# Bleibt die Antwort aus, wird nach der Schonfrist gemeldet.
_merker2 = {}
wachhund.pruefen(cfg, _idx_still, jetzt_w, einst_w, {}, _merker2)
_dritt = wachhund.pruefen(cfg, _idx_still, jetzt_w + timedelta(minutes=13),
                          einst_w, {}, _merker2)
pruefe(len(_dritt) == 1 and _dritt[0]["art"] == "stumm",
       f"wer nicht antwortet, wird gemeldet ({_dritt})")

# Und nicht zu frueh: Innerhalb der Schonfrist bleibt es still.
_merker3 = {}
wachhund.pruefen(cfg, _idx_still, jetzt_w, einst_w, {}, _merker3)
_frueh = wachhund.pruefen(cfg, _idx_still, jetzt_w + timedelta(minutes=3),
                          einst_w, {}, _merker3)
pruefe(_frueh == [], f"waehrend der Schonfrist wird nicht gemeldet ({_frueh})")

# Ein veralteter Stand darf nicht warnen: Nach einem Batteriewechsel zeigen
# manche Geraete tagelang den alten Wert.
def lage_batterie(prozent, gemeldet):
    idx = {"climate.a": {"entity_id": "climate.a", "state": "heat",
                         "last_reported": "2026-08-25T11:58:00+00:00",
                         "attributes": {"friendly_name": "Thermostat A"}},
           "climate.b": {"entity_id": "climate.b", "state": "heat",
                         "last_reported": "2026-08-25T11:58:00+00:00",
                         "attributes": {"friendly_name": "Thermostat B"}},
           "sensor.a_batterie": {"entity_id": "sensor.a_batterie",
                                 "state": str(prozent),
                                 "last_reported": gemeldet, "attributes": {}}}
    return wachhund.pruefen(cfg, idx, jetzt_w, einst_w,
                            {"climate.a": "sensor.a_batterie"})

frisch = lage_batterie(10, "2026-08-25T10:00:00+00:00")
pruefe(len(frisch) == 1 and "Stand" in frisch[0]["text"],
       f"frischer Stand warnt und nennt die Uhrzeit ({frisch[0]['text'] if frisch else '-'})")
alt = lage_batterie(10, "2026-08-24T00:25:00+00:00")
pruefe(alt == [],
       f"ein 36 Stunden alter Stand warnt nicht mehr ({alt})")

# Ein ausgefallenes Geraet wird nicht zusaetzlich wegen Batterie gemeldet
st = lage(a_zustand="unavailable", batterie=5)
pruefe(len(st) == 1 and st[0]["art"] == "unerreichbar",
       "Ausfall verdeckt die Batteriemeldung")

# Abgeschaltete Ueberwachung schweigt
einst_aus = store.validate_einstellungen({"wachhund": {"aktiv": False}})
pruefe(wachhund.pruefen(cfg, {}, jetzt_w, einst_aus, {}) == [],
       "abgeschaltete Ueberwachung meldet nichts")

print("\n--- Geraet, das keine Sollwerte annimmt ---")
# Beobachtet an den FRITZ!-Thermostaten: Stehen sie in der Sommerpause,
# lehnen sie jeden Sollwert ab. Das ist kein Batterieproblem, sieht aber wie
# ein Ausfall aus - und muss deshalb gemeldet werden.
def lage_verweigert(fehler, preset=None):
    idx = {"climate.a": {"entity_id": "climate.a", "state": "off",
                         "last_reported": "2026-08-25T11:58:00+00:00",
                         "attributes": {"friendly_name": "Thermostat A",
                                        **({"preset_mode": preset} if preset else {})}},
           "climate.b": {"entity_id": "climate.b", "state": "heat",
                         "last_reported": "2026-08-25T11:58:00+00:00",
                         "attributes": {"friendly_name": "Thermostat B"}}}
    return wachhund.pruefen(cfg, idx, jetzt_w, einst_w, {},
                            {"climate.a": {"schreib_fehler": fehler}})

pruefe(lage_verweigert(2) == [], "zwei Fehlschlaege sind noch keine Stoerung")
st = lage_verweigert(3)
pruefe(len(st) == 1 and st[0]["art"] == "verweigert",
       f"ab dem dritten wird gemeldet ({st[0]['text'] if st else '-'})")
st = lage_verweigert(4, preset="summer")
pruefe(st and "Sommerpause" in st[0]["text"],
       f"die Sommerpause wird als Ursache benannt ({st[0]['text'] if st else '-'})")

print("\n--- Melden nur auf Flanke ---")
erste = lage(a_zustand="unavailable")
hinzu, weg = wachhund.vergleichen(erste, {})
pruefe(len(hinzu) == 1 and not weg, "erste Stoerung wird gemeldet")

gedaechtnis = wachhund.als_gedaechtnis(erste)
hinzu, weg = wachhund.vergleichen(erste, gedaechtnis)
pruefe(not hinzu and not weg, "dieselbe Stoerung wird nicht erneut gemeldet")

hinzu, weg = wachhund.vergleichen([], gedaechtnis)
pruefe(not hinzu and len(weg) == 1, "Behebung wird gemeldet")

# Aus schwacher Batterie wird ein Ausfall: neue Nachricht
vorher = wachhund.als_gedaechtnis(lage(batterie=15))
hinzu, weg = wachhund.vergleichen(lage(a_zustand="unavailable"), vorher)
pruefe(len(hinzu) == 1 and len(weg) == 1,
       "Wechsel der Stoerungsart wird gemeldet")

# Dieselbe Lage in Ortszeit gerechnet muss dieselbe Dauer ergeben
def lage_ortszeit(gemeldet):
    idx = {"climate.a": {"entity_id": "climate.a", "state": "heat",
                         "last_reported": gemeldet,
                         "attributes": {"friendly_name": "Thermostat A"}},
           "climate.b": {"entity_id": "climate.b", "state": "heat",
                         "last_reported": "2026-08-25T11:58:00+00:00",
                         "attributes": {"friendly_name": "Thermostat B"}}}
    merker = {}
    wachhund.pruefen(cfg, idx, jetzt_ortszeit, einst_w, {}, merker)
    return wachhund.pruefen(cfg, idx, jetzt_ortszeit + wachhund.WECK_SCHONFRIST
                            + timedelta(minutes=1), einst_w, {}, merker)

st_utc = lage(a_gemeldet="2026-08-24T09:00:00+00:00")
st_lokal = lage_ortszeit("2026-08-24T09:00:00+00:00")
pruefe(st_utc and st_lokal and st_utc[0]["text"] == st_lokal[0]["text"],
       f"Ortszeit ergibt dieselbe Dauer wie UTC ({st_lokal[0]['text'] if st_lokal else '-'})")
pruefe(lage_ortszeit("2026-08-25T10:00:00+00:00") == [],
       "vor zwei Stunden gemeldet -> keine Stoerung (kein Zeitzonenversatz)")

titel, text = wachhund.meldung_bauen(lage(a_zustand="unavailable"), [])
pruefe("ausgefallen" in titel and "Thermostat A" in text,
       f"Meldung nennt Ross und Reiter ({titel})")

print("\n=== Batteriezuordnung ===")

# Verschwindet eine gemerkte Batterieanzeige - etwa weil die Entitaet
# umbenannt wurde -, muss die Zuordnung sofort neu geholt werden. Sonst haelt
# der Planer bis zu einer Stunde an einer toten ID fest und meldet eine
# schwache Batterie faelschlich als behoben.
regelung._BATTERIEN["stand"] = {"climate.a": "sensor.alt_batterie"}
regelung._BATTERIEN["geholt"] = montag
gerufen = []
echt = regelung.wachhund.batterien_je_thermostat
regelung.wachhund.batterien_je_thermostat = lambda: (
    gerufen.append(1) or {"climate.a": "sensor.neu_batterie"})

regelung._batterien_holen(montag, {}, {"sensor.alt_batterie": {"state": "50"}})
pruefe(not gerufen, "solange die Anzeige da ist, bleibt die Zuordnung stehen")

regelung._batterien_holen(montag, {}, {"sensor.neu_batterie": {"state": "10"}})
pruefe(gerufen and regelung._BATTERIEN["stand"]["climate.a"] == "sensor.neu_batterie",
       "verschwundene Anzeige loest ein Neuholen aus")
regelung.wachhund.batterien_je_thermostat = echt
regelung._BATTERIEN["stand"] = None


print("\n=== Sprachdateien der Oberflaeche ===")

# Eine Sprachdatei meldet sich unter ihrem Dateinamen an. Vertippt man sich
# dort, laedt die Oberflaeche die Datei und findet trotzdem nichts - ein
# Fehler, der sich nur im Browser zeigt und dort wie ein fehlender Text
# aussieht.
import os as _os
_ordner = _os.path.join(_os.path.dirname(__file__), "..", "frontend", "sprachen")
_dateien = sorted(f for f in _os.listdir(_ordner) if f.endswith(".js"))
pruefe(bool(_dateien), f"Sprachdateien gefunden ({', '.join(_dateien) or 'keine'})")
for _datei in _dateien:
    _code = _datei[:-3]
    _inhalt = open(_os.path.join(_ordner, _datei), encoding="utf-8").read()
    pruefe(f"window.SPRACHEN.{_code} =" in _inhalt,
           f"{_datei} meldet sich als '{_code}' an")
    for _teil in ("locale:", "woerter:", "muster:", "vorlagen:"):
        pruefe(_teil in _inhalt, f"{_datei} hat {_teil.rstrip(':')}")

# Was die Oberflaeche kann, muss das Backend auch koennen - sonst spricht die
# Kachel Englisch und ihre Begruendung Deutsch.
_ohne_backend = [f[:-3] for f in _dateien if f[:-3] not in texte.sprachen()]
pruefe(not _ohne_backend,
       f"jede Oberflaechensprache steht auch in texte.py ({_ohne_backend or 'alle'})")

print("\n=== Temperatureinheit ===")

# Absolute Temperaturen und Spannen duerfen nicht verwechselt werden: Wer eine
# Spanne wie eine Temperatur umrechnet, addiert 32 auf einen Abstand.
pruefe(einheit.absolut(21, "°F") == 69.8, "21 °C sind 69.8 °F")
pruefe(einheit.differenz(1.5, "°F") == 2.7, "eine Spanne von 1.5 K sind 2.7 °F")
pruefe(einheit.nach_celsius(69.8, "°F") == 21.0, "und wieder zurueck")
pruefe(einheit.umrechnen(21, "°C", "°F") == 69.8
       and einheit.umrechnen(1.5, "°C", "°F", spanne=True) == 2.7,
       "Umrechnen kennt den Unterschied")

einheit.einheit_setzen("°F")
pruefe(einheit.schritt() == 1.0, "in Fahrenheit wird in ganzen Graden gestellt")
_vorgabe = store.standard_einstellungen()
_raum_f = store.standard_raum()
pruefe(_raum_f["komfort"] == 70 and _vorgabe["frostschutz"] == 46,
       f"Vorgaben in Fahrenheit gerundet ({_raum_f['komfort']}, {_vorgabe['frostschutz']})")
pruefe(_vorgabe["sommer"]["hysterese"] == 2.5,
       f"die Hysterese als Spanne ({_vorgabe['sommer']['hysterese']})")
pruefe(_vorgabe["heizkurve"]["steilheit"] == 0.06,
       "die Steilheit bleibt gleich - sie ist ein Verhaeltnis")

# Ein Raum mit 70 °F muss zulaessig sein; in Celsius-Grenzen waere er es nicht.
_r = store.validate_raum({"name": "Test", "komfort": 70, "eco": 66,
                          "nacht": 64, "abwesend": 62, "min": 41, "max": 79})
pruefe(_r["komfort"] == 70, "Fahrenheit-Werte bestehen die Pruefung")

# Der Wechsel des Massystems zieht die gespeicherten Werte mit. Ohne das
# stuende nach einem Umschalten 21 in der Datei - und das Haus kuehlte auf
# 21 °F herunter.
einheit.einheit_setzen("°C")
_config = {"einheit": "°C",
           "einstellungen": {**store.STANDARD_EINSTELLUNGEN,
                             "frostschutz": 8.0,
                             "sommer": {"aktiv": True, "grenze": 16.0, "hysterese": 1.5}},
           "raeume": [{"name": "Wohnzimmer", "komfort": 21.0, "eco": 19.0,
                       "nacht": 18.0, "abwesend": 17.0, "min": 5.0, "max": 26.0}]}
einheit.einheit_setzen("°F")
_gespeichert = []
_echt = store.save_config
store.save_config = lambda c: _gespeichert.append(c) or c
_neu = store.einheit_angleichen(json.loads(json.dumps(_config)))
store.save_config = _echt
pruefe(_neu["raeume"][0]["komfort"] == 69.8,
       f"beim Wechsel wird der Sollwert umgerechnet ({_neu['raeume'][0]['komfort']})")
pruefe(_neu["einstellungen"]["sommer"]["hysterese"] == 2.7,
       f"die Hysterese als Spanne ({_neu['einstellungen']['sommer']['hysterese']})")
pruefe(_neu["einheit"] == "°F" and _gespeichert,
       "die neue Einheit wird vermerkt und gespeichert")
_nochmal = store.einheit_angleichen(_neu)
pruefe(_nochmal["raeume"][0]["komfort"] == 69.8,
       "ein zweiter Lauf rechnet nicht noch einmal um")
einheit.einheit_setzen("°C")

print("\n=== Zweisprachigkeit ===")

# Jeder Text muss in beiden Sprachen stehen und dieselben Platzhalter tragen.
# Ein vergessener Platzhalter faellt sonst erst im Betrieb auf - als Satz mit
# einer Luecke mitten in einer Begruendung.
import re as _re
_luecken = []
for _schluessel, _eintrag in texte.TEXTE.items():
    _fehlend = {"de", "en"} - set(_eintrag)
    if _fehlend:
        _luecken.append(f"{_schluessel}: fehlt {sorted(_fehlend)}")
        continue
    _platz = {_sp: set(_re.findall(r"\{(\w+)\}", _eintrag[_sp])) for _sp in ("de", "en")}
    if _platz["de"] != _platz["en"]:
        _luecken.append(f"{_schluessel}: {_platz['de']} vs {_platz['en']}")
for _name, _tabelle in (("MODUS", texte.MODUS), ("ZUSTAND", texte.ZUSTAND)):
    for _k, _v in _tabelle.items():
        if {"de", "en"} - set(_v):
            _luecken.append(f"{_name}.{_k}")
pruefe(not _luecken,
       f"alle {len(texte.TEXTE)} Texte zweisprachig mit gleichen Platzhaltern "
       f"({'; '.join(_luecken[:3]) if _luecken else 'ok'})")

# Die Sprache wirkt sich auf die Begruendung aus - und nur auf sie.
texte.sprache_setzen("en")
_en = texte.t("zeitplan", modus=texte.modus("komfort"), uhrzeit="07:30")
texte.sprache_setzen("de")
_de = texte.t("zeitplan", modus=texte.modus("komfort"), uhrzeit="07:30")
pruefe(_en == "Schedule: comfort from 07:30" and _de == "Zeitplan: Komfort ab 07:30 Uhr",
       f"dieselbe Lage in beiden Sprachen ({_en!r} / {_de!r})")

# Unbekannte Sprachen bekommen Englisch, nicht einen leeren Text.
pruefe(texte.sprache_setzen("fr-CA") == "en", "unbekannte Sprache faellt auf Englisch")
pruefe(texte.sprache_setzen("de-AT") == "de", "de-AT bleibt Deutsch")
texte.sprache_setzen("de")

print("\n=== Huellkurve ===")
import huellkurve as hk

# Ein Raum mit zwei Komfortbloecken und einer Mittagsluecke.
buero = {"name": "Buero", "aktiv": True, "zeitplan": [
    {"start": "06:00", "modus": "komfort", "gilt": "immer", "tage": zp.TAGE},
    {"start": "08:00", "modus": "eco", "gilt": "immer", "tage": zp.TAGE},
    {"start": "17:00", "modus": "komfort", "gilt": "immer", "tage": zp.TAGE},
    {"start": "22:00", "modus": "nacht", "gilt": "immer", "tage": zp.TAGE}]}
bad = {"name": "Bad", "aktiv": True, "zeitplan": [
    {"start": "05:30", "modus": "komfort", "gilt": "immer", "tage": zp.TAGE},
    {"start": "07:00", "modus": "eco", "gilt": "immer", "tage": zp.TAGE}]}

pruefe(hk.raum_fenster(buero, "mon", None, None) == [(360, 480), (1020, 1320)],
       "Schaltpunkte werden zu Komfortfenstern")
pruefe(hk.als_text(hk.fuer_tag([buero, bad], "mon", None, None))
       == "05:30-08:00 17:00-22:00 ##:##-##:##",
       "die Huellkurve vereinigt ueber die Raeume (Bad zieht den Morgen vor)")

# Die Mittagsluecke bleibt, die kleine Luecke wird geschlossen.
viele = [(360, 480), (500, 540), (1020, 1320), (1350, 1400)]
pruefe(hk.eindampfen(viele, 3) == [(360, 540), (1020, 1320), (1350, 1400)],
       "eingedampft wird an der kleinsten Luecke, nicht an der ersten")
pruefe(hk.eindampfen(viele, 2) == [(360, 540), (1020, 1400)],
       "und weiter, bis die Phasen passen")
pruefe(all(e - b > 0 for b, e in hk.eindampfen(viele, 1)),
       "auch eine einzige Phase bleibt wohlgeformt")

pruefe(hk.als_text([]) == "##:##-##:## ##:##-##:## ##:##-##:##",
       "kein Komfortbedarf ergibt einen leeren Tag")
pruefe(hk.aus_text("06:00-22:00 ##:##-##:## ##:##-##:##") == [(360, 1320)],
       "Zurueckgelesen wird nur, was belegt ist")
pruefe(hk.aus_text(hk.als_text([(360, 480), (1020, 1320)]))
       == [(360, 480), (1020, 1320)],
       "hin und zurueck ergibt dasselbe")

# Ein Raum in "nur absenken" spannt die Huellkurve nicht auf – sonst waere
# sie 24 Stunden breit und die ganze Uebung sinnlos.
hand = {"name": "Hand", "aktiv": True, "betriebsart": "nur_absenken",
        "zeitplan": [{"start": "00:00", "modus": "komfort", "gilt": "immer",
                      "tage": zp.TAGE}]}
pruefe(hk.fuer_tag([hand], "mon", None, None) == [],
       "ein handgefuehrter Raum spannt die Huellkurve nicht auf")
aus = dict(buero, aktiv=False)
pruefe(hk.fuer_tag([aus], "mon", None, None) == [],
       "ein abgeschalteter Raum auch nicht")

# Unbekannte Tagesart: beide Faelle, nicht geraten.
schule = {"name": "Kind", "aktiv": True, "zeitplan": [
    {"start": "06:00", "modus": "komfort", "gilt": "schultag", "tage": zp.TAGE},
    {"start": "07:30", "modus": "eco", "gilt": "schultag", "tage": zp.TAGE},
    {"start": "09:00", "modus": "komfort", "gilt": "schulfrei", "tage": zp.TAGE},
    {"start": "11:00", "modus": "eco", "gilt": "schulfrei", "tage": zp.TAGE}]}
pruefe(hk.als_text(hk.fuer_tag([schule], "mon", False, None)).startswith("06:00-07:30"),
       "am Schultag gilt der Schultag-Zweig")
pruefe(hk.als_text(hk.fuer_tag([schule], "mon", True, None)).startswith("09:00-11:00"),
       "am schulfreien Tag der andere")
beide = hk.fuer_tag([schule], "mon", None, None)
pruefe(beide == [(360, 450), (540, 660)],
       "ist die Tagesart unbekannt, gelten beide – nicht geraten wird nicht")

# Die Erweiterung fuer das, was kein Zeitplan vorhersieht.
mittag = datetime(2026, 9, 11, 12, 0)
pruefe(hk.erweitern("06:00-08:00 ##:##-##:## ##:##-##:##", 14 * 60, mittag)
       == "06:00-08:00 12:00-14:00 ##:##-##:##",
       "die Partytaste bekommt ein eigenes Fenster")
pruefe(hk.erweitern("06:00-22:00 ##:##-##:## ##:##-##:##", 14 * 60, mittag) is None,
       "laeuft schon Komfort, wird nicht geschrieben")
pruefe(hk.erweitern("06:00-13:00 ##:##-##:## ##:##-##:##", 14 * 60, mittag)
       == "06:00-14:00 ##:##-##:## ##:##-##:##",
       "ein laufendes Fenster wird verlaengert statt gestueckelt")
pruefe(hk.erweitern("06:00-08:00 ##:##-##:## ##:##-##:##", 11 * 60, mittag) is None,
       "was in der Vergangenheit endet, wird nicht geschrieben")

print("\n=== Kesselregelung ===")
import kessel

WOCHENTAGE = ["11", "11.1", "11.2", "11.3", "11.4", "11.5", "11.6"]
SVENS_PLAN = {nr: ("06:00-22:00 ##:##-##:## ##:##-##:##" if i < 5
                   else "08:00-22:00 ##:##-##:## ##:##-##:##")
              for i, nr in enumerate(WOCHENTAGE)}


class Anlage:
    """Ein Anlagenmanager auf dem Papier – merkt sich, was ihm gesagt wird."""

    def __init__(self, uebernommen=False, antwort=None, stur=False):
        self.werte = dict(SVENS_PLAN)
        self.werte["70"] = "3"            # Programm 1
        self.uebernommen = uebernommen
        self.antwort = antwort
        self.stur = stur                  # nimmt an, behaelt aber das Seine
        self.gesetzt = []
        self.anmeldungen = 0
        self.abmeldungen = 0

    def __call__(self, methode, adresse, nutzlast=None, zeit=20.0):
        if adresse.endswith("/api/katalog"):
            return {"programmwahl": {"nr": "70", "werte": [], "zu": {"1": "3"}},
                    "zeitprogramme": {"1": {"name": "Zeitschaltprogramm 1",
                                            "tage": WOCHENTAGE}}}
        if adresse.endswith("/api/werte"):
            return {"werte": {nr: {"value": v, "error": 0}
                              for nr, v in self.werte.items()}}
        if adresse.endswith("/api/uebernahme") and methode == "GET":
            eintrag = {"quelle": "heizungsplaner", "name": "Heizungsplaner"}
            return {"quellen": {}, "parameter":
                    {nr: eintrag for nr in WOCHENTAGE} if self.uebernommen else {}}
        if adresse.endswith("/api/uebernahme"):
            self.anmeldungen += 1
            self.uebernommen = True
            return {}
        if "/api/uebernahme/" in adresse:
            self.abmeldungen += 1
            self.uebernommen = False
            return {}
        if adresse.endswith("/api/setzen"):
            if self.antwort:
                raise self.antwort
            self.gesetzt.append((nutzlast["nr"], nutzlast["wert"]))
            if not self.stur:
                self.werte[nutzlast["nr"]] = nutzlast["wert"]
            return {"gesetzt": True}
        raise AssertionError(adresse)


def _lauf(anlage, bericht, config, state):
    alt, kessel._json = kessel._json, anlage
    try:
        return kessel.fuehren(bericht, config, state, lambda *a, **k: None)
    finally:
        kessel._json = alt


def CONFIG(raeume=None, **extra):
    # Bewusst eine Funktion: dict(...) waere eine flache Kopie, und der
    # verschachtelte Kessel-Block bliebe zwischen den Pruefungen derselbe.
    return {"einstellungen": {"kessel": {"aktiv": True,
                                         "adresse": "http://anlage:8099"},
                              **extra},
            "raeume": raeume if raeume is not None else [buero, bad]}


FREITAG = datetime(2026, 9, 11, 12, 0)


def BERICHT(zustand="eco", wechsel=None):
    return {"zeit": FREITAG.isoformat(), "sommerbetrieb": False,
            "schulfrei": False, "arbeitstag": True,
            "raeume": [{"name": "Buero", "zustand": zustand,
                        "naechster_wechsel": wechsel}]}


anlage, zustand = Anlage(), {}
lage = _lauf(anlage, BERICHT(), CONFIG(), zustand)
pruefe(anlage.anmeldungen == 1, "beim ersten Lauf werden alle 7 Tage uebernommen")
pruefe(zustand["kessel"]["original"] == SVENS_PLAN,
       "und Svens vorgefundener Plan wird zuerst gesichert")
pruefe(all(w == "05:30-08:00 17:00-22:00 ##:##-##:##"
           for _, w in anlage.gesetzt), "geschrieben wird die Huellkurve")
pruefe(len(anlage.gesetzt) == 7, "einmal je Wochentag")

vorher = len(anlage.gesetzt)
_lauf(anlage, BERICHT(), CONFIG(), zustand)
pruefe(len(anlage.gesetzt) == vorher,
       "beim zweiten Lauf geht kein einziges Telegramm mehr raus")

# Trockenlauf: rechnen ja, stellen nein.
trocken, ztr = Anlage(uebernommen=True), {}
lage = _lauf(trocken, BERICHT(), CONFIG(trockenlauf=True), ztr)
pruefe(trocken.gesetzt == [] and lage.get("trocken"),
       "im Trockenlauf wird nichts gestellt")

# Aussserplanmaessiger Bedarf – die Partytaste um 12 Uhr bis 15 Uhr.
party, zp2 = Anlage(uebernommen=True), {}
_lauf(party, BERICHT(), CONFIG(), zp2)          # erst den Grundplan setzen
party.gesetzt.clear()
lage = _lauf(party, BERICHT("party", "2026-09-11T15:00:00"), CONFIG(), zp2)
pruefe(lage.get("erweitert"), "die Partytaste erweitert den heutigen Tag")
pruefe(any(nr == "11.4" and "12:00-15:00" in w for nr, w in party.gesetzt),
       f"und zwar nur den Freitag ({party.gesetzt})")

# Ein handgefuehrter Raum darf die Huellkurve nicht ueber die Erweiterung
# wieder aufspannen – sonst schliesst fuer_tag ihn aus und bedarf_bis holt ihn
# zurueck. Genau das ist am 11.09.2026 live passiert: Hobbyraum, Flur und
# Gaestetoilette stehen dauerhaft auf "manuell" und haetten die Regelung rund
# um die Uhr auf Komfort gehalten.
pruefe("manuell" not in kessel.KOMFORT_ZUSTAENDE,
       "ein handgefuehrter Raum spannt auch die Erweiterung nicht auf")
pruefe(kessel.bedarf_bis(BERICHT("manuell", "2026-09-12T21:00:00")) is None,
       "und loest kein naechtliches Dauerfenster aus")
pruefe(kessel.bedarf_bis(BERICHT("party", "2026-09-11T15:00:00")) == 15 * 60,
       "die Partytaste dagegen schon")
pruefe(kessel.bedarf_bis(BERICHT("komfort", "2026-09-12T07:00:00")) == 24 * 60,
       "was ueber den Tag hinausreicht, gilt bis Mitternacht")

# Die Schreibbremse.
bremse, zb = Anlage(uebernommen=True), {}
_lauf(bremse, BERICHT(), CONFIG(), zb)
zaehler = zb["kessel"]["schreibzaehler"]
zaehler["11.4"] = kessel.SCHREIBGRENZE
bremse.gesetzt.clear()
bremse.werte["11.4"] = "00:00-01:00 ##:##-##:## ##:##-##:##"   # jemand verstellt
lage = _lauf(bremse, BERICHT(), CONFIG(), zb)
pruefe(bremse.gesetzt == [], "ueber der Tagesgrenze wird nicht mehr geschrieben")
pruefe("fri" in (lage.get("gebremst") or []) and lage.get("hinweis"),
       "und die Lage sagt, welcher Tag gebremst wurde")

# Wenn die Regelung die Schaltzeiten nicht behaelt.
stur, zs, cfg = Anlage(stur=True), {}, CONFIG()
for _ in range(kessel.VERWORFEN_GRENZE + 1):
    lage = _lauf(stur, BERICHT(), cfg, zs)
pruefe(cfg["einstellungen"]["kessel"]["aktiv"] is False,
       "behaelt die Regelung die Zeiten nicht, gibt der Planer auf")
pruefe(stur.abmeldungen == 1, "die Uebernahme wird zurueckgegeben")
pruefe(any(w == SVENS_PLAN[nr] for nr, w in stur.gesetzt),
       "und Svens Plan wieder hineingeschrieben")

# Abschalten von Hand: genauso.
aus, za = Anlage(), {}
_lauf(aus, BERICHT(), CONFIG(), za)
aus.gesetzt.clear()
_lauf(aus, BERICHT(), CONFIG(**{}) | {"einstellungen": {"kessel": {"aktiv": False,
      "adresse": "http://anlage:8099"}}}, za)
pruefe(aus.abmeldungen == 1, "beim Abschalten wird die Uebernahme zurueckgegeben")
pruefe(sorted(nr for nr, _ in aus.gesetzt) == sorted(WOCHENTAGE),
       "und alle sieben Tage auf den vorgefundenen Stand gebracht")

# Der Mensch hebt die Uebernahme im Anlagenmanager auf.
mensch, zm, cfg2 = Anlage(), {}, CONFIG()
_lauf(mensch, BERICHT(), cfg2, zm)
mensch.uebernommen = False
mensch.gesetzt.clear()
lage = _lauf(mensch, BERICHT(), cfg2, zm)
pruefe(mensch.anmeldungen == 1, "nach dem Aufheben wird nicht neu angemeldet")
pruefe(cfg2["einstellungen"]["kessel"]["aktiv"] is False,
       "der Planer schaltet die Fuehrung selbst ab")
pruefe(sorted(nr for nr, _ in mensch.gesetzt) == sorted(WOCHENTAGE),
       "und gibt Svens Plan zurueck")

# Uebernahme steht, aber das Gedaechtnis ist weg – nach einer Neuinstallation.
# Gefuehrt wird weiter, aber der fehlende Weg zurueck muss gesagt werden.
ohne, zo = Anlage(uebernommen=True), {}
lage = _lauf(ohne, BERICHT(), CONFIG(), zo)
pruefe("nicht mehr bekannt" in (lage.get("hinweis") or ""),
       "ohne gesicherten Plan wird auf den fehlenden Weg zurueck hingewiesen")
ohne.gesetzt.clear()
lage = _lauf(ohne, BERICHT(), {"einstellungen": {"kessel": {"aktiv": False,
             "adresse": "http://anlage:8099"}}, "raeume": []}, zo)
pruefe(ohne.gesetzt == [] and lage.get("hinweis"),
       "und beim Abschalten wird nichts erfunden, sondern gemeldet")

# Fuehrt ein anderes Add-on den Plan, wird nicht darum gerangelt.
class Fremd(Anlage):
    def __call__(self, methode, adresse, nutzlast=None, zeit=20.0):
        if adresse.endswith("/api/uebernahme") and methode == "GET":
            return {"quellen": {}, "parameter":
                    {"11": {"quelle": "anderes", "name": "Ein anderes Add-on"}}}
        return Anlage.__call__(self, methode, adresse, nutzlast, zeit)

fremd = Fremd()
lage = _lauf(fremd, BERICHT(), CONFIG(), {})
pruefe(fremd.gesetzt == [] and fremd.anmeldungen == 0,
       "ein fremd gefuehrter Plan wird in Ruhe gelassen")
pruefe("Ein anderes Add-on" in (lage.get("hinweis") or ""),
       "und die Lage nennt den, der ihn haelt")

# 403 heisst "im Anlagenmanager noch gesperrt".
gesperrt = Anlage(uebernommen=True,
                  antwort=kessel.Abgelehnt(403, "noch nicht freigegeben"))
lage = _lauf(gesperrt, BERICHT(), CONFIG(), {})
pruefe("Heizungsanlagenmanager" in (lage.get("fehler") or ""),
       "eine Sperre verweist auf den Anlagenmanager")

# Die Anschrift kommt vom Anlagenmanager selbst, per MQTT.
kessel._gefunden = ""
kessel.anschrift_merken("http://95552f8b-heizungsanlage:8099/")
pruefe(kessel.basis({"kessel": {"aktiv": True}}) == "http://95552f8b-heizungsanlage:8099",
       "die angesagte Anschrift wird uebernommen")
kessel.anschrift_merken("javascript:boese()")
pruefe(kessel.basis({"kessel": {"aktiv": True}}) == "http://95552f8b-heizungsanlage:8099",
       "was nicht nach http aussieht, wird nicht uebernommen")
pruefe(kessel.basis({"kessel": {"aktiv": True, "adresse": "http://eigen:1"}})
       == "http://eigen:1", "eine eingetragene Adresse geht der Ansage vor")
kessel._gefunden = ""

print("\n=== Validierung ===")
try:
    store.validate_raum({"name": "", "thermostate": []})
    pruefe(False, "leerer Name wird abgelehnt")
except store.ValidationError:
    pruefe(True, "leerer Name wird abgelehnt")
try:
    store.validate_raum({"name": "X", "min": 20, "max": 18})
    pruefe(False, "Maximum unter Minimum wird abgelehnt")
except store.ValidationError:
    pruefe(True, "Maximum unter Minimum wird abgelehnt")
try:
    store.validate_zeitplan([{"start": "25:00", "modus": "komfort", "tage": ["mon"]}])
    pruefe(False, "ungültige Uhrzeit wird abgelehnt")
except store.ValidationError:
    pruefe(True, "ungültige Uhrzeit wird abgelehnt")

print(f"\n{'ALLE PRÜFUNGEN BESTANDEN' if not fehler else str(len(fehler)) + ' FEHLER'}")
sys.exit(1 if fehler else 0)
