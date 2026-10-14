# mintPDF 1.39.3

Lokale PDF-Werkzeugsammlung für Linux Mint, Python und GTK 4.
Autor: Josef Lehner · https://dogtruck.eu · GPL-3.0-only (siehe LICENSE).

## Start und Installation

Voraussetzungen: Python 3.12, `python3-gi`, `gir1.2-gtk-4.0`.
Die optionale PDF-Bibliothek PyMuPDF lässt sich mit `sh setup_dependencies.sh`
installieren; dafür werden `python3-venv` und eine Internetverbindung benötigt.
Sie liegt ausschließlich in der lokalen virtuellen Umgebung `.venv`.

Start aus dem Quellcode: `.venv/bin/python mintpdf.py` oder, wenn alle
Abhängigkeiten systemweit vorliegen, `python3 mintpdf.py`.

Benutzerlokale Installation: `python3 install.py`.
Der Installer erstellt einen Menüeintrag, einen Desktop-Starter und das Kommando
`~/.local/bin/mintpdf`. Bereits vorhandene Dateien werden nicht überschrieben.
Optionale Abhängigkeiten im installierten Verzeichnis erneut einrichten.
Deinstallation: `python3 ~/.local/opt/mintpdf/install.py --uninstall`.
Später selbst erzeugte Dateien werden erhalten. Mit dem mitgelieferten Einrichtungsskript nachinstallierte Bibliotheken werden
ebenfalls für die Deinstallation erfasst.

## DEB-Paket für Linux Mint 22.x

Das GitHub-Release enthält ein DEB für amd64 und Python 3.12 mit PyMuPDF 1.28.2:

```bash
sudo apt install ./mintpdf_1.39.3_amd64.deb
```

APT installiert GTK/Cairo, Ghostscript, LibreOffice, OCRmyPDF, Tesseract mit Deutsch/Englisch, wkhtmltopdf und die Java-Laufzeit als Pflichtabhängigkeiten, auch ohne Recommends. veraPDF 1.30.3 ist im DEB enthalten. Für den Quellstart bleiben externe Werkzeuge separat erforderlich. Fehlende Werkzeuge nennt die Oberfläche. Das Paket enthält Menüeintrag, Programmsymbol und eine verwaltete Desktop-Verknüpfung, sofern ein Desktop-Ordner aktiviert ist. Entfernen mit `sudo apt remove mintpdf` bereinigt die eigenen Laufzeitdaten unter `~/.local/share/mintpdf`; separat gespeicherte PDFs bleiben erhalten. Nicht erreichbare oder geschützte Pfade werden gemeldet.

Quellpaket und SHA-256-Prüfsummen stehen im selben Release. Entwicklungsumgebung, Einstellungen und Logs sind ausgeschlossen. Tests: siehe [PRUEFANLEITUNG.md](PRUEFANLEITUNG.md).

## Bedienung

Jede Funktion startet mit einem Dateidialog: Quelldateien passend zur Aktion,
bei Erstellen/Webseite die Ausgabedatei. Anschließend Optionen festlegen und
mit Fertigstellen starten. PDF bearbeiten öffnet stattdessen direkt LibreOffice Draw. Abbrechen erzeugt keine Ausgabe.

Ghostscript wird für reine Komprimierung verwendet (fünf Qualitätsprofile).
OCRmyPDF ist für Texterkennung vorgesehen (Tesseract-Sprache, Modus, PDF/PDF-A,
Optimierung und Scan-Ausrichtung). PyMuPDF bleibt für Seitenoperationen zuständig.
PDF-in-Bilder bietet eine wählbare Auflösung. OCRmyPDF und Tesseract müssen
installiert sein; Sprachen werden aus Tesseract erkannt. Die OCR-Funktion
bleibt bei fehlenden Programmen sichtbar und ist ausgegraut.


Unter **Datei → Einstellungen → Ausgabe** lässt sich der Ausgabeordner dauerhaft
ändern (anfangs Downloads). Die Einstellung `output_dir` bleibt nach Neustarts erhalten.
**PDF trennen** öffnet zuerst eine PDF-Auswahl, dann die Trennmöglichkeiten:
Einzelseiten, Blöcke mit N Seiten, Trennstellen nach Seitennummern oder eigene
Seitenbereiche mit Semikolon. Vorschau prüfen und mit **Fertigstellen** ein ZIP
mit den Teil-PDFs erzeugen.


