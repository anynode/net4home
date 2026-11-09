# HS-Safety: Scharfschaltung und Kontakte

Diese Anleitung beschreibt, was ein HS-Safety in Home Assistant zeigt und wie die Alarmanlage von dort scharf und unscharf geschaltet wird.

Die Auslöser-Liste bleibt im net4home-Konfigurator. Home Assistant liest sie und schaltet die Anlage. Es schreibt keine Konfiguration ins Modul.

## Was im Konfigurator stehen muss

Im Konfigurator, Reiter der Auslöser, bekommt jeder überwachte Kontakt eine Zeile:

| Feld | Wirkung in Home Assistant |
|---|---|
| Objektadresse | Der Kontakt, dessen Zustand gelesen wird. |
| Text | Der Name des Sensors, höchstens 8 Zeichen. |
| Aktiv bei | In welchen Scharf-Stufen dieser Kontakt zählt. |
| Sensortyp | Steht als Attribut am Sensor (NO oder NC). Den Zustand dreht Home Assistant daran nicht um. |

Leere Zeilen, Adresse 0 oder `FFFF`, legt Home Assistant nicht an.

Die Stufen im Konfigurator bedeuten:

| Im Konfigurator | Der Kontakt zählt bei |
|---|---|
| Extern | nur Extern |
| Intern 2+Ext. | Intern 2 und Extern |
| Intern 1+2+Ext. | Intern 1, Intern 2 und Extern |
| Sabotage | keiner Scharf-Stufe. Der Kontakt löst den Sensor **Alarm** nicht aus. |

Ein Bewegungsmelder in dieser Liste ist ein normaler Kontakt. Solange er Bewegung meldet, gilt er als offen und **Bereit (Extern)** bleibt aus.

## Was die Integration anlegt

Am Modul, zum Beispiel `MI0301`:

| Entität | Bedeutung |
|---|---|
| `alarm_control_panel.<modul>` | Scharf und unscharf schalten. Die Karte verlangt keinen Code. |
| `sensor.<modul>_scharf_stufe` | Die aktuelle Stufe als Text: Aus, Schaltung läuft, Intern 1, Intern 2, Extern. |
| `binary_sensor.<modul>_bereit_extern` | An, wenn jeder Kontakt, der bei Extern zählt, geschlossen ist. |
| `binary_sensor.<modul>_alarm` | An, wenn die Anlage scharf ist und ein Kontakt dieser Stufe offen ist. |
| `binary_sensor.<modul>_sabotage` | An, wenn das Modul Sabotage meldet und die Anlage scharf ist. |
| `binary_sensor.<modul>_<name>` | Ein Sensor je belegter Auslöser-Zeile. An bedeutet offen. |

Die Entitäts-ID kann den Bereich enthalten. Auf dem Gerät heißen die Entitäten **Bereit (Extern)**, **Alarm**, **Sabotage** und **Scharf-Stufe**. Die Kontakt-Sensoren heißen wie der Text im Konfigurator, zum Beispiel `MI0301 F 00.01`.

Home Assistant nennt die Stufen anders als das Modul:

| Zustand der Alarmkarte | Scharf-Stufe | Im Konfigurator |
|---|---|---|
| Deaktiviert (`disarmed`) | Aus | Unscharf |
| Scharfschalten (`arming`) | Schaltung läuft | Das Modul prüft noch die Kontakte. |
| Zuhause (`armed_home`) | Intern 1 | Intern 1 scharf |
| Nacht (`armed_night`) | Intern 2 | Intern 2 scharf |
| Abwesend (`armed_away`) | Extern | Extern scharf |

Die Schaltflächen der Karte senden die Befehle mit Prüfung. Das Modul schaltet nur scharf, wenn die Kontakte dieser Stufe geschlossen sind.

| Schaltfläche | Befehl ans Modul |
|---|---|
| Zuhause | 11, Intern 1 mit Prüfung |
| Nacht | 12, Intern 2 mit Prüfung |
| Abwesend | 13, Extern mit Prüfung |
| Deaktivieren | 0, unscharf |

