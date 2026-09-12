// Englisch. Eine Sprachdatei besteht aus drei Teilen und sonst nichts:
//
//   woerter   – feste Texte, Schlüssel ist der deutsche Originaltext
//   muster    – Texte mit Zahlen darin, als reguläre Ausdrücke
//   vorlagen  – die Namen der Zeitplan-Vorlagen, über ihren Wert angesprochen
//
// Wer eine Sprache ergänzen will, kopiert diese Datei nach `<code>.js`,
// übersetzt die rechte Seite und ist fertig – am Code ändert sich nichts.
// Ein fehlender Eintrag fällt nicht aus: Er bleibt deutsch stehen.

window.SPRACHEN = window.SPRACHEN || {};
window.SPRACHEN.en = {
  // Zahlen und Uhrzeiten: „21.5 °C“ und „14:00“ statt „21,5“ und „2:00 pm“.
  locale: 'en-GB',

  woerter: {
  // Kopf und Navigation
  "🔥 Heizungsplaner": "🔥 Heating Planner",
  "Heizungsplaner": "Heating Planner",
  "Übersicht": "Overview",
  "Räume": "Rooms",
  "Einstellungen": "Settings",
  "Protokoll": "Log",
  "🎉 Party": "🎉 Party",
  "Jetzt prüfen": "Check now",
  "Aktualisieren": "Refresh",
  "MQTT": "MQTT",
  "Liest die Zustände aus Home Assistant neu ein, entscheidet für jeden Raum und stellt die Thermostate. Von selbst geschieht das alle paar Minuten.":
    "Reads the states from Home Assistant again, decides for every room and sets the thermostats. This happens by itself every few minutes.",

  // Ersteinrichtung
  "Ersteinrichtung": "Initial setup",
  "Aus Home Assistant übernehmen": "Import from Home Assistant",
  "Vorschlag anzeigen": "Show proposal",
  "Ausgewählte Räume anlegen": "Create selected rooms",
  "Der Planer kann die Räume aus Home Assistant übernehmen: je Bereich ein Raum mit seinen Thermostaten, einem üblichen Zeitplan und – wo der Name es nahelegt – der zuständigen Person.":
    "The planner can import the rooms from Home Assistant: one room per area, with its thermostats, a typical schedule and – where the name suggests it – the person in charge.",

  // Raumliste und Dialog
  "Raum hinzufügen": "Add room",
  "Raum löschen": "Delete room",
  "Speichern": "Save",
  "Schließen": "Close",
  "Name": "Name",
  "Raum": "Room",
  "Raum aktiv – ausgeschaltet bleibt das Ventil zu":
    "Room active – switched off, the valve stays closed",
  "Betriebsart": "Operating mode",
  "Nach Zeitplan führen": "Follow the schedule",
  "Von Hand – nur zu festen Zeiten absenken":
    "By hand – set back at fixed times only",
  "Thermostate": "Thermostats",
  "Mehrfachauswahl mit ⌘ bzw. Strg. Gruppen-Helfer gehören nicht hierher – der Planer stellt jeden Heizkörper einzeln.":
    "Group helpers do not belong here – the planner sets every radiator individually.",
  "Grundlagen": "Basics",
  "Temperaturen": "Temperatures",
  "Zeitplan": "Schedule",
  "Belegung": "Occupancy",
  "Fühler und Melder": "Sensors",

  // Temperaturen
  "Sollwerte der Modi": "Setpoints per mode",
  "Komfort (": "Comfort (",
  "Eco (": "Eco (",
  "Nacht (": "Night (",
  "Abwesend (": "Away (",
  "Grenzen des Raumes": "Limits of this room",
  "Nie unter (": "Never below (",
  "Nie über (": "Never above (",
  "Die Grenzen deckeln auch die Heizkurve.":
    "The limits also cap the heating curve.",
  "Heizkurve auf diesen Raum anwenden": "Apply the heating curve to this room",
  "Komfort": "Comfort",
  "Eco": "Eco",
  "Nacht": "Night",
  "Aus": "Off",
  "Sollwert": "Setpoint",

  // Zeitplan
  "Punkt hinzufügen": "Add point",
  "Umschaltpunkt hinzufügen": "Add switching point",
  "Vorlage einsetzen …": "Insert template …",
  "Jeder Punkt gilt, bis der nächste kommt. Der letzte Punkt des Tages reicht über Mitternacht.":
    "Each point applies until the next one. The last point of the day reaches past midnight.",
  "immer": "always",
  "Schultag": "school day",
  "schulfrei": "day off",

  // Übersteuerung
  "Übersteuerung": "Override",
  "Regel hinzufügen": "Add rule",
  "Bedingung hinzufügen": "Add condition",
  "Bezeichnung, z. B. Homeoffice": "Name, e.g. working from home",
  "wenn": "if",
  "und": "and",
  "ist an / zu Hause": "is on / at home",
  "ist aus / fort": "is off / away",
  "greift gerade": "active now",
  "ruht": "idle",
  "Keine Regel – es gilt immer der Zeitplan.":
    "No rule – the schedule always applies.",
  "Treffen mehrere zu, gewinnt die oberste.":
    "If several apply, the topmost wins.",
  "Diese Regel entfernen": "Remove this rule",
  "Diese Bedingung entfernen": "Remove this condition",
  "ab wann die Regel greift – leer: rund um die Uhr":
    "when the rule starts – empty: around the clock",
  "bis wann die Regel greift": "when the rule ends",
  "Treffen alle Bedingungen einer Regel zu, gilt ihr Modus statt des Zeitplans. So entsteht eine Homeoffice-Regelung ohne Schalter:":
    "If all conditions of a rule apply, its mode replaces the schedule. That is how a working-from-home rule works without any switch:",
  "Werktag ist an": "workday is on",
  "Ferien sind aus": "holidays are off",
  "Isabel ist zu Hause": "someone is at home",
  "→ Komfort. Personen zählen als „an“, solange sie zu Hause sind. Das Zeitfenster grenzt ein, wann die Regel überhaupt greifen darf – ohne es liefe sie auch nachts um drei weiter. Leere Zeiten heißen: rund um die Uhr. Offene Fenster, Sommerbetrieb, Urlaub und die Anwesenheitsabsenkung bleiben stärker.":
    "→ comfort. People count as “on” while they are at home. The time window limits when the rule may apply at all – without it the rule would still be running at three in the morning. Empty times mean: around the clock. Open windows, summer mode, holiday and the presence setback remain stronger.",

  // Belegung
  "Freigabe": "Release switch",
  "Nur heizen, wenn dieser Schalter an ist": "Only heat while this switch is on",
  "immer freigegeben": "always released",
  "Für Räume, die nur zeitweise gebraucht werden – ein Gästezimmer etwa. Steht der Schalter auf aus, bleibt der Raum kalt.":
    "For rooms that are only used occasionally – a guest room, for instance. With the switch off, the room stays cold.",
  "Wer den Raum belegt": "Who uses this room",
  "Absenken, wenn niemand Zuständiges da ist":
    "Set back when nobody in charge is present",
  "Absenken, wenn niemand Zuständiges zu Hause ist":
    "Set back when nobody in charge is at home",
  "Bei der Partytaste mitmachen": "Take part in the party button",
  "Nur der Präsenzmelder zählt – Personen im Haus bleiben außer Betracht":
    "Only the presence sensor counts – people in the house are ignored",
  "Zuständige Personen": "People in charge",
  "Nichts ausgewählt = die ganze Familie zählt.":
    "Nothing selected = the whole family counts.",
  "Eigene Karenzzeit (Minuten)": "Own grace period (minutes)",
  "Leer lassen, dann gilt die Karenzzeit aus den Einstellungen.":
    "Leave empty to use the grace period from the settings.",
  "global": "global",

  // Fühler und Melder
  "Raumfühler": "Room sensor",
  "Mittelwert der Thermostate dieses Raumes":
    "Average of this room's thermostats",
  "Präsenz- und Bewegungsmelder": "Presence and motion sensors",
  "Fensterkontakte": "Window contacts",
  "Sonstige Melder": "Other binary sensors",
  "Sobald hier ein echter Kontakt steht, entscheidet er allein – die Temperatursturz-Erkennung tritt zurück. Meldet ein Kontakt nichts, springt sie wieder ein. Die":
    "As soon as a real contact is listed here, it decides alone – the temperature-drop detection steps back. If a contact reports nothing, the detection returns. The",
  "geräteeigene Erkennung": "device's own detection",
  "eines Thermostats löst zwar mit aus, verdrängt die Sturz-Erkennung aber nicht: Sie schweigt, sobald das Gerät abgeschaltet ist.":
    "of a thermostat does trigger as well, but does not replace the drop detection: it goes quiet as soon as the device is switched off.",
  "Zusätzlich auf Temperatursturz achten, auch wenn alle Kontakte geschlossen melden":
    "Watch the temperature drop as well, even when all contacts report closed",
  "filtern …": "filter …",
  "Nichts gefunden.": "Nothing found.",
  "Nichts zur Auswahl.": "Nothing to choose from.",

  // Einstellungen
  "Betrieb": "Operation",
  "Automatik – der Planer stellt die Thermostate":
    "Automatic – the planner sets the thermostats",
  "Trockenlauf – nur rechnen und protokollieren, nichts stellen":
    "Dry run – only calculate and log, set nothing",
  "Handeingriffe achten – ein von Hand gedrehtes Thermostat bleibt bis zum nächsten Zeitplanwechsel unangetastet":
    "Respect manual changes – a thermostat turned by hand stays untouched until the next scheduled change",
  "Takt (Sekunden)": "Cycle (seconds)",
  "Quellen aus Home Assistant": "Sources from Home Assistant",
  "Außentemperatur": "Outdoor temperature",
  "Wetterdienst oder Außenfühler. Ein Fühler in der Sonne taugt nicht – er meldet mittags zweistellig zu viel.":
    "Weather service or outdoor sensor. A sensor in the sun is useless – at noon it reads far too high.",
  "Schulfrei / Wochenende": "Day off / weekend",
  "Entscheidet, ob im Zeitplan die Schultag- oder die Schulfrei-Punkte gelten.":
    "Decides whether the school-day or the day-off points of the schedule apply.",
  "Urlaubsschalter": "Holiday switch",
  "Urlaubstemperatur (": "Holiday temperature (",
  "Frostschutz (": "Frost protection (",
  "Witterung": "Weather",
  "Heizkurve": "Heating curve",
  "Sollwert nach Außentemperatur nachführen":
    "Follow the outdoor temperature with the setpoint",
  "Basis-Außentemperatur (": "Base outdoor temperature (",
  "Steilheit (K je K)": "Slope (K per K)",
  "Höchstens (K)": "At most (K)",
  "Dämpfung (Stunden)": "Damping (hours)",
  "Die Dämpfung glättet die Außentemperatur, damit ein sonniger Nachmittag im Februar nicht die Heizung abstellt. Beim ersten Lauf holt sich der Planer den Anlauf aus der Historie.":
    "Damping smooths the outdoor temperature so that a sunny afternoon in February does not switch off the heating. On the first run the planner takes its starting value from the history.",
  "Dämpfung neu anlaufen lassen": "Restart the damping",
  "Sommerbetrieb": "Summer mode",
  "Bei milder Witterung nicht heizen": "Do not heat in mild weather",
  "Grenze (": "Threshold (", ", gedämpft)": ", damped)",
  "Hysterese (K)": "Hysteresis (K)",
  "Anwesenheit und Vorheizen": "Presence and preheating",
  "Absenkung bei Abwesenheit": "Setback when away",
  "Karenzzeit (Minuten)": "Grace period (minutes)",
  "So lange muss ein Raum leer sein, bevor abgesenkt wird. Je Raum überschreibbar.":
    "A room must be empty this long before it is set back. Can be overridden per room.",
  "Vorheizen": "Preheating",
  "Rechtzeitig vor dem Zeitplanwechsel anlaufen":
    "Start in time before the scheduled change",
  "Grundvorlauf (Min.)": "Base lead time (min.)",
  "Zuschlag je Grad Kälte": "Extra per degree of cold",
  "Höchstens (Min.)": "At most (min.)",
  "Heimkehr ab (km)": "Return from (km)",
  "Mindestannäherung (km)": "Minimum approach (km)",
  "Als heimkehrend gilt nur, wer näher als die Schwelle ist,":
    "Only someone closer than the threshold counts as returning,",
  "in keiner Zone steht": "is in no zone",
  "und dessen Entfernung in den letzten 15 Minuten um mindestens den genannten Wert abgenommen hat. Die Entfernung allein genügt nicht: Eine Schule in einem Kilometer Abstand hielte das Kinderzimmer sonst den ganzen Vormittag auf Komforttemperatur.":
    "and whose distance has decreased by at least the given value over the last 15 minutes. Distance alone is not enough: a school one kilometre away would otherwise keep the child's room at comfort temperature all morning.",
  "Fenstererkennung": "Window detection",
  "Bei offenem Fenster auf Frostschutz gehen":
    "Fall back to frost protection when a window is open",
  "Temperatursturz (K)": "Temperature drop (K)",
  "innerhalb von (Min.)": "within (min.)",
  "Sperre danach (Min.)": "Lock afterwards (min.)",
  "Der Temperatursturz greift nur in Räumen ohne Fensterkontakte. Kontakte trägt man je Raum ein.":
    "The temperature drop only applies in rooms without window contacts. Contacts are entered per room.",
  "Partytaste": "Party button",
  "Dauer (Stunden)": "Duration (hours)",
  "Diese Räume machen mit": "These rooms take part",
  "Ein Druck hebt die gewählten Räume für die eingestellte Dauer auf den Sollwert – danach führt wieder der Zeitplan. Ein offenes Fenster bleibt stärker; Urlaub und Sommerbetrieb treten zurück.":
    "One press lifts the selected rooms to the setpoint for the configured duration – afterwards the schedule takes over again. An open window stays stronger; holiday and summer mode step back.",
  "Überwachung": "Monitoring",
  "Melden, wenn ein Thermostat ausfällt": "Report when a thermostat fails",
  "Schweigefrist (Stunden)": "Silence period (hours)",
  "So lange darf ein Gerät nichts von sich hören lassen, bevor es als ausgefallen gilt.":
    "A device may stay silent this long before it counts as failed.",
  "Batteriewarnung ab (%)": "Battery warning below (%)",
  "Nur dort, wo es überhaupt eine Anzeige gibt.":
    "Only where there is a reading at all.",
  "Meldewege": "Notification targets",
  "Mehrfachauswahl mit ⌘ bzw. Strg. Gemeldet wird einmal beim Ausfall und einmal bei der Behebung – eine Warnung, die stündlich erneut kommt, wird bald weggewischt.":
    "Reported once on failure and once on recovery – a warning that returns every hour is soon swiped away.",
  "Probemeldung senden": "Send test notification",
  "Erst speichern, dann die Probe senden – geprüft werden die gespeicherten Meldewege.":
    "Save first, then send the test – the saved notification targets are what gets checked.",
  "Einstellungen speichern": "Save settings",

  // Raumliste
  "Bearbeiten": "Edit",
  "ganze Familie": "whole family",
  "Neuer Raum": "New room",

  // Zustände auf den Kacheln
  "Abwesend": "Away",
  "Heimkehr": "Coming home",
  "Urlaub": "Holiday",
  "Fenster offen": "Window open",
  "Sommer": "Summer",
  "Gesperrt": "Blocked",
  "Von Hand": "Manual",
  "Absenkung": "Setback",
  "Party": "Party",
  "Vorheizen": "Preheating",
  "· Ventil zu": "· valve closed",
  "Sommerbetrieb": "Summer mode",
  "Regelbetrieb": "Normal operation",
  "Trockenlauf": "Dry run",
  "Automatik aus": "Automatic off",
  "Schultag": "School day",
  "Schulfrei": "Day off",

  // Kopfzeile und Kacheln
  "Draußen": "Outside",
  "Nächster Wechsel": "Next change",
  "Letzter Durchlauf": "Last run",
  "Störungen": "Faults",
  "werden geregelt": "are being controlled",
  "Ventile geschlossen": "valves closed",
  "Ventil zu": "valve closed",
  "der erste Takt steht noch aus": "the first cycle is still pending",
  "Zurückgesetzt – noch kein Wert": "Reset – no value yet",
  "kein MQTT": "no MQTT",
  "prüft …": "checking …",
  "nicht erreichbar": "unavailable",
  "Konfiguration nicht lesbar": "Configuration cannot be read",
  "Noch keine Räume eingerichtet.": "No rooms set up yet.",
  "Kein Raum macht mit": "No room takes part",
  "Nichts ausgewählt": "Nothing selected",
  "Neuer Raum": "New room",
  "alle Räume abgesenkt": "all rooms set back",
  "der Planer greift nicht ein": "the planner does not intervene",
  "von Hand": "manual",
  "nur Präsenzmelder": "presence sensor only",
  "zu Hause": "at home",
  "ist zu Hause": "is at home",
  "läuft": "is on",
  "läuft nicht": "is not on",
  "gewählt": "selected",
  "dieser Raum": "this room",
  "· geräteeigene Erkennung": "· device's own detection",
  "· kommt näher": "· approaching",
  "(zurzeit nicht in Home Assistant)": "(currently not in Home Assistant)",
  "Diesen Vorschlag nicht mehr anzeigen": "Do not show this suggestion again",
  "Absenkpunkt hinzufügen": "Add setback point",
  "Aus – Ventil zu": "Off – valve closed",
  "Die gewählten Räume für die eingestellte Dauer auf Komfort":
    "Lifts the selected rooms to comfort for the configured duration",
  "Alle Bedingungen treffen zu und die Uhrzeit liegt im Fenster.":
    "All conditions apply and the time is within the window.",

  // Protokoll
  "Protokoll leeren": "Clear log",
  "Zeit": "Time",
  "Was": "What",
  "Warum": "Why",
  "Wer ist zu Hause": "Who is at home",

  // ── Tagesarten im Zeitplan
  "Schule": "School",
  "Arbeit": "Work",
  "Werktag": "Working day",
  "arbeitsfrei": "day off",
  "Arbeitstag": "Working day source",
  "suchen …": "search \u2026",
  "Für die Punkte „Werktag“ und „arbeitsfrei“ – gedacht für alle, die arbeiten statt zur Schule zu gehen. Gemeint ist ein Schalter, der an ist, wenn gearbeitet wird: Wochenende und Feiertage also aus. Genau das liefert die Workday-Integration von Home Assistant (binary_sensor.workday_sensor). Ohne Angabe bleiben die beiden Punktarten wirkungslos.":
    "For the \u201cWorking day\u201d and \u201cday off\u201d points \u2013 meant for anyone who works rather than goes to school. It wants a switch that is on when work happens: weekends and public holidays off. That is exactly what Home Assistant\u2019s built-in Workday integration provides (binary_sensor.workday_sensor). Without a source, both kinds of point stay inert.",

  // ── Haushalt
  "Wer zum Haushalt zählt": "Who counts as the household",
  "Nichts angehakt: alle Personen zählen. Das ist die Vorgabe und für die meisten richtig.":
    "Nothing ticked: everyone counts. That is the default and right for most people.",
  "Wichtig wird die Auswahl, wenn in Home Assistant mehr Personen stehen als im Haus wohnen – Gäste, alte Konten oder Personen ohne Gerätetracker. Letztere stehen dauerhaft auf „zu Hause“ und hielten damit jeden Raum für besetzt; die Absenkung bei Abwesenheit griffe dann nie mehr.":
    "The selection matters when Home Assistant holds more people than live in the house \u2013 guests, old accounts, or people without a device tracker. The latter stay \u201cat home\u201d permanently and would keep every room occupied, so the away setback would never take effect again.",
  "Je Raum lässt sich die Auswahl weiter einengen.":
    "The selection can be narrowed further per room.",

  // ── Öltank (optionaler Baustein)
  // Kesselregelung
  "Kesselregelung": "Boiler control",
  "Kessel": "Boiler",
  "Das Wochenprogramm der Heizungsregelung mitführen":
    "Also set the controller's weekly program",
  "Braucht das Add-on Heizungsanlagenmanager. Der Planer schreibt die Schaltzeiten, die die Regelung ohnehin fährt: die Vereinigung aller Komfortzeiten über alle Räume. Damit senkt die Anlage ab, wenn kein Raum mehr Wärme will, und steht bereit, wenn der erste Raum sie braucht – statt ihr eigenes Zeitprogramm gegen den Plan zu fahren.":
    "Requires the Heizungsanlagenmanager add-on. The planner writes the switching times the controller runs anyway: the union of all comfort periods across all rooms. The system then sets back once no room wants heat any more, and stands ready when the first room needs it – instead of running its own time program against the plan.",
  "Weil der Planer seinen Plan im Voraus kennt, entsteht dabei kein Versatz. Nur was kein Zeitplan vorhersieht – die Partytaste, eine greifende Übersteuerungsregel – wird nachgetragen, und das kann eine Taktlänge dauern.":
    "Because the planner knows its schedule in advance, there is no offset. Only what no schedule foresees – the party button, an override rule that takes effect – is added afterwards, and that can take one cycle.",
  "Solange die Übernahme steht, sind die Schaltzeiten im Anlagenmanager ausgeblendet. Der Knopf „Übernahme aufheben“ dort gibt sie jederzeit zurück – der Planer schreibt dann den vorgefundenen Wochenplan zurück, schaltet sich ab und meldet es im Protokoll.":
    "While the takeover is in place, the switching times are hidden in the system manager. The “Release takeover” button there hands them back at any time – the planner then writes back the weekly program it found, switches itself off and says so in the log.",
  "Adresse des Anlagenmanagers": "Address of the system manager",
  "Leer lassen: Der Planer findet das Add-on von selbst. Nur eintragen, wenn der Anlagenmanager woanders läuft.":
    "Leave empty: the planner finds the add-on by itself. Only fill this in if the system manager runs elsewhere.",
  "wird selbst gefunden": "found automatically",
  "Die Übernahme ist noch nicht angemeldet.": "The takeover is not registered yet.",
  "wartet": "waiting",
  "Anlagenmanager nicht erreichbar": "System manager not reachable",
  "Trockenlauf – nicht gestellt": "Dry run – not set",
  "heute verlängert": "extended today",
  "Öltank": "Oil tank",
  "Füllstand": "Tank level",
  "Wird geladen …": "Loading …",
  "Restmenge": "Remaining",
  "Für den Brenner erreichbar": "Reachable for the burner",
  "Der Tank wurde voll gefüllt": "The tank was filled completely",
  "Preis je Liter": "Price per litre",
  "oder Gesamtpreis": "or total price",
  "Beim Preis genügt eines von beiden – das andere rechnet sich aus der Menge. Der Verbrauch wird danach zum gleitenden Durchschnittspreis bewertet: Jede Lieferung mischt sich mit dem Restbestand, so wie das Öl im Tank auch.":
    "Either price will do \u2013 the other follows from the quantity. Consumption is then valued at a moving average price: every delivery mixes with what is left, just as the oil in the tank does.",
  "Kosten dieser Monat": "Cost this month",
  "Kosten Heizperiode": "Cost this season",
  "Mischpreis · Wert im Tank": "Average price \u00b7 value in tank",
  "noch kein Preis eingetragen": "no price recorded yet",
  "Dann ist der Inhalt danach bekannt – der Tankwagen füllt bis zur Abschaltung des Grenzwertgebers. Zusammen mit den beiden Höhen reicht das, um Anzeige bei vollem Tank und Nullpunkt auszurechnen: zwei Gleichungen für zwei Unbekannte. Das erspart den Gang mit dem Peilstab in den Dom.":
    "Then the content afterwards is known \u2013 the tanker fills until the overfill cut-off trips. Together with the two heights that is enough to work out the reading when full and the zero point: two equations for two unknowns. It saves the trip to the dome with a dipstick.",
  "Stand vorher (cm)": "Level before (cm)",
  "Stand nachher (cm)": "Level after (cm)",
  "Die beiden Höhen sind freiwillig – aber wenn du sie notierst, misst diese Lieferung den Tank gleich mit ein: Liter je Zentimeter ist die gelieferte Menge geteilt durch den Höhenunterschied. Genauer geht es nicht, und es ersetzt jede Schätzung aus dem Typenschild.":
    "Both heights are optional \u2013 but if you note them down, this delivery measures the tank at the same time: litres per centimetre is the delivered quantity divided by the difference in height. It does not get more accurate than that, and it replaces any estimate from the nameplate.",
  "Füllstand (cm)": "Level (cm)",
  "oder in Litern": "or in litres",
  "Peilstab": "Dipstick",
  "Freiwillig. Wer den Stand am Tank in Zentimetern abliest, bekommt damit die ehrliche Restmenge: Was unter dem Saugfuß steht, gehört dir, hilft dem Brenner aber nicht mehr.":
    "Optional. If you read the level off the tank in centimetres, this gives you the honest remaining quantity: whatever sits below the suction foot is yours, but no longer any help to the burner.",
  "Anzeige bei vollem Tank (cm)": "Reading when the tank is full (cm)",
  "Anzeige bei leerem Tank (cm)": "Reading when the tank is empty (cm)",
  "Meist 0 – aber ein nachgerüsteter Anzeiger hat oft eine Skala, die nicht zum Tank passt. Steht der Zeiger bei leerem Tank auf 8, gehört hier 8 hinein.":
    "Usually 0 \u2013 but a retrofitted gauge often has a scale that does not match the tank. If the needle sits at 8 on an empty tank, put 8 here.",
  "Untergrenze (cm)": "Lower limit (cm)",
  "Höhe des Saugfußes, auf derselben Skala abgelesen. Darunter zieht der Brenner Luft.":
    "Height of the suction foot, read off the same scale. Below that the burner draws air.",
  "Höhe des Saugfußes. Darunter zieht der Brenner Luft.":
    "Height of the suction foot. Below that the burner draws air.",
  "Liter je Zentimeter": "Litres per centimetre",
  "Trägt sich beim Einmessen selbst ein.": "Fills itself in when the tank is measured.",
  "⚠ Der Stand liegt unter dem Saugfuß – der Brenner kann Luft ziehen.":
    "\u26a0 The level is below the suction foot \u2013 the burner may draw air.",
  "Verbrauch heute": "Used today",
  "Reichweite": "Days left",
  "Lieferung eintragen": "Record a delivery",
  "Die Menge vom Lieferschein ist geeicht und damit genauer als jede Rechnung – sie zieht den Stand wieder gerade.":
    "The quantity on the delivery note is calibrated and therefore more accurate than any calculation – it puts the level straight again.",
  "Datum": "Date",
  "Menge (Liter)": "Quantity (litres)",
  "Verbuchen": "Record",
  "Stand von Hand setzen": "Set the level by hand",
  "Nach einem Blick auf den Zeiger am Tank.": "After a glance at the gauge on the tank.",
  "Füllstand (Liter)": "Level (litres)",
  "Übernehmen": "Apply",
  "Letzte Lieferungen": "Recent deliveries",
  "Verbrauch": "Consumption",
  "Dieser Monat": "This month",
  "Heizperiode": "Heating season",
  "Seit Beginn der Aufzeichnung": "Since records began",
  "Noch kein Monat erfasst": "No month recorded yet",
  "Die Monatssummen bleiben dauerhaft erhalten. In Home Assistant steht derselbe Verlauf zusätzlich als Sensor – dort führt die Langzeitstatistik ihn unabhängig von diesem Add-on weiter.":
    "Monthly totals are kept indefinitely. The same history is also available as a sensor in Home Assistant, where long-term statistics carry it on independently of this add-on.",
  "Noch keine Lieferung eingetragen": "No delivery recorded yet",
  "Alles unauffällig.": "Nothing unusual.",
  "⚠ Der Leckagemelder hat angesprochen.": "⚠ The leak detector has triggered.",
  "Der Vorrat wird knapp.": "The supply is running low.",
  "Noch kein Füllstand bekannt – trag eine Lieferung ein oder setz den Stand von Hand.":
    "No level known yet – record a delivery or set the level by hand.",
  "Kein Laufzeitzähler eingestellt – der Stand ändert sich nur durch Eingaben.":
    "No runtime counter configured – the level only changes when you enter something.",
  "Lieferung verbucht": "Delivery recorded",
  "Stand übernommen": "Level applied",
  "Bitte eine Menge angeben": "Please enter a quantity",
  "Bitte einen Füllstand angeben": "Please enter a level",
  "Tanküberwachung anzeigen – Restmenge, Verbrauch und Leckagewache":
    "Show tank monitoring – remaining oil, consumption and leak watch",
  "Nur für Anlagen mit Öltank. Ausgeschaltet erscheint der Reiter „Öltank“ gar nicht erst.":
    "Only for systems with an oil tank. When switched off, the \u201cOil tank\u201d tab does not appear at all.",
  "Tankinhalt (Liter)": "Tank capacity (litres)",
  "Füllgrenze (%)": "Fill limit (%)",
  "Steht auf dem Typenschild, meist 95.": "Stated on the nameplate, usually 95.",
  "Warnschwelle (Liter)": "Warning threshold (litres)",
  "Verbrauch aus der Brennerlaufzeit": "Consumption from burner runtime",
  "Optional. Ohne diese Quelle bleibt der Stand stehen, bis jemand eine Lieferung einträgt.":
    "Optional. Without this source the level stays put until someone records a delivery.",
  "Laufzeitzähler": "Runtime counter",
  "Düsendurchsatz (Liter/Stunde)": "Nozzle throughput (litres/hour)",
  "Aus der Düsengröße; wird mit jeder Lieferung genauer.":
    "From the nozzle size; gets more accurate with every delivery.",
  "Leckagewache": "Leak watch",
  "Melder im Auffangraum": "Detector in the bund",
  "Heizöl leitet keinen Strom – ein gewöhnlicher Wassermelder spricht darauf nicht an. Es braucht einen optischen Sensor oder einen Schwimmer.":
    "Heating oil does not conduct electricity – an ordinary water alarm will not respond to it. You need an optical sensor or a float.",
  "Leer: die Meldewege des Wachhunds.": "Empty: the watchdog\u2019s notification channels.",
  },

  muster: [
  [/^(\d+) von (\d+)$/, "$1 of $2"],
  [/^(\d+) von (\d+) · (\d+) gewählt$/, "$1 of $2 · $3 selected"],
  [/^(\d+) zur Auswahl$/, "$1 to choose from"],
  [/^(\d+) zur Auswahl · (\d+) gewählt$/, "$1 to choose from · $2 selected"],
  [/^(\d+) weitere – zum Suchen tippen$/, "$1 more – type to search"],
  [/^nur (.+)$/, "only $1"],
  [/^greift nicht: (.+)$/, "not active: $1"],
  [/^greift heute nicht – (.+)$/, "not active today – $1"],
  [/^greift gerade nicht – (.+)$/, "not active right now – $1"],
  [/^ist nicht zu Hause$/, "is not at home"],
  [/^(\d+) Thermostat\(e\)$/, "$1 thermostat(s)"],
  [/^(\d+) Absenkpunkt\(e\)$/, "$1 setback point(s)"],
  [/^seit (\d\d:\d\d)$/, "since $1"],
  [/^nächster Wechsel (\d\d:\d\d)$/, "next change $1"],
  [/^ist ([\d,.]+) °C$/, "is $1 °C"],
  // Der Hinweis beim Raumfühler wird aus Teilen gebaut – hier als Ganzes.
  [/^Ohne eigenen Fühler mittelt der Planer die Ist-Temperaturen der (\d+) Thermostate, die im Reiter Grundlagen angehakt sind\.$/,
   "Without its own sensor the planner averages the current temperatures of the $1 thermostats ticked under Basics."],
  [/^Ohne eigenen Fühler mittelt der Planer die Ist-Temperaturen des Thermostats, das im Reiter Grundlagen angehakt ist\.$/,
   "Without its own sensor the planner uses the current temperature of the thermostat ticked under Basics."],
  [/^Ohne eigenen Fühler mittelt der Planer die Ist-Temperaturen der Thermostate dieses Raumes – zurzeit ist im Reiter Grundlagen keines angehakt\.$/,
   "Without its own sensor the planner averages this room's thermostats – currently none is ticked under Basics."],
  [/^Der Planer führt den Sollwert durchgehend nach Zeitplan, Anwesenheit und Außentemperatur\.$/,
   "The planner controls the setpoint continuously by schedule, presence and outdoor temperature."],
  [/^Der Planer stellt den Raum nur zu den Zeitpunkten des Plans\. Dazwischen der Planer greift nicht ein.*$/,
   "The planner only sets this room at the points of the schedule. In between it does not intervene."],
  [/^Die Regel ist eingerichtet, aber diese Bedingung trifft nicht zu\. Sobald sie erfüllt ist, greift die Regel von selbst\.$/,
   "The rule is set up, but this condition does not apply. As soon as it does, the rule takes effect by itself."],
  [/^Alle Bedingungen treffen zu, aber die Uhrzeit liegt außerhalb des Zeitfensters\.$/,
   "All conditions apply, but the time is outside the window."],
  [/^greift nicht: (.+) meldet nichts$/, "not active: $1 reports nothing"],
  [/^(.+) ist gerade nicht „(an|aus)“\.$/, "$1 is currently not “$2”."],
  [/^(.+) meldet weder an noch aus\.$/, "$1 reports neither on nor off."],
  [/^(\d+) Thermostat$/, "$1 thermostat"],
  [/^(\d+) Thermostate$/, "$1 thermostats"],
  [/^(\d+) Absenkpunkt$/, "$1 setback point"],
  [/^(\d+) Absenkpunkte$/, "$1 setback points"],
  [/^nächster Wechsel (.+)$/, "next change $1"],
  // Die Einheit steht als Zeichen dahinter – °C oder °F, je nach Maßsystem.
  [/^gedämpft ([\d,.]+) (°[CF])$/, "damped $1 $2"],
  [/^außen ([\d,.]+) (°[CF])$/, "outside $1 $2"],
  [/^ist ([\d,.]+) (°[CF])$/, "is $1 $2"],
  [/^Komfort ([\d,.]+) \/ Eco ([\d,.]+) (°[CF])$/, "Comfort $1 / eco $2 $3"],
  [/^Komfort ([\d,.]+) \/ Eco ([\d,.]+) °C$/, "Comfort $1 / eco $2 °C"],
  [/^(\d+) Punkte$/, "$1 points"],
  [/^(\d+) Punkt$/, "$1 point"],
  [/^(\d+) Person\(en\)$/, "$1 person(s)"],
  [/^(\d+) Melder$/, "$1 sensors"],
  [/^(\d+) Kontakt(e)?$/, "$1 window contact$2"],
  [/^Von Hand · Planer wieder ab (\d\d:\d\d) Uhr · geplant ([\d,.]+) (°[CF])$/,
   "By hand · planner resumes at $1 · plan $2 $3"],
  [/^Parameter (\d+)$/, "Parameter $1"],
  [/^Übernommen: (.+), heute (.+)\.$/, "Taken over: $1, today $2."],
  [/^Komfort bis (\d\d:\d\d) Uhr$/, "comfort until $1"],
  [/^Reduziert bis (\d\d:\d\d) Uhr$/, "reduced until $1"],
  [/^Der Heizungsanlagenmanager antwortet gerade nicht: (.*)$/,
   "The heating system manager is not answering right now: $1"],
  ],

  vorlagen: {"wohnraum": "Living space", "kinderzimmer": "Child's room",
                     "schlafzimmer": "Bedroom", "nebenraum": "Secondary room"  },
};
