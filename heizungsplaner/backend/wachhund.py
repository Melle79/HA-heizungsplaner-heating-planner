"""Überwachung der Thermostate: Wer nicht mehr antwortet, wird gemeldet.

Der Anlass ist ein konkreter Vorfall: Während eines Urlaubs fielen vier
Thermostate wegen leerer Batterien aus, und niemand bemerkte es.

Eine Batteriewarnung allein hilft hier nicht – die zehn SwitchBot-Thermostate
dieses Hauses melden über Matter **gar keinen Ladestand**. Was sie melden, ist
ihr Zustand, und zwar regelmäßig. Bleibt diese Meldung aus, ist das Gerät tot,
gleich aus welchem Grund: leere Batterie, abgezogener Funkstick, Defekt.
Deshalb wacht der Planer über das **Lebenszeichen**, nicht über die Batterie –
und nimmt den Ladestand nur mit, wo es ihn gibt.

Gemeldet wird auf Flanke: einmal beim Auftreten, einmal bei der Behebung. Eine
Warnung, die stündlich erneut aufs Telefon kommt, wird nach dem dritten Mal
weggewischt und beim vierten Mal übersehen.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import ha_api
import texte

_LOGGER = logging.getLogger(__name__)

# Wie eine Störung benannt und wie dringend sie ist.
ARTEN = {
    "fehlt":        ("wach_fehlt", "fehler"),
    "unerreichbar": ("wach_unerreichbar", "fehler"),
    "stumm":        ("wach_stumm", "fehler"),
    "batterie":     ("wach_batterie", "warnung"),
    "verweigert":   ("wach_verweigert", "fehler"),
    "sommerpause":  ("wach_sommerpause", "fehler"),
    "kein_fuehler": ("wach_kein_fuehler", "warnung"),
}

# So oft darf ein Schreibvorgang scheitern, bevor es als Störung gilt.
FEHLSCHLAEGE = 3

# So lange bekommt ein angestupstes Gerät Zeit zu antworten, bevor es als
# ausgefallen gilt. Zwei Takte – der Weckruf und die Antwort brauchen jeweils
# ihren Weg durch Funk und Integration.
WECK_SCHONFRIST = timedelta(minutes=12)

# So lange darf ein Thermostat antworten, ohne eine Raumtemperatur zu liefern.
#
# Dieser Fall fällt durch alle anderen Prüfungen: Das Gerät ist erreichbar, es
# meldet sich regelmäßig, es nimmt Sollwerte an – nur sein Fühler schweigt.
# Für den Planer ist der Raum damit blind: keine Ist-Anzeige, keine
# Fenstererkennung über den Temperatursturz, keine Absenkung nach Messwert.
# Drei Stunden sind großzügig; normalerweise meldet so ein Gerät stündlich.
FUEHLER_FRIST = timedelta(hours=3)

# Älter als das wird ein Batteriestand nicht mehr für bare Münze genommen.
# Manche Geräte melden ihn nur bei Änderung – nach einem Batteriewechsel steht
# dort womöglich tagelang der alte Wert, und eine Warnung darauf wäre falsch.
BATTERIE_HOECHSTALTER_H = 12


def _zeit(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        wert = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return wert if wert.tzinfo else wert.replace(tzinfo=timezone.utc)


def batterien_je_thermostat() -> dict:
    """Thermostat → Batterieanzeige am selben Gerät, sofern es eine gibt.

    Die meisten Thermostate dieses Hauses haben keine. Wo es eine gibt, ist sie
    die frühere Warnung – der ausbleibende Lebenszeichen-Ping kommt erst, wenn
    das Gerät schon steht.
    """
    vorlage = (
        "{%- for c in states.climate if c.attributes.total_member_count is not defined %}"
        "{{ c.entity_id }}|"
        "{% for e in device_entities(device_id(c.entity_id)) %}"
        "{% if e.startswith('sensor.') and state_attr(e, 'device_class') == 'battery' %}"
        "{{ e }}{% endif %}{% endfor %}\n{% endfor -%}")
    zuordnung = {}
    for zeile in ha_api.template(vorlage).splitlines():
        thermostat, _, batterie = zeile.partition("|")
        if thermostat and batterie:
            zuordnung[thermostat.strip()] = batterie.strip()
    return zuordnung


def pruefen(config: dict, states_index: dict, jetzt: datetime,
            einstellungen: dict, batterien: dict,
            thermostat_zustand: dict | None = None,
            sommerbetrieb: bool = False) -> list[dict]:
    """Alle Thermostate der eingerichteten Räume durchsehen.

    ``thermostat_zustand`` ist das Gedächtnis des Planers je Gerät. Daraus
    stammt die Zahl der vergeblichen Schreibvorgänge: Ein Thermostat, das den
    Sollwert wiederholt nicht annimmt, ist so gut wie ausgefallen, auch wenn es
    sich brav meldet.
    """
    # `or {}` wäre hier falsch: Ein leeres Gedächtnis ist gültig – es wird
    # gefüllt. Wer es ersetzt, verwirft den Weckruf-Merker gleich wieder.
    if thermostat_zustand is None:
        thermostat_zustand = {}
    wacht = einstellungen.get("wachhund") or {}
    if not wacht.get("aktiv", True):
        return []

    # Im Sommerbetrieb sind die Ventile zu und die Geräte haben nichts zu
    # berichten. Gemessen am 25.08.2026: reguläre Pausen von bis zu 13 Stunden,
    # ohne dass irgendetwas fehlte. Eine Frist, die im Heizbetrieb sinnvoll
    # ist, erzeugt hier reihenweise Fehlalarme – deshalb gilt sie im Sommer
    # doppelt.
    stumm_ab = timedelta(hours=float(wacht.get("stumm_stunden", 24)))
    if sommerbetrieb:
        stumm_ab *= 2
    schwelle = float(wacht.get("batterie_prozent", 20))
    # Der Planer rechnet in lokaler Zeit ohne Zeitzone, Home Assistant meldet
    # in UTC. `astimezone` liest eine zeitzonenlose Angabe als Ortszeit – ein
    # `replace(tzinfo=utc)` hätte die Uhr um den Zeitzonenversatz verstellt und
    # jedes Gerät zwei Stunden zu früh für tot erklärt.
    jetzt_utc = jetzt.astimezone(timezone.utc)

    stoerungen = []
    for raum in config["raeume"]:
        for entity_id in raum.get("thermostate") or []:
            eintrag = states_index.get(entity_id)
            name = ((eintrag or {}).get("attributes") or {}).get(
                "friendly_name", entity_id)

            if eintrag is None:
                stoerungen.append(_bauen(entity_id, name, raum, "fehlt", ""))
                continue

            if eintrag.get("state") in ("unavailable", "unknown"):
                stoerungen.append(_bauen(entity_id, name, raum, "unerreichbar", ""))
                continue

            gemeldet = _zeit(eintrag.get("last_reported")
                             or eintrag.get("last_updated"))
            if gemeldet and jetzt_utc - gemeldet > stumm_ab:
                # Vor der Meldung wird angeklopft. Ein Thermostat, das lange
                # schweigt, ist meist nicht tot, sondern hatte nichts zu
                # sagen: Im Sommerbetrieb schreibt der Planer nicht mehr, also
                # meldet auch das Gerät nichts. Ein Weckruf unterscheidet
                # beides – genau das, was ein Mensch tut, wenn er den
                # Sollwert kurz verstellt.
                merker = thermostat_zustand.setdefault(entity_id, {})
                geweckt = _zeit(merker.get("geweckt_am"))
                if geweckt and gemeldet > geweckt:
                    merker.pop("geweckt_am", None)   # hat geantwortet
                    geweckt = None
                if geweckt is None:
                    ha_api.auffrischen(entity_id)
                    merker["geweckt_am"] = jetzt_utc.isoformat(timespec="seconds")
                    continue
                if jetzt_utc - geweckt < WECK_SCHONFRIST:
                    continue                          # noch Zeit zu antworten

                stunden = (jetzt_utc - gemeldet).total_seconds() / 3600
                stoerungen.append(_bauen(entity_id, name, raum, "stumm",
                                         texte.t("wach_seit",
                                                 stunden=f"{stunden:.0f}")))
                continue

            # Hat sich gemeldet – ein etwaiger Weckruf ist erledigt.
            thermostat_zustand.get(entity_id, {}).pop("geweckt_am", None)

            # Die Sommerpause eines FRITZ!-Thermostats ist ein Zustand in der
            # FRITZ!Box, nicht in Home Assistant: Das Gerät lehnt jeden
            # Sollwert ab, solange sie läuft, und nichts hier kann sie
            # beenden. Gemeldet wird sie, sobald der Planer wieder heizen
            # will – dann ist der Hinweis eine Handlungsanweisung und keine
            # Nachricht über den Sommer.
            if not sommerbetrieb and (eintrag.get("attributes") or {}).get(
                    "preset_mode") == "summer":
                stoerungen.append(_bauen(entity_id, name, raum, "sommerpause",
                                         texte.t("wach_fritzbox")))
                continue

            # Antwortet, liefert aber keine Raumtemperatur.
            #
            # Nur dort gemeldet, wo der Raum seine Temperatur von den
            # Thermostaten bezieht – hat er einen eigenen Fühler, ist der
            # Messwert des Ventils ohnehin entbehrlich.
            if not (raum.get("raumtemp") or "").strip():
                hat_wert = ha_api.as_float(
                    (eintrag.get("attributes") or {}).get(
                        "current_temperature")) is not None
                merker = thermostat_zustand.setdefault(entity_id, {})
                if hat_wert:
                    merker.pop("ohne_fuehler_seit", None)
                else:
                    seit = _zeit(merker.get("ohne_fuehler_seit"))
                    if seit is None:
                        merker["ohne_fuehler_seit"] = jetzt_utc.isoformat(
                            timespec="seconds")
                    elif jetzt_utc - seit >= FUEHLER_FRIST:
                        stunden = (jetzt_utc - seit).total_seconds() / 3600
                        stoerungen.append(_bauen(
                            entity_id, name, raum, "kein_fuehler",
                            texte.t("wach_seit", stunden=f"{stunden:.0f}")))
                        continue

            fehler = (thermostat_zustand.get(entity_id) or {}).get("schreib_fehler", 0)
            if fehler >= FEHLSCHLAEGE:
                zusatz = texte.t("wach_versuche", anzahl=fehler)
                if (eintrag.get("attributes") or {}).get("preset_mode") == "summer":
                    zusatz += texte.t("wach_sommerpause_zusatz")
                stoerungen.append(_bauen(entity_id, name, raum, "verweigert", zusatz))
                continue

            batterie_id = batterien.get(entity_id)
            batterie = states_index.get(batterie_id) if batterie_id else None
            stand = ha_api.as_float((batterie or {}).get("state"))
            if stand is not None and stand <= schwelle:
                # Wie alt ist die Angabe? Ein Gerät, das seinen Ladestand nur
                # bei Änderung meldet, zeigt nach einem Batteriewechsel weiter
                # den alten Wert – davor zu warnen wäre schlicht falsch.
                gemessen = _zeit((batterie or {}).get("last_reported")
                                 or (batterie or {}).get("last_updated"))
                alter = ((jetzt_utc - gemessen).total_seconds() / 3600
                         if gemessen else None)
                if alter is not None and alter > BATTERIE_HOECHSTALTER_H:
                    _LOGGER.info("Batteriestand von %s ist %.0f Stunden alt "
                                 "(%.0f %%) – keine Warnung", batterie_id, alter, stand)
                else:
                    zusatz = (texte.t("wach_batterie_stand",
                                      prozent=f"{stand:.0f}",
                                      uhrzeit=gemessen.astimezone().strftime("%H:%M"))
                              if gemessen else f"{stand:.0f} %")
                    stoerungen.append(_bauen(entity_id, name, raum, "batterie", zusatz))

    return stoerungen


def _bauen(entity_id: str, name: str, raum: dict, art: str, zusatz: str) -> dict:
    schluessel, schwere = ARTEN[art]
    text = texte.t(schluessel)
    return {
        "entity_id": entity_id,
        "name": name,
        "raum": raum["name"],
        "art": art,
        "schwere": schwere,
        "text": f"{name} ({raum['name']}) {text}" + (f" – {zusatz}" if zusatz else ""),
    }


def vergleichen(neu: list[dict], gemerkt: dict) -> tuple[list[dict], list[dict]]:
    """Was ist neu hinzugekommen, was hat sich erledigt?

    Verglichen wird über Entität **und** Art: Wird aus „schwache Batterie“ ein
    „meldet sich nicht mehr“, ist das eine neue Nachricht wert – das Gerät ist
    inzwischen ganz ausgefallen.
    """
    jetzt = {f"{s['entity_id']}|{s['art']}": s for s in neu}
    vorher = set(gemerkt or {})
    hinzu = [s for schluessel, s in jetzt.items() if schluessel not in vorher]
    weg = [gemerkt[schluessel] for schluessel in vorher if schluessel not in jetzt]
    return hinzu, weg


def als_gedaechtnis(stoerungen: list[dict]) -> dict:
    return {f"{s['entity_id']}|{s['art']}": s for s in stoerungen}


def meldung_bauen(hinzu: list[dict], weg: list[dict]) -> tuple[str, str] | None:
    """Titel und Text für die Benachrichtigung – oder nichts zu melden."""
    if not hinzu and not weg:
        return None
    if hinzu:
        schwer = [s for s in hinzu if s["schwere"] == "fehler"]
        titel = (texte.t("wach_meldung_titel", anzahl=len(schwer),
                         mehrzahl="" if len(schwer) == 1
                         else ("e" if texte.sprache() == "de" else "s"))
                 if schwer else texte.t("wach_meldung_batterie"))
        zeilen = [s["text"] for s in hinzu]
        if weg:
            zeilen.append("")
            zeilen += [texte.t("wach_wieder_zeile", name=s["name"]) for s in weg]
        return titel, "\n".join(zeilen)
    return (texte.t("wach_wieder_titel"),
            "\n".join(s["text"].replace(texte.t(ARTEN[s["art"]][0]),
                                        texte.t("wach_meldet_wieder"))
                      for s in weg))
