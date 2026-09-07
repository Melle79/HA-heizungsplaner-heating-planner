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
tank.stand_setzen(state, einstellungen()['tank'], 3000)
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
tank.stand_setzen(state2, ohne['tank'], 1000)
bericht = tank.takt(ohne, state2)
pruefe(bericht["stand_liter"] == 1000, "der Stand bleibt stehen")
pruefe(bericht["laufzeit_gekoppelt"] is False, "die Oberfläche erfährt davon")

print("\n=== Lieferungen ===")
state3 = {}
tank.stand_setzen(state3, einstellungen()['tank'], 500)
tank.lieferung_eintragen(state3, 2000, '2026-09-07', einstellungen()['tank'])
pruefe(state3["tank"]["stand_liter"] == 2500.0, "2000 Liter kommen dazu")
tank.lieferung_eintragen(state3, 9000, None, einstellungen()['tank'])
pruefe(state3["tank"]["stand_liter"] == 4465.0,
       "mehr als voll geht nicht – der Deckel greift")
try:
    tank.lieferung_eintragen(state3, 0, None, einstellungen()['tank'])
    pruefe(False, "eine Lieferung über null Liter wird abgelehnt")
except ValueError:
    pruefe(True, "eine Lieferung über null Liter wird abgelehnt")

print("\n=== Einmessen ueber eine Lieferung ===")
# Der eigentliche Gewinn: Aus geeichter Liefermenge und zwei Peilstab-Werten
# faellt die Liter-je-Zentimeter heraus - genauer als jede Rechnung aus dem
# Typenschild von 1965.
tk = einstellungen()["tank"]
state_m = {}
eintrag = tank.lieferung_eintragen(state_m, 3000, "2026-09-07", tk,
                                   cm_vorher=30.0, cm_nachher=126.0)
pruefe(eintrag["liter_pro_cm"] == 31.25,
       "3000 Liter auf 96 cm ergeben 31,25 Liter je Zentimeter")
pruefe(tk["liter_pro_cm"] == 31.25, "der Wert landet in den Einstellungen")
pruefe(state_m["tank"]["stand_liter"] == 3937.5,
       "der Stand kommt aus der gemessenen Hoehe, nicht aus der Summe")

# Verdrehte Eingabe: nachher tiefer als vorher
try:
    tank.lieferung_eintragen({}, 3000, None, dict(tk), cm_vorher=100.0, cm_nachher=40.0)
    pruefe(False, "nachher unter vorher wird abgelehnt")
except ValueError:
    pruefe(True, "nachher unter vorher wird abgelehnt")

print("\n=== Was der Brenner wirklich erreicht ===")
tk2 = einstellungen()["tank"]
tk2.update({"liter_pro_cm": 31.25, "hoehe_voll_cm": 142.0, "hoehe_min_cm": 8.0})
state_v = {}
tank.stand_setzen(state_v, tk2, cm=20.0)
pruefe(state_v["tank"]["stand_liter"] == 625.0, "20 cm sind 625 Liter im Tank")
_zustaende["sensor.brennerstunden"] = "0.0"
b = tank.takt({"tank": tk2}, state_v)
pruefe(b["reserve_liter"] == 250, "unter dem Saugfuss stehen 250 Liter")
pruefe(b["verfuegbar_liter"] == 375, "erreichbar sind nur 375 Liter")
pruefe(b["stand_cm"] == 20.0, "die Hoehe wird zurueckgerechnet")
pruefe(b["unter_grenze"] is False, "ueber der Grenze gibt es keine Meldung")

tank.stand_setzen(state_v, tk2, cm=6.0)
b = tank.takt({"tank": tk2}, state_v)
pruefe(b["verfuegbar_liter"] == 0, "unter dem Saugfuss ist nichts mehr erreichbar")
pruefe(b["unter_grenze"] is True, "und das wird gemeldet")
pruefe(len(tank.meldungen(b, state_v)) >= 1, "es gibt eine Meldung dazu")

