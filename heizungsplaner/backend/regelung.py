"""Die Regelkette: aus Zeitplan, Wetter und Anwesenheit wird ein Sollwert.

Für jeden Raum entsteht in jedem Takt eine Entscheidung aus einer festen
Rangfolge. Der erste zutreffende Fall gewinnt:

1. Raum abgeschaltet      → Ventil zu
2. Fenster offen          → Frostschutz, für eine Sperrzeit
3. Partytaste läuft       → Komfort, bis sie abläuft
4. Urlaub                 → Urlaubstemperatur
5. Sommerbetrieb          → Ventil zu
6. Zeitplan               → Komfort / Eco / Nacht, ggf. vorgezogen (Vorheizen)
7. niemand zuständig da   → auf Abwesenheitstemperatur absenken
8. Heizkurve              → Aufschlag nach Außentemperatur

Jede Entscheidung trägt ihre Begründung mit sich; sie steht später in der
Oberfläche und im Protokoll. Wer wissen will, warum ein Raum gerade 17 °C
bekommt, soll das nicht aus dem Quelltext erschließen müssen.

Geschrieben wird ausschließlich auf **Flanke**: Ein Sollwert geht nur dann an
ein Thermostat, wenn dort tatsächlich etwas anderes eingestellt ist. Ein
Pegelabgleich, der bei jedem Takt stur denselben Wert schreibt, macht ein
Add-on zum Besitzer der Entität und überfährt jede andere Bedienung.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import anwesenheit
import einheit
import ha_api
import kessel
import texte
import wachhund
import witterung
import zeitplan as zp

_LOGGER = logging.getLogger(__name__)

# So lange bekommt ein Thermostat Zeit, einen geschriebenen Wert zu bestätigen,
# bevor erneut geschrieben oder eine Abweichung als Handeingriff gewertet wird.
# Funkthermostate melden sich nur alle paar Minuten.
BESTAETIGUNG_MIN = 15

# Feinere Sollwerte als ein halbes Grad kann kein Heizkörperthermostat.
# Die kleinste Änderung, die geschrieben wird. In Fahrenheit ein ganzes Grad:
# feiner lösen die Geräte dort nicht auf, und jeder Schreibvorgang kostet
# Batterie. Über `_schritt()` statt als feste Zahl, damit ein Wechsel des
# Maßsystems sofort wirkt.
SCHRITT_CELSIUS = 0.5


def _schritt() -> float:
    return einheit.schritt()

# Ein Thermostat, das den Sollwert nicht annimmt, wird nicht bei jedem Takt
# aufs Neue bestürmt. Nach ein paar Fehlschlägen genügt ein Versuch in
# größerem Abstand – gemeldet wird es ohnehin über die Überwachung.
FEHLSCHLAEGE_BIS_SCHONUNG = 3
SCHONFRIST_MIN = 30

# Betriebsart „nur absenken“: So lange nach einem Absenkzeitpunkt versucht der
# Planer, den Wert zu setzen. Danach gehört der Raum wieder der Hand, die ihn
# stellt. Das Fenster überbrückt einen ausgefallenen Takt oder ein Thermostat,
# das gerade nicht antwortet – ein einzelner Schuss ginge dabei verloren.
AUSLOESE_FENSTER_MIN = 30


def _jetzt() -> datetime:
    return datetime.now()


def _iso(zeitpunkt: datetime | None) -> str | None:
    return zeitpunkt.isoformat(timespec="seconds") if zeitpunkt else None


def _aus_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _runden(wert: float) -> float:
    schritt = _schritt()
    return round(round(wert / schritt) * schritt, 1)


def _bool_state(states_index: dict, entity_id: str) -> bool | None:
    eintrag = states_index.get(entity_id)
    if not eintrag:
        return None
    zustand = eintrag.get("state")
    if zustand in ("on", "off"):
        return zustand == "on"
    # Personen und Gerätetracker sprechen ihre eigene Sprache. „home“ heißt an,
    # jede andere Zone heißt aus: Wer im Büro sitzt, ist nicht zu Hause.
    if entity_id.split(".", 1)[0] in ("person", "device_tracker"):
        if zustand in (None, "", "unknown", "unavailable"):
            return None
        return zustand == "home"
    return None


# ------------------------------------------------------------ Raumklima ----

def raumtemperatur(raum: dict, states_index: dict) -> float | None:
    """Ist-Temperatur des Raumes: eigener Fühler, sonst Mittel der Thermostate."""
    eigener = raum.get("raumtemp")
    if eigener:
        eintrag = states_index.get(eigener)
        if eintrag:
            wert = ha_api.as_float(eintrag.get("state"))
            if wert is not None:
                return wert
    werte = []
    for entity_id in raum.get("thermostate") or []:
        eintrag = states_index.get(entity_id)
        if not eintrag:
            continue
        wert = ha_api.as_float((eintrag.get("attributes") or {}).get("current_temperature"))
        if wert is not None:
            werte.append(wert)
    return round(sum(werte) / len(werte), 1) if werte else None


def fenster_offen(raum: dict, states_index: dict, rz: dict, ist: float | None,
                  jetzt: datetime, fenster_cfg: dict) -> tuple[bool, str, str]:
    """Fenstererkennung: erst die Kontakte, dann ersatzweise der Temperatursturz.

    Rückgabe: offen, Begründung, Hinweis zum Verfahren.

    Sobald ein Raum verlässliche Kontakte hat, entscheiden allein sie – der
    Temperatursturz ist der Notbehelf für Räume ohne Kontakte und schlägt
    sonst auch mal grundlos an (ein anlaufender Heizkörper verwirbelt die
    Luft am Thermostatfühler). Wer beides will, schaltet es am Raum zu.

    **Die geräteeigene Fenstererkennung eines Thermostats zählt dabei nicht
    als Kontakt.** Sie löst zwar aus, verdrängt die Sturzerkennung aber nicht:
    Sie macht dasselbe wie diese, nur im Gerät, und schweigt, sobald das Gerät
    abgeschaltet ist oder in der Sommerpause steht. Ein Raum, dessen einziger
    „Kontakt“ eine solche Meldung ist, wäre sonst ohne Fenstererkennung – so
    stand die Gästetoilette am 25.08.2026 da.

    **Ein Kontakt, der nichts meldet, gilt nicht als „geschlossen“.** Ein
    leerer Knopf, ein abgezogener Zigbee-Stick oder ein noch nicht angelernter
    Sensor würde den Raum sonst stillschweigend blind machen. In dem Fall
    springt die Sturzerkennung wieder ein.
    """
    if not fenster_cfg.get("aktiv"):
        return False, "", ""

    kontakte = raum.get("fenster") or []
    verlaesslich, stumm = 0, []
    for entity_id in kontakte:
        name = ((states_index.get(entity_id) or {}).get("attributes") or {}).get(
            "friendly_name", entity_id)
        geraeteeigen = ha_api.ist_geraeteeigene_erkennung(entity_id, name)
        zustand = _bool_state(states_index, entity_id)
        if zustand is None:
            # Ein stummer geräteeigener Melder ist kein Grund zur Sorge – die
            # Sturzerkennung läuft ohnehin weiter. Fällt das Gerät ganz aus,
            # meldet es der Wachhund.
            if not geraeteeigen:
                stumm.append(entity_id)
            continue
        if not geraeteeigen:
            verlaesslich += 1
        if zustand:
            return True, (texte.t("fenster_geraet", name=name) if geraeteeigen
                          else texte.t("fenster_kontakt", name=name)), ""

    hinweis = ""
    if stumm:
        hinweis = texte.t("fenster_stumm", anzahl=len(stumm))
    sturz_erlaubt = verlaesslich == 0 or raum.get("sturz_auch_mit_kontakten") or stumm
    if not sturz_erlaubt or ist is None:
        return False, "", hinweis

    fenster_min = int(fenster_cfg.get("sturz_min", 10))
    schwelle = float(fenster_cfg.get("sturz_k", 1.2))
    verlauf = rz.get("verlauf") or []
    grenze = jetzt - timedelta(minutes=fenster_min)
    frueher = [wert for stempel, wert in verlauf
               if (_aus_iso(stempel) or jetzt) >= grenze]
    if frueher:
        hoechster = max(frueher)
        if hoechster - ist >= schwelle:
            return True, texte.t("fenster_sturz",
                                 grad=f"{hoechster - ist:.1f}",
                                 minuten=fenster_min), hinweis
    return False, "", hinweis


def _im_fenster(von: str | None, bis: str | None, jetzt: datetime) -> bool:
    """Liegt ``jetzt`` im Zeitfenster? Ohne Fenster gilt: immer.

    Ein Fenster darf über Mitternacht reichen (22:00–06:00) – dieselbe Regel
    wie beim Zeitplan, wo der letzte Punkt des Tages in den nächsten reicht.
    """
    if not von or not bis:
        return True
    jetzt_hm = jetzt.strftime("%H:%M")
    if von <= bis:
        return von <= jetzt_hm < bis
    return jetzt_hm >= von or jetzt_hm < bis


def uebersteuerung_lage(raum: dict, states_index: dict,
                        jetzt: datetime) -> dict:
    """Wie steht es um die Übersteuerungsregeln des Raumes?

    Gibt Name, ob sie greift, und – wenn nicht – warum. Dieselbe Auskunft, die
    die Oberfläche in der Regel selbst anzeigt, damit sie auch über MQTT auf
    dem Dashboard landen kann.

    Unterschieden wird dabei zwischen „heute nicht“ und „gerade nicht“: Ein
    Ferientag gilt bis Mitternacht, eine abwesende Person kann in fünf Minuten
    zurück sein.
    """
    regeln = raum.get("uebersteuerung") or []
    if not regeln:
        return {"name": "", "greift": False, "lage": "", "bis": "—"}

    greifend = _uebersteuerung(raum, states_index, jetzt)
    if greifend:
        # „bis 14:00 Uhr“ ist die Angabe, die man auf einer Kachel sehen will –
        # der Zielwert steht ohnehin daneben. Ohne Zeitfenster bleibt es bei
        # „läuft“, denn ein Ende gibt es dann nicht.
        bis = greifend.get("fenster", "").strip(" ()")
        return {"name": greifend["name"], "greift": True,
                "lage": texte.t("regel_greift"),
                "bis": bis or texte.t("regel_laeuft")}

    # Sonst die erste Regel erklären – sie ist die ranghöchste.
    regel = regeln[0]
    name = regel.get("name") or "Übersteuerung"
    for bedingung in regel.get("wenn") or []:
        entity_id = bedingung.get("entity") or ""
        ist = _bool_state(states_index, entity_id)
        soll = (bedingung.get("zustand", "an") == "an")
        if ist is not None and ist == soll:
            continue
        anzeige = ((states_index.get(entity_id) or {}).get("attributes") or {}).get(
            "friendly_name", entity_id)
        art = entity_id.split(".", 1)[0]
        person = art in ("person", "device_tracker")
        tagesfrage = art == "calendar" or any(
            wort in entity_id for wort in
            ("workday", "feiertag", "ferien", "schulfrei", "urlaub"))
        if ist is None:
            grund = texte.t("grund_meldet_nichts", name=anzeige)
        elif not soll:
            grund = texte.t("grund_zuhause" if person
                            else "grund_laeuft" if art == "calendar"
                            else "grund_an", name=anzeige)
        else:
            grund = texte.t("grund_nicht_zuhause" if person
                            else "grund_laeuft_nicht" if art == "calendar"
                            else "grund_aus", name=anzeige)
        return {"name": name, "greift": False, "bis": texte.t("regel_ruht"),
                "lage": texte.t("regel_heute_nicht" if tagesfrage
                                else "regel_gerade_nicht", grund=grund)}

    return {"name": name, "greift": False, "bis": texte.t("regel_ruht"),
            "lage": texte.t("regel_ausserhalb", von=regel.get("von"),
                            bis=regel.get("bis"))}


def _uebersteuerung(raum: dict, states_index: dict,
                    jetzt: datetime) -> dict | None:
    """Die erste zutreffende Übersteuerungsregel des Raumes.

    Eine Regel trifft zu, wenn **alle** ihre Bedingungen erfüllt sind – so
    entsteht aus „Werktag“, „keine Ferien“ und „Isabel ist zu Hause“ eine
    Homeoffice-Regelung, ohne dass jemand einen Schalter umlegen muss.

    Die Reihenfolge in der Konfiguration ist die Rangfolge. Eine Entität, die
    nichts meldet, lässt ihre Bedingung durchfallen – anders als beim
    Freigabeschalter, wo ein kaputter Schalter den Raum kalt ließe, kann hier
    nichts Schlimmes passieren: Ohne Übersteuerung gilt schlicht der Zeitplan.
    """
    for eintrag in raum.get("uebersteuerung") or []:
        if not _im_fenster(eintrag.get("von"), eintrag.get("bis"), jetzt):
            continue
        namen = []
        for bedingung in eintrag.get("wenn") or []:
            entity_id = bedingung.get("entity")
            ist = _bool_state(states_index, entity_id) if entity_id else None
            if ist is None or ist != (bedingung.get("zustand", "an") == "an"):
                break
            name = ((states_index.get(entity_id) or {}).get("attributes") or {}).get(
                "friendly_name", entity_id)
            namen.append(name if bedingung.get("zustand", "an") == "an"
                         else f"ohne {name}")
        else:
            if namen:
                # Hat die Regel einen Namen, steht der im Protokoll – „Homeoffice“
                # sagt mehr als die Aufzählung ihrer drei Bedingungen.
                # Der Name bleibt rein – das Zeitfenster kommt als eigener
                # Zusatz, damit ihn niemand mitschleppt, der nur den Namen
                # der Regel braucht.
                return {"modus": eintrag.get("modus", "komfort"),
                        "name": eintrag.get("name") or " · ".join(namen),
                        "fenster": (texte.t("uebersteuerung_bis",
                                            uhrzeit=eintrag["bis"])
                                    if eintrag.get("von") and eintrag.get("bis")
                                    else "")}
    return None


# Ab so vielen gleichen Rückstellungen ist es keine Hand mehr.
#
# Ein Mensch, der ein Thermostat dreimal binnen zwei Tagen auf **denselben**
# Wert zurückdreht, ist ungewöhnlich. Ein Zeitprogramm im Gerät tut genau das.
# Bei Svens SwitchBot-Thermostat in Lunas Zimmer lief neben dem Planer ein
# zweiter Plan in der Hersteller-App: Er stellte immer wieder auf 8 °C, der
# Planer hielt es jedes Mal für einen Handeingriff und zog sich zurück – und
# das Zimmer blieb zwei Tage ungeheizt, ohne dass irgendwo etwas anschlug.
FREMDPROGRAMM_AB = 3
FREMDPROGRAMM_FENSTER = timedelta(days=2)


def _fremdprogramm_merken(gedaechtnis: dict, wert: float, jetzt: datetime,
                          raum: dict, entity_id: str, attrs: dict,
                          protokoll) -> None:
    """Wiederholte Rückstellungen auf denselben Wert sammeln – und melden.

    Der Planer zieht sich bei einem Handeingriff bewusst zurück; das bleibt so.
    Aber er sagt jetzt Bescheid, wenn das Muster nicht zu einem Menschen passt,
    statt sich stumm immer wieder verdrängen zu lassen. Zurückgehalten wird
    nach der Meldung weiter – was in der Hersteller-App eingestellt ist, kann
    nur dort abgeschaltet werden.
    """
    frueher = [_aus_iso(z) for z in (gedaechtnis.get("hand_wann") or [])]
    letzte = [z for z in frueher if z and jetzt - z <= FREMDPROGRAMM_FENSTER]
    if gedaechtnis.get("hand_wert") is not None and \
            abs(float(gedaechtnis["hand_wert"]) - wert) >= 0.25:
        letzte = []                       # anderer Wert: Zählung von vorn
    letzte.append(jetzt)
    gedaechtnis["hand_wann"] = [_iso(z) for z in letzte[-FREMDPROGRAMM_AB:]]
    gedaechtnis["hand_wert"] = wert

    if len(letzte) < FREMDPROGRAMM_AB or gedaechtnis.get("fremd_gemeldet"):
        return
    gedaechtnis["fremd_gemeldet"] = _iso(jetzt)
    protokoll(raum["name"], texte.t("log_fremdprogramm"),
              texte.t("fremdprogramm", name=attrs.get("friendly_name", entity_id),
                      grad=f"{wert:.1f}", anzahl=len(letzte)),
              entity_id, art="warnung")


def _verlauf_fortschreiben(rz: dict, ist: float | None, jetzt: datetime,
                           quelle: str) -> None:
    """Kurzes Temperaturgedächtnis je Raum, eine Stunde tief.

    Wechselt die Quelle – ein anderer Raumfühler, oder gar keiner mehr –, wird
    das Gedächtnis verworfen. Zwei Fühler in einem Raum zeigen selten dasselbe;
    der Sprung beim Umschalten sähe sonst aus wie ein Temperatursturz und
    löste einen Fensteralarm aus.
    """
    if rz.get("temperaturquelle") != quelle:
        rz["temperaturquelle"] = quelle
        rz["verlauf"] = []
        rz["fenster_bis"] = None
    if ist is None:
        return
    verlauf = rz.get("verlauf") or []
    verlauf.append([_iso(jetzt), ist])
    grenze = jetzt - timedelta(hours=1)
    rz["verlauf"] = [[stempel, wert] for stempel, wert in verlauf
                     if (_aus_iso(stempel) or jetzt) >= grenze][-60:]


# ----------------------------------------------------------- Entscheidung ----

def entscheide(raum: dict, rz: dict, umgebung: dict) -> dict:
    """Zielwert und Zustand für einen Raum ermitteln.

    ``rz`` ist der gespeicherte Laufzeitzustand des Raumes und wird dabei
    fortgeschrieben (Leerzeit, Fenstersperre, Temperaturverlauf).
    """
    jetzt = umgebung["jetzt"]
    einst = umgebung["einstellungen"]
    states_index = umgebung["states_index"]
    frostschutz = float(einst["frostschutz"])

    ist = raumtemperatur(raum, states_index)
    _verlauf_fortschreiben(rz, ist, jetzt,
                           raum.get("raumtemp") or "thermostate")
    nur_absenken = raum.get("betriebsart") == "nur_absenken"

    def ergebnis(zustand: str, ziel: float, begruendung: str, **extra) -> dict:
        ziel = _runden(max(float(raum["min"]), min(float(raum["max"]), ziel)))
        # In der Betriebsart „nur absenken“ gehört der Sollwert der Hand, die
        # ihn gestellt hat. Greift ein Sonderzustand ein, wird der vorgefundene
        # Wert gemerkt und hinterher wiederhergestellt – sonst bliebe der Raum
        # nach einmal Lüften für immer auf Frostschutz stehen.
        if nur_absenken and zustand in ("fenster", "urlaub", "sommer"):
            extra.setdefault("merken", True)
            extra.setdefault("erzwingen", True)
        return {"zustand": zustand, "ziel": ziel, "begruendung": begruendung,
                "ist": ist, **extra}

    # 1 — Raum abgeschaltet oder nicht freigegeben
    if not raum.get("aktiv", True):
        return ergebnis("aus", frostschutz, texte.t("raum_aus"), ventil_zu=True)

    # Ein Raum, der nur zeitweise gebraucht wird – ein Gästezimmer etwa –
    # hängt an einem Schalter in Home Assistant. Steht der auf aus, bleibt der
    # Raum kalt, ganz gleich was Zeitplan und Anwesenheit sagen.
    freigabe = raum.get("freigabe_entity")
    if freigabe:
        zustand_freigabe = _bool_state(states_index, freigabe)
        if zustand_freigabe is False:
            name = (states_index.get(freigabe, {}).get("attributes") or {}).get(
                "friendly_name", freigabe)
            return ergebnis("gesperrt", frostschutz,
                            texte.t("gesperrt", name=name), ventil_zu=True)
        if zustand_freigabe is None:
            # Der Schalter fehlt oder meldet nichts. Den Raum deswegen kalt zu
            # lassen wäre die unangenehmere Überraschung, also wird geheizt und
            # der Hinweisbalken meldet den fehlenden Schalter.
            _LOGGER.warning("Freigabe %s für Raum %s meldet nichts – der Raum "
                            "wird normal geregelt", freigabe, raum["name"])

    # 2 — Fenster
    sperre_bis = _aus_iso(rz.get("fenster_bis"))
    offen, fenster_grund, fenster_hinweis = fenster_offen(
        raum, states_index, rz, ist, jetzt, einst["fenster"])
    if offen:
        sperre_bis = jetzt + timedelta(minutes=int(einst["fenster"]["sperre_min"]))
        rz["fenster_bis"] = _iso(sperre_bis)
        return ergebnis("fenster", frostschutz, fenster_grund)
    if sperre_bis and sperre_bis > jetzt:
        rest = int((sperre_bis - jetzt).total_seconds() // 60) + 1
        return ergebnis("fenster", frostschutz,
                        texte.t("sperre_rest", minuten=rest))
    rz["fenster_bis"] = None

    # 3 — Partytaste
    #
    # Sie steht vor Urlaub und Sommerbetrieb: Wer sie drückt, ist im Haus und
    # will es warm haben – ganz gleich, was der Kalender sagt. Nur ein offenes
    # Fenster bleibt stärker; dagegen anzuheizen wäre sinnlos.
    party_bis = umgebung.get("party_bis")
    if party_bis and raum.get("party", True):
        rest = int((party_bis - jetzt).total_seconds() // 60) + 1
        ziel = zp.modus_temperatur(raum, einst["party"]["modus"], frostschutz)
        hinweis = texte.t("party_sommer") if umgebung.get("sommerbetrieb") else ""
        return ergebnis("party", ziel,
                        texte.t("party", minuten=rest, hinweis=hinweis))

    # 4 — Urlaub
    if umgebung.get("urlaub"):
        return ergebnis("urlaub", float(einst["urlaub_temperatur"]),
                        texte.t("urlaub"))

    # 5 — Sommerbetrieb
    if umgebung.get("sommerbetrieb"):
        gedaempft = umgebung.get("aussen_gedaempft")
        return ergebnis("sommer", frostschutz,
                        texte.t("sommer", grad=f"{gedaempft:.1f}")
                        if gedaempft is not None else texte.t("sommer_ohne_wert"),
                        ventil_zu=True)

    # 6a — Betriebsart „nur absenken“: der Plan stößt an, statt zu führen
    plan = raum.get("zeitplan") or []
    if nur_absenken:
        return _nur_absenken(raum, rz, umgebung, plan, ist, ergebnis,
                             fenster_hinweis)

    # 6 — Zeitplan, ggf. übersteuert, ggf. vorgezogen
    eintrag = zp.aktueller_eintrag(plan, jetzt, umgebung.get("schulfrei"),
                                   umgebung.get("arbeitstag"))
    modus = eintrag["modus"] if eintrag else "eco"
    basis = zp.modus_temperatur(raum, modus, frostschutz)
    begruendung = (texte.t("zeitplan", modus=texte.modus(modus),
                           uhrzeit=eintrag["start"]) if eintrag
                   else texte.t("zeitplan_leer"))

    # Ein Schalter kann den Zeitplan übersteuern – ein Homeoffice-Schalter
    # etwa hält das Büro auf Komfort, statt es vormittags abzusenken. Er
    # ersetzt den Modus des Plans; Anwesenheit und Heizkurve gelten weiter.
    # Das ist Absicht: Wer den Schalter anlässt und wegfährt, heizt kein
    # leeres Haus, und die Absenkung eines Fensters bleibt stärker.
    uebersteuerung = _uebersteuerung(raum, states_index, jetzt)
    if uebersteuerung:
        modus = uebersteuerung["modus"]
        basis = zp.modus_temperatur(raum, modus, frostschutz)
        begruendung = texte.t("uebersteuerung", name=uebersteuerung["name"],
                              fenster=uebersteuerung.get("fenster", ""),
                              modus=texte.modus(modus))
        if uebersteuerung["modus"] == "aus":
            return ergebnis("uebersteuert", frostschutz, begruendung,
                            ventil_zu=True)

    vorlauf = witterung.vorlaufminuten(umgebung.get("aussen"), einst["vorheizen"])
    if vorlauf and not uebersteuerung:
        kommend = zp.naechster_waermerer_wechsel(
            raum, jetzt, umgebung.get("schulfrei"), basis, frostschutz,
            umgebung.get("arbeitstag"))
        if kommend:
            zeitpunkt, kommender_eintrag = kommend
            if jetzt + timedelta(minutes=vorlauf) >= zeitpunkt:
                basis = zp.modus_temperatur(raum, kommender_eintrag["modus"], frostschutz)
                modus = kommender_eintrag["modus"]
                begruendung = texte.t(
                    "vorheizen", modus=texte.modus(kommender_eintrag["modus"]),
                    uhrzeit=kommender_eintrag["start"], minuten=vorlauf)

    # 7 — Anwesenheit
    zustand = modus
    if einst["anwesenheit"]["aktiv"] and raum.get("anwesenheit", True):
        besetzt, anwesenheits_grund = anwesenheit.raum_besetzt(
            raum, states_index, umgebung["personen"])
        if besetzt:
            rz["leer_seit"] = None
        else:
            leer_seit = _aus_iso(rz.get("leer_seit"))
            if leer_seit is None:
                leer_seit = jetzt
                rz["leer_seit"] = _iso(leer_seit)
            karenz = raum.get("karenz_min")
            if karenz is None:
                karenz = einst["anwesenheit"]["karenz_min"]
            karenz = int(karenz)
            leer_minuten = (jetzt - leer_seit).total_seconds() / 60.0
            if leer_minuten >= karenz:
                # Zählt allein der Melder, darf die Entfernung einer Person
                # nichts bewirken: Sonst liefe die Heizung an, sobald jemand
                # nach Hause fährt – auch wenn niemand den Raum betritt.
                schwelle = 0.0
                if einst["vorheizen"].get("aktiv") and not raum.get("nur_praesenz"):
                    schwelle = float(einst["vorheizen"].get("heimkehr_km", 0))
                heimweg, heimweg_grund = anwesenheit.kommt_heim(
                    raum, umgebung["personen"], schwelle)
                if heimweg:
                    begruendung = texte.t("heimkehr_erwartet", grund=heimweg_grund)
                    zustand = "heimkehr"
                else:
                    abwesend = float(raum["abwesend"])
                    if abwesend < basis:
                        basis = abwesend
                        zustand = "abwesend"
                        begruendung = texte.t("leer_seit_grund",
                                              grund=anwesenheits_grund,
                                              minuten=int(leer_minuten))
            else:
                rest = int(karenz - leer_minuten) + 1
                begruendung += texte.t("absenkung_in", grund=anwesenheits_grund,
                                       minuten=rest)

    # 8 — Heizkurve
    #
    # Nur auf gewollte Raumtemperaturen, nicht auf Sparwerte: Die Kurve soll
    # dafür sorgen, dass ein Raum sein Komfortziel auch bei Kälte erreicht.
    # Die Abwesenheitstemperatur ist dagegen ein reiner Haltewert – dort wäre
    # ein Aufschlag genau das Gegenteil dessen, wofür er gedacht ist.
    korrektur = 0.0
    if raum.get("heizkurve", True) and zustand in ("komfort", "eco", "nacht", "heimkehr"):
        korrektur = witterung.korrektur(umgebung.get("aussen"), einst["heizkurve"])
        if abs(korrektur) >= 0.05:
            vorzeichen = "+" if korrektur > 0 else ""
            begruendung += texte.t("heizkurve", vorzeichen=vorzeichen,
                                   grad=f"{korrektur:.1f}")

    if fenster_hinweis:
        begruendung += f" · {fenster_hinweis}"

    return ergebnis(zustand, basis + korrektur, begruendung, korrektur=korrektur)


def _eingestellter_sollwert(raum: dict, states_index: dict) -> float | None:
    """Was gerade an den Thermostaten des Raumes steht – Mittel über alle."""
    werte = []
    for entity_id in raum.get("thermostate") or []:
        eintrag = states_index.get(entity_id)
        if not eintrag:
            continue
        wert = ha_api.as_float((eintrag.get("attributes") or {}).get("temperature"))
        if wert is not None:
            werte.append(wert)
    return round(sum(werte) / len(werte), 1) if werte else None


def _nur_absenken(raum: dict, rz: dict, umgebung: dict, plan: list[dict],
                  ist: float | None, ergebnis, fenster_hinweis: str) -> dict:
    """Betriebsart „von Hand, nur zu festen Zeiten absenken“.

    Der Raum wird von Hand gestellt. Der Planer greift allein zu den
    Zeitpunkten des Plans ein und lässt ihn sonst in Ruhe – auch dann, wenn
    jemand hochdreht. Das ist der Unterschied zum geführten Zeitplan, bei dem
    der letzte Umschaltpunkt dauerhaft gilt.

    Beim ersten Lauf wird der zurückliegende Zeitpunkt nur vermerkt, nicht
    ausgeführt: Ein Add-on-Start um 22 Uhr soll nicht die Absenkung von 21 Uhr
    nachholen und dabei eine Handeinstellung überfahren.
    """
    jetzt = umgebung["jetzt"]
    einst = umgebung["einstellungen"]
    frostschutz = float(einst["frostschutz"])
    eingestellt = _eingestellter_sollwert(raum, umgebung["states_index"])

    def ruhen(begruendung: str) -> dict:
        # Angezeigt wird, was von Hand eingestellt ist. Meldet das Thermostat
        # keinen Sollwert – FRITZ-Geräte tun das in der Sommerpause nicht –,
        # bleibt das Feld leer, statt ersatzweise die Ist-Temperatur als Ziel
        # auszugeben. Eine Zahl, die kein Sollwert ist, liest sich wie einer.
        anzeige = eingestellt if eingestellt is not None else (ist or frostschutz)
        if fenster_hinweis:
            begruendung += f" · {fenster_hinweis}"
        return ergebnis("manuell", anzeige, begruendung, handwert=eingestellt,
                        nicht_schreiben=True, wiederherstellen=True)

    treffer = zp.letzter_zeitpunkt(plan, jetzt, umgebung.get("schulfrei"),
                                   umgebung.get("arbeitstag"))
    if not treffer:
        return ruhen(texte.t("hand_ohne_punkt"))

    zeitpunkt, eintrag = treffer
    zuletzt = _aus_iso(rz.get("zuletzt_ausgeloest"))
    naechster = zp.naechster_wechsel(plan, jetzt, umgebung.get("schulfrei"),
                                     umgebung.get("arbeitstag"))
    ausblick = (texte.t("hand_ausblick", uhrzeit=naechster[1]["start"])
                if naechster else "")

    if zuletzt is None:
        rz["zuletzt_ausgeloest"] = _iso(zeitpunkt)
        return ruhen(texte.t("hand_gestellt", ausblick=ausblick))

    if zeitpunkt > zuletzt:
        faellig_seit = jetzt - zeitpunkt
        if faellig_seit <= timedelta(minutes=AUSLOESE_FENSTER_MIN):
            ziel = zp.modus_temperatur(raum, eintrag["modus"], frostschutz)
            # Genau dieser Eingriff soll die Handeinstellung überschreiben –
            # sonst hielte ihn die Handeingriff-Erkennung für einen Konflikt.
            return ergebnis("absenkung", ziel,
                            texte.t("hand_absenkung", uhrzeit=eintrag["start"],
                                    modus=f"{ziel:.1f} °C"), erzwingen=True)
        # Verpasst – etwa weil das Add-on stand. Nicht nachholen, nur vermerken.
        rz["zuletzt_ausgeloest"] = _iso(zeitpunkt)
        return ruhen(texte.t("hand_verpasst", uhrzeit=eintrag["start"],
                             ausblick=ausblick))

    return ruhen(texte.t("hand_gestellt", ausblick=ausblick))


# ------------------------------------------------------------- Ausführung ----

def _thermostat_grenzen(attrs: dict) -> tuple[float, float]:
    return (ha_api.as_float(attrs.get("min_temp")) or 5.0,
            ha_api.as_float(attrs.get("max_temp")) or 30.0)


def anwenden(raum: dict, entscheidung: dict, state: dict, umgebung: dict,
             protokoll) -> list[dict]:
    """Die Entscheidung an die Thermostate des Raumes weitergeben.

    Gibt zurück, was tatsächlich geschaltet wurde – für Protokoll und Anzeige.
    """
    jetzt = umgebung["jetzt"]
    einst = umgebung["einstellungen"]
    states_index = umgebung["states_index"]
    trockenlauf = bool(einst.get("trockenlauf"))
    ventil_zu = bool(entscheidung.get("ventil_zu"))
    aktionen = []

    for entity_id in raum.get("thermostate") or []:
        eintrag = states_index.get(entity_id)
        if not eintrag:
            protokoll(raum["name"], texte.t("log_fehlt"),
                      texte.t("fehlt_entity", entity=entity_id))
            continue
        attrs = eintrag.get("attributes") or {}
        gedaechtnis = state["thermostate"].setdefault(entity_id, {})
        zuletzt_am = _aus_iso(gedaechtnis.get("gesetzt_am"))
        frisch = bool(zuletzt_am and (jetzt - zuletzt_am) < timedelta(minutes=BESTAETIGUNG_MIN))
        ist_soll_jetzt = ha_api.as_float(attrs.get("temperature"))

        # -- Handeinstellung vor einem Sonderzustand sichern ------------------
        if entscheidung.get("merken") and gedaechtnis.get("vor_sonderzustand") is None:
            if ist_soll_jetzt is not None:
                gedaechtnis["vor_sonderzustand"] = ist_soll_jetzt

        # -- Raum ruht: nur eine gesicherte Handeinstellung zurückgeben -------
        if entscheidung.get("nicht_schreiben"):
            gesichert = gedaechtnis.get("vor_sonderzustand")
            if entscheidung.get("wiederherstellen") and gesichert is not None:
                gedaechtnis["vor_sonderzustand"] = None
                if trockenlauf:
                    aktionen.append({"entity_id": entity_id, "aktion": "zurück",
                                     "wert": gesichert, "trocken": True})
                elif ist_soll_jetzt is None or abs(ist_soll_jetzt - gesichert) >= _schritt() / 2:
                    if ha_api.set_temperature(entity_id, gesichert):
                        gedaechtnis.update({"soll": gesichert, "gesetzt_am": _iso(jetzt),
                                            "hvac": "heat"})
                        aktionen.append({"entity_id": entity_id, "aktion": "zurück",
                                         "wert": gesichert})
                        protokoll(raum["name"],
                                  texte.t("zurueck_auf", grad=f"{gesichert:.1f}"),
                                  texte.t("hand_zurueck", grad=f"{gesichert:.1f}"),
                                  entity_id)
            continue

        # -- Ventil schließen (Sommer / Raum abgeschaltet) --------------------
        #
        # Nicht jedes Thermostat lässt sich abschalten. Manche Matter-Geräte
        # nehmen den Befehl an und springen eine Minute später von selbst
        # zurück auf „heat“. Wer das nicht bemerkt, schickt bei jedem Takt
        # aufs Neue ein „aus“ – Dauerfeuer, das nichts bewirkt außer die
        # Batterie zu leeren. Nach zwei vergeblichen Versuchen weicht der
        # Planer deshalb dauerhaft auf den Frostschutzwert aus; das schließt
        # das Ventil genauso, nur über den Sollwert.
        kann_aus = "off" in (attrs.get("hvac_modes") or [])
        if ventil_zu and kann_aus and not gedaechtnis.get("aus_vergeblich"):
            if eintrag.get("state") == "off":
                gedaechtnis.update({"hvac": "off", "aus_fehlversuche": 0})
                continue
            if frisch and gedaechtnis.get("hvac") == "off":
                continue  # eben erst geschickt, Thermostat meldet noch nicht zurück
            if gedaechtnis.get("hvac") == "off":
                # Wir hatten ausgeschaltet, das Gerät steht wieder auf „heat“.
                fehlversuche = gedaechtnis.get("aus_fehlversuche", 0) + 1
                gedaechtnis["aus_fehlversuche"] = fehlversuche
                if fehlversuche >= 2:
                    gedaechtnis["aus_vergeblich"] = True
                    protokoll(raum["name"], texte.t("log_bleibt_an"),
                              texte.t("nicht_uebernommen",
                                      name=attrs.get("friendly_name", entity_id)),
                              entity_id)
                    # kein continue: unten wird jetzt der Sollwert gesetzt
                else:
                    if trockenlauf:
                        aktionen.append({"entity_id": entity_id, "aktion": "aus",
                                         "trocken": True})
                        continue
                    if ha_api.set_hvac_mode(entity_id, "off"):
                        gedaechtnis.update({"hvac": "off", "gesetzt_am": _iso(jetzt)})
                        aktionen.append({"entity_id": entity_id, "aktion": "aus"})
                    continue
            else:
                if trockenlauf:
                    aktionen.append({"entity_id": entity_id, "aktion": "aus",
                                     "trocken": True})
                    continue
                if ha_api.set_hvac_mode(entity_id, "off"):
                    gedaechtnis.update({"hvac": "off", "gesetzt_am": _iso(jetzt),
                                        "soll": None})
                    aktionen.append({"entity_id": entity_id, "aktion": "aus"})
                    protokoll(raum["name"], "aus", entscheidung["begruendung"], entity_id)
                continue

        ziel = float(entscheidung["ziel"])
        unten, oben = _thermostat_grenzen(attrs)
        ziel = _runden(max(unten, min(oben, ziel)))
        ist_soll = ha_api.as_float(attrs.get("temperature"))

        # -- Handeingriff erkennen -------------------------------------------
        # Weicht der Sollwert am Gerät von unserem zuletzt geschriebenen Wert
        # ab, hat jemand von Hand gedreht. Das gilt bis zum nächsten
        # Zeitplanwechsel, danach führt wieder der Plan.
        erzwingen = bool(entscheidung.get("erzwingen"))
        if einst.get("manuell_respektieren") and not frisch and not erzwingen:
            geschrieben = gedaechtnis.get("soll")
            vor_schreiben = gedaechtnis.get("vor_schreiben")
            # Steht am Gerät noch genau der Wert, den es vor unserem Befehl
            # hatte, dann hat niemand gedreht – das Gerät hat den Befehl
            # schlicht nicht umgesetzt. Das als Handeingriff zu werten wäre
            # der teuerste Irrtum: Der Planer zöge sich zurück und der Raum
            # bliebe auf einem Wert, den niemand gewollt hat.
            nicht_umgesetzt = (vor_schreiben is not None and ist_soll is not None
                               and abs(ist_soll - vor_schreiben) < _schritt() / 2)
            if nicht_umgesetzt and geschrieben is not None \
                    and abs(ist_soll - ziel) >= _schritt():
                fehler = gedaechtnis.get("schreib_fehler", 0) + 1
                gedaechtnis["schreib_fehler"] = fehler
                gedaechtnis["fehler_zuletzt"] = _iso(jetzt)
                if fehler <= FEHLSCHLAEGE_BIS_SCHONUNG:
                    protokoll(raum["name"], texte.t("log_nicht_bestaetigt"),
                              f"{attrs.get('friendly_name', entity_id)}: "
                              + texte.t("nicht_bestaetigt", grad=f"{geschrieben:.1f}")
                              + f" ({ist_soll:.1f} °C)", entity_id)
            elif (geschrieben is not None and ist_soll is not None
                    and abs(ist_soll - geschrieben) >= _schritt()
                    and abs(ist_soll - ziel) >= _schritt()):
                manuell_bis = umgebung["raum_wechsel"].get(raum["id"])
                gedaechtnis["manuell_bis"] = _iso(manuell_bis)
                gedaechtnis["soll"] = ist_soll
                aktionen.append({"entity_id": entity_id, "aktion": "manuell",
                                 "wert": ist_soll})
                protokoll(raum["name"], texte.t("log_manuell"),
                          texte.t("hand_erkannt", grad=f"{ist_soll:.1f}"),
                          entity_id)
                _fremdprogramm_merken(gedaechtnis, ist_soll, jetzt, raum,
                                      entity_id, attrs, protokoll)
                continue
        manuell_bis = _aus_iso(gedaechtnis.get("manuell_bis"))
        if manuell_bis and manuell_bis > jetzt and not erzwingen:
            continue
        if manuell_bis:
            gedaechtnis["manuell_bis"] = None
            # Der Zeitplan greift wieder, und niemand hat dazwischengefunkt:
            # Damit ist der Verdacht auf ein Fremdprogramm erledigt.
            for schluessel in ("hand_wann", "hand_wert", "fremd_gemeldet"):
                gedaechtnis.pop(schluessel, None)

        # -- Betriebsart sicherstellen ---------------------------------------
        if eintrag.get("state") == "off" and not trockenlauf:
            if not frisch or gedaechtnis.get("hvac") != "heat":
                ha_api.set_hvac_mode(entity_id, "heat")
                gedaechtnis["hvac"] = "heat"
                gedaechtnis["gesetzt_am"] = _iso(jetzt)

        # -- Sollwert nur auf Flanke -----------------------------------------
        if ist_soll is not None and abs(ist_soll - ziel) < _schritt() / 2:
            # Angekommen: Gedächtnis auffrischen und den Fehlerzähler löschen.
            gedaechtnis.update({"soll": ziel, "schreib_fehler": 0,
                                "fehler_zuletzt": None, "vor_schreiben": None})
            continue
        if frisch and gedaechtnis.get("soll") is not None \
                and abs(gedaechtnis["soll"] - ziel) < _schritt() / 2:
            continue  # bereits geschickt, Bestätigung steht noch aus

        if trockenlauf:
            aktionen.append({"entity_id": entity_id, "aktion": "soll",
                             "wert": ziel, "vorher": ist_soll, "trocken": True})
            continue

        # Ein Gerät, das sich schon mehrfach verweigert hat, bekommt nur noch
        # in größerem Abstand einen Versuch. Sonst füllt es bei jedem Takt das
        # Protokoll, ohne dass sich etwas ändert.
        fehler = gedaechtnis.get("schreib_fehler", 0)
        if fehler >= FEHLSCHLAEGE_BIS_SCHONUNG:
            letzter = _aus_iso(gedaechtnis.get("fehler_zuletzt"))
            if letzter and (jetzt - letzter) < timedelta(minutes=SCHONFRIST_MIN):
                continue

        gedaechtnis["vor_schreiben"] = ist_soll
        if ha_api.set_temperature(entity_id, ziel):
            gedaechtnis.update({"soll": ziel, "gesetzt_am": _iso(jetzt), "hvac": "heat"})
            # Fehlerzähler nur zurücksetzen, wenn der Wert auch angekommen ist –
            # das entscheidet sich erst beim nächsten Takt.
            aktionen.append({"entity_id": entity_id, "aktion": "soll",
                             "wert": ziel, "vorher": ist_soll})
            protokoll(raum["name"],
                      f"{ziel:.1f} °C",
                      entscheidung["begruendung"], entity_id)
        else:
            gedaechtnis["schreib_fehler"] = fehler + 1
            gedaechtnis["fehler_zuletzt"] = _iso(jetzt)
            if fehler + 1 <= FEHLSCHLAEGE_BIS_SCHONUNG:
                grund = ""
                preset = attrs.get("preset_mode")
                if preset == "summer":
                    grund = " – das Gerät steht in der Sommerpause"
                protokoll(raum["name"], "fehlgeschlagen",
                          f"{attrs.get('friendly_name', entity_id)} nimmt den "
                          f"Sollwert {ziel:.1f} °C nicht an{grund}", entity_id)

    return aktionen


# ----------------------------------------------------------------- Takt ----

def takt(config: dict, state: dict, protokoll) -> dict:
    """Ein vollständiger Regeldurchlauf über alle Räume."""
    jetzt = _jetzt()
    einst = config["einstellungen"]

    if not ha_api.ist_bereit():
        _LOGGER.info("Home Assistant ist noch nicht bereit – Takt ausgesetzt")
        return {"zeit": _iso(jetzt), "fehler": "Home Assistant startet gerade",
                "startet": True, "raeume": []}

    states = ha_api.get_states()
    if not states:
        _LOGGER.warning("Keine Zustände von Home Assistant erhalten – Takt übersprungen")
        return {"zeit": _iso(jetzt), "fehler": "Home Assistant nicht erreichbar",
                "raeume": []}
    states_index = {s.get("entity_id"): s for s in states}

    aussen = witterung.aussentemperatur(states_index, einst.get("aussen_entity", ""))
    letzter_takt = _aus_iso(state.get("letzter_takt"))
    sekunden = (jetzt - letzter_takt).total_seconds() if letzter_takt else 0.0

    vorgeschichte = state.get("aussen_gedaempft")
    if vorgeschichte is None and aussen is not None:
        # Erster Lauf: Die Dämpfung braucht einen Anlauf. Ohne ihn beginnt sie
        # beim aktuellen Messwert – an einem kühlen Sommertag hieße das
        # Heizbetrieb, obwohl die Woche davor mild war.
        vorgeschichte = ha_api.historien_mittel(
            einst.get("aussen_entity", ""),
            max(24.0, float(einst["daempfung_stunden"]) * 2))
        if vorgeschichte is not None:
            protokoll(texte.t("log_alle_raeume"), texte.t("log_anlauf"),
                      texte.t("log_gedaempft_uebernommen",
                              grad=f"{vorgeschichte:.1f}"))

    gedaempft = witterung.daempfen(vorgeschichte, aussen,
                                   sekunden, float(einst["daempfung_stunden"]))
    sommer = witterung.sommerbetrieb(gedaempft, einst["sommer"],
                                     bool(state.get("sommerbetrieb")))
    if sommer != bool(state.get("sommerbetrieb")):
        protokoll(texte.t("log_alle_raeume"),
                  texte.t("log_sommer_ein" if sommer else "log_sommer_aus"),
                  texte.t("log_gedaempft", grad=f"{gedaempft:.1f}")
                  if gedaempft is not None else texte.t("log_aussen_unbekannt"))

    # Läuft gerade eine Party? Abgelaufene Tasten räumen sich selbst weg.
    party_bis = _aus_iso(state.get("party_bis"))
    if party_bis and party_bis <= jetzt:
        protokoll(texte.t("log_alle_raeume"), texte.t("log_party_vorbei_was"),
                  texte.t("log_party_vorbei"))
        party_bis = None
        state["party_bis"] = None

    urlaub = _bool_state(states_index, einst.get("urlaub_entity", "")) or False
    schulfrei = _bool_state(states_index, einst.get("schulfrei_entity", ""))
    arbeitstag = _bool_state(states_index, einst.get("arbeitstag_entity", ""))
    heim = ha_api.zone_home(states)
    zonen = anwesenheit.zonennamen(states_index)
    personen = anwesenheit.personen_status(states_index, heim, zonen,
                                           einst.get("haushalt"))
    anwesenheit.bewegung_fortschreiben(
        personen, state.setdefault("personen", {}), jetzt,
        float(einst["vorheizen"].get("heimkehr_annaeherung_km", 0.3)))

    # Je Raum: wann der nächste Umschaltpunkt fällig ist und worauf er stellt.
    # Der Zeitpunkt allein sagt wenig – wer auf die Übersicht schaut, will
    # wissen, was gleich passiert.
    raum_wechsel, naechste = {}, {}
    for raum in config["raeume"]:
        treffer = zp.naechster_wechsel(raum.get("zeitplan") or [], jetzt, schulfrei,
                                       arbeitstag)
        raum_wechsel[raum["id"]] = treffer[0] if treffer else jetzt + timedelta(hours=12)
        if treffer:
            zeitpunkt, eintrag = treffer
            naechste[raum["id"]] = {
                "zeit": _iso(zeitpunkt),
                "uhrzeit": eintrag["start"],
                "modus": eintrag["modus"],
                "ziel": zp.modus_temperatur(raum, eintrag["modus"],
                                            float(einst["frostschutz"])),
            }

    umgebung = {
        "jetzt": jetzt, "einstellungen": einst, "states_index": states_index,
        "aussen": aussen, "aussen_gedaempft": gedaempft, "sommerbetrieb": sommer,
        "urlaub": urlaub, "schulfrei": schulfrei, "arbeitstag": arbeitstag,
        "personen": personen,
        "raum_wechsel": raum_wechsel, "party_bis": party_bis,
    }

    automatik = bool(einst.get("automatik"))
    ergebnisse = []
    for raum in config["raeume"]:
        rz = state["raeume"].setdefault(raum["id"], {})
        entscheidung = entscheide(raum, rz, umgebung)
        aktionen = []
        if automatik:
            aktionen = anwenden(raum, entscheidung, state, umgebung, protokoll)
        vorher = rz.get("zustand")
        if vorher != entscheidung["zustand"]:
            rz["seit"] = _iso(jetzt)
        rz.update({
            "zustand": entscheidung["zustand"],
            "ziel": entscheidung["ziel"],
            "ist": entscheidung.get("ist"),
            "begruendung": entscheidung["begruendung"],
            "aktualisiert": _iso(jetzt),
        })
        naechster = raum_wechsel.get(raum["id"])
        kommend = naechste.get(raum["id"])
        ergebnisse.append({
            "id": raum["id"], "name": raum["name"],
            "zustand": entscheidung["zustand"], "ziel": entscheidung["ziel"],
            "ist": entscheidung.get("ist"), "begruendung": entscheidung["begruendung"],
            "handwert": entscheidung.get("handwert"),
            "uebersteuerung": uebersteuerung_lage(raum, states_index, jetzt),
            "seit": rz.get("seit"), "aktionen": aktionen,
            "naechster_wechsel": _iso(naechster),
            "naechster_modus": (kommend or {}).get("modus"),
            "naechstes_ziel": (kommend or {}).get("ziel"),
            "naechste_uhrzeit": (kommend or {}).get("uhrzeit"),
            "thermostate": [
                {
                    "entity_id": eid,
                    "name": (states_index.get(eid, {}).get("attributes") or {}).get(
                        "friendly_name", eid),
                    "soll": ha_api.as_float(
                        (states_index.get(eid, {}).get("attributes") or {}).get("temperature")),
                    "ist": ha_api.as_float(
                        (states_index.get(eid, {}).get("attributes") or {}).get(
                            "current_temperature")),
                    "betriebsart": states_index.get(eid, {}).get("state"),
                    "manuell_bis": state["thermostate"].get(eid, {}).get("manuell_bis"),
                    "vorhanden": eid in states_index,
                }
                for eid in raum.get("thermostate") or []
            ],
        })

    # Der Wachhund läuft nach den Räumen: Er soll auch ein Thermostat sehen,
    # das gerade eben erst als fehlend aufgefallen ist.
    try:
        stoerungen = wachhund.pruefen(config, states_index, jetzt, einst,
                                      _batterien_holen(jetzt, state, states_index),
                                      state.get("thermostate") or {},
                                      sommerbetrieb=sommer)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Überwachung fehlgeschlagen: %s", err)
        stoerungen = []

    # Der Kessel zuletzt: Er soll dem folgen, was die Räume gerade tatsächlich
    # bekommen haben, nicht dem, was vor dem Durchlauf geplant war. Steht die
    # Automatik still, rührt er sich so wenig wie die Thermostate – ein Planer,
    # der nichts stellt, darf auch die Anlage nicht umschalten.
    kessel_lage = {"aktiv": False}
    if automatik:
        try:
            kessel_lage = kessel.fuehren(
                {"zeit": _iso(jetzt), "sommerbetrieb": sommer,
                 "schulfrei": schulfrei, "arbeitstag": arbeitstag,
                 "raeume": ergebnisse},
                config, state, protokoll)
        except Exception as err:  # noqa: BLE001
            # Der Anlagenmanager ist ein zweites Add-on. Ist es gerade beim
            # Neustart, darf das nicht den ganzen Takt kosten – die Räume sind
            # zu diesem Zeitpunkt längst gestellt.
            _LOGGER.warning("Kesselführung fehlgeschlagen: %s", err)
            kessel_lage = {"aktiv": True, "erreichbar": False,
                           "fehler": str(err)}

    state.update({
        "aussen_gedaempft": round(gedaempft, 2) if gedaempft is not None else None,
        "sommerbetrieb": sommer,
        "letzter_takt": _iso(jetzt),
    })

    return {
        "zeit": _iso(jetzt),
        "aussen": aussen,
        "aussen_gedaempft": round(gedaempft, 2) if gedaempft is not None else None,
        "sommerbetrieb": sommer,
        "urlaub": urlaub,
        "schulfrei": schulfrei,
        "arbeitstag": arbeitstag,
        "party_bis": _iso(party_bis),
        "automatik": automatik,
        "trockenlauf": bool(einst.get("trockenlauf")),
        "personen": personen,
        "raeume": ergebnisse,
        "stoerungen": stoerungen,
        "kessel": kessel_lage,
    }


_BATTERIEN: dict = {"stand": None, "geholt": None}


def _batterien_holen(jetzt: datetime, state: dict, states_index: dict) -> dict:
    """Die Zuordnung Thermostat → Batterieanzeige, einmal je Stunde erneuert.

    Sie ändert sich nur, wenn Geräte dazukommen – eine Template-Abfrage in
    jedem Takt wäre Verschwendung.

    **Sofort erneuert wird sie, wenn eine gemerkte Batterieanzeige verschwunden
    ist.** Sonst hielte der Planer bis zu einer Stunde an einer Entität fest,
    die es nicht mehr gibt – und meldete währenddessen eine schwache Batterie
    als behoben. Genau das geschah am 25.08.2026, als die Entitäten zweier
    umgezogener Thermostate ihren alten Einbauort im Namen verloren.
    """
    letzte = _BATTERIEN["geholt"]
    bekannt = _BATTERIEN["stand"]
    verschwunden = bool(bekannt) and any(
        batterie not in states_index for batterie in bekannt.values())
    if bekannt is None or letzte is None or verschwunden or \
            (jetzt - letzte) > timedelta(hours=1):
        if verschwunden:
            _LOGGER.info("Eine Batterieanzeige ist verschwunden – "
                         "die Zuordnung wird neu geholt")
        _BATTERIEN["stand"] = wachhund.batterien_je_thermostat()
        _BATTERIEN["geholt"] = jetzt
    return _BATTERIEN["stand"]
