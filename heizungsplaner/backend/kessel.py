"""Die Heizungsregelung dem Plan des Hauses folgen lassen.

Der Planer stellt Thermostatventile – aber ein Ventil kann nur verteilen, was
der Kessel liefert. Läuft dessen Regelung nach eigenem Wochenprogramm,
arbeiten beide gegeneinander: Der Planer heizt morgens um halb sechs vor,
während die Regelung noch absenkt, und abends um zehn hält sie Vorlauf
bereit, den kein Raum mehr will. Man merkt das nicht am Thermometer, sondern
am Ölverbrauch.

Dieses Modul löst die Doppelung auf – und zwar über die **Schaltzeiten**,
nicht über die Betriebsart. Das hat einen handfesten Grund: Die Betriebsart
eines Siemens-Albatros-Reglers gehört dem Schalter am Gerät. Sie lässt sich
über den Bus setzen, der Regler quittiert das sogar – und stellt Minuten
später seinen eigenen Stand wieder her. Schaltzeiten dagegen bleiben stehen.

Der Planer schreibt also das Wochenprogramm, das die Regelung ohnehin fährt.
Darin schaltet sie zwischen **Komfort-** und **Reduziertsollwert** um, nicht
zwischen ein und aus; außerhalb der Phasen heizt sie weiter, nur schwächer.
Das ist genau die Unterscheidung, die der Planer für jeden Raum trifft. Die
Vereinigung aller Komfortzeiten – die Hüllkurve, gerechnet in
``huellkurve.py`` – ist das, was hineingeschrieben wird.

Weil der Planer seinen Plan im Voraus kennt, entsteht dabei **kein Versatz**:
Die Regelung schaltet auf die Minute mit ihm. Nur was kein Zeitplan
vorhersieht – die Partytaste, eine greifende Übersteuerungsregel – wird
nachgetragen, und dort kann es eine Taktlänge dauern.

Gesprochen wird mit dem Add-on *Heizungsanlagenmanager* über dessen
Übernahme-Schnittstelle. Drei Dinge macht dieses Modul dabei zur Bedingung:

* **Ohne Anmeldung ändert sich nichts.** Ab Werk ist hier nichts eingerichtet.
* **Der Mensch davor behält das letzte Wort.** Hebt jemand die Übernahme dort
  auf, meldet sich der Planer *nicht* stillschweigend neu an, und er schreibt
  den vorgefundenen Wochenplan zurück. Ein Knopf, den ein Programm sofort
  wieder aushebelt, wäre eine Attrappe.
* **Es wird nachgesehen, ob das Geschriebene hält.** Auf Flanke zu schreiben
  genügt nicht, wenn die Gegenseite den Wert stillschweigend verwirft.

Wochenprogramme liegen im nichtflüchtigen Speicher des Reglers, und der hat
endlich viele Schreibzyklen. Einmal am Tag je Wochentag ist davon weit
entfernt; ein Fehler, der zwei Regeln gegeneinander schalten lässt, wäre es
nicht. Darum die Tagesgrenze in ``SCHREIBGRENZE``.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime

import huellkurve
import store
import texte
import zeitplan

_LOGGER = logging.getLogger(__name__)

QUELLE = "heizungsplaner"

# Vom Anlagenmanager über MQTT angesagt. Nachschlagen kann der Planer die
# Anschrift nicht: Die Add-on-Liste gibt der Supervisor nur mit
# Verwalterrechten heraus, und die braucht ein Heizungsplaner nicht.
_gefunden = ""

# Zustände, in denen ein Raum wirklich Komfort verlangt – also mehr, als der
# Reduziertsollwert der Regelung hergibt. Sie lösen eine Erweiterung des
# laufenden Fensters aus, wenn der Wochenplan sie nicht schon abdeckt.
#
# Eine Falle steckt in „uebersteuert“: Diesen Zustand vergibt `regelung.py`
# **nur**, wenn eine Übersteuerungsregel auf „aus“ steht. Greift eine Regel
# mit Komfort, trägt der Raum den Namen des Modus („komfort“). „uebersteuert“
# gehört deshalb zu den geschlossenen Räumen, nicht zu den warmen – genau
# andersherum, als der Name vermuten lässt.
KOMFORT_ZUSTAENDE = frozenset({
    "komfort",     # Zeitplan oder eine Regel verlangt Komfort
    "party",       # Partytaste
    "heimkehr",    # jemand ist auf dem Heimweg, der Raum wird vorgewärmt
})

# „manuell“ steht bewusst **nicht** darin – also kein handgeführter Raum.
#
# Das war beim Bauen anders gedacht und einmal live falsch: Bei Sven stehen
# Hobbyraum, Flur und Gästetoilette dauerhaft auf „nur absenken“ und melden
# darum immer „manuell“. Sie hätten die Hüllkurve rund um die Uhr aufgespannt
# und die ganze Ersparnis zunichtegemacht – während `huellkurve.fuer_tag` sie
# aus demselben Grund ausschließt. Ein Modul, das sich selbst widerspricht.
#
# Die Abwägung dahinter war aus der alten Fassung mitgeschleppt, die die
# Betriebsart stellte: Dort hieß „nicht in der Hüllkurve“ tatsächlich
# *Standby*, also keine Wärme, und im Zweifel warm zu fahren war richtig. Beim
# Wochenprogramm heißt es nur *Reduziertsollwert* – bei Sven 20 °C. Das reicht
# für einen Flur allemal, und wer den Hobbyraum von Hand hochdreht, bekommt
# Vorlauf, sobald irgendein anderer Raum Komfort verlangt.

# So oft darf der Planer einen Wochentag an einem Tag neu schreiben. Die
# Grenze ist kein Sparzwang, sondern eine Bremse: Zwei Regeln, die einander
# umschalten, schrieben sonst im Takt des Planers in den Speicher des
# Reglers. Ein Dutzend deckt jeden gewollten Fall ab – Plan am Morgen,
# Partytaste, eine Regel, die kommt und geht.
SCHREIBGRENZE = 12

# So oft darf ein Wert zurückspringen, bevor der Planer die Führung aufgibt.
# Einmal kann ein Lesefehler sein oder ein Telegramm, das sich mit dem
# Lesezyklus überschnitten hat. Dreimal ist eine Antwort.
VERWORFEN_GRENZE = 3


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


def bedarf_bis(bericht: dict) -> int | None:
    """Bis wann ein Raum Komfort verlangt, den kein Wochenplan vorhersieht.

    Zurück kommt die Minute des Tages, oder ``None``, wenn niemand etwas
    Außerplanmäßiges will. Maßgeblich ist der späteste anstehende Wechsel
    unter den Räumen, die gerade Komfort fahren – bei der Partytaste also ihr
    Ende, bei einer Übersteuerungsregel das Ende ihres Zeitfensters.

    Findet sich kein Zeitpunkt, wird eine Stunde angesetzt. Das ist keine
    Schätzung des Bedarfs, sondern eine Frist: Beim nächsten Takt wird ohnehin
    neu gerechnet, und ein Fenster, das zu kurz war, wächst dann weiter.
    """
    spaeteste = None
    for raum in bericht.get("raeume") or []:
        if raum.get("zustand") not in KOMFORT_ZUSTAENDE:
            continue
        wechsel = raum.get("naechster_wechsel")
        minute = None
        if wechsel:
            try:
                zeit = datetime.fromisoformat(str(wechsel))
                minute = zeit.hour * 60 + zeit.minute
                if zeit.date() != _jetzt_datum(bericht):
                    minute = 24 * 60      # reicht über den Tag hinaus
            except ValueError:
                minute = None
        if minute is None:
            minute = _jetzt_minute(bericht) + 60
        spaeteste = minute if spaeteste is None else max(spaeteste, minute)
    return spaeteste


def _jetzt(bericht: dict) -> datetime:
    try:
        return datetime.fromisoformat(str(bericht.get("zeit")))
    except (TypeError, ValueError):
        return datetime.now()


def _jetzt_datum(bericht: dict):
    return _jetzt(bericht).date()


def _jetzt_minute(bericht: dict) -> int:
    jetzt = _jetzt(bericht)
    return jetzt.hour * 60 + jetzt.minute


def _tagesart(bericht: dict):
    """Welche Tagesart für welchen Tag gilt.

    Für **heute** weiß der Planer es: Die Schalter für schulfrei und
    Arbeitstag stehen im Bericht. Für jeden anderen Tag weiß er es nicht –
    Ferien beginnen, Feiertage fallen an –, und dann kommt ``None`` zurück.
    Die Hüllkurve rechnet solche Tage beidseitig und steht lieber zu früh
    bereit als zu spät; am Tag selbst schreibt der Planer den richtigen Stand
    darüber.
    """
    heute = _jetzt_datum(bericht)
    schulfrei = bericht.get("schulfrei")
    arbeitstag = bericht.get("arbeitstag")

    def fuer(tag):
        if tag.date() == heute:
            return schulfrei, arbeitstag
        return None, None
    return fuer


def lage(einstellungen: dict) -> dict:
    """Was der Anlagenmanager meldet: Programm, Parameter und was darin steht."""
    adresse = basis(einstellungen)
    if not adresse:
        return {"erreichbar": False, "fehler": texte.t("kessel_nicht_gefunden")}
    try:
        katalog = _json("GET", f"{adresse}/api/katalog")
        uebernahme = _json("GET", f"{adresse}/api/uebernahme")
        werte = _json("GET", f"{adresse}/api/werte")
    except (Abgelehnt, urllib.error.URLError, OSError, ValueError) as fehler:
        return {"erreichbar": False, "fehler": str(fehler)}
    werte = werte.get("werte") or werte

    # Welches der Wochenprogramme fährt die Regelung gerade? Das sagt die
    # Programmwahl – der einzige Parameter, den dieses Modul noch liest. Sie
    # zu *stellen* haben wir aufgegeben; sie zu lesen ist die Voraussetzung
    # dafür, das richtige Programm zu beschreiben.
    wahl = katalog.get("programmwahl") or {}
    ist_wahl = str((werte.get(str(wahl.get("nr") or "")) or {}).get("value") or "")
    nummer = next((p for p, w in (wahl.get("zu") or {}).items() if w == ist_wahl), None)

    programme = katalog.get("zeitprogramme") or {}
    programm = programme.get(str(nummer)) if nummer else None
    if not programm:
        return {"erreichbar": True, "fehler": texte.t("kessel_kein_programm")}

    tage = list(programm.get("tage") or [])
    if len(tage) != 7:
        return {"erreichbar": True, "fehler": texte.t("kessel_kein_programm")}

    # Die Parameter stehen in der Reihenfolge Montag … Sonntag.
    zuordnung = dict(zip(zeitplan.TAGE, (str(t) for t in tage)))
    inhalt, gelesen, fehlend = {}, {}, []
    for tag, nr in zuordnung.items():
        eintrag = werte.get(nr) or {}
        if eintrag.get("error") or eintrag.get("value") in (None, ""):
            fehlend.append(nr)
        else:
            inhalt[tag] = str(eintrag["value"])
            # Wann der Anlagenmanager diesen Wert zuletzt von der Anlage geholt
            # hat. Ohne diese Angabe ließe sich „die Regelung hat es verworfen“
            # nicht von „der Manager hat seit unserem Schreiben nicht wieder
            # gelesen“ unterscheiden – und genau diese Verwechslung hat die
            # Führung am 12.09.2026 zweimal grundlos abgeschaltet.
            gelesen[nr] = str(eintrag.get("zeit") or "")

    gefuehrt = uebernahme.get("parameter") or {}
    meine = [nr for nr in zuordnung.values()
             if (gefuehrt.get(nr) or {}).get("quelle") == QUELLE]
    fremde = {nr: e.get("name") for nr, e in gefuehrt.items()
              if nr in set(zuordnung.values()) and e.get("quelle") != QUELLE}

    return {
        "erreichbar": True,
        "programm": str(nummer),
        "name": programm.get("name") or "",
        "parameter": zuordnung,
        "inhalt": inhalt,
        "gelesen": gelesen,
        "fehlend": fehlend,
        "uebernommen": len(meine) == 7,
        "teilweise": 0 < len(meine) < 7,
        "fremd": next(iter(fremde.values()), None) if fremde else None,
    }


def anmelden(einstellungen: dict, parameter: list[str]) -> bool:
    adresse = basis(einstellungen)
    if not adresse:
        return False
    try:
        _json("PUT", f"{adresse}/api/uebernahme", {
            "quelle": QUELLE,
            "name": "Heizungsplaner",
            "hinweis": texte.t("kessel_hinweis"),
            "parameter": list(parameter),
        })
        _LOGGER.info("Wochenprogramm übernommen: %s", ", ".join(parameter))
        return True
    except (Abgelehnt, urllib.error.URLError, OSError, ValueError) as fehler:
        _LOGGER.warning("Übernahme fehlgeschlagen: %s", fehler)
        return False


def abmelden(einstellungen: dict) -> bool:
    """Die Übernahme zurückgeben.

    Ohne diesen Schritt bliebe der Wochenplan im Anlagenmanager ausgeblendet,
    obwohl ihn niemand mehr führt: sieben Kacheln, die für immer verschwunden
    sind, weil ein Schalter woanders umgelegt wurde.
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


