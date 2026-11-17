# -*- coding: utf-8 -*-
"""Die Karten für den Abschnitt „Heizungsplaner“."""

UEBERSICHT = """{%- set sym = {
  'komfort': ['🔥','Komfort'], 'eco': ['🌙','Eco'], 'nacht': ['💤','Nacht'],
  'abwesend': ['🚪','Abwesend'], 'heimkehr': ['🚗','Heimkehr'],
  'urlaub': ['🏖️','Urlaub'], 'fenster': ['🪟','Fenster offen'],
  'sommer': ['☀️','Sommer'], 'aus': ['⏻','Aus'], 'gesperrt': ['🔒','Gesperrt'],
  'manuell': ['✋','Von Hand'], 'absenkung': ['⬇️','Absenkung'],
  'party': ['🎉','Party'] } -%}
{%- set ruht = ['sommer','aus','gesperrt'] -%}
{%- set raeume = states.sensor | selectattr('entity_id','search','heizungsplaner_raum_')
      | rejectattr('state','in',['unavailable','unknown']) | sort(attribute='name') | list -%}
{%- set aktiv = raeume | rejectattr('attributes.zustand','in',ruht) | list -%}
{%- set roh = state_attr('sensor.heizungsplaner_aussentemperatur_gedaempft','roh') -%}
{%- if is_state('switch.heizungsplaner_party','on') -%}
🎉 **Party bis {{ state_attr('switch.heizungsplaner_party','bis_uhrzeit') }} Uhr** – noch {{ state_attr('switch.heizungsplaner_party','restminuten') }} Minuten

{% endif -%}
{%- set betrieb = [] -%}
{%- if is_state('binary_sensor.heizungsplaner_trockenlauf','on') -%}
{%- set betrieb = betrieb + ['🧪 **Trockenlauf** – es wird nichts gestellt'] -%}
{%- endif -%}
{%- if is_state('binary_sensor.heizungsplaner_sommerbetrieb','on') -%}
{%- set betrieb = betrieb + ['☀️ **Sommerbetrieb** – die Ventile bleiben zu'] -%}
{%- endif -%}
{%- if is_state('input_boolean.urlaub','on') -%}
{%- set betrieb = betrieb + ['🏖️ **Urlaub**'] -%}
{%- endif -%}
{{ betrieb | join(' · ') if betrieb else '🔥 **Regelbetrieb**' }}

Draußen **{{ roh | round(1) if roh is not none else '?' }} °C** · gedämpft {{ states('sensor.heizungsplaner_aussentemperatur_gedaempft') }} °C · {{ aktiv | count }} von {{ raeume | count }} Räumen geregelt

| | Raum | Ziel | Ist | Danach |
|:--:|---|--:|--:|---|
{% for r in raeume -%}
{%- set a = r.attributes -%}
{%- set z = a.zustand | default('') -%}
{%- set s = sym.get(z, ['•', z]) -%}
{%- set ist = a.ist_temperatur -%}
{%- set kommt = sym.get(a.naechster_modus, ['', a.naechster_modus or '']) -%}
| {{ s[0] }} | **{{ r.name | replace('Heizungsplaner ','') | replace('Heizung ','') }}**{{ ' 🪟' if a.fenster == 'offen' else (' ⚠️' if a.fenster == 'stumm' else '') }} | {% if z in ruht %}*zu*{% else %}{{ r.state | float | round(1) }} °C{% endif %} | {{ (ist | float | round(1) ~ ' °C') if ist not in [none,'unknown'] else '–' }} | {% if a.naechste_uhrzeit %}{{ a.naechste_uhrzeit }} {{ kommt[0] }} {{ a.naechstes_ziel | round(1) }} °C{% else %}–{% endif %} |
{% endfor %}
{%- set auffaellig = raeume | selectattr('attributes.zustand','in',
      ['fenster','abwesend','gesperrt','manuell','heimkehr']) | list -%}
{%- if auffaellig %}
{% for r in auffaellig -%}
{{ sym.get(r.attributes.zustand, ['•'])[0] }} *{{ r.name | replace('Heizungsplaner ','') | replace('Heizung ','') }}: {{ r.attributes.begruendung }}*
{% endfor -%}
{%- endif %}
{%- if raeume | selectattr('attributes.zustand','in',ruht) | list | count > 0 %}

*„zu“ = Ventil geschlossen. Die Schaltpunkte laufen weiter und greifen, sobald wieder geregelt wird.*
{%- endif %}"""

AUSFALL = """## ⚠️ Ausgefallen
{% for m in state_attr('binary_sensor.heizungsplaner_stoerung','fehler') or [] -%}
- {{ m }}
{% endfor %}
*Diese Räume werden gerade nicht geregelt.*"""

HINWEIS = """### Hinweise
{% for m in state_attr('binary_sensor.heizungsplaner_stoerung','warnungen') or [] -%}
- {{ m }}
{% endfor %}"""