print("\n=== Voll getankt: die Geometrie faellt mit ab ===")
# Svens Fall vor der ersten Bestellung: Anzeiger nachgeruestet, Skala passt
# nicht, Nullpunkt unbekannt. Eine volle Fuellung loest beides auf.
tk_f = einstellungen()["tank"]        # 4700 l, 95 % -> 4465 nutzbar
state_f = {}
tank.stand_setzen(state_f, tk_f, 500)
# 3920 Liter von 23 auf 135 cm: 112 cm Unterschied, also 35,0 l/cm.
e = tank.lieferung_eintragen(state_f, 3920, "2026-09-10", tk_f,
                             cm_vorher=23.0, cm_nachher=135.0, voll=True)
pruefe(e["liter_pro_cm"] == 35.0,
       "die Steigung kommt aus der Differenz der Ablesungen")
pruefe(tk_f["hoehe_voll_cm"] == 135.0,
       "die Anzeige bei vollem Tank ist jetzt gemessen, nicht geschaetzt")
erwartet = round(135.0 - 4465 / 35.0, 1)      # 7,4 cm
pruefe(tk_f["nullpunkt_cm"] == erwartet,
       f"der Nullpunkt faellt mit ab ({erwartet} cm)")
pruefe(state_f["tank"]["stand_liter"] == 4465.0,
       "der Stand ist danach der bekannte Inhalt, nicht die Summe")
# Gegenprobe: Die Umrechnung trifft die volle Hoehe wieder.
pruefe(abs(tank.cm_zu_liter(tk_f, 135.0) - 4465.0) < 2.0,
       "135 cm ergeben rueckgerechnet wieder den vollen Tank")

print("\n=== Voll getankt ohne Hoehen ===")
tk_g = einstellungen()["tank"]
state_g = {}
tank.stand_setzen(state_g, tk_g, 200)
tank.lieferung_eintragen(state_g, 4000, None, tk_g, voll=True)
pruefe(state_g["tank"]["stand_liter"] == 4465.0,
       "auch ohne Ablesungen gilt danach der bekannte Inhalt")
pruefe(tk_g["nullpunkt_cm"] == 0.0, "an der Geometrie aendert sich nichts")

print("\n=== Wenn der Nenninhalt nicht zur Skala passt ===")
# Zu grosser Nenninhalt: Der errechnete Nullpunkt waere negativ. Statt eine
# unsinnige Zahl zu speichern, wird auf null geklemmt.
tk_h = einstellungen(inhalt_liter=20000.0)["tank"]
tank.lieferung_eintragen({}, 3600, None, tk_h,
                         cm_vorher=23.0, cm_nachher=126.0, voll=True)
pruefe(tk_h["nullpunkt_cm"] == 0.0, "ein negativer Nullpunkt wird auf 0 geklemmt")
e_h = tank.lieferung_eintragen({}, 3600, None, dict(tk_h),
                               cm_vorher=23.0, cm_nachher=126.0, voll=True)
pruefe("hinweis" in e_h, "und der Nutzer bekommt einen Hinweis, nicht nur der Log")

print("\n=== Nachgeruesteter Anzeiger: der Nullpunkt ===")
# Svens Fall: Skala 0-150 cm auf einem Tank von etwa 130 cm. Der Zeiger steht
# bei leerem Tank nicht auf null.
tk_v = einstellungen()["tank"]
tk_v.update({"liter_pro_cm": 35.0, "hoehe_voll_cm": 126.0, "hoehe_min_cm": 15.0,
             "nullpunkt_cm": 8.0})
pruefe(tank.cm_zu_liter(tk_v, 8.0) == 0.0, "am Nullpunkt sind es null Liter")
pruefe(tank.cm_zu_liter(tk_v, 23.0) == 525.0,
       "23 cm sind 15 cm ueber null, also 525 Liter statt 805")
pruefe(tank.cm_zu_liter(tk_v, 3.0) == 0.0,
       "unter dem Nullpunkt gibt es keine negativen Liter")
pruefe(tank.liter_zu_cm(tk_v, 525.0) == 23.0, "der Rueckweg trifft wieder 23 cm")