PDF zusammenführen öffnet sofort die PDF-Dateiauswahl. Danach die Dateien im
Reihenfolgefenster mit „Nach oben“ und „Nach unten“ sortieren und mit
„Fertigstellen“ zusammenführen. Weitere PDFs hinzufügen oder entfernen ist möglich.
Standard-Ausgabeordner aller Werkzeuge ist `~/Downloads` (bei Josef
`/home/josef/Downloads`). Vorhandene Dateinamen erhalten im Vorschlag eine Nummer.
Die Oberfläche verwendet eine klassische Menüleiste.


30 implementierte Werkzeuge sind über die Menüleiste erreichbar. Die Startseite zeigt alle 35 Kacheln;
Kacheln mit fehlenden Abhängigkeiten sind ausgegraut und nicht anklickbar. Erkennung alle fünf Sekunden; nach
Installation einer Python-Bibliothek das Programm neu starten.

PyMuPDF: Zusammenfügen, Trennen, Bilder in PDF, PDF in Bilder, Bilder extrahieren,
Verschlüsseln, Entschlüsseln, Drehen, Löschen, Extrahieren, Sortieren,
Wasserzeichen, Seitenzahlen, Überlagern, Sichtvergleich, Optimieren,
Textschwärzung und Erstellen. Ghostscript: Komprimieren. LibreOffice: PDF bearbeiten und Office-nach-PDF. OCRmyPDF: OCR.
wkhtmltopdf: Webseite in PDF.

Beim Sichtvergleich werden A und B nebeneinander angeordnet. Es gibt keine
automatische Differenzmarkierung. Unterschreiben ist keine Zertifikatssignatur.
Textschwärzung entfernt durchsuchbare Texttreffer; gescannte Seiten benötigen OCR.
Bearbeiten öffnet LibreOffice Draw direkt nach der PDF-Auswahl.
PDF erstellen setzt eingegebenen Text auf eine neue A4-Seite.

Ausgaben werden neu erzeugt. Existierende Ziele werden auch bei gleichzeitigem
Zugriff nicht überschrieben. Seiten- und Bildserien werden in ZIP-Dateien gespeichert.

## Konfiguration, Sprachen und Hilfe

`config/settings.json` speichert Sprache und optionale GitHub-Rohdatenquelle.
`logs/mintpdf.log` enthält Fehler ohne Passwörter. Bei schreibgeschützter
Installation liegen Benutzerdaten unter `~/.local/share/mintpdf`.
Deutsch und Englisch sind enthalten. `languages/<code>.json` enthält ausschließlich
Stringwerte, dazu `language_code` und `language_name`. Spracheinstellungen und
HTML-Hilfen werden dynamisch erkannt. Fehlende Texte fallen auf Englisch zurück;
fehlende Hilfe wird gemeldet und nicht durch eine andere Sprache ersetzt.

Die Einstellungen können Sprachdateien und HTML-Hilfen aus einer eingetragenen
mintPDF-GitHub-Rohdatenbasis herunterladen. Da dieses Projekt nicht veröffentlicht
wurde, ist noch keine Quelle voreingestellt. Neue Dateien werden geprüft und
vorhandene Dateien erhalten. Keine automatischen Netzverbindungen beim Start.

## Kommandozeile

```sh
python3 mintpdf.py --help
python3 mintpdf.py --list-tools
python3 mintpdf.py --tool merge --input a.pdf --input b.pdf --output merged.pdf
python3 mintpdf.py --tool extract --input a.pdf --pages 1,3-5 --output selected.pdf
```

Passwörter werden interaktiv abgefragt und nicht als Kommandozeilenparameter
übergeben. Die Argumente gelten auch für die installierte Anwendung.

## Entwicklung und Build

`core.py` enthält Werkzeugkatalog und Verarbeitung; `mintpdf.py` enthält GTK,
Sprachen und Einstellungen. `resources/` enthält die 3D-Icons.
`python3 build.py` erstellt bereinigte Pakete ohne Logs, Konfigurationen,
Entwicklungsdateien und private Startdatei. Bytecode mit Python 3.12 erstellen.
Die Quellen und Buildinformationen liegen im Quellcodepaket bei.
Fremde Programme/Bibliotheken sind eigenständige Komponenten unter ihren
jeweiligen Lizenzen und werden nicht in diesen Paketen mitgeliefert.

