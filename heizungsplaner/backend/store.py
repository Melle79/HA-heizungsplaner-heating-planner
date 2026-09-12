"""Persistenz: Konfiguration (Räume, Zeitpläne, Einstellungen) und Laufzeitzustand.

Zwei Dateien unter ``/data``:

``config.json``  – was der Benutzer eingestellt hat.
``zustand.json`` – was der Planer zuletzt getan hat.

Der Laufzeitzustand **muss** die Platte überleben. Ohne ihn wüsste der Planer
nach einem Neustart nicht mehr, welchen Sollwert er zuletzt geschrieben hat,
und würde bei jedem Start aufs Neue in jedes Thermostat schreiben – genau das
Dauerfeuer, das der Urlaubsplaner sich geleistet hat.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
import einheit
import texte

DATA_DIR = os.environ.get("DATA_DIR", "./data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
STATE_FILE = os.path.join(DATA_DIR, "zustand.json")

_lock = threading.Lock()

TAGE = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MODI = ["komfort", "eco", "nacht", "aus"]
# Zwei Paare, weil nicht jeder im Haus demselben Kalender folgt: Schüler
# richten sich nach den Ferien, Berufstätige nach den Feiertagen.
GELTUNG = ["immer", "schultag", "schulfrei", "werktag", "arbeitsfrei"]

# "plan"         – der Planer führt den Sollwert durchgehend.
# "nur_absenken" – der Raum wird von Hand gestellt; der Planer greift allein zu
#                  den Zeitpunkten des Plans ein und lässt ihn sonst in Ruhe.
BETRIEBSARTEN = ["plan", "nur_absenken"]

# Bedingungen einer Übersteuerung. „an“ deckt on/home/true ab – eine Person
# zählt also als an, solange sie zu Hause ist.
ZUSTAENDE = ["an", "aus"]

_LOGGER = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ValidationError(ValueError):
    """Ungültige Eingabedaten."""


# ── Was eine Temperatur ist ─────────────────────────────────────────────────
#
# Die Vorgaben unten stehen in Celsius. Läuft Home Assistant in Fahrenheit,
# werden sie beim Anlegen umgerechnet – und beim Wechsel des Maßsystems auch
# die bereits gespeicherten Werte (siehe `einheit_angleichen`).
#
# „absolut“ meint eine Temperatur (21 °C → 69,8 °F), „spanne“ eine Differenz
# (1,5 K → 2,7 °F). Wer eine Spanne wie eine Temperatur umrechnet, addiert 32
# auf einen Abstand – und bekommt Unsinn.

TEMPERATURFELDER_EINSTELLUNGEN = {
    ("urlaub_temperatur",): "absolut",
    ("frostschutz",): "absolut",
    ("heizkurve", "basis_aussen"): "absolut",
    ("heizkurve", "max_korrektur"): "spanne",
    ("sommer", "grenze"): "absolut",
    ("sommer", "hysterese"): "spanne",
    ("fenster", "sturz_k"): "spanne",
    # Minuten je Grad Kälte: ein Grad Fahrenheit ist die kleinere Spanne,
    # also braucht es je Grad weniger Vorlauf.
    ("vorheizen", "min_pro_grad"): "je_grad",
}

TEMPERATURFELDER_RAUM = {
    "komfort": "absolut", "eco": "absolut", "nacht": "absolut",
    "abwesend": "absolut", "min": "absolut", "max": "absolut",
}

# Die Steilheit der Heizkurve bleibt, wie sie ist: Kelvin je Kelvin ist
# dasselbe Verhältnis wie Grad Fahrenheit je Grad Fahrenheit.


# --------------------------------------------------------------- Vorgaben ----

STANDARD_EINSTELLUNGEN = {
    "automatik": True,
    "trockenlauf": True,          # sicherer Start: erst rechnen, nicht schalten
    "aussen_entity": "weather.forecast_home",
    "daempfung_stunden": 24.0,    # Zeitkonstante der gedämpften Außentemperatur
    "schulfrei_entity": "input_boolean.wochenende_feiertag",
    # Getrennt vom Schulfrei-Schalter: Wer arbeitet, hat in den Schulferien
    # trotzdem Dienst. Gemeint ist ein Schalter, der "an" ist, wenn gearbeitet
    # wird – Wochenende und Feiertage also "aus". Genau das liefert die
    # Workday-Integration von Home Assistant.
    "arbeitstag_entity": "",
    "urlaub_entity": "input_boolean.urlaub",
    "urlaub_temperatur": 12.0,
    "frostschutz": 8.0,
    "takt_sekunden": 300,
    "manuell_respektieren": True,
    # Melder, die der Planer nicht mehr zur Zuordnung vorschlagen soll.
    "ignorierte_vorschlaege": [],
    # Wer zum Haushalt zählt. **Leer heißt: alle** – so verhält sich der
    # Planer wie bisher, und niemand muss nach einem Update etwas nachtragen.
    #
    # Die Angabe ist trotzdem wichtig: Eine Person ohne Gerätetracker steht in
    # Home Assistant dauerhaft auf "unknown" oder "home" und hielte damit
    # jeden Raum für besetzt. Die Absenkung bei Abwesenheit wäre still tot.
    "haushalt": [],
    "heizkurve": {
        "aktiv": True,
        "basis_aussen": 15.0,     # bei dieser Außentemperatur gilt der Sollwert unverändert
        "steilheit": 0.06,        # Kelvin Aufschlag je Kelvin Außenkälte
        "max_korrektur": 1.5,
    },
    "sommer": {
        "aktiv": True,
        "grenze": 16.0,           # gedämpfte Außentemperatur, ab der nicht mehr geheizt wird
        "hysterese": 1.5,
    },
    "anwesenheit": {
        "aktiv": True,
        "karenz_min": 45,         # so lange muss der Raum leer sein, bevor abgesenkt wird
    },
    "vorheizen": {
        "aktiv": True,
        "grund_min": 30,          # Vorlauf bei milder Witterung
        "min_pro_grad": 2.0,      # zusätzliche Minuten je Grad unter 15 °C
        "max_min": 120,
        "heimkehr_km": 8.0,       # näher als das gilt jemand als möglicherweise heimkehrend
        # … aber nur, wenn die Entfernung auch abnimmt. Ohne diese Prüfung
        # gälte eine Schule im Nachbarort den ganzen Vormittag als Heimweg.
        "heimkehr_annaeherung_km": 0.3,
    },
    "fenster": {
        "aktiv": True,
        "sturz_k": 1.2,           # Temperatursturz in Kelvin …
        "sturz_min": 10,          # … innerhalb dieser Zeitspanne
        "sperre_min": 30,         # so lange bleibt der Raum danach auf Frostschutz
    },
    # Die Partytaste: einmal drücken, und der Plan tritt für ein paar Stunden
    # zurück. Danach läuft alles von selbst weiter – niemand muss daran denken,
    # sie wieder auszuschalten.
    "party": {
        "dauer_stunden": 3.0,
        "modus": "komfort",
    },
    # Öltank: für fast jeden uninteressant, deshalb ab Werk aus. Erst wenn
    # jemand hier "aktiv" setzt, erscheint der Reiter überhaupt.
    "tank": {
        "aktiv": False,
        "inhalt_liter": 3000.0,       # Nenninhalt laut Typenschild
        "max_fuell_prozent": 95,      # so viel darf hinein (Behälterauflage)
        "warnschwelle_liter": 500.0,  # darunter gibt es eine Warnung
        # Peilstab-Angaben, alle freiwillig. Sind Höhe und Liter je Zentimeter
        # bekannt, rechnet der Planer zwischen beidem um – und kennt endlich
        # den Unterschied zwischen "im Tank" und "für den Brenner erreichbar".
        "hoehe_voll_cm": 0.0,         # Anzeige bei vollem Tank; 0 = unbekannt
        "hoehe_min_cm": 0.0,          # darunter saugt der Brenner Luft
        # Was die Anzeige bei leerem Tank zeigt. Bei einem nachgerüsteten
        # Anzeiger ist das selten null: Die Skala passt dann nicht zum Tank,
        # der Faden ist zu lang oder zu kurz abgelängt. Ohne diesen Versatz
        # rechnet jede Umrechnung an der Wirklichkeit vorbei.
        "nullpunkt_cm": 0.0,
        "liter_pro_cm": 0.0,          # 0 = noch nicht eingemessen
        "brenner_entity": "",         # Sensor mit der Brennerlaufzeit in Stunden
        "durchsatz_l_h": 2.4,         # Öldurchsatz der Düse
        "leckage_entity": "",         # Melder im Auffangraum, optional
        "waehrung": "€",              # nur Beschriftung, gerechnet wird ohnehin
        "melden_an": [],              # leer = die Meldewege des Wachhunds
    },
    # Die Kesselregelung: ebenfalls ab Werk aus. Sie greift in ein zweites
    # Add-on und über dieses in die Anlage selbst – so etwas schaltet man
    # bewusst ein oder gar nicht.
    "kessel": {
        "aktiv": False,
        # Der Wochenplan, den der Planer in der Regelung vorgefunden hat.
        # Er steht hier und nicht im Laufzeitzustand, weil er jedes Abschalten
        # und jeden Neustart überleben muss: Er ist der einzige Weg zurück.
        "original": {},
        # Leer heißt: das Add-on unter seinem üblichen Namen im Docker-Netz
        # von Home Assistant. Eintragen muss das nur, wer den
        # Heizungsanlagenmanager woanders betreibt.
        "adresse": "",
    },
    # Ein ausgefallenes Thermostat soll auffallen, ohne dass jemand hinsieht.
    "wachhund": {
        "aktiv": True,
        "stumm_stunden": 24.0,     # so lange darf ein Gerät schweigen
        "batterie_prozent": 20,   # Warnschwelle, wo es eine Anzeige gibt
        "melden_an": ["notify.persistent_notification"],
    },
}

STANDARD_RAUM = {
    "name": "Neuer Raum",
    "aktiv": True,
    "betriebsart": "plan",
    "thermostate": [],
    "personen": [],       # leer = jede Person zählt
    "praesenz": [],
    "fenster": [],
    "raumtemp": "",
    "komfort": 21.0,
    "eco": 19.0,
    "abwesend": 17.0,
    "nacht": 18.0,
    "min": 5.0,
    "max": 26.0,
    "heizkurve": True,
    "anwesenheit": True,
    "nur_praesenz": False,
    "party": True,             # macht dieser Raum bei der Partytaste mit?
    "karenz_min": None,        # None = die globale Karenzzeit gilt
    "freigabe_entity": "",     # leer = der Raum ist immer freigegeben
    "sturz_auch_mit_kontakten": False,
    # Regeln, die den Zeitplan übersteuern, solange ihre Bedingungen alle
    # zutreffen – etwa „Werktag, keine Ferien, Isabel zu Hause“ für ein
    # Wohnzimmer, das sonst vormittags absinken würde.
    # [{"modus": "komfort", "wenn": [{"entity": "…", "zustand": "an"}, …]}]
    "uebersteuerung": [],
    "zeitplan": [],
}


def standard_einstellungen() -> dict:
    """Die Vorgaben in der Einheit, die Home Assistant gerade führt."""
    import copy
    e = copy.deepcopy(STANDARD_EINSTELLUNGEN)
    for pfad, art in TEMPERATURFELDER_EINSTELLUNGEN.items():
        ziel = e
        for teil in pfad[:-1]:
            ziel = ziel[teil]
        ziel[pfad[-1]] = _umrechnen_vorgabe(ziel[pfad[-1]], art)
    return e


def standard_raum() -> dict:
    r = dict(STANDARD_RAUM)
    for feld, art in TEMPERATURFELDER_RAUM.items():
        r[feld] = _umrechnen_vorgabe(r[feld], art)
    return r


def _umrechnen_vorgabe(wert, art):
    # In Fahrenheit auf ganze Grad runden: 70 °F liest sich wie eine bewusste
    # Vorgabe, 69,8 °F wie das Ergebnis einer Umrechnung.
    if art == "absolut":
        gerechnet = einheit.absolut(wert)
        return round(gerechnet) if einheit.ist_fahrenheit() else gerechnet
    if art == "spanne":
        gerechnet = einheit.differenz(wert)
        return round(gerechnet * 2) / 2 if einheit.ist_fahrenheit() else gerechnet
    if art == "je_grad":
        # Minuten je Grad: bei Fahrenheit sind die Grade kleiner.
        return round(float(wert) * 5 / 9, 2) if einheit.ist_fahrenheit() else wert
    return wert


def _leer_config() -> dict:
    return {"einstellungen": standard_einstellungen(), "raeume": [],
            "einheit": einheit.einheit()}


# ------------------------------------------------------------------- I/O ----

def _read(path: str, fallback):
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return fallback


def _write(path: str, data) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _merge(vorgabe: dict, gespeichert: dict) -> dict:
    """Gespeicherte Werte über die Vorgaben legen, verschachtelt.

    Sorgt dafür, dass neue Einstellungen aus einer Add-on-Aktualisierung
    auftauchen, ohne dass die Konfiguration von Hand nachgezogen werden muss.
    """
    out = dict(vorgabe)
    for key, value in (gespeichert or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


# --------------------------------------------------------- Konfiguration ----

def load_config() -> dict:
    with _lock:
        roh = _read(CONFIG_FILE, None)
    if not roh:
        return _leer_config()
    config = {
        "einstellungen": _merge(standard_einstellungen(), roh.get("einstellungen") or {}),
        "raeume": [_merge(standard_raum(), r) for r in (roh.get("raeume") or [])],
        "einheit": roh.get("einheit") or einheit.CELSIUS,
    }
    return einheit_angleichen(config)


def einheit_angleichen(config: dict) -> dict:
    """Gespeicherte Temperaturen an einen Wechsel des Maßsystems anpassen.

    Stellt jemand Home Assistant von Celsius auf Fahrenheit um, stehen in der
    Konfiguration weiterhin die alten Zahlen. Ohne diese Anpassung würde der
    Planer ein Haus auf 21 °F herunterkühlen – die Zahl bliebe dieselbe, ihre
    Bedeutung nicht.

    Umgerechnet wird einmal, danach steht die neue Einheit in der Datei.
    """
    alt = config.get("einheit") or einheit.CELSIUS
    neu = einheit.einheit()
    if alt == neu:
        return config

    _LOGGER.warning("Maßsystem gewechselt: %s → %s, Temperaturen werden "
                    "umgerechnet", alt, neu)
    e = config["einstellungen"]
    for pfad, art in TEMPERATURFELDER_EINSTELLUNGEN.items():
        ziel = e
        for teil in pfad[:-1]:
            ziel = ziel.get(teil) or {}
        if pfad[-1] not in ziel:
            continue
        if art == "je_grad":
            faktor = 5 / 9 if neu == einheit.FAHRENHEIT else 9 / 5
            ziel[pfad[-1]] = round(float(ziel[pfad[-1]]) * faktor, 2)
        else:
            ziel[pfad[-1]] = einheit.umrechnen(ziel[pfad[-1]], alt, neu,
                                               spanne=(art == "spanne"))
    for raum in config["raeume"]:
        for feld, art in TEMPERATURFELDER_RAUM.items():
            if feld in raum:
                raum[feld] = einheit.umrechnen(raum[feld], alt, neu,
                                               spanne=(art == "spanne"))
    config["einheit"] = neu
    save_config(config)
    return config


def save_config(config: dict) -> dict:
    with _lock:
        _write(CONFIG_FILE, config)
    return config


# ------------------------------------------------------------ Validierung ----

def _temp(wert, name: str, min_c: float, max_c: float) -> float:
    """Eine Temperatur prüfen – die Grenzen in Celsius, geprüft in der Einheit
    des Systems. Sonst lehnte der Planer in Fahrenheit jeden brauchbaren Wert
    ab: 70 °F liegt weit außerhalb von „4 bis 30“."""
    return _zahl(wert, name, einheit.absolut(min_c), einheit.absolut(max_c))


def _spanne(wert, name: str, min_k: float, max_k: float) -> float:
    """Eine Differenz prüfen – Kelvin-Grenzen, umgerechnet ohne Nullpunkt."""
    return _zahl(wert, name, einheit.differenz(min_k), einheit.differenz(max_k))


def _zahl(wert, name: str, minimum: float, maximum: float) -> float:
    try:
        f = float(wert)
    except (TypeError, ValueError) as err:
        raise ValidationError(f"{name}: Zahl erwartet") from err
    if not minimum <= f <= maximum:
        raise ValidationError(f"{name}: Wert muss zwischen {minimum} und {maximum} liegen")
    return round(f, 2)


def validate_zeitplan(zeitplan) -> list[dict]:
    if not isinstance(zeitplan, list):
        raise ValidationError("Zeitplan: Liste erwartet")
    out = []
    for eintrag in zeitplan:
        if not isinstance(eintrag, dict):
            raise ValidationError("Zeitplan: ungültiger Eintrag")
        start = str(eintrag.get("start", "")).strip()
        if not _TIME_RE.match(start):
            raise ValidationError(f"Zeitplan: ungültige Uhrzeit {start!r} (erwartet HH:MM)")
        modus = str(eintrag.get("modus", "")).strip()
        if modus not in MODI:
            raise ValidationError(f"Zeitplan: unbekannter Modus {modus!r}")
        gilt = str(eintrag.get("gilt", "immer")).strip() or "immer"
        if gilt not in GELTUNG:
            raise ValidationError(f"Zeitplan: unbekannte Geltung {gilt!r}")
        tage = [t for t in (eintrag.get("tage") or []) if t in TAGE]
        if not tage:
            raise ValidationError("Zeitplan: mindestens ein Wochentag nötig")
        out.append({"start": start, "modus": modus, "gilt": gilt, "tage": tage})
    out.sort(key=lambda e: e["start"])
    return out


def validate_raum(raum: dict, vorhandene_id: str | None = None) -> dict:
    if not isinstance(raum, dict):
        raise ValidationError("Raum: Objekt erwartet")
    name = str(raum.get("name") or "").strip()[:60]
    if not name:
        raise ValidationError(texte.t("fehler_name"))

    thermostate = [str(e).strip() for e in (raum.get("thermostate") or []) if str(e).strip()]
    for eid in thermostate:
        if not eid.startswith("climate."):
            raise ValidationError(texte.t("fehler_kein_thermostat", entity=eid))

    minimum = _temp(raum.get("min", einheit.absolut(5.0)), "Minimum", 4.0, 30.0)
    maximum = _temp(raum.get("max", einheit.absolut(26.0)), "Maximum", 4.0, 35.0)
    if maximum <= minimum:
        raise ValidationError(texte.t("fehler_max_min"))

    temperaturen = {}
    for schluessel, vorgabe_c in (("komfort", 21.0), ("eco", 19.0),
                                  ("abwesend", 17.0), ("nacht", 18.0)):
        temperaturen[schluessel] = _zahl(
            raum.get(schluessel, einheit.absolut(vorgabe_c)),
            schluessel.capitalize(), minimum, maximum)

    betriebsart = str(raum.get("betriebsart") or "plan").strip()
    if betriebsart not in BETRIEBSARTEN:
        raise ValidationError(texte.t("fehler_betriebsart", wert=betriebsart))

    # Übersteuerungen: Reihenfolge = Rangfolge, die erste zutreffende gewinnt.
    # Innerhalb einer Regel müssen **alle** Bedingungen zutreffen.
    uebersteuerung = []
    for eintrag in (raum.get("uebersteuerung") or []):
        if not isinstance(eintrag, dict):
            raise ValidationError("Übersteuerung: Objekt erwartet")
        modus = str(eintrag.get("modus") or "komfort").strip()
        if modus not in MODI:
            raise ValidationError(texte.t("fehler_modus", wert=modus))

        # Die frühere Form kannte nur einen Schalter je Regel.
        rohe = eintrag.get("wenn")
        if rohe is None and eintrag.get("entity"):
            rohe = [{"entity": eintrag["entity"], "zustand": "an"}]

        bedingungen = []
        for bedingung in (rohe or []):
            if not isinstance(bedingung, dict):
                raise ValidationError("Bedingung: Objekt erwartet")
            entity = str(bedingung.get("entity") or "").strip()
            if not entity:
                continue
            zustand = str(bedingung.get("zustand") or "an").strip()
            if zustand not in ZUSTAENDE:
                raise ValidationError(texte.t("fehler_bedingung", wert=zustand))
            bedingungen.append({"entity": entity, "zustand": zustand})
        # Zeitfenster: leer heißt „rund um die Uhr“. Ohne Fenster hielte eine
        # Homeoffice-Regel den Raum auch nachts um drei auf Komfort – die
        # Bedingungen treffen ja weiter zu.
        von = str(eintrag.get("von") or "").strip()
        bis = str(eintrag.get("bis") or "").strip()
        for wert in (von, bis):
            if wert and not _TIME_RE.match(wert):
                raise ValidationError(texte.t("fehler_uhrzeit", wert=wert))
        if bool(von) != bool(bis):
            raise ValidationError(texte.t("fehler_fenster_paar"))
        if von and von == bis:
            raise ValidationError(texte.t("fehler_fenster_gleich"))

        if bedingungen:
            uebersteuerung.append({
                "name": str(eintrag.get("name") or "").strip()[:40],
                "modus": modus, "von": von, "bis": bis, "wenn": bedingungen})

    karenz = raum.get("karenz_min")
    if karenz in (None, "", "null"):
        karenz = None
    else:
        karenz = int(_zahl(karenz, "Karenzzeit des Raumes", 0, 480))

    return {
        "id": vorhandene_id or uuid.uuid4().hex[:8],
        "name": name,
        "aktiv": bool(raum.get("aktiv", True)),
        "betriebsart": betriebsart,
        "thermostate": thermostate,
        "personen": [str(e).strip() for e in (raum.get("personen") or []) if str(e).strip()],
        "praesenz": [str(e).strip() for e in (raum.get("praesenz") or []) if str(e).strip()],
        "fenster": [str(e).strip() for e in (raum.get("fenster") or []) if str(e).strip()],
        "raumtemp": str(raum.get("raumtemp") or "").strip(),
        "min": minimum,
        "max": maximum,
        "heizkurve": bool(raum.get("heizkurve", True)),
        "anwesenheit": bool(raum.get("anwesenheit", True)),
        "nur_praesenz": bool(raum.get("nur_praesenz", False)),
        "party": bool(raum.get("party", True)),
        "karenz_min": karenz,
        "freigabe_entity": str(raum.get("freigabe_entity") or "").strip(),
        "sturz_auch_mit_kontakten": bool(raum.get("sturz_auch_mit_kontakten", False)),
        "uebersteuerung": uebersteuerung,
        "zeitplan": validate_zeitplan(raum.get("zeitplan") or []),
        **temperaturen,
    }


def validate_einstellungen(roh: dict) -> dict:
    """Nur bekannte Felder übernehmen und in vernünftige Grenzen zwingen."""
    e = _merge(standard_einstellungen(), roh or {})
    e["automatik"] = bool(e["automatik"])
    e["trockenlauf"] = bool(e["trockenlauf"])
    e["manuell_respektieren"] = bool(e["manuell_respektieren"])
    e["aussen_entity"] = str(e["aussen_entity"] or "").strip()
    e["schulfrei_entity"] = str(e["schulfrei_entity"] or "").strip()
    e["arbeitstag_entity"] = str(e["arbeitstag_entity"] or "").strip()
    e["urlaub_entity"] = str(e["urlaub_entity"] or "").strip()
    e["urlaub_temperatur"] = _temp(e["urlaub_temperatur"], "Urlaubstemperatur", 5.0, 25.0)
    e["frostschutz"] = _temp(e["frostschutz"], "Frostschutz", 4.0, 15.0)
    e["daempfung_stunden"] = _zahl(e["daempfung_stunden"], "Dämpfung", 0.0, 48.0)
    e["takt_sekunden"] = int(_zahl(e["takt_sekunden"], "Takt", 60, 3600))
    e["haushalt"] = [str(p).strip() for p in (e.get("haushalt") or [])
                     if str(p).strip().startswith("person.")]
    e["ignorierte_vorschlaege"] = sorted({
        str(x).strip() for x in (e.get("ignorierte_vorschlaege") or []) if str(x).strip()})

    k = e["heizkurve"]
    k["aktiv"] = bool(k["aktiv"])
    k["basis_aussen"] = _temp(k["basis_aussen"], "Basis-Außentemperatur", -10.0, 25.0)
    k["steilheit"] = _zahl(k["steilheit"], "Steilheit", 0.0, 0.5)
    k["max_korrektur"] = _spanne(k["max_korrektur"], "Maximale Korrektur", 0.0, 6.0)

    s = e["sommer"]
    s["aktiv"] = bool(s["aktiv"])
    s["grenze"] = _temp(s["grenze"], "Sommergrenze", 5.0, 30.0)
    s["hysterese"] = _spanne(s["hysterese"], "Hysterese", 0.0, 5.0)

    a = e["anwesenheit"]
    a["aktiv"] = bool(a["aktiv"])
    a["karenz_min"] = int(_zahl(a["karenz_min"], "Karenzzeit", 0, 480))

    v = e["vorheizen"]
    v["aktiv"] = bool(v["aktiv"])
    v["grund_min"] = int(_zahl(v["grund_min"], "Grundvorlauf", 0, 240))
    v["min_pro_grad"] = _zahl(v["min_pro_grad"], "Minuten je Grad", 0.0, 15.0)
    v["max_min"] = int(_zahl(v["max_min"], "Maximaler Vorlauf", 0, 360))
    v["heimkehr_km"] = _zahl(v["heimkehr_km"], "Heimkehr-Entfernung", 0.0, 100.0)
    v["heimkehr_annaeherung_km"] = _zahl(
        v["heimkehr_annaeherung_km"], "Mindestannäherung", 0.0, 20.0)

    pa = e["party"]
    pa["dauer_stunden"] = _zahl(pa["dauer_stunden"], "Partydauer", 0.5, 24.0)
    if str(pa.get("modus")) not in MODI:
        pa["modus"] = "komfort"

    w = e["wachhund"]
    w["aktiv"] = bool(w["aktiv"])
    w["stumm_stunden"] = _zahl(w["stumm_stunden"], "Schweigefrist", 0.5, 168.0)
    w["batterie_prozent"] = int(_zahl(w["batterie_prozent"], "Batterieschwelle", 0, 100))
    w["melden_an"] = [str(d).strip() for d in (w.get("melden_an") or []) if str(d).strip()]

    tk = e["tank"]
    tk["aktiv"] = bool(tk["aktiv"])
    tk["inhalt_liter"] = _zahl(tk["inhalt_liter"], "Tankinhalt", 0.0, 100000.0)
    tk["max_fuell_prozent"] = int(_zahl(tk["max_fuell_prozent"], "Füllgrenze", 50, 100))
    tk["warnschwelle_liter"] = _zahl(tk["warnschwelle_liter"], "Warnschwelle", 0.0, 100000.0)
    tk["durchsatz_l_h"] = _zahl(tk["durchsatz_l_h"], "Düsendurchsatz", 0.0, 100.0)
    tk["hoehe_voll_cm"] = _zahl(tk["hoehe_voll_cm"], "Höhe bei vollem Tank", 0.0, 1000.0)
    tk["hoehe_min_cm"] = _zahl(tk["hoehe_min_cm"], "Untergrenze", 0.0, 1000.0)
    tk["liter_pro_cm"] = _zahl(tk["liter_pro_cm"], "Liter je Zentimeter", 0.0, 1000.0)
    tk["nullpunkt_cm"] = _zahl(tk["nullpunkt_cm"], "Nullpunkt", 0.0, 1000.0)
    if tk["hoehe_voll_cm"] and tk["nullpunkt_cm"] >= tk["hoehe_voll_cm"]:
        raise ValidationError("Der Nullpunkt muss unter der Höhe bei vollem Tank liegen")
    if tk["hoehe_voll_cm"] and tk["hoehe_min_cm"] >= tk["hoehe_voll_cm"]:
        raise ValidationError(
            "Die Untergrenze muss unter der Höhe bei vollem Tank liegen")
    tk["brenner_entity"] = str(tk["brenner_entity"] or "").strip()
    tk["leckage_entity"] = str(tk["leckage_entity"] or "").strip()
    tk["waehrung"] = (str(tk["waehrung"] or "").strip() or "€")[:3]
    tk["melden_an"] = [str(d).strip() for d in (tk.get("melden_an") or []) if str(d).strip()]

    k = e["kessel"]
    k["aktiv"] = bool(k["aktiv"])
    # Der gesicherte Plan wird durchgereicht, nicht neu erfunden: Schlüssel
    # sind Parameternummern, Werte die Schaltzeilen der Regelung.
    k["original"] = {str(nr): str(wert)
                     for nr, wert in (k.get("original") or {}).items()
                     if str(nr).strip() and str(wert).strip()}
    adresse = str(k.get("adresse") or "").strip().rstrip("/")
    if adresse and not adresse.startswith(("http://", "https://")):
        raise ValidationError(
            "Die Adresse des Heizungsanlagenmanagers beginnt mit http:// oder https://")
    k["adresse"] = adresse

    f = e["fenster"]
    f["aktiv"] = bool(f["aktiv"])
    f["sturz_k"] = _spanne(f["sturz_k"], "Temperatursturz", 0.2, 10.0)
    f["sturz_min"] = int(_zahl(f["sturz_min"], "Sturz-Zeitfenster", 2, 120))
    f["sperre_min"] = int(_zahl(f["sperre_min"], "Fenstersperre", 1, 240))
    return e


# ------------------------------------------------------------- Raum-CRUD ----

def add_raum(raum: dict) -> dict:
    config = load_config()
    neu = validate_raum(raum)
    config["raeume"].append(neu)
    save_config(config)
    return neu


def update_raum(raum_id: str, raum: dict) -> dict:
    config = load_config()
    for i, vorhanden in enumerate(config["raeume"]):
        if vorhanden.get("id") == raum_id:
            neu = validate_raum(raum, vorhandene_id=raum_id)
            config["raeume"][i] = neu
            save_config(config)
            return neu
    raise ValidationError("Raum nicht gefunden")


def delete_raum(raum_id: str) -> bool:
    config = load_config()
    vorher = len(config["raeume"])
    config["raeume"] = [r for r in config["raeume"] if r.get("id") != raum_id]
    if len(config["raeume"]) == vorher:
        return False
    save_config(config)
    return True


def update_einstellungen(roh: dict) -> dict:
    config = load_config()
    config["einstellungen"] = validate_einstellungen(
        _merge(config["einstellungen"], roh or {}))
    save_config(config)
    return config["einstellungen"]


# -------------------------------------------------------- Laufzeitzustand ----

def load_state() -> dict:
    with _lock:
        state = _read(STATE_FILE, None)
    if not isinstance(state, dict):
        state = {}
    state.setdefault("thermostate", {})   # entity_id -> {soll, gesetzt_am, modus}
    state.setdefault("raeume", {})        # raum_id  -> Laufzeitdaten
    state.setdefault("party_bis", None)
    state.setdefault("veroeffentlichte_raeume", [])
    state.setdefault("aussen_gedaempft", None)
    state.setdefault("sommerbetrieb", False)
    state.setdefault("tank", {})
    return state


def save_state(state: dict) -> None:
    with _lock:
        _write(STATE_FILE, state)