# Die Einmessung ueber eine Lieferung bleibt vom Versatz unberuehrt: Sie
# rechnet mit der Differenz, und die kuerzt ihn heraus.
tk_a = einstellungen()["tank"]; tk_a["nullpunkt_cm"] = 0.0
tk_b = einstellungen()["tank"]; tk_b["nullpunkt_cm"] = 8.0
e1 = tank.lieferung_eintragen({}, 3000, None, tk_a, cm_vorher=30.0, cm_nachher=126.0)
e2 = tank.lieferung_eintragen({}, 3000, None, tk_b, cm_vorher=30.0, cm_nachher=126.0)
pruefe(e1["liter_pro_cm"] == e2["liter_pro_cm"],
       "der Versatz kuerzt sich beim Einmessen heraus")

# Ohne eingemessenen Wert wird die Steigung ueber die nutzbare Hoehe geschaetzt,
# und die ist um den Nullpunkt kuerzer.
tk_s = einstellungen()["tank"]
tk_s.update({"hoehe_voll_cm": 126.0, "nullpunkt_cm": 8.0})
pruefe(abs(tank.liter_je_cm(tk_s) - 4465.0 / 118.0) < 0.01,
       "die Schaetzung rechnet mit 118 statt 126 Zentimetern")

try:
    store.validate_einstellungen({"tank": {"hoehe_voll_cm": 100, "nullpunkt_cm": 120}})
    pruefe(False, "ein Nullpunkt ueber der Fuellhoehe wird abgelehnt")
except store.ValidationError:
    pruefe(True, "ein Nullpunkt ueber der Fuellhoehe wird abgelehnt")

print("\n=== Zentimeter ohne Einmessung ===")
tk3 = einstellungen()["tank"]      # ohne hoehe_voll_cm und liter_pro_cm
try:
    tank.stand_setzen({}, tk3, cm=50.0)
    pruefe(False, "Zentimeter ohne Kalibrierung werden abgelehnt")
except ValueError:
    pruefe(True, "Zentimeter ohne Kalibrierung werden abgelehnt")

print("\n=== Untergrenze ueber der Fuellhoehe ===")
try:
    store.validate_einstellungen({"tank": {"hoehe_voll_cm": 100, "hoehe_min_cm": 120}})
    pruefe(False, "eine Untergrenze ueber der Fuellhoehe wird abgelehnt")
except store.ValidationError:
    pruefe(True, "eine Untergrenze ueber der Fuellhoehe wird abgelehnt")

print("\n=== Warnschwelle ===")
state4 = {}
tank.stand_setzen(state4, einstellungen()['tank'], 700)
_zustaende["sensor.brennerstunden"] = "0.0"
bericht = tank.takt(einstellungen(), state4)
pruefe(bericht["warnung"] is True, "unter 800 Litern wird gewarnt")
pruefe(bericht["prozent"] == 16, "700 von 4465 Litern sind 16 %")

print("\n=== Eine Ablesung bleibt eine Ablesung ===")
# Der Fehler, der das ausgeloest hat: Der Stand lag in Litern. Wer danach den
# Nullpunkt berichtigte, bekam mehr Oel statt weniger - die Literzahl blieb
# stehen, und der Planer behauptete eine Anzeige, die am Tank nicht stand.
tk_a = einstellungen()["tank"]
tk_a.update({"hoehe_voll_cm": 126.0, "hoehe_min_cm": 15.0, "nullpunkt_cm": 0.0})
state_a = {}
tank.stand_setzen(state_a, tk_a, cm=23.0)
_zustaende["sensor.brennerstunden"] = "0.0"
b1 = tank.takt({"tank": tk_a}, state_a)
pruefe(b1["stand_cm"] == 23.0, "die Anzeige steht auf 23 cm")
pruefe(b1["stand_liter"] == 815, "das sind ohne Versatz 815 Liter")

# Jetzt der Nullpunkt - und nur der.
tk_a["nullpunkt_cm"] = 10.0
b2 = tank.takt({"tank": tk_a}, state_a)
pruefe(b2["stand_cm"] == 23.0, "die Anzeige steht immer noch auf 23 cm")
pruefe(b2["stand_liter"] < b1["stand_liter"],
       f"und es ist jetzt WENIGER Oel ({b2['stand_liter']} statt {b1['stand_liter']})")