Zusätzlich gibt es drei Taster **Scharf ohne Prüfung**. Sie senden 1, 2 und 3 und schalten auch bei offenen Kontakten scharf. Ein offener Kontakt kann dann sofort Alarm auslösen. Die Taster sind nach dem Einrichten aus und erscheinen erst, wenn sie am Gerät aktiviert werden.

## Einrichten

1. Im Konfigurator die Auslöser eintragen: Adresse, Name und Stufe.
2. Home Assistant neu starten, damit die Liste gelesen wird. Eine Änderung im Konfigurator erscheint erst nach dem nächsten Start.
3. Das Gerät des Moduls öffnen, zum Beispiel `MI0301`.
4. Prüfen, ob die Kontakt-Sensoren da sind und einen Zustand haben. `unknown` heißt, auf die Abfrage kam keine Antwort.
5. **Bereit (Extern)** ansehen. Steht dort `aus` oder `unknown`, die Attribute `open_contacts` und `unknown_contacts` lesen.
6. Die Alarmkarte auf ein Dashboard legen. Ein Code ist nicht nötig.

Die Anlage wird beim Start einmal abgefragt: Stufe, Auslöser-Liste und jeder Kontakt. Nach einem Schaltbefehl aus Home Assistant wird die Stufe noch ein paar Sekunden lang erneut gelesen. Eine dauernde Abfrage gibt es nicht. Telegramme, die das Modul von sich aus sendet, werden mitgelesen.

Schaltbefehle von einem anderen Teilnehmer, zum Beispiel dem Konfigurator oder einem Leser, sieht Home Assistant, sobald das Modul den neuen Status auf den Bus schreibt. Kommt dieses Telegramm nicht, bleibt die Karte auf dem letzten bekannten Zustand, bis Home Assistant neu startet.

## Scharf schalten

1. **Bereit (Extern)** muss `an` sein, wenn Extern geschaltet werden soll. Für Intern 1 oder Intern 2 zählen nur die Kontakte dieser Stufe. Die Karte **Bereit (Extern)** prüft die Extern-Liste.
2. Auf der Alarmkarte **Zuhause**, **Nacht** oder **Abwesend** wählen.

Weigert sich das Modul, bleibt die Karte auf **Deaktiviert**. Ein offener Kontakt der gewählten Stufe steht in `open_contacts` von **Bereit (Extern)** oder am einzelnen Kontakt-Sensor.

## Scharf ohne Prüfung

1. Das Gerät des Moduls öffnen.
2. Oben die deaktivierten Entitäten einblenden.
3. Die Taster **Scharf ohne Prüfung: Intern 1**, **Intern 2** und **Extern** aktivieren.

Diese Taster umgehen die Prüfung im Modul. Sie sind für den Fall gedacht, dass ein Kontakt dauerhaft offen ist und die Anlage trotzdem scharf werden soll.

## Sabotage

Das Modul setzt das Sabotage-Bit oft schon im unscharfen Zustand. Der Sensor **Sabotage** bleibt dann `aus`. Er wird `an`, sobald die Anlage scharf ist und das Bit weiterhin gesetzt ist.

Das rohe Bit steht am Sensor im Attribut `sabotage_raw`. `alarm_state` zeigt die Stufe, zu der diese Meldung gehört.

## Protokoll

Das Protokoll ist die Ereignisliste des Moduls: Scharf- und Unscharfschaltungen, Alarme mit dem auslösenden Kontakt, falsche Keys und Konfigurationsbefehle.

### So kommt das Protokoll nach Home Assistant

Die Integration liest das Protokoll selbst. Einen Knopf dafür gibt es nicht.

1. **Beim Start** von Home Assistant. Die Auslöser-Liste und das Protokoll werden nacheinander gelesen. Das dauert je nach Bus und Anzahl der Einträge einige Zeit. Erst danach steht das Protokoll vollständig da.
2. **Nach jeder Änderung der Scharf-Stufe**, also auch nach einem Schaltbefehl aus Home Assistant oder vom Bedienteil. Das Protokoll wird dann neu gelesen, damit der neue Eintrag erscheint.

