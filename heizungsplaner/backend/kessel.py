"""Die Kesselregelung dem Raumbedarf folgen lassen.

Der Planer stellt Thermostatventile – aber ein Ventil kann nur verteilen, was
der Kessel liefert. Läuft dessen Regelung nach eigenem Zeitprogramm, arbeiten
beide gegeneinander: Der Planer heizt morgens vor, während der Kessel noch
absenkt, und abends hält der Kessel Vorlauf bereit, den kein Raum mehr will.

Dieses Modul löst die Doppelung auf. Es führt genau **einen** Parameter der
Regelung – die Programmwahl – und leitet ihn aus dem ab, was der Planer
ohnehin für jeden Raum entschieden hat:

* irgendein Raum auf Komfortniveau  → **Nenn**
* nur Sparwerte, aber Wärmebedarf   → **Reduziert**
* Sommerbetrieb des Planers         → **Sommer**
* kein Raum verlangt Wärme          → **Standby**

Gesprochen wird mit dem Add-on *Heizungsanlagenmanager* über dessen
Übernahme-Schnittstelle. Zwei Dinge macht sie richtig, und daran hält sich
dieses Modul:

* **Ohne Anmeldung ändert sich nichts.** Ab Werk ist hier nichts eingerichtet.
* **Der Mensch davor behält das letzte Wort.** Hebt jemand die Übernahme dort
  auf, meldet sich der Planer *nicht* stillschweigend neu an. Ein Knopf, den
  ein Programm sofort wieder aushebelt, wäre eine Attrappe.

Geschrieben wird auf Flanke, wie überall im Planer: Der zuletzt gestellte Wert
steht im Laufzeitzustand, und solange die Regelung ihn führt, geht kein Befehl
über den Bus. Ein Heizkreis, der alle fünf Minuten dieselbe Betriebsart
zugerufen bekommt, hat nichts davon außer Bustelegrammen.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

import store
import texte

_LOGGER = logging.getLogger(__name__)

QUELLE = "heizungsplaner"

# Vom Anlagenmanager über MQTT angesagt. Nachschlagen kann der Planer die
# Anschrift nicht: Die Add-on-Liste gibt der Supervisor nur mit
# Verwalterrechten heraus, und die braucht ein Heizungsplaner nicht.
_gefunden = ""

# Welcher Raumzustand wie viel Wärme verlangt.
#
# Die Zustandsnamen sind hier mit Bedacht einzeln aufgeführt und nicht über
# den Sollwert erraten: Ein Raum auf 20 °C kann im Komfortbetrieb stehen oder
# per Hand so eingestellt sein, und beides heißt für den Kessel etwas anderes.
#
# Eine Falle steckt in „uebersteuert“: Diesen Zustand vergibt `regelung.py`
# **nur**, wenn eine Übersteuerungsregel auf „aus“ steht. Greift eine Regel
# mit Komfort oder Absenkung, trägt der Raum den Namen des Modus („komfort“,
# „eco“, „nacht“). „uebersteuert“ gehört deshalb zu den geschlossenen Räumen,
# nicht zu den warmen – genau andersherum, als der Name vermuten lässt.
KOMFORT_ZUSTAENDE = frozenset({
    "komfort",     # Zeitplan oder eine Regel verlangt Komfort
    "party",       # Partytaste
    "heimkehr",    # jemand ist auf dem Heimweg, der Raum wird vorgewärmt
    "manuell",     # Handeinstellung: Wir kennen ihren Wert nicht sicher und
                   # gehen auf die sichere Seite – zu wenig Vorlauf ist eine
                   # kalte Wohnung, zu viel nur ein bisschen Öl.
})
SPAR_ZUSTAENDE = frozenset({
    "eco", "nacht",   # geplante Absenkung
    "abwesend",       # niemand da, aber der Raum wird gehalten
    "absenkung",      # „nur absenken“: der planmäßige Eingriff
    "urlaub",         # Urlaubstemperatur – niedrig, aber sie will Vorlauf
})
# Alles Übrige – aus, gesperrt, fenster, sommer, uebersteuert – verlangt
# nichts. Fehlt ein Zustand in beiden Listen, zählt er ebenso als kein Bedarf;
# neu hinzukommende Sonderzustände sind im Planer immer Abschaltungen gewesen.

# Was in der Programmwahl steht, hängt an der Regelung. Erkannt wird über den
# Text der Auswahl, nicht über die Zahl: Die Nummern unterscheiden sich
# zwischen BSB, LPB und PPS, die Bezeichnungen der Siemens-Regler nicht.
WAHL_WORTE = {
    "nenn": ("nenn", "komfort", "comfort", "dauerbetrieb"),
    "reduziert": ("reduziert", "reduced", "spar"),
    "sommer": ("sommer", "summer"),
    "standby": ("standby", "schutz", "frost"),
}


class Abgelehnt(Exception):
    """Der Anlagenmanager hat die Bitte beantwortet – aber mit Nein."""

    def __init__(self, code: int, text: str):
        super().__init__(text)
        self.code = code
        self.text = text


def _json(methode: str, adresse: str, nutzlast: dict | None = None,
          zeit: float = 20.0):
    daten = json.dumps(nutzlast).encode() if nutzlast is not None else None
    req = urllib.request.Request(
        adresse, data=daten, method=methode,
        headers={"Content-Type": "application/json"} if daten else {})
    try:
        with urllib.request.urlopen(req, timeout=zeit) as antwort:
            text = antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        # Der Anlagenmanager begründet jede Ablehnung im Rumpf – 403 „nicht
        # freigegeben“, 409 „führt schon jemand anders“. Diesen Satz wegzuwerfen
        # und nur „HTTP Error 403“ zu melden, hieße den Nutzer raten zu lassen.
        rumpf = fehler.read().decode("utf-8", "replace")
        try:
            grund = (json.loads(rumpf) or {}).get("fehler") or rumpf
        except ValueError:
            grund = rumpf
        raise Abgelehnt(fehler.code, str(grund).strip()) from fehler
    return json.loads(text) if text else {}


def anschrift_merken(adresse: str | None) -> None:
    """Die Anschrift übernehmen, die der Anlagenmanager über MQTT ansagt.

    Er kennt seinen Hostnamen im Docker-Netz selbst; der Planer kann ihn nicht
    nachschlagen, ohne Rechte zu verlangen, die er nicht braucht. Die Nachricht
    liegt „retained“ beim Broker und kommt deshalb auch dann sofort an, wenn
    der Manager gerade nicht läuft.
    """
    global _gefunden
    adresse = (adresse or "").strip().rstrip("/")
    if not adresse.startswith(("http://", "https://")):
        return
    if adresse != _gefunden:
        _LOGGER.info("Heizungsanlagenmanager meldet sich unter %s", adresse)
    _gefunden = adresse


def basis(einstellungen: dict) -> str | None:
    """Die Adresse des Anlagenmanagers – eingetragen oder angesagt."""
    eigene = ((einstellungen.get("kessel") or {}).get("adresse") or "").strip()
    if eigene:
        return eigene.rstrip("/")
    return _gefunden or None


def gewuenschte_wahl(bericht: dict) -> str:
    """Welche Betriebsart die Regelung fahren soll – aus dem Raumbedarf.

    Der Sommerbetrieb des Planers hat Vorrang: Sind die Ventile ohnehin zu,
    muss der Kessel für die Heizung nicht bereitstehen. Das Warmwasser bleibt
    davon unberührt, es hängt an einem eigenen Parameter.
    """
    if bericht.get("sommerbetrieb"):
        return "sommer"

    zustaende = {r.get("zustand") for r in bericht.get("raeume") or []}
    if zustaende & KOMFORT_ZUSTAENDE:
        return "nenn"
    if zustaende & SPAR_ZUSTAENDE:
        return "reduziert"
    # Alle Räume abgeschaltet, gesperrt oder am offenen Fenster. Standby ist
    # nicht „aus“: Der Frostschutz der Regelung bleibt darunter aktiv.
    return "standby"


def wert_zu(wahl: str, auswahl: list[dict]) -> str | None:
    """Den Zahlenwert finden, den diese Regelung für die Betriebsart führt."""
    worte = WAHL_WORTE.get(wahl) or ()
    for eintrag in auswahl or []:
        text = str(eintrag.get("text") or "").strip().lower()
        if any(text.startswith(wort) for wort in worte):
            return str(eintrag.get("wert"))
    return None


def lage(einstellungen: dict) -> dict:
    """Was der Anlagenmanager gerade meldet – und wer die Programmwahl führt."""
    adresse = basis(einstellungen)
    if not adresse:
        return {"erreichbar": False, "fehler": texte.t("kessel_nicht_gefunden")}
    try:
        katalog = _json("GET", f"{adresse}/api/katalog")
        uebernahme = _json("GET", f"{adresse}/api/uebernahme")
    except (Abgelehnt, urllib.error.URLError, OSError, ValueError) as fehler:
        return {"erreichbar": False, "fehler": str(fehler)}

    wahl = katalog.get("programmwahl") or {}
    nr = str(wahl.get("nr") or "")
    fuehrt = (uebernahme.get("parameter") or {}).get(nr)

    # Was in der Regelung *wirklich* steht. Ohne diesen Blick wüsste der
    # Planer nur, dass sein Telegramm angenommen wurde – nicht, ob der Wert
    # danach noch da ist.
    ist = None
    try:
        werte = _json("GET", f"{adresse}/api/werte")
        eintrag = (werte.get("werte") or werte).get(nr) or {}
        if not eintrag.get("error"):
            ist = str(eintrag.get("value"))
    except (Abgelehnt, urllib.error.URLError, OSError, ValueError):
        pass
    return {
        "erreichbar": True,
        "parameter": nr,
        "ist": ist,
        "name": wahl.get("name") or "",
        "auswahl": wahl.get("werte") or [],
        "schreibbar": bool(wahl.get("schreibbar")),
        "uebernommen": bool(fuehrt) and fuehrt.get("quelle") == QUELLE,
        "fremd": (fuehrt or {}).get("name") if fuehrt
                 and fuehrt.get("quelle") != QUELLE else None,
    }


def anmelden(einstellungen: dict, parameter: str) -> bool:
    adresse = basis(einstellungen)
    if not adresse:
        return False
    try:
        _json("PUT", f"{adresse}/api/uebernahme", {
            "quelle": QUELLE,
            "name": "Heizungsplaner",
            "hinweis": texte.t("kessel_hinweis"),
            "parameter": [parameter],
        })
        _LOGGER.info("Programmwahl %s übernommen", parameter)
        return True
    except (Abgelehnt, urllib.error.URLError, OSError, ValueError) as fehler:
        _LOGGER.warning("Übernahme fehlgeschlagen: %s", fehler)
        return False


def abmelden(einstellungen: dict) -> bool:
    """Die Programmwahl zurückgeben – beim Abschalten der Kesselführung.

    Ohne diesen Schritt bliebe der Parameter im Anlagenmanager ausgeblendet,
    obwohl ihn niemand mehr führt: eine Kachel, die für immer verschwunden
    ist, weil ein Schalter woanders umgelegt wurde.
    """
    adresse = basis(einstellungen)
    if not adresse:
        return False
    try:
        _json("DELETE", f"{adresse}/api/uebernahme/{QUELLE}")
        return True
    except (Abgelehnt, urllib.error.URLError, OSError, ValueError) as fehler:
        _LOGGER.warning("Abmelden fehlgeschlagen: %s", fehler)
        return False


# So oft darf ein Wert zurückspringen, bevor der Planer die Führung aufgibt.
# Einmal kann ein Lesefehler sein oder ein Telegramm, das sich mit dem
# Lesezyklus überschnitten hat. Dreimal ist eine Antwort.
VERWORFEN_GRENZE = 3


def _verworfen(merker: dict, wert: str, ist: str | None, einstellungen: dict,
               ergebnis: dict, protokoll):
    """Hat die Regelung den zuletzt gestellten Wert wieder verworfen?

    Ein Telegramm anzunehmen und ein Telegramm zu befolgen sind zweierlei.
    Bei einem Siemens-Albatros-Regler etwa gehört die Betriebsart dem Schalter
    am Gerät: Der Bus darf sie setzen, der Regler stellt Sekunden später seinen
    eigenen Stand wieder her. Wer nur auf Flanke schreibt, merkt davon nichts –
    der zuletzt gestellte Wert steht im Gedächtnis, eine Flanke kommt nie
    wieder, und die Oberfläche behauptet monatelang etwas Falsches.

    Deshalb wird verglichen. Springt der Wert wiederholt zurück, gibt der
    Planer die Führung auf, statt weiter gegen die Anlage anzuschreiben.
    Zurück kommt dann die Lage, sonst ``None`` – dann geht es normal weiter.
    """
    if merker.get("gesetzt") is None or ist is None:
        return None
    if merker["gesetzt"] != wert:
        merker.pop("verworfen", None)   # anderer Bedarf: neuer Versuch
        return None
    if ist == wert:
        merker.pop("verworfen", None)   # sitzt
        return None

    zahl = int(merker.get("verworfen", 0)) + 1
    merker["verworfen"] = zahl
    ergebnis["verworfen"] = zahl
    if zahl < VERWORFEN_GRENZE:
        merker.pop("gesetzt", None)     # noch einmal versuchen
        return None

    # Erst zurückgeben, dann abschalten: Sonst bliebe der Parameter im
    # Anlagenmanager ausgeblendet, weil ihn dort noch jemand zu führen scheint.
    abmelden(einstellungen)
    _abschalten(einstellungen)
    merker.clear()
    protokoll(texte.t("log_alle_raeume"), texte.t("kessel_verworfen"),
              texte.t("kessel_verworfen_warum", ist=ist, soll=wert),
              art="warnung")
    return {"aktiv": False, "erreichbar": True, "verworfen": zahl,
            "hinweis": texte.t("kessel_verworfen_warum", ist=ist, soll=wert)}


def _abschalten(einstellungen: dict) -> None:
    """Die Führung abschalten – und zwar dauerhaft.

    Nur das übergebene Verzeichnis zu ändern reichte nicht: Es stammt aus dem
    laufenden Takt und wird nirgends zurückgeschrieben. Der Planer hätte sich
    beim nächsten Neustart wieder angemeldet und damit genau das getan, was
    er hier gerade unterlässt.
    """
    einstellungen.setdefault("kessel", {})["aktiv"] = False
    try:
        config = store.load_config()
        config["einstellungen"].setdefault("kessel", {})["aktiv"] = False
        store.save_config(config)
    except Exception as fehler:  # noqa: BLE001
        _LOGGER.warning("Kesselführung ließ sich nicht abschalten: %s", fehler)


def fuehren(bericht: dict, einstellungen: dict, state: dict, protokoll) -> dict:
    """Die Regelung nachführen – einmal je Takt, nur auf Flanke.

    Zurück kommt die Lage für Oberfläche und MQTT, auch wenn nichts
    geschrieben wurde: Wer sehen will, was der Planer der Anlage zumutet, soll
    das nicht aus dem Protokoll zusammensuchen müssen.
    """
    kessel = einstellungen.get("kessel") or {}
    merker = state.setdefault("kessel", {})

    if not kessel.get("aktiv"):
        # Gerade ausgeschaltet? Dann die Übernahme zurückgeben, solange wir
        # noch wissen, dass wir sie hatten.
        if merker.pop("angemeldet", False):
            abmelden(einstellungen)
            merker.pop("gesetzt", None)
        return {"aktiv": False}

    stand = lage(einstellungen)
    if not stand["erreichbar"]:
        return {"aktiv": True, "erreichbar": False, "fehler": stand["fehler"]}

    parameter = stand["parameter"]
    if not parameter or not stand["auswahl"]:
        return {"aktiv": True, "erreichbar": True,
                "hinweis": texte.t("kessel_keine_wahl")}
    if stand["fremd"]:
        return {"aktiv": True, "erreichbar": True, "uebernommen": False,
                "hinweis": texte.t("kessel_fremd", quelle=stand["fremd"])}

    # Hat jemand die Übernahme drüben aufgehoben? Dann bleibt sie aufgehoben,
    # bis sie hier wieder eingeschaltet wird. Alles andere machte den Knopf
    # dort zur Attrappe.
    if not stand["uebernommen"]:
        if merker.get("angemeldet"):
            merker["angemeldet"] = False
            merker.pop("gesetzt", None)
            _abschalten(einstellungen)
            protokoll(texte.t("log_alle_raeume"),
                      texte.t("kessel_freigegeben"),
                      texte.t("kessel_freigegeben_warum"), art="warnung")
            return {"aktiv": False, "erreichbar": True, "abgegeben": True}
        if not anmelden(einstellungen, parameter):
            return {"aktiv": True, "erreichbar": True, "uebernommen": False}
    merker["angemeldet"] = True

    stand_ist = stand.get("ist")
    wahl = gewuenschte_wahl(bericht)
    wert = wert_zu(wahl, stand["auswahl"])
    if wert is None:
        return {"aktiv": True, "erreichbar": True, "uebernommen": True,
                "wahl": wahl,
                "hinweis": texte.t("kessel_unbekannt",
                                   wahl=texte.t("kessel_wahl_" + wahl))}

    ergebnis = {"aktiv": True, "erreichbar": True, "uebernommen": True,
                "parameter": parameter, "wahl": wahl, "wert": wert,
                "ist": stand_ist, "anzeige": texte.t("kessel_wahl_" + wahl)}

    # Die Flanke allein genügt nicht. Manche Regelungen nehmen ein Telegramm
    # an, quittieren es sogar – und stellen den eigenen Stand kurz darauf
    # wieder her. Die Betriebsart eines Albatros-Reglers etwa gehört dem
    # Schalter am Gerät, nicht dem Bus. Ohne diesen Vergleich zeigte der
    # Planer monatelang „Nennbetrieb“, während die Anlage ihr eigenes
    # Programm fährt: eine Lüge, die niemandem auffällt.
    verworfen = _verworfen(merker, wert, stand_ist, einstellungen,
                           ergebnis, protokoll)
    if verworfen is not None:
        return verworfen

    if merker.get("gesetzt") == wert:
        return ergebnis                      # steht schon so – kein Telegramm
    if einstellungen.get("trockenlauf"):
        ergebnis["trocken"] = True
        return ergebnis

    try:
        _json("POST", f"{basis(einstellungen)}/api/setzen",
              {"nr": parameter, "wert": wert, "quelle": QUELLE})
    except Abgelehnt as fehler:
        # 403 heißt: Im Anlagenmanager ist das Stellen noch gesperrt. Das ist
        # kein Störfall, sondern ein vergessener Schalter – und der Satz muss
        # sagen, wo er sitzt, sonst sucht man ihn im Planer.
        ergebnis["fehler"] = (texte.t("kessel_gesperrt") if fehler.code == 403
                              else fehler.text)
        _LOGGER.warning("Programmwahl abgelehnt (%s): %s",
                        fehler.code, fehler.text)
        return ergebnis
    except (urllib.error.URLError, OSError, ValueError) as fehler:
        ergebnis["fehler"] = str(fehler)
        _LOGGER.warning("Programmwahl setzen fehlgeschlagen: %s", fehler)
        return ergebnis

    merker["gesetzt"] = wert
    protokoll(texte.t("log_alle_raeume"),
              texte.t("kessel_gestellt", wahl=ergebnis["anzeige"]),
              texte.t("kessel_gestellt_warum", wahl=ergebnis["anzeige"]))
    ergebnis["geschrieben"] = True
    return ergebnis