# Farbe über card-mod – aber sparsam: Die Karte behält Hintergrund und Rahmen
# des Themes und bekommt nur einen farbigen Streifen an der Kante sowie eine
# farbige Überschrift. Eine Karte mit eigener Grundfarbe fällt sonst aus dem
# Dashboard heraus, statt sich einzufügen.
def _akzent(farbe):
    # card-mod erwartet für das Innere einer Karte die Wörterbuchform: „.“
    # meint die Karte selbst, „ha-markdown $“ deren Schattenwurzel.
    return {"style": {
        ".": f"ha-card {{ border-left: 3px solid {farbe}; }}",
        "ha-markdown $": f"h2, h3 {{ color: {farbe}; margin-top: 0; }}",
    }}


STIL_AUSFALL = _akzent("var(--error-color, #f44336)")
STIL_HINWEIS = _akzent("var(--warning-color, #ffa726)")


# Spaltenbreiten: Das Symbol braucht wenig, der Raumname bekommt den Rest,
# die Zahlen stehen rechtsbündig beieinander.
TABELLENSTIL = """
table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0 4px 0;
}
th {
  font-size: 0.78em;
  font-weight: 500;
  opacity: 0.6;
  text-align: left;
  padding: 2px 8px 6px 8px;
  border-bottom: 1px solid var(--divider-color);
}
td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--divider-color);
}
tr:last-child td { border-bottom: none; }
th:nth-child(1), td:nth-child(1) { width: 30px; text-align: center; padding-right: 0; }
th:nth-child(3), td:nth-child(3),
th:nth-child(4), td:nth-child(4) { text-align: right; white-space: nowrap; }
th:nth-child(5), td:nth-child(5) { text-align: right; white-space: nowrap; }
"""


# ── Eine Regel im Blick behalten ────────────────────────────────────────────
#
# Für einen Raum, dessen Zeitplan zeitweise von einer Regel übersteuert wird –
# etwa das Wohnzimmer mit seiner Homeoffice-Regelung. Eine Kachel, die nur
# erscheint, solange die Regel greift, und sonst nichts vom Platz nimmt.
#
# Bewusst **keine** `conditional`-Karte: In einer Sections-Ansicht meldet die
# in HA 2026.8 „Konfigurationsfehler“. Dort ist `visibility` an der Karte
# selbst der richtige Weg.

def regelkarte(sensor, name="Homeoffice", icon="mdi:laptop"):
    """Eine Kachel, sichtbar nur solange die Übersteuerungsregel greift.

    ``sensor`` ist der Raum-Sensor des Planers, etwa
    ``sensor.heizungsplaner_raum_wohnzimmer``. Angezeigt wird, bis wann die
    Regel läuft – „bis 14:00 Uhr“; ein Klick öffnet den Sensor mit Zielwert,
    Begründung und Lage.
    """
    return {
        "type": "tile",
        "entity": sensor,
        "name": name,
        "icon": icon,
        "color": "green",
        "state_content": ["uebersteuerung_bis"],
        "visibility": [{
            "condition": "template",
            "value_template": (f"{{{{ state_attr('{sensor}', "
                               f"'uebersteuerung_greift') | default(false, true) }}}}"),
        }],
    }


def abschnitt():
    return {
        "type": "grid",
        "cards": [
            {"type": "heading", "heading": "Heizungsplaner",
             "heading_style": "title", "icon": "mdi:radiator",
             "badges": [
                 {"type": "entity", "entity": "sensor.heizungsplaner_status"},
                 {"type": "entity",
                  "entity": "sensor.heizungsplaner_aussentemperatur_gedaempft"},
             ]},
            {"type": "tile", "entity": "switch.heizungsplaner_party",
             "name": "Partytaste", "icon": "mdi:party-popper",
             "state_content": ["anzeige"],
             "features": [{"type": "toggle"}],
             "features_position": "inline"},
            {"type": "conditional",
             "conditions": [{"condition": "numeric_state",
                             "entity": "binary_sensor.heizungsplaner_stoerung",
                             "attribute": "ausgefallen", "above": 0}],
             "card": {"type": "markdown", "content": AUSFALL,
                      "card_mod": STIL_AUSFALL}},
            {"type": "conditional",
             "conditions": [{"condition": "numeric_state",
                             "entity": "binary_sensor.heizungsplaner_stoerung",
                             "attribute": "warnungen_anzahl", "above": 0}],
             "card": {"type": "markdown", "content": HINWEIS,
                      "card_mod": STIL_HINWEIS}},
            {"type": "markdown", "content": UEBERSICHT,
             "card_mod": {"style": {"ha-markdown $": TABELLENSTIL}}},
            {"type": "entities", "title": "Betrieb", "show_header_toggle": False,
             "entities": [
                 {"entity": "switch.heizungsplaner_party", "name": "Partytaste"},
                 {"entity": "binary_sensor.heizungsplaner_sommerbetrieb",
                  "name": "Sommerbetrieb"},
                 {"entity": "binary_sensor.heizungsplaner_trockenlauf",
                  "name": "Trockenlauf"},
                 {"entity": "binary_sensor.heizungsplaner_stoerung",
                  "name": "Störung"},
                 {"entity": "input_boolean.gastezimmer_belegt",
                  "name": "Gästezimmer belegt"},
                 {"entity": "input_boolean.urlaub", "name": "Urlaub"},
             ]},
        ],
    }
