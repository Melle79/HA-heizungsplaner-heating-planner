# Heating Planner · Heizungsplaner

A Home Assistant add-on that sets radiator thermostats ahead of time – by
schedule, outdoor temperature and presence.

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FMelle79%2FHA-heizungsplaner-heating-planner)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-melle79-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/melle79)

> 📖 Full manual: **[DOCS.md](heizungsplaner/DOCS.md)** · 🇩🇪 Auf Deutsch:
> **[README.de.md](README.de.md)**

Instead of fixed times per thermostat, the planner calculates a setpoint for
every room in every cycle – and explains it. The interface does not only say
that the living room gets 21.5 °C, but why: “Preheating for comfort at 12:30
(50 minutes lead time) · heating curve +0.6 K”.

**The planner follows Home Assistant.** Language – German and English are
built in, anything else shows English – and the temperature unit: Celsius or
Fahrenheit, with defaults, limits and step size following along. There is
nothing to configure; both come from `/config` and are read on every cycle.

![Overview with all rooms, setpoint and reasoning](heizungsplaner/doku/bilder/en/uebersicht.png)

## What the planner takes into account

* **A schedule per room** – switching points for comfort, eco, night and off.
  A point can apply to a day type, and there are two pairs: *school day /
  school-free* for anyone at school, and *working day / day off* for anyone in
  work. During the summer holidays it is school-free – but whoever works still
  gets up at six.
* **Outdoor temperature** – a heating curve follows it: the colder it is
  outside, the higher the setpoint. In mild weather the system enters summer
  mode and closes the valves.
* **Presence per room** – every room can have the people responsible for it
  assigned. If none of them is at home, the planner sets back after a grace
  period; if someone approaches the house, it preheats again. A global list
  defines who counts as the household at all – which matters once Home
  Assistant holds more people than live in the house.
* **Preheating** – the lead time depends on the outdoor temperature. At 12 °C
  thirty minutes are enough, at −10 °C it takes two hours.
* **Windows** – via contacts or, where there are none, via the temperature
  drop in the room. Retrofitted contacts are offered for assignment by the
  planner itself; a contact that fails does not count as “closed”.
* **Holiday** – a switch in Home Assistant puts the whole house on the holiday
  temperature.
* **Monitoring** – if a thermostat stops reporting, a notification goes out.
  Because these devices report no battery level at all, the planner watches
  for signs of life instead of the battery.
* **Manual mode per room** – whoever wants to set a room by hand lets the
  planner set back at fixed times only. In between it does not touch the room.
* **Release per room** – a guest room is only heated while a switch in Home
  Assistant allows it.
* **Override rules** – rules made of conditions replace the schedule: “workday,
  no holidays, someone is at home” keeps the living room at comfort instead of
  setting it back in the morning. Anything that can be on or off works as a
  condition – switches, sensors, calendars and people.
* **Party button** – lifts the selected rooms to comfort for a few hours and
  resets itself afterwards.
* **Units** – Celsius or Fahrenheit, taken from the measurement system. Spans
  are converted as spans: a hysteresis of 1.5 K becomes 2.7 °F, not 34.7. If
  the measurement system changes, the stored values are converted once.

* **Boiler control** *(optional, off by default)* – the planner can also set
  the controller's program selection, so the heating system stops running its
  own time program against the plan: nominal as soon as a room wants comfort,
  reduced when all are set back, summer in summer mode. Requires the
  *Heizungsanlagenmanager* add-on. Whoever releases the takeover there keeps
  it released – the planner does not register again on its own.

* **Oil tank** *(optional, off by default)* – remaining oil, daily
  consumption, days left and a leak watch. The level works without a sensor in
  the tank: the calibrated delivery note as the anchor, burner runtime times
  nozzle throughput as the resolution in between.

## The interface

Four tabs: **Overview**, **Rooms**, **Settings**, **Log** – plus **Oil tank**
once it is switched on.

The **overview** (image above) shows each room's setpoint, the measured
temperature and, in one sentence, why this value applies. On top you find the
outdoor temperature, the party button and the *Check now* button.

Rooms are set up under **Rooms**:

![Room list with operating mode and number of thermostats](heizungsplaner/doku/bilder/en/raeume.png)

Every room opens in a dialogue with five tabs – basics, temperatures,
schedule, occupancy, sensors:

![Basics of a room: operating mode and assigned thermostats](heizungsplaner/doku/bilder/en/raum-grundlagen.png)

The **schedule** consists of switching points, not of time ranges: each point
applies until the next one comes – always, on school days only or on days off
only:

![Schedule with switching points for school days and days off](heizungsplaner/doku/bilder/raum-zeitplan.png)

Below it are the **override rules**: while all conditions of a rule apply and
the time is within its window, its mode replaces the schedule. That is how a
working-from-home rule works without any switch. Each rule says whether it is
active and, if not, what is missing:

![Override rule with conditions and time window](heizungsplaner/doku/bilder/en/uebersteuerung.png)

**Occupancy** holds who uses the room – the people responsible, a presence
sensor, an own grace period – and whether the room takes part in the party
button:

![Occupancy: release switch, people in charge, grace period](heizungsplaner/doku/bilder/en/raum-belegung.png)

Under **Sensors** the temperature sensor, presence sensors and window contacts
are attached to the room. Devices are ticked, and a filter row above each list
shows only what belongs to this room – otherwise the letterbox contact would
be on offer in the living room:

![Sensors with a filter row above each list](heizungsplaner/doku/bilder/en/raum-melder.png)

The **settings** apply to the whole house: heating curve, summer mode,
preheating, presence, window detection, monitoring and notification targets:

![Settings with heating curve and summer mode](heizungsplaner/doku/bilder/en/einstellungen.png)

The **log** records every change with its reason – faults in red, warnings in
yellow:

![Log of switching operations with reasons](heizungsplaner/doku/bilder/en/protokoll.png)

## Installation

1. In Home Assistant open **Settings → Add-ons → Add-on Store**, then
   **Repositories** from the three-dot menu, and add this address:

   ```
   https://github.com/Melle79/HA-heizungsplaner-heating-planner
   ```

   Or use the button at the top of this document.

2. Install and start the **Heizungsplaner** add-on.
3. Open the interface. It starts in **dry run**: the planner calculates and
   logs, but does not set any thermostat yet.
4. Use **Import from Home Assistant** to create the rooms, then check
   schedules and temperatures.
5. Once the result looks right, switch off the dry run in the settings.

The full manual is in [DOCS.md](heizungsplaner/DOCS.md).

## Entities in Home Assistant

Over MQTT the add-on creates a device called “Heizungsplaner”:

| Entity | Meaning |
|---|---|
| `sensor.heizungsplaner_status` | short form of the operating state |
| `sensor.heizungsplaner_aussentemperatur_gedaempft` | damped outdoor temperature |
| `binary_sensor.heizungsplaner_sommerbetrieb` | summer mode active |
| `binary_sensor.heizungsplaner_trockenlauf` | dry run active |
| `sensor.heizungsplaner_raum_<name>` | setpoint per room; attributes: `zustand`, `begruendung`, `ist_temperatur`, `naechster_wechsel` as well as `uebersteuerung`, `uebersteuerung_greift`, `uebersteuerung_lage` and `uebersteuerung_bis` |
| `switch.heizungsplaner_party` | party button, with the remaining time as an attribute |
| `binary_sensor.heizungsplaner_stoerung` | a thermostat has stopped reporting; messages separated by severity as attributes |
| `sensor.heizungsplaner_stoerungen` | number of failed thermostats |
| `sensor.heizungsplaner_kessel` | the controller's operating mode, while the boiler control is switched on |

The entity ids stay German – they are part of every existing installation, and
renaming them would break dashboards and automations.

## Cards for the dashboard

[`heizungsplaner/dashboard/`](heizungsplaner/dashboard/) holds a ready-made
overview: party button, fault display and a table of all rooms with setpoint,
measured temperature and the next switching point. It relies on the MQTT
entities only and therefore works from outside the house as well.

There is also `regelkarte(sensor)` – a tile that **only appears while an
override rule is active**, showing until when. It belongs where you look at
the room anyway, not in the planner's own section.

## Test run

The control logic can be checked without Home Assistant and without any
third-party packages:

```
python3 heizungsplaner/tests/test_logik.py
```

Around 250 checks cover schedules across midnight, the heating curve and
summer hysteresis, presence including the return home, window detection, the
“setback only” mode and writing on edges. Quite a few of them are there
because the case was wrong once – for instance a school one kilometre away
that kept a child's room “on the way home” all morning.

## Licence

MIT