def schreiben(einstellungen: dict, nr: str, text: str) -> None:
    """Einen Wochentag stellen. Wirft ``Abgelehnt``, wenn die Anlage nein sagt."""
    _json("POST", f"{basis(einstellungen)}/api/setzen",
          {"nr": nr, "wert": text, "quelle": QUELLE})


def original_lesen(einstellungen: dict) -> dict:
    """Der Wochenplan, den der Planer vorgefunden hat.

    Er liegt in der **Konfiguration**, nicht im Laufzeitzustand. Das ist nicht
    beliebig: Beim Aufgeben wird der Merker geleert, und lag das Original
    darin, war es mit weg. Beim nächsten Einschalten fand der Planer dann
    seinen eigenen Plan vor, hielt ihn für den ursprünglichen und sicherte ihn
    – womit der Weg zurück endgültig verloren war. Genau das ist am
    12.09.2026 passiert und hat Svens 06:00–22:00 gekostet.
    """
    return dict((einstellungen.get("kessel") or {}).get("original") or {})


def ist_eigener(inhalt: dict, plan: dict) -> bool:
    """Ist das, was in der Anlage steht, schon unsere eigene Hüllkurve?

    Die zweite Sicherung gegen ein festgeschriebenes Eigengewächs: Selbst wenn
    das gesicherte Original einmal fehlt – nach einer Neuinstallation etwa –,
    darf der Planer nicht ausgerechnet seinen eigenen Plan als den
    vorgefundenen ablegen. Er erkennt ihn daran, dass er genau das ist, was er
    heute schreiben würde.
    """
    if not inhalt or not plan:
        return False
    return all(huellkurve.aus_text(inhalt.get(tag, "")) ==
               huellkurve.aus_text(text) for tag, text in plan.items())


