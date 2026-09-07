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
        "verbrauch_tage": {},     # {"YYYY-MM-DD": liter}
        "leck_seit": None,
    }


def _zustand(state: dict) -> dict:
    t = state.setdefault("tank", {})
    for schluessel, wert in standard_zustand().items():
        t.setdefault(schluessel, wert)
    return t


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

    return {
        "aktiv": True,
        "stand_liter": None if stand is None else round(stand),
        "nutzbar_liter": round(nutzbar),
        "prozent": None if (stand is None or nutzbar <= 0)
                   else round(stand / nutzbar * 100),
        "verbrauch_heute": round(t["verbrauch_tage"].get(heute, 0.0), 1),
        "reichweite_tage": _reichweite_tage(t, stand),
        "laufzeit_h": t["laufzeit_h"],
        "laufzeit_gekoppelt": bool(tank.get("brenner_entity")),
        "verbrauch_takt": round(verbrauch_takt, 3),
        "leck": leck,
        "leck_seit": t["leck_seit"],
        "leckage_ueberwacht": bool(leck_entity),
        "warnung": stand is not None and warnschwelle > 0 and stand < warnschwelle,
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
        ("warnung", bericht.get("warnung"), "Heizöl wird knapp",
         f"Restmenge etwa {bericht.get('stand_liter')} Liter."),
    ):
        if aktiv and not gemerkt.get(schluessel):
            raus.append((titel, text))
            gemerkt[schluessel] = True
        elif not aktiv:
            gemerkt.pop(schluessel, None)
    return raus


# ------------------------------------------------------------- Eingaben ----

def lieferung_eintragen(state: dict, liter: float, datum: str | None,
                        nutzbar: float) -> dict:
    """Eine Tanklieferung verbuchen und den Stand entsprechend anheben."""
    if liter <= 0:
        raise ValueError("Liefermenge muss größer als null sein")
    t = _zustand(state)
    eintrag = {"datum": datum or date.today().isoformat(), "liter": round(float(liter), 1)}
    t["lieferungen"].append(eintrag)
    t["lieferungen"] = t["lieferungen"][-60:]
    vorher = t["stand_liter"] or 0.0
    # Mehr als voll geht nicht – wer sich vertippt, bekommt den Deckel, nicht
    # einen Tank mit 6000 Litern in einem 4700-Liter-Behälter.
    t["stand_liter"] = round(min(vorher + eintrag["liter"], nutzbar), 1) if nutzbar > 0 \
        else round(vorher + eintrag["liter"], 1)
    return eintrag


def stand_setzen(state: dict, liter: float, nutzbar: float) -> float:
    """Den Stand von Hand korrigieren – etwa nach einem Blick auf den Zeiger."""
    if liter < 0:
        raise ValueError("Der Füllstand kann nicht negativ sein")
    t = _zustand(state)
    t["stand_liter"] = round(min(float(liter), nutzbar) if nutzbar > 0 else float(liter), 1)
    return t["stand_liter"]
