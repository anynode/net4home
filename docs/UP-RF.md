

# UP-RF 

## Allgemeine Beschreibung

Busmodul zum Lesen und Erkennen von RF-Keys im Innenbereich. Die Montage erfolgt in handelsüblichen Unterputzdosen 60mm. Das Modul beinhaltet eine externe Lesespule und ein Info-LED. Über die Lesespule können Transponder (RF-Keys) durch einfaches „Davorhalten“ gelesen werden. 
Der Lesevorgang dauert ca. 200ms und ist für eine Entfernung bis ca. 10cm ausgelegt. Des weiteren ist im Modulspeicher eine Tabelle für 20 RF-Keys enthalten. Der Anlernvorgang für neue zu berechtigende Keys kann ohne PC nur mit einem Masterkey erfolgen. Geht ein RF-Key verloren, 
kann dieser aus der Tabelle gelöscht werden. Bei den RF-Keys handelt es sich um Chips mit einem 40-bit langen Code, der mit dem im Modul gespeicherten verglichen wird. Es ergeben sich so 1.099.511.627.776 verschiedene Schlüssel. Das Modul kann u.a. zum Steuern des EXT-LD (Motorriegel zum Verriegeln von 
Türen) genutzt werden. Außerdem eignet es sich zum Aufbau einer Zeiterfassungsumgebung. Bei Einsatz einer HS-Safety (Alarmanlage mit Busanschluss) kann über dieses Modul die Scharf- und Unscharfschaltung zusätzlich bedient werden.

## Funktion

- Lesespule für Leseabstand bis 10 cm
- externe LED signalisiert lesen
- LED kann Scharfzustand einer HS-Safety anzeigen 
- 20 Einträge für gelernte RF-Keys
- kann bei Erkennung eines RF-Key Befehl auf den Bus gesendet werden
- unterscheiden von „lang“ und „kurz“ vorhalten
- sendet gelesene Key-Daten auf den Bus
- direkter Anschluss an den Bus
- keine extra Versorgungsspannung erforderlich

### Verbindung zu anderen Buskomponenten

Verbindung zum Türsummer
Das UP-RF kann in Kombination mit anderen Buskomponenten zu den vielfältigsten Systemen zusammengestellt werden. In der einfachsten Variante sendet das UP-RF einen Befehl an einen anderen Busteilnehmer beim „kurz“ Vorhalten und einen anderen beim „lang“ Vorhalten. Dieses 
geschieht nur dann, wenn ein RF-Key erkannt wurde, der auf dem Modul gespeichert ist. Andere unbekannte RF-Keys werden ignoriert, jedoch selbst trotzdem auf den Bus gesendet. Hierdurch kann z.B. das Probieren eines Angreifers von einer Alarmanlage erkannt werden. In unserem ersten Beispiel 
sendet der UP-RF einen Befehl beim „kurz“ Vorhalten des RF-Key, hier als Karte dargestellt an einen Relaisaktor, der als Timer 3 Sekunden konfiguriert ist. Dieser steuert einen Türsummer (Öffner) für 3 Sekunden an.

Verbindung zum EXT-LD
In diesem Beispiel kommt noch ein EXT-LD (Motorriegel) hinzu. Hier sendet das UP-RF die Befehle „Entriegeln“ bei kurzem Vorhalten und „Verriegeln“ bei langem Vorhalten. Im EXT-LD kann beim Erreichen der „ENTRIEGELT“-Position der Befehl zum Senden des Befehles „öffnen“ an den HS-ARx, 
an den der Türöffner einer zweiten Tür angeschlossen ist, konfiguriert werden. Nach jedem Entriegeln kann so anschließend noch der Türöffner einer zweiten Tür betätigt werden, um auch diese Tür freizugeben. 

Verbindung zur Alarmanlage HS-Safety
Zum Steuern einer Alarmanlage kann der UP-RF verwendet werden, da alle gelesenen RF-Keys immer auch auf den Bus gesendet werden unabhängig davon, ob sie in der internen Tabelle einen direkten 
Befehl auf den Bus senden oder nicht. Die Alarmanlage wiederum hat eine eigene Tabelle zur Verwaltung der berechtigten RF-Keys. Sie schaltet beim Erkennen eines berechtigten RF-Keys in den 
Scharf- oder Unscharfzustand und steuert die externe LED des UP-RF an, die wiederum den Zustand der Alarmanlage signalisiert. Bei dieser Konfiguration sollte die LED von außen sichtbar angebracht 
werden.

Verbindung zum Zutrittskontrollmodul HS-Access
Eine weitere komplexere Konfiguration ist die Verbindung mit einem HS-Access Zutrittskontrollsystem, welches neben einer großen Key-RF-Verwaltung auch eine uhrzeitabhängige Berechtigung beherrscht. 
Hierdurch können z.B. Zeitfenster für Zutrittserlaubnis geschaffen werden. Optional zu der HS-Access kann ein PC mit einer Datenbank ins System integriert werden. Dieser zeichnet dann alle Ereignisse 
auf und kann die gewonnenen Daten anderen Systemen wie z.B. Lohnabrechnung zugänglich machen.

### Bedienung

Key „kurz“ vorhalten (>0,5 Sekunden) 
LED blinkt schnell
UP-RF sendet Befehl 1, wenn RF-Key bekannt

Key „lang“ vorhalten (>2 Sekunden) 
LED blinkt erst schnell und ist dann dunkel
UP-RF sendet Befehl 2, wenn RF-Key bekannt

Masterkey „kurz“ vorhalten
UP-RF ist für 15 Sekunden im Lernmodus (LED blinkt langsam)

Masterkey „lang“ vorhalten
Alle gelernten RF-Keys außer Masterkeys werden gelöscht.

