"""Aus den Zeitplänen aller Räume eine Hüllkurve für die Heizungsregelung.

Die Regelung kennt keine Räume. Sie kennt ein Wochenprogramm mit bis zu drei
Phasen je Tag und schaltet darin zwischen **Komfort-** und **Reduziertsollwert**
um – nicht zwischen ein und aus. Außerhalb der Phasen heizt sie also weiter,
nur auf niedrigerem Niveau.

Das passt genau zu dem, was der Planer ohnehin unterscheidet. Gesucht ist
deshalb die Frage: *Wann will irgendein Raum Komfort?* Die Vereinigung dieser
Zeiten über alle Räume ist die Hüllkurve, und die schreibt der Planer in die
Regelung.

Warum die Vereinigung und nicht der Durchschnitt: Der Kessel liefert einen
Vorlauf für das ganze Haus. Will das Bad um sechs warm werden und das
Wohnzimmer erst um acht, muss ab sechs Vorlauf da sein – verteilen tun die
Ventile. Umgekehrt gilt: Wo *kein* Raum Komfort will, darf die Regelung
absenken, und genau das tat sie bisher nicht, weil sie ihr eigenes Programm
fuhr.

Diese Datei rechnet nur. Sie kennt weder Netz noch Anlage, und lässt sich
darum vollständig auf dem Schreibtisch prüfen.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

import zeitplan as zp

# So viele Phasen führt ein Siemens-Albatros-Regler je Tag. Mehr lassen sich
# nicht schreiben; was darüber hinausgeht, wird zusammengelegt.
PHASEN = 3

# Der Modus, für den die Regelung ihren Komfortsollwert fahren soll. „eco“ und
# „nacht“ stehen bewusst nicht hier: Für die genügt der Reduziertsollwert, und
# das ist ja der Sinn der Sache.
KOMFORT = ("komfort",)

LEER = "##:##-##:##"


def _minuten(text: str) -> int:
    stunde, minute = str(text).split(":")[:2]
    return int(stunde) * 60 + int(minute)


def _uhr(minuten: int) -> str:
    minuten = max(0, min(24 * 60, int(minuten)))
    return f"{minuten // 60 % 24:02d}:{minuten % 60:02d}"


def raum_fenster(raum: dict, wochentag: str, schulfrei: bool | None,
                 arbeitstag: bool | None) -> list[tuple[int, int]]:
    """Wann dieser Raum an diesem Tag Komfort will – in Minuten ab Mitternacht.

    Der Zeitplan besteht aus Schaltpunkten, nicht aus Zeiträumen: Ein Punkt
    gilt, bis der nächste kommt. Ein Komfortfenster beginnt also bei einem
    Komfortpunkt und endet beim nächsten Punkt gleich welchen Modus.

    Der letzte Punkt des Vortages reicht in diesen Tag hinein. Steht er auf
    Komfort, beginnt der Tag warm – sonst fiele jede Nachtschicht unter den
    Tisch, bei der jemand bis zwei Uhr auf ist.
    """
    punkte = sorted(
        ((_minuten(e["start"]), e.get("modus", "komfort")) for e in raum.get("zeitplan") or []
         if zp._passt(e, wochentag, schulfrei, arbeitstag)),
        key=lambda p: p[0])
    if not punkte:
        # Kein Punkt an diesem Tag: Der Raum hat keinen Plan, der hier greift.
        # Er bekommt keine Zeit in der Hüllkurve – Wärme holt er sich über die
        # dynamische Erweiterung, falls er sie doch verlangt.
        return []

    fenster = []
    for i, (beginn, modus) in enumerate(punkte):
        if modus not in KOMFORT:
            continue
        ende = punkte[i + 1][0] if i + 1 < len(punkte) else 24 * 60
        if ende > beginn:
            fenster.append((beginn, ende))
    return fenster


def vereinigen(fenster: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Überlappende und aneinandergrenzende Fenster zusammenlegen."""
    if not fenster:
        return []
    zusammen = []
    for beginn, ende in sorted(fenster):
        if zusammen and beginn <= zusammen[-1][1]:
            zusammen[-1] = (zusammen[-1][0], max(zusammen[-1][1], ende))
        else:
            zusammen.append((beginn, ende))
    return zusammen


def eindampfen(fenster: list[tuple[int, int]],
               hoechstens: int = PHASEN) -> list[tuple[int, int]]:
    """Auf die Zahl der Phasen bringen, die die Regelung führen kann.

    Zusammengelegt wird an der **kleinsten Lücke**: Zwei Blöcke mit zwanzig
    Minuten Abstand zu verschmelzen kostet zwanzig Minuten Komfortbetrieb; die
    Mittagspause von fünf Stunden bleibt dafür erhalten. Andersherum wäre es
    genau falsch.

    Zusammenlegen heißt immer: mehr Wärme, nie weniger. Ein Kessel, der zu
    früh bereitsteht, kostet Öl; einer, der zu spät kommt, kostet eine kalte
    Wohnung – und die zweite Sorte Fehler ist die teurere.
    """
    fenster = vereinigen(fenster)
    while len(fenster) > hoechstens:
        luecken = [(fenster[i + 1][0] - fenster[i][1], i)
                   for i in range(len(fenster) - 1)]
        _, i = min(luecken)
        fenster[i:i + 2] = [(fenster[i][0], fenster[i + 1][1])]
    return fenster


