"""Heizungsplaner – Dienst, Regeltakt und REST-Schnittstelle.

Der Takt läuft in einem eigenen Faden und rechnet alle paar Minuten alle Räume
durch. Die Oberfläche liest denselben Bericht, den auch MQTT bekommt; es gibt
keine zweite Wahrheit.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, send_from_directory

import einheit
import ha_api
import logbuch
import regelung
import store
import tank
import texte
import uebernahme
import wachhund
from version import VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
_LOGGER = logging.getLogger("heizungsplaner")

FRONTEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "frontend")

app = Flask(__name__, static_folder=None)

_takt_lock = threading.Lock()
_wecker = threading.Event()
_letzter_bericht: dict = {"zeit": None, "raeume": [], "hinweis": "Noch kein Durchlauf"}
_publisher = None


# ----------------------------------------------------------- Zeitzone ----

def _zeitzone_uebernehmen() -> None:
    """Die Zeitzone von Home Assistant übernehmen.

    Ohne das rechnet der Container in UTC – ein Zeitplan mit 21:00 Uhr würde
    im Sommer zwei Stunden zu spät schalten.
    """
    try:
        req = urllib.request.Request(
            "http://supervisor/core/api/config",
            headers={"Authorization": f"Bearer {os.environ.get('SUPERVISOR_TOKEN', '')}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            zone = json.loads(resp.read().decode("utf-8")).get("time_zone")
        if zone:
            os.environ["TZ"] = zone
            time.tzset()
            _LOGGER.info("Zeitzone: %s", zone)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Zeitzone konnte nicht übernommen werden: %s", err)


# --------------------------------------------------------------- Takt ----

def _takt_ausfuehren() -> dict:
    global _letzter_bericht
    with _takt_lock:
        config = store.load_config()
        state = store.load_state()
        try:
            bericht = regelung.takt(config, state, logbuch.eintragen)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Regeltakt fehlgeschlagen")
            bericht = {"zeit": None, "raeume": [], "fehler": str(err)}
        else:
            _stoerungen_melden(bericht.get("stoerungen") or [], state,
                               config["einstellungen"])
            bericht["tank"] = _tank_rechnen(config["einstellungen"], state)
            store.save_state(state)
        bericht["version"] = VERSION
        _letzter_bericht = bericht
    if _publisher is not None:
        try:
            _publisher.publish_status(bericht)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("MQTT-Meldung fehlgeschlagen: %s", err)
    return bericht


def _tank_rechnen(einstellungen: dict, state: dict) -> dict:
    """Der Tankteil ist optional – und darf den Regelbetrieb nie gefährden.

    Deshalb steht er in einer eigenen Funktion mit eigenem Fangnetz: Wenn hier
    etwas schiefgeht, heizt das Haus trotzdem weiter.
    """
    if not (einstellungen.get("tank") or {}).get("aktiv"):
        return {"aktiv": False}
    try:
        bericht = tank.takt(einstellungen, state)
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Tankberechnung fehlgeschlagen")
        return {"aktiv": True, "fehler": str(err)}

    dienste = ((einstellungen.get("tank") or {}).get("melden_an")
               or (einstellungen.get("wachhund") or {}).get("melden_an") or [])
    for titel, text in tank.meldungen(bericht, state):
        logbuch.eintragen("Öltank", titel, text, "",
                          art="fehler" if bericht.get("leck") else "warnung")
        for dienst in dienste:
            ha_api.notify(dienst, titel, text)
    return bericht


def _stoerungen_melden(stoerungen: list, state: dict, einstellungen: dict) -> None:
    """Neue Störungen einmal melden, behobene einmal entwarnen.

    Der Auslöser für diese Funktion: Während eines Urlaubs fielen vier
    Thermostate wegen leerer Batterien aus, ohne dass es jemand mitbekam. Eine
    Meldung, die nur in der Oberfläche steht, hilft in so einem Fall nicht –
    sie muss dorthin, wo man sie auch aus der Ferne sieht.
    """
    gemerkt = state.get("stoerungen") or {}
    hinzu, weg = wachhund.vergleichen(stoerungen, gemerkt)
    state["stoerungen"] = wachhund.als_gedaechtnis(stoerungen)
    if not hinzu and not weg:
        return

    for eintrag in hinzu:
        logbuch.eintragen(eintrag["raum"], "Störung", eintrag["text"],
                          eintrag["entity_id"],
                          art="fehler" if eintrag["schwere"] == "fehler" else "warnung")
    for eintrag in weg:
        logbuch.eintragen(eintrag["raum"], "wieder da",
                          f"{eintrag['name']} meldet sich wieder",
                          eintrag["entity_id"], art="gut")

    meldung = wachhund.meldung_bauen(hinzu, weg)
    if not meldung:
        return
    titel, text = meldung
    dienste = (einstellungen.get("wachhund") or {}).get("melden_an") or []
    if not dienste:
        _LOGGER.warning("Störung, aber kein Meldeweg eingestellt: %s", titel)
        return
    for dienst in dienste:
        ha_api.notify(dienst, titel, text)


def _takt_schleife() -> None:
    while True:
        bericht = _takt_ausfuehren()
        raeume = len(bericht.get("raeume") or [])
        if bericht.get("fehler"):
            _LOGGER.warning("Takt mit Fehler: %s", bericht["fehler"])
        else:
            _LOGGER.info("Takt: %d Räume, außen %s °C%s", raeume,
                         bericht.get("aussen"),
                         " (Trockenlauf)" if bericht.get("trockenlauf") else "")
        pause = int(store.load_config()["einstellungen"].get("takt_sekunden", 300))
        _wecker.wait(timeout=pause)
        _wecker.clear()


def _sofort_rechnen() -> None:
    """Den Regeltakt vorziehen, etwa nach einer Änderung in der Oberfläche."""
    _wecker.set()


# ---------------------------------------------------------------- MQTT ----

def _mqtt_starten() -> None:
    global _publisher
    host = os.environ.get("MQTT_HOST")
    if not host:
        _LOGGER.warning("Kein MQTT – die Statusentitäten fehlen in Home Assistant")
        return
    import mqtt_publisher
    _publisher = mqtt_publisher.Publisher(
        host, int(os.environ.get("MQTT_PORT", 1883)),
        os.environ.get("MQTT_USER"), os.environ.get("MQTT_PASSWORD"))

    def bereit() -> None:
        _discovery_auffrischen()
        if _letzter_bericht.get("zeit"):
            _publisher.publish_status(_letzter_bericht)

    _publisher.on_ready = bereit
    _publisher.on_party = lambda an: _party_setzen(an)
    _publisher.start()


def _discovery_auffrischen() -> None:
    """Entitäten neu anmelden – und die weggefallener Räume abräumen."""
    if _publisher is None or not _publisher.connected.is_set():
        return
    try:
        raeume = store.load_config()["raeume"]
        aktuell = _publisher.raum_schluessel(raeume)
        zustand = store.load_state()
        veraltet = [k for k in (zustand.get("veroeffentlichte_raeume") or [])
                    if k not in aktuell]
        if veraltet:
            _publisher.entferne_raeume(veraltet)
        _publisher.publish_discovery(raeume)
        zustand["veroeffentlichte_raeume"] = aktuell
        store.save_state(zustand)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Discovery fehlgeschlagen: %s", err)


# ------------------------------------------------------------ Oberfläche ----

@app.route("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.route("/<path:datei>")
def statisch(datei: str):
    return send_from_directory(FRONTEND, datei)


# ------------------------------------------------------------------ API ----

@app.route("/api/sprache")
def api_sprache():
    """Welche Sprache und welches Maßsystem führt Home Assistant?

    Die Oberfläche fragt das einmal beim Laden. Ein eigener, winziger Endpunkt
    statt eines Feldes im Status: Die Übersetzung soll stehen, bevor die
    ersten Daten eintreffen – sonst blitzt die deutsche Fassung kurz auf.
    """
    return jsonify({"sprache": texte.sprache(),
                    "einheit": einheit.einheit()})

@app.route("/api/status")
def api_status():
    return jsonify(_letzter_bericht)


@app.route("/api/takt", methods=["POST"])
def api_takt():
    return jsonify(_takt_ausfuehren())


@app.route("/api/config")
def api_config():
    config = store.load_config()
    return jsonify({**config, "version": VERSION})


@app.route("/api/raeume", methods=["GET", "POST"])
def api_raeume():
    if request.method == "GET":
        return jsonify(store.load_config()["raeume"])
    try:
        raum = store.add_raum(request.get_json(force=True) or {})
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    _discovery_auffrischen()
    _sofort_rechnen()
    return jsonify(raum), 201


@app.route("/api/raeume/<raum_id>", methods=["PUT", "DELETE"])
def api_raum(raum_id: str):
    if request.method == "DELETE":
        if not store.delete_raum(raum_id):
            return jsonify({"fehler": texte.t("api_raum_fehlt")}), 404
        zustand = store.load_state()
        zustand["raeume"].pop(raum_id, None)
        store.save_state(zustand)
        _discovery_auffrischen()
        _sofort_rechnen()
        return jsonify({"ok": True})
    try:
        raum = store.update_raum(raum_id, request.get_json(force=True) or {})
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    _discovery_auffrischen()
    _sofort_rechnen()
    return jsonify(raum)


@app.route("/api/einstellungen", methods=["GET", "PUT"])
def api_einstellungen():
    if request.method == "GET":
        return jsonify(store.load_config()["einstellungen"])
    vorher = store.load_config()["einstellungen"].get("aussen_entity")
    try:
        einstellungen = store.update_einstellungen(request.get_json(force=True) or {})
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    if einstellungen.get("aussen_entity") != vorher:
        # Andere Quelle, andere Vorgeschichte: Der geglättete Wert der alten
        # Entität würde sonst noch tagelang nachwirken.
        _anlauf_verwerfen()
    _sofort_rechnen()
    return jsonify(einstellungen)


def _anlauf_verwerfen() -> None:
    """Die gedämpfte Außentemperatur verwerfen – sie läuft neu aus der Historie an."""
    with _takt_lock:
        zustand = store.load_state()
        zustand["aussen_gedaempft"] = None
        store.save_state(zustand)


@app.route("/api/anlauf", methods=["POST"])
def api_anlauf():
    _anlauf_verwerfen()
    logbuch.eintragen("Alle Räume", "Anlauf",
                      "Gedämpfte Außentemperatur zurückgesetzt")
    return jsonify(_takt_ausfuehren())


@app.route("/api/entitaeten")
def api_entitaeten():
    states = ha_api.get_states()
    # Bereiche für beide Domänen in einer Abfrage: Die Oberfläche zeigt die
    # Auswahllisten nach Bereich gruppiert und engt sie auf den Bereich des
    # Raumes ein – dafür braucht auch das Thermostat seinen Bereich.
    bereiche = ha_api.bereiche_je_entitaet(("binary_sensor", "climate"))
    kandidaten = ha_api.sensor_candidates(states, bereiche=bereiche)
    return jsonify({
        "thermostate": ha_api.climate_entities(states, bereiche),
        "personen": ha_api.person_entities(states),
        "meldewege": ha_api.notify_dienste(),
        **kandidaten,
    })


@app.route("/api/uebernahme", methods=["GET", "POST"])
def api_uebernahme():
    """Vorschlag anzeigen (GET) oder übernehmen (POST)."""
    try:
        vorschlag = uebernahme.vorschlag()
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Übernahme fehlgeschlagen")
        return jsonify({"fehler": str(err)}), 500
    if request.method == "GET":
        return jsonify(vorschlag)

    auswahl = (request.get_json(force=True) or {}).get("raeume")
    if isinstance(auswahl, list) and auswahl:
        namen = {str(n) for n in auswahl}
        vorschlag = [r for r in vorschlag if r["name"] in namen]

    config = store.load_config()
    vorhandene = {r["name"] for r in config["raeume"]}
    angelegt = []
    for roh in vorschlag:
        if roh["name"] in vorhandene:
            continue
        roh.pop("_art", None)
        roh.pop("_fuehler_vorschlag", None)
        try:
            angelegt.append(store.validate_raum(roh))
        except store.ValidationError as err:
            _LOGGER.warning("Raum %s übersprungen: %s", roh["name"], err)
    config["raeume"].extend(angelegt)
    store.save_config(config)
    logbuch.eintragen("Alle Räume", "Einrichtung",
                      f"{len(angelegt)} Räume aus Home Assistant übernommen")
    _discovery_auffrischen()
    _sofort_rechnen()
    return jsonify({"angelegt": [r["name"] for r in angelegt]})


@app.route("/api/vorschlag/abweisen", methods=["POST"])
def api_vorschlag_abweisen():
    """Einen Zuordnungsvorschlag dauerhaft verstummen lassen.

    Ohne diesen Weg stünde ein Melder, den man in diesem Raum gar nicht will,
    für immer im Hinweisbalken – und ein Balken, den man wegen Dauerrauschen
    überliest, ist schlechter als keiner.
    """
    entity_id = str((request.get_json(force=True) or {}).get("entity_id") or "").strip()
    if not entity_id:
        return jsonify({"fehler": texte.t("api_keine_entitaet")}), 400
    config = store.load_config()
    liste = set(config["einstellungen"].get("ignorierte_vorschlaege") or [])
    liste.add(entity_id)
    store.update_einstellungen({"ignorierte_vorschlaege": sorted(liste)})
    return jsonify({"ok": True, "abgewiesen": sorted(liste)})


def _party_setzen(an: bool, stunden: float | None = None) -> dict:
    """Die Partytaste drücken oder vorzeitig beenden."""
    with _takt_lock:
        config = store.load_config()
        zustand = store.load_state()
        if an:
            dauer = stunden if stunden else float(
                (config["einstellungen"].get("party") or {}).get("dauer_stunden", 3))
            bis = datetime.now() + timedelta(hours=dauer)
            zustand["party_bis"] = bis.isoformat(timespec="seconds")
            logbuch.eintragen("Alle Räume", "Party an",
                              f"Komfort bis {bis.strftime('%H:%M')} Uhr")
        else:
            if not zustand.get("party_bis"):
                return {"party_bis": None}
            zustand["party_bis"] = None
            logbuch.eintragen("Alle Räume", "Party aus",
                              "Vorzeitig beendet – der Zeitplan führt wieder")
        store.save_state(zustand)
    _sofort_rechnen()
    return {"party_bis": store.load_state().get("party_bis")}


@app.route("/api/party", methods=["POST", "DELETE"])
def api_party():
    if request.method == "DELETE":
        return jsonify(_party_setzen(False))
    daten = request.get_json(silent=True) or {}
    stunden = daten.get("stunden")
    try:
        stunden = float(stunden) if stunden else None
    except (TypeError, ValueError):
        return jsonify({"fehler": texte.t("api_dauer")}), 400
    if stunden is not None and not 0.5 <= stunden <= 24:
        return jsonify({"fehler": "Die Dauer muss zwischen 0,5 und 24 Stunden liegen"}), 400
    return jsonify(_party_setzen(True, stunden))


@app.route("/api/party/raeume", methods=["PUT"])
def api_party_raeume():
    """Festlegen, welche Räume die Partytaste mitnimmt.

    Die Wahrheit steht am Raum – hier wird sie nur für alle auf einmal
    gesetzt, damit man die Auswahl an einer Stelle überblickt.
    """
    gewaehlt = set((request.get_json(force=True) or {}).get("raeume") or [])
    config = store.load_config()
    for raum in config["raeume"]:
        raum["party"] = raum["id"] in gewaehlt
    store.save_config(config)
    _sofort_rechnen()
    return jsonify({"raeume": [r["id"] for r in config["raeume"] if r["party"]]})


# ------------------------------------------------------------------ Tank ----
# Alle drei Wege antworten mit 404, solange der Tankteil nicht eingeschaltet
# ist. So kann die Oberfläche fragen, ohne vorher zu wissen, ob es ihn gibt.

def _tank_einstellungen() -> tuple[dict, dict] | tuple[None, None]:
    """Gibt (alle Einstellungen, Tankblock) zurück – oder zweimal None, wenn aus."""
    einstellungen = store.load_config()["einstellungen"]
    tk = einstellungen.get("tank") or {}
    return (einstellungen, tk) if tk.get("aktiv") else (None, None)


@app.route("/api/tank")
def api_tank():
    einstellungen, _ = _tank_einstellungen()
    if einstellungen is None:
        return jsonify({"aktiv": False}), 404
    state = store.load_state()
    bericht = tank.takt(einstellungen, state)
    store.save_state(state)
    return jsonify(bericht)


@app.route("/api/tank/lieferung", methods=["POST"])
def api_tank_lieferung():
    """Eine Tanklieferung verbuchen – die Zahl vom Lieferschein.

    Sie ist geeicht und damit die genaueste Information, die es über diesen
    Tank je geben wird. Deshalb zieht sie den gerechneten Stand gerade.
    """
    _, tk = _tank_einstellungen()
    if tk is None:
        return jsonify({"fehler": "Der Tankteil ist nicht eingeschaltet"}), 404
    daten = request.get_json(force=True) or {}
    try:
        liter = float(daten.get("liter"))
    except (TypeError, ValueError):
        return jsonify({"fehler": "Bitte eine Liefermenge in Litern angeben"}), 400
    state = store.load_state()
    try:
        eintrag = tank.lieferung_eintragen(
            state, liter, str(daten.get("datum") or "").strip() or None,
            tank.nutzbar_liter(tk))
    except ValueError as err:
        return jsonify({"fehler": str(err)}), 400
    store.save_state(state)
    logbuch.eintragen("Öltank", "Lieferung",
                      f"{eintrag['liter']:.0f} Liter verbucht", "", art="gut")
    _sofort_rechnen()
    return jsonify(eintrag)


@app.route("/api/tank/stand", methods=["PUT"])
def api_tank_stand():
    """Den Stand von Hand setzen – etwa nach einem Blick auf den Zeiger."""
    _, tk = _tank_einstellungen()
    if tk is None:
        return jsonify({"fehler": "Der Tankteil ist nicht eingeschaltet"}), 404
    daten = request.get_json(force=True) or {}
    try:
        liter = float(daten.get("liter"))
    except (TypeError, ValueError):
        return jsonify({"fehler": "Bitte einen Füllstand in Litern angeben"}), 400
    state = store.load_state()
    try:
        stand = tank.stand_setzen(state, liter, tank.nutzbar_liter(tk))
    except ValueError as err:
        return jsonify({"fehler": str(err)}), 400
    store.save_state(state)
    logbuch.eintragen("Öltank", "Stand korrigiert",
                      f"auf {stand:.0f} Liter gesetzt", "", art="info")
    _sofort_rechnen()
    return jsonify({"stand_liter": stand})


@app.route("/api/zustand")
def api_zustand():
    """Der Laufzeitzustand, wie der Planer ihn sich gemerkt hat.

    Für den Fall, dass ein Raum sich anders verhält als erwartet: Hier steht,
    was der Planer zuletzt geschrieben hat, ob er einen Handeingriff vermutet
    und wie oft ein Gerät sich verweigert hat.
    """
    zustand = store.load_state()
    # Der Temperaturverlauf ist für die Diagnose uninteressant und lang.
    schlank = {k: v for k, v in zustand.items() if k != "raeume"}
    schlank["raeume"] = {
        rid: {k: v for k, v in daten.items() if k != "verlauf"}
        for rid, daten in (zustand.get("raeume") or {}).items()
    }
    return jsonify(schlank)


@app.route("/api/thermostate/vergessen", methods=["POST"])
def api_thermostate_vergessen():
    """Das Gedächtnis zu den Thermostaten verwerfen.

    Vermuteter Handeingriff, gezählte Fehlschläge, zuletzt geschriebener Wert –
    alles zurück auf Anfang. Danach stellt der Planer beim nächsten Takt wieder
    frei nach Plan.
    """
    entity_id = (request.get_json(silent=True) or {}).get("entity_id")
    with _takt_lock:
        zustand = store.load_state()
        vorher = len(zustand.get("thermostate") or {})
        if entity_id:
            zustand["thermostate"].pop(entity_id, None)
            betroffen = 1
        else:
            zustand["thermostate"] = {}
            betroffen = vorher
        store.save_state(zustand)
    logbuch.eintragen("Alle Räume", "zurückgesetzt",
                      f"Gedächtnis zu {betroffen} Thermostat(en) verworfen")
    _sofort_rechnen()
    return jsonify({"zurueckgesetzt": betroffen})


@app.route("/api/wachhund/probe", methods=["POST"])
def api_wachhund_probe():
    """Eine Probemeldung über die eingestellten Wege schicken.

    Ob ein Meldeweg trägt, merkt man sonst erst im Ernstfall – und dann ist es
    zu spät. Genau dafür ist diese Überwachung ja gebaut worden.
    """
    dienste = ((store.load_config()["einstellungen"].get("wachhund") or {})
               .get("melden_an") or [])
    if not dienste:
        return jsonify({"fehler": texte.t("api_kein_meldeweg")}), 400
    ergebnis = {}
    for dienst in dienste:
        ergebnis[dienst] = ha_api.notify(
            dienst, "Heizungsplaner: Probemeldung",
            "Wenn diese Nachricht ankommt, funktioniert der Meldeweg. So würde "
            "sich auch ein ausgefallenes Thermostat melden.")
    return jsonify({"gesendet": ergebnis})


@app.route("/api/logbuch", methods=["GET", "DELETE"])
def api_logbuch():
    if request.method == "DELETE":
        logbuch.leeren()
        return jsonify({"ok": True})
    return jsonify(logbuch.lesen(int(request.args.get("grenze", 200))))


@app.route("/api/gesundheit")
def api_gesundheit():
    """Was der Einrichtung im Weg steht – für den Hinweisbalken der Oberfläche."""
    config = store.load_config()
    # Während Home Assistant startet, ist die Entitätenliste unvollständig.
    # Daraus einen Befund zu machen hieße, ein Dutzend Ausfälle zu melden, die
    # keine sind – wie es beim Neustart einmal geschah.
    if not ha_api.ist_bereit():
        return jsonify({"hinweise": [{
            "art": "info",
            "text": texte.t("hin_startet")}],
            "startet": True,
            "mqtt": _publisher is not None and _publisher.connected.is_set()})

    states = ha_api.get_states()
    vorhanden = {s.get("entity_id") for s in states}
    einst = config["einstellungen"]
    hinweise = []

    # Störungen zuerst: Ein ausgefallenes Thermostat wiegt schwerer als eine
    # fehlende Zuordnung.
    for stoerung in (_letzter_bericht.get("stoerungen") or []):
        hinweise.append({"art": "fehler" if stoerung["schwere"] == "fehler"
                         else "warnung", "text": stoerung["text"]})

    if not config["raeume"]:
        hinweise.append({"art": "info",
                         "text": texte.t("hin_keine_raeume")})
    if einst.get("trockenlauf"):
        hinweise.append({"art": "warnung",
                         "text": texte.t("hin_trockenlauf")})
    if not einst.get("automatik"):
        hinweise.append({"art": "warnung", "text": texte.t("hin_automatik_aus")})

    for schluessel, feld in (("aussen_entity", "feld_aussen"),
                             ("urlaub_entity", "feld_urlaub"),
                             ("schulfrei_entity", "feld_schulfrei")):
        entity_id = einst.get(schluessel)
        if entity_id and entity_id not in vorhanden:
            hinweise.append({"art": "fehler",
                             "text": texte.t("hin_entity_fehlt",
                                             feld=texte.t(feld),
                                             entity=entity_id)})

    zustand_je_id = {s.get("entity_id"): s.get("state") for s in states}
    zugeordnete_kontakte = {e for raum in config["raeume"] for e in raum["fenster"]}
    zugeordnete_melder = {e for raum in config["raeume"] for e in raum["praesenz"]}

    belegt: dict[str, str] = {}
    for raum in config["raeume"]:
        # Ein Kontakt, der nichts meldet, gilt nicht als „geschlossen“ – sonst
        # macht ein leerer Knopf den Raum stillschweigend blind.
        for entity_id in raum["fenster"]:
            if zustand_je_id.get(entity_id) not in ("on", "off"):
                hinweise.append({
                    "art": "warnung",
                    "text": texte.t("hin_kontakt_stumm", entity=entity_id,
                                    raum=raum["name"])})
        freigabe = raum.get("freigabe_entity")
        if freigabe and freigabe not in vorhanden:
            hinweise.append({
                "art": "fehler",
                "text": texte.t("hin_freigabe_fehlt", entity=freigabe,
                                raum=raum["name"])})
        stumme_melder = [e for e in raum["praesenz"]
                         if zustand_je_id.get(e) not in ("on", "off")]
        for entity_id in stumme_melder:
            hinweise.append({
                "art": "warnung",
                "text": texte.t("hin_melder_stumm", entity=entity_id,
                                raum=raum["name"])})
        if raum.get("nur_praesenz") and len(stumme_melder) == len(raum["praesenz"]):
            hinweise.append({
                "art": "warnung",
                "text": texte.t("hin_nur_praesenz_stumm", raum=raum["name"])})
        if not raum["thermostate"]:
            hinweise.append({"art": "warnung",
                             "text": texte.t("hin_kein_thermostat",
                                             raum=raum["name"])})
        if not raum["zeitplan"]:
            hinweise.append({"art": "warnung",
                             "text": texte.t("hin_kein_zeitplan",
                                             raum=raum["name"])})
        for entity_id in raum["thermostate"]:
            if entity_id not in vorhanden:
                hinweise.append({"art": "fehler",
                                 "text": texte.t("hin_thermostat_weg",
                                                 entity=entity_id,
                                                 raum=raum["name"])})
            if entity_id in belegt:
                hinweise.append({"art": "fehler",
                                 "text": texte.t("hin_doppelt", entity=entity_id,
                                                 a=belegt[entity_id],
                                                 b=raum["name"])})
            else:
                belegt[entity_id] = raum["name"]

    # Neu nachgerüstete Melder anbieten: Was im Bereich eines Raumes liegt und
    # noch keinem zugeordnet ist, wäre sonst leicht zu übersehen.
    raum_je_name = {raum["name"]: raum for raum in config["raeume"]}
    bereiche = ha_api.bereiche_je_entitaet(("binary_sensor",))
    abgewiesen = set(einst.get("ignorierte_vorschlaege") or [])
    for s in states:
        eid = s.get("entity_id", "")
        if not eid.startswith("binary_sensor.") or eid in abgewiesen:
            continue
        attrs = s.get("attributes") or {}
        name = attrs.get("friendly_name", eid)
        klasse = attrs.get("device_class")
        if klasse in ("motion", "occupancy", "presence"):
            art, feld = "praesenz", "Präsenz-/Bewegungsmelder"
            if eid in zugeordnete_melder:
                continue
        elif ha_api.ist_fensterkontakt(eid, name, klasse):
            art, feld = "fenster", "Fensterkontakte"
            if eid in zugeordnete_kontakte:
                continue
        else:
            continue
        bereich = bereiche.get(eid)
        raum = raum_je_name.get(bereich) if bereich else None
        if raum:
            hinweise.append({
                "art": "vorschlag",
                "text": f"„{name}“ – Bereich „{bereich}“, noch keinem Raum "
                        f"zugeordnet.",
                "raum_id": raum["id"], "entity_id": eid, "feld": art,
                "feldname": feld})

    return jsonify({"hinweise": hinweise, "mqtt": _publisher is not None
                    and _publisher.connected.is_set()})


# ---------------------------------------------------------------- Start ----

def main() -> None:
    _zeitzone_uebernehmen()
    if not ha_api.available():
        _LOGGER.error("Kein SUPERVISOR_TOKEN – der Planer kann nichts stellen")
    _mqtt_starten()
    threading.Thread(target=_takt_schleife, name="regeltakt", daemon=True).start()
    _LOGGER.info("Heizungsplaner %s startet auf Port 8098", VERSION)
    app.run(host="0.0.0.0", port=8098, threaded=True)


if __name__ == "__main__":
    main()
