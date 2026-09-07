#!/usr/bin/env python3
"""Trockenprüfung des Tankteils – ohne Öltank, ohne Home Assistant.

Aufruf aus dem Repo:

    python3 heizungsplaner/tests/test_tank.py

Dieser Baustein hängt an einer Anlage, die außer dem Autor kaum jemand hat.
Damit trotzdem jemand daran arbeiten kann, ist die Brennerlaufzeit hier
gefälscht: ``ha_api.get_state`` wird ersetzt, und der „Zähler“ ist eine Zahl,
die der Test selbst weiterdreht.

Geprüft wird vor allem, was in der Praxis schiefgeht: der erste Zählerstand
(der kein Verbrauch ist), ein zurückgesetzter Zähler und ein Zählersprung nach
einem Wechsel der Kesselanbindung.
"""
import os
import sys
import tempfile
from datetime import date, timedelta

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "backend"))

import ha_api
import store
import tank

fehler = []


def pruefe(bedingung, text):
    print(f"  {'✓' if bedingung else '✗'} {text}")
    if not bedingung:
        fehler.append(text)


# ── Der gefälschte Kessel ────────────────────────────────────────────────
_zustaende: dict[str, str] = {}


def _get_state(entity_id):
    if entity_id not in _zustaende:
        return None
    return {"entity_id": entity_id, "state": _zustaende[entity_id]}


ha_api.get_state = _get_state


def einstellungen(**abweichend):
    e = store.standard_einstellungen()
    e["tank"].update({
        "aktiv": True,
        "inhalt_liter": 4700.0,
        "max_fuell_prozent": 95,
        "warnschwelle_liter": 800.0,
        "brenner_entity": "sensor.brennerstunden",
        "durchsatz_l_h": 2.4,
    })
    e["tank"].update(abweichend)
    return e


print("=== Ausgeschaltet bleibt ausgeschaltet ===")
e = einstellungen()
e["tank"]["aktiv"] = False
state = {}
bericht = tank.takt(e, state)
pruefe(bericht == {"aktiv": False}, "abgeschaltet gibt es nur die Absage")
pruefe("tank" not in state, "abgeschaltet wird nichts in den Zustand geschrieben")

print("\n=== Nutzbare Menge ===")
pruefe(tank.nutzbar_liter(einstellungen()["tank"]) == 4465.0,
       "4700 Liter bei 95 % Füllgrenze sind 4465 Liter")

print("\n=== Der erste Zählerstand ist kein Verbrauch ===")
state = {}
_zustaende["sensor.brennerstunden"] = "1234.0"
tank.stand_setzen(state, 3000, 4465.0)
bericht = tank.takt(einstellungen(), state)
pruefe(bericht["stand_liter"] == 3000,
       "der Anfangsbestand überlebt den ersten Takt unverändert")
pruefe(state["tank"]["laufzeit_h"] == 1234.0, "der Zählerstand ist gemerkt")

print("\n=== Verbrauch aus der Laufzeit ===")
_zustaende["sensor.brennerstunden"] = "1236.0"      # zwei Stunden gelaufen
bericht = tank.takt(einstellungen(), state)
pruefe(bericht["stand_liter"] == 2995,
       "zwei Stunden × 2,4 l/h ergeben 4,8 Liter weniger")
pruefe(abs(bericht["verbrauch_heute"] - 4.8) < 0.01,
       "der Tagesverbrauch steht bei 4,8 Litern")

print("\n=== Ein zurückgesetzter Zähler frisst den Tank nicht leer ===")
_zustaende["sensor.brennerstunden"] = "3.0"          # Kessel getauscht, Zähler neu
bericht = tank.takt(einstellungen(), state)
pruefe(bericht["stand_liter"] == 2995,
       "der Rücksprung wird übernommen, aber nicht verbucht")
pruefe(state["tank"]["laufzeit_h"] == 3.0, "der neue Zählerstand gilt ab jetzt")

print("\n=== Ein Zählersprung ist kein Verbrauch ===")
_zustaende["sensor.brennerstunden"] = "5000.0"       # plötzlich Gesamtstand seit 1998
bericht = tank.takt(einstellungen(), state)
pruefe(bericht["stand_liter"] == 2995,
       "ein Sprung über 24 Stunden wird verworfen")

print("\n=== Ohne Laufzeitzähler passiert nichts ===")
ohne = einstellungen(brenner_entity="")
state2 = {}
tank.stand_setzen(state2, 1000, 4465.0)
bericht = tank.takt(ohne, state2)
pruefe(bericht["stand_liter"] == 1000, "der Stand bleibt stehen")
pruefe(bericht["laufzeit_gekoppelt"] is False, "die Oberfläche erfährt davon")

