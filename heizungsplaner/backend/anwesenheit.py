"""Wer ist da, wer kommt gleich – und was heißt das für einen einzelnen Raum.

Ein Raum gilt als besetzt, wenn eine der für ihn zuständigen Personen zu Hause
ist oder ein Präsenzmelder im Raum anschlägt. Sind für einen Raum keine
Personen hinterlegt, zählt die ganze Familie.

Zwei Eigenheiten dieses Hauses sind berücksichtigt:

* Die Tracker melden unterwegs eigene Standzonen statt ``not_home``. Deshalb
  wird ausschließlich auf ``home`` geprüft – eine Prüfung auf ``not_home``
  würde nie greifen.
* Die Heimkehr wird nicht abgewartet, sondern über die Entfernung zur
  Heimzone vorhergesehen, damit der Raum bei der Ankunft schon warm ist.
"""
from __future__ import annotations

import math
import texte

ERDRADIUS_KM = 6371.0

# Über diese Spanne wird geprüft, ob jemand näher kommt. Kürzer wäre zu sehr
# vom GPS-Rauschen abhängig, länger würde die Heimkehr zu spät bemerken.
ANNAEHERUNG_FENSTER_MIN = 15


def entfernung_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Großkreisentfernung zweier Punkte in Kilometern."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * ERDRADIUS_KM * math.asin(math.sqrt(a))


def zonennamen(states_index: dict) -> set[str]:
    """Die Anzeigenamen aller Zonen außer der Heimzone.

    Eine Person, die in einer Zone steht, meldet deren Namen als Zustand –
    „Realschule“ statt ``not_home``. Genau daran lässt sich erkennen, dass
    jemand angekommen ist und nicht unterwegs.
    """
    namen = set()
    for entity_id, eintrag in states_index.items():
        if not entity_id.startswith("zone.") or entity_id == "zone.home":
            continue
        name = (eintrag.get("attributes") or {}).get("friendly_name")
        if name:
            namen.add(name)
    return namen


def personen_status(states_index: dict, heim: tuple[float, float, float] | None,
                    zonen: set[str] | None = None,
                    haushalt: list[str] | None = None) -> dict:
    """Für jede Person: zu Hause? wie weit weg? in einer Zone?

    ``haushalt`` grenzt ein, wer überhaupt zählt. **Leer oder None heißt: alle**
    – das ist das bisherige Verhalten und bleibt die Vorgabe.

    Die Einschränkung gibt es, weil in einer gewachsenen Installation mehr
    ``person.*``-Entitäten stehen, als Menschen im Haus wohnen: Gäste, alte
    Konten, Personen ohne Gerätetracker. Gerade die letzte Sorte ist heikel –
    sie steht dauerhaft auf "unknown" oder "home" und hielte jeden Raum für
    besetzt, womit die Absenkung bei Abwesenheit lautlos nie mehr griffe.
    """
    zonen = zonen if zonen is not None else zonennamen(states_index)
    erlaubt = {p for p in (haushalt or []) if p}
    out = {}
    for entity_id, eintrag in states_index.items():
        if not entity_id.startswith("person."):
            continue
        if erlaubt and entity_id not in erlaubt:
            continue
        attrs = eintrag.get("attributes", {}) or {}
        zustand = eintrag.get("state")
        zuhause = zustand == "home"
        distanz = None
        if heim and not zuhause:
            try:
                lat = float(attrs.get("latitude"))
                lon = float(attrs.get("longitude"))
            except (TypeError, ValueError):
                lat = lon = None
            if lat is not None and lon is not None:
                distanz = round(entfernung_km(lat, lon, heim[0], heim[1]), 2)
        out[entity_id] = {
            "name": attrs.get("friendly_name", entity_id),
            "zuhause": zuhause,
            "zustand": zustand,
            "entfernung_km": distanz,
            "in_zone": zustand if (not zuhause and zustand in zonen) else None,
            "naehert_sich": False,
        }
    return out


