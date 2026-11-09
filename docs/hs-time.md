# HS-Time: Uhr und Schaltuhr

Diese Anleitung beschreibt, was ein HS-Time in Home Assistant zeigt und was sich dort schalten lässt.

Die Schaltpunkte bleiben im net4home-Konfigurator. Home Assistant liest die Tabelle und die Uhr. Die acht Profile lassen sich ein- und ausschalten. Die Tabelle selbst schreibt Home Assistant nicht.

## Was die Integration anlegt

Am Modul, zum Beispiel `MI0300`:

| Entität | Bedeutung |
|---|---|
| `sensor.<modul>_uhrzeit` | Datum und Uhrzeit des Moduls. |
| `sensor.<modul>_minuten_ohne_empfang` | Minuten seit dem letzten DCF-Empfang. |
| `binary_sensor.<modul>_synchron` | An, wenn die Uhr fertig synchronisiert ist. |
| `binary_sensor.<modul>_empfang` | An, wenn DCF empfangen wird. |
| `binary_sensor.<modul>_sommerzeit` | An, wenn das Modul Sommerzeit meldet. |
| `binary_sensor.<modul>_feiertag` | An, wenn das Modul den Tag als Feiertag führt. |
| `switch.<modul>_profil_1` … `_profil_8` | Die acht Profile. An heißt, das Profil ist in der aktiven Maske. |
| `sensor.<modul>_schaltuhr` | Die Schaltpunkte. Der Zustand ist die Anzahl, die Zeilen stehen in den Attributen. |
| `sensor.<modul>_sunrise` | Heutiger Sonnenaufgang, wie das Modul ihn meldet. |
| `sensor.<modul>_sunset` | Heutiger Sonnenuntergang. |

Die Entitäts-ID kann den Bereich enthalten. Auf dem Gerät heißen die Entitäten **Uhrzeit**, **Minuten ohne Empfang**, **Profil 1** bis **Profil 8** und **Schaltuhr**.

Die Uhr wird etwa einmal pro Minute gelesen. Sonnenaufgang, Sonnenuntergang und die Profile kommen mit derselben Abfrage. Die Schalttabelle wird beim Start einmal gelesen, und nur, wenn **Beim Neustart Modulinfo lesen** an ist. Was dieser Schalter sonst auslässt, steht in der [Anleitung Lesen beim Start](lesen.md).

## Profile schalten

1. Das Gerät des HS-Time öffnen.
2. **Profil 1** bis **Profil 8** ein- oder ausschalten.

Jedes Profil ist ein Bit der Maske im Modul. Wer eines ändert, schreibt die ganze Maske. Die Schaltpunkte, die dieses Profil nennen, gelten danach mit oder ohne dieses Profil. Welche Zeile gerade dazugehört, zeigt die Spalte **Aktiv** der Schaltuhr.

Solange die Maske noch nicht gelesen wurde, sind die Profile `nicht verfügbar`.

## Die Schaltuhr

Der Zustand ist zum Beispiel `12 Schaltpunkte, 4 aktiv`. `Keine Schaltpunkte` heißt, die Tabelle wurde gelesen und keine Zeile ist belegt. `unknown` heißt, die Tabelle wurde noch nicht gelesen.

Unter **Attribute**:

| Attribut | Inhalt |
|---|---|
| `rows` | Eine Zeile je belegtem Schaltpunkt. |
| `markdown` | Dieselbe Tabelle als Markdown. |

Eine Zeile in `rows`:

| Feld | Inhalt |
|---|---|
| `nr` | Nummer der Zeile, ab 1. |
| `mode` | Zum Beispiel Täglich, Jährlich, Relativ zum Sonnenaufgang. |
| `when` | Uhrzeit, so wie das Modul sie speichert. Bei Sonnenbezug der Abstand, ein nachgestelltes Minus ist ein negativer Abstand. |
| `weekdays` | Wochentage als `MoDiMiDoFrSaSoFe`, Lücken als `--`. Leer, wenn der Modus keine Wochentage hat. |
| `target` | Name des Ziels, sonst die Objektadresse. |
| `command` | Zum Beispiel Ein, Aus, Auf, Ab oder eine Helligkeit in Prozent. |
| `profiles` | Profile dieser Zeile, `alle` oder `keine`. |
| `active` | `true`, wenn eines dieser Profile an ist und der Wochentag passt. An einem Feiertag zählt auch das Bit `Fe`. |

`active` heißt nicht, dass der Schaltpunkt in dieser Minute auslöst. Es heißt, die Zeile ist heute unter der aktuellen Maske beteiligt.

Leere Zeilen der Tabelle erscheinen nicht.

### Schaltuhr auf einem Dashboard

Die Karte übernimmt die fertige Tabelle aus dem Attribut `markdown`:

```yaml
type: markdown
title: Schaltuhr
content: "{{ state_attr('sensor.mi0300_schaltuhr', 'markdown') }}"
```

`sensor.mi0300_schaltuhr` durch die eigene Entität ersetzen. Die Entitäts-ID steht im Dialog der Entität **Schaltuhr**.