def original_sichern(einstellungen: dict, plan: dict) -> bool:
    """Den vorgefundenen Plan sichern – **einmal**, und nie überschreiben.

    Steht schon etwas da, bleibt es stehen. Ein zweites Sichern könnte nur
    noch den eigenen Plan festschreiben.
    """
    if original_lesen(einstellungen):
        return False
    einstellungen.setdefault("kessel", {})["original"] = dict(plan)
    try:
        config = store.load_config()
        config["einstellungen"].setdefault("kessel", {})["original"] = dict(plan)
        store.save_config(config)
    except Exception as fehler:  # noqa: BLE001
        _LOGGER.warning("Wochenplan ließ sich nicht sichern: %s", fehler)
        return False
    _LOGGER.info("Vorgefundener Wochenplan gesichert: %s", plan)
    return True


def zurueckgeben(einstellungen: dict, merker: dict) -> int:
    """Den vorgefundenen Wochenplan wiederherstellen.

    Das ist die eigentliche Bedingung dafür, hier überhaupt hineinschreiben zu
    dürfen: Was der Planer vorgefunden hat, war Svens Einstellung – 06:00 bis
    22:00 unter der Woche, 08:00 bis 22:00 am Wochenende. Sie nach dem
    Abschalten stehen zu lassen hieße, jemandem seinen Heizungsplan
    wegzunehmen, ohne es zu sagen.
    """
    original = original_lesen(einstellungen)
    if not original:
        # Kein gesicherter Stand. Das passiert, wenn die Übernahme drüben noch
        # steht, das Gedächtnis hier aber weg ist – nach einer Neuinstallation
        # etwa. Dann gibt es keinen Weg zurück, und das muss gesagt werden:
        # Stillschweigend nichts zu tun hieße, jemanden im Glauben zu lassen,
        # sein alter Plan käme wieder.
        _LOGGER.warning("Kein gesicherter Wochenplan – nichts zurückzustellen")
        return 0
    zurueck = 0
    for nr, text in original.items():
        try:
            schreiben(einstellungen, nr, text)
            zurueck += 1
        except (Abgelehnt, urllib.error.URLError, OSError, ValueError) as fehler:
            _LOGGER.warning("Wochentag %s nicht zurückgestellt: %s", nr, fehler)
    if zurueck:
        _LOGGER.info("%d Wochentage auf den vorgefundenen Stand gebracht", zurueck)
    return zurueck


