# Home Assistant net4home Integration

Dieses Repository enthält die Custom Component zur Integration von net4home-Geräten mit Home Assistant.
Die net4home-Integration für Home Assistant ermöglicht es Ihnen, eine Verbindung zu net4home-Hardware-Geräten herzustellen.

Die Integration von net4home in Home Assistant bietet unbegrenzte Möglichkeiten für die Automatisierung.  
Die einfache Integration einer bestehenden Installation eröffnet eine Vielzahl von Anwendungsmöglichkeiten in Verbindung mit Geräten anderer Hersteller.

## Voraussetzungen

Die Integration erfordert einen net4home Bus-Connector.
Jede Verbindung zu einem Bus-Connector wird in Home Assistant als **Hub**-Gerät dargestellt. Nachdem der Hub verbunden ist, erscheinen net4home-Module als untergeordnete Geräte. Entitäten werden basierend auf dem gemeldeten Gerätetyp erstellt.
Die `net4home`-Integration ermöglicht Verbindungen zu mehr als einem Bus-Connector. Für jeden Connector muss ein neuer Integrations-Eintrag erstellt werden.

## Funktionen

- Manuelle Konfiguration (Host, Port, Bus-Passwort, MI, OBJADR)
- Binäre Sensoren (Kontakt, Bewegung, etc.)
- Lokalisierungsunterstützung in Englisch, Deutsch und Spanisch
- **Diagnose-Sensoren** für Gerätekonfiguration:
  - **PowerUp-Status** für Schalter und Lampen (Dimmer) - zeigt das Einschaltverhalten nach Stromausfall
  - **Minimale Helligkeit** für Dimmer - zeigt die konfigurierte minimale Helligkeit in Prozent
  - **Timer** für Timer-Aktoren - zeigt die konfigurierte Timer-Dauer in Sekunden
  - **Laufzeit** für Jalousien - zeigt die konfigurierte Laufzeit in Sekunden
- **Options-Flow** ermöglicht die Aktualisierung von MI und OBJADR ohne Neu-Konfiguration
- **Manueller ENUM_ALL-Trigger** über den Options-Flow zur Geräteerkennung

## Installation

### HACS-Installation (Empfohlen)

Um diese Integration über HACS (Home Assistant Community Store) zu installieren, verwenden Sie diese Schaltfläche:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=anynode&repo=net4home&category=integration)

Nach der Installation über HACS:
1. Starten Sie Home Assistant neu
2. Gehen Sie zu Einstellungen → Geräte & Dienste → Integration hinzufügen
3. Suchen Sie nach "net4home" und folgen Sie dem Setup-Assistenten

### Manuelle Installation

Wenn Sie die Installation manuell bevorzugen, folgen Sie diesen Schritten:
1. Kopieren Sie den `net4home`-Ordner in Ihr Home Assistant Konfigurationsverzeichnis unter `custom_components/`:
   ```
   custom_components/net4home/
   ```
2. Starten Sie Home Assistant neu
3. Gehen Sie zu Einstellungen → Geräte & Dienste → Integration hinzufügen
4. Suchen Sie nach "net4home" und folgen Sie dem Setup-Assistenten

## Konfiguration

Der Bus-Connector wird mit Host, Port und Passwort eingetragen. Läuft das Add-on **net4home Server**, bietet die Einrichtung stattdessen **Lokal** an. Dabei werden Adresse, Port und Passwort nicht abgefragt. Das Add-on meldet den Dienst unter dem Namen `net4home`.

### Ersteinrichtung

Während der Ersteinrichtung können Sie konfigurieren:
- **Host**: IP-Adresse oder Hostname des Bus-Connectors
- **Port**: TCP-Port (Standard: 3478)
- **Passwort**: Bus-Passwort
- **MI**: Modul-ID der Integration auf dem Bus (Standard: 65281)
- **OBJADR**: Objektadresse der Integration (Standard: 32700)
- **Unbekannte Geräte automatisch erkennen**: ein Modul anlegen, sobald es von sich aus sendet

