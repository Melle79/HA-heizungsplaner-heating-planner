# Änderungen

## 1.25.0

- **Neu: Der Planer kann die Kesselregelung mitführen.** Bisher stellte er
  Thermostatventile, während die Heizungsregelung ihr eigenes Zeitprogramm
  fuhr – beide arbeiteten gegeneinander. Der Planer heizte morgens vor,
  während der Kessel noch absenkte; abends hielt der Kessel Vorlauf bereit,
  den kein Raum mehr wollte.
- Eingeschaltet wird das unter *Einstellungen → Kesselregelung*. Es braucht
  das Add-on **Heizungsanlagenmanager**; der Planer meldet dort die
  Programmwahl zur Übernahme an und führt sie nach dem Wärmebedarf der Räume:
  **Nenn**, sobald ein Raum Komfort will · **Reduziert**, wenn alle abgesenkt
  sind · **Sommer** im Sommerbetrieb · **Standby**, wenn kein Raum geregelt
  wird.
- Geschrieben wird wie überall **auf Flanke**: Steht die Betriebsart schon so,
  geht kein Telegramm über den Bus.
- **Hebt jemand die Übernahme im Anlagenmanager auf, bleibt sie aufgehoben.**
  Der Planer schaltet die Führung daraufhin selbst ab und vermerkt es im
  Protokoll. Ein Knopf, den ein Programm zwei Minuten später wieder aushebelt,
  wäre eine Attrappe.
- Neue Entität `sensor.heizungsplaner_kessel` mit der Betriebsart im Klartext
  – sie erscheint nur bei eingeschalteter Führung.
- Ab Werk ist die Kesselregelung **aus**. Sie greift über ein zweites Add-on
  in die Anlage selbst; so etwas schaltet man bewusst ein oder gar nicht.

## 1.24.1

- **Behoben: Tankwerte ohne Zahl landeten auf `unavailable` statt `unknown`.**
  Für „kein Wert" hatte ich das Wort `unknown` gesendet. Das ist für einen
  Sensor mit Geräteklasse keine gültige Zahl – Home Assistant erklärte die
  Entität daraufhin für nicht verfügbar. Vorgeschrieben ist die Zeichenfolge
  `None`; daraus wird dort der Zustand *unbekannt*.
- Betroffen war vor allem die Reichweite, solange noch kein Verbrauch
  vorliegt. Am Verhalten des Add-ons ändert sich sonst nichts.

## 1.24.0

- **Behoben: Eine Änderung der Umrechnung veränderte die Ölmenge in die
  falsche Richtung.** Der Füllstand lag in Litern gespeichert, eingegeben
  worden war er aber als *Ablesung*. Wer danach den Nullpunkt berichtigte,
  bekam mehr Öl statt weniger – die Literzahl blieb stehen, und der Planer
  behauptete eine Anzeige, die am Tank gar nicht stand.
- **Die Ablesung ist jetzt die gespeicherte Wahrheit**, die Literzahl nur
  daraus abgeleitet: Stand = letzte Beobachtung minus Verbrauch seitdem.
  Ändert sich die Umrechnung – anderer Nullpunkt, neue Einmessung –, wandert
  die Literzahl mit, und der Zeigerstand bleibt der, den man abgelesen hat.
- Wer den Stand in **Litern** einträgt, bekommt weiterhin Liter. Auch eine
  Lieferung setzt die Grundlage neu.
- Ein Zustand aus einer älteren Fassung behält seinen Literwert – beim Update
  springt nichts.
- Die Oberfläche zeigt als Hinweis am Bestand, worauf er beruht: welche
  Ablesung, von wann.

## 1.23.0

- **Neu: Was das Heizöl kostet.** Zu jeder Lieferung lässt sich **Preis je
  Liter** oder **Gesamtpreis** eintragen – eines genügt, das andere rechnet
  sich aus der Menge. Ein Komma statt Punkt wird verstanden.
- Bewertet wird der Verbrauch zum **gleitenden Durchschnittspreis**: Jede
  Lieferung mischt sich mit dem Restbestand, so wie das Öl im Tank auch. Das
  ist die übliche Lagerbewertung und die einzige Rechnung, die ohne
  Erfindungen auskommt.
- Neu im Reiter: **Kosten dieses Monats**, **Kosten der Heizperiode**,
  Mischpreis und **Wert des Bestands**. Die Monatsliste und die
  Lieferungsliste zeigen die Beträge mit.
- Neu in Home Assistant: **Heizöl Kosten** mit `device_class: monetary` und
  `state_class: total_increasing` – damit steht die Heizölrechnung in
  derselben Langzeitstatistik wie Strom und Gas.
- Ohne Preisangabe bleibt alles bei Litern. Erfundene Zahlen gibt es nicht.

## 1.22.0

- **Neu: „Der Tank wurde voll gefüllt".** Ein Haken beim Eintragen einer
  Lieferung, und der Planer rechnet sich die ganze Geometrie selbst aus. Der
  Tankwagen füllt bis zur Abschaltung des Grenzwertgebers, der Inhalt danach
  ist also bekannt. Zusammen mit den beiden Ablesungen sind das zwei
  Gleichungen für zwei Unbekannte – heraus fallen **Liter je Zentimeter**,
  die **Anzeige bei vollem Tank** und der **Nullpunkt**.
- Damit erübrigt sich der Gang mit dem Peilstab in den Dom, um den Versatz
  einer nachgerüsteten Skala zu bestimmen.
- Der Stand nach einer vollen Füllung ist der bekannte Inhalt – er schlägt
  jede Ablesung und jede Fortschreibung.
- Kommt ein **negativer** Nullpunkt heraus, sagt der Planer das jetzt in der
  Oberfläche statt nur im Log: Dann passt der eingetragene Nenninhalt nicht zu
  dieser Skala, und beides gehört überprüft.

## 1.21.0

- **Neu: Nullpunkt für nachgerüstete Anzeiger.** Bisher rechnete der Planer
  „Liter = cm × Liter je Zentimeter" und nahm damit an, dass der Zeiger bei
  leerem Tank auf null steht. Bei einem nachträglich aufgeschraubten Anzeiger
  stimmt das selten – eine 150-cm-Skala auf einem 130-cm-Tank, ein zu lang
  abgelängter Faden, und die ganze Skala liegt verschoben. Unter *Anzeige bei
  leerem Tank* lässt sich der Versatz jetzt eintragen; gerechnet wird ab dann
  mit der Höhe **über dem Nullpunkt**.
