"""Der Wochenplan eines Raumes: welcher Modus gilt jetzt, und was kommt als Nächstes.

Ein Zeitplan ist eine Liste von Umschaltpunkten – genau wie am mechanischen
Heizungsprogramm. Jeder Punkt sagt: ab dieser Uhrzeit, an diesen Wochentagen,
gilt dieser Modus. Es gibt keine Endzeiten; der nächste Punkt löst den
vorherigen ab. Dadurch kann keine Lücke entstehen, in der niemand zuständig
ist – der Fallstrick der Slot-Pläne mit ``stop``-Zeit.

Ein Punkt kann auf eine Tagesart beschränkt sein. Es gibt zwei Paare, weil
nicht jeder im Haus demselben Kalender folgt:

* **Schultag / schulfrei** – für alle, die zur Schule gehen. Entscheidet der
  Schulfrei-Schalter, der auch die Ferien kennt.
* **Werktag / arbeitsfrei** – für alle, die arbeiten. Entscheidet allein der
  **Feiertag**: Das Wochenende steckt schon in den Wochentag-Haken des Punktes,
  und Schulferien gehen einen Berufstätigen nichts an.

Beide Paare lassen sich in einem Plan mischen; welcher Fall gerade gilt,
entscheiden zwei getrennte Entitäten in Home Assistant.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

TAGE = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _uhrzeit(text: str) -> time:
    stunde, minute = text.split(":")
    return time(int(stunde), int(minute))


def _passt(eintrag: dict, wochentag: str, schulfrei: bool | None,
           feiertag: bool | None = None) -> bool:
    if wochentag not in eintrag.get("tage", []):
        return False
    gilt = eintrag.get("gilt", "immer")
    if gilt == "immer":
        return True
    # Ohne Kenntnis des zuständigen Schalters gelten nur die immer-Einträge –
    # sonst würden beide Hälften eines Paares gleichzeitig greifen.
    if gilt in ("schultag", "schulfrei"):
        if schulfrei is None:
            return False
        return (gilt == "schulfrei") == schulfrei
    if gilt in ("werktag", "arbeitsfrei"):
        if feiertag is None:
            return False
        return (gilt == "arbeitsfrei") == feiertag
    return False


def letzter_zeitpunkt(zeitplan: list[dict], jetzt: datetime,
                      schulfrei: bool | None,
                      feiertag: bool | None = None) -> tuple[datetime, dict] | None:
    """Der zuletzt fällig gewordene Umschaltpunkt samt Zeitpunkt.

    Sucht rückwärts über Tagesgrenzen hinweg: Die Nachtabsenkung von gestern
    Abend gilt bis zum ersten Punkt von heute früh. Der Zeitpunkt wird
    gebraucht, um „ist gerade fällig geworden“ von „gilt schon seit gestern“
    zu unterscheiden.
    """
    for versatz in range(8):
        tag = jetzt - timedelta(days=versatz)
        wochentag = TAGE[tag.weekday()]
        kandidaten = [e for e in zeitplan if _passt(e, wochentag, schulfrei, feiertag)]
        if versatz == 0:
            kandidaten = [e for e in kandidaten if _uhrzeit(e["start"]) <= jetzt.time()]
        if kandidaten:
            eintrag = max(kandidaten, key=lambda e: e["start"])
            return datetime.combine(tag.date(), _uhrzeit(eintrag["start"])), eintrag
    return None


def aktueller_eintrag(zeitplan: list[dict], jetzt: datetime,
                      schulfrei: bool | None,
                      feiertag: bool | None = None) -> dict | None:
    """Der zuletzt fällig gewordene Umschaltpunkt."""
    treffer = letzter_zeitpunkt(zeitplan, jetzt, schulfrei, feiertag)
    return treffer[1] if treffer else None


def naechster_wechsel(zeitplan: list[dict], jetzt: datetime,
                      schulfrei: bool | None,
                      feiertag: bool | None = None) -> tuple[datetime, dict] | None:
    """Der nächste anstehende Umschaltpunkt samt Zeitpunkt."""
    for versatz in range(8):
        tag = jetzt + timedelta(days=versatz)
        wochentag = TAGE[tag.weekday()]
        kandidaten = [e for e in zeitplan if _passt(e, wochentag, schulfrei, feiertag)]
        if versatz == 0:
            kandidaten = [e for e in kandidaten if _uhrzeit(e["start"]) > jetzt.time()]
        if kandidaten:
            eintrag = min(kandidaten, key=lambda e: e["start"])
            zeitpunkt = datetime.combine(tag.date(), _uhrzeit(eintrag["start"]))
            return zeitpunkt, eintrag
    return None


def modus_temperatur(raum: dict, modus: str, frostschutz: float) -> float:
    """Die im Raum hinterlegte Temperatur für einen Modus."""
    if modus == "aus":
        return float(frostschutz)
    return float(raum.get(modus, raum.get("eco", 19.0)))


def naechster_waermerer_wechsel(raum: dict, jetzt: datetime, schulfrei: bool | None,
                                aktuelle_temperatur: float,
                                frostschutz: float,
                                feiertag: bool | None = None
                                ) -> tuple[datetime, dict] | None:
    """Der nächste Wechsel, der es wärmer haben will – Ziel des Vorheizens.

    Sucht über mehrere Wechsel hinweg, damit auch ein kurzer Zwischenschritt
    (etwa ``nacht`` → ``eco`` → ``komfort``) das Vorheizen nicht verdeckt.
    """
    zeitplan = raum.get("zeitplan") or []
    if not zeitplan:
        return None
    zeiger = jetzt
    for _ in range(8):
        treffer = naechster_wechsel(zeitplan, zeiger, schulfrei, feiertag)
        if not treffer:
            return None
        zeitpunkt, eintrag = treffer
        ziel = modus_temperatur(raum, eintrag["modus"], frostschutz)
        if ziel > aktuelle_temperatur + 0.1:
            return zeitpunkt, eintrag
        zeiger = zeitpunkt + timedelta(minutes=1)
    return None


# ------------------------------------------------------------- Vorgaben ----

def standardplan(art: str = "wohnraum") -> list[dict]:
    """Ein brauchbarer Plan zum Anfangen, angelehnt an übliche Familienzeiten."""
    werktage = ["mon", "tue", "wed", "thu", "fri"]
    alle = TAGE
    if art == "kinderzimmer":
        return [
            {"start": "06:00", "modus": "komfort", "gilt": "schultag", "tage": werktage},
            {"start": "07:30", "modus": "eco", "gilt": "schultag", "tage": werktage},
            {"start": "13:00", "modus": "komfort", "gilt": "schultag", "tage": werktage},
            {"start": "09:00", "modus": "komfort", "gilt": "schulfrei", "tage": alle},
            {"start": "21:00", "modus": "nacht", "gilt": "immer", "tage": alle},
        ]
    if art == "schlafzimmer":
        return [
            {"start": "06:00", "modus": "komfort", "gilt": "immer", "tage": alle},
            {"start": "09:00", "modus": "eco", "gilt": "immer", "tage": alle},
            {"start": "19:00", "modus": "komfort", "gilt": "immer", "tage": alle},
            {"start": "22:00", "modus": "nacht", "gilt": "immer", "tage": alle},
        ]
    if art == "nebenraum":
        return [
            {"start": "07:00", "modus": "eco", "gilt": "immer", "tage": alle},
            {"start": "21:00", "modus": "nacht", "gilt": "immer", "tage": alle},
        ]
    return [
        {"start": "05:30", "modus": "komfort", "gilt": "schultag", "tage": werktage},
        {"start": "07:30", "modus": "eco", "gilt": "schultag", "tage": werktage},
        {"start": "12:30", "modus": "komfort", "gilt": "schultag", "tage": werktage},
        {"start": "09:00", "modus": "komfort", "gilt": "schulfrei", "tage": alle},
        {"start": "21:00", "modus": "nacht", "gilt": "immer", "tage": alle},
    ]
