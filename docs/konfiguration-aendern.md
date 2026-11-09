# Konfiguration ändern

Diese Anleitung beschreibt, was nach einer Änderung zu tun ist. Eine Änderung kann an zwei Stellen passieren:

- **Am Bus**: im Konfigurator oder am Modul selbst, zum Beispiel eine Laufzeit oder eine Gruppe.
- **In Home Assistant**: in den Optionen der Integration, zum Beispiel Host, Port oder die Startschalter.

Eine Änderung am Bus kommt erst nach Home Assistant, wenn die Integration sie liest. Das geschieht über den Taster **Lese Modul** am Gerät oder über einen Neustart. Welcher Weg nötig ist, zeigt die Tabelle.

## Die Regel

1. Die Änderung zuerst im Konfigurator speichern oder ins Modul schreiben.
2. In Home Assistant den kleinsten Schritt wählen: **Lese Modul**, dann **Neu laden**, dann Neustart.
3. Einen Neustart nur machen, wenn die Tabelle es verlangt. Ein Neustart liest beim Start viel vom Bus und dauert deshalb mehrere Minuten.

## Was wann nötig ist

| Was geändert wurde | Was tun | Neustart nötig |
|---|---|---|
| Laufzeit einer Jalousie (am Kanal) | Am Modul **Lese Modul** drücken | Nein |
| Schalttabelle oder Uhr eines HS-Time | Am Modul **Lese Modul** drücken | Nein |
| Gruppen eines Moduls (Konfigurator) | **Beim Neustart Gruppen lesen** an lassen und Home Assistant neu starten | Ja |
| Host, Port, Passwort, MI oder OBJADR | In den Optionen speichern, dann **Neu laden** | Nein |
| Startschalter **Beim Neustart Gruppen lesen** oder **Beim Neustart Modulinfo lesen** | In den Optionen speichern, dann **Neu laden** | Nein |
| Auslöser der HS-Safety (Konfigurator) | Home Assistant neu starten | Ja |
| Neue Version der Integration | Home Assistant neu starten | Ja |
| Neue Module auf dem Bus | In den Optionen **Busmodule ermitteln** drücken | Nein |

**Neu laden** findet man unter **Einstellungen → Geräte & Dienste → net4home** im Menü **⋮**.

Die Optionen stehen unter **Einstellungen → Geräte & Dienste → net4home → Konfigurieren**.

## Laufzeit einer Jalousie

Die Laufzeit steht am Kanal des Aktors. Nach **Lese Modul** kennt Home Assistant sie. Die Position in Prozent erscheint aber erst, wenn der Aktor die Position kennt. Das ist der Fall, nachdem die Jalousie einmal ganz auf oder ganz zu gefahren ist. Bis dahin zeigt Home Assistant nur auf oder zu. Details stehen im [README](../README.md#jalousien).

Zeigt die Jalousie nach **Lese Modul** noch keine Prozent, dann **Neu laden** drücken. Hilft das nicht, Home Assistant neu starten.

## Wenn es danach nicht stimmt

1. Den Taster **Lese Modul** am betroffenen Gerät noch einmal drücken.
2. **Neu laden** der Integration.
3. Erst dann Home Assistant neu starten.
4. Das Protokoll prüfen. Hinweise dazu stehen in der [Fehlersuche](fehlersuche.md).

Die Gruppen und die Startschalter sind in den Anleitungen [Gruppen](gruppen.md) und [Lesen beim Start](lesen.md) beschrieben.