- Vorgabe ist 0 – für passende Geräte ändert sich damit nichts.
- Die Einmessung über eine Lieferung war davon nie betroffen: Sie rechnet mit
  der Differenz zweier Ablesungen, und ein Versatz kürzt sich heraus. Das ist
  jetzt auch so geprüft.
- Auch die geschätzte Steigung berücksichtigt den Nullpunkt: Sie teilt den
  Tankinhalt durch die Höhe *über* ihm, nicht durch die Skalenhöhe.

## 1.20.0

- **Neu: Der Ölverbrauch bekommt ein Gedächtnis.** Bisher hielt der Planer nur
  60 Tagewerte – genug für die Reichweite, aber die Frage „wie viel war es
  letzten Winter" konnte er nicht beantworten. Jetzt bleiben **Monatssummen
  dauerhaft** erhalten, und der Reiter zeigt diesen Monat, die laufende
  Heizperiode und den Gesamtverbrauch. Die Heizperiode beginnt im **Juli**;
  ein Kalenderjahr zerschnitte den Winter in der Mitte.
- **Neu: Der Tank kommt nach Home Assistant.** Fünf Entitäten, die nur
  entstehen, wenn der Tankteil eingeschaltet ist – und wieder verschwinden,
  wenn er abgeschaltet wird: erreichbare Menge, Menge im Tank, Reichweite,
  Leckagemelder und der Gesamtverbrauch.
- **„Heizöl verbraucht" trägt `state_class: total_increasing`.** Damit baut
  Home Assistant von selbst eine Langzeitstatistik mit Tages-, Monats- und
  Jahreswerten, die den Verlust der Add-on-Daten überlebt. Wer InfluxDB an
  Home Assistant hängt, bekommt den Verlauf dort ohne weiteres Zutun.
- Ein Tank ohne bekannten Stand meldet `unknown` statt null. Eine erfundene
  Null landete sonst als echter Messwert in der Statistik.
- Beim Ein- und Ausschalten des Tankteils wird die Discovery sofort erneuert,
  nicht erst beim nächsten Neustart.

## 1.19.0

- **Neu im Öltank: der Peilstab.** Wer den Stand am Tank in Zentimetern
  abliest, kann jetzt *Anzeige bei vollem Tank*, *Untergrenze* und *Liter je
  Zentimeter* eintragen. Alles freiwillig – ohne diese Felder verhält sich der
  Tankteil wie bisher.
- **Einmessen statt schätzen.** Beim Eintragen einer Lieferung lassen sich der
  Stand *vorher* und *nachher* in Zentimetern angeben. Daraus fällt die
  Liter-je-Zentimeter heraus: gelieferte Menge geteilt durch den
  Höhenunterschied. Das ist der genaueste Wert, den es über diesen Behälter je
  geben wird – aus einer geeichten Menge und dem Tank selbst statt aus einem
  Typenschild. Er trägt sich in die Einstellungen ein, und der abgelesene Stand
  ersetzt danach die gerechnete Summe: Eine Messung schlägt eine
  Fortschreibung.
- **Die ehrliche Restmenge.** Der Saugfuß sitzt einige Zentimeter über dem
  Boden; was darunter steht, hilft dem Brenner nicht mehr. Mit einer
  Untergrenze zeigt der Reiter jetzt „für den Brenner erreichbar" als
  Hauptzahl und „im Tank" klein darunter. Warnschwelle und Reichweite rechnen
  mit der erreichbaren Menge. Fällt der Stand unter den Saugfuß, gibt es eine
  eigene Meldung – der Brenner zieht dann Luft und geht auf Störung.
- Der Füllstand lässt sich von Hand nun auch **in Zentimetern** setzen. Das ist
  die Zahl, die am Tank steht.
- Abgefangen: verdrehte Höhen (nachher unter vorher), Zentimeter ohne
  Kalibrierung und eine Untergrenze über der Füllhöhe.

## 1.18.0

- **Suche über den Auswahllisten.** Wer in einer gewachsenen Installation den
  Workday-Sensor sucht, scrollt sonst an „Aquarium-Membranpumpe“ vorbei. Ab
  zwölf Einträgen erscheint über der Liste ein Suchfeld, das Namen und
  Entitäts-ID durchsucht. Bei drei Wetterquellen bleibt es weg – dort wäre es
  nur im Weg.
- **Geändert: Aus der Quelle „Feiertag“ wird „Arbeitstag“.** Die Umkehrung ist
  Absicht: Gemeint ist jetzt ein Schalter, der **an** ist, wenn gearbeitet
  wird. Genau das liefert die **Workday-Integration** von Home Assistant
  (`binary_sensor.workday_sensor`), und sie kennt Wochenende *und* Feiertage.
  Damit deckt ein einziges Punktpaar alles ab: *Werktag* mit Haken auf Montag
  bis Freitag, *arbeitsfrei* mit Haken auf allen sieben Tagen. Mit dem reinen
  Feiertagssensor aus v1.17.0 hätte das Wochenende eine dritte Gruppe von
  Punkten gebraucht.
- Wer in v1.17.0 bereits eine Feiertagsquelle eingetragen hatte, muss sie neu
  setzen – die Bedeutung hat sich umgedreht, ein stilles Übernehmen wäre genau
  verkehrt herum gewesen. Die Einstellung war einen Tag alt und ab Werk leer.

## 1.17.1

- **Behoben: Die MQTT-Auto-Discovery war seit v1.15.0 tot.** `mqtt_publisher`
  rief `einheit.einheit()` auf, ohne das Modul zu importieren. Der Aufruf
  steckt im Discovery-Pfad, der seinen Fehler nur in den Log schreibt – die
  Statusentitäten des Planers wurden also sechs Tage lang stillschweigend nicht
  mehr angemeldet. Im Log stand `Discovery fehlgeschlagen: name 'einheit' is
  not defined`.
- Der Prüflauf fängt jetzt die ganze Fehlerklasse: Er liest jedes Modul im
  Backend und meldet jedes `modul.funktion()`, dessen Modul nicht importiert
  ist. Gegen den ursprünglichen Fehler gegengeprüft.

## 1.17.0

