"""Öltank – Restmenge aus Lieferungen und Brennerlaufzeit, plus Leckagewache.

Optionaler Baustein: Ohne ``einstellungen["tank"]["aktiv"]`` läuft hier nichts,
und die Oberfläche zeigt den Reiter erst gar nicht an. Wer keinen Öltank hat –
also fast jeder – merkt von diesem Modul nichts.

Das Messprinzip kommt ohne Sensor im Tank aus und stützt sich auf zwei Zahlen,
die sich gegenseitig korrigieren:

* Die **Liefermenge** steht auf dem Lieferschein. Sie ist geeicht und damit
  genauer als jeder Füllstandsgeber – aber sie kommt nur ein- bis zweimal im
  Jahr.
* Die **Brennerlaufzeit** liefert die Auflösung dazwischen. Mal Düsendurchsatz
  ergibt sie den Verbrauch, und weil der Durchsatz nur ein Schätzwert ist,
  driftet sie – bis die nächste Lieferung sie wieder einnordet.

Fehlt die Laufzeit (etwa weil noch keine Kesselanbindung existiert), bleibt der
Stand einfach stehen, bis jemand ihn von Hand korrigiert. Das Modul ist also
auch für sich allein brauchbar.

Wer die Anzeige am Tank in Zentimetern abliest, kann zusätzlich mit dem
Peilstab arbeiten. Zwei Dinge werden damit möglich:

* **Einmessen statt schätzen.** Wer bei einer Lieferung den Stand vorher und
  nachher notiert, bekommt die Liter je Zentimeter geschenkt: gelieferte Menge
  geteilt durch den Höhenunterschied. Das ist genauer als jede Rechnung aus dem
  Typenschild, weil es den Tank misst, wie er wirklich ist.
* **Die ehrliche Restmenge.** Der Saugfuß sitzt einige Zentimeter über dem
  Boden. Was darunter steht, gehört dem Besitzer, aber nicht mehr dem Brenner –
  der zieht dann Luft und geht auf Störung. Mit einer Untergrenze unterscheidet
  der Planer zwischen "im Tank" und "für den Brenner erreichbar".
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import ha_api

_LOGGER = logging.getLogger(__name__)

# So viel Brennerlaufzeit kann zwischen zwei Takten höchstens dazugekommen
# sein. Alles darüber ist kein Verbrauch, sondern ein Zählersprung – etwa
# weil die Kesselanbindung neu eingerichtet wurde und plötzlich den
# Gesamtstand seit 1998 meldet.
MAX_ZUWACHS_H = 24.0

# So lange hebt die Verbrauchshistorie auf. Zwei Monate reichen für eine
# belastbare Reichweite und halten die Zustandsdatei klein.
VERLAUF_TAGE = 60

# Weniger als so viele Tage mit Verbrauch: keine Reichweite. Eine Hochrechnung
# aus zwei Sommertagen wäre eine Zahl ohne Aussage.
MIN_TAGE_FUER_REICHWEITE = 3


def standard_zustand() -> dict:
    return {
        "stand_liter": None,      # None = noch nie gesetzt
        "laufzeit_h": None,       # letzter gesehener Zählerstand
        "lieferungen": [],        # [{"datum": "YYYY-MM-DD", "liter": 3000.0}]
        "verbrauch_tage": {},     # {"YYYY-MM-DD": liter} – nur die letzten 60 Tage
        # Monatssummen bleiben für immer. Zwölf Zahlen im Jahr kosten nichts,
        # und erst damit lässt sich eine Heizperiode mit der vorigen
        # vergleichen – die Frage, um die es beim Heizöl eigentlich geht.
        "verbrauch_monate": {},   # {"YYYY-MM": liter}
        # Ein Zähler, der nur wächst. Home Assistant macht daraus mit
        # state_class "total_increasing" eine Langzeitstatistik, die den
        # Verlust dieser Datei überlebt.
        "gesamt_liter": 0.0,
        # Gleitender Durchschnittspreis, wie bei einer Lagerbewertung: Jede
        # Lieferung mischt sich mit dem Restbestand. Der Verbrauch wird zu
        # diesem Mischpreis bewertet – alles andere wäre geraten, weil im Tank
        # nun einmal kein Öl von 2019 neben Öl von 2026 liegt.
        "preis_pro_liter": None,
        "kosten_monate": {},      # {"YYYY-MM": Betrag}
        "kosten_gesamt": 0.0,
        "leck_seit": None,
    }


def _zustand(state: dict) -> dict:
    t = state.setdefault("tank", {})
    for schluessel, wert in standard_zustand().items():
        t.setdefault(schluessel, wert)
    return t


def liter_je_cm(tank: dict) -> float:
    """Liter je Zentimeter – eingemessen, sonst aus dem Typenschild geschätzt."""
    gemessen = float(tank.get("liter_pro_cm") or 0.0)
    if gemessen > 0:
        return gemessen
    hoehe = float(tank.get("hoehe_voll_cm") or 0.0) - float(
        tank.get("nullpunkt_cm") or 0.0)
    if hoehe > 0:
        return nutzbar_liter(tank) / hoehe
    return 0.0


def cm_zu_liter(tank: dict, cm: float) -> float | None:
    """Eine Ablesung in Liter – über dem Nullpunkt, nicht über der Skala.

    Der Nullpunkt ist das, was die Anzeige bei leerem Tank zeigt. Bei einem
    nachgerüsteten Anzeiger ist er selten null.
    """
    je_cm = liter_je_cm(tank)
    if je_cm <= 0:
        return None
    ueber_null = float(cm) - float(tank.get("nullpunkt_cm") or 0.0)
    return round(max(0.0, ueber_null) * je_cm, 1)


def liter_zu_cm(tank: dict, liter: float | None) -> float | None:
    je_cm = liter_je_cm(tank)
    if je_cm <= 0 or liter is None:
        return None
    return round(liter / je_cm + float(tank.get("nullpunkt_cm") or 0.0), 1)


def reserve_liter(tank: dict) -> float:
    """Was unter dem Saugfuß steht und dem Brenner nicht mehr hilft."""
    return cm_zu_liter(tank, float(tank.get("hoehe_min_cm") or 0.0)) or 0.0


def nutzbar_liter(tank: dict) -> float:
    """Was tatsächlich hineinpasst – Tanks dürfen nicht randvoll gefüllt werden."""
    return float(tank.get("inhalt_liter") or 0.0) * float(
        tank.get("max_fuell_prozent") or 100) / 100.0


# ------------------------------------------------------------- Verbrauch ----

def _verbrauch_buchen(t: dict, liter: float, heute: str) -> None:
    if liter <= 0:
        return
    if t["stand_liter"] is not None:
        t["stand_liter"] = max(0.0, round(t["stand_liter"] - liter, 2))
    verlauf = t["verbrauch_tage"]
    verlauf[heute] = round(verlauf.get(heute, 0.0) + liter, 3)
    _verlauf_kuerzen(verlauf)
    monat = heute[:7]
    t["verbrauch_monate"][monat] = round(
        t["verbrauch_monate"].get(monat, 0.0) + liter, 2)
    t["gesamt_liter"] = round(t.get("gesamt_liter", 0.0) + liter, 2)

    preis = t.get("preis_pro_liter")
    if preis:
        kosten = liter * float(preis)
        t["kosten_monate"][monat] = round(
            t["kosten_monate"].get(monat, 0.0) + kosten, 2)
        t["kosten_gesamt"] = round(t.get("kosten_gesamt", 0.0) + kosten, 2)


def _verlauf_kuerzen(verlauf: dict) -> None:
    grenze = (date.today() - timedelta(days=VERLAUF_TAGE)).isoformat()
    for tag in [d for d in verlauf if d < grenze]:
        verlauf.pop(tag, None)


def _laufzeit_lesen(entity_id: str) -> float | None:
    if not entity_id:
        return None
    zustand = ha_api.get_state(entity_id)
    if not zustand:
        return None
    return ha_api.as_float(zustand.get("state"))


def _reichweite_tage(t: dict, stand: float | None) -> int | None:
    if stand is None:
        return None
    verlauf = t["verbrauch_tage"]
    if len(verlauf) < MIN_TAGE_FUER_REICHWEITE:
        return None
    # Nur die jüngsten zwei Wochen: Was im Oktober verbraucht wurde, sagt im
    # Januar nichts mehr über die kommenden Tage.
    juengste = sorted(verlauf)[-14:]
    werte = [verlauf[tag] for tag in juengste]
    schnitt = sum(werte) / len(werte)
    if schnitt <= 0.05:      # Sommer: der Tank reicht rechnerisch ewig
        return None
    return int(stand / schnitt)


def saison(heute: date | None = None) -> str:
    """Die laufende Heizperiode als "2026/27".

    Sie beginnt im Juli, nicht im Januar: Ein Kalenderjahr zerschneidet den
    Winter in der Mitte und macht jeden Vergleich wertlos.
    """
    heute = heute or date.today()
    beginn = heute.year if heute.month >= 7 else heute.year - 1
    return f"{beginn}/{str(beginn + 1)[-2:]}"


def _preis_mischen(t: dict, liter: float, preis: float) -> float:
    """Gleitender Durchschnittspreis nach einer Lieferung.

    Der alte Bestand behält seinen Wert, die neue Lieferung bringt ihren mit,
    und der Mischpreis gilt ab jetzt für alles im Tank. Das ist die übliche
    Lagerbewertung – und die einzige Rechnung, die ohne Erfindungen auskommt.
    """
    bestand = t.get("stand_liter") or 0.0
    alt = t.get("preis_pro_liter")
    if alt is None or bestand <= 0:
        return round(float(preis), 4)
    wert = bestand * float(alt) + liter * float(preis)
    return round(wert / (bestand + liter), 4)


def _saison_summe(monate: dict, heute: date | None = None) -> float:
    heute = heute or date.today()
    beginn = heute.year if heute.month >= 7 else heute.year - 1
    summe = 0.0
    for schluessel, liter in monate.items():
        try:
            jahr, monat = int(schluessel[:4]), int(schluessel[5:7])
        except (ValueError, IndexError):
            continue
        if (jahr, monat) >= (beginn, 7) and (jahr, monat) <= (beginn + 1, 6):
            summe += liter
    return round(summe, 1)


# ----------------------------------------------------------------- Takt ----

def takt(einstellungen: dict, state: dict) -> dict:
    """Einmal nachrechnen. Gibt den Bericht zurück, den Oberfläche und MQTT sehen."""
    tank = einstellungen.get("tank") or {}
    if not tank.get("aktiv"):
        return {"aktiv": False}

    t = _zustand(state)
    heute = date.today().isoformat()

    # ── Verbrauch aus der Brennerlaufzeit
    laufzeit = _laufzeit_lesen(tank.get("brenner_entity") or "")
    verbrauch_takt = 0.0
    if laufzeit is not None:
        vorher = t["laufzeit_h"]
        if vorher is None:
            # Erster Kontakt: nur merken. Der Zählerstand selbst ist kein
            # Verbrauch, sonst wäre der Tank sofort leer.
            t["laufzeit_h"] = laufzeit
        else:
            zuwachs = laufzeit - vorher
            if zuwachs < 0:
                _LOGGER.info("Brennerzähler zurückgesetzt (%.2f → %.2f h)", vorher, laufzeit)
                t["laufzeit_h"] = laufzeit
            elif zuwachs > MAX_ZUWACHS_H:
                _LOGGER.warning("Unplausibler Sprung der Brennerlaufzeit: +%.1f h – "
                                "übernommen, aber nicht als Verbrauch gebucht", zuwachs)
                t["laufzeit_h"] = laufzeit
            elif zuwachs > 0:
                verbrauch_takt = zuwachs * float(tank.get("durchsatz_l_h") or 0.0)
                _verbrauch_buchen(t, verbrauch_takt, heute)
                t["laufzeit_h"] = laufzeit

    # ── Leckagewache
    leck = False
    leck_entity = tank.get("leckage_entity") or ""
    if leck_entity:
        zustand = ha_api.get_state(leck_entity)
        if zustand:
            leck = str(zustand.get("state", "")).lower() in ("on", "true", "nass", "wet")
    if leck and not t["leck_seit"]:
        t["leck_seit"] = datetime.now().isoformat(timespec="seconds")
    elif not leck:
        t["leck_seit"] = None

    stand = t["stand_liter"]
    nutzbar = nutzbar_liter(tank)
    warnschwelle = float(tank.get("warnschwelle_liter") or 0.0)
    reserve = reserve_liter(tank)
    # Das ist die Zahl, die zählt: Was unter dem Saugfuß steht, kann der
    # Brenner nicht holen. Ein Tank mit 200 Litern "drin" kann leer sein.
    verfuegbar = None if stand is None else max(0.0, stand - reserve)

    return {
        "aktiv": True,
        "stand_liter": None if stand is None else round(stand),
        "nutzbar_liter": round(nutzbar),
        "prozent": None if (stand is None or nutzbar <= 0)
                   else round(stand / nutzbar * 100),
        "stand_cm": liter_zu_cm(tank, stand),
        "verfuegbar_liter": None if verfuegbar is None else round(verfuegbar),
        "reserve_liter": round(reserve) if reserve else 0,
        "liter_pro_cm": round(liter_je_cm(tank), 2) or None,
        "eingemessen": bool(tank.get("liter_pro_cm")),
        "verbrauch_heute": round(t["verbrauch_tage"].get(heute, 0.0), 1),
        "verbrauch_monat": round(t["verbrauch_monate"].get(heute[:7], 0.0), 1),
        "verbrauch_saison": _saison_summe(t["verbrauch_monate"]),
        "saison": saison(),
        "gesamt_liter": round(t.get("gesamt_liter", 0.0), 1),
        "preis_pro_liter": (round(t["preis_pro_liter"], 3)
                            if t.get("preis_pro_liter") else None),
        "wert_im_tank": (round(stand * t["preis_pro_liter"])
                         if (stand is not None and t.get("preis_pro_liter")) else None),
        "kosten_monat": round(t["kosten_monate"].get(heute[:7], 0.0), 2),
        "kosten_saison": _saison_summe(t["kosten_monate"]),
        "kosten_gesamt": round(t.get("kosten_gesamt", 0.0), 2),
        "waehrung": tank.get("waehrung") or "€",
        # Die jüngsten 24 Monate für die Oberfläche, neueste zuerst.
        "monate": [{"monat": m, "liter": round(t["verbrauch_monate"][m], 1),
                    "kosten": round(t["kosten_monate"].get(m, 0.0), 2) or None}
                   for m in sorted(t["verbrauch_monate"], reverse=True)[:24]],
        "reichweite_tage": _reichweite_tage(t, verfuegbar),
        "laufzeit_h": t["laufzeit_h"],
        "laufzeit_gekoppelt": bool(tank.get("brenner_entity")),
        "verbrauch_takt": round(verbrauch_takt, 3),
        "leck": leck,
        "leck_seit": t["leck_seit"],
        "leckage_ueberwacht": bool(leck_entity),
        "warnung": (verfuegbar is not None and warnschwelle > 0
                    and verfuegbar < warnschwelle),
        # Unter dem Saugfuß zieht der Brenner Luft und geht auf Störung.
        "unter_grenze": verfuegbar is not None and reserve > 0 and verfuegbar <= 0,
        "lieferungen": list(reversed(t["lieferungen"]))[:12],
    }


# ------------------------------------------------------------- Meldungen ----

def meldungen(bericht: dict, state: dict) -> list[tuple[str, str]]:
    """Was gemeldet werden soll – aber jede Lage nur einmal.

    Ohne dieses Gedächtnis stünde bei einem Leck alle fünf Minuten dieselbe
    Nachricht auf dem Telefon, und beim dritten Mal schaut niemand mehr hin.
    """
    if not bericht.get("aktiv"):
        return []
    gemerkt = state.setdefault("tank_gemeldet", {})
    raus: list[tuple[str, str]] = []

    for schluessel, aktiv, titel, text in (
        ("leck", bericht.get("leck"), "Leckage am Öltank",
         "Der Melder im Auffangraum hat angesprochen. Bitte sofort nachsehen."),
        ("unter_grenze", bericht.get("unter_grenze"), "Heizöl unter der Grenze",
         "Der Stand liegt unter dem Saugfuß – der Brenner kann Luft ziehen und "
         "auf Störung gehen."),
        ("warnung", bericht.get("warnung"), "Heizöl wird knapp",
         f"Für den Brenner erreichbar sind noch etwa "
         f"{bericht.get('verfuegbar_liter')} Liter."),
    ):
        if aktiv and not gemerkt.get(schluessel):
            raus.append((titel, text))
            gemerkt[schluessel] = True
        elif not aktiv:
            gemerkt.pop(schluessel, None)
    return raus


# ------------------------------------------------------------- Eingaben ----

def lieferung_eintragen(state: dict, liter: float, datum: str | None,
                        tank: dict, cm_vorher: float | None = None,
                        cm_nachher: float | None = None,
                        voll: bool = False,
                        preis_pro_liter: float | None = None,
                        gesamtpreis: float | None = None) -> dict:
    """Eine Tanklieferung verbuchen und den Stand entsprechend anheben.

    Sind der Stand **vorher und nachher** in Zentimetern dabei, misst diese
    Lieferung den Tank gleich mit ein: Liter je Zentimeter ist die gelieferte
    Menge geteilt durch den Höhenunterschied. Das ist der genaueste Wert, den
    es über diesen Behälter je geben wird – er stammt aus einer geeichten
    Menge und dem Tank selbst, nicht aus einem Typenschild von 1965.

    Wurde der Tank dabei **voll gefüllt**, fällt sogar noch mehr ab. Dann ist
    der Inhalt danach bekannt – der Tankwagen füllt bis zur Abschaltung des
    Grenzwertgebers, also auf die Füllgrenze. Damit stehen zwei Gleichungen für
    zwei Unbekannte, und der Planer kennt anschließend auch:

    * die **Anzeige bei vollem Tank** – gemessen statt geschätzt, das ist ja
      genau die Ablesung, die gerade vorliegt;
    * den **Nullpunkt** der Skala, also was die Anzeige bei leerem Tank zeigt::

          Nullpunkt = cm nachher − bekannter Inhalt ÷ Liter je Zentimeter

    Das erspart den Gang mit dem Peilstab in den Dom. Die Rechnung hängt
    allerdings am Nenninhalt vom Typenschild: Stimmt der nicht, wandert der
    Fehler in den Nullpunkt.

    Der eingemessene Wert wird in die Einstellungen zurückgeschrieben; der
    Aufrufer speichert sie.
    """
    if liter <= 0:
        raise ValueError("Liefermenge muss größer als null sein")
    t = _zustand(state)
    eintrag = {"datum": datum or date.today().isoformat(),
               "liter": round(float(liter), 1)}

    # ── Preis: eines von beiden genügt, das andere fällt heraus
    if preis_pro_liter is None and gesamtpreis is not None:
        preis_pro_liter = float(gesamtpreis) / float(liter)
    if preis_pro_liter is not None:
        if preis_pro_liter < 0:
            raise ValueError("Der Preis kann nicht negativ sein")
        eintrag["preis_pro_liter"] = round(float(preis_pro_liter), 4)
        eintrag["gesamtpreis"] = round(float(preis_pro_liter) * float(liter), 2)

    # ── Einmessen, wenn beide Höhen dabei sind
    if cm_vorher is not None and cm_nachher is not None:
        differenz = float(cm_nachher) - float(cm_vorher)
        if differenz <= 0:
            raise ValueError("Der Stand nachher muss über dem Stand vorher liegen")
        eintrag["cm_vorher"] = round(float(cm_vorher), 1)
        eintrag["cm_nachher"] = round(float(cm_nachher), 1)
        eintrag["liter_pro_cm"] = round(float(liter) / differenz, 2)
        tank["liter_pro_cm"] = eintrag["liter_pro_cm"]
        _LOGGER.info("Tank eingemessen: %.1f l auf %.1f cm = %.2f l/cm",
                     liter, differenz, eintrag["liter_pro_cm"])

    # Erst mischen, dann den Bestand anheben – der alte Preis gilt für das,
    # was vorher drin war.
    if eintrag.get("preis_pro_liter") is not None:
        t["preis_pro_liter"] = _preis_mischen(
            t, float(liter), eintrag["preis_pro_liter"])

    # ── Voll getankt: Der Inhalt danach ist bekannt, und damit die Geometrie
    nutzbar = nutzbar_liter(tank)
    if voll:
        eintrag["voll"] = True
        if cm_nachher is not None:
            # Die Ablesung bei vollem Tank ist keine Schätzung mehr.
            tank["hoehe_voll_cm"] = round(float(cm_nachher), 1)
            eintrag["hoehe_voll_cm"] = tank["hoehe_voll_cm"]
            je_cm = liter_je_cm(tank)
            if je_cm > 0 and nutzbar > 0:
                null = round(float(cm_nachher) - nutzbar / je_cm, 1)
                if null < 0:
                    # Das ist keine Panne, sondern ein Befund: Der Nenninhalt
                    # vom Typenschild passt nicht zu dem, was die Skala sagt.
                    # Der Nutzer soll das erfahren, nicht nur der Log.
                    eintrag["hinweis"] = (
                        f"Der errechnete Nullpunkt wäre {null:.1f} cm – "
                        f"negativ. Das heißt: Der eingetragene Tankinhalt passt "
                        f"nicht zu dieser Skala. Prüf den Nenninhalt und die "
                        f"Füllgrenze; bis dahin steht der Nullpunkt auf 0.")
                    _LOGGER.warning("Errechneter Nullpunkt wäre %.1f cm – der "
                                    "Nenninhalt passt nicht zur Skala.", null)
                    null = 0.0
                if null < float(cm_nachher):
                    tank["nullpunkt_cm"] = null
                    eintrag["nullpunkt_cm"] = null
                    _LOGGER.info("Nullpunkt aus voller Füllung: %.1f cm", null)

    t["lieferungen"].append(eintrag)
    t["lieferungen"] = t["lieferungen"][-60:]

    if voll and nutzbar > 0:
        # Der bekannte Inhalt schlägt jede Ablesung und jede Fortschreibung.
        t["stand_liter"] = round(nutzbar, 1)
    elif cm_nachher is not None and liter_je_cm(tank) > 0:
        # Die abgelesene Höhe ist eine Messung, die gerechnete Summe nur eine
        # Fortschreibung. Die Messung gewinnt.
        t["stand_liter"] = cm_zu_liter(tank, float(cm_nachher))
    else:
        vorher = t["stand_liter"] or 0.0
        # Mehr als voll geht nicht – wer sich vertippt, bekommt den Deckel,
        # nicht einen Tank mit 6000 Litern in einem 4700-Liter-Behälter.
        t["stand_liter"] = round(min(vorher + eintrag["liter"], nutzbar), 1) \
            if nutzbar > 0 else round(vorher + eintrag["liter"], 1)
    return eintrag


def stand_setzen(state: dict, tank: dict, liter: float | None = None,
                 cm: float | None = None) -> float:
    """Den Stand von Hand korrigieren – in Litern oder in Zentimetern.

    Zentimeter sind der natürlichere Weg: Das ist die Zahl, die am Tank steht.
    Sie setzt allerdings voraus, dass Liter je Zentimeter bekannt sind.
    """
    if cm is not None:
        if cm < 0:
            raise ValueError("Der Füllstand kann nicht negativ sein")
        liter = cm_zu_liter(tank, float(cm))
        if liter is None:
            raise ValueError("Für Zentimeter fehlen die Liter je Zentimeter – "
                             "trag sie ein oder miss den Tank bei der nächsten "
                             "Lieferung ein")
    if liter is None or liter < 0:
        raise ValueError("Der Füllstand kann nicht negativ sein")
    nutzbar = nutzbar_liter(tank)
    t = _zustand(state)
    t["stand_liter"] = round(min(float(liter), nutzbar) if nutzbar > 0 else float(liter), 1)
    return t["stand_liter"]