Sind noch keine Module gespeichert, sucht der erste Start den Bus von selbst. Danach liest er die Modulinfo und die Gruppen. Ein zweiter Start ist dafür nicht nötig.

### Optionen

Nachdem die Integration eingerichtet wurde, können Sie die Optionen über folgendes aufrufen:
Einstellungen → Geräte & Dienste → net4home → Konfigurieren

In den Optionen können Sie:
- **MI** und **OBJADR** ändern
- **Busmodule ermitteln**: die Suche auf dem Bus anstoßen
- **Unbekannte Geräte automatisch erkennen**
- **Beim Neustart Gruppen lesen** und **Beim Neustart Modulinfo lesen**: die langen Tabellen beim Start auslassen. Was gelesen wird und was ausbleibt, beschreibt die [Anleitung Lesen beim Start](docs/lesen.md).

Was nach einer Änderung im Konfigurator oder in den Optionen zu tun ist, beschreibt die [Anleitung Konfiguration ändern](docs/konfiguration-aendern.md).

## Unterstützte Gerätetypen

- **Alarm**: HS-Safety. Scharfschaltung, Kontakte und Sabotage beschreibt die [Anleitung HS-Safety](docs/hs-safety.md).
- **Binary_sensor**: Kontaktsensoren, Bewegungsmelder und andere binäre Eingänge
- **Climate**: Thermostat und Heizungssteuerung (UP-TLH). Sollwert, Tagwert, Nachtwert und die beiden Regler beschreibt die [Anleitung UP-TLH](docs/up-tlh.md).
- **HS-Time**: Uhr, acht Profile und die Schalttabelle. Beschreibt die [Anleitung HS-Time](docs/hs-time.md).
- **Cover**: Jalousien- und Rollladensteuerung (HS-AJ3, HS-AJ4-500, etc.)
- **Light**: Dimmer-Steuerungen mit Helligkeitsunterstützung (HS-AD3, HS-AD3e, HS-AD1-1x10V)
- **Sensor**: Temperatur-, Feuchtigkeits- und Beleuchtungsstärke-Sensoren
- **Switch**: Relais-Schalter und Timer-Aktoren (HS-AR6, UP-AR2, etc.)
- **UP-RF**: Schlüsselverzeichnis mit Zuordnung zu Personen und ein Zutrittsereignis je Leser. Die Einrichtung beschreibt die [Anleitung UP-RF-Schlüssel](docs/rf-schluessel.md).
- **Gruppen**: eine Entität je Schaltgruppe, ein Telegramm an die Gruppenadresse. Anlegen, Namen und Mitglieder beschreibt die [Anleitung Gruppen](docs/gruppen.md).

> Die implementierten Plattformen decken nicht die gesamte Funktionalität des
> net4home-Systems ab. Daher bietet die net4home-Integration eine
> Vielzahl von Ereignissen, Geräte-Triggern und Aktionen. Diese sind ideal
> für die Verwendung in Automatisierungsskripten oder für Template-Plattformen.

## Diagnoseinformationen

Die Integration stellt Diagnose-Sensoren für jeden Gerätetyp zur Anzeige von Konfigurationsinformationen bereit:

### Schalter und Lampen
- **PowerUp**: Zeigt das Einschaltverhalten nach Stromausfall:
  - AUS (OFF)
  - EIN (ON)
  - wie vor Stromausfall (as before power loss)
  - keine Änderung (no change)
  - EIN mit 100% (ON with 100% - nur Dimmer)

### Lampen (Dimmer)
- **PowerUp**: Einschaltverhalten (siehe oben)
- **Minimale Helligkeit**: Konfigurierte minimale Helligkeit in Prozent (0-100%)

### Timer-Aktoren
- **PowerUp**: Einschaltverhalten (siehe oben)
- **Timer**: Konfigurierte Timer-Dauer in Sekunden

### Jalousien
- **Laufzeit**: Konfigurierte Laufzeit in Sekunden