Beim Start wird das eigene Sitzungslog geleert. Unter **Bearbeiten → Logs anzeigen** lässt es sich schreibgeschützt öffnen und aktualisieren.


## PDF bearbeiten

PDF auswählen: LibreOffice Draw öffnet das Dokument direkt. Es erscheint weder
„Fertigstellen“ noch eine Meldung zum Start des externen Programms.
Texte, Bilder und Zeichnungsobjekte werden in Draw bearbeitet. Für eine neue PDF
in Draw **Datei → Exportieren als → Als PDF exportieren** verwenden und den
gewünschten Ausgabeordner wählen (zum Beispiel Downloads). Die mintPDF-Einstellung
für den Ausgabeordner wird nicht auf die externen Draw-Dialoge übertragen.
Der interne Editor wird nicht mehr aufgerufen. Bei fehlendem LibreOffice ist die
Kachel ausgegraut; das Log nennt `sudo apt install libreoffice`.
Auch `python3 mintpdf.py --tool edit --input datei.pdf` öffnet Draw direkt.

Fehlende Laufzeitmodule und Programme erscheinen beim Start mit **E_DEP** und
Installationsvorschlägen in `logs/mintpdf.log`. Diese Befehle werden nur angezeigt,
nicht automatisch ausgeführt. apt-Pakete hängen von den eingerichteten Mint-
Paketquellen ab. PyMuPDF wird mit dem mitgelieferten Einrichtungsskript in einer
virtuellen Umgebung installiert. Nach Installation mintPDF neu starten.


## Formular aus Muster erstellen

Die neue Kachel und der Menüeintrag öffnen zuerst eine PDF-Dateiauswahl. Danach
entscheidet eine automatische Prüfung, ob eine ausfüllbare PDF erzeugt werden kann:

- Bereits vorhandene Formularfelder: unverändert erhalten, keine doppelten Felder.
- Erkennbare Muster: beschriftete kleine Rechtecke werden Ankreuzkästchen;
  Punkt-/Unterstrichzeilen und klar beschriftete Linien/Textboxen werden Textfelder.
- Keine sicheren Kandidaten: verständlicher Hinweis statt einer vermeintlichen
  erfolgreichen Umwandlung. Scans werden nicht automatisch erkannt.

Die Analyse nennt Feldzahlen und Seiten ohne erkannte Felder. Fertigstellen erzeugt
eine neue PDF im eingestellten Ausgabeordner. Das sichtbare Layout bleibt erhalten:
transparente Felder, keine zusätzlichen Rahmen, automatische Schriftgröße.
Neu erzeugte Kästchen sind unabhängig; bestehende Ja/Nein-Gruppen bleiben erhalten.
Die geometrische Erkennung ist konservativ, aber keine Garantie für vollständige
oder semantisch richtige Erkennung. Ergebnis im Formularbetrachter prüfen.
Zum Ausfüllen die Datei in Xreader oder einem anderen PDF-Formularbetrachter öffnen.
„PDF bearbeiten“ bleibt der getrennte Aufruf von LibreOffice Draw.

CLI: `python3 mintpdf.py --tool form --input muster.pdf --output formular.pdf`.
`core.py` enthält Erkennung und Erstellung; die Originaldatei wird nie verändert.

## Passwortschutz entfernen

Nach der PDF-Auswahl wird die Verschlüsselung geprüft. Ungeschützte Dateien
benötigen kein Passwort. Bei ohne Öffnungspasswort lesbaren PDFs können
Berechtigungsbeschränkungen ohne Passwort entfernt oder ein bekanntes Passwort
verwendet werden. Eine PDF mit Öffnungssperre benötigt ein gültiges Öffnungs- oder
Eigentümerpasswort. Keine Passwortsuche oder Umgehung unbekannter Öffnungspasswörter.
Ausgabe als neue unverschlüsselte Datei; Formulare, Lesezeichen und Metadaten bleiben
erhalten. Passwörter werden weder gespeichert noch protokolliert.

## Visuell schwärzen

