# Fehlersuche

Diese Anleitung hilft, wenn ein Gerät fehlt, ein Zustand nicht stimmt oder die Verbindung abreißt. Sie nennt, wo die Meldungen stehen, was sie bedeuten und was als Nächstes zu tun ist.

## Wo die Meldungen stehen

**Protokoll.** **Einstellungen → System → Protokolle**. Die Meldungen der Integration beginnen mit `custom_components.net4home`. Oben rechts **Vollständige Protokolle anzeigen** wählen, sonst fasst Home Assistant gleiche Meldungen zusammen.

**Debug-Protokoll.** Für eine genaue Suche:

1. **Einstellungen → Geräte & Dienste → net4home** öffnen.
2. Im Menü **⋮** die Option **Debug-Protokollierung aktivieren** wählen.
3. Den Fehler nachstellen.
4. Im selben Menü **Debug-Protokollierung deaktivieren**. Home Assistant lädt die Protokolldatei herunter.

Das Debug-Protokoll enthält jedes gesendete Telegramm. Nach dem Nachstellen wieder ausschalten, sonst wächst das Protokoll schnell.

**Diagnosedaten.** Auf der Seite der Integration im Menü **⋮** **Diagnosedaten herunterladen**. Die Datei enthält jedes bekannte Gerät mit Modell, Objektadresse, übergeordnetem Modul und Lesestand (`detail_status`), außerdem MI und OBJADR der Verbindung und ob sie besteht. Host, Passwort und Titel des Eintrags sind geschwärzt.

**Geräteliste ins Protokoll.** Die Aktion `net4home.debug_devices` schreibt jedes registrierte Gerät mit Typ und Namen ins Protokoll.

## Verbindung zum Bus-Connector

Beim Start steht im Protokoll:

```
Connect with net4home Bus connector at 192.168.x.x:3478
```

Ist der Bus-Connector beim Start nicht erreichbar, zeigt die Integration **Einrichtung wird wiederholt** mit Host, Port und Fehler. Nach zehn Sekunden ohne Antwort gilt der Versuch als gescheitert. Home Assistant versucht es danach von selbst erneut, mit wachsendem Abstand. Host und Port prüfen und den Bus-Connector erreichbar machen. Wer nicht warten will, wählt im Menü **⋮** **Neu laden**.

Reißt die Verbindung im Betrieb ab, steht dort:

```
[IP] Connection to net4home Bus connector closed
[IP] Try to reconnect - attempt 1/5 in 5.0s...
```

Die Integration versucht es in Runden zu fünf Versuchen, mit 5, 10, 15, 20 und 25 Sekunden Abstand. Gelingt es, folgt `Reconnect successful`, und Schalter und Lampen werden neu abgefragt. Nach einer erfolglosen Runde steht `Maximale Reconnect-Versuche erreicht` im Protokoll, und die nächste Runde beginnt. Ist der Bus-Connector wieder erreichbar, verbindet sich die Integration also von selbst. Wer nicht bis zum nächsten Versuch warten will, startet sie mit **Neu laden**.

Solange die Verbindung fehlt, sind Lampen, Schalter, Jalousien, Motorriegel, Gruppen, Klima, Alarmanlage und Eingänge `nicht verfügbar`. Im Protokoll steht `Connection to bus connector … is down`, danach `… is up`. Ein Befehl in dieser Zeit wird abgelehnt, die Meldung **Keine Verbindung zum Busconnector. Der Befehl wurde nicht gesendet.** erscheint in der Oberfläche und als Fehler der Automation.

## Start dauert lange

Nach einem Neustart liest die Integration Modulinfo und Gruppentabellen. Bei vielen Modulen dauert das mehrere Minuten. Im Protokoll:

| Meldung | Bedeutung |
|---|---|
| `Reading MI0136 (HS-AR6) ns=… na=… nm=…` | Die Modulinfo dieses Moduls wird gelesen. |
| `Reading group tables of 42 modules` | Das Gruppenlesen beginnt. |
| `MI0136 group table: 1 used of 80 lines` | Ein Modul ist fertig. |
| `MI0136 group table missed 45 of 80 lines` | So viele Zeilen kamen auch nach Wiederholung nicht an. |
| `Group G522 cover: …` | Das Gruppenlesen ist fertig, eine Zeile je Gruppe. |

Beide Teile lassen sich beim Start auslassen. Wie, steht in der [Anleitung Lesen beim Start](lesen.md).

