# Lesen beim Start

Diese Anleitung beschreibt, was Home Assistant nach einem Start vom Bus liest und wie die beiden Schalter das verkürzen.

Die Schalter stehen unter **Einstellungen → Geräte & Dienste → net4home → Konfigurieren**. Beide sind in der Voreinstellung an. Speichern mit **OK** übernimmt die Schalter, startet aber nichts neu. Sie wirken beim nächsten Start, also nach einem Neustart von Home Assistant oder nach **Neu laden** der Integration.

## Beim Neustart Gruppen lesen

An liest die Gruppentabellen aller Schaltmodule. Das ist der lange Teil am Ende des Starts. Aus lässt die Tabellen aus und nimmt die Gruppen vom letzten Lesen.

Wann die Gruppen erscheinen, wo die Kanäle stehen und wie die Namen laufen, beschreibt die [Anleitung Gruppen](gruppen.md).

## Beim Neustart Modulinfo lesen

An liest die Konfiguration der Module, die noch nicht vollständig gelesen ist, und zusätzlich diese Tabellen:

- Aktoren, Sensoren und Modulspec der noch ausstehenden Module
- die Schalttabelle jedes HS-Time
- die Schlüssel-Liste der UP-RF-Leser
- die Modulspec der Klingel
- Aktorkanäle, die beim letzten Lesen unvollständig waren

Aus überspringt genau diese Tabellen. Die schon bekannten Geräte und Entitäten bleiben.

Weiterhin gelesen werden die kurzen Zustände: Uhrzeit und Profile der Schaltuhr, Sollwerte der UP-TLH, Scharf-Stufe und Kontakte des HS-Safety, die Zustände der Sensoren, der SI-Module und der Türöffner. Die Schalttabelle selbst gehört zur Modulinfo und bleibt dann auf dem letzten Stand. Details zur Uhr stehen in der [Anleitung HS-Time](hs-time.md).

## Ein einzelnes Modul lesen

**Lese Modul** am Gerät eines Moduls liest die Modulinfo dieses einen Moduls, auch wenn der Schalter aus ist. Die Gruppentabellen liest dieser Taster nicht. Dafür muss **Beim Neustart Gruppen lesen** an sein und die Integration neu starten.

## Erster Start

Sind noch keine Module gespeichert, sucht die Integration den Bus von selbst. Sie wartet, bis die Suche fertig ist, liest dann die Modulinfo der gefundenen Module und danach die Gruppentabellen. Der Einrichtungsdialog hat dafür keinen eigenen Schalter.

## Unbekannte Geräte

**Unbekannte Geräte automatisch erkennen** legt ein Modul an, sobald von seiner Adresse ein Telegramm kommt und das Modul noch nicht bekannt ist. Aus bleiben nur die Module, die schon gespeichert sind.

**Busmodule ermitteln** stößt dieselbe Suche später noch einmal an, zum Beispiel wenn ein Modul neu auf den Bus gekommen ist. Das ist dieselbe Suche wie `net4home.enum_all`. Die Gruppentabelle eines so gefundenen Moduls liest erst der nächste Start.