- **Neu: Werktag und arbeitsfrei im Zeitplan.** Bisher kannte ein
  Umschaltpunkt nur *immer*, *Schultag* und *schulfrei* – gedacht für
  Kinderzimmer. Wer arbeitet, folgt aber einem anderen Kalender: In den
  Schulferien ist Dienst, an Feiertagen nicht. Dafür gibt es jetzt ein
  zweites Paar, das sich mit dem ersten in einem Plan mischen lässt.
- Die neue Quelle unter *Einstellungen* heißt **Feiertag** und ist bewusst
  getrennt vom Schulfrei-Schalter. Dort gehört **nur** der Feiertag hinein:
  Das Wochenende steckt schon in den Wochentag-Haken des Punktes, und
  Schulferien sind für einen Berufstätigen keine freien Tage. Ohne Angabe
  bleiben die beiden neuen Punktarten wirkungslos – bestehende Pläne
  ändern sich also nicht.
- **Neu: „Wer zum Haushalt zählt".** Bisher zählte **jede** `person.*`-Entität
  aus Home Assistant zur Anwesenheit, und einschränken ließ sich das nur je
  Raum. Das ist heikler, als es klingt: Eine Person **ohne Gerätetracker**
  steht dauerhaft auf „zu Hause" und hält damit jeden Raum für besetzt – die
  Absenkung bei Abwesenheit greift dann nie mehr, ohne dass irgendwo ein
  Fehler auftaucht. Unter *Einstellungen → Anwesenheit* lässt sich jetzt
  global festlegen, wer gemeint ist. **Leer heißt weiterhin: alle**, das
  bisherige Verhalten bleibt also unverändert. Die Auswahl je Raum engt
  innerhalb des Haushalts weiter ein.
- **Neu: Öltank – optional.** Restmenge, Tagesverbrauch, Reichweite und eine
  Leckagewache, zu finden unter *Einstellungen → Öltank*. **Ab Werk aus**: Wer
  ihn nicht einschaltet, sieht den Reiter „Öltank“ gar nicht erst und merkt von
  diesem Baustein nichts.
- Der Füllstand kommt ohne Sensor im Tank aus. Er stützt sich auf zwei Zahlen,
  die sich gegenseitig korrigieren: die **Liefermenge** vom Lieferschein, die
  geeicht ist, aber nur ein- bis zweimal im Jahr kommt – und die
  **Brennerlaufzeit** mal Düsendurchsatz, die die Auflösung dazwischen liefert
  und mit jeder Lieferung wieder eingenordet wird.
- Der Laufzeitzähler ist **optional**. Fehlt er, bleibt der Stand stehen, bis
  jemand eine Lieferung einträgt oder ihn von Hand setzt – der Tankteil ist
  also auch ohne Kesselanbindung brauchbar.
- Gegen die drei Fälle, die einen gerechneten Tank sonst leerfressen: Der
  **erste** gesehene Zählerstand gilt nicht als Verbrauch, ein **Rücksprung**
  (neuer Kessel) wird übernommen statt verbucht, und ein **Sprung** über 24
  Stunden je Takt gilt als Zählerfehler.
- **Leckagewache**: ein Melder im Auffangraum als optionale Entität. Meldung
  einmal beim Ansprechen, nicht alle fünf Minuten. Heizöl leitet keinen Strom –
  ein gewöhnlicher Wassermelder taugt dafür nicht, es braucht einen optischen
  Sensor oder einen Schwimmer. Ohne eigene Meldewege gelten die des Wachhunds.
- Der Tankteil rechnet in einem **eigenen Fangnetz**: Geht dort etwas schief,
  läuft die Heizungsregelung unberührt weiter.
- Die Auswahllisten kennen jetzt **Zählerstände** (Sensoren mit `state_class`
  `total`/`total_increasing` oder Einheit h/min) – daraus wählt man die
  Brennerlaufzeit, statt sich durch alle numerischen Sensoren zu suchen.

## 1.16.1

- **Behoben: Ausfallmeldungen für Geräte, die nur still waren.** Im
  Sommerbetrieb schreibt der Planer nicht mehr – also meldet auch das Gerät
  nichts. Büro, Hobbyraum und Gästezimmer schwiegen dabei über einen Tag und
  wurden als ausgefallen gemeldet, obwohl sie erreichbar waren.
- Vor einer Meldung wird jetzt **angeklopft**: Der Planer lässt Home Assistant
  den Zustand neu holen, wartet zwölf Minuten und meldet erst, wenn auch dann
  nichts kommt. Meldet sich das Gerät, war es nur still.
- Die Schweigefrist steht auf 24 Stunden (vorher 12), im Sommerbetrieb
  weiterhin doppelt.
- Dabei gefunden: Ein **leeres** Thermostat-Gedächtnis wurde verworfen statt
  gefüllt (`or {}` statt `is None`). Bei einer frischen Einrichtung wäre der
  Weckruf-Merker sofort wieder weg gewesen.

## 1.16.0

- **Vorbereitet für weitere Sprachen.** Die Oberfläche lädt ihre Sprachdatei
  jetzt nach Sprachcode aus `frontend/sprachen/<code>.js`; die Mechanik steckt
  in `uebersetzung.js` und kennt keine einzige Vokabel mehr.
- Welche Sprachen es gibt, leitet das Backend aus `texte.py` ab – eine neue
  Sprache ist eine Spalte in der Tabelle und eine Datei im Frontend, sonst
  nichts.
- **Ausweichkette:** Fehlt eine Sprache, gilt Englisch; fehlt auch das, bleibt
  es bei Deutsch. Eine halbfertige Übersetzung räumt die Oberfläche nicht
  leer.
- Das Zahlen- und Uhrzeitformat steht in der Sprachdatei (`locale`) statt in
  einer Fallunterscheidung mit zwei Zweigen.
- Der Prüflauf sieht die Sprachdateien durch: Meldet sich jede unter ihrem
  Dateinamen an, hat sie alle Teile, und gibt es sie auch im Backend?
- Beide Handbücher erklären, wie man eine Sprache ergänzt – samt der Grenze
  des Verfahrens bei Sprachen mit mehr als zwei Pluralformen.

## 1.15.1

- README und Add-on-Beschreibung nennen die Einheit: Der Planer folgt Home
  Assistant nicht nur in der Sprache, sondern auch in Celsius oder Fahrenheit.
  Im Handbuch stand es bereits.

## 1.15.0

- **Celsius oder Fahrenheit, je nach Maßsystem von Home Assistant.** Die
  Einheit steht in derselben Antwort wie die Sprache und wird bei jedem Takt
  gelesen. Anzeige, Vorgaben, Grenzen und die Schrittweite folgen ihr.
