# UP-RF-Schlüssel: Verzeichnis, Personen und Zutritt

Diese Anleitung richtet das Schlüsselverzeichnis eines UP-RF-Lesers ein: welcher Schlüssel wem gehört, und eine Übersicht auf einem Dashboard.

Die Zuordnung bleibt nach einem Neustart von Home Assistant erhalten.

## Was die Integration anlegt

Sobald ein UP-RF-Modul erkannt ist, gibt es:

| Entität | Bedeutung |
|---|---|
| `sensor.<leser>_rf_key` | Der zuletzt gelesene Schlüssel an diesem Leser. Der Zustand ist der zehnstellige Code. |
| `event.<leser>_zutritt` | Ein Ereignis je Tastendruck, mit Schlüssel, Name und Person. Erscheint im Logbuch. |
| `sensor.rf_schlusselverzeichnis` | Alle bekannten Schlüssel. Der Zustand ist die Anzahl, die Liste steht in den Attributen. |

Leere Lesungen (`0000000000` und `FFFFFFFFFF`) werden nicht gespeichert.

## Voraussetzung

Unter **Einstellungen → Personen** muss für jeden Benutzer eine Person existieren, zum Beispiel `person.oliver`. Die Aktion zur Zuordnung bietet genau diese Personen zur Auswahl an.

## Einen Schlüssel einer Person zuordnen

1. Den Schlüssel einmal an einen Leser halten, der ihn erkennt.
2. Den Code ablesen. Er steht als Zustand auf dem Sensor **RF-Key** dieses Lesers, zum Beispiel `sensor.mi0098_rf_key`. Solange dort `unknown` steht, wurde noch kein Schlüssel gelesen.
3. **Entwicklerwerkzeuge** öffnen und den Reiter **Aktionen** wählen. In älteren Versionen heißt dieser Reiter **Dienste**.
4. `RF-Schlüssel` suchen und **net4home: RF-Schlüssel einer Person zuordnen** auswählen.
5. Die Felder ausfüllen:
   - **Schlüsselcode:** der zehnstellige Code, Groß- und Kleinschreibung ist egal.
   - **Person:** die Person aus der Liste.
   - **Name:** ein freier Name, zum Beispiel `Schlüssel blau`. Das Feld darf leer bleiben.
6. **Aktion ausführen**.

Dasselbe geht als YAML im Aktionseditor:

```yaml
action: net4home.assign_rf_key
data:
  code: "1A2B3C4D5E"
  person: person.oliver
  name: "Schlüssel blau"
```

`code` ist der zehnstellige Schlüssel. `person` ist die Entität aus **Einstellungen → Personen**. `name` darf wegfallen.

Dieselbe Aktion ändert eine bestehende Zuordnung. Ein leeres Feld **Person** oder **Name** entfernt genau diese Angabe und lässt den Rest stehen.

Einen Schlüssel ganz aus dem Verzeichnis nehmen: Aktion **net4home: RF-Schlüssel entfernen**, denselben Code eintragen, ausführen. Wird er danach erneut gelesen, erscheint er wieder als unbekannter Schlüssel.

Bei mehr als einer net4home-Instanz zusätzlich das Feld **entry_id** der betroffenen Instanz angeben.

## Das Verzeichnis auf einem Dashboard anzeigen

1. Das Dashboard öffnen und oben rechts **Bearbeiten** wählen.
2. **Karte hinzufügen** → Karte **Markdown**.
3. Unten **Code-Editor anzeigen** wählen und den bisherigen Inhalt durch diesen Block ersetzen:

```yaml
type: markdown
title: RF-Schlüssel
content: |
  {%- set keys = state_attr('sensor.rf_schlusselverzeichnis', 'keys') or [] -%}
  {%- if keys -%}
  <table role='presentation' border='0' width='100%'>
  {%- for k in keys -%}
  {%- set reader = k.get('last_reader') -%}
  {%- set eid = ('sensor.' ~ reader|lower ~ '_rf_key') if reader else '' -%}
  {%- set fname = state_attr(eid, 'friendly_name') if reader else none -%}
  {%- set aname = area_name(eid) if reader else none -%}
  {%- set where = fname if fname and ' RF-Key' not in fname else aname or reader -%}
  {%- set seen = k.get('last_seen') -%}
  {%- set when = seen[:16].replace('T', ' ') if seen else '' -%}
  <tr>
  <td width='36' align='center' valign='middle'><font color='{{ '#039be5' if seen else '#9e9e9e' }}'><ha-icon icon='mdi:key'></ha-icon></font></td>
  <td valign='middle'><strong>{{ k.get('name') or k.code }}</strong><br><font color='#9e9e9e'><small>{{ k.code }}{% if where %} · {{ where }}{% elif not seen %} · noch nicht gesehen{% endif %}</small></font></td>
  <td width='148' align='right' valign='top'><font color='#9e9e9e'><small>{{ when }}</small></font></td>
  </tr>
  {%- endfor -%}
  </table>
  {%- else -%}
  Noch keine Schlüssel bekannt.
  {%- endif -%}
```

4. **Speichern**.

Die Karte aktualisiert sich bei jedem Tastendruck und bei jeder Zuordnung.

Jede Zeile zeigt den Namen, darunter den Code und den Leser, und rechts den Zeitpunkt der letzten Lesung. Ein Schlüssel, der nur zugeordnet und noch nie gelesen wurde, ist grau und trägt den Hinweis „noch nicht gesehen“. Person und Anzahl stehen nicht auf der Karte. Sie bleiben in den Attributen des Sensors.

Die Liste ist nach der letzten Lesung sortiert. Schlüssel ohne Lesung stehen unten.

## Namen der Leser

Der Lesername sucht in dieser Reihenfolge:

1. Der Anzeigename des Sensors **RF-Key** dieses Lesers, sofern er umbenannt wurde. Aus `MI0098 RF-Key` wird zum Beispiel `Leser Haustür`.
2. Der Bereich, dem das Leser-Gerät zugeordnet ist, zum Beispiel `Nebeneingang`.
3. Die Moduladresse, zum Beispiel `MI0099`, wenn weder Name noch Bereich gesetzt sind.

So bekommt ein Leser einen Namen:

1. **Einstellungen → Geräte & Dienste → Geräte**, den UP-RF-Leser öffnen.
2. Beim Sensor **RF-Key** das Zahnrad öffnen und unter **Name** den gewünschten Namen eintragen, zum Beispiel `Leser Haustür`.
3. Die **Entitäts-ID** `sensor.mi00xx_rf_key` unverändert lassen. Die Karte findet den Leser über diese ID.

Alternativ dem Gerät einen Bereich zuweisen. Die Karte verwendet den Bereich, solange der Sensor **RF-Key** seinen Standardnamen behält.

## Zutritt im Logbuch

Jeder Tastendruck erzeugt ein Ereignis auf der Entität **Zutritt** des Lesers. Im Logbuch und in den Entitätsdetails stehen:

- `rf_key`: der Code
- `key_name`: der vergebene Name
- `person`: die Personen-Entität, zum Beispiel `person.oliver`
- `person_name`: der Anzeigename der Person

`key_name` und `person` sind leer, solange der Schlüssel nicht zugeordnet ist. Die Zuordnung gilt ab dem nächsten Tastendruck. Bereits geschriebene Logbucheinträge ändern sich nicht.

Die Ereignisse lassen sich als Auslöser in Automatisierungen verwenden. Der Gerätetrigger des Lesers bietet weiterhin **RF-Key short hold**, **long hold** und **removed after short**, optional gefiltert auf einen bestimmten Code.
