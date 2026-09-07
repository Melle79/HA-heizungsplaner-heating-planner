# Heating Planner · Heizungsplaner – Manual

This manual explains what the planner does and why. For installation the
[README](https://github.com/Melle79/HA-heizungsplaner-heating-planner) is enough.

🇩🇪 *Diese Anleitung gibt es auch auf Deutsch:*
[DOCS.de.md](https://github.com/Melle79/HA-heizungsplaner-heating-planner/blob/main/heizungsplaner/DOCS.de.md)

The interface follows the language of Home Assistant. German and English are
built in; anything other than German shows English. There is nothing to
configure – the planner reads the language from Home Assistant on every cycle.

## The interface

Four tabs: Overview, Rooms, Settings, Log.

### Overview

For each room the setpoint, the measured temperature and the reasoning in one
sentence. On top the outdoor temperature, the party button and the *Check now*
button; below them the notice bar whenever something needs attention.

![Overview with all rooms, setpoint and reasoning](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/en/uebersicht.png)

The state words on the tiles:

| Word | Meaning |
|---|---|
| Comfort / Eco / Night | the schedule is in charge |
| Preheating | the next change is being brought forward |
| Away | nobody responsible is in the house, the grace period has passed |
| Coming home | someone is approaching, the room warms up again |
| Window open | frost protection, then a lock period |
| Manual | somebody turned the thermostat, the planner stands back |
| Blocked | the release switch is off |
| Party | the party button is running |
| Summer / Holiday | valves closed, or the holiday temperature |

### Rooms

![Room list with operating mode and number of thermostats](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/en/raeume.png)

Every room opens in a dialogue with five tabs. **Basics** holds the name, the
operating mode and the thermostats of the room:

![Basics of a room: operating mode and assigned thermostats](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/en/raum-grundlagen.png)

The **schedule** consists of switching points (see below). *Insert template*
fills an empty plan with a typical day:

![Schedule with switching points for school days and days off](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/raum-zeitplan.png)

**Occupancy** says who uses the room – the people in charge, an own release
switch, an own grace period – and whether the room takes part in the party
button:

![Occupancy: release switch, people in charge, grace period](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/en/raum-belegung.png)

**Temperatures** holds the four setpoints and the hard limits of the room.
Under **Sensors** you find the temperature sensor, presence sensors and window
contacts:

![Sensors with a filter row above every list](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/en/raum-melder.png)

Devices are **ticked**; what is assigned can be seen at a glance. Above every
list sits a filter row – necessary because a household quickly has several
hundred binary sensors. Without it the letterbox contact would be on offer in
the living room:

* **Tick “only <room>”** – shows only what belongs to this room. That means
  the area in Home Assistant, but also the name: in this installation of all
  things the living-room window contact carries no area, and a pure area
  filter would hide it. The tick only appears when there is anything to find
  for that room at all.
* **Search field** – searches names and entity ids. As soon as something is
  typed, the *other binary sensors* are searched as well.
* Whatever is **ticked stays visible**, no matter how you filter. A hidden
  assignment would be lost on saving.
* On the right you see how many devices the list currently shows and how many
  of them are ticked.

The group **Other binary sensors** – everything binary that is not a contact –
stays collapsed at first and only appears when you search. The line on the
right says how many are waiting there.

### Settings

Everything that applies to the whole house: cycle, heating curve, summer mode,
preheating, presence, window detection, holiday, party button, monitoring and
notification targets. The example values below the heating curve are
recalculated while you change it.

![Settings with heating curve and summer mode](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/en/einstellungen.png)

### Log

Every change with its reason, the most recent first. Faults have a red
background, warnings a yellow one – so you can see at a glance whether
something has been left behind.

![Log of switching operations with reasons](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/en/protokoll.png)

## How the setpoint is decided

In every cycle (default: every five minutes) each room runs through the same
order of precedence. The first case that applies wins, the later ones are not
considered:

It applies to rooms in the *follow the schedule* mode; for *setback only* see
below.

| Rank | Case | Result |
|---|---|---|
| 1 | room switched off in the planner | valve closed |
| 2 | release switch off | valve closed |
| 3 | window open | frost protection, then a lock period |
| 4 | party button running | comfort, for the configured duration |
| 5 | holiday switch on | holiday temperature |
| 6 | summer mode | valve closed |
| 7 | schedule, possibly overridden | comfort / eco / night, possibly brought forward |
| 8 | nobody responsible present | away temperature |
| 9 | heating curve | surcharge based on the outdoor temperature |

The heating curve only applies to intended room temperatures (comfort, eco,
night). It is **not** applied to the away, holiday and frost-protection
temperatures: those are holding values, not a target climate.

Every decision carries its reasoning with it. It appears on the room tile and
in the log.

## The “Check now” button

By itself the planner calculates every few minutes (configurable under
*Cycle*) and also immediately whenever the configuration changes. The button
brings such a run forward: read the states from Home Assistant again, decide
for every room, and set the thermostats where needed. Afterwards it briefly
shows how many thermostats were set – or that there was nothing to do.

Useful after changing a setting, when you do not want to wait for the next
cycle.

## Operating modes per room

**Follow the schedule** (default) – the planner determines the setpoint
continuously, as described in the order of precedence above.

**By hand – set back at fixed times only** – the room is set by hand, at the
thermostat or in Home Assistant. The planner only intervenes at the points of
the schedule and otherwise leaves the room alone, even if somebody turns it
up. For rooms you warm up on demand and only want reliably turned down in the
evening – a guest toilet, for instance.

In this mode presence, preheating and the heating curve do not apply; they
presuppose a continuously controlled target. What still applies:

* A **setback point** sets the temperature of its mode once. In doing so it
  deliberately overwrites a manual setting – that is what it is there for.
  Afterwards the room belongs to the hand again.
* A **missed** point is not made up. If the add-on starts at 22:00, it does
  not apply the 21:00 setback afterwards and thus never overruns a manual
  setting. Within 30 minutes of the point it keeps trying – that bridges a
  cycle that failed to run.
* **Window, holiday and summer mode** still apply. The planner remembers the
  setpoint it found and **restores it** as soon as the special state is over.
  Without that the room would stay on frost protection forever after airing
  once.

## Schedule

### Day types

Every switching point applies to a day type. There are two pairs, because not
everyone in the house follows the same calendar:

| Point applies … | when |
|---|---|
| **always** | on the ticked weekdays, no further condition |
| **school day** | when the school-free switch is *off* |
| **school-free** | when it is *on* – holidays, public holidays, weekend |
| **working day** | when the working-day switch is *on* |
| **day off** | when it is *off* – weekends and public holidays |

Both pairs can be mixed in one schedule. Use school day / school-free for a
child's room, working day / day off for the room of someone in work.

The difference is not cosmetic: during the summer holidays *school-free* is on,
but anyone who works still gets up at six. That is why the two pairs hang on
**different sources** (*Settings → Sources from Home Assistant*).

Home Assistant's built-in **Workday integration** is the natural source:
`binary_sensor.workday_sensor` is on when work happens and already knows
weekends and public holidays. One pair of points then covers everything –
*working day* ticked Monday to Friday, *day off* ticked on all seven days. The
day-off point then applies on weekends **and** public holidays.

A pure public-holiday sensor would work too, but would leave the weekend
uncovered – you would need a third group of points for that.

Without a source, *working day* and *day off* stay inert and only the other
points apply.


A schedule consists of **switching points**, not of time ranges. Each point
says: from this time, on these weekdays, this mode applies – until the next
point comes. The last point of a day reaches past midnight into the next one.
That way no gap can occur in which no mode applies.

Each point applies either **always**, only on **school days** or only on
**days off**. Which case applies is decided by the entity configured in the
settings. If none is set, only the “always” points take effect.

Four temperatures per room:

* **Comfort** – when the room is in use
* **Eco** – during the day, when the room is merely kept available
* **Night** – night setback
* **Away** – when nobody responsible is in the house

Plus **never below** / **never above** as the hard limits of the room. They
also cap the heating curve.

### Recipe: a room that should only be protected from cooling out

For rooms in which you do not want to heat, but do not want to freeze either –
a bedroom, for instance:

* **a single switching point**, e.g. `00:00 → eco`,
* **eco** set to the desired lower limit, e.g. 18 °C,
* **heating curve off** – it would raise the setpoint in cold weather and thus
  do exactly what is not wanted here,
* **presence setback off** – the lower limit applies regardless of whether
  anybody is in the house.

The setpoint then stays at 18 °C around the clock. The thermostat regulates by
itself: it only heats when the room falls below, and never otherwise.

A manual setting remains possible and holds **until the next switching
point** – with a single point that means until midnight. Whoever turns it up
to 21 °C in the evening finds 18 °C again the next morning.

In summer mode this room is closed as well; the lower limit only applies again
once the damped outdoor temperature falls below the summer threshold.

## Override: a rule instead of the schedule

A room can be given rules that suspend the schedule. A rule consists of a mode
and any number of conditions; it applies while **all** conditions are met.

![Working-from-home rule in the schedule tab](https://raw.githubusercontent.com/Melle79/HA-heizungsplaner-heating-planner/main/heizungsplaner/doku/bilder/en/uebersteuerung.png)

The occasion is working from home. The living room follows a schedule that
sets it to eco in the morning, because usually nobody is there. If somebody
works at home, it should stay warm – without a switch, without rebuilding the
schedule:

| Condition | Entity | State |
|---|---|---|
| workday | `binary_sensor.workday_sensor` | is on |
| no holidays | `calendar.school_holidays` | is off |
| someone is at home | `person.…` | is on |

plus the time window **08:00–18:00**.

Result: **comfort** instead of eco. If one of the three does not apply, the
schedule takes over again.

Anything that can be on or off works as a condition: switches and helpers,
sensors, calendars (`on` while an event is running) and people. **A person
counts as “on” while they are at home** – whoever is in another zone, at the
office for instance, counts as away.

The **time window** limits when the rule may apply at all. Without it the
working-from-home rule would still be running at three in the morning –
workday, no holidays and somebody at home still apply – and the living room
would be at comfort instead of night. Empty times mean: around the clock. A
window may reach past midnight (22:00–06:00), just like a schedule point.

The **name** of the rule is free. It later appears in the reasoning and in the
log: “Working from home – comfort instead of schedule” reads better there than
a list of three entities. Without a name the conditions are listed.

**How to tell whether a rule is running:** the rule says so itself – and names
the reason. Below its header one of the following lines appears, and in front
of every condition a tick or a cross:

| Line | Meaning |
|---|---|
| *active now* | all conditions met, time within the window |
| *not active today – School holidays is on* | a condition that applies for the whole day: calendar, workday, holidays |
| *not active right now – … is not at home* | a condition that can change at any moment |
| *not active right now – outside 08:00–18:00* | everything fits except the time |
| *… reports nothing* | the entity delivers neither on nor off |

The distinction is not cosmetic: a holiday lasts until midnight, an absent
person can be back in five minutes. When a rule applies, its name also appears
in the reasoning on the room tile and in the log.

If several rules are configured, the topmost one wins. An entity that reports
nothing lets its condition fail (sign `?`) – then the schedule simply applies.

**What the override does not suspend:** an open window, summer mode, the
holiday switch and the presence setback. That is deliberate: a rule that gets
stuck will not heat an empty house.

The mode *off* closes the valve – for a rule that shuts a room down for a
while. For permanent blocking there is the
[release switch](#release-rooms-that-are-only-used-occasionally); it stands
high in the order of precedence and applies even against the party button.

## Heating curve

```
surcharge = slope × (base outdoor temperature − outdoor temperature)
```

capped at the configured maximum. With the defaults (base 15 °C, slope 0.06,
maximum 1.5 K) that means: +0.9 K at 0 °C outside, +1.5 K at −10 °C, −0.3 K at
20 °C. The interface recalculates the examples while you change the values.

The curve compensates for the fact that a radiator needs a higher flow
temperature in the cold to hold the same room temperature. It does not replace
flow-temperature control at the boiler.

## Summer mode

The outdoor temperature is smoothed exponentially (default: a 24-hour time
constant). On the first run the planner takes its starting value from the
history of Home Assistant, so that the smoothing does not begin at a momentary
reading. If the smoothed value rises above the threshold, the valves close; it
must fall below by the hysteresis before heating resumes. Without smoothing a
sunny February afternoon would switch off the heating.

Thermostats that support `off` are switched off – that saves battery and
closes the valve completely. All others get the frost-protection value.

**When a device cannot be switched off:** some Matter thermostats accept the
command and are back on `heat` a minute later. Without a countermeasure the
planner would send a new “off” in every cycle – a barrage that achieves
nothing except draining the battery. After two futile attempts it therefore
closes the valve permanently via the frost-protection value and notes this in
the log. If the device later does report itself as switched off, the normal
path applies again.

## Party button

One press, and the selected rooms go to comfort for the configured duration –
no matter what the schedule says. Afterwards the schedule takes over again;
nobody has to remember to reset the button.

It can be found in three places: as a button at the top of the interface (with
the remaining time), as `switch.heizungsplaner_party` in Home Assistant – and
thus on the dashboard, by voice or in automations – and via `POST /api/party`,
optionally with a different duration (`{"stunden": 5}`).

**Which rooms take part** is configured in the settings under *Party button*;
a bedroom is usually not wanted there. The same setting can be found in the
room itself under *Occupancy*.

In the order of precedence the party stands **before holiday and summer
mode**: whoever presses it is in the house and wants it warm, regardless of
what the calendar says. Only an **open window** stays stronger – heating
against it would be pointless. If summer mode is running, the reasoning says
that the system may not be heating at all.

## Release: rooms that are only used occasionally

A room can be tied to a switch in Home Assistant (*release switch*). While it
is off, the room stays cold – no matter what the schedule and presence say.
Intended for a guest room that should only be heated when guests are actually
there: switch on, and the stored schedule applies as in any other room.

If the switch is missing in Home Assistant or reports nothing, the room is
**controlled normally** and the notice bar reports it. Leaving a room cold
because of a broken switch would be the more unpleasant surprise.

## Presence

### Who counts as the household

*Settings → Presence* holds the list of people the planner considers at all.
**Nothing ticked means everyone** – that is the default and right for most
people.

The selection matters once Home Assistant holds more people than live in the
house. The dangerous case is a person **without a device tracker**: they stay
“at home” permanently and thereby keep every room occupied. The away setback
would never take effect again, and no error would point to it – the rooms
would simply stay warm.

The per-room selection (“Responsible people”) narrows things further within
the household.


Every room can have people assigned to it. Without an assignment the whole
family counts. In addition a presence or motion sensor can report the room as
occupied.

**Only the presence sensor counts** – for rooms you enter and leave again
instead of staying in: an office, a workshop. Then people are disregarded and
the sensor in the room decides alone. Without this setting a room without
people assigned would always be occupied as soon as anybody is in the house,
and the sensor would have no effect.

In this mode preheating on return is switched off as well: otherwise the
heating would start as soon as somebody drives home, even though nobody enters
the room.

**A sensor that reports nothing does not count as “nobody there”.** With a
failed or wrongly configured sensor the room would otherwise sit on the away
temperature permanently without anyone noticing. If not a single sensor of the
room answers, it counts as occupied and the notice bar reports it.

If nobody responsible is present, the planner waits for the **grace period**
(default: 45 minutes) before setting back. A short trip to the baker therefore
costs nothing. Every room can have its own grace period – an office whose
motion sensor drops out after two minutes needs a shorter one than a living
room.

The **return home** is anticipated. Three things must apply:

1. the person is closer to the home zone than the configured distance,
2. they are **in no zone** – whoever sits at school or at the office has
   arrived there, even if that is only one kilometre away,
3. their distance has decreased over the last 15 minutes by at least the
   configured **minimum approach**.

Distance alone is not enough. With a school one kilometre away the children
would be “close” all morning – their rooms would heat through and the presence
setback would come to nothing. The minimum approach also filters out GPS
noise: a value of 0.3 km does not react to the hundred metres by which a
resting position drifts.

Only `home` is checked. Trackers that report their own zones on the way
instead of `not_home` therefore work correctly.

## Preheating

```
lead time = base lead time + extra × (15 °C − outdoor temperature)
```

capped at the maximum. The planner looks ahead to when the schedule next asks
for something warmer and brings that change forward by the lead time.
Multi-step transitions (night → eco → comfort) are recognised as well.

## Window detection

Two ways, in this order:

**Window contacts.** What is configured in the room under *Window contacts*
decides. As soon as a room has at least one contact that reports something,
the temperature-drop detection steps back for that room – a real contact is
more accurate, and the drop occasionally triggers for no reason when a
starting radiator stirs the air at the thermostat's sensor. Whoever wants both
enables *Watch the temperature drop as well* in the room.

**The device's own detection is not a contact.** Some thermostats – the
FRITZ!Smart Thermo, for instance – detect an open window themselves via the
drop at their own sensor and report this as a separate entity. The planner
accepts such a report as a trigger, but lets the drop detection keep running
alongside. After all it does the same thing, only inside the device, and it
goes quiet as soon as the device is switched off or in its summer pause. A
room whose only entry is such a report would otherwise be left without window
detection. In the selection list they are marked as *device's own detection*.

**Temperature drop.** For rooms without contacts: if the room temperature
falls by more than the configured value within the time window, the window
counts as open. For this the planner keeps a temperature memory of one hour
per room. The room temperature is the configured sensor, otherwise the average
of the `current_temperature` of all thermostats in the room.

After either route the room stays on frost protection for the lock period, so
that brief airing is not immediately heated against.

### Retrofitting contacts

New contacts only need to be assigned in Home Assistant to an **area** that
corresponds to a room of the planner. A notice then appears on the overview
with an *Assign* button that opens the room with the contact preselected –
saving is enough. The same applies to new presence and motion sensors.

Whatever you do not want there disappears from the notices permanently via
*Not needed*.

In the selection list the contacts are grouped by area, the room's own area on
top. A contact is anything carrying the device class `window`, `door` or
`opening` **or** a matching word in its name – that is how the “open window
detected” reports of some thermostats are found, which come without a device
class. Everything else binary sits under *Other binary sensors* and only
appears once you type in the search field.

### When a contact fails

**A contact that reports nothing does not count as “closed”.** An empty
battery, an unplugged radio stick or a device not yet paired would otherwise
make the room blind without a word. If a configured contact reports neither
`on` nor `off`, the temperature-drop detection steps in again for that room,
the reasoning says so (“… report nothing – falling back to temperature drop”),
and a warning appears on the overview.

## While Home Assistant is starting

After a restart Home Assistant delivers its entities gradually. Whoever
calculates during that phase takes the devices not yet loaded for gone. The
planner therefore asks Home Assistant for its state before every cycle and
pauses while that is not `RUNNING` – no switching, no faults, no
notifications. During that time the interface shows a notice instead of a list
of defects.

## Monitoring: when a thermostat fails

The occasion was an incident: during a holiday four thermostats failed because
of empty batteries, and nobody noticed.

A battery warning alone does not help here. The SwitchBot thermostats report
**no charge level at all** over Matter – there is nothing to monitor. What they
report is their state, and they do so regularly. If that stops, the device is
dead, whatever the reason. The planner therefore watches for **signs of
life**:

| Case | When |
|---|---|
| no longer exists | the entity has disappeared from Home Assistant |
| unavailable | state `unavailable` or `unknown` |
| has stopped reporting | no sign of life since the silence period, and the wake-up call went unanswered (default 24 hours, doubled in summer mode) |
| low battery | where there is a reading, below the threshold (default 20 %) and **not older than twelve hours** |
| refuses setpoints | three write operations rejected in a row |
| in summer pause | the device reports `summer` although heating is due |

For the battery level its age counts as well. Some devices only report it on
change – after a battery swap the old value may sit there for days. Warning
about that would be wrong, so a reading older than twelve hours is
disregarded. Conversely the message names the time of the measurement, so that
you can judge it.

**The summer pause is reported by the planner on its own**, as soon as summer
mode ends and a device is still on `summer`. That is the moment when the hint
is useful: before it, it would be news about the summer; after it, the room
would stay cold. It can only be ended in the FRITZ!Box – under *Smart Home →
edit device → schedule → summer time*. Home Assistant cannot do it: the
integration shows the mode, and the list of presets then contains nothing but
`summer`.

Until then the case above applies as well: a device in summer pause rejects
every setpoint. The message says so explicitly, so that nobody goes looking
for batteries where none are missing.

After three failures the planner only tries every 30 minutes. Otherwise such a
device would fill the log in every cycle without anything changing.

**How long may a device stay silent?** Longer than one would think – and the
period alone is not enough. In summer mode the planner stops writing, so the
device has nothing to report either: the office, the hobby room and the guest
room stayed silent for more than a day with nothing wrong with them.

That is why the planner **knocks first**. It asks Home Assistant to refresh
that entity – a wake-up call without any radio command to the device – waits
twelve minutes, and only reports if nothing comes back. If the device answers,
it was merely quiet. This is exactly what a person does who briefly changes
the setpoint to see whether the thermostat is still alive.

The period itself is 24 hours, doubled in summer mode. In heating mode a
device reports on every setpoint change, so it is considerably stricter than
it sounds.

Reporting happens **on edges**: once when it occurs, once when it is resolved.
A warning that arrives on the phone again every hour is swiped away after the
third time and overlooked on the fourth. If a low battery turns into a
failure, that counts as a new message.

The notification targets are chosen in the settings from the `notify` services
of Home Assistant – the companion app works well when away from home, the
persistent notification in the interface additionally at home. Every fault
also appears in the log and in the notice bar.

For your own automations there is `binary_sensor.heizungsplaner_stoerung`
(device class `problem`) with the messages as an attribute, as well as
`sensor.heizungsplaner_stoerungen` with the number of failed devices.

## Oil tank (optional)

This part is **off by default**. It only appears once you switch it on under
*Settings → Oil tank* – before that there is no “Oil tank” tab and nothing is
calculated. Anyone heating with gas, district heating or a heat pump will never
notice this chapter.

### Where the level comes from

Without a sensor in the tank, from two figures that correct each other:

* The **delivered quantity** on the delivery note is calibrated and therefore
  more accurate than any measurement – but it only arrives once or twice a year.
* The **burner runtime** times the nozzle throughput provides the resolution in
  between. As the throughput is only an estimate from the nozzle size, it
  drifts – until the next delivery puts it straight again.

The runtime counter is optional. If you do not configure one, the level simply
stays put until you record a delivery or set it by hand.

### The dipstick: measure instead of estimate

If you read the level off the tank in centimetres, three extra fields become
useful – *reading when full*, *lower limit* and *litres per centimetre*.

**The delivery does the measuring.** Note the level before and after filling
and enter both together with the delivered quantity. The planner works out:

```
litres per centimetre = delivered quantity ÷ (cm after − cm before)
```

That is the most accurate figure this vessel will ever produce – it comes from
a calibrated quantity and the tank itself, not from a nameplate. The value is
written into the settings, and from then on the planner converts between
centimetres and litres: the level can be set in centimetres, and the display
shows both.

**Filled up completely? Then the geometry works itself out.** Tick *The
tank was filled completely* when recording the delivery. The tanker fills until
the overfill cut-off trips, so the content afterwards is known – the fill
limit. Together with the two readings that gives two equations for two
unknowns, and the planner learns in one go:

* **litres per centimetre** from the difference in height,
* the **reading when full** – which is exactly the reading at hand, so measured
  rather than estimated,
* the **zero point**, from `cm after − known content ÷ litres per centimetre`.

After that the dipstick is redundant. One caveat: the calculation rests on the
nominal capacity from the nameplate. If it produces a **negative** zero point,
the planner says so explicitly – the capacity entered does not fit this scale,
and both deserve a check.

**What is stored is the reading, not the litre figure.** Enter the level in
centimetres and the planner remembers exactly that – working out the litres
afresh each time, minus whatever has been burned since.

That sounds like a detail but is the difference between right and wrong: correct
the zero point later, or measure the tank anew, and the litre figure follows.
Were the truth held in litres, the planner would claim a needle position that
the tank does not show.

Enter the level in litres and you still get litres. A delivery also resets the
basis.

**The zero point, if the gauge was retrofitted.** The planner works out
litres from the height *above the zero point* – that is, above whatever the
gauge shows on an empty tank. On a factory-matched device that is zero. On a
gauge screwed on later, rarely: a 150 cm scale on a 130 cm tank, a cord cut
too long, and the whole scale sits shifted.

Two notes:

* **Calibration through a delivery is unaffected.** It works on the
  *difference* between two readings, and an offset cancels out. The slope is
  right even when the scale is not.
* **The zero point itself has to be established once.** Easiest shortly before
  a delivery, when the tank is nearly empty: dip a stick through the dome,
  measure the true oil height and compare it with the gauge – the difference is
  the offset.

**The lower limit is the honest figure.** The suction foot sits a few
centimetres above the bottom. Whatever is below it is yours, but no longer any
help to the burner, which starts drawing air and faults out. With a lower limit
entered, the planner distinguishes:

| | |
|---|---|
| **in the tank** | everything that is in there |
| **reachable for the burner** | everything above the suction foot |

Warning threshold and days left then use the reachable quantity. A tank with
250 litres “in it” can be empty as far as the burner is concerned.

### Consumption and history

The tab shows three spans: this month, the current heating season and
everything since records began. The **heating season starts in July** – a
calendar year would cut the winter in half and make every comparison
worthless.

Two things are kept: **daily values for 60 days** (that is all the days-left
figure needs) and **monthly totals forever**. Twelve numbers a year cost
nothing, and only they allow one season to be compared with the last.

On top of that come the **MQTT entities**, as soon as the tank part is switched
on:

| Entity | |
|---|---|
| Heating oil reachable | above the suction foot |
| Heating oil in tank | everything in there |
| **Heating oil used** | a counter that only grows |
| Heating oil days left | days |
| Oil tank leak | the detector in the bund |

“Heating oil used” carries `state_class: total_increasing`. Home Assistant
turns that into **long-term statistics** with daily, monthly and yearly figures
on its own – which survive the loss of the add-on's data. If you feed InfluxDB
or another database from Home Assistant, the history lands there with no
further effort.

A tank with no known level reports `unknown`, not zero. An invented zero would
otherwise end up in the statistics as a real measurement.

### What the oil costs

Every delivery can carry a **price per litre** or a **total price** – either
will do, the other follows from the quantity.

Consumption is then valued at a **moving average price**: every delivery mixes
with what is left, just as the oil in the tank does. With 2000 litres at 1.10
in the tank and 2000 litres at 0.90 added, consumption from then on is valued
at 1.00. That is standard inventory valuation and the only calculation that
needs no invention – the tank does not keep the 2019 oil neatly beside the 2026
oil.

Out of it come: cost per month and per heating season, the value of what is
currently in the tank, and a cost counter in Home Assistant. It carries
`device_class: monetary`, so it sits in the same statistics as electricity and
gas.

Without a price, everything stays in litres – no invented figures.

### Settings

| Field | Meaning |
|---|---|
| Tank capacity | Nominal capacity from the nameplate |
| Fill limit | How much may go in, usually 95 % |
| Warning threshold | Below this you get a warning, based on the reachable quantity |
| Reading when full | What the dipstick shows on a full tank |
| Lower limit | Height of the suction foot |
| Litres per centimetre | Fills itself in when the tank is measured |
| Runtime counter | Sensor holding the burner hours |
| Nozzle throughput | Litres per operating hour |
| Detector in the bund | For the leak watch |
| Notify | Empty: the watchdog’s channels |

### Guarding against wrong figures

A calculated tank is only as good as its counter, and counters jump. Three
cases are handled: the **first** counter value seen is never treated as
consumption – otherwise the tank would be empty after the first cycle. A
**backward jump** (new boiler, reset counter) is adopted as a new baseline
rather than booked. And a **jump** of more than 24 hours between two cycles is
treated as a counter fault and goes to the log, not into the calculation.

### Leak watch

A detector in the bund, given as any entity that knows “on” and “off”. If it
triggers there is **one** notification, not the same one every five minutes.

One hint that saves money: **heating oil does not conduct electricity.** The
usual water alarms measure the resistance between two contacts and stay silent
in a pool of oil. You need an optical sensor or a float.

### Days left

The average of the last fourteen days, projected onto the remaining quantity.
With fewer than three days of consumption there is no figure, and in summer –
when nothing is used – you get a dash instead of an infinity.

## Manual changes

If a thermostat is adjusted by hand – at the device, in Home Assistant or by
an automation – the planner recognises the deviation from its last written
value and stands back **until the next scheduled change**. Afterwards the
schedule takes over again. This can be switched off under *Settings →
Operation*.

Radio thermostats report with a delay. The planner therefore only treats a
deviation as a manual change 15 minutes after its own write operation.

**Not every deviation is a hand.** Some devices acknowledge a setpoint and
still do not apply it – they stand unchanged afterwards. The planner therefore
remembers which value was on the device *before* its command: if it is still
exactly that one, nobody turned anything, the device swallowed the command
instead. It then tries again and reports it as a fault after three failures.
This distinction matters – read as a manual change, the planner would stand
back and the room would stay at a value nobody wanted.

## How writing works

A setpoint only goes to a thermostat when something different is actually set
there – **on edges, not on levels**. An add-on that stubbornly writes the same
value in every cycle becomes the owner of the entity and overruns every other
form of operation.

Every thermostat is addressed **individually**. A bulk call would fail on a
single switched-off device and drag all the others down with it. If a
thermostat does not accept the setpoint, the planner switches it to `heat`
once and tries again.

The last written value lives in `/data/zustand.json` and survives a restart.
Without that memory every start of the add-on would write into every
thermostat.

## Dry run and automatic off

**Dry run** – the planner calculates, logs and reports over MQTT, but sets no
thermostat. The right state for the first few days.

**Automatic off** – the planner no longer writes into the thermostats and
leaves them as they are.

### Back to the previous control

1. Switch on the dry run (or automatic off).
2. Re-enable the schedules and automations you switched off before.

In both cases the thermostats keep the last value set – the planner does not
tidy up when switched off, so that an accidental switch does not leave a cold
house behind.

## Initial setup

The assistant reads the areas from Home Assistant and creates one room per
area that has a thermostat: with the thermostats of that area, a typical
schedule and – where the area name contains a first name – the person in
charge. Group helpers are left out; the planner sets every radiator
individually. Devices registered twice under the same display name are
imported only once.

The proposal is shown before it is saved. Afterwards schedules, temperatures
and the assignment of people want checking – guessed is not decided.

## Migrating from the Scheduler integration

While both are running, two systems write to the same setpoints and overrule
each other. Therefore:

1. Set up the rooms in the planner and watch them for a few days in dry run.
2. Hold the log against the actual times.
3. **Switch off** the scheduler entries for the heating.
4. Only then switch off the dry run.

The notice bar of the interface warns when a thermostat is listed in two rooms
– the two rooms would then set it against each other.

## Cards for the dashboard

`heizungsplaner/dashboard/` in the repository holds a ready-made overview: the
party button with its remaining time, a fault display that only appears when
there is something to report, and a table of all rooms with setpoint, measured
temperature, state and the next switching point. The cards read the MQTT
entities only and therefore work from outside the house as well.

In addition there is `regelkarte(sensor)`: a tile that only appears while an
override rule is active, showing until when (“until 14:00”). It belongs in the
section where you look at the room anyway. It builds on the attributes
`uebersteuerung`, `uebersteuerung_greift`, `uebersteuerung_lage` and
`uebersteuerung_bis` of the room sensor – a card that searches the reasoning
for keywords instead breaks with the first renamed room.

**Do not use a `conditional` card:** in a sections view Home Assistant 2026.8
reports a “configuration error” for it. There `visibility` belongs on the card
itself. And if the attribute named under `state_content` is empty, a tile card
shows the state of the sensor instead – which is why `uebersteuerung_bis` is
never empty but carries “idle” when nothing is running.

## Files

| File under `/data` | Content |
|---|---|
| `config.json` | rooms, schedules, settings |
| `zustand.json` | last written setpoints, runtime state per room |
| `logbuch.json` | log of the last 500 switching operations |

## Units: Celsius or Fahrenheit

The planner takes the unit from the measurement system of Home Assistant
(`/config` → `unit_system.temperature`) – the same answer that carries the
language. Home Assistant already converts climate entities into that unit, so
the numbers arrive correct; what matters is that everything **fixed** follows
along:

* the **defaults** – comfort 21 °C becomes 70 °F, frost protection 8 °C
  becomes 46 °F, rounded to whole degrees because that is how a default should
  read;
* the **limits** of the input checks – 70 °F would fall outside a range meant
  for Celsius;
* **spans** as opposed to temperatures: a hysteresis of 1.5 K becomes 2.7 °F,
  not 34.7. Adding 32 to a distance is the classic mistake here;
* the **step size**: half a degree in Celsius, a whole one in Fahrenheit,
  because the devices do not resolve finer there and every write costs
  battery;
* the **slope** of the heating curve stays as it is – kelvin per kelvin is the
  same ratio as degrees Fahrenheit per degree Fahrenheit.

**When the measurement system changes**, the stored values are converted once
and the new unit is noted in `config.json`. Without that a comfort value of 21
would remain the number 21 – and the planner would cool the house down to
21 °F. The conversion is logged.

## Language

The planner speaks German and English. It takes the language from Home
Assistant (`/config` → `language`) and follows a change there from the next
cycle onwards; anything other than German shows English.

Three things deliberately stay German, because they are data rather than
interface:

* the **entity ids** (`sensor.heizungsplaner_raum_wohnzimmer`) – they are part
  of every existing installation, and renaming them would break dashboards and
  automations;
* the **keys** of modes and states (`komfort`, `sommer`, `fenster`) as they
  appear in the stored configuration and in MQTT attributes;
* the **names** you gave to rooms, rules and devices.


## Adding a language

The planner speaks German and English. A third language is two files and no
code change:

**1. The backend** – `backend/texte.py` holds every sentence the planner
writes. Each entry is a small table; add a column:

```python
"zeitplan": {
    "de": "Zeitplan: {modus} ab {uhrzeit} Uhr",
    "en": "Schedule: {modus} from {uhrzeit}",
    "fr": "Programme : {modus} à partir de {uhrzeit}",
},
```

The placeholders must be the same in every language – the test run checks
exactly that, along with the tables `MODUS` and `ZUSTAND`. Which languages
exist is derived from these entries; nothing is registered anywhere.

**2. The interface** – copy `frontend/sprachen/en.js` to `<code>.js`, change
the first line to `window.SPRACHEN.fr = {`, set `locale` (it decides decimal
separator and clock format) and translate the right-hand side. The file has
three parts: `woerter` for fixed texts, `muster` for texts containing numbers,
`vorlagen` for the schedule templates.

The key is always the **German original text** – that way a forgotten entry
does not break anything, it simply stays German.

**What is not covered:** the patterns under `muster` are regular expressions
and assume that singular and plural differ the way they do in German and
English. Languages with more plural forms – Polish or Russian, for instance –
need one pattern per form, or a rebuild towards real keys.

If a language is missing at runtime, English is used; if that is missing too,
German remains. A half-finished translation therefore never empties the
interface.