- Spannen werden dabei anders gerechnet als Temperaturen: Aus 1,5 K Hysterese
  werden 2,7 °F, nicht 34,7. Die Steilheit der Heizkurve bleibt unverändert –
  sie ist ein Verhältnis.
- **Beim Wechsel des Maßsystems werden die gespeicherten Werte umgerechnet**
  und die Einheit in `config.json` vermerkt. Ohne das bliebe ein Komfortwert
  von 21 die Zahl 21 – und der Planer kühlte das Haus auf 21 °F herunter.
- In Fahrenheit wird in ganzen Graden gestellt und die Beispiele der Heizkurve
  rechnen mit 14/32/50 °F statt mit −10/0/10 °C.
- Für deutsche Installationen ändert sich nichts.

## 1.14.0

- **Der Planer spricht Englisch.** Oberfläche, Begründungen, Protokoll,
  Störungsmeldungen und Hinweise gibt es jetzt in zwei Sprachen. Eingestellt
  wird nichts: Die Sprache kommt von Home Assistant (`/config` → `language`)
  und folgt einer Änderung dort ab dem nächsten Takt.
- Deutsch bleibt für deutsche Installationen unverändert – Wort für Wort.
- Zahlen und Uhrzeiten folgen der Sprache: „21,5 °C“ im Deutschen,
  „21.5 °C“ im Englischen.
- **Namen bleiben unangetastet.** Räume, Regeln und Geräte sind Daten, keine
  Oberfläche; ebenso die Entitäts-IDs und die Schlüssel der Modi und Zustände,
  die in jeder gespeicherten Konfiguration stecken.
- README und Handbuch gibt es auf Englisch (`README.md`, `DOCS.md`) und auf
  Deutsch (`README.de.md`, `DOCS.de.md`).
- Der Prüflauf hält die Sprachen gegeneinander: gleiche Schlüssel, gleiche
  Platzhalter. Eine halbe Übersetzung fällt damit sofort auf.

## 1.13.2

- `uebersteuerung_bis` ist nie mehr leer: „bis 14:00 Uhr“, solange die Regel
  greift, sonst „ruht“. Eine Tile-Karte fällt bei einem leeren Attribut auf
  den Zustand des Sensors zurück – auf der Homeoffice-Kachel stand dann der
  Zielwert von 8 °C, der wie eine Außentemperatur aussah.

## 1.13.1

- Der Raum-Sensor trägt zusätzlich `uebersteuerung_bis` – „bis 14:00 Uhr“,
  solange eine Regel greift, sonst „läuft“ bei Regeln ohne Zeitfenster. Für
  eine Dashboard-Kachel ist das die nützlichere Angabe als der Zielwert.

## 1.13.0

- **Die Lage der Übersteuerungsregel geht über MQTT nach Home Assistant.** Der
  Raum-Sensor trägt jetzt `uebersteuerung` (Name der Regel),
  `uebersteuerung_greift` und `uebersteuerung_lage` (Grund im Klartext) als
  Attribute – damit lässt sich eine Dashboard-Karte bauen, ohne die Begründung
  nach Stichworten zu durchsuchen.

## 1.12.2

- **„Heute nicht“ statt „nicht“.** Scheitert eine Regel an einem Ferientag
  oder einem freien Tag, steht dort jetzt *greift heute nicht – Ferien &
  Feiertage läuft*; scheitert sie an einer abwesenden Person, *greift gerade
  nicht – Isabel ist nicht zu Hause*. Ein Ferientag gilt bis Mitternacht, eine
  Person kann in fünf Minuten zurück sein – das sind zwei verschiedene
  Aussagen.

## 1.12.1

- **„Ruht“ sagt jetzt, warum.** Statt eines Worts, das man erst deuten muss,
  steht dort *greift nicht: Ferien & Feiertage* – die erste Bedingung, die
  nicht zutrifft – oder *greift nicht: außerhalb 08:00–18:00*, wenn allein die
  Uhrzeit sie zurückhält. Meldet eine Entität gar nichts, steht das dort.
- Die Anzeige sitzt unter der Kopfzeile, damit ein langer Grund den
  Löschknopf nicht verschiebt.

## 1.12.0

- **Zeitfenster je Übersteuerungsregel.** Ohne eines liefe eine
  Homeoffice-Regel auch nachts um drei weiter – ihre Bedingungen treffen ja
  weiterhin zu. Neue Regeln bekommen 08:00–18:00 vorgeschlagen; leere Zeiten
  heißen rund um die Uhr, und ein Fenster darf über Mitternacht reichen.
- Die Regel zeigt „ruht – außerhalb der Zeit“, wenn allein das Fenster sie
  gerade zurückhält.

## 1.11.2

- **Man sieht jetzt, ob eine Übersteuerungsregel greift.** Die Regel zeigt
  *greift gerade* oder *ruht*, und vor jeder Bedingung steht ein Häkchen oder
  ein Kreuz mit ihrem aktuellen Stand. Bisher blieb nur Raten, warum ein Raum
  im Zeitplan steht statt auf Komfort.

## 1.11.1

- **Behoben: Ausfallmeldungen für Geräte, denen nichts fehlt.** Die
  Schweigefrist stand auf sechs Stunden. Gemessen über drei Tage melden die
  Thermostate im Sommerbetrieb aber regulär bis zu 13 Stunden nichts – die
  Ventile sind zu, es gibt nichts zu berichten. Die Vorgabe liegt jetzt bei
  zwölf Stunden und gilt im Sommerbetrieb doppelt.

## 1.11.0

- **Die Übersteuerung kennt jetzt Bedingungen statt eines Schalters.** Eine
  Regel greift, solange alle ihre Bedingungen zutreffen – damit entsteht eine
  Homeoffice-Regelung ganz ohne Schalter: *Werktag ist an*, *Ferien sind aus*,
  *Isabel ist zu Hause* → Komfort.
- Als Bedingung taugt alles, was an oder aus sein kann: Schalter, Melder,
  Kalender und Personen. Eine Person zählt als „an“, solange sie zu Hause ist;
  eine andere Zone zählt als fort.
- Jede Regel kann eine Bezeichnung tragen. Sie steht in der Begründung und im
  Protokoll – „Homeoffice“ statt einer Aufzählung von Entitäten.