Eine Änderung der Auslöser im Konfigurator wird erst nach einem Neustart von Home Assistant gelesen. Wer nur das Protokoll neu laden will, ändert die Scharf-Stufe oder startet Home Assistant neu.

Das Lesen schreibt nichts ins Modul.

### Der Sensor

| Entität | Inhalt |
|---|---|
| `sensor.<modul>_protokoll` | Zustand: der neueste Eintrag als Text, sonst `Keine Einträge`. |

Ein Eintrag steht in den Attributen zweimal:

| Attribut | Inhalt |
|---|---|
| `rows` | Liste mit `time`, `trigger`, `text` und `line`. Neueste zuerst. |
| `entries` | Nur die Zeilen als Text, neueste zuerst. |

Beispiel für einen Eintrag in `rows`:

```yaml
time: "07.11.26 23:00:00"
trigger: "Haustür"
text: "Alarm ausgelöst"
line: "07.11.26 23:00:00  Haustür  Alarm ausgelöst"
```

Der Zeitstempel ist die Zeit, die das Modul gespeichert hat. Home Assistant rechnet sie nicht um.

Die Texte wie `Extern scharf` oder `Deaktiviert` stammen aus einer Zuordnung in der Integration. Das Modul sendet nur einen Code. Für unbekannte Codes steht `Ereignis 0x..`. Der Code `0xE8` heißt im Konfigurator `Sabotage Ein`. Die Integration zeigt dafür `Deaktiviert`, weil das Sabotage-Bit auch im unscharfen Zustand gesetzt sein kann und dann keine Aktion des Benutzers war.

### Protokoll auf einem Dashboard

Die Karte liest die Attribute `rows` des Sensors:

```yaml
type: markdown
title: Protokoll
content: |
  | Zeit | Auslöser | Ereignis |
  |---|---|---|
  {%- for r in state_attr('sensor.mi0301_protokoll', 'rows') or [] %}
  | {{ r.time }} | {{ r.trigger or '–' }} | {{ r.text }} |
  {%- endfor %}
```

Die Zeichen `{%-` am Zeilenanfang sind nötig, sonst entstehen Leerzeilen und die Tabelle bricht.

## Schlüssel

Die Schlüssel (Tabelle 3 im Konfigurator, Reiter **Schlüssel**) liest die Integration in dieser Version nicht aus. Es gibt dafür keine Entität und kein Attribut. Die Schlüssel werden im Konfigurator gepflegt. In Home Assistant sind sie nicht sichtbar.

Die Schlüssel-Ereignisse im Protokoll (`3x falscher Key`) erscheinen dagegen im Protokoll-Sensor.

## Kontakte ohne Antwort

Manche Adressen in der Auslöser-Liste gehören zu einem anderen Modul und antworten nicht auf die Kontaktabfrage. Bei einer Tür an einem EXT-LD ist das der Fall. Der Sensor bleibt auf `unknown`, und der Name steht in `unknown_contacts` von **Bereit (Extern)**.

Solange ein überwachter Kontakt unbekannt ist, wird **Bereit (Extern)** nicht `an`. Home Assistant schätzt den Zustand nicht aus dem anderen Modul.

## Attribute

**Bereit (Extern)**

| Attribut | Inhalt |
|---|---|
| `open_contacts` | Namen der Extern-Kontakte, die offen sind. |
| `unknown_contacts` | Namen der Extern-Kontakte ohne Antwort. |

**Alarm**

| Attribut | Inhalt |
|---|---|
| `open_contacts` | Namen der offenen Kontakte der aktuellen Stufe. Leer, solange der Sensor `aus` ist. |

**Kontakt**

| Attribut | Inhalt |
|---|---|
| `address` | Objektadresse aus dem Konfigurator. |
| `armed_levels` | Stufen, in denen dieser Kontakt zählt: Intern 1, Intern 2, Extern. |
| `sabotage_contact` | Die Zeile ist als Sabotage eingetragen. |
| `normally_open` | Sensortyp NO. |
| `normally_closed` | Sensortyp NC. |