def _stempel(einstellungen: dict) -> str:
    """Der Zeitpunkt eines Schreibvorgangs, vergleichbar mit denen der Anlage.

    Der Anlagenmanager stempelt jeden gelesenen Wert in Ortszeit ohne Zone
    (``2026-09-12T10:10:27``). Beide Add-ons laufen unter derselben Zeitzone
    von Home Assistant, deshalb genügt derselbe Aufbau – und ISO-Zeiten lassen
    sich als Zeichenketten der Reihe nach vergleichen.
    """
    return datetime.now().isoformat(timespec="seconds")


def _darf_schreiben(merker: dict, nr: str, heute: str) -> bool:
    """Die Tagesbremse: wie oft dieser Wochentag heute schon geschrieben wurde.

    Nicht aus Sparsamkeit – ein Dutzend Schreibvorgänge tun keinem Speicher
    weh. Sondern damit ein Fehler nicht zum Dauerfeuer wird: Zwei Regeln, die
    einander umschalten, schrieben sonst im Takt des Planers in den EEPROM des
    Reglers, und das hält er keine Saison lang aus.
    """
    zaehler = merker.setdefault("schreibzaehler", {})
    if zaehler.get("tag") != heute:
        zaehler.clear()
        zaehler["tag"] = heute
    return int(zaehler.get(nr, 0)) < SCHREIBGRENZE