## Häufige Fälle

| Was man sieht | Ursache | Was tun |
|---|---|---|
| Ein Aktor zeigt nicht, dass er an einem Taster geschaltet wurde. | Im Konfigurator fehlt das Flag **Statusänderung**. Das Modul meldet den neuen Zustand nicht. | Im Konfigurator **Statusänderung** setzen und übertragen. Am Gerät zeigt der Diagnose-Sensor **State changes**, ob das Flag gesetzt ist. |
| Ein Zustand bleibt `unbekannt`. | Das Modul hat auf die Abfrage beim Start nicht geantwortet. | Am Modul **Lese Modul** drücken. Hilft das nicht, im Protokoll nach Meldungen mit der MI des Moduls suchen. |
| Ein Modul fehlt ganz. | Es wurde nie gefunden. | In **Konfigurieren** **Busmodule ermitteln** wählen und speichern. Mit **Unbekannte Geräte automatisch erkennen** wird es auch angelegt, sobald es von sich aus sendet. |
| Ein Kanal eines Moduls fehlt. | Die Aktortabelle wurde nicht vollständig gelesen. | Am Modul **Lese Modul** drücken. |
| Ein Gerät hat Entitäten doppelt, eine davon leer. | Ein alter Eintrag aus einer früheren Version ist übrig. Er ist `nicht verfügbar` und wird nicht mehr bereitgestellt. | Die leere Entität öffnen, Zahnrad, **Löschen**. Vorher prüfen, dass kein Dashboard und keine Automation sie nutzt. |
| Das Attribut **Gruppen** ist leer. | Das Gruppenlesen läuft noch, oder der Kanal ist in keiner Gruppe. | Warten bis `Group G…` im Protokoll steht, dann den Dialog neu öffnen. Siehe [Anleitung Gruppen](gruppen.md). |
| Eine Gruppe aus dem Konfigurator fehlt. | Die Zeilen dieser Gruppe kamen beim Lesen nicht an, oder die Zeile ist ein Eingangsspeicher und kein Ausgang. | Im Protokoll nach `group table missed` suchen. **Beim Neustart Gruppen lesen** einschalten und neu starten. |
| Eine Jalousie zeigt keine Position, oder **Position setzen** meldet, die Position sei unbekannt. | Am Kanal ist keine Laufzeit eingetragen, oder die Jalousie stand seit dem Einschalten des Moduls nie ganz auf oder ganz zu. Der Aktor meldet dann `0xFF`, im Debug-Protokoll `status 0xFF, position None`. | Im Konfigurator die Laufzeit setzen, am Modul **Lese Modul** drücken. Die Jalousie einmal ganz auf oder ganz zu fahren. Siehe [Jalousien](../README.md#jalousien). |
| Eine Jalousie steht auf `auf` oder `zu`, obwohl sie an einem Taster anders gefahren wurde. | Der Taster sendet an eine Adresse, die Home Assistant nicht kennt, und **Statusänderung** fehlt. | Im Konfigurator **Statusänderung** am Jalousiekanal setzen. |
| Die Schaltuhr steht auf `unbekannt`. | Die Schalttabelle wurde noch nie gelesen, oder **Beim Neustart Modulinfo lesen** ist aus. | Den Schalter einschalten und neu starten. Siehe [Anleitung HS-Time](hs-time.md). |
| Im Dialog **Konfigurieren** stehen Schlüsselnamen wie `read_groups_on_startup`. | Der Browser hat die alten Übersetzungen gespeichert. | Die Seite mit **Strg+F5** neu laden. |
| Eine neue Version der Integration zeigt keine Wirkung. | Home Assistant lädt den Code der Integration nur beim Start. **Neu laden** genügt dafür nicht. | Home Assistant neu starten. |

Fehler bei HS-Safety, UP-TLH und UP-RF beschreiben die jeweiligen Anleitungen: [HS-Safety](hs-safety.md), [UP-TLH](up-tlh.md), [UP-RF-Schlüssel](rf-schluessel.md).

## Was zu einer Fehlermeldung gehört

- Version der Integration (**Einstellungen → Geräte & Dienste → net4home**) und von Home Assistant
- Modultyp und MI, zum Beispiel `HS-AR6 MI0136`, und die Software-Version aus dem Konfigurator
- was erwartet war und was passiert ist
- ein Debug-Protokoll, in dem der Fehler einmal nachgestellt ist
- die Diagnosedaten