- Abrufe der Oberfläche laufen mit `no-store`. Sonst beantwortet der Browser
  eine Abfrage schon mal aus dem Cache und zeigt einen Stand von vorgestern.

## 1.10.0

- **Übersteuerung je Raum.** Im Reiter *Zeitplan* lassen sich Schalter aus
  Home Assistant hinterlegen, die den Plan außer Kraft setzen, solange sie an
  sind – ein Homeoffice-Schalter hält das Büro so auf Komfort, statt es
  vormittags abzusenken. Mehrere Schalter sind möglich, der oberste gewinnt.
- Offenes Fenster, Sommerbetrieb, Urlaub und die Anwesenheitsabsenkung bleiben
  stärker: Ein vergessener Schalter heizt kein leeres Haus.

## 1.9.2

- **Der Planer erinnert an die FRITZ!-Sommerpause**, sobald der Sommerbetrieb
  endet und ein Thermostat noch auf `summer` steht. Ein solches Gerät lehnt
  jeden Sollwert ab, und beenden lässt sich der Modus nur in der FRITZ!Box –
  Home Assistant zeigt ihn nur an. Bisher fiel das erst auf, nachdem der Raum
  drei Schreibversuche lang kalt geblieben war.

## 1.9.1

- **Eine verschwundene Batterieanzeige wird sofort neu gesucht.** Die
  Zuordnung Thermostat → Batterie wurde nur stündlich erneuert. Wird eine
  Entität umbenannt, hielt der Planer bis zu einer Stunde an der toten ID fest
  – und meldete eine schwache Batterie in der Zwischenzeit als behoben.

## 1.9.0

- **Die geräteeigene Fenstererkennung eines Thermostats gilt nicht mehr als
  Kontakt.** Sie löst weiterhin aus, verdrängt die Temperatursturz-Erkennung
  aber nicht mehr. Bisher genügte eine solche Meldung, um den Sturz
  abzuschalten – die Gästetoilette stand damit ohne Fenstererkennung da, denn
  ihr FRITZ!-Thermostat meldet in der Sommerpause gar nichts.
- In der Auswahlliste sind solche Melder als *geräteeigene Erkennung*
  gekennzeichnet, und ihr Schweigen wird nicht mehr als Ausfall angemahnt.

## 1.8.11

- **Behoben: Ein Raum zeigte die Personen des zuvor geöffneten Raumes.** Die
  Personenliste wurde beim Öffnen nicht zurückgesetzt und übernahm ihren Stand
  aus der Anzeige statt aus dem Raum. Wer nacheinander zwei Räume öffnete, fand
  im zweiten die Zuordnung des ersten – und hätte sie beim Speichern dorthin
  übernommen. Betroffen war nur die Fassung 1.8.9/1.8.10 vom 25.08.2026.
- Grundsätzlich behoben statt nur für die Personen: Eine Auswahlliste
  übernimmt den Stand aus der Anzeige jetzt ausschließlich beim Filtern.
  Befüllt sie jemand von außen, gilt der übergebene Wert.

## 1.8.10

- **„Mittelwert der Thermostate“ sagt jetzt, welcher.** Gemeint waren immer
  die Thermostate des Raumes – die im Reiter *Grundlagen* angehakten –, aber
  das stand nirgends. Der Hinweis nennt sie beim Namen und zählt sie mit; er
  folgt der Auswahl, während man sie ändert.

## 1.8.9

- **Geräte werden angehakt statt markiert.** Thermostate, Präsenzmelder,
  Fensterkontakte, Personen und Meldewege stehen jetzt in Häkchenlisten. In
  einer Mehrfachauswahl musste man scrollen und eine Markierung deuten, um zu
  sehen, was zugeordnet ist.
- Eine Zeile je Gerät: Name und Entitäts-ID laufen zusammen und werden am Ende
  gekürzt, der volle Text steht im Tooltip. Die ID entfällt, wo sie dem Namen
  entspricht – bei den Meldewegen stand sonst alles doppelt.
- Der Knopf *Zuordnen* aus dem Hinweisbalken setzt das Häkchen und scrollt die
  Zeile in die Mitte.

## 1.8.8

- **Die Auswahllisten im Raum lassen sich filtern.** Über jeder Liste steht
  jetzt ein Suchfeld und ein Häkchen „nur dieser Raum“. Bisher standen unter
  den Fensterkontakten des Wohnzimmers auch die Haustür, der Briefkasten und
  gut zweihundert sonstige Melder.
- Als „gehört zu diesem Raum“ zählt nicht nur der Bereich, sondern auch der
  Name: `binary_sensor.heizung_wohnzimmer_offenes_fenster_erkannt` trägt gar
  keinen Bereich, ein reiner Bereichsfilter hätte im Wohnzimmer genau den
  Kontakt verborgen, den man dort sucht.
- Die Gruppe **Sonstige Melder** erscheint erst beim Suchen. Sie ungefragt
  unter die fünf echten Kontakte zu hängen machte die Liste unbrauchbar.
- Zugeordnete Geräte bleiben immer sichtbar, gleich wie gefiltert wird – eine
  ausgeblendete Zuordnung ginge beim Speichern verloren.
- Die Thermostatliste ist jetzt ebenfalls nach Bereich gruppiert, der eigene
  Bereich zuoberst.

## 1.8.7

- **Eigenes Icon und Logo.** Ein Heizkörper, darüber die Stufenkurve eines
  Tagesplans – im Add-on-Store und in der Seitenleiste stand bisher ein
  allgemeines Symbol.
- **Dokumentation mit Bildern.** README und Anleitung zeigen jetzt die
  Oberfläche: Übersicht, Räume, Raum-Dialog, Einstellungen und Protokoll. Die
  Anleitung beginnt mit einem Rundgang und einer Tabelle der Zustandsworte.
- In der Anleitung fehlten in der Rangfolge die Freigabe und die Partytaste;
  die Tabelle stimmt jetzt mit der Regelkette überein. Der Abschnitt über den
  Knopf „Jetzt prüfen“ stand zweimal darin.
- Beim Öffnen eines Raumes lag der Fokus auf „Schließen“. Er sitzt jetzt im
  Namensfeld, wenn ein Raum neu angelegt wird, und sonst nirgends.

## 1.8.6

- Der Knopf „Jetzt rechnen“ heißt jetzt **„Jetzt prüfen“**, erklärt sich beim
  Überfahren und meldet nach dem Durchlauf, wie viele Thermostate gestellt
  wurden – oder dass nichts zu tun war. Vorher blieb offen, was er überhaupt
  bewirkt.

