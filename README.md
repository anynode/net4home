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

- Auto-Erkennung über Zeroconf
- Manuelle Konfiguration (Host, Port, Bus-Passwort, MI, OBJADR)
- Binäre Sensoren (Kontakt, Bewegung, etc.)
- Lokalisierungsunterstützung in Englisch, Deutsch und Spanisch
- Module über den Options-Flow hinzufügen (Modultyp, Software-Version, EE-Text und MI)
- Geräte über den Options-Flow hinzufügen (MI und Modultyp)
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

Der net4home Bus-Connector kann von Home Assistant automatisch erkannt werden. Wenn eine Instanz gefunden wurde, wird sie als "Gefunden" angezeigt. Sie können sie dann direkt einrichten.

### Ersteinrichtung

Während der Ersteinrichtung können Sie konfigurieren:
- **Host**: IP-Adresse oder Hostname des Bus-Connectors
- **Port**: TCP-Port (Standard: 3478)
- **Passwort**: Bus-Passwort
- **MI**: Modul-ID (Standard: 1)
- **OBJADR**: Objektadresse (Standard: 1)
- **Erkennen**: Option zum Auslösen von ENUM_ALL während des Setups

### Optionen

Nachdem die Integration eingerichtet wurde, können Sie die Optionen über folgendes aufrufen:
Einstellungen → Geräte & Dienste → net4home → Konfigurieren

In den Optionen können Sie:
- **MI aktualisieren**: Modul-ID ändern ohne Neu-Konfiguration
- **OBJADR aktualisieren**: Objektadresse ändern ohne Neu-Konfiguration
- **ENUM_ALL auslösen**: Geräteerkennung manuell auslösen

## Unterstützte Gerätetypen

- **Binary_sensor**: Kontaktsensoren, Bewegungsmelder und andere binäre Eingänge
- **Climate**: Thermostat und Heizungssteuerung (UP-TLH)
- **Cover**: Jalousien- und Rollladensteuerung (HS-AJ3, HS-AJ4-500, etc.)
- **Light**: Dimmer-Steuerungen mit Helligkeitsunterstützung (HS-AD3, HS-AD3e, HS-AD1-1x10V)
- **Sensor**: Temperatur-, Feuchtigkeits- und Beleuchtungsstärke-Sensoren
- **Switch**: Relais-Schalter und Timer-Aktoren (HS-AR6, UP-AR2, etc.)

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

Alle Diagnose-Sensoren werden automatisch aktualisiert, wenn die Gerätekonfiguration vom Bus gelesen wird.

## Einrichten von Geräten und Entitäten

Die `net4home`-Hardware-Module werden durch Home Assistant _Geräte_ dargestellt. Die Peripherie jedes `net4home`-Moduls wird durch Home Assistant _Entitäten_ dargestellt. Peripherien sind beispielsweise die Ausgangsports, Relais und Variablen eines Moduls.

## Anforderungen

Um eine stabile und fehlerfreie Funktionsweise zu gewährleisten, sollte die Konfiguration im net4home-Konfigurator zunächst überprüft werden.

Eigentlich sollte bereits alles korrekt konfiguriert sein. Die Erfahrung zeigt jedoch, dass wir hier etwas nacharbeiten müssen, da oft etwas nachgerüstet oder angepasst wurde. Über die Jahre gibt es sicherlich einige Dinge, die mit wenigen Klicks aufgeräumt werden können. Dies ist der wichtigste Teil einer sauberen Integration. Eine spätere Nacharbeit ist sehr zeitaufwändig.

> Änderungen an Statusänderungen haben keinen Einfluss auf die bestehenden Funktionen.

Das Flag **Statusänderung** muss für die folgenden Aktoren gesetzt werden. Dies ist wichtig, damit die HA immer Informationen über den aktuellen Status zur Anzeige erhält. Wenn beispielsweise eine Lampe durch einen normalen Schalter geschaltet wird, hat die HA hier keine Information. Es gibt auch die Statusänderung, die an andere Bus-Geräte kommuniziert wird.

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

## Version

Aktuelle Version: **1.3.0**

## Support

Für Probleme, Funktionswünsche oder Beiträge besuchen Sie bitte das [GitHub-Repository](https://github.com/anynode/net4home).