def _gezaehlt(merker: dict, nr: str) -> int:
    zaehler = merker.setdefault("schreibzaehler", {})
    zaehler[nr] = int(zaehler.get(nr, 0)) + 1
    return zaehler[nr]


def _verworfen(merker: dict, ist: dict, gelesen: dict, einstellungen: dict,
               protokoll) -> dict | None:
    """Hat die Regelung zurückgenommen, was der Planer geschrieben hat?

    Ein Telegramm anzunehmen und ein Telegramm zu befolgen sind zweierlei.
    Die Betriebsart dieses Reglers etwa gehört dem Schalter am Gerät: Der Bus
    darf sie setzen, der Regler stellt Sekunden später seinen eigenen Stand
    wieder her. Bei den Schaltzeiten ist das nachgemessen anders – aber
    darauf zu *vertrauen*, wäre derselbe Fehler noch einmal.

    Verglichen wird jedoch nur gegen einen Wert, den der Anlagenmanager
    **nach** unserem Schreiben von der Anlage geholt hat. Er liest zyklisch
    und nicht jeden Parameter in jedem Takt; sein Zwischenstand kann Minuten
    alt sein. Ohne diese Prüfung liest der Planer seinen eigenen alten Wert
    zurück und hält ihn für einen Widerspruch – zweimal am 12.09.2026
    geschehen, beide Male grundlos aufgegeben.
    """
    geschrieben = merker.get("geschrieben") or {}
    if not geschrieben:
        return None

    abweichung = []
    for nr, eintrag in geschrieben.items():
        if nr not in ist:
            continue
        text, am = eintrag.get("text"), eintrag.get("am") or ""
        frisch = gelesen.get(nr) or ""
        if not frisch or frisch <= am:
            continue                       # seither nicht neu gelesen
        if huellkurve.aus_text(ist[nr]) != huellkurve.aus_text(text):
            abweichung.append(nr)

    if not abweichung:
        merker.pop("verworfen", None)
        return None

    zahl = int(merker.get("verworfen", 0)) + 1
    merker["verworfen"] = zahl
    if zahl < VERWORFEN_GRENZE:
        for nr in abweichung:
            geschrieben.pop(nr, None)      # noch einmal versuchen
        return None

    nr = abweichung[0]
    hinweis = texte.t("kessel_verworfen_warum", ist=ist.get(nr, "—"),
                      soll=(geschrieben.get(nr) or {}).get("text", "—"))
    zurueckgeben(einstellungen, merker)
    abmelden(einstellungen)
    _abschalten(einstellungen)
    merker.clear()
    protokoll(texte.t("log_alle_raeume"), texte.t("kessel_verworfen"),
              hinweis, art="warnung")
    return {"aktiv": False, "erreichbar": True, "verworfen": zahl,
            "hinweis": hinweis}


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