## 1.8.5

- Die Dashboard-Karten liegen jetzt im Repository unter
  `heizungsplaner/dashboard/`: als fertige YAML-Fassung zum Einfügen, dazu der
  Baukasten und ein Erzeuger. Bisher gab es sie nur auf dem Rechner, von dem
  aus sie eingespielt wurden.

## 1.8.4

- **Im Raum-Dialog ließ sich das Ende nicht erreichen.** Die Innenhöhe war
  ausgerechnet (`84vh − 168px`); bei niedrigen Fenstern ging die Rechnung nicht
  auf und die Fußzeile legte sich über den Inhalt. Der Dialog ist jetzt ein
  Flex-Behälter – Kopf, Reiter und Fußzeile behalten ihre Höhe, das Blatt
  dazwischen nimmt den Rest und scrollt. Geprüft bis hinunter zu 300 Pixeln
  Fensterhöhe.
- Beim Wechsel des Reiters beginnt der Inhalt wieder oben.

## 1.8.3

- Die Störungsentität trennt Meldungen nach Schwere (`fehler`, `warnungen`
  samt Anzahl). Damit kann ein Dashboard Ausfälle und bloße Hinweise
  unterschiedlich darstellen, statt beides in eine Liste zu werfen.

## 1.8.1

- Das Protokoll färbt Einträge nach ihrer Schwere: Störungen rot, Fehlschläge
  und Handeingriffe gelb, Entwarnungen grün. Die Einordnung geschieht auch
  beim Lesen, damit bereits vorhandene Einträge mitgefärbt werden.

## 1.8.0

- **Der Planer setzt aus, solange Home Assistant startet.** Nach einem Neustart
  liefert Home Assistant seine Entitäten nach und nach; die Oberfläche meldete
  in dieser Phase ein Dutzend angeblich verschwundener Thermostate und Melder.
  Vor jedem Takt wird nun geprüft, ob Home Assistant `RUNNING` meldet – sonst
  wird nicht geschaltet, nichts gemeldet und nichts benachrichtigt.

## 1.7.6

- **Veraltete Batteriestände warnen nicht mehr.** Manche Geräte melden den
  Ladestand nur bei Änderung; nach einem Batteriewechsel steht dort noch der
  alte Wert, und die Warnung schickte jemanden nach Batterien, die längst
  gewechselt waren. Stände, die älter als zwölf Stunden sind, bleiben
  unberücksichtigt; die Meldung nennt jetzt die Uhrzeit der Messung.

## 1.7.4

- **Ein verschluckter Befehl wird nicht mehr für einen Handeingriff gehalten.**
  Im Betrieb aufgefallen: Ein Thermostat quittierte den Sollwert und stand
  danach unverändert da. Nach Ablauf der Bestätigungsfrist hätte der Planer das
  als Handeingriff gewertet und sich bis zum nächsten Zeitplanwechsel
  zurückgezogen – der Raum wäre auf einem Wert geblieben, den niemand wollte.
  Jetzt merkt er sich den Wert vor dem Befehl: Steht das Gerät noch genau
  darauf, versucht er es erneut und meldet es nach drei Fehlschlägen.

## 1.7.3

- Die Partytaste meldet die Restzeit als fertigen Text (`anzeige`), etwa
  „noch 2 h 47 min, bis 19:03 Uhr“ – die Kachel zeigt damit die verbleibende
  Zeit statt eines „Ein“, das ohnehin am Schalter steht.
- Die Auswahl der Party-Räume speichert sich beim Anklicken selbst. Bisher
  hing sie am gemeinsamen „Speichern“ und wurde mitgeschrieben, sobald jemand
  nur die Dauer änderte – dabei konnte eine veraltete Liste die Auswahl still
  überschreiben.
- Party-Symbol in der Raumübersicht ergänzt.

## 1.7.2

- Die Partytaste liefert das Ende zusätzlich als fertige Uhrzeit
  (`bis_uhrzeit`). In Lovelace-Templates gibt es kein `strftime`; die
  Zeitrechnerei dort war eine Fehlerquelle, die im Zweifel eine ganze Karte
  lahmlegt.

## 1.7.1

- **Thermostate, die Sollwerte ablehnen, werden gemeldet.** Im Betrieb
  aufgefallen: Die beiden FRITZ!-Geräte stehen in der Sommerpause und nehmen
  nichts an – der Planer versuchte es bei jedem Takt aufs Neue. Nach drei
  Fehlschlägen gilt das jetzt als Störung, die Meldung nennt die Sommerpause
  als mögliche Ursache, und weitere Versuche erfolgen nur noch alle 30 Minuten.
- Die Partytaste liegt jetzt auch als Kachel auf der Dashboard-Ansicht.

## 1.7.0

**Partytaste.** Einmal drücken, und die gewählten Räume gehen für die
eingestellte Dauer (Vorgabe drei Stunden) auf Komfort. Danach stellt sie sich
von selbst zurück.

- Bedienbar über den Knopf in der Oberfläche (zeigt die Restzeit), über
  `switch.heizungsplaner_party` in Home Assistant und über `POST /api/party`.
- In den Einstellungen lässt sich festlegen, **welche Räume mitmachen** und mit
  welchem Sollwert.
- Rangfolge: vor Urlaub und Sommerbetrieb, aber nach dem offenen Fenster.

## 1.6.1

- Anleitung um das Rezept „ein Raum soll nur vor dem Auskühlen geschützt
  werden“ ergänzt, samt Prüffällen: ein Schaltpunkt als Untergrenze, keine
  Heizkurve, keine Anwesenheitsabsenkung – und eine Handeinstellung, die bis
  zum nächsten Schaltpunkt hält.

## 1.6.0

- Jeder Raum meldet jetzt nicht nur, **wann** der nächste Umschaltpunkt fällig
  ist, sondern auch **worauf** er stellt: Uhrzeit, Modus und Zielwert. Der
  Zeitpunkt allein sagt wenig – wer auf die Übersicht schaut, will wissen, was
  gleich passiert. Als Attribute an `sensor.heizungsplaner_raum_<name>`.

## 1.5.5

