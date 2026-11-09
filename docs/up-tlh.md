# UP-TLH: Sollwert, Tagwert und Nachtwert

Diese Anleitung beschreibt, was ein UP-TLH in Home Assistant zeigt und was sich dort ändern lässt. Ein UP-T nutzt dieselben Entitäten.

Die Temperaturregelung bleibt im Modul. Home Assistant gibt Werte vor und liest mit, was andere Teilnehmer auf den Bus schreiben.

## Was das Modul selbst tut

Im Konfigurator gibt es drei Temperaturen und zwei Regler:

| Im Konfigurator | Bedeutung |
|---|---|
| Aktueller Sollwert | Die Temperatur, auf die das Modul gerade regelt. |
| Tagwert | Gespeicherte Vorgabe für den Tag. |
| Nachtwert | Gespeicherte Vorgabe für die Nacht. |
| Heizregler aktiv | Der Heizregler im Modul ist eingeschaltet. |
| Kühlregler aktiv | Der Kühlregler im Modul ist eingeschaltet. |

Kp, Ki, Ta und die Ansteuerung des Heiz- oder Kühlaktors laufen im UP-TLH. Home Assistant schiebt den Tagwert oder den Nachtwert nicht auf den aktuellen Sollwert. Welcher der beiden Werte gerade gilt, entscheidet das Modul zusammen mit dem Zeitprofil auf dem Bus.

## Was die Integration anlegt

Am Modul, zum Beispiel `MI0264`:

| Entität | Bedeutung |
|---|---|
| `climate.<modul>` | Aktueller Sollwert und Modus. Der Modus fasst die beiden Regler zusammen. |
| `number.<modul>_tagwert` | Tagwert, verstellbar. |
| `number.<modul>_nachtwert` | Nachtwert, verstellbar. |

Die Entitäts-ID kann den Bereich enthalten, zum Beispiel `number.oliver_mi0264_tagwert`. Auf dem Gerät heißen die Entitäten **Tagwert** und **Nachtwert**.

An der Climate-Entität stehen zusätzlich die Attribute `heat_active` und `cool_active`. Sie entsprechen den beiden Häkchen im Konfigurator.

| Modus | Heizregler | Kühlregler |
|---|---|---|
| heat | an | aus |
| cool | aus | an |
| heat_cool | an | an |
| off | aus | aus |

Die Messwerte hängen als eigene Geräte unter dem Modul. Ab Benutzer-Software 1.17 liegen sie fest hinter der Basisadresse:

| Messwert | Objekt ab Software 1.17 |
|---|---|
| Temperatur | Basisadresse + 3 |
| Helligkeit | Basisadresse + 4 |
| Luftfeuchte | Basisadresse + 5 |

Bei `MI0264` (Software 4.04/1.22) ist die Basisadresse 26401, die Messwerte liegen also auf 26404, 26405 und 26406.

Ältere Software, zum Beispiel 3.00/1.09, speichert die Objektadresse in jedem Sensordatensatz. Es gibt keinen festen Abstand zur Basisadresse. `MI0254` meldet Temperatur, Helligkeit und Luftfeuchte auf 25401, 25402 und 25403. Die Temperatur teilt sich dort die Adresse mit dem Sollwert. `MI0259` hat den Sollwert auf Objekt 800 und die Messwerte auf 25901, 25902 und 25903. Die Integration liest diese drei Datensätze beim Start und fragt die Werte ab. Sensoren, die früher an einer geratenen Adresse angelegt wurden, entfernt sie dabei. Bei `MI0259` sind das die Objekte 801 bis 805. Bei den anderen Modulen mit Software 1.09 sind es die Adressen ab Basisadresse + 3, zum Beispiel 25404, 25405 und 25406 bei `MI0254`. Die drei Adressen aus den Datensätzen bleiben.

Das Sendeintervall stellt der Konfigurator ein, bei `MI0264` 5 Minuten.

Dazu gibt es die Sensoren **Presetday**, **Presetnight** und **Targettemp**. Sie zeigen Tagwert, Nachtwert und den aktuellen Sollwert nur an. Verstellen lassen sie sich nicht. Dieselben Werte stehen an **Tagwert**, **Nachtwert** und der Climate-Entität.

## Aktuellen Sollwert ändern

1. Das Gerät des UP-TLH öffnen, zum Beispiel `MI0264`.
2. Die Climate-Entität öffnen.
3. Die Zieltemperatur setzen.

Zulässig sind 5 bis 30 °C in Schritten von 0,5 °C. Der Modus schaltet die Regler:

- **Heizen** schaltet nur den Heizregler ein.
- **Kühlen** schaltet nur den Kühlregler ein.
- **Heizen/Kühlen** schaltet beide ein.
- **Aus** schaltet beide aus.

## Tagwert und Nachtwert ändern

1. Am selben Gerät die Entität **Tagwert** oder **Nachtwert** öffnen.
2. Die Temperatur eintragen.

Zulässig sind 0 bis 40 °C in Schritten von 0,1 °C. 0 °C ist ein gültiger Tagwert und bedeutet, dass diese Vorgabe ungenutzt ist.

Das Modul speichert beide Werte in einem Datensatz. Wer den Tagwert ändert, schreibt den Nachtwert unverändert mit, und umgekehrt. Dafür muss der andere Wert schon bekannt sein. Direkt nach dem Start ist das der Fall, sobald die Entitäten einen Wert zeigen.

## Änderungen von einer anderen Stelle

Ändert der Konfigurator oder ein anderes Busteilnehmer einen Wert, übernimmt Home Assistant ihn, sobald das Telegramm am Bus-Connector ankommt:

- Tagwert und Nachtwert aktualisieren die beiden Zahlen-Entitäten.
- Ein neuer aktueller Sollwert aktualisiert die Climate-Entität.
- Eine Änderung der Regler aktualisiert den Modus und die Attribute `heat_active` und `cool_active`.

Beim Start liest die Integration den aktuellen Sollwert und die Regler einmal vom Modul. Eine Änderung, die im Konfigurator nur auf dem Bildschirm steht und noch nicht mit **Übernehmen** oder **Sichern** auf den Bus geschrieben wurde, erscheint in Home Assistant nicht. Ist das Fenster noch offen, zeigt ein erneutes Lesen dort den Wert, den Home Assistant geschrieben hat.