def fuehren(bericht: dict, config: dict, state: dict, protokoll) -> dict:
    """Das Wochenprogramm der Regelung nachführen – einmal je Takt.

    Zurück kommt die Lage für Oberfläche und MQTT, auch wenn nichts
    geschrieben wurde: Wer sehen will, was der Planer der Anlage zumutet, soll
    das nicht aus dem Protokoll zusammensuchen müssen.
    """
    einstellungen = config["einstellungen"]
    kessel = einstellungen.get("kessel") or {}
    merker = state.setdefault("kessel", {})

    if not kessel.get("aktiv"):
        # Gerade ausgeschaltet? Dann den vorgefundenen Plan zurückschreiben
        # und die Übernahme zurückgeben, solange wir noch wissen, dass wir sie
        # hatten.
        if merker.pop("angemeldet", False):
            zurueck = zurueckgeben(einstellungen, merker)
            abmelden(einstellungen)
            ohne = not original_lesen(einstellungen)
            merker.clear()
            if ohne:
                protokoll(texte.t("log_alle_raeume"),
                          texte.t("kessel_kein_original"),
                          texte.t("kessel_kein_original_warum"), art="warnung")
            return {"aktiv": False, "zurueckgestellt": zurueck,
                    "hinweis": texte.t("kessel_kein_original_warum") if ohne else ""}
        return {"aktiv": False}

    stand = lage(einstellungen)
    if not stand["erreichbar"]:
        return {"aktiv": True, "erreichbar": False, "fehler": stand["fehler"]}
    if stand.get("fehler"):
        return {"aktiv": True, "erreichbar": True, "hinweis": stand["fehler"]}
    if stand["fremd"]:
        return {"aktiv": True, "erreichbar": True, "uebernommen": False,
                "hinweis": texte.t("kessel_fremd", quelle=stand["fremd"])}

    parameter = stand["parameter"]            # {"mon": "11", "tue": "11.1", …}
    inhalt = stand["inhalt"]                  # {"mon": "06:00-22:00 …", …}
    if len(inhalt) < 7:
        # Noch nicht alles gelesen. Lieber einen Takt warten als einen
        # Wochenplan auf halber Kenntnis überschreiben.
        return {"aktiv": True, "erreichbar": True,
                "hinweis": texte.t("kessel_unvollstaendig")}

    # -- Übernahme ----------------------------------------------------------
    #
    # Hat jemand sie drüben aufgehoben? Dann bleibt sie aufgehoben, bis sie
    # hier wieder eingeschaltet wird. Alles andere machte den Knopf dort zur
    # Attrappe.
    if not stand["uebernommen"]:
        if merker.get("angemeldet"):
            zurueckgeben(einstellungen, merker)
            _abschalten(einstellungen)
            merker.clear()
            protokoll(texte.t("log_alle_raeume"), texte.t("kessel_freigegeben"),
                      texte.t("kessel_freigegeben_warum"), art="warnung")
            return {"aktiv": False, "erreichbar": True, "abgegeben": True}
        # Erstanmeldung: Vorher sichern, was dort steht. Danach ist es zu spät –
        # der eigene Plan stünde darin, und der Weg zurück wäre verloren.
        # Vor dem Sichern prüfen, ob dort schon unser eigener Plan steht –
        # dann ist es nicht der vorgefundene, und Sichern würde ihn für immer
        # festschreiben.
        vorschau = huellkurve.woche(config.get("raeume") or [],
                                    _jetzt(bericht), _tagesart(bericht))
        if ist_eigener(inhalt, vorschau):
            _LOGGER.warning("In der Regelung steht bereits der eigene Plan – "
                            "es wird nichts als Original gesichert")
        else:
            original_sichern(
                einstellungen,
                {parameter[tag]: text for tag, text in inhalt.items()})
        if not anmelden(einstellungen, list(parameter.values())):
            return {"aktiv": True, "erreichbar": True, "uebernommen": False}
    merker["angemeldet"] = True

    # Übernahme steht, aber wir haben nie gesichert? Dann ist das Gedächtnis
    # verloren gegangen. Geführt wird weiter – aber der Weg zurück fehlt, und
    # darauf muss die Oberfläche hinweisen, statt einen vorzutäuschen.
    ohne_original = not original_lesen(einstellungen)

    # -- Hat gehalten, was wir geschrieben haben? ---------------------------
    nach_nr = {parameter[tag]: text for tag, text in inhalt.items()}
    aufgegeben = _verworfen(merker, nach_nr, stand["gelesen"],
                            einstellungen, protokoll)
    if aufgegeben is not None:
        return aufgegeben

    # -- Was hineingehört ---------------------------------------------------
    jetzt = _jetzt(bericht)
    plan = huellkurve.woche(config.get("raeume") or [], jetzt,
                            _tagesart(bericht))

    # Außerplanmäßiger Bedarf – Partytaste, eine greifende Regel, jemand auf
    # dem Heimweg. Nur für heute, und nur wenn der Wochenplan ihn nicht schon
    # abdeckt. Hier entsteht der einzige Versatz des ganzen Verfahrens: bis zu
    # einer Taktlänge.
    heute = zeitplan.TAGE[jetzt.weekday()]
    bis = bedarf_bis(bericht)
    erweitert = False
    if bis is not None:
        breiter = huellkurve.erweitern(plan[heute], bis, jetzt)
        if breiter:
            plan[heute] = breiter
            erweitert = True

    ergebnis = {"aktiv": True, "erreichbar": True, "uebernommen": True,
                "programm": stand["name"], "heute": plan[heute],
                "erweitert": erweitert,
                "anzeige": _anzeige(plan[heute], jetzt)}
    if ohne_original:
        ergebnis["hinweis"] = texte.t("kessel_kein_original_warum")

    if einstellungen.get("trockenlauf"):
        ergebnis["trocken"] = True
        return ergebnis

    # -- Schreiben, wo es abweicht -----------------------------------------
    datum = jetzt.date().isoformat()
    geschrieben, gebremst = [], []
    for tag, nr in parameter.items():
        soll = plan.get(tag)
        if soll is None:
            continue
        if huellkurve.aus_text(inhalt.get(tag, "")) == huellkurve.aus_text(soll):
            continue                       # steht schon so – kein Telegramm
        if not _darf_schreiben(merker, nr, datum):
            gebremst.append(tag)
            continue
        try:
            schreiben(einstellungen, nr, soll)
        except Abgelehnt as fehler:
            ergebnis["fehler"] = (texte.t("kessel_gesperrt")
                                  if fehler.code == 403 else fehler.text)
            _LOGGER.warning("Wochentag %s abgelehnt (%s): %s",
                            nr, fehler.code, fehler.text)
            return ergebnis
        except (urllib.error.URLError, OSError, ValueError) as fehler:
            ergebnis["fehler"] = str(fehler)
            return ergebnis
        _gezaehlt(merker, nr)
        merker.setdefault("geschrieben", {})[nr] = {
            "text": soll, "am": _stempel(einstellungen)}
        geschrieben.append(tag)

    if geschrieben:
        # Den Manager bitten, die geschriebenen Tage sofort nachzulesen. Ohne
        # das käme die Bestätigung erst, wenn sein Lesezyklus zufällig wieder
        # an diesen Parametern vorbeikommt.
        try:
            _json("POST", f"{basis(einstellungen)}/api/lesen",
                  {"nr": [parameter[tag] for tag in geschrieben]})
        except (Abgelehnt, urllib.error.URLError, OSError, ValueError) as fehler:
            _LOGGER.info("Nachlesen nicht ausgelöst: %s", fehler)
        ergebnis["geschrieben"] = geschrieben
        protokoll(texte.t("log_alle_raeume"),
                  texte.t("kessel_gestellt", anzahl=len(geschrieben)),
                  texte.t("kessel_gestellt_warum", plan=plan[heute]))
    if gebremst:
        ergebnis["gebremst"] = gebremst
        ergebnis["hinweis"] = texte.t("kessel_gebremst", grenze=SCHREIBGRENZE)
        _LOGGER.warning("Schreibbremse greift für: %s", ", ".join(gebremst))
    return ergebnis


def _anzeige(text: str, jetzt: datetime) -> str:
    """Was auf der Kachel steht: fährt die Regelung gerade Komfort oder nicht."""
    minute = jetzt.hour * 60 + jetzt.minute
    for beginn, ende in huellkurve.aus_text(text):
        if beginn <= minute < ende:
            return texte.t("kessel_komfort_bis", uhrzeit=huellkurve._uhr(ende))
    kommend = [b for b, _ in huellkurve.aus_text(text) if b > minute]
    if kommend:
        return texte.t("kessel_reduziert_bis",
                       uhrzeit=huellkurve._uhr(min(kommend)))
    return texte.t("kessel_reduziert")
