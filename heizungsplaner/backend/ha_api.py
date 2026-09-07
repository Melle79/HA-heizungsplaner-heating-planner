"""Zugriff auf die Home-Assistant-API über den Supervisor-Proxy.

Alles, was das Add-on über Home Assistant weiß oder an ihm ändert, läuft hier
durch. Zwei Eigenheiten der Heizungssteuerung sind eingebaut:

* ``set_temperature`` scheitert an einem ausgeschalteten Thermostat und reißt
  bei einem Sammelaufruf alle übrigen mit. Deshalb wird **jeder Thermostat
  einzeln** angesprochen und ein Fehler bleibt lokal.
* Ein Thermostat im Modus ``off`` nimmt keinen Sollwert an. Wer heizen will,
  muss ihn vorher auf ``heat`` stellen.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

import einheit
import texte

_LOGGER = logging.getLogger(__name__)

API_BASE = "http://supervisor/core/api"
TIMEOUT = 15


def _token() -> str:
    return os.environ.get("SUPERVISOR_TOKEN", "")


def available() -> bool:
    return bool(_token())


def _request(method: str, path: str, payload: dict | None = None):
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        method=method,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body) if body else None


# ---------------------------------------------------------------- lesen ----

def ist_bereit() -> bool:
    """Läuft Home Assistant, oder startet es gerade?

    Während des Starts liefert `/states` eine wachsende Teilliste. Wer darauf
    rechnet, hält die noch nicht geladenen Geräte für verschwunden – und meldet
    im schlimmsten Fall ein Dutzend Ausfälle, die keine sind.
    """
    if not available():
        return False
    try:
        config = _request("GET", "/config")
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(config, dict):
        return False
    # Die Sprache steht in derselben Antwort – ein eigener Aufruf wäre
    # Verschwendung. Sie ändert sich selten, wird aber bei jedem Takt
    # nachgezogen: Wer sie in Home Assistant umstellt, soll sie nicht erst
    # nach einem Neustart des Add-ons wiederfinden.
    texte.sprache_setzen(config.get("language"))
    einheit.einheit_setzen(
        (config.get("unit_system") or {}).get("temperature"))

    zustand = config.get("state")
    # Ältere Fassungen melden kein `state` – dann wird Bereitschaft angenommen.
    return zustand in (None, "RUNNING")


def get_states() -> list[dict]:
    """Alle Zustände auf einen Schlag – ein Aufruf je Regeltakt."""
    if not available():
        return []
    try:
        states = _request("GET", "/states")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Zustände konnten nicht geladen werden: %s", err)
        return []
    return states if isinstance(states, list) else []


def get_state(entity_id: str) -> dict | None:
    if not available():
        return None
    try:
        data = _request("GET", f"/states/{entity_id}")
        return data if isinstance(data, dict) else None
    except urllib.error.HTTPError as err:
        if err.code != 404:
            _LOGGER.warning("Fehler beim Lesen von %s: %s", entity_id, err)
        return None
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("HA-API nicht erreichbar: %s", err)
        return None


def as_float(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # NaN aussortieren


# -------------------------------------------------------------- schalten ----

def auffrischen(entity_id: str) -> bool:
    """Home Assistant bitten, den Zustand dieser Entität neu zu holen.

    Der harmlose Weckruf: kein Funkbefehl an das Gerät, keine Änderung, nur
    die Aufforderung an die Integration, nachzusehen. Gedacht für den Fall,
    dass ein Thermostat lange schweigt – dann unterscheidet die Antwort ein
    stilles Gerät von einem toten.
    """
    if not available():
        return False
    try:
        _request("POST", "/services/homeassistant/update_entity",
                 {"entity_id": entity_id})
        _LOGGER.info("%s angestupst", entity_id)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Weckruf an %s fehlgeschlagen: %s", entity_id, err)
        return False


def set_hvac_mode(entity_id: str, mode: str) -> bool:
    """Betriebsart setzen (``heat`` / ``off``)."""
    if not available():
        return False
    try:
        _request("POST", "/services/climate/set_hvac_mode",
                 {"entity_id": entity_id, "hvac_mode": mode})
        _LOGGER.info("%s → Betriebsart %s", entity_id, mode)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Betriebsart %s für %s fehlgeschlagen: %s", mode, entity_id, err)
        return False


def set_temperature(entity_id: str, temperature: float) -> bool:
    """Sollwert eines einzelnen Thermostats setzen.

    Ein ausgeschaltetes Thermostat lehnt den Aufruf ab – dann wird es einmal
    auf ``heat`` gestellt und der Sollwert erneut geschickt.
    """
    if not available():
        _LOGGER.warning("Kein SUPERVISOR_TOKEN – %s kann nicht gestellt werden", entity_id)
        return False
    payload = {"entity_id": entity_id, "temperature": round(float(temperature), 1)}
    try:
        _request("POST", "/services/climate/set_temperature", payload)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Sollwert für %s abgelehnt (%s) – versuche einzuschalten", entity_id, err)

    if not set_hvac_mode(entity_id, "heat"):
        return False
    try:
        _request("POST", "/services/climate/set_temperature", payload)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Sollwert %.1f für %s endgültig fehlgeschlagen: %s",
                        temperature, entity_id, err)
        return False


# ------------------------------------------------------------- Auswahlen ----

def climate_entities(states: list[dict] | None = None,
                     bereiche: dict | None = None) -> list[dict]:
    """Alle Thermostate für die Raumkonfiguration in der Oberfläche.

    Gruppen-Helfer (``climate_group_helper``) bleiben außen vor: Der Planer
    stellt jeden Heizkörper einzeln, sonst kämpfen Gruppe und Planer um
    denselben Sollwert.

    Der Bereich kommt mit, damit die Oberfläche die Auswahllisten auf den
    Bereich eines Raumes einengen kann.
    """
    bereiche = bereiche if bereiche is not None else {}
    out = []
    for s in states if states is not None else get_states():
        eid = s.get("entity_id", "")
        if not eid.startswith("climate."):
            continue
        attrs = s.get("attributes", {}) or {}
        out.append({
            "entity_id": eid,
            "name": attrs.get("friendly_name", eid),
            "min_temp": as_float(attrs.get("min_temp")) or 5.0,
            "max_temp": as_float(attrs.get("max_temp")) or 30.0,
            "current_temperature": as_float(attrs.get("current_temperature")),
            "temperature": as_float(attrs.get("temperature")),
            "state": s.get("state"),
            "bereich": bereiche.get(eid, ""),
            "gruppe": bool(attrs.get("total_member_count")),
        })
    out.sort(key=lambda e: e["name"])
    return out


def person_entities(states: list[dict] | None = None) -> list[dict]:
    out = []
    for s in states if states is not None else get_states():
        eid = s.get("entity_id", "")
        if not eid.startswith("person."):
            continue
        attrs = s.get("attributes", {}) or {}
        out.append({
            "entity_id": eid,
            "name": attrs.get("friendly_name", eid),
            "state": s.get("state"),
            # Für die Bedingungen einer Übersteuerung: „an“ heißt zu Hause.
            "zustand": "on" if s.get("state") == "home" else "off",
        })
    out.sort(key=lambda e: e["name"])
    return out


TEMPLATE_API = f"{API_BASE}/template"

# Wörter, an denen ein Fensterkontakt auch ohne Geräteklasse zu erkennen ist.
# „Tür“ steht bewusst nicht darin: Es steckt in Gerätenamen wie „Heizung
# Eingangstür“, deren Nebenmelder (Sommermodus, Tastensperre) sonst alle als
# Kontakt gälten. Türkontakte erkennt die Geräteklasse ``door`` zuverlässig.
FENSTER_WORTE = ("fenster", "window", "kipp")

# Manche Thermostate erkennen ein offenes Fenster selbst – am Temperatursturz
# an ihrem eigenen Fühler – und melden das als eigene Entität. Das ist kein
# Kontakt am Fenster, sondern dasselbe Verfahren wie die Sturzerkennung des
# Planers, nur im Gerät. Solche Melder dürfen die Sturzerkennung deshalb nicht
# verdrängen: Steht das Gerät in der Sommerpause oder ist es abgeschaltet,
# meldet es nie – der Raum wäre stillschweigend ohne Fenstererkennung.
GERAETEEIGENE_WORTE = ("offenes fenster erkannt", "offenes_fenster",
                       "fenster offen erkannt", "window open detected",
                       "open_window", "window_open")

# Was trotz passender Geräteklasse oder passendem Namen keiner ist. Zwei
# Fallgruben aus der Praxis: Die Öffnungszeiten von Tankstellen kommen als
# `device_class: opening`, und die Diagnosemelder eines Rollladens tragen das
# Fenster im Namen, an dem sie hängen.
KEIN_KONTAKT_WORTE = ("status", "blocking", "obstacle", "sun program",
                      "sonnenprogramm", "aufnahme", "update", "verfügbar",
                      "battery", "batterie", "signal", "calibration",
                      "tastensperre", "sommermodus", "urlaubsmodus")


def template(vorlage: str) -> str:
    """Ein Jinja-Template in Home Assistant auswerten lassen.

    Der einzige Weg, aus einem Add-on an die Bereichszuordnung zu kommen: Das
    Geräte- und Entitätenregister gibt es nur über die Websocket-API, die einem
    Add-on nicht offensteht. ``area_name()`` liefert dieselbe Auskunft.
    """
    if not available():
        return ""
    req = urllib.request.Request(
        TEMPLATE_API, method="POST",
        data=json.dumps({"template": vorlage}).encode("utf-8"),
        headers={"Authorization": f"Bearer {_token()}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Template konnte nicht ausgewertet werden: %s", err)
        return ""


_bereich_cache: dict[tuple, tuple[float, dict]] = {}
BEREICH_CACHE_SEKUNDEN = 300


def bereiche_je_entitaet(domains: tuple[str, ...] = ("binary_sensor",),
                         hoechstalter: float = BEREICH_CACHE_SEKUNDEN) -> dict:
    """Entity-ID → Bereichsname für die angegebenen Domänen.

    Kurz zwischengespeichert: Bereiche ändern sich selten, die Oberfläche
    fragt aber alle halbe Minute nach.
    """
    import time

    gespeichert = _bereich_cache.get(domains)
    if gespeichert and time.monotonic() - gespeichert[0] < hoechstalter:
        return gespeichert[1]

    teile = [
        "{%- for s in states." + domain + " %}{{ s.entity_id }}|"
        "{{ area_name(s.entity_id) or '' }}\n{% endfor -%}"
        for domain in domains
    ]
    zuordnung = {}
    for zeile in template("".join(teile)).splitlines():
        entity_id, _, bereich = zeile.partition("|")
        if entity_id and bereich:
            zuordnung[entity_id] = bereich
    if zuordnung or gespeichert is None:
        _bereich_cache[domains] = (time.monotonic(), zuordnung)
    return zuordnung if zuordnung else (gespeichert[1] if gespeichert else {})


def ist_fensterkontakt(entity_id: str, name: str, klasse: str | None) -> bool:
    """Fensterkontakt an Geräteklasse oder Bezeichnung erkennen.

    ``window`` und ``door`` sind eindeutig. ``opening`` ist es nicht – diese
    Klasse tragen auch Öffnungszeiten von Geschäften –, deshalb muss dort der
    Name mitspielen. Ohne Geräteklasse zählt allein der Name; so werden auch
    die „Offenes Fenster erkannt“-Meldungen mancher Thermostate gefunden.

    Ausgeschlossen bleibt, was nach Diagnose klingt: Ein Rolladen bringt
    Melder wie „Rollo Fenster Luna Obstacle Detection“ mit, die das Fenster
    nur im Namen führen, an dem sie hängen.
    """
    if klasse in ("window", "door"):
        return True
    text = f"{entity_id} {name}".lower()
    if any(wort in text for wort in KEIN_KONTAKT_WORTE):
        return False
    return any(wort in text for wort in FENSTER_WORTE)


def ist_geraeteeigene_erkennung(entity_id: str, name: str) -> bool:
    """Meldet hier ein Thermostat seine eigene Fenstererkennung?"""
    text = f"{entity_id} {name}".lower().replace("-", " ")
    return any(wort in text for wort in GERAETEEIGENE_WORTE)


def sensor_candidates(states: list[dict] | None = None,
                      mit_bereichen: bool = True,
                      bereiche: dict | None = None) -> dict:
    """Kandidaten für die Auswahllisten der Oberfläche.

    Die Fensterliste enthält, was nach Geräteklasse oder Namen ein Kontakt ist;
    alles übrige Binäre steht getrennt unter ``sonstige_melder``. Ohne diese
    Trennung stünden in der Auswahl auch Dinge wie Tankstellen-Öffnungszeiten.
    """
    aussen, fenster, sonstige, praesenz, raumtemp, schalter = [], [], [], [], [], []
    # Zählerstände: alles, was monoton wächst oder in Stunden/Minuten zählt.
    # Daraus wählt der Tankteil die Brennerlaufzeit – eine Liste aller
    # numerischen Sensoren wäre in einer gewachsenen Installation unbrauchbar.
    zaehler = []
    # Kalender taugen als Bedingung einer Übersteuerung: „Ferien & Feiertage“
    # ist genau die Entität, die eine Homeoffice-Regel braucht.
    kalender = []
    zustaende = states if states is not None else get_states()
    if bereiche is None:
        bereiche = bereiche_je_entitaet(("binary_sensor",)) if mit_bereichen else {}

    for s in zustaende:
        eid = s.get("entity_id", "")
        attrs = s.get("attributes", {}) or {}
        name = attrs.get("friendly_name", eid)
        domain = eid.split(".", 1)[0]
        klasse = attrs.get("device_class")
        if domain == "weather":
            aussen.append({"entity_id": eid, "name": name,
                           "wert": as_float(attrs.get("temperature"))})
        elif domain == "sensor" and klasse == "temperature":
            eintrag = {"entity_id": eid, "name": name, "wert": as_float(s.get("state"))}
            aussen.append(eintrag)
            raumtemp.append(eintrag)
        elif domain == "sensor" and (
                attrs.get("state_class") in ("total", "total_increasing")
                or str(attrs.get("unit_of_measurement") or "").strip() in ("h", "min")):
            if as_float(s.get("state")) is not None:
                zaehler.append({"entity_id": eid, "name": name,
                                "wert": as_float(s.get("state")),
                                "einheit": attrs.get("unit_of_measurement") or ""})
        elif domain == "binary_sensor":
            eintrag = {"entity_id": eid, "name": name,
                       "bereich": bereiche.get(eid, ""),
                       "zustand": s.get("state")}
            if klasse in ("motion", "occupancy", "presence"):
                praesenz.append(eintrag)
            elif ist_fensterkontakt(eid, name, klasse):
                eintrag["geraeteeigen"] = ist_geraeteeigene_erkennung(eid, name)
                fenster.append(eintrag)
            else:
                sonstige.append(eintrag)
            schalter.append(eintrag)
        elif domain in ("input_boolean", "switch"):
            schalter.append({"entity_id": eid, "name": name,
                             "zustand": s.get("state")})
        elif domain == "calendar":
            kalender.append({"entity_id": eid, "name": name,
                             "zustand": s.get("state")})
    for liste in (aussen, fenster, sonstige, praesenz, raumtemp, schalter,
                  kalender, zaehler):
        liste.sort(key=lambda e: e["name"])
    return {"aussen": aussen, "fenster": fenster, "sonstige_melder": sonstige,
            "praesenz": praesenz, "raumtemp": raumtemp, "schalter": schalter,
            "kalender": kalender, "zaehler": zaehler}


def zone_home(states: list[dict] | None = None) -> tuple[float, float, float] | None:
    """Koordinaten und Radius der Heimzone – Grundlage fürs Vorheizen."""
    for s in states if states is not None else get_states():
        if s.get("entity_id") != "zone.home":
            continue
        attrs = s.get("attributes", {}) or {}
        lat = as_float(attrs.get("latitude"))
        lon = as_float(attrs.get("longitude"))
        radius = as_float(attrs.get("radius")) or 100.0
        if lat is not None and lon is not None:
            return lat, lon, radius
    return None


def historien_mittel(entity_id: str, stunden: float = 48.0) -> float | None:
    """Mittlere Außentemperatur der letzten Stunden aus der HA-Historie.

    Beim allerersten Start hat der Planer keine Vorgeschichte. Ohne sie würde
    die gedämpfte Außentemperatur beim aktuellen Messwert beginnen – an einem
    kühlen Sommertag hieße das: Heizbetrieb, obwohl die Woche davor mild war.
    Die Historie liefert den fehlenden Anlauf.

    Zwei Eigenheiten der Historien-Schnittstelle sind zu beachten: Ohne
    ``end_time`` gibt sie nur einen Tag ab dem Startzeitpunkt zurück, und der
    Zeitstempel muss URL-kodiert sein, sonst antwortet sie mit 400.
    """
    import datetime
    import urllib.parse

    if not entity_id or not available():
        return None
    jetzt = datetime.datetime.now(datetime.timezone.utc)
    seit = urllib.parse.quote((jetzt - datetime.timedelta(hours=stunden)).isoformat())
    bis = urllib.parse.quote(jetzt.isoformat())
    try:
        daten = _request(
            "GET",
            f"/history/period/{seit}?filter_entity_id={entity_id}&end_time={bis}")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Historie für %s nicht lesbar: %s", entity_id, err)
        return None

    werte = []
    for reihe in daten if isinstance(daten, list) else []:
        for punkt in reihe if isinstance(reihe, list) else []:
            attrs = punkt.get("attributes") or {}
            rohwert = (attrs.get("temperature") if entity_id.startswith("weather.")
                       else punkt.get("state"))
            wert = as_float(rohwert)
            if wert is not None:
                werte.append(wert)
    if not werte:
        return None
    mittel = round(sum(werte) / len(werte), 2)
    _LOGGER.info("Außentemperatur der letzten %.0f Stunden: %.1f °C aus %d Werten",
                 stunden, mittel, len(werte))
    return mittel


def notify(dienst: str, titel: str, nachricht: str) -> bool:
    """Eine Benachrichtigung über einen notify-Dienst von Home Assistant senden."""
    if not available() or not dienst:
        return False
    name = dienst.split(".", 1)[-1]
    try:
        _request("POST", f"/services/notify/{name}",
                 {"title": titel, "message": nachricht})
        _LOGGER.info("Benachrichtigung über %s: %s", dienst, titel)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Benachrichtigung über %s fehlgeschlagen: %s", dienst, err)
        return False


def notify_dienste() -> list[dict]:
    """Alle verfügbaren notify-Dienste für die Auswahl in der Oberfläche."""
    if not available():
        return []
    try:
        dienste = _request("GET", "/services")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Dienste konnten nicht geladen werden: %s", err)
        return []
    out = []
    for eintrag in dienste if isinstance(dienste, list) else []:
        if eintrag.get("domain") != "notify":
            continue
        for name in sorted(eintrag.get("services") or {}):
            out.append({"entity_id": f"notify.{name}", "name": f"notify.{name}"})
    return out