def als_text(fenster: list[tuple[int, int]], phasen: int = PHASEN) -> str:
    """Die Schreibweise der Regelung: ``06:00-08:00 17:00-22:00 ##:##-##:##``."""
    teile = [f"{_uhr(b)}-{_uhr(e)}" for b, e in fenster[:phasen]]
    teile += [LEER] * (phasen - len(teile))
    return " ".join(teile)


def aus_text(text: str) -> list[tuple[int, int]]:
    """Zurücklesen, was in der Regelung steht – zum Vergleichen."""
    fenster = []
    for teil in str(text or "").split():
        if "#" in teil or "-" not in teil:
            continue
        von, bis = teil.split("-", 1)
        try:
            fenster.append((_minuten(von), _minuten(bis)))
        except (ValueError, IndexError):
            continue
    return fenster


def fuer_tag(raeume: list[dict], wochentag: str, schulfrei: bool | None,
             arbeitstag: bool | None) -> list[tuple[int, int]]:
    """Die Hüllkurve über alle Räume für einen Wochentag.

    Übergangen werden Räume, die abgeschaltet sind oder deren Sollwert von
    Hand geführt wird: Für einen Raum in „nur absenken“ weiß der Planer nicht,
    wann jemand ihn warm haben will – er würde die Hüllkurve über den ganzen
    Tag aufspannen und damit den Sinn der Übung zunichtemachen. Solche Räume
    melden ihren Bedarf über die dynamische Erweiterung, wenn er auftritt.
    """
    # Eine unbekannte Tagesart wird nicht geraten, sondern beidseitig
    # gerechnet: Für übermorgen weiß niemand, ob Ferien sind. Die Vereinigung
    # beider Fälle steht zu früh bereit statt zu spät – und am Tag selbst
    # schreibt der Planer den richtigen Stand ohnehin darüber.
    lagen = [(s, a) for s in ((schulfrei,) if schulfrei is not None else (True, False))
             for a in ((arbeitstag,) if arbeitstag is not None else (True, False))]
    alle = []
    for raum in raeume or []:
        if not raum.get("aktiv", True):
            continue
        if raum.get("betriebsart") == "nur_absenken":
            continue
        for schul, arbeit in lagen:
            alle += raum_fenster(raum, wochentag, schul, arbeit)
    return eindampfen(alle)


def woche(raeume: list[dict], jetzt: datetime, tagesart) -> dict[str, str]:
    """Die ganze Woche als ``{"mon": "06:00-22:00 ##:##-##:## ##:##-##:##", …}``.

    ``tagesart`` wird je Tag gefragt und gibt ``(schulfrei, arbeitstag)``
    zurück. Für heute und morgen weiß der Planer das aus Kalender und
    Schaltern; für die Tage danach kann er nur schätzen. Deshalb wird gefragt
    statt gerechnet – wer die Antwort nicht kennt, gibt die **weitere** von
    beiden Tagesarten zurück und ist auf der sicheren Seite.
    """
    plan = {}
    for versatz in range(7):
        tag = jetzt + timedelta(days=versatz)
        name = zp.TAGE[tag.weekday()]
        if name in plan:
            continue
        schulfrei, arbeitstag = tagesart(tag)
        plan[name] = als_text(fuer_tag(raeume, name, schulfrei, arbeitstag))
    return plan


def erweitern(text: str, bis_minute: int, jetzt: datetime) -> str | None:
    """Das laufende Fenster bis ``bis_minute`` verlängern – oder eines anlegen.

    Dafür sind die Sonderfälle da, die kein Zeitplan vorhersieht: die
    Partytaste, eine Übersteuerungsregel, die gerade greift, jemand auf dem
    Heimweg. Zurück kommt der neue Text, oder ``None``, wenn ohnehin schon
    Komfort gefahren wird – dann ist nichts zu tun und nichts zu schreiben.
    """
    jetzt_min = jetzt.hour * 60 + jetzt.minute
    bis_minute = min(int(bis_minute), 24 * 60)
    if bis_minute <= jetzt_min:
        return None
    fenster = aus_text(text)
    for beginn, ende in fenster:
        if beginn <= jetzt_min < ende and ende >= bis_minute:
            return None                 # läuft schon lange genug
    return als_text(eindampfen(fenster + [(jetzt_min, bis_minute)]))