- **Ein Wechsel des Raumfühlers löst keinen Fensteralarm mehr aus.** Zwei
  Fühler in einem Raum zeigen selten dasselbe; der Sprung beim Umschalten sah
  aus wie ein Temperatursturz und schickte den Raum auf Frostschutz. Beim
  Quellenwechsel wird das Temperaturgedächtnis nun verworfen.

## 1.5.4

- Wird ein Raum umbenannt oder gelöscht, verschwindet jetzt auch seine Entität
  aus Home Assistant. Bisher blieb ein Geisterraum stehen: Die
  Discovery-Nachricht ist „retained“ und überlebte das Add-on.

## 1.5.3

- **Thermostate, die sich nicht abschalten lassen.** Im Betrieb beobachtet:
  Ein SwitchBot-Thermostat nimmt das „aus“ an und steht eine Minute später
  wieder auf `heat`. Der Planer hätte das bei jedem Takt wiederholt –
  Dauerfeuer, das nur Batterie kostet. Nach zwei vergeblichen Versuchen
  schließt er das Ventil nun über den Frostschutzwert und schreibt es ins
  Protokoll.

## 1.5.2

- Zeitzonenfehler in der Überwachung behoben: Die zeitzonenlose Ortszeit des
  Planers wurde als UTC gelesen, wodurch jedes Gerät um den Zeitzonenversatz
  zu alt erschien – im Sommer zwei Stunden. Bei einer Schweigefrist von sechs
  Stunden hätte das zu frühem Alarm geführt.

## 1.5.1

- Knopf „Probemeldung senden“ in den Einstellungen. Ob ein Meldeweg trägt,
  merkte man sonst erst im Ernstfall – und dann ist es zu spät.

## 1.5.0

**Überwachung der Thermostate.** Anlass: Während eines Urlaubs fielen vier
Thermostate wegen leerer Batterien aus, ohne dass es jemand mitbekam.

- Der Planer wacht über das **Lebenszeichen** jedes Thermostats. Eine
  Batteriewarnung allein trüge nicht weit – die SwitchBot-Geräte melden über
  Matter gar keinen Ladestand.
- Erkannt werden: verschwundene Entitäten, `unavailable`, ausbleibende
  Meldungen (Vorgabe: 6 Stunden) und – wo es eine Anzeige gibt – schwache
  Batterien.
- Gemeldet wird über frei wählbare `notify`-Dienste, **einmal beim Auftreten
  und einmal bei der Behebung**.
- Neue Entitäten `binary_sensor.heizungsplaner_stoerung` und
  `sensor.heizungsplaner_stoerungen` für eigene Automationen.

## 1.4.3

- Der Prüflauf liegt jetzt im Repository unter `heizungsplaner/tests/` und
  läuft ohne Home Assistant und ohne Fremdpakete.
- Anleitung um den Rückweg zur vorherigen Steuerung ergänzt.

## 1.4.2

- Abstand zwischen Name und Aufenthalt in der Personenübersicht.

## 1.4.1

- **Die Heimkehr-Erkennung sah nur die Entfernung an.** Wer eine Schule in
  einem Kilometer Abstand besucht, galt damit den ganzen Vormittag als „auf
  dem Heimweg", und die Anwesenheitsabsenkung des Kinderzimmers lief ins
  Leere. Jetzt zählt eine Person nur dann als heimkehrend, wenn sie zusätzlich
  **in keiner Zone steht** und ihre Entfernung über die letzten 15 Minuten um
  eine einstellbare Mindestannäherung (Vorgabe 0,3 km) abgenommen hat.