pruefe(b2["reserve_liter"] < b1["reserve_liter"],
       f"und weniger liegt unter dem Saugfuss ({b2['reserve_liter']} statt "
       f"{b1['reserve_liter']})")
# Die erreichbare Menge aendert sich dabei kaum, und das ist richtig: Der
# Abstand zwischen Zeiger und Saugfuss bleibt 8 cm, nur wiegt ein Skalen-
# zentimeter jetzt mehr Liter, weil derselbe Inhalt auf weniger cm verteilt ist.
pruefe(abs(b2["verfuegbar_liter"] - b1["verfuegbar_liter"]) < 40,
       "die erreichbare Menge bleibt in derselben Groessenordnung")

print("\n=== Verbrauch zaehlt von der Ablesung ab ===")
_zustaende["sensor.brennerstunden"] = "10.0"      # 24 Liter
b3 = tank.takt({"tank": tk_a}, state_a)
pruefe(abs(b3["stand_liter"] - (b2["stand_liter"] - 24)) <= 1,
       "24 Liter weniger als bei der Ablesung")
# Und eine Korrektur der Umrechnung rechnet den Verbrauch weiter mit.
tk_a["nullpunkt_cm"] = 8.0
b4 = tank.takt({"tank": tk_a}, state_a)
erwartet = round(tank.cm_zu_liter(tk_a, 23.0) - 24, 1)
pruefe(abs(b4["stand_liter"] - erwartet) <= 1,
       "nach der naechsten Korrektur stimmt beides zusammen")

print("\n=== Literangaben bleiben Literangaben ===")
tk_l = einstellungen()["tank"]
state_l = {}
tank.stand_setzen(state_l, tk_l, 1000)
tk_l["nullpunkt_cm"] = 10.0                       # aendert an Litern nichts
_zustaende["sensor.brennerstunden"] = "0.0"
b = tank.takt({"tank": tk_l}, state_l)
pruefe(b["stand_liter"] == 1000, "wer Liter eintraegt, bekommt Liter")

print("\n=== Zustand aus einer aelteren Fassung ===")
# Ohne "basis" darf beim Update nichts springen.
alt_state = {"tank": {"stand_liter": 815.0, "laufzeit_h": None, "lieferungen": [],
                      "verbrauch_tage": {}, "leck_seit": None}}
b = tank.takt(einstellungen(), alt_state)
pruefe(b["stand_liter"] == 815, "der alte Literwert gilt unveraendert weiter")

print("\n=== Preise und der gleitende Mischpreis ===")
tk_p = einstellungen()["tank"]
state_p = {}
# Erste Lieferung: 2000 Liter zu 1,10 - der Tank war leer.
e = tank.lieferung_eintragen(state_p, 2000, "2026-01-10", tk_p, preis_pro_liter=1.10)
pruefe(e["gesamtpreis"] == 2200.0, "der Gesamtpreis faellt aus der Menge")
pruefe(state_p["tank"]["preis_pro_liter"] == 1.10, "der Mischpreis ist der Lieferpreis")

# Gesamtpreis statt Literpreis: das andere rechnet sich aus.
e2 = tank.lieferung_eintragen({}, 1000, None, dict(tk_p), gesamtpreis=950.0)
pruefe(e2["preis_pro_liter"] == 0.95, "aus 950 Euro fuer 1000 Liter werden 0,95/l")

# Zweite Lieferung zu einem anderen Preis: der Bestand mischt sich.
tank.lieferung_eintragen(state_p, 2000, "2026-06-10", tk_p, preis_pro_liter=0.90)
pruefe(state_p["tank"]["preis_pro_liter"] == 1.0,
       "2000 l zu 1,10 und 2000 l zu 0,90 ergeben 1,00 im Mittel")

print("\n=== Kosten folgen dem Verbrauch ===")
_zustaende["sensor.brennerstunden"] = "0.0"
tank.takt({"tank": tk_p}, state_p)
_zustaende["sensor.brennerstunden"] = "10.0"          # 24 Liter
b = tank.takt({"tank": tk_p}, state_p)
pruefe(b["kosten_gesamt"] == 24.0, "24 Liter zu 1,00 kosten 24 Euro")
pruefe(b["kosten_monat"] == 24.0, "die Monatskosten stehen auch")
pruefe(b["preis_pro_liter"] == 1.0, "der Mischpreis steht im Bericht")
pruefe(b["wert_im_tank"] == round(b["stand_liter"] * 1.0),
       "der Wert im Tank ist Bestand mal Mischpreis")