PDF schwärzen öffnet nach der Dateiauswahl direkt die PDF-Vorschau. Bereiche
mit der Maus aufziehen, Seiten wechseln und bei Bedarf Rückgängig/Wiederholen
verwenden. „Schwärzen und speichern“ schreibt eine neue PDF in den gewählten
Ausgabeordner. Entfernt werden Text, Bildpixel und berührte Vektorgrafiken im
markierten Bereich sowie dortige Formularfelder und Anmerkungen. Metadaten und
Dateianhänge werden aus der Ausgabe entfernt. Originale bleiben unverändert.
Unmarkierte Vorkommen derselben Inhalte an anderen Stellen bleiben erhalten.
Die Vorschau zeigt Markierungen; dauerhaft entfernt sind Inhalte erst in der
gespeicherten Ausgabe. Für die Vorschau werden python3-cairo und python3-gi-cairo
benötigt. Die bestehende CLI-Textschwärzung bleibt verfügbar.

### PDF optimieren
Nach der Dateiauswahl erscheinen eine Analyse und passende Optimierungsoptionen. Struktur und Daten werden standardmäßig verlustfrei komprimiert; Formularfelder, Lesezeichen, Kommentare, Metadaten und Anhänge bleiben erhalten. Schriftuntergruppen und das Entfernen von Metadaten/Anhängen sind optional. CLI: `--opt-structure 0|1|3|4`, `--no-opt-compress`, `--no-opt-images`, `--no-opt-font-compress`, `--opt-fonts`, `--opt-metadata`, `--opt-attachments`.

### Mehrere Funktionen
Über Datei → Mehrere Funktionen eine PDF einmal auswählen. Funktionen hinzufügen (auch mehrfach), die Reihenfolge mit Nach oben/unten festlegen und Ablauf starten. Jeder Schritt zeigt seine Optionen; nach Fertigstellen wird seine gespeicherte Ausgabe automatisch zum nächsten Schritt weitergegeben. Zwischenergebnisse bleiben erhalten. Beim Schließen eines Schritts endet der Ablauf. Externe Editoren, visuelles Schwärzen, ZIP-Ausgaben und Mehrdatei-Funktionen werden separat gestartet. Verschlüsselung als letzten Schritt einplanen.

### PDF-Vergleich ab 1.11.0
Zwei PDFs im Vergleichsfenster auswählen. Automatisch wählt bei vorhandenem Text „Text + optisch“, sonst „Optisch“. Zusätzlich sind Text, Optisch und Technisch einzeln auswählbar. Die Übersicht zählt Seiten, zusammenhängende Textänderungen und optische Rasterbereiche. Nebeneinander, farbige Differenzansicht und Bericht zeigen Details; Datei → Bericht speichern exportiert UTF-8-Text. Nicht geprüfte Kategorien werden nicht als Null ausgegeben. Technisch prüft ausgewählte Merkmale statt sämtlicher PDF-Objekte. OCR wird nicht durchgeführt. Bei stark umgebauten Dokumenten ist die heuristische Seitenzuordnung zu kontrollieren. Die CLI-Funktion compare behält ihren bisherigen PDF-Sichtvergleich bei.


## Startseite ab 1.12.0

Start im Arbeitsordner mit `./.start.sh`. Alle 32 Werkzeuge stehen in einem durchgehenden Kachelraster ohne Gruppenüberschriften. Suche: Strg+F. Kacheln und Menü verwenden dieselben Namen und Zustände. Fehlende Voraussetzungen werden unter der Kachel erklärt; die Prüfung erfolgt im Hintergrund sowie vor Verarbeitung. Jede Kachel besitzt eine eigene Überschrift in der DE/EN-Hilfe. Bild / Unterschrift einfügen erzeugt eine sichtbare Bildunterschrift, keine kryptografische Signatur.

## Arbeitsstand 1.12.1

Die Laufzeit besteht aus zwei Python-Dateien: `mintpdf.py` für Oberfläche,
Menü und Arbeitsfenster; `core.py` für Funktionsdefinitionen und Verarbeitung.
Die bisherigen Formular-, Optimierungs-, Vergleichs- und Schwärzungsfunktionen
sind darin enthalten. Optionale Bibliotheken werden erst bei Bedarf importiert.
`build.py` und `install.py` bleiben als getrennte Wartungswerkzeuge bestehen;
Prüfungen liegen unter `tests/`. Der nicht verwendete alte Editor wird nicht
mitgeführt; seine unveränderten Quellen bleiben im bestätigten Archivbestand.