Ist am Kanal eine Laufzeit eingetragen, rechnet der Aktor seine Position selbst und meldet sie auf Anfrage in Prozent: 100 ist ganz auf, 0 ganz zu. Home Assistant zeigt diese Position. Nach dem Einschalten des Moduls kennt der Aktor sie erst, wenn die Jalousie einmal ganz auf oder ganz zu gefahren ist. Bis dahin ist die Position unbekannt.

Fahrbefehle an den Kanal oder an eine Gruppe mit dem Kanal sieht Home Assistant auf dem Bus, auch die von Tastern. Die Jalousie zeigt dann **Öffnet** oder **Schließt**, und die Position läuft während der Fahrt mit. Am Ende der Fahrt fragt Home Assistant den Aktor nach der tatsächlichen Position.

Mit Laufzeit lässt sich die Jalousie auf eine Position fahren. Home Assistant fährt los und sendet nach der berechneten Zeit Stopp. Ohne Laufzeit meldet der Aktor keine Position, die Jalousie zeigt dann nur auf oder zu nach dem letzten Fahrbefehl.

Alle Diagnose-Sensoren werden automatisch aktualisiert, wenn die Gerätekonfiguration vom Bus gelesen wird.

## Einrichten von Geräten und Entitäten

Die `net4home`-Hardware-Module werden durch Home Assistant _Geräte_ dargestellt. Die Peripherie jedes `net4home`-Moduls wird durch Home Assistant _Entitäten_ dargestellt. Peripherien sind beispielsweise die Ausgangsports, Relais und Variablen eines Moduls.

## Anforderungen

Um eine stabile und fehlerfreie Funktionsweise zu gewährleisten, sollte die Konfiguration im net4home-Konfigurator zunächst überprüft werden.

Eigentlich sollte bereits alles korrekt konfiguriert sein. Die Erfahrung zeigt jedoch, dass wir hier etwas nacharbeiten müssen, da oft etwas nachgerüstet oder angepasst wurde. Über die Jahre gibt es sicherlich einige Dinge, die mit wenigen Klicks aufgeräumt werden können. Dies ist der wichtigste Teil einer sauberen Integration. Eine spätere Nacharbeit ist sehr zeitaufwändig.

Das Flag **Statusänderung** muss für die folgenden Aktoren gesetzt werden. Sonst erfährt Home Assistant nicht, wenn ein Aktor von einer anderen Stelle geschaltet wird, zum Beispiel von einem Taster am Bus. Die Anzeige bleibt dann auf dem letzten bekannten Zustand.

Die folgenden Module sind zu überprüfen:
- HS-AR6
- UP-AR2
- HS-AJ3
- HS-AJ4-500
- HS-AD3
- HS-AD3e

## Dienste

Die Integration stellt die folgenden benutzerdefinierten Dienste bereit:

- `net4home.debug_devices`: Protokolliert alle registrierten Geräte im Home Assistant-Log
- `net4home.clear_devices`: Löscht alle gespeicherten Geräte aus der Integration
- `net4home.enum_all`: Löst die Geräteerkennung aus (ENUM_ALL-Befehl)
- `net4home.assign_rf_key`: Ordnet einem UP-RF-Schlüssel eine Person und einen Namen zu
- `net4home.remove_rf_key`: Entfernt einen Schlüssel aus dem RF-Schlüsselverzeichnis

Die Einrichtung von Verzeichnis, Dashboard-Karte und Lesernamen beschreibt die [Anleitung UP-RF-Schlüssel](docs/rf-schluessel.md).

## Version

Aktuelle Version: **1.3.6**

## Fehlersuche

Wo die Meldungen stehen, was bei einer abgerissenen Verbindung passiert und die häufigsten Fälle beschreibt die [Anleitung Fehlersuche](docs/fehlersuche.md).

## Support

Für Probleme, Funktionswünsche oder Beiträge besuchen Sie bitte das [GitHub-Repository](https://github.com/anynode/net4home).