pruefe(b["waehrung"] == "€", "die Waehrung kommt aus den Einstellungen")

print("\n=== Ohne Preis bleibt es bei Litern ===")
tk_o = einstellungen()["tank"]
state_o = {}
tank.stand_setzen(state_o, tk_o, 1000)
tank.lieferung_eintragen(state_o, 500, None, tk_o)     # kein Preis
_zustaende["sensor.brennerstunden"] = "0.0"
tank.takt({"tank": tk_o}, state_o)
_zustaende["sensor.brennerstunden"] = "10.0"
b = tank.takt({"tank": tk_o}, state_o)
pruefe(b["preis_pro_liter"] is None, "ohne Lieferpreis gibt es keinen Mischpreis")
pruefe(b["kosten_gesamt"] == 0.0, "und keine Kosten - keine erfundenen Zahlen")
pruefe(b["wert_im_tank"] is None, "auch keinen Wert im Tank")

try:
    tank.lieferung_eintragen({}, 100, None, dict(tk_o), preis_pro_liter=-1)
    pruefe(False, "ein negativer Preis wird abgelehnt")
except ValueError:
    pruefe(True, "ein negativer Preis wird abgelehnt")

print("\n=== Verbrauchshistorie ===")
# Tageswerte werden nach 60 Tagen weggeworfen, Monatssummen nie. Nur so
# laesst sich eine Heizperiode mit der vorigen vergleichen.
state_h = {}
tank.stand_setzen(state_h, einstellungen()["tank"], 3000)
_zustaende["sensor.brennerstunden"] = "0.0"
tank.takt(einstellungen(), state_h)
_zustaende["sensor.brennerstunden"] = "10.0"     # zehn Stunden = 24 Liter
b = tank.takt(einstellungen(), state_h)
pruefe(b["gesamt_liter"] == 24.0, "der Gesamtzaehler steht bei 24 Litern")
pruefe(b["verbrauch_monat"] == 24.0, "die Monatssumme auch")
pruefe(len(b["monate"]) == 1, "es gibt einen Monat in der Liste")

_zustaende["sensor.brennerstunden"] = "20.0"
b = tank.takt(einstellungen(), state_h)
pruefe(b["gesamt_liter"] == 48.0, "der Gesamtzaehler waechst nur")

# Alte Tageswerte fliegen raus, die Monatssummen bleiben
t = state_h["tank"]
t["verbrauch_tage"][(date.today() - timedelta(days=90)).isoformat()] = 99.0
t["verbrauch_monate"]["2019-01"] = 500.0
_zustaende["sensor.brennerstunden"] = "20.5"
b = tank.takt(einstellungen(), state_h)
pruefe(all(tag >= (date.today() - timedelta(days=61)).isoformat()
           for tag in t["verbrauch_tage"]),
       "Tageswerte aelter als 60 Tage sind fort")
pruefe(t["verbrauch_monate"].get("2019-01") == 500.0,
       "die Monatssumme von 2019 steht noch")

print("\n=== Heizperiode ===")
# Sie beginnt im Juli - ein Kalenderjahr zerschnitte den Winter in der Mitte.
pruefe(tank.saison(date(2026, 9, 7)) == "2026/27", "September gehoert zu 2026/27")
pruefe(tank.saison(date(2027, 2, 1)) == "2026/27", "Februar auch noch")
pruefe(tank.saison(date(2027, 7, 1)) == "2027/28", "im Juli beginnt die naechste")
monate = {"2026-08": 100.0, "2026-12": 400.0, "2027-03": 300.0,
          "2027-08": 50.0, "2026-05": 200.0}
pruefe(tank._saison_summe(monate, date(2027, 2, 1)) == 800.0,
       "die Periode 2026/27 summiert nur ihre eigenen Monate")

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
tank.stand_setzen(state6, einstellungen()['tank'], 1000)
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