Menü: Datei / Werkzeuge / Hilfe. Datei enthält Mehrere Funktionen, Ausgabeordner
und Einstellungen, danach eine Trennlinie und Beenden. Werkzeuge enthält die
acht Funktionsgruppen. Hilfe enthält Hilfe (F1), Protokoll, Info und Über.

24 passende Kachelbilder aus `/home/josef/Bilder` wurden visuell geprüft und
unverändert in `resources/` übernommen. Bildquellen: `resources/BILDQUELLEN.json`.
Alle sichtbaren Werkzeugkacheln verwenden PNG-Icons aus der einheitlichen 3D-Kollektion. Die
Verfügbarkeit einer Funktion hängt weiterhin von ihrer Implementierung und
ihren Voraussetzungen ab. Programmsymbol: das ausdrücklich von Josef gewählte
`mintpdf.png`; das Wolf-und-D-Wasserzeichen bleibt davon getrennt.


### Hilfe → Info
Die Werkzeugübersicht zeigt Verfügbarkeit, Version und APT-Paketnamen der
tatsächlichen Abhängigkeiten aus projekt.json. Optionale Werkzeuge und ihre
Funktionen sind gekennzeichnet. Die Prüfung läuft im Hintergrund; Schließen
bleibt bedienbar. Es erfolgt keine Installation. Über bleibt ein eigener Dialog.

## PDF-Seiten zuschneiden (1.13.0)

PDF auswählen und im Vorschaufenster einen Rahmen um den Bereich ziehen, der bleiben soll. Abgedunkelte Ränder werden ausgeblendet. Links, rechts, oben und unten lassen sich auch in Millimetern einstellen. Das Seitenmenü wechselt zwischen Seiten; jeder Zuschnitt bleibt erhalten. Bearbeiten überträgt den proportionalen Rahmen auf alle Seiten oder setzt die aktuelle Seite zurück. Datei → Zuschnitt als neue PDF speichern erzeugt eine neue Datei. Originale und vorhandene Ziele werden nicht überschrieben. Inhalte außerhalb des Rahmens bleiben technisch in der PDF; vertrauliche Inhalte mit PDF schwärzen entfernen.

## Bilder in PDF (1.15.0)

Zuerst die vorhandene PDF auswählen, danach die einzufügenden Bilder. Die Vorschau zeigt den PDF-Inhalt und alle eingefügten Bilder. Für jedes Bild PDF-Zielseite, Abstand links/oben und Breite einstellen. Über das Seitenmenü zwischen den Bildern wechseln. Datei → Speichern erzeugt eine neue PDF; Originale bleiben erhalten. Die CLI ohne Platzierungsoptionen behält die bisherige Konvertierung bei.

Bild direkt verschieben: Das blau umrahmte aktuelle Bild in der Vorschau mit gedrückter linker Maustaste ziehen. Die Positionswerte folgen automatisch; das Bild bleibt innerhalb der PDF-Seite. Andere Bilder über das Seitenmenü auswählen.

Bildgröße ändern: An einem der vier Eckpunkte des blauen Rahmens ziehen. Das Seitenverhältnis bleibt erhalten. Alternativ die Bildbreite in Millimetern eingeben.

## Bilder gezielt extrahieren (1.16.0)

Bilder extrahieren: PDF auswählen, gewünschte Bilder in der Vorschau mit einem Häkchen markieren, dann Datei → Speichern. Nur die gewählten Bilder werden in einer neuen ZIP-Datei gespeichert. Bearbeiten bietet Alle auswählen und Auswahl aufheben. Wiederverwendete Bilder erscheinen einmal mit allen Seitenfundstellen. Die Original-PDF bleibt erhalten. Die Übersicht zeigt eingebettete Bildobjekte; für komplette Seiten PDF in Bilder verwenden.


Bildgröße innerhalb einer PDF ändern: „Bilder in PDF“ öffnen, zuerst PDF und danach Bild auswählen. In der Vorschau an den vier Eckpunkten ziehen oder Bildbreite in Millimetern eingeben. Die eigene Kachel „Bildgröße und Position ändern“ bearbeitet vorhandene PDF-Bilder.

