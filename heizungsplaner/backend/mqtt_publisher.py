"""MQTT Discovery: der Heizungsplaner als Gerät mit Entitäten in Home Assistant.

Feste Entitäten für den Gesamtzustand, dazu je Raum ein Sensor mit Zielwert
und Begründung. Damit lässt sich der Planer im Dashboard anzeigen und in
Automationen verwenden, ohne die Add-on-Oberfläche zu öffnen.
"""
from __future__ import annotations

import json
import logging
import re
import threading

import paho.mqtt.client as mqtt

from version import VERSION
import einheit
import kessel
import texte

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PREFIX = "homeassistant"

# Das Thema, unter dem der Heizungsanlagenmanager seine Anschrift ansagt.
ANLAGE_ANSCHRIFT = "heizungsanlage/anschrift"
BASE_TOPIC = "heizungsplaner"
AVAILABILITY_TOPIC = f"{BASE_TOPIC}/availability"
COMMAND_TOPIC = f"{BASE_TOPIC}/cmd"
PARTY_COMMAND_TOPIC = f"{BASE_TOPIC}/party/set"
DEVICE_ID = "heizungsplaner"

# (component, key, Anzeigename, Icon, Einheit, device_class)
# „TEMPERATUR“ steht für die Einheit des Maßsystems – °C oder °F.
GRUND_ENTITAETEN = [
    ("sensor", "status", "Heizungsplaner Status", "mdi:radiator", None, None),
    # Die Einheit steht als None und wird beim Veröffentlichen gesetzt – sie
    # hängt am Maßsystem von Home Assistant, nicht an dieser Tabelle.
    ("sensor", "aussentemperatur_gedaempft", "Außentemperatur gedämpft",
     "mdi:thermometer-lines", "TEMPERATUR", "temperature"),
    ("binary_sensor", "sommerbetrieb", "Sommerbetrieb", "mdi:sun-thermometer", None, None),
    ("binary_sensor", "trockenlauf", "Trockenlauf", "mdi:test-tube", None, None),
    ("binary_sensor", "stoerung", "Heizung Störung", "mdi:radiator-off", None, "problem"),
    ("sensor", "stoerungen", "Ausgefallene Thermostate", "mdi:alert-circle",
     None, None),
]

# Die Kesselregelung, ebenfalls nur bei eingeschalteter Führung. Ein Sensor
# genügt: Er trägt die Betriebsart als Zustand, alles Weitere als Attribut.
# Eine eigene Störmeldung bekommt er nicht – ein nicht erreichbarer
# Anlagenmanager ist kein Heizungsfehler, und die Kachel sagt es im Klartext.
KESSEL_ENTITAETEN = [
    ("sensor", "kessel", "Kessel Wochenprogramm", "mdi:water-boiler", None, None),
]

# Der Öltank ist optional und bekommt seine Entitäten nur, wenn er
# eingeschaltet ist – sonst stünden in jeder Installation fünf leere Sensoren.
# (component, key, Anzeigename, Icon, Einheit, device_class, state_class)
#
# "tank_verbrauch" ist der wichtigste Eintrag: Ein Zähler, der nur wächst.
# Daraus baut Home Assistant von selbst eine Langzeitstatistik mit Tages-,
# Monats- und Jahreswerten, die den Verlust der Add-on-Daten überlebt.
TANK_ENTITAETEN = [
    ("sensor", "tank_verfuegbar", "Heizöl erreichbar", "mdi:fuel",
     "L", "volume_storage", "measurement"),
    ("sensor", "tank_stand", "Heizöl im Tank", "mdi:barrel",
     "L", "volume_storage", "measurement"),
    ("sensor", "tank_verbrauch", "Heizöl verbraucht", "mdi:fire",
     "L", "volume", "total_increasing"),
    ("sensor", "tank_reichweite", "Heizöl Reichweite", "mdi:calendar-clock",
     "d", "duration", None),
    # Kosten als eigener Zähler: Damit steht die Heizölrechnung neben Strom
    # und Gas in derselben Statistik.
    ("sensor", "tank_kosten", "Heizöl Kosten", "mdi:cash",
     "WAEHRUNG", "monetary", "total_increasing"),
    ("binary_sensor", "tank_leck", "Öltank Leckage", "mdi:water-alert",
     None, "problem", None),
]