Lernmodus
Im Lernmodus kann ein neuer Key gelernt werden. Dieser wird im Speicher abgelegt, wenn er noch 
nicht enthalten ist und noch ein Platz frei ist. Maximal können 20 RF-Keys gespeichert werden.

Um den Masterkey zu lernen, muss aus Sicherheitsgründen ein PC mit dem Konfigurationsprogramm 
benutzt werden. Der Masterkey kann nur andere Keys anlernen, selbst aber keine Befehle senden. Er 
sollte an einem sicheren Ort aufbewahrt werden. Masterkeys können auch nur vom PC aus gelöscht 
werden.

Bei jedem Vorhalten eines RF-Keys werden die Daten des RF-Keys über den Bus gesendet. In diesem 
Paket sind auch Informationen, ob lang oder kurz vorgehalten wurde, enthalten. Dieses ermöglicht es 
anderen Modulen diese Informationen zu verarbeiten.

##  Montage / Anschluss

Das Modul ist für den Einbau in Unterputzdosen in geschlossenen Räumen konzipiert. Die Lesespule 
und die externe LED können auch in den Außenbereich geführt werden. Beim Verlängern der 
Leitungen zur Lesespule wird keine Garantie für die Funktion sowie die Einhaltung der EMVVorschriften übernommen. Die Lesespule kann auch hinter dicken Glasscheiben oder in Mauern 
montiert werden. Da sich die Einbauorte von Fall zu Fall stark unterscheiden, sollten hier eigene 
Versuche mit der Reichweite zum RF-Key unternommen werden. Ungeeignet sind Abdeckungen der 
Spule aus leitfähigem oder magnetischen Material. Zu Personen mit älteren Herzschrittmachern sollte 
ein Sicherheitsabstand zur Lesespule eingehalten werden.
Vor der Montage der Leitungen ist die Busspannung abzuschalten. Beachten: Es ist auf Einhaltung der 
angegebenen Umgebungstemperatur zu achten und falls nötig ist für Belüftung zu sorgen. Es ist 
unbedingt auf Trennung des Busanschlusses von fremden Potentialen zu achten! Es dürfen keine 
Verbindungen vom Bus zu L, N oder PE hergestellt werden.

## Konfiguration

Auf dem Modul sind lokale Objektadressen zu konfigurieren, die wie an vielen anderen Punkten auch 
nur einmal im Bus vorhanden sein dürfen. Hierzu zählen die Aktorobjektadresse der externen LED sowie die Sensorobjektadresse (Absenderobjektadresse) des
- 1. Befehls („kurzes“ Vorhalten)
- 2. Befehls („langes“ Vorhalten)

Zu jedem der zwei Befehle muss eine Zieladresse und ein Befehl angegeben werden. Tabelle mit gespeicherten RF-Keys
Im Modul sind bis zu 20 RF-Keys incl. Masterkey speicherbar. Diese können ausgelesen, gelöscht oder geschrieben werden. Es muss mindestens ein Masterkey gelernt werden, um weitere RF-Keys im Modul zu speichern.

## Betrieb

Dem Modul ist folgender Betriebsparameter zugerordnet:
- externe LED ein/aus

Dieser Parameter kann durch Busbefehle verändert oder gelesen werden.

Verhalten bei Wiederkehr der Versorgungsspannung
Alle gespeicherten Keys bleiben bei Ausfall erhalten. Die LED ist aus.

Die externe LED ist wie ein einfacher Binäraktor aufgebaut. Der Zustand kann gelesen und geschrieben werden.

Kommunikation mit dem LED-Aktor
Aktion Befehl Parameter
				1
LED ein 			Set 		ungleich 0
LED aus 			Set 		0
LED umschalten 		Toggle
Anfrage LED? 		Req			-> Antwort vom Modul ActorAck 0/1


## Bus Mitschnitte

### Konfiguration auslesen

15:25:03	MI0099 (MI0099)		Konfigurator (MIFF01)	03 2D 02 01 11 04 00 01 0D 04 01 00 0A 00 DA	D0_ACK_TYP,UP-RF	MI 	

15:25:03	MI0099 (MI0099)		Konfigurator (MIFF01)	2E 00 00 03	D0_GET_VC_ACK	MI 	
15:25:03	MI0099 (MI0099)		Konfigurator (MIFF01)	03 2D 02 01 11 04 00 01 0D 04 01 00 0A 00 DA	D0_ACK_TYP,UP-RF	MI 	

15:25:03	MI0099 (MI0099)		Konfigurator (MIFF01)	2E 00 00 03	D0_GET_VC_ACK	MI 	
15:25:03	MI0099 (MI0099)		Konfigurator (MIFF01)	03 2D 02 01 11 04 00 01 0D 04 01 00 0A 00 DA	D0_ACK_TYP,UP-RF	MI 	

15:25:04	MI0099 (MI0099)		Konfigurator (MIFF01)	10 00 0B 6A 60 35 00 00 00 00 FF FF FF 26 AD	D0_RD_SENSOR_DATA_ACK 15	MI 	
15:25:04	MI0099 (MI0099)		Konfigurator (MIFF01)	10 01 0B 00 00 FF FF FF 00 00 FF FF FF 26 AE	D0_RD_SENSOR_DATA_ACK 15	MI 	


### Key kurz und lang vorgehalten
	
15:26:54	MI0099 (MI0099)	9901	27232	65 07 03 01 05 F4 69 E9 00 04	D0_VALUE_ACK	MI RF-Key 0105F469E9 weggezogen nach kurz	
15:29:01	MI0099 (MI0099)	9901	27232	65 07 03 01 05 F4 69 E9 00 02	D0_VALUE_ACK	MI RF-Key 0105F469E9 lang vorgehalten	