## Vorhandene PDF-Bilder bearbeiten (1.18.0)

Bildgröße und Position ändern: PDF auswählen. Vorhandenes Bild anklicken oder über das Seitenmenü wählen. Ziehen verschiebt das Bild, Eckpunkte ändern die Größe proportional. Millimeterwerte sind ebenfalls einstellbar. Datei → Speichern erzeugt eine neue PDF. Überlappende, gedrehte oder komplex eingebettete Bildobjekte und offene Schwärzungen werden abgewiesen. Für neue Bilder weiterhin Bilder in PDF verwenden.

Vorhandene PDF-Bilder: „PDF-Seite anzeigen“ und das Seitenmenü blättern ohne Bildverschiebung. Dabei wird die Auswahl aufgehoben. Klick auf freie Fläche wählt ebenfalls ab; Bild anklicken wählt erneut aus.

## Bild in PDF drehen (1.19.0)

PDF auswählen, vorhandenes Bild anklicken. Bearbeiten → Bild 90° nach links/rechts drehen. Position und Größe sind weiter einstellbar. Datei → Speichern erzeugt eine neue PDF. Passt das gedrehte Bild nicht auf die Seite, zuerst verkleinern.

## Bildzuschnitt (1.20.0)

Bild in PDF zuschneiden: PDF auswählen, Bild anklicken und einen Rahmen um den verbleibenden Bereich ziehen. Dunkle Ränder werden abgeschnitten. Bearbeiten → Bildzuschnitt übernehmen wendet den Ausschnitt an. Datei → Speichern übernimmt auch den aktuellen Rahmen und erstellt eine neue PDF. Rahmen zurücksetzen verwirft nur einen noch nicht übernommenen Rahmen. Original bleibt erhalten.

Zuschnitt feinjustieren: Grüne Ecken oder Kantenpunkte ziehen, innerhalb des Rahmens ziehen zum Verschieben. Randwerte in Millimetern einstellen. Zoom 100–400 % vergrößert die Vorschau; Bildgröße und Ausgabe bleiben davon unberührt. Erst Übernehmen oder Speichern wendet den Zuschnitt an.

## Textsuche (1.34.6)

Text suchen: PDF auswählen und Suchtext eingeben. Trefferseiten erscheinen links; eine Seite anklicken zeigt gelbe Fundstellen in der Vorschau. Die PDF bleibt unverändert. Suche nutzt vorhandenen PDF-Text, bei reinen Scans zuerst Text per OCR erkennen ausführen. Fundstellen zählen Textrechtecke; bei Zeilenumbrüchen kann ein Suchausdruck mehrere Rechtecke ergeben.

Webseite in PDF: zuerst eine lokale HTML-/HTM-Datei auswählen, danach das PDF-Ziel.

PDF/A erzeugen erstellt PDF/A-2b mit Ghostscript und eingebettetem sRGB-Profil. Erkannte Unverträglichkeiten brechen die Verarbeitung ab. Die Konformität wird vor dem Speichern automatisch mit veraPDF geprüft.

PDF/A-Konformität: Nach der Erzeugung prüft veraPDF CLI ausdrücklich das Profil PDF/A-2b. Nur bei vollständigem, positivem Prüfbericht wird die neue PDF gespeichert. Ohne veraPDF bleibt die Funktion deaktiviert; Java wird vom Validator benötigt. Einrichtung: https://docs.verapdf.org/install/

PDF/A prüfen validiert vorhandene PDFs ohne Änderung mit automatisch erkanntem Profil. Ohne gültige PDF/A-Angabe verwendet veraPDF PDF/A-1b.

PDF/A-Erzeugung normalisiert Überdruckmodus 1 für die RGB-Archivkopie zu Modus 0 und setzt Anmerkungen druckbar. Links bleiben erhalten; das Original bleibt unverändert. Die Druckdarstellung kann sich ändern.

Dokumenteninformationen liest Dateieigenschaften, Seitenmaße, Metadaten und Objektanzahlen ohne Änderung der PDF. Datumswerte werden lokal für Europe/Berlin angezeigt.