- Die Personenübersicht zeigt jetzt den Zonennamen („Realschule") statt einer
  Entfernung und vermerkt, wer näher kommt.

## 1.4.0

Die Oberfläche ist neu aufgebaut. Sie war über die vorangegangenen
Erweiterungen gewachsen, ohne dass die Anordnung mitgewachsen wäre.

- **Übersicht:** Eine Lage-Leiste über den Raumkacheln beantwortet die vier
  Fragen, die man zuerst stellt – Betriebszustand, Außentemperatur, wie viele
  Räume geregelt werden, wann der nächste Wechsel kommt. Die Kacheln zeigen
  Zielwert und Begründung; die Thermostate liegen darunter in einem
  aufklappbaren Fach statt immer sichtbar.
- **Raum-Dialog:** statt einer Scrollstrecke aus sieben Abschnitten nun fünf
  Reiter – Grundlagen, Temperaturen, Zeitplan, Belegung, Fühler und Melder.
- **Raumliste:** feste Spalten statt Fließtext, damit sich Räume vergleichen
  lassen.
- **Einstellungen:** in benannte Tafeln mit Unterabschnitten gegliedert.
- Zustände heißen auf Deutsch („Fenster offen“ statt „fenster“), Personen
  stehen als Kennzeichen statt in einer Tabelle, und das Ganze ist auf
  Handybreite brauchbar.

## 1.3.4

- Zuordnungsvorschläge sind kürzer gefasst und liegen ab dreien in einem
  zugeklappten Fach, damit sie die echten Hinweise nicht zudecken.

## 1.3.3

- Zuordnungsvorschläge lassen sich mit *Nicht nötig* dauerhaft abweisen. Ein
  Hinweisbalken, den man wegen Dauerrauschen überliest, ist schlechter als
  keiner.

## 1.3.2

- Nicht nur nachgerüstete Fensterkontakte, auch neue **Präsenz- und
  Bewegungsmelder** im Bereich eines Raumes werden zur Zuordnung angeboten.


## 1.3.1

- **Ein Präsenzmelder, der nichts meldet, gilt nicht als „niemand da“.** Bei
  einem ausgefallenen oder falsch eingetragenen Melder stünde ein Raum mit
  „nur der Präsenzmelder zählt“ sonst dauerhaft auf der Abwesenheitstemperatur,
  ohne dass es auffällt. Jetzt gilt er als belegt, und der Hinweisbalken meldet
  den stummen Melder.

## 1.3.0

- **Freigabe je Raum:** Ein Raum kann an einen Schalter in Home Assistant
  gehängt werden und bleibt kalt, solange der aus ist – für ein Gästezimmer,
  das nur bei Gästen geheizt werden soll. Fehlt der Schalter, wird der Raum
  normal geregelt und der Hinweisbalken meldet es.
- **Nur der Präsenzmelder zählt:** neue Raumoption für Räume wie ein Büro.
  Personen im Haus bleiben dann außer Betracht; auch das Vorheizen bei
  Heimkehr entfällt, sonst liefe die Heizung an, sobald jemand nach Hause
  fährt, ohne den Raum zu betreten.
- **Eigene Karenzzeit je Raum** – ein Bewegungsmelder, der nach zwei Minuten
  abfällt, braucht eine kürzere Nachlaufzeit als ein Wohnzimmer.

## 1.2.1

- Räume im Handbetrieb zeigen auf der Kachel den von Hand eingestellten Wert
  mit dem Zusatz „von Hand“. Meldet das Thermostat gar keinen Sollwert – die
  FRITZ-Geräte tun das in der Sommerpause nicht –, steht dort „Von Hand“ statt
  einer Zahl, die keine Zielvorgabe ist.

## 1.2.0

Neue Betriebsart je Raum: **von Hand, nur zu festen Zeiten absenken**.

- Der Raum wird von Hand gestellt; der Planer greift allein zu den Zeitpunkten
  des Plans ein und lässt ihn sonst unangetastet, auch wenn jemand hochdreht.
- Ein Absenkzeitpunkt überschreibt die Handeinstellung ausdrücklich – dafür
  ist er da. Ein verpasster Zeitpunkt wird nicht nachgeholt.
- Fenster, Urlaub und Sommerbetrieb greifen weiterhin; der vorgefundene
  Sollwert wird gemerkt und danach wiederhergestellt, damit der Raum nach
  einmal Lüften nicht auf Frostschutz stehen bleibt.

## 1.1.2

- Türkontakte werden nur noch über die Geräteklasse `door` erkannt, nicht mehr
  über das Wort „Tür“ im Namen. Sonst galten die Nebenmelder eines Thermostats,
  dessen Gerät „Heizung Eingangstür“ heißt (Sommermodus, Tastensperre), alle
  als Fensterkontakt.

## 1.1.1

- Die Erkennung von Fensterkontakten trennt jetzt zwei Fallgruben ab: Die
  Öffnungszeiten von Tankstellen kommen als `device_class: opening` und sind
  keine Kontakte; die Diagnosemelder eines Rolladens („Obstacle Detection“,
  „Blocking Detection“, „Sun Program Active“) führen das Fenster nur im Namen,
  an dem sie hängen.

## 1.1.0

Fensterkontakte lassen sich jetzt schrittweise nachrüsten.

- Die Auswahl der Fensterkontakte ist nach Bereich gruppiert und enthält nur
  noch, was nach Geräteklasse oder Namen ein Kontakt ist. Alles übrige Binäre
  steht getrennt unter „Sonstige Melder“.
- Ein neuer Kontakt im Bereich eines Raumes wird auf der Übersicht gemeldet,
  mit Knopf „Zuordnen“, der den Raum mit vorgewähltem Kontakt öffnet.
- **Ein Kontakt, der nichts meldet, gilt nicht mehr als „geschlossen“.** Bei
  leerer Batterie oder gestörtem Funk fällt der Raum auf die
  Temperatursturz-Erkennung zurück, statt blind zu werden; die Übersicht warnt.
- Sobald ein Raum verlässliche Kontakte hat, entscheiden allein sie. Die neue
  Raumoption „Zusätzlich auf Temperatursturz achten“ schaltet beides zu.
- Die Ersteinrichtung übernimmt Fensterkontakte und Präsenzmelder des Bereichs
  gleich mit.

## 1.0.5

- Räume mit geschlossenem Ventil zeigen „Aus · Ventil zu“ statt der
  Frostschutztemperatur als große Zahl – die Zahl las sich wie ein Heizziel.
- Deutsches Dezimalkomma in der ganzen Oberfläche.

## 1.0.4

- Knopf „Dämpfung neu anlaufen lassen“ in den Einstellungen: verwirft die
  geglättete Außentemperatur, die dann wieder aus der Historie ansetzt.
- Beim Wechsel der Außentemperatur-Quelle geschieht das von selbst – der
  geglättete Wert der alten Quelle würde sonst tagelang nachwirken.

## 1.0.3

- Die gedämpfte Außentemperatur wird beim ersten Lauf aus der Historie von
  Home Assistant angesetzt. Vorher begann sie beim aktuellen Messwert – an
  einem kühlen Sommertag hätte der Planer dadurch die Heizung angeworfen,
  obwohl die Woche davor mild war.
- Die Zeitkonstante der Dämpfung liegt jetzt bei 24 statt 6 Stunden, näher an
  der üblichen Heizgrenzenbetrachtung.

## 1.0.2

- Der Einrichtungsassistent schlägt für Schlafzimmer eigene Temperaturen vor
  (Komfort 20 °C statt 23 °C).


## 1.0.1

- Die Bereichszuordnung des Einrichtungsassistenten läuft jetzt über eine
  Template-Abfrage statt über die Websocket-API. Diese steht einem Add-on
  nicht offen, weshalb zuvor alle Thermostate in einem Sammelraum „Ohne
  Bereich“ landeten.
- Thermostate ohne Bereich werden als abgeschalteter Raum vorgeschlagen,
  statt stillschweigend zu verschwinden.
- In der Oberfläche bleiben eingestellte Entitäten in den Auswahllisten
  erhalten, auch wenn Home Assistant sie gerade nicht meldet. Vorher konnte
  ein Speichern die Zuordnung löschen.
- Die Heizkurve wirkt nur noch auf Komfort-, Eco- und Nachttemperatur, nicht
  mehr auf Abwesenheits- und Haltewerte.

## 1.0.0

Erste Fassung.

- Zeitplan je Raum mit Umschaltpunkten für Komfort, Eco, Nacht und Aus,
  getrennt nach Schultagen und schulfreien Tagen
- Heizkurve nach Außentemperatur, mit Sommerbetrieb und Hysterese auf einer
  geglätteten Außentemperatur
- Anwesenheitsabsenkung je Raum mit zuständigen Personen, Karenzzeit und
  Heimkehr-Erkennung über die Entfernung zur Heimzone
- Vorheizen mit außentemperaturabhängigem Vorlauf
- Fenstererkennung über Kontakte oder Temperatursturz
- Handeingriffe werden erkannt und bis zum nächsten Zeitplanwechsel geachtet
- Schreiben ausschließlich auf Flanke, jedes Thermostat einzeln
- Assistent zur Übernahme der Räume aus den Bereichen in Home Assistant
- Statusentitäten über MQTT, Protokoll der Schaltvorgänge
- Trockenlauf als Auslieferungszustand