print("\n=== Lieferungen ===")
state3 = {}
tank.stand_setzen(state3, 500, 4465.0)
tank.lieferung_eintragen(state3, 2000, "2026-09-07", 4465.0)
pruefe(state3["tank"]["stand_liter"] == 2500.0, "2000 Liter kommen dazu")
tank.lieferung_eintragen(state3, 9000, None, 4465.0)
pruefe(state3["tank"]["stand_liter"] == 4465.0,
       "mehr als voll geht nicht – der Deckel greift")
try:
    tank.lieferung_eintragen(state3, 0, None, 4465.0)
    pruefe(False, "eine Lieferung über null Liter wird abgelehnt")
except ValueError:
    pruefe(True, "eine Lieferung über null Liter wird abgelehnt")

print("\n=== Warnschwelle ===")
state4 = {}
tank.stand_setzen(state4, 700, 4465.0)
_zustaende["sensor.brennerstunden"] = "0.0"
bericht = tank.takt(einstellungen(), state4)
pruefe(bericht["warnung"] is True, "unter 800 Litern wird gewarnt")
pruefe(bericht["prozent"] == 16, "700 von 4465 Litern sind 16 %")

print("\n=== Leckage ===")
state5 = {}
_zustaende["binary_sensor.oelwanne"] = "on"
mit_leck = einstellungen(leckage_entity="binary_sensor.oelwanne")
bericht = tank.takt(mit_leck, state5)
pruefe(bericht["leck"] is True, "der Melder wird gelesen")
pruefe(bool(state5["tank"]["leck_seit"]), "der Zeitpunkt ist festgehalten")
meldungen = tank.meldungen(bericht, state5)
pruefe(len(meldungen) == 1, "es gibt genau eine Meldung")
pruefe(tank.meldungen(bericht, state5) == [],
       "beim zweiten Takt schweigt sie – sonst alle fünf Minuten dieselbe SMS")
_zustaende["binary_sensor.oelwanne"] = "off"
bericht = tank.takt(mit_leck, state5)
pruefe(state5["tank"]["leck_seit"] is None, "Entwarnung setzt den Zeitpunkt zurück")

print("\n=== Reichweite ===")
state6 = {}
tank.stand_setzen(state6, 1000, 4465.0)
t = state6["tank"]
for i in range(5):
    tag = (date.today() - timedelta(days=i)).isoformat()
    t["verbrauch_tage"][tag] = 20.0
_zustaende["sensor.brennerstunden"] = "0.0"
bericht = tank.takt(einstellungen(), state6)
pruefe(bericht["reichweite_tage"] == 50, "1000 Liter bei 20 l/Tag reichen 50 Tage")
t["verbrauch_tage"] = {(date.today() - timedelta(days=i)).isoformat(): 0.0
                       for i in range(5)}
bericht = tank.takt(einstellungen(), state6)
pruefe(bericht["reichweite_tage"] is None,
       "im Sommer gibt es keine Reichweite statt einer Unendlichkeit")

print("\n=== Einstellungen werden geprüft ===")
e = store.validate_einstellungen({"tank": {"aktiv": True, "inhalt_liter": 4700,
                                           "durchsatz_l_h": 2.4}})
pruefe(e["tank"]["aktiv"] is True and e["tank"]["inhalt_liter"] == 4700.0,
       "gültige Werte kommen unverändert durch")
# Unsinn wird abgelehnt, nicht stillschweigend zurechtgebogen – sonst speichert
# jemand 300 % Füllgrenze und wundert sich später über die Zahlen.
for feld, wert, was in (("max_fuell_prozent", 300, "Füllgrenze über 100 %"),
                        ("durchsatz_l_h", -5, "negativer Düsendurchsatz"),
                        ("inhalt_liter", -1, "negativer Tankinhalt")):
    try:
        store.validate_einstellungen({"tank": {feld: wert}})
        pruefe(False, f"{was} wird abgelehnt")
    except store.ValidationError:
        pruefe(True, f"{was} wird abgelehnt")
pruefe(store.standard_einstellungen()["tank"]["aktiv"] is False,
       "ab Werk ist der Tankteil aus")

print(f"\n{'ALLE PRÜFUNGEN BESTANDEN' if not fehler else str(len(fehler)) + ' FEHLER'}")
sys.exit(1 if fehler else 0)