# Die Partytaste ist bewusst ein Schalter und kein Knopf: Man will sehen, ob
# sie noch läuft, und sie vorzeitig wieder ausschalten können.
PARTY = ("party", "Partytaste", "mdi:party-popper")


def _slug(text: str) -> str:
    text = (text.lower()
            .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "raum"


class Publisher:
    """MQTT-Verbindung, Discovery und Zustandsmeldungen."""

    # Vorgabe, damit ein Aufruf vor der ersten Discovery nicht auf die Nase
    # fällt. Der wirkliche Wert kommt aus den Tankeinstellungen.
    _waehrung = "€"

    def __init__(self, host: str, port: int, username: str | None, password: str | None):
        self.connected = threading.Event()
        self.on_ready = None
        self.on_command = None
        self.on_party = None
        self._bekannte_raeume: set[str] = set()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                   client_id="heizungsplaner")
        if username:
            self._client.username_pw_set(username, password or "")
        self._client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._host = host
        self._port = port

    def start(self) -> None:
        try:
            self._client.connect_async(self._host, self._port, keepalive=60)
            self._client.loop_start()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("MQTT-Verbindung fehlgeschlagen: %s", err)

    def stop(self) -> None:
        try:
            self._client.publish(AVAILABILITY_TOPIC, "offline", retain=True)
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    def _publish(self, topic: str, payload: str) -> None:
        self._client.publish(topic, payload, qos=1, retain=True)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            _LOGGER.info("Mit MQTT-Broker verbunden")
            client.publish(AVAILABILITY_TOPIC, "online", qos=1, retain=True)
            client.subscribe(COMMAND_TOPIC, qos=1)
            client.subscribe(PARTY_COMMAND_TOPIC, qos=1)
            # Der Heizungsanlagenmanager sagt hier an, unter welchem Namen er
            # im Docker-Netz zu erreichen ist. Die Nachricht ist „retained“:
            # Sie liegt beim Broker und kommt sofort, auch wenn der Manager
            # gerade nicht läuft.
            client.subscribe(ANLAGE_ANSCHRIFT, qos=1)
            self.connected.set()
            if self.on_ready is not None:
                try:
                    self.on_ready()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.error("Fehler nach Verbindungsaufbau: %s", err)
        else:
            _LOGGER.error("MQTT-Verbindung abgelehnt: %s", reason_code)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        _LOGGER.warning("MQTT-Verbindung getrennt (%s)", reason_code)
        self.connected.clear()

    def _on_message(self, client, userdata, msg) -> None:
        if msg.topic == ANLAGE_ANSCHRIFT:
            try:
                daten = json.loads(msg.payload.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                return
            kessel.anschrift_merken(daten.get("adresse"))
            return
        if msg.topic == PARTY_COMMAND_TOPIC:
            if self.on_party is not None:
                try:
                    self.on_party(msg.payload.decode("utf-8").strip().upper() == "ON")
                except Exception as err:  # noqa: BLE001
                    _LOGGER.error("Partytaste: %s", err)
            return
        if msg.topic != COMMAND_TOPIC or self.on_command is None:
            return
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            _LOGGER.warning("Ungültiger Befehl: %s", err)
            return
        try:
            self.on_command(payload)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Befehl konnte nicht ausgeführt werden: %s", err)

    # ---------------------------------------------------------- Discovery ----

    def _device(self) -> dict:
        return {
            "identifiers": [DEVICE_ID],
            "name": "Heizungsplaner",
            "manufacturer": "Heizungsplaner Add-on",
            "model": "Vorausschauende Heizungssteuerung",
            "sw_version": VERSION,
        }

    def raum_schluessel(self, raeume: list[dict] | None) -> list[str]:
        return [f"raum_{_slug(r['name'])}" for r in raeume or []]

    def entferne_raeume(self, schluessel: list[str]) -> None:
        """Entitäten weggefallener oder umbenannter Räume aus HA nehmen.

        Ohne das bliebe nach jedem Umbenennen ein Geisterraum stehen: Die
        Discovery-Nachricht ist „retained“, also überlebt sie das Add-on und
        wird beim nächsten Start von Home Assistant wieder eingelesen.
        """
        for key in schluessel:
            self._publish(f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{key}/config", "")
            self._publish(f"{BASE_TOPIC}/{key}/state", "")
            self._publish(f"{BASE_TOPIC}/{key}/attributes", "")
            self._bekannte_raeume.discard(key)
        if schluessel:
            _LOGGER.info("Entfernt: %s", ", ".join(schluessel))

    def publish_discovery(self, raeume: list[dict] | None = None,
                          tank_aktiv: bool = False,
                          waehrung: str = "€",
                          kessel_aktiv: bool = False) -> None:
        device = self._device()
        self._waehrung = waehrung or "€"
        for component, key, name, icon, mass, klasse in KESSEL_ENTITAETEN:
            pfad = f"{DISCOVERY_PREFIX}/{component}/{DEVICE_ID}/{key}/config"
            if not kessel_aktiv:
                self._publish(pfad, "")      # "retained" – muss weg, nicht leer
                continue
            self._publish(pfad, json.dumps({
                "name": name,
                "unique_id": f"{DEVICE_ID}_{key}",
                "default_entity_id": f"{component}.{DEVICE_ID}_{key}",
                "state_topic": f"{BASE_TOPIC}/{key}/state",
                "json_attributes_topic": f"{BASE_TOPIC}/{key}/attributes",
                "availability_topic": AVAILABILITY_TOPIC,
                "icon": icon,
                "device": device,
            }, ensure_ascii=False))
        for component, key, name, icon, mass, klasse, verlauf in TANK_ENTITAETEN:
            pfad = f"{DISCOVERY_PREFIX}/{component}/{DEVICE_ID}/{key}/config"
            if not tank_aktiv:
                # Abgeschaltet: die Anmeldung zurücknehmen. Sie ist "retained"
                # und bliebe sonst für immer stehen.
                self._publish(pfad, "")
                continue
            payload = {
                "name": name,
                "unique_id": f"{DEVICE_ID}_{key}",
                "default_entity_id": f"{component}.{DEVICE_ID}_{key}",
                "state_topic": f"{BASE_TOPIC}/{key}/state",
                "json_attributes_topic": f"{BASE_TOPIC}/{key}/attributes",
                "availability_topic": AVAILABILITY_TOPIC,
                "icon": icon,
                "device": device,
            }
            if mass:
                # „WAEHRUNG“ steht für das Zeichen aus den Tankeinstellungen.
                payload["unit_of_measurement"] = (
                    self._waehrung if mass == "WAEHRUNG" else mass)
            if klasse:
                payload["device_class"] = klasse
            if verlauf:
                payload["state_class"] = verlauf
            self._publish(pfad, json.dumps(payload))
        for component, key, name, icon, mass, klasse in GRUND_ENTITAETEN:
            payload = {
                "name": name,
                "unique_id": f"{DEVICE_ID}_{key}",
                "default_entity_id": f"{component}.{DEVICE_ID}_{key}",
                "state_topic": f"{BASE_TOPIC}/{key}/state",
                "json_attributes_topic": f"{BASE_TOPIC}/{key}/attributes",
                "availability_topic": AVAILABILITY_TOPIC,
                "icon": icon,
                "device": device,
            }
            if mass:
                # „TEMPERATUR“ steht für das Maßsystem von Home Assistant.
                payload["unit_of_measurement"] = (
                    einheit.einheit() if mass == "TEMPERATUR" else mass)
            if klasse:
                payload["device_class"] = klasse
            self._publish(f"{DISCOVERY_PREFIX}/{component}/{DEVICE_ID}/{key}/config",
                          json.dumps(payload))

        key, name, icon = PARTY
        self._publish(f"{DISCOVERY_PREFIX}/switch/{DEVICE_ID}/{key}/config",
                      json.dumps({
                          "name": name,
                          "unique_id": f"{DEVICE_ID}_{key}",
                          "default_entity_id": f"switch.{DEVICE_ID}_{key}",
                          "state_topic": f"{BASE_TOPIC}/{key}/state",
                          "command_topic": PARTY_COMMAND_TOPIC,
                          "json_attributes_topic": f"{BASE_TOPIC}/{key}/attributes",
                          "availability_topic": AVAILABILITY_TOPIC,
                          "icon": icon,
                          "device": device,
                      }))

        for raum in raeume or []:
            key = f"raum_{_slug(raum['name'])}"
            self._bekannte_raeume.add(key)
            payload = {
                "name": f"Heizung {raum['name']}",
                "unique_id": f"{DEVICE_ID}_{key}",
                "default_entity_id": f"sensor.{DEVICE_ID}_{key}",
                "state_topic": f"{BASE_TOPIC}/{key}/state",
                "json_attributes_topic": f"{BASE_TOPIC}/{key}/attributes",
                "availability_topic": AVAILABILITY_TOPIC,
                "unit_of_measurement": einheit.einheit(),
                "device_class": "temperature",
                "icon": "mdi:radiator",
                "device": device,
            }
            self._publish(f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{key}/config",
                          json.dumps(payload))
        _LOGGER.info("Discovery veröffentlicht (%d Räume)", len(raeume or []))

    # ------------------------------------------------------------ Zustand ----

    def publish_status(self, bericht: dict) -> None:
        """Den Bericht eines Regeltakts nach MQTT spiegeln."""
        if not self.connected.is_set():
            return
        raeume = bericht.get("raeume") or []
        aktive = [r for r in raeume if r["zustand"] not in ("aus", "sommer")]
        if bericht.get("trockenlauf"):
            status = texte.t("mq_trockenlauf")
        elif not bericht.get("automatik"):
            status = texte.t("mq_automatik_aus")
        elif bericht.get("sommerbetrieb"):
            status = texte.t("mq_sommer")
        elif bericht.get("urlaub"):
            status = texte.t("mq_urlaub")
        else:
            status = texte.t("mq_aktiv", aktive=len(aktive), gesamt=len(raeume))

        self._zustand("status", status, {
            "zeit": bericht.get("zeit"),
            "automatik": bericht.get("automatik"),
            "trockenlauf": bericht.get("trockenlauf"),
            "urlaub": bericht.get("urlaub"),
            "schulfrei": bericht.get("schulfrei"),
            "aussentemperatur": bericht.get("aussen"),
            "raeume": {r["name"]: r["zustand"] for r in raeume},
        })
        gedaempft = bericht.get("aussen_gedaempft")
        self._zustand("aussentemperatur_gedaempft",
                      f"{gedaempft:.1f}" if gedaempft is not None else "unknown",
                      {"roh": bericht.get("aussen")})
        self._zustand("sommerbetrieb", "ON" if bericht.get("sommerbetrieb") else "OFF", {})
        self._zustand("trockenlauf", "ON" if bericht.get("trockenlauf") else "OFF", {})

        # Damit sich eigene Automationen daran hängen können – eine Durchsage
        # über die Lautsprecher etwa.
        stoerungen = bericht.get("stoerungen") or []
        schwer = [s for s in stoerungen if s.get("schwere") == "fehler"]
        leicht = [s for s in stoerungen if s.get("schwere") != "fehler"]
        # Getrennt nach Schwere, damit das Dashboard Ausfälle und bloße
        # Hinweise unterschiedlich darstellen kann.
        self._zustand("stoerung", "ON" if stoerungen else "OFF",
                      {"anzahl": len(stoerungen), "ausgefallen": len(schwer),
                       "warnungen_anzahl": len(leicht),
                       "meldungen": [s["text"] for s in stoerungen],
                       "fehler": [s["text"] for s in schwer],
                       "warnungen": [s["text"] for s in leicht]})
        self._zustand("stoerungen", str(len(schwer)),
                      {"geraete": [s["entity_id"] for s in schwer],
                       "meldungen": [s["text"] for s in stoerungen]})

        bis = bericht.get("party_bis")
        rest, uhrzeit = 0, None
        if bis:
            from datetime import datetime
            try:
                ende = datetime.fromisoformat(bis)
                rest = max(0, int((ende - datetime.now()).total_seconds() // 60))
                # Die Uhrzeit fertig mitliefern: In Lovelace-Templates gibt es
                # kein `strftime`, und die Zeitrechnerei dort ist eine
                # Fehlerquelle, die im Zweifel die ganze Karte lahmlegt.
                uhrzeit = ende.strftime("%H:%M")
            except ValueError:
                pass
        # Fertiger Anzeigetext für die Kachel: Dass die Taste an ist, sieht man
        # am Schalter – interessant ist, wie lange noch.
        if bis and rest > 0:
            dauer = (f"{rest // 60} h {rest % 60:02d} min" if rest >= 60
                     else f"{rest} min")
            anzeige = f"noch {dauer}, bis {uhrzeit} Uhr"
        else:
            anzeige = "aus"
        self._zustand("party", "ON" if bis else "OFF",
                      {"laeuft_bis": bis, "bis_uhrzeit": uhrzeit,
                       "restminuten": rest, "anzeige": anzeige,
                       "raeume": [r["name"] for r in raeume
                                  if r["zustand"] == "party"]})

        for raum in raeume:
            key = f"raum_{_slug(raum['name'])}"
            self._zustand(key, f"{raum['ziel']:.1f}", {
                "zustand": raum["zustand"],
                "begruendung": raum["begruendung"],
                # Für Dashboard-Karten: greift eine Übersteuerungsregel, und
                # wenn nicht, warum. Ohne das müsste eine Karte die Begründung
                # nach Stichworten durchsuchen.
                "uebersteuerung": (raum.get("uebersteuerung") or {}).get("name", ""),
                "uebersteuerung_greift": (raum.get("uebersteuerung") or {}).get("greift", False),
                "uebersteuerung_lage": (raum.get("uebersteuerung") or {}).get("lage", ""),
                "uebersteuerung_bis": (raum.get("uebersteuerung") or {}).get("bis", ""),
                "ist_temperatur": raum.get("ist"),
                "seit": raum.get("seit"),
                "naechster_wechsel": raum.get("naechster_wechsel"),
                "naechste_uhrzeit": raum.get("naechste_uhrzeit"),
                "naechster_modus": raum.get("naechster_modus"),
                "naechstes_ziel": raum.get("naechstes_ziel"),
                "thermostate": [t["entity_id"] for t in raum.get("thermostate", [])],
            })

        self._tank_zustand(bericht.get("tank") or {})
        self._kessel_zustand(bericht.get("kessel") or {})

    def _kessel_zustand(self, kessel: dict) -> None:
        """Was die Regelung gerade fährt – als Satz, nicht als Schaltzeile.

        Auf der Kachel soll „Komfort bis 22:00 Uhr“ stehen, nicht
        „05:30-08:00 17:00-22:00 ##:##-##:##“. Der geschriebene Wochentag
        bleibt als Attribut daneben, für den Fall, dass jemand nachsehen will,
        was der Planer der Anlage geschickt hat.
        """
        if not kessel.get("aktiv"):
            return
        if not kessel.get("erreichbar", True):
            zustand = "nicht erreichbar"
        elif kessel.get("hinweis"):
            zustand = "wartet"
        else:
            zustand = kessel.get("anzeige") or "unknown"
        self._zustand("kessel", zustand, {
            "programm": kessel.get("programm"),
            "heute": kessel.get("heute"),
            "erweitert": bool(kessel.get("erweitert")),
            "uebernommen": bool(kessel.get("uebernommen")),
            "gestellt": kessel.get("geschrieben") or [],
            "hinweis": kessel.get("hinweis") or kessel.get("fehler") or "",
        })

    def _tank_zustand(self, tank: dict) -> None:
        """Die Tankwerte nach MQTT spiegeln – nur wenn es den Tank gibt."""
        if not tank.get("aktiv") or tank.get("fehler"):
            return

        def zahl(wert):
            # Kein Wert heißt "None" – so schreibt es die MQTT-Anbindung von
            # Home Assistant vor, und daraus wird dort der Zustand "unknown".
            #
            # Nicht etwa das Wort "unknown" senden: Das ist für einen Sensor
            # mit Geräteklasse keine gültige Zahl, und die Entität landet
            # daraufhin auf "unavailable" statt auf "unbekannt".
            #
            # Eine erfundene Null wäre ohnehin falsch: Ein Tank ohne bekannten
            # Stand ist nicht leer, und die Null stünde als echter Messwert in
            # der Langzeitstatistik.
            return "None" if wert is None else str(wert)

        gemeinsam = {"saison": tank.get("saison"),
                     "eingemessen": tank.get("eingemessen")}
        self._zustand("tank_verfuegbar", zahl(tank.get("verfuegbar_liter")), {
            **gemeinsam,
            "im_tank_liter": tank.get("stand_liter"),
            "stand_cm": tank.get("stand_cm"),
            "unter_dem_saugfuss_liter": tank.get("reserve_liter"),
            "unter_grenze": tank.get("unter_grenze"),
            "warnung": tank.get("warnung"),
        })
        self._zustand("tank_stand", zahl(tank.get("stand_liter")), {
            **gemeinsam,
            "stand_cm": tank.get("stand_cm"),
            "prozent": tank.get("prozent"),
            "liter_pro_cm": tank.get("liter_pro_cm"),
        })
        self._zustand("tank_verbrauch", zahl(tank.get("gesamt_liter")), {
            **gemeinsam,
            "heute_liter": tank.get("verbrauch_heute"),
            "monat_liter": tank.get("verbrauch_monat"),
            "heizperiode_liter": tank.get("verbrauch_saison"),
        })
        self._zustand("tank_reichweite", zahl(tank.get("reichweite_tage")), gemeinsam)
        self._zustand("tank_kosten", zahl(tank.get("kosten_gesamt")), {
            **gemeinsam,
            "preis_pro_liter": tank.get("preis_pro_liter"),
            "wert_im_tank": tank.get("wert_im_tank"),
            "monat": tank.get("kosten_monat"),
            "heizperiode": tank.get("kosten_saison"),
        })
        self._zustand("tank_leck", "ON" if tank.get("leck") else "OFF",
                      {**gemeinsam, "seit": tank.get("leck_seit"),
                       "ueberwacht": tank.get("leckage_ueberwacht")})

    def _zustand(self, key: str, state: str, attributes: dict) -> None:
        self._publish(f"{BASE_TOPIC}/{key}/state", state)
        self._publish(f"{BASE_TOPIC}/{key}/attributes",
                      json.dumps(attributes, ensure_ascii=False))

    def remove_all(self) -> None:
        """Alle Entitäten wieder aus Home Assistant entfernen."""
        for component, key, *_ in GRUND_ENTITAETEN + [("switch",) + PARTY[:1]]:
            self._publish(f"{DISCOVERY_PREFIX}/{component}/{DEVICE_ID}/{key}/config", "")
            self._publish(f"{BASE_TOPIC}/{key}/state", "")
        for key in self._bekannte_raeume:
            self._publish(f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{key}/config", "")
            self._publish(f"{BASE_TOPIC}/{key}/state", "")
        _LOGGER.info("Entitäten aus MQTT entfernt")
