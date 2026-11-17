"""Heizenergie je Raum – geschätzt, nicht gemessen.

Gemessen wird nur, was der Kessel verbrennt: Brennerlaufzeit mal
Düsendurchsatz, verbucht im Tankteil. Welcher Raum davon wie viel bekommen
hat, sagt kein Gerät – dafür müsste jedes Thermostat melden, wie weit sein
Ventil offen steht, und das tun die üblichen Geräte nicht.

Geschätzt wird deshalb über den Wärmeverlust: Ein Raum, der 23 °C halten
soll, während draußen 3 °C sind, verliert in einer Stunde etwa doppelt so viel
wie einer bei 13 °C Unterschied. Über die Zeit aufsummiert ergibt das je Raum
ein Gewicht – Gradstunden mal Raumfaktor –, und nach diesen Gewichten wird der
tatsächlich verbrannte Liter verteilt. Ein fester Anteil geht vorher ans
Warmwasser; in Stunden, in denen kein Raum geheizt wird (Sommer), geht alles
dorthin.

Was die Schätzung nicht weiß: wie groß die Heizkörper sind, wie gut ein Raum
gedämmt ist und dass Räume sich gegenseitig mitheizen. Der Raumfaktor in den
Raumeinstellungen fängt das Grobe ab. Mit 20–30 % Abweichung je Raum muss man
rechnen; für die Reihenfolge und den Verlauf über die Monate reicht es.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

# Ein Liter Heizöl EL enthält rund 10 kWh (Heizwert). Was der Kessel davon
# als Wärme abgibt, ist weniger – verteilt wird aber, was bezahlt wurde.
KWH_JE_LITER = 10.0
WARMWASSER_ANTEIL = 0.15

# Zwischen zwei Takten liegen ein paar Minuten. Eine längere Lücke (Neustart,
# Ausfall) wird nicht als Heizzeit gezählt – sonst verteilte die erste Stunde
# nach einem Ausfall den Verbrauch nach einem Zustand, den niemand kennt.
MAX_LUECKE_MIN = 30

TAGE_BEHALTEN = 62
RUHT = ("sommer", "aus", "gesperrt")
WARMWASSER = "_warmwasser"


def _zustand(state: dict) -> dict:
    e = state.setdefault("energie", {})
    e.setdefault("letzter", None)
    e.setdefault("offen", {})          # raum_id → Gewicht seit der letzten Buchung
    e.setdefault("konten", {})         # raum_id → {kwh, eur, tage, monate, ...}
    return e


def _konto(e: dict, raum_id: str) -> dict:
    k = e["konten"].setdefault(raum_id, {})
    k.setdefault("kwh", 0.0)
    k.setdefault("eur", 0.0)
    k.setdefault("tage", {})
    k.setdefault("monate", {})
    k.setdefault("tage_eur", {})
    k.setdefault("monate_eur", {})
    return k


def _buchen(k: dict, kwh: float, eur: float | None, heute: str) -> None:
    k["kwh"] = round(k["kwh"] + kwh, 3)
    k["tage"][heute] = round(k["tage"].get(heute, 0.0) + kwh, 3)
    k["monate"][heute[:7]] = round(k["monate"].get(heute[:7], 0.0) + kwh, 3)
    if eur is not None:
        k["eur"] = round(k["eur"] + eur, 3)
        k["tage_eur"][heute] = round(k["tage_eur"].get(heute, 0.0) + eur, 3)
        k["monate_eur"][heute[:7]] = round(k["monate_eur"].get(heute[:7], 0.0) + eur, 3)
    grenze = (date.fromisoformat(heute) - timedelta(days=TAGE_BEHALTEN)).isoformat()
    for verlauf in (k["tage"], k["tage_eur"]):
        for tag in [t for t in verlauf if t < grenze]:
            verlauf.pop(tag, None)


def gewicht(raum: dict, ergebnis: dict, aussen: float | None, stunden: float) -> float:
    """Gradstunden mal Raumfaktor – das, was dieser Raum seit dem letzten Takt
    an Wärme gezogen haben dürfte, in willkürlicher Einheit."""
    if aussen is None or stunden <= 0 or ergebnis.get("zustand") in RUHT:
        return 0.0
    innen = ergebnis.get("ist")
    if innen is None:
        innen = ergebnis.get("ziel")
    if innen is None:
        return 0.0
    faktor = float(raum.get("energie_faktor") or 1.0)
    return max(0.0, float(innen) - float(aussen)) * faktor * stunden


def verteilen(e: dict, liter: float, preis: float | None, heute: str,
              anteil_ww: float = WARMWASSER_ANTEIL,
              kwh_je_liter: float = KWH_JE_LITER) -> None:
    """Einen verbrannten Liter auf Warmwasser und Räume aufteilen."""
    if liter <= 0:
        return
    kwh = liter * kwh_je_liter
    eur = liter * preis if preis else None
    gewichte = {r: g for r, g in e["offen"].items() if g > 0}
    summe = sum(gewichte.values())
    ww = 1.0 if summe <= 0 else min(max(anteil_ww, 0.0), 1.0)
    _buchen(_konto(e, WARMWASSER), kwh * ww,
            None if eur is None else eur * ww, heute)
    for raum_id, g in gewichte.items():
        teil = (1.0 - ww) * g / summe
        _buchen(_konto(e, raum_id), kwh * teil,
                None if eur is None else eur * teil, heute)
    e["offen"] = {}


def takt(config: dict, state: dict, bericht: dict, tankbericht: dict,
         jetzt: datetime | None = None) -> dict:
    jetzt = jetzt or datetime.now()
    heute = jetzt.date().isoformat()
    e = _zustand(state)
    einst = (config.get("einstellungen") or {}).get("energie") or {}

    letzter = e.get("letzter")
    stunden = 0.0
    if letzter:
        try:
            minuten = (jetzt - datetime.fromisoformat(letzter)).total_seconds() / 60
            if 0 < minuten <= MAX_LUECKE_MIN:
                stunden = minuten / 60
        except ValueError:
            pass
    e["letzter"] = jetzt.isoformat(timespec="seconds")

    # Erst das Gewicht dieses Takts, dann der Liter: Der Brenner hat in der
    # Zeit gebrannt, die gerade zu Ende gegangen ist.
    raeume = {r["id"]: r for r in config.get("raeume") or []}
    aussen = bericht.get("aussen")
    for ergebnis in bericht.get("raeume") or []:
        raum = raeume.get(ergebnis.get("id"))
        if raum is None:
            continue
        g = gewicht(raum, ergebnis, aussen, stunden)
        if g > 0:
            e["offen"][raum["id"]] = round(e["offen"].get(raum["id"], 0.0) + g, 4)

    liter = float(tankbericht.get("verbrauch_takt") or 0.0)
    verteilen(e, liter, tankbericht.get("preis_pro_liter"), heute,
              float(einst.get("warmwasser_anteil", WARMWASSER_ANTEIL)),
              float(einst.get("kwh_je_liter", KWH_JE_LITER)))

    return bericht_bauen(e, list(raeume.values()), heute)


def bericht_bauen(e: dict, raeume: list[dict], heute: str) -> dict:
    monat = heute[:7]
    jahr = int(heute[:4])
    beginn = f"{jahr if int(heute[5:7]) >= 7 else jahr - 1}-07"

    def zeile(raum_id: str, name: str) -> dict:
        k = _konto(e, raum_id)
        saison = [m for m in k["monate"] if m >= beginn]
        return {
            "id": raum_id, "name": name,
            "kwh": round(k["kwh"], 2), "eur": round(k["eur"], 2),
            "heute_kwh": round(k["tage"].get(heute, 0.0), 2),
            "heute_eur": round(k["tage_eur"].get(heute, 0.0), 2),
            "monat_kwh": round(k["monate"].get(monat, 0.0), 1),
            "monat_eur": round(k["monate_eur"].get(monat, 0.0), 2),
            "saison_kwh": round(sum(k["monate"][m] for m in saison), 1),
            "saison_eur": round(sum(k["monate_eur"].get(m, 0.0) for m in saison), 2),
        }

    return {
        "raeume": [zeile(r["id"], r["name"]) for r in raeume],
        "warmwasser": zeile(WARMWASSER, "Warmwasser"),
        "geschaetzt": True,
    }
