# Gruppen: Schaltgruppen vom Bus

Diese Anleitung beschreibt, wann Home Assistant die Schaltgruppen anlegt, wie das Lesen beim Start ausbleibt, wo die zugehörigen Kanäle stehen und wie die Namen funktionieren.

Die Zugehörigkeit bleibt im net4home-Konfigurator. Home Assistant liest sie und schaltet die Gruppe mit einem Telegramm an die Gruppenadresse. Es schreibt keine Gruppen ins Modul und löscht keine.

## Wann die Gruppen angelegt werden

Die Gruppentabellen werden beim Start der Integration gelesen, ganz am Ende der übrigen Startabfragen. Der Schalter **Beim Neustart Gruppen lesen** steht dafür an. Das ist die Voreinstellung.

Gelesen wird jedes Schaltmodul, das eine Gruppentabelle hat. Leere Zeilen antworten trotzdem, deshalb geht das Lesen durch die ganze Tabelle. Bei vielen Modulen dauert das mehrere Minuten. Solange es läuft, ist das Attribut **Gruppen** an den Kanälen leer, und schon vorhandene Gruppen zeigen `nicht verfügbar`.

Fertig ist das Lesen, wenn die Gruppen am Gerät **Gruppen** wieder einen Zustand haben. Den Dialog eines Kanals danach neu öffnen, das Attribut füllt sich nicht in einem schon offenen Dialog.

Eine Gruppe wird eine Entität:

| Mitglieder | Entität | Was sie kann |
|---|---|---|
| nur Lampen | Licht | an, aus, Helligkeit |
| nur Jalousien | Jalousie | auf, ab, stopp |
| Schalter oder gemischt | Schalter | an und aus |

Alle Entitäten liegen am Gerät **Gruppen** (Einstellungen → Geräte & Dienste → net4home). Der erste Name ist `Gruppe 510` für die Busadresse G510. Die Entitäts-ID bleibt `gruppen_gruppe_510`, auch nach dem Umbenennen. Sie kann den Bereich enthalten. Dashboards, die diese ID nutzen, bleiben gültig.

**Lese Modul** an einem einzelnen Modul liest dessen Aktor- und Sensordaten. Die Gruppentabellen liest es nicht.

Ein Kanal kann in mehreren Gruppen stehen. Eine Gruppe kann Kanäle von vielen Modulen enthalten.

## Lesen am Start auslassen

1. **Einstellungen → Geräte & Dienste → net4home → Konfigurieren** öffnen.
2. **Beim Neustart Gruppen lesen** ausschalten.
3. Mit **OK** speichern.

Der nächste Start überspringt die Gruppentabellen und nimmt die Gruppen vom letzten Lesen. Die Entitäten, die Zustände und die vergebenen Namen bleiben. Geändert wird die Zugehörigkeit dabei nicht. Wer im Konfigurator eine Gruppe umbaut, schaltet den Schalter wieder an und startet neu. Danach kann er wieder aus bleiben.

Ist der Schalter aus und es wurde noch nie eine Tabelle gelesen, gibt es keine Gruppen, bis ein Start mit eingeschaltetem Schalter durch ist.

**Beim Neustart Modulinfo lesen** ist ein eigener Schalter und betrifft die Gruppen nicht. Was er auslässt, steht in der [Anleitung Lesen beim Start](lesen.md).

## Welche Kanäle dazugehören

Die Geräteseite eines Moduls zeigt keine Gruppen. Die Zugehörigkeit steht an zwei Entitäten.

**An der Gruppe.** Die Gruppenentität öffnen, zum Beispiel `Gruppe 522` oder den selbst vergebenen Namen. Unter **Attribute**:

| Attribut | Inhalt |
|---|---|
| Adresse | Die Busadresse, zum Beispiel `G522`. |
| Mitglieder | Die Kanäle dieser Gruppe. |

Jedes Mitglied ist der Name des Kanals, so wie er an der Kanal-Entität steht, zum Beispiel `Jalousie links`. Gibt es für den Kanal noch keine Entität, steht dort Modul und Kanal, zum Beispiel `MI0315 CH6`.

**Am Kanal.** Die Kanal-Entität öffnen, also die Zeile in der Karte **Steuerung**, nicht die Geräteseite. Unter **Attribute** steht **Gruppen**. Dort sind alle Gruppen dieses Kanals, durch Komma getrennt. Hat die Gruppe einen eigenen Namen, steht der Name. Sonst `Gruppe 520`.

Dieselben Attribute stehen unter **Entwicklerwerkzeuge → Zustände**. Dort und in Vorlagen heißen sie `groups`, `address` und `members`, zum Beispiel `{{ state_attr('cover.ch1_32001', 'groups') }}`. Die deutschen Namen zeigt nur der Dialog.

## Wie die Namen laufen

Das Modul speichert keinen Namen, nur die Adresse und den Kanal. Den Namen vergibt jeder selbst in Home Assistant.

1. Die Gruppenentität öffnen.
2. Das Zahnrad öffnen, oder über die Entitätsliste **Einstellungen** der Entität.
3. Das Feld **Name** setzen, zum Beispiel `Jalousie beide`.
4. Speichern.

Der Name bleibt über einen Neustart erhalten. Er wird nicht in den Konfigurator und nicht ins Modul geschrieben. Zwei Gruppen dürfen denselben Namen tragen.

Dieser Name erscheint danach im Attribut **Gruppen** der zugehörigen Kanäle. Ohne eigenen Namen steht dort `Gruppe 520`.

Die Namen der Mitglieder sind die Namen der Kanal-Entitäten. Wer eine Jalousie in `Jalousie links` umbenennt, sieht diesen Namen in der Mitgliederliste, sobald die Gruppenentität ihren Zustand neu schreibt. Die Entitäts-ID der Gruppe ändert sich durch keinen dieser Namen.

## Gruppen einem Raum zuordnen

Jede Gruppe bekommt ihren Raum einzeln. Das geht an der Gruppenentität, nicht am Gerät **Gruppen**.

Wird der Raum am Gerät **Gruppen** gesetzt, erbt jede Gruppe diesen Raum. Dann stehen alle Gruppen in einem Raum. Das ist nicht gewollt. Das Gerät soll keinen Raum haben.

1. Die Gruppenentität öffnen, zum Beispiel `Jalousien Besprechung Boston`.
2. Das Zahnrad öffnen.
3. Den Schalter **Bereich des Geräts verwenden** ausschalten. Solange er an ist, blendet Home Assistant das Feld **Bereich** aus.
4. Im Feld **Bereich** den Raum wählen, zum Beispiel **Besprechung Boston**.
5. **Aktualisieren** klicken.

Für jede weitere Gruppe wiederholen, zum Beispiel `Jalousien Thomas` in den Raum **Thomas**.

Steht am Gerät **Gruppen** noch ein Raum, übernehmen ihn alle Gruppen, die den Schalter an haben. Den Raum am Gerät entfernen: Einstellungen → Geräte & Dienste → Geräte → **Gruppen** → Zahnrad → Bereich leeren.
