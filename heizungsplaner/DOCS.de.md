# Heizungsplaner · Heating Planner – Anleitung

Diese Anleitung erklärt, was der Planer tut und warum. Für die Installation
genügt die [README](https://github.com/Melle79/HA-heizungsplaner-heating-planner/blob/main/README.de.md).

🇬🇧 *This manual is also available in English:*
[DOCS.md](https://github.com/Melle79/HA-heizungsplaner-heating-planner/blob/main/heizungsplaner/DOCS.md)

## Die Oberfläche

Vier Reiter: Übersicht, Räume, Einstellungen, Protokoll.

### Übersicht

Je Raum der Zielwert, die gemessene Temperatur und in einem Satz die
Begründung. Oben stehen die Außentemperatur, die Partytaste und der Knopf
*Jetzt prüfen*; darunter der Hinweisbalken, wenn etwas Aufmerksamkeit braucht.

![Übersicht mit allen Räumen, Zielwert und Begründung](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/uebersicht.png)

Die Zustandsworte auf den Kacheln:

| Wort | Bedeutung |
|---|---|
| Komfort / Eco / Nacht | der Zeitplan führt |
| Vorheizen | der nächste Wechsel wird vorgezogen |
| Abwesend | niemand Zuständiges im Haus, Karenzzeit abgelaufen |
| Heimkehr | jemand nähert sich, der Raum wird wieder warm |
| Fenster offen | Frostschutz, danach Sperrzeit |
| Von Hand | jemand hat am Thermostat gedreht, der Planer hält sich zurück |
| Gesperrt | Freigabeschalter aus |
| Party | die Partytaste läuft |
| Sommer / Urlaub | Ventile zu bzw. Urlaubstemperatur |

### Räume

![Raumliste mit Betriebsart und Zahl der Thermostate](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/raeume.png)

Jeder Raum öffnet sich in einem Dialog mit fünf Reitern. Unter **Grundlagen**
stehen Name, Betriebsart und die Thermostate des Raumes:

![Grundlagen eines Raumes: Betriebsart und zugeordnete Thermostate](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/raum-grundlagen.png)

Der **Zeitplan** besteht aus Umschaltpunkten (siehe unten). *Vorlage einsetzen*
füllt einen leeren Plan mit einem üblichen Tagesablauf:

![Zeitplan mit Umschaltpunkten für Schultage und schulfreie Tage](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/raum-zeitplan.png)

Unter **Belegung** steht, wer den Raum benutzt – zuständige Personen, ein
eigener Freigabeschalter, eine eigene Karenzzeit – und ob der Raum bei der
Partytaste mitmacht:

![Belegung: Freigabeschalter, zuständige Personen, Karenzzeit](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/raum-belegung.png)

**Temperaturen** hält die vier Sollwerte und die harten Grenzen des Raumes.
Unter **Fühler und Melder** stehen Temperaturfühler, Präsenzmelder und
Fensterkontakte:

![Fühler und Melder mit Filterzeile über jeder Auswahlliste](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/raum-melder.png)

Geräte werden **angehakt**; was zugeordnet ist, sieht man auf einen Blick.
Über jeder Liste sitzt eine Filterzeile – nötig, weil ein Haushalt schnell
mehrere hundert binäre Melder hat. Ohne sie stünde im Wohnzimmer auch der
Briefkastenkontakt zur Auswahl:

* **Häkchen „nur <Raum>“** – zeigt nur, was zu diesem Raum gehört. Das ist
  der Bereich in Home Assistant, aber auch der Name: In dieser Installation
  trägt ausgerechnet der Wohnzimmer-Fensterkontakt keinen Bereich, und ein
  reiner Bereichsfilter würde ihn verstecken. Das Häkchen erscheint nur, wenn
  es für den Raum überhaupt etwas zu finden gibt.
* **Suchfeld** – durchsucht Namen und Entitäts-ID. Sobald etwas darin steht,
  werden auch die *sonstigen Melder* durchsucht.
* Was **angehakt ist, bleibt immer sichtbar**, gleich wie gefiltert wird.
  Eine ausgeblendete Zuordnung würde beim Speichern verlorengehen.
* Rechts steht, wie viele Geräte die Liste gerade zeigt und wie viele davon
  angehakt sind.

Die Gruppe **Sonstige Melder** – alles Binäre, das kein Kontakt ist – bleibt
zunächst zugeklappt und erscheint erst beim Suchen. Die Zeile rechts sagt,
wie viele dort warten.

### Einstellungen

Alles, was fürs ganze Haus gilt: Takt, Heizkurve, Sommerbetrieb, Vorheizen,
Anwesenheit, Fenstererkennung, Urlaub, Partytaste, Überwachung und Meldewege.
Die Beispielwerte unter der Heizkurve rechnen beim Verstellen mit.

![Einstellungen mit Heizkurve und Sommerbetrieb](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/einstellungen.png)

### Protokoll

Jede Änderung mit Begründung, die jüngste zuerst. Störungen sind rot
hinterlegt, Warnungen gelb – so ist auf einen Blick zu sehen, ob etwas
liegengeblieben ist.

![Protokoll der Schaltvorgänge mit Begründung](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/protokoll.png)

## Wie der Sollwert zustande kommt

In jedem Takt (Standard: alle fünf Minuten) durchläuft jeder Raum dieselbe
Rangfolge. Der erste zutreffende Fall gewinnt, die späteren kommen nicht mehr
zum Zug:

Sie gilt für Räume in der Betriebsart *nach Zeitplan führen*; für
*nur absenken* siehe unten.

| Rang | Fall | Ergebnis |
|---|---|---|
| 1 | Raum im Planer abgeschaltet | Ventil zu |
| 2 | Freigabeschalter aus | Ventil zu |
| 3 | Fenster offen | Frostschutz, danach Sperrzeit |
| 4 | Partytaste läuft | Komfort, für die eingestellte Dauer |
| 5 | Urlaubsschalter an | Urlaubstemperatur |
| 6 | Sommerbetrieb | Ventil zu |
| 7 | Zeitplan, ggf. übersteuert | Komfort / Eco / Nacht, ggf. vorgezogen |
| 8 | niemand Zuständiges da | Abwesenheitstemperatur |
| 9 | Heizkurve | Aufschlag nach Außentemperatur |

Die Heizkurve gilt nur für gewollte Raumtemperaturen (Komfort, Eco, Nacht).
Auf die Abwesenheits-, Urlaubs- und Frostschutztemperatur wird sie **nicht**
angewandt: Das sind Haltewerte, kein Zielklima.

Jede Entscheidung trägt ihre Begründung mit. Sie steht auf der Raumkachel und
im Protokoll.

## Der Knopf „Jetzt prüfen“

Von selbst rechnet der Planer alle paar Minuten (einstellbar unter *Takt*) und
außerdem sofort, wenn sich an der Konfiguration etwas ändert. Der Knopf zieht
einen solchen Durchlauf vor: Zustände aus Home Assistant neu einlesen, für
jeden Raum entscheiden, und wo nötig die Thermostate stellen. Danach zeigt er
kurz, wie viele Thermostate dabei gestellt wurden – oder dass nichts zu tun
war.

Nützlich, wenn man eine Einstellung geändert hat und nicht auf den nächsten
Takt warten will.

## Betriebsarten je Raum

**Nach Zeitplan führen** (Vorgabe) – der Planer bestimmt den Sollwert
durchgehend, wie in der Rangfolge oben beschrieben.

**Von Hand – nur zu festen Zeiten absenken** – der Raum wird von Hand gestellt,
am Thermostat oder in Home Assistant. Der Planer greift allein zu den
Zeitpunkten des Plans ein und lässt ihn sonst in Ruhe, auch wenn jemand
hochdreht. Für Räume, die man nach Bedarf warm macht und abends nur
zuverlässig heruntergefahren haben will – ein Gäste-WC etwa.

In dieser Betriebsart gelten Anwesenheit, Vorheizen und Heizkurve nicht; sie
setzen ein durchgehend geführtes Ziel voraus. Was weiter gilt:

* Ein **Absenkzeitpunkt** stellt die Temperatur seines Modus einmal ein. Er
  überschreibt dabei ausdrücklich eine Handeinstellung – dafür ist er da.
  Danach gehört der Raum wieder der Hand.
* Ein **verpasster** Zeitpunkt wird nicht nachgeholt. Startet das Add-on um
  22 Uhr, holt es die Absenkung von 21 Uhr nicht nach und überfährt so keine
  Handeinstellung. Innerhalb von 30 Minuten nach dem Zeitpunkt versucht es
  weiter – das überbrückt einen ausgefallenen Takt.
* **Fenster, Urlaub und Sommerbetrieb** greifen weiterhin. Der Planer merkt
  sich dabei den vorgefundenen Sollwert und **stellt ihn wieder her**, sobald
  der Sonderzustand vorbei ist. Ohne das bliebe der Raum nach einmal Lüften
  für immer auf Frostschutz stehen.

## Zeitplan

### Tagesarten

Jeder Umschaltpunkt gilt für eine Tagesart. Es gibt zwei Paare, weil nicht
jeder im Haus demselben Kalender folgt:

| Punkt gilt … | wann |
|---|---|
| **immer** | an den angehakten Wochentagen, ohne weitere Bedingung |
| **Schultag** | wenn der Schulfrei-Schalter *aus* ist |
| **schulfrei** | wenn er *an* ist – Ferien, Feiertage, Wochenende |
| **Werktag** | wenn der Arbeitstag-Schalter *an* ist |
| **arbeitsfrei** | wenn er *aus* ist – Wochenende und Feiertage |

Beide Paare lassen sich in einem Plan mischen. Für ein Kinderzimmer nimmt man
Schultag und schulfrei, für das Zimmer einer berufstätigen Person Werktag und
arbeitsfrei.

Der Unterschied ist nicht kosmetisch: In den Sommerferien ist *schulfrei* an,
aber wer arbeitet, steht trotzdem um sechs auf. Deshalb hängen die beiden
Paare an **verschiedenen Quellen** (*Einstellungen → Quellen aus Home
Assistant*).

Als Arbeitstag-Quelle eignet sich die **Workday-Integration** von Home
Assistant: `binary_sensor.workday_sensor` ist an, wenn gearbeitet wird, und
kennt Wochenende und Feiertage. Damit deckt ein einziges Punktpaar alles ab –
*Werktag* mit Haken auf Montag bis Freitag, *arbeitsfrei* mit Haken auf allen
sieben Tagen. Der arbeitsfrei-Punkt greift dann an Wochenenden **und** an
Feiertagen.

Ein reiner Feiertagssensor täte es auch, ließe aber das Wochenende offen –
dafür bräuchte es dann eine dritte Gruppe von Punkten.

Ohne eingetragene Quelle bleiben *Werktag* und *arbeitsfrei* wirkungslos, und
nur die übrigen Punkte greifen.


Ein Zeitplan besteht aus **Umschaltpunkten**, nicht aus Zeitfenstern. Jeder
Punkt sagt: ab dieser Uhrzeit, an diesen Wochentagen, gilt dieser Modus – bis
der nächste Punkt kommt. Der letzte Punkt eines Tages reicht über Mitternacht
in den nächsten. Dadurch kann keine Lücke entstehen, in der kein Modus gilt.

Jeder Punkt gilt wahlweise **immer**, nur an **Schultagen** oder nur an
**schulfreien** Tagen. Welcher Fall vorliegt, entscheidet die in den
Einstellungen hinterlegte Entität (hier: `input_boolean.wochenende_feiertag`).
Ist sie nicht gesetzt, greifen ausschließlich die „immer“-Punkte.

Vier Temperaturen je Raum:

* **Komfort** – wenn der Raum benutzt wird
* **Eco** – tagsüber, wenn der Raum nur bereitgehalten wird
* **Nacht** – Nachtabsenkung
* **Abwesend** – wenn niemand Zuständiges im Haus ist

Dazu **Nie unter** / **Nie über** als harte Grenzen des Raumes. Sie deckeln
auch die Heizkurve.

### Rezept: ein Raum soll nur vor dem Auskühlen geschützt werden

Für Räume, in denen man nicht heizen, aber auch nicht frieren will – ein
Schlafzimmer etwa:

* **ein einziger Schaltpunkt**, etwa `00:00 → Eco`,
* **Eco** auf die gewünschte Untergrenze, etwa 18 °C,
* **Heizkurve aus** – sie würde den Sollwert bei Kälte anheben und damit genau
  das tun, was hier nicht gewollt ist,
* **Anwesenheitsabsenkung aus** – die Untergrenze gilt unabhängig davon, ob
  jemand im Haus ist.

Der Sollwert steht dann rund um die Uhr auf 18 °C. Das Thermostat regelt
selbst: Es heizt erst, wenn der Raum darunter fällt, und sonst nie.

Eine Handeinstellung bleibt dabei möglich und hält **bis zum nächsten
Schaltpunkt** – bei einem einzigen Punkt also bis Mitternacht. Wer abends auf
21 °C dreht, findet am nächsten Morgen wieder die 18 °C vor.

Im Sommerbetrieb ist auch dieser Raum zu; die Untergrenze greift erst wieder,
wenn die gedämpfte Außentemperatur unter die Sommergrenze fällt.

## Übersteuerung: eine Regel statt des Zeitplans

Ein Raum kann Regeln bekommen, die den Zeitplan außer Kraft setzen. Eine Regel
besteht aus einem Modus und beliebig vielen Bedingungen; sie greift, solange
**alle** Bedingungen zutreffen.

![Homeoffice-Regel im Reiter Zeitplan](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/uebersteuerung.png)

Der Anlass ist das Homeoffice. Das Wohnzimmer läuft nach einem Plan, der es
vormittags auf Eco stellt, weil dann üblicherweise niemand da ist. Arbeitet
jemand zu Hause, soll es warm bleiben – ohne Schalter, ohne Zeitplanumbau:

| Bedingung | Entität | Zustand |
|---|---|---|
| Werktag | `binary_sensor.workday_sensor` | ist an |
| keine Ferien | `calendar.ferien_feiertage_bayern` | ist aus |
| Isabel ist da | `person.isabel` | ist an |

dazu das Zeitfenster **08:00–18:00**.

Ergebnis: **Komfort** statt Eco. Trifft eine der drei nicht zu, führt wieder
der Zeitplan.

Als Bedingung taugt alles, was an oder aus sein kann: Schalter und Helfer,
Melder, Kalender (`on`, solange ein Termin läuft) und Personen. **Eine Person
zählt als „an", solange sie zu Hause ist** – wer in einer anderen Zone steht,
etwa im Büro, zählt als fort.

Das **Zeitfenster** grenzt ein, wann die Regel überhaupt greifen darf. Ohne
es liefe die Homeoffice-Regel auch nachts um drei weiter – Werktag, keine
Ferien und Isabel zu Hause treffen ja weiterhin zu, und das Wohnzimmer stünde
statt auf Nacht auf Komfort. Leere Zeiten heißen: rund um die Uhr. Ein Fenster
darf über Mitternacht reichen (22:00–06:00), wie ein Zeitplanpunkt auch.

Die **Bezeichnung** der Regel ist frei. Sie steht später in der Begründung und
im Protokoll: „Homeoffice – komfort statt Zeitplan" ist dort lesbarer als die
Aufzählung dreier Entitäten. Ohne Bezeichnung werden die Bedingungen genannt.

**Woran man sieht, ob eine Regel läuft:** Die Regel selbst sagt es – und
nennt den Grund. Unter der Kopfzeile steht eine der folgenden Zeilen, davor
vor jeder Bedingung ein Häkchen oder ein Kreuz:

| Zeile | Bedeutung |
|---|---|
| *greift gerade* | alle Bedingungen erfüllt, Uhrzeit im Fenster |
| *greift heute nicht – Ferien & Feiertage läuft* | eine Bedingung, die für den ganzen Tag gilt: Kalender, Werktag, Ferien |
| *greift gerade nicht – Isabel ist nicht zu Hause* | eine Bedingung, die sich jederzeit ändern kann |
| *greift gerade nicht – außerhalb 08:00–18:00 Uhr* | inhaltlich passt alles, nur die Uhrzeit nicht |
| *… meldet nichts* | die Entität liefert weder an noch aus |

Die Unterscheidung ist nicht kosmetisch: Ein Ferientag gilt bis Mitternacht,
eine abwesende Person kann in fünf Minuten zurück sein. Greift eine Regel, steht ihre Bezeichnung
außerdem in der Begründung auf der Raumkachel und im Protokoll:
„Homeoffice – komfort statt Zeitplan".

Sind mehrere Regeln hinterlegt, gewinnt die oberste. Eine Entität, die nichts
meldet, lässt ihre Bedingung durchfallen (Zeichen `?`) – dann gilt schlicht
der Zeitplan.

**Was die Übersteuerung nicht aushebelt:** ein offenes Fenster, den
Sommerbetrieb, den Urlaubsschalter und die Anwesenheitsabsenkung. Das ist
Absicht: Eine Regel, die sich verhakt, heizt so kein leeres Haus.

Der Modus *Aus* schließt das Ventil – für eine Regel, die einen Raum zeitweise
ganz stilllegt. Zum dauerhaften Sperren gibt es die
[Freigabe](#freigabe-räume-die-nur-zeitweise-gebraucht-werden); sie steht in
der Rangfolge weit oben und gilt auch gegen die Partytaste.

## Heizkurve

```
Aufschlag = Steilheit × (Basis-Außentemperatur − Außentemperatur)
```

begrenzt auf den eingestellten Höchstwert. Mit den Vorgaben (Basis 15 °C,
Steilheit 0,06, Höchstwert 1,5 K) heißt das: bei 0 °C draußen +0,9 K, bei
−10 °C +1,5 K, bei 20 °C −0,3 K. Die Oberfläche rechnet die Beispiele beim
Verstellen mit.

Die Kurve gleicht aus, dass ein Heizkörper bei Kälte mehr Vorlauf braucht, um
dieselbe Raumtemperatur zu halten. Sie ersetzt keine Vorlauftemperatur­regelung
am Kessel.

## Sommerbetrieb

Die Außentemperatur wird exponentiell geglättet (Vorgabe: 24 Stunden
Zeitkonstante). Beim ersten Lauf holt sich der Planer den Anlauf aus der
Historie von Home Assistant, damit die Glättung nicht bei einem
Momentanwert beginnt. Steigt der geglättete Wert über die Grenze, schließen die
Ventile; er muss um die Hysterese darunter fallen, bevor wieder geheizt wird.
Ohne Glättung würde ein sonniger Februarnachmittag die Heizung abstellen.

Thermostate, die `off` können, werden abgeschaltet – das spart Batterie und
schließt das Ventil vollständig. Alle anderen bekommen den Frostschutzwert.

**Wenn ein Gerät sich nicht abschalten lässt:** Manche Matter-Thermostate
nehmen den Befehl an und stehen eine Minute später wieder auf `heat`. Ohne
Gegenmaßnahme schickt der Planer bei jedem Takt ein neues „aus“ – Dauerfeuer,
das nichts bewirkt außer die Batterie zu leeren. Nach zwei vergeblichen
Versuchen schließt er das Ventil deshalb dauerhaft über den Frostschutzwert
und vermerkt das im Protokoll. Meldet sich das Gerät später doch einmal als
abgeschaltet, gilt wieder der normale Weg.

## Partytaste

Einmal drücken, und die gewählten Räume gehen für die eingestellte Dauer auf
Komfort – gleich, was der Zeitplan sagt. Danach führt wieder der Plan; niemand
muss daran denken, die Taste zurückzustellen.

Zu finden an drei Stellen: als Knopf oben in der Oberfläche (mit Restzeit), als
`switch.heizungsplaner_party` in Home Assistant – also auch auf dem Dashboard,
per Sprachbefehl oder in Automationen – und über `POST /api/party`, wahlweise
mit abweichender Dauer (`{"stunden": 5}`).

**Welche Räume mitmachen**, steht in den Einstellungen unter *Partytaste*; ein
Schlafzimmer will man dort meist nicht dabei haben. Dieselbe Einstellung findet
sich auch im Raum selbst unter *Belegung*.

In der Rangfolge steht die Party **vor Urlaub und Sommerbetrieb**: Wer sie
drückt, ist im Haus und will es warm haben, gleich was der Kalender sagt. Nur
ein **offenes Fenster** bleibt stärker – dagegen anzuheizen wäre sinnlos. Läuft
gerade Sommerbetrieb, sagt die Begründung dazu, dass die Anlage möglicherweise
gar nicht heizt.

## Freigabe: Räume, die nur zeitweise gebraucht werden

Ein Raum kann an einen Schalter in Home Assistant gehängt werden (*Freigabe*).
Steht der auf aus, bleibt der Raum kalt – ganz gleich, was Zeitplan und
Anwesenheit sagen. Gedacht für ein Gästezimmer, das nur geheizt werden soll,
wenn tatsächlich Gäste da sind: Schalter an, und der hinterlegte Zeitplan
greift wie bei jedem anderen Raum.

Fehlt der Schalter in Home Assistant oder meldet er nichts, wird der Raum
**normal geregelt** und der Hinweisbalken meldet es. Einen Raum wegen eines
kaputten Schalters kalt zu lassen wäre die unangenehmere Überraschung.

## Anwesenheit

### Wer zum Haushalt zählt

Unter *Einstellungen → Anwesenheit* steht, welche Personen der Planer
überhaupt betrachtet. **Nichts angehakt heißt: alle** – das ist die Vorgabe
und für die meisten richtig.

Wichtig wird die Auswahl, wenn in Home Assistant mehr Personen stehen als im
Haus wohnen. Der gefährliche Fall ist eine Person **ohne Gerätetracker**: Sie
steht dauerhaft auf „zu Hause" und hält damit jeden Raum für besetzt. Die
Absenkung bei Abwesenheit griffe dann nie mehr, und es gäbe keine
Fehlermeldung, die darauf hinweist – die Räume blieben einfach warm.

Die Auswahl je Raum („Zuständige Personen") engt innerhalb des Haushalts
weiter ein.


Jedem Raum lassen sich zuständige Personen zuordnen. Ohne Zuordnung zählt die
ganze Familie. Zusätzlich kann ein Präsenz- oder Bewegungsmelder den Raum als
besetzt melden.

**Nur der Präsenzmelder zählt** – für Räume, die man betritt und wieder
verlässt, statt sich dort aufzuhalten: ein Büro, eine Werkstatt. Dann bleiben
Personen außer Betracht, und allein der Melder im Raum entscheidet. Ohne diese
Einstellung wäre ein Raum ohne Personenzuordnung immer belegt, sobald irgendwer
im Haus ist, und der Melder bliebe wirkungslos.

In dieser Betriebsart ist auch das Vorheizen bei Heimkehr abgeschaltet: Sonst
liefe die Heizung an, sobald jemand nach Hause fährt, obwohl niemand den Raum
betritt.

**Ein Melder, der nichts meldet, gilt nicht als „niemand da“.** Bei einem
ausgefallenen oder falsch eingetragenen Melder stünde der Raum sonst dauerhaft
auf der Abwesenheitstemperatur, ohne dass es auffällt. Antwortet kein einziger
Melder des Raumes, gilt er als belegt und der Hinweisbalken meldet es.

Ist niemand Zuständiges da, wartet der Planer die **Karenzzeit** ab (Vorgabe:
45 Minuten), bevor er absenkt. Ein kurzer Gang zum Bäcker kostet damit nichts.
Jeder Raum kann eine eigene Karenzzeit bekommen – ein Büro, dessen
Bewegungsmelder nach zwei Minuten abfällt, braucht eine kürzere als ein
Wohnzimmer.

Die **Heimkehr** wird vorhergesehen. Dafür müssen drei Dinge zutreffen:

1. die Person ist näher als die eingestellte Entfernung zur Heimzone,
2. sie steht **in keiner Zone** – wer in der Schule oder im Büro sitzt, ist
   dort angekommen, auch wenn das nur einen Kilometer entfernt ist,
3. ihre Entfernung hat in den letzten 15 Minuten um die eingestellte
   **Mindestannäherung** abgenommen.

Die Entfernung allein genügt nicht. Liegt die Schule einen Kilometer
entfernt, wären die Kinder den ganzen Vormittag „nah" – ihre Zimmer würden
durchheizen und die Anwesenheitsabsenkung liefe ins Leere. Die
Mindestannäherung filtert zugleich das GPS-Rauschen heraus: Ein Wert von
0,3 km spricht nicht auf die hundert Meter an, um die eine ruhende Position
schwankt.

Geprüft wird ausschließlich auf `home`. Tracker, die unterwegs eigene
Standzonen melden statt `not_home`, funktionieren damit korrekt.

## Vorheizen

```
Vorlauf = Grundvorlauf + Zuschlag × (15 °C − Außentemperatur)
```

begrenzt auf den Höchstwert. Der Planer schaut voraus, wann der Zeitplan das
nächste Mal etwas Wärmeres verlangt, und zieht den Wechsel um den Vorlauf vor.
Auch mehrstufige Übergänge (Nacht → Eco → Komfort) werden erkannt.

## Fenstererkennung

Zwei Wege, in dieser Rangfolge:

**Fensterkontakte.** Was im Raum unter *Fensterkontakte* eingetragen ist,
entscheidet. Sobald ein Raum mindestens einen Kontakt hat, der etwas meldet,
tritt die Temperatursturz-Erkennung für diesen Raum zurück – ein echter
Kontakt ist genauer, und der Sturz schlägt gelegentlich grundlos an, wenn ein
anlaufender Heizkörper die Luft am Thermostatfühler verwirbelt. Wer beides
will, schaltet am Raum *Zusätzlich auf Temperatursturz achten* ein.

**Die geräteeigene Erkennung eines Thermostats ist kein Kontakt.** Manche
Thermostate – die FRITZ!Smart Thermo etwa – erkennen ein offenes Fenster
selbst am Sturz an ihrem eigenen Fühler und melden das als eigene Entität.
Der Planer nimmt eine solche Meldung als Auslöser an, lässt die
Sturz-Erkennung daneben aber weiterlaufen. Sie macht schließlich dasselbe,
nur im Gerät, und schweigt, sobald das Gerät abgeschaltet ist oder in der
Sommerpause steht. Ein Raum, dessen einziger Eintrag eine solche Meldung ist,
stünde sonst ohne Fenstererkennung da. In der Auswahlliste sind sie als
*geräteeigene Erkennung* gekennzeichnet.

**Temperatursturz.** Für Räume ohne Kontakte: Fällt die Raumtemperatur um mehr
als den eingestellten Wert innerhalb des Zeitfensters, gilt das Fenster als
offen. Der Planer führt dafür je Raum ein Temperaturgedächtnis über eine
Stunde. Als Raumtemperatur dient der eingetragene Fühler, sonst der Mittelwert
der `current_temperature` aller Thermostate des Raumes.

Nach beiden Wegen bleibt der Raum für die Sperrzeit auf Frostschutz, damit ein
kurzes Stoßlüften nicht sofort wieder gegengeheizt wird.

### Kontakte nachrüsten

Neue Kontakte müssen nur in Home Assistant einem **Bereich** zugeordnet sein,
der einem Raum des Planers entspricht. Dann erscheint auf der Übersicht ein
Hinweis samt Knopf *Zuordnen*, der den Raum mit vorgewähltem Kontakt öffnet –
Speichern genügt. Dasselbe gilt für neue Präsenz- und Bewegungsmelder.

Was man dort nicht haben will, verschwindet mit *Nicht nötig* dauerhaft aus
den Hinweisen.

In der Auswahlliste stehen die Kontakte nach Bereich gruppiert, der eigene
Bereich zuoberst. Als Kontakt gilt, was die Geräteklasse `window`, `door` oder
`opening` trägt **oder** ein entsprechendes Wort im Namen führt – so werden
auch die „Offenes Fenster erkannt“-Meldungen mancher Thermostate gefunden, die
ohne Geräteklasse kommen. Alles übrige Binäre steht unter *Sonstige Melder*
und erscheint erst, wenn man ins Suchfeld tippt.

### Wenn ein Kontakt ausfällt

**Ein Kontakt, der nichts meldet, gilt nicht als „geschlossen“.** Eine leere
Batterie, ein abgezogener Funkstick oder ein noch nicht angelerntes Gerät
würde den Raum sonst stillschweigend blind machen. Meldet ein eingetragener
Kontakt weder `on` noch `off`, springt für diesen Raum die
Temperatursturz-Erkennung wieder ein, die Begründung sagt es
(„… melden nichts – ersatzweise Temperatursturz“), und auf der Übersicht steht
eine Warnung.

## Während Home Assistant startet

Nach einem Neustart liefert Home Assistant seine Entitäten nach und nach. Wer
in dieser Phase rechnet, hält die noch nicht geladenen Geräte für verschwunden.
Der Planer fragt deshalb vor jedem Takt den Zustand von Home Assistant ab und
setzt aus, solange dieser nicht `RUNNING` ist – kein Schalten, keine Störung,
keine Benachrichtigung. Die Oberfläche zeigt in dieser Zeit einen Hinweis statt
einer Mängelliste.

## Überwachung: wenn ein Thermostat ausfällt

Der Anlass ist ein Vorfall: Während eines Urlaubs fielen vier Thermostate wegen
leerer Batterien aus, und niemand bemerkte es.

Eine Batteriewarnung allein hilft dabei nicht. Die SwitchBot-Thermostate melden
über Matter **gar keinen Ladestand** – es gibt nichts zu überwachen. Was sie
melden, ist ihr Zustand, und zwar regelmäßig. Bleibt das aus, ist das Gerät tot,
gleich aus welchem Grund. Der Planer wacht deshalb über das **Lebenszeichen**:

| Fall | Wann |
|---|---|
| gibt es nicht mehr | die Entität ist aus Home Assistant verschwunden |
| nicht erreichbar | Zustand `unavailable` oder `unknown` |
| meldet sich nicht mehr | seit der Schweigefrist kein Lebenszeichen – und der Weckruf blieb unbeantwortet (Vorgabe 24 Stunden, im Sommerbetrieb doppelt) |
| schwache Batterie | wo es eine Anzeige gibt, unterhalb der Schwelle (Vorgabe 20 %) und **nicht älter als zwölf Stunden** |
| nimmt keine Sollwerte an | drei Schreibvorgänge in Folge abgelehnt |
| steht in der Sommerpause | das Gerät meldet `summer`, obwohl geheizt werden soll |

Beim Batteriestand zählt auch sein Alter. Manche Geräte melden ihn nur bei
Änderung – nach einem Batteriewechsel steht dort womöglich noch tagelang der
alte Wert. Eine Warnung darauf wäre falsch, deshalb bleibt ein Stand, der
älter als zwölf Stunden ist, unberücksichtigt. Die Meldung nennt umgekehrt die
Uhrzeit der Messung, damit man sie einordnen kann.

**Die Sommerpause meldet der Planer von sich aus**, sobald der Sommerbetrieb
endet und ein Gerät noch auf `summer` steht. Das ist der Zeitpunkt, an dem der
Hinweis etwas nützt: Vorher wäre er eine Nachricht über den Sommer, nachher
bliebe der Raum kalt. Beenden lässt sie sich nur in der FRITZ!Box – unter
*Smart Home → Gerät bearbeiten → Zeitschaltung → Sommerzeit*. Home Assistant
kann es nicht: Die Integration zeigt den Modus an, und die Liste der
Voreinstellungen enthält dann nichts außer `summer`.

Bis dahin gilt auch der Fall darüber: Ein Gerät in der Sommerpause lehnt jeden
Sollwert ab. Die Meldung nennt das ausdrücklich, damit man nicht nach
Batterien sucht, wo keine fehlen.

Nach drei Fehlschlägen versucht der Planer es nur noch alle 30 Minuten. Sonst
füllte ein solches Gerät bei jedem Takt das Protokoll, ohne dass sich etwas
ändert.

**Wie lange darf ein Gerät schweigen?** Länger, als man denkt – und die Frist
allein genügt nicht. Im Sommerbetrieb schreibt der Planer nicht mehr, also hat
auch das Gerät nichts zu melden: Büro, Hobbyraum und Gästezimmer schwiegen
dabei über einen Tag, ohne dass ihnen etwas fehlte.

Deshalb wird vor einer Meldung **angeklopft**. Der Planer bittet Home
Assistant, den Zustand dieser Entität neu zu holen – ein Weckruf ohne
Funkbefehl ans Gerät –, wartet zwölf Minuten und meldet erst, wenn auch dann
nichts kommt. Meldet sich das Gerät, war es nur still. Genau das tut ein
Mensch, der den Sollwert kurz verstellt, um zu sehen, ob das Thermostat noch
lebt.

Die Frist selbst liegt bei 24 Stunden und gilt im Sommerbetrieb doppelt. Im
Heizbetrieb meldet ein Gerät bei jeder Sollwertänderung, dort ist sie
deutlich schärfer, als sie klingt.

Gemeldet wird **auf Flanke**: einmal beim Auftreten, einmal bei der Behebung.
Eine Warnung, die stündlich erneut aufs Telefon kommt, wird nach dem dritten
Mal weggewischt und beim vierten Mal übersehen. Wird aus einer schwachen
Batterie ein Ausfall, gilt das als neue Nachricht.

Die Meldewege wählt man in den Einstellungen aus den `notify`-Diensten von Home
Assistant – für die Ferne taugt die Companion-App, für zu Hause zusätzlich die
dauerhafte Benachrichtigung in der Oberfläche. Jede Störung steht außerdem im
Protokoll und im Hinweisbalken.

Für eigene Automationen gibt es `binary_sensor.heizungsplaner_stoerung`
(Geräteklasse `problem`) mit den Meldungen als Attribut sowie
`sensor.heizungsplaner_stoerungen` mit der Zahl der ausgefallenen Geräte.

## Öltank (optional)

Dieser Baustein ist **ab Werk aus**. Er erscheint erst, wenn du ihn unter
*Einstellungen → Öltank* einschaltest – vorher gibt es den Reiter „Öltank“
nicht, und es wird auch nichts gerechnet. Wer mit Gas, Fernwärme oder einer
Wärmepumpe heizt, merkt von diesem Kapitel nichts.

### Woher der Füllstand kommt

Ohne Sensor im Tank, aus zwei Zahlen, die sich gegenseitig korrigieren:

* Die **Liefermenge** vom Lieferschein ist geeicht und damit genauer als jede
  Messung – aber sie kommt nur ein- bis zweimal im Jahr.
* Die **Brennerlaufzeit** mal Düsendurchsatz liefert die Auflösung dazwischen.
  Weil der Durchsatz nur ein Schätzwert aus der Düsengröße ist, driftet sie –
  bis die nächste Lieferung sie wieder einnordet.

Der Laufzeitzähler ist optional. Trägst du keinen ein, bleibt der Stand
einfach stehen, bis du eine Lieferung einträgst oder ihn von Hand setzt. Auch
so ist die Anzeige brauchbar: Sie zeigt dann, was seit der letzten Lieferung
noch übrig sein sollte.

### Der Peilstab: einmessen statt schätzen

Wer die Anzeige am Tank in Zentimetern abliest, kann drei zusätzliche Felder
ausfüllen – *Anzeige bei vollem Tank*, *Untergrenze* und *Liter je Zentimeter*.
Damit wird aus der Rechnung etwas Belastbares.

**Das Einmessen macht die Lieferung selbst.** Notiere beim Tanken den Stand
vorher und nachher und trag beides mit der Liefermenge ein. Der Planer rechnet:

```
Liter je Zentimeter = gelieferte Menge ÷ (cm nachher − cm vorher)
```

Das ist der genaueste Wert, den es über diesen Behälter je geben wird – er
stammt aus einer geeichten Menge und dem Tank selbst, nicht aus einem
Typenschild von 1965. Der Wert trägt sich in die Einstellungen ein, und ab
dann rechnet der Planer zwischen Zentimetern und Litern hin und her: Der Stand
lässt sich in Zentimetern setzen, und die Anzeige nennt beides.

**Voll getankt? Dann rechnet sich die Geometrie selbst aus.** Setz beim
Eintragen den Haken *Der Tank wurde voll gefüllt*. Der Tankwagen füllt bis zur
Abschaltung des Grenzwertgebers, der Inhalt danach ist also bekannt – die
Füllgrenze. Zusammen mit den beiden Ablesungen stehen damit zwei Gleichungen
für zwei Unbekannte, und der Planer lernt in einem Zug:

* die **Liter je Zentimeter** aus dem Höhenunterschied,
* die **Anzeige bei vollem Tank** – das ist ja genau die Ablesung, die gerade
  vorliegt, also gemessen statt geschätzt,
* den **Nullpunkt** aus `cm nachher − bekannter Inhalt ÷ Liter je Zentimeter`.

Danach ist der Peilstab überflüssig. Ein Vorbehalt bleibt: Die Rechnung hängt
am Nenninhalt vom Typenschild. Kommt dabei ein **negativer** Nullpunkt heraus,
sagt der Planer das ausdrücklich – dann passt der eingetragene Tankinhalt nicht
zu dieser Skala, und beides gehört überprüft.

**Der Nullpunkt, wenn der Anzeiger nachgerüstet ist.** Der Planer rechnet
Liter aus der Höhe *über dem Nullpunkt* – also über dem, was die Anzeige bei
leerem Tank zeigt. Bei einem ab Werk passenden Gerät ist das null. Bei einem
nachträglich aufgeschraubten Anzeiger selten: Eine 150-cm-Skala auf einem
130-cm-Tank, ein zu lang abgelängter Faden, und schon liegt die ganze Skala
verschoben.

Zwei Hinweise dazu:

* **Die Einmessung über eine Lieferung ist davon unberührt.** Sie rechnet mit
  der *Differenz* zweier Ablesungen, und ein Versatz kürzt sich dabei heraus.
  Die Steigung stimmt also auch bei krummer Skala.
* **Den Nullpunkt selbst muss man einmal bestimmen.** Am einfachsten kurz vor
  einer Lieferung, wenn der Tank fast leer ist: Peilstab in den Dom, wahre
  Ölhöhe messen, mit der Anzeige vergleichen – die Differenz ist der Versatz.

**Die Untergrenze ist die ehrlichere Zahl.** Der Saugfuß sitzt einige
Zentimeter über dem Boden. Was darunter steht, gehört dir, hilft dem Brenner
aber nicht mehr – der zieht dann Luft und geht auf Störung. Ist eine
Untergrenze eingetragen, unterscheidet der Planer:

| | |
|---|---|
| **im Tank** | alles, was drin ist |
| **für den Brenner erreichbar** | alles oberhalb des Saugfußes |

Warnschwelle und Reichweite rechnen dann mit der erreichbaren Menge, nicht mit
der gesamten. Ein Tank mit 250 Litern „drin" kann für den Brenner leer sein.

### Verbrauch und Verlauf

Drei Zeitspannen stehen im Reiter: dieser Monat, die laufende Heizperiode und
alles seit Beginn der Aufzeichnung. Die **Heizperiode beginnt im Juli** – ein
Kalenderjahr zerschnitte den Winter in der Mitte und machte jeden Vergleich
wertlos.

Aufbewahrt wird zweierlei: **Tageswerte 60 Tage lang** (mehr braucht die
Reichweite nicht) und **Monatssummen für immer**. Zwölf Zahlen im Jahr kosten
nichts, und erst damit lässt sich eine Heizperiode mit der vorigen vergleichen.

Dazu kommen die **MQTT-Entitäten**, sobald der Tankteil eingeschaltet ist:

| Entität | |
|---|---|
| Heizöl erreichbar | oberhalb des Saugfußes |
| Heizöl im Tank | alles, was drin ist |
| **Heizöl verbraucht** | ein Zähler, der nur wächst |
| Heizöl Reichweite | Tage |
| Öltank Leckage | der Melder im Auffangraum |

„Heizöl verbraucht" trägt `state_class: total_increasing`. Damit baut Home
Assistant daraus von selbst eine **Langzeitstatistik** mit Tages-, Monats- und
Jahreswerten – die überlebt auch den Verlust der Add-on-Daten. Wer InfluxDB
oder eine andere Datenbank an Home Assistant hängt, bekommt den Verlauf dort
ohne weiteres Zutun mit.

Ein Tank ohne bekannten Stand meldet `unknown`, nicht null. Eine erfundene Null
landete sonst als echter Messwert in der Statistik.

### Was das Heizöl kostet

Zu jeder Lieferung lässt sich der **Preis je Liter** oder der **Gesamtpreis**
eintragen – eines von beiden genügt, das andere rechnet sich aus der Menge.

Bewertet wird der Verbrauch danach zum **gleitenden Durchschnittspreis**: Jede
Lieferung mischt sich mit dem Restbestand, so wie das Öl im Tank auch. Wer
2000 Liter zu 1,10 im Tank hat und 2000 Liter zu 0,90 dazubekommt, verbraucht
ab dann zu 1,00. Das ist die übliche Lagerbewertung und die einzige Rechnung,
die ohne Erfindungen auskommt – im Tank liegt nun einmal kein Öl von 2019
säuberlich neben dem von 2026.

Daraus entstehen: Kosten je Monat und je Heizperiode, der Wert dessen, was
gerade im Tank steht, und ein Kostenzähler in Home Assistant. Der trägt
`device_class: monetary`, steht also in derselben Statistik wie Strom und Gas.

Ohne Preisangabe bleibt alles bei Litern – erfundene Zahlen gibt es nicht.

### Einstellungen

| Feld | Bedeutung |
|---|---|
| Tankinhalt | Nenninhalt laut Typenschild |
| Füllgrenze | Wie viel hinein darf, meist 95 % |
| Warnschwelle | Darunter gibt es eine Warnung, gerechnet auf die erreichbare Menge |
| Anzeige bei vollem Tank | Was der Peilstab bei vollem Tank zeigt |
| Untergrenze | Höhe des Saugfußes |
| Liter je Zentimeter | Trägt sich beim Einmessen selbst ein |
| Laufzeitzähler | Sensor mit der Brennerlaufzeit in Stunden |
| Düsendurchsatz | Liter je Betriebsstunde |
| Melder im Auffangraum | Für die Leckagewache |
| Melden an | Leer: die Meldewege des Wachhunds |

### Was gegen falsche Zahlen unternommen wird

Ein gerechneter Tank ist nur so gut wie sein Zähler, und Zähler springen. Drei
Fälle sind abgefangen: Der **erste** gesehene Zählerstand gilt nie als
Verbrauch – sonst wäre der Tank beim ersten Takt leer. Ein **Rücksprung**
(neuer Kessel, zurückgesetzter Zähler) wird als neuer Ausgangswert übernommen
statt verbucht. Und ein **Sprung** von mehr als 24 Stunden zwischen zwei Takten
gilt als Zählerfehler und wandert ins Protokoll, nicht in die Rechnung.

### Leckagewache

Ein Melder im Auffangraum, angegeben als beliebige Entität, die „an“ oder „aus“
kennt. Spricht er an, gibt es **eine** Meldung – nicht alle fünf Minuten
dieselbe.

Ein Hinweis, der Geld spart: **Heizöl leitet keinen Strom.** Die üblichen
Wassermelder messen den Widerstand zwischen zwei Kontakten und schweigen bei
einer Ölpfütze. Es braucht einen optischen Sensor oder einen Schwimmer.

### Reichweite

Der Durchschnitt der letzten vierzehn Tage, hochgerechnet auf die Restmenge.
Unter drei Tagen mit Verbrauch gibt es keine Zahl, und im Sommer – wenn nichts
verbraucht wird – steht dort ein Strich statt einer Unendlichkeit.

## Handeingriffe

Wird ein Thermostat von Hand verstellt – am Gerät, in Home Assistant oder per
Automation –, erkennt der Planer die Abweichung von seinem zuletzt
geschriebenen Wert und hält sich **bis zum nächsten Zeitplanwechsel** zurück.
Danach führt wieder der Plan. Abschaltbar über *Einstellungen → Betrieb*.

Funkthermostate melden verzögert. Deshalb wertet der Planer eine Abweichung
erst 15 Minuten nach dem eigenen Schreibvorgang als Handeingriff.

**Nicht jede Abweichung ist eine Hand.** Manche Geräte quittieren einen
Sollwert und setzen ihn trotzdem nicht um – sie stehen danach unverändert da.
Der Planer merkt sich deshalb, welcher Wert *vor* seinem Befehl am Gerät
stand: Ist es noch genau dieser, hat niemand gedreht, sondern das Gerät hat
den Befehl verschluckt. Er versucht es dann erneut und meldet es nach drei
Fehlschlägen als Störung. Diese Unterscheidung ist wichtig – als Handeingriff
gedeutet, zöge sich der Planer zurück und der Raum bliebe auf einem Wert, den
niemand gewollt hat.

## Wie geschrieben wird

Ein Sollwert geht nur dann an ein Thermostat, wenn dort tatsächlich etwas
anderes eingestellt ist – **auf Flanke, nicht auf Pegel**. Ein Add-on, das in
jedem Takt stur denselben Wert schreibt, wird zum Besitzer der Entität und
überfährt jede andere Bedienung.

Jedes Thermostat wird **einzeln** angesprochen. Ein Sammelaufruf würde an
einem einzigen abgeschalteten Gerät scheitern und alle übrigen mitreißen.
Nimmt ein Thermostat den Sollwert nicht an, schaltet der Planer es einmal auf
`heat` und versucht es erneut.

Der zuletzt geschriebene Wert liegt in `/data/zustand.json` und überlebt einen
Neustart. Ohne dieses Gedächtnis würde jeder Add-on-Start in jedes Thermostat
schreiben.

## Trockenlauf und Automatik aus

**Trockenlauf** – der Planer rechnet, protokolliert und meldet über MQTT, aber
stellt kein Thermostat. Der richtige Zustand für die ersten Tage.

**Automatik aus** – der Planer rechnet nicht mehr in die Thermostate hinein
und lässt sie, wie sie sind.

### Zurück zur vorherigen Steuerung

1. Trockenlauf einschalten (oder Automatik aus).
2. Die zuvor abgeschalteten Zeitpläne und Automationen wieder aktivieren.

Die Thermostate behalten in beiden Fällen den zuletzt gestellten Wert – der
Planer räumt beim Abschalten nichts auf, damit ein versehentliches Umschalten
kein kaltes Haus hinterlässt.

## Ersteinrichtung

Der Assistent liest die Bereiche aus Home Assistant und legt je Bereich mit
Thermostat einen Raum an: mit den Thermostaten dieses Bereichs, einem üblichen
Zeitplan und – wo der Bereichsname einen Vornamen enthält – der zuständigen
Person. Gruppen-Helfer bleiben außen vor; der Planer stellt jeden Heizkörper
einzeln. Doppelt registrierte Geräte mit gleichem Anzeigenamen werden nur
einmal übernommen.

Der Vorschlag wird angezeigt, bevor er gespeichert wird. Danach gehören
Zeitpläne, Temperaturen und Personenzuordnung geprüft – geraten ist nicht
entschieden.

## Umstieg von der Scheduler-Integration

Solange beide laufen, schreiben zwei Systeme auf dieselben Sollwerte und
überstimmen sich gegenseitig. Deshalb:

1. Räume im Planer einrichten und einige Tage im Trockenlauf beobachten.
2. Das Protokoll gegen die tatsächlichen Zeiten halten.
3. Die Scheduler-Einträge für die Heizung **ausschalten**.
4. Erst dann den Trockenlauf abschalten.

Der Hinweisbalken der Oberfläche warnt, wenn ein Thermostat in zwei Räumen
steht – dann würden sich die beiden Räume gegenseitig verstellen.

## Karten fürs Dashboard

Unter `heizungsplaner/dashboard/` im Repository liegt eine fertige Übersicht
zum Einfügen: die Partytaste mit Restzeit, eine Störungsanzeige, die nur
erscheint, wenn es etwas zu melden gibt, und eine Tabelle aller Räume mit
Zielwert, Ist-Temperatur, Zustand und dem nächsten Schaltpunkt. Die Karten
lesen ausschließlich die MQTT-Entitäten und funktionieren deshalb auch von
unterwegs.

Dazu kommt `regelkarte(sensor)`: eine Kachel, die nur erscheint, solange eine
Übersteuerungsregel greift, und zeigt, bis wann („bis 14:00 Uhr"). Sie gehört
in den Abschnitt, in dem man den Raum ohnehin ansieht. Grundlage sind die
Attribute `uebersteuerung`, `uebersteuerung_greift`, `uebersteuerung_lage` und
`uebersteuerung_bis` am Raum-Sensor – eine Karte, die stattdessen die
Begründung nach Stichworten durchsucht, bricht beim ersten umbenannten Raum.

**Keine `conditional`-Karte verwenden:** In einer Sections-Ansicht meldet die
in Home Assistant 2026.8 „Konfigurationsfehler". Dort gehört `visibility` an
die Karte selbst. Und ist das unter `state_content` genannte Attribut leer,
zeigt eine Tile-Karte ersatzweise den Zustand des Sensors – deshalb ist
`uebersteuerung_bis` nie leer, sondern trägt „ruht", wenn nichts läuft.

## Dateien

| Datei unter `/data` | Inhalt |
|---|---|
| `config.json` | Räume, Zeitpläne, Einstellungen |
| `zustand.json` | zuletzt geschriebene Sollwerte, Laufzeitzustand je Raum |
| `logbuch.json` | Protokoll der letzten 500 Schaltvorgänge |

## Einheit: Celsius oder Fahrenheit

Die Einheit nimmt der Planer aus dem Maßsystem von Home Assistant
(`/config` → `unit_system.temperature`) – aus derselben Antwort wie die
Sprache. Die Zahlen selbst kommen bereits richtig an, denn Home Assistant
rechnet Klima-Entitäten in dieses Maßsystem um. Entscheidend ist, dass alles
**Feste** mitzieht:

* die **Vorgaben** – aus Komfort 21 °C werden 70 °F, aus Frostschutz 8 °C
  werden 46 °F, auf ganze Grad gerundet, weil eine Vorgabe sich so lesen soll;
* die **Grenzen** der Eingabeprüfung – 70 °F läge außerhalb einer Spanne, die
  für Celsius gedacht ist;
* **Spannen** im Unterschied zu Temperaturen: Aus 1,5 K Hysterese werden
  2,7 °F, nicht 34,7. Auf einen Abstand 32 zu addieren ist hier der
  klassische Fehler;
* die **Schrittweite**: ein halbes Grad in Celsius, ein ganzes in Fahrenheit,
  weil die Geräte dort nicht feiner auflösen und jeder Schreibvorgang
  Batterie kostet;
* die **Steilheit** der Heizkurve bleibt, wie sie ist – Kelvin je Kelvin ist
  dasselbe Verhältnis wie Grad Fahrenheit je Grad Fahrenheit.

**Wechselt das Maßsystem**, werden die gespeicherten Werte einmal umgerechnet
und die neue Einheit in `config.json` vermerkt. Ohne das bliebe ein
Komfortwert von 21 die Zahl 21 – und der Planer kühlte das Haus auf 21 °F
herunter. Die Umrechnung steht im Protokoll.

## Sprache

Der Planer spricht Deutsch und Englisch. Die Sprache nimmt er von Home
Assistant (`/config` → `language`) und folgt einer Änderung dort ab dem
nächsten Takt; alles außer Deutsch zeigt Englisch.

Drei Dinge bleiben mit Absicht deutsch, weil sie Daten sind und keine
Oberfläche:

* die **Entitäts-IDs** (`sensor.heizungsplaner_raum_wohnzimmer`) – sie stecken
  in jeder bestehenden Einrichtung, ein Umbenennen bräche Dashboards und
  Automationen;
* die **Schlüssel** der Modi und Zustände (`komfort`, `sommer`, `fenster`), so
  wie sie in der gespeicherten Konfiguration und in den MQTT-Attributen
  stehen;
* die **Namen**, die man Räumen, Regeln und Geräten gegeben hat.


## Eine Sprache ergänzen

Der Planer spricht Deutsch und Englisch. Eine dritte Sprache sind zwei Dateien
und keine Codeänderung:

**1. Das Backend** – in `backend/texte.py` steht jeder Satz, den der Planer
schreibt. Jeder Eintrag ist eine kleine Tabelle; eine Spalte kommt dazu:

```python
"zeitplan": {
    "de": "Zeitplan: {modus} ab {uhrzeit} Uhr",
    "en": "Schedule: {modus} from {uhrzeit}",
    "fr": "Programme : {modus} à partir de {uhrzeit}",
},
```

Die Platzhalter müssen in allen Sprachen dieselben sein – genau das prüft der
Prüflauf, ebenso die Tabellen `MODUS` und `ZUSTAND`. Welche Sprachen es gibt,
leitet der Planer aus diesen Einträgen ab; angemeldet wird nichts.

**2. Die Oberfläche** – `frontend/sprachen/en.js` nach `<code>.js` kopieren,
in der ersten Zeile `window.SPRACHEN.fr = {` setzen, `locale` eintragen (sie
entscheidet über Dezimaltrenner und Uhrzeitform) und die rechte Seite
übersetzen. Die Datei hat drei Teile: `woerter` für feste Texte, `muster` für
Texte mit Zahlen darin, `vorlagen` für die Zeitplan-Vorlagen.

Schlüssel ist immer der **deutsche Originaltext** – so bricht ein vergessener
Eintrag nichts, er bleibt schlicht deutsch stehen.

**Was der Aufbau nicht abdeckt:** Die Einträge unter `muster` sind reguläre
Ausdrücke und setzen voraus, dass Ein- und Mehrzahl sich verhalten wie im
Deutschen und Englischen. Sprachen mit mehr Pluralformen – Polnisch oder
Russisch etwa – brauchen ein Muster je Form oder einen Umbau auf echte
Schlüssel.

Fehlt eine Sprache zur Laufzeit, gilt Englisch; fehlt auch das, bleibt es bei
Deutsch. Eine halbfertige Übersetzung räumt die Oberfläche also nie leer.