def bewegung_fortschreiben(personen: dict, gedaechtnis: dict, jetzt,
                           mindest_annaeherung_km: float) -> None:
    """Je Person merken, wie weit sie weg war, und daraus die Richtung ableiten.

    Ohne diese Prüfung wäre die Entfernung allein aussagelos: Wer eine
    Schule in einem Kilometer Entfernung besucht, ist den ganzen Vormittag
    „nah“, ohne je auf dem Heimweg zu sein.
    """
    from datetime import timedelta

    grenze = jetzt - timedelta(minutes=ANNAEHERUNG_FENSTER_MIN)
    for entity_id, person in personen.items():
        eintrag = gedaechtnis.setdefault(entity_id, {})
        verlauf = [(stempel, wert) for stempel, wert in (eintrag.get("verlauf") or [])]

        distanz = person.get("entfernung_km")
        if distanz is None:
            # Ohne Standort lässt sich nichts über die Richtung sagen. Der
            # Verlauf bleibt stehen, damit ein einzelner Aussetzer ihn nicht
            # verwirft.
            continue

        frueher = [wert for stempel, wert in verlauf
                   if _zeit(stempel) and _zeit(stempel) <= grenze]
        if frueher:
            # Der größte Wert im Fenster: Wer zwischendurch näher war und sich
            # wieder entfernt hat, gilt nicht als heimkehrend.
            person["naehert_sich"] = (max(frueher) - distanz) >= mindest_annaeherung_km

        verlauf.append((jetzt.isoformat(timespec="seconds"), distanz))
        eintrag["verlauf"] = [
            [stempel, wert] for stempel, wert in verlauf
            if _zeit(stempel) and _zeit(stempel) >= jetzt - timedelta(
                minutes=ANNAEHERUNG_FENSTER_MIN * 3)][-40:]


def _zeit(text):
    from datetime import datetime
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def zustaendige(raum: dict, alle_personen: dict) -> list[str]:
    """Die für einen Raum maßgeblichen Personen; leere Liste heißt: alle."""
    personen = [p for p in (raum.get("personen") or []) if p in alle_personen]
    return personen or list(alle_personen.keys())


def praesenz_lage(raum: dict, states_index: dict) -> tuple[bool, int]:
    """Meldet einer der Melder Bewegung, und wie viele antworten überhaupt?

    Die Zahl der antwortenden Melder wird gebraucht, um einen Raum nicht
    stillschweigend für immer als leer zu führen, wenn sein einziger Melder
    fehlt oder ausgefallen ist.
    """
    verlaesslich = 0
    for entity_id in raum.get("praesenz") or []:
        eintrag = states_index.get(entity_id)
        zustand = eintrag.get("state") if eintrag else None
        if zustand not in ("on", "off"):
            continue
        verlaesslich += 1
        if zustand == "on":
            return True, verlaesslich
    return False, verlaesslich


def praesenz_aktiv(raum: dict, states_index: dict) -> bool:
    return praesenz_lage(raum, states_index)[0]


def raum_besetzt(raum: dict, states_index: dict, personen: dict) -> tuple[bool, str]:
    """Ist gerade jemand für diesen Raum da? Mit Begründung für das Protokoll.

    Mit ``nur_praesenz`` zählt allein der Melder im Raum. Das ist für Räume
    gedacht, die nur zeitweise benutzt werden – ein Büro etwa. Ohne diese
    Einstellung wäre ein Raum ohne Personenzuordnung immer belegt, sobald
    irgendwer im Haus ist, und der Melder bliebe wirkungslos.
    """
    bewegung, verlaesslich = praesenz_lage(raum, states_index)
    if bewegung:
        return True, texte.t("praesenz_bewegung")
    if raum.get("nur_praesenz"):
        # Kein antwortender Melder heißt nicht „niemand da“. Sonst stünde der
        # Raum nach einem ausgefallenen oder falsch eingetragenen Melder
        # dauerhaft auf der Abwesenheitstemperatur, ohne dass es auffällt.
        if verlaesslich == 0:
            return True, texte.t("praesenz_stumm")
        return False, texte.t("praesenz_niemand")
    for entity_id in zustaendige(raum, personen):
        if personen[entity_id]["zuhause"]:
            return True, texte.t("person_zuhause",
                                 name=personen[entity_id]["name"])
    return False, texte.t("niemand_zuhause")


def kommt_heim(raum: dict, personen: dict, schwelle_km: float) -> tuple[bool, str]:
    """Ist eine zuständige Person auf dem Heimweg?

    Drei Bedingungen, alle nötig:

    * näher als die Schwelle,
    * **nicht in einer Zone** – wer in der Schule oder im Büro sitzt, ist dort
      angekommen, auch wenn das nur einen Kilometer entfernt ist,
    * **erkennbar näher kommend** – die Entfernung muss über die letzten
      Minuten abgenommen haben.

    Die Entfernung allein genügt nicht: Eine Schule in Sichtweite hielte den
    Raum sonst den ganzen Schultag auf Komforttemperatur.
    """
    if schwelle_km <= 0:
        return False, ""
    naechste, name = None, ""
    for entity_id in zustaendige(raum, personen):
        person = personen[entity_id]
        distanz = person.get("entfernung_km")
        if person["zuhause"] or distanz is None:
            continue
        if person.get("in_zone") or not person.get("naehert_sich"):
            continue
        if naechste is None or distanz < naechste:
            naechste, name = distanz, person["name"]
    if naechste is not None and naechste <= schwelle_km:
        return True, texte.t("heimkehr_naehert", name=name,
                             km=f"{naechste:.1f}")
    return False, ""
