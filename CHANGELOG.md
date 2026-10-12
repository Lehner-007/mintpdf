## 1.39.2

- Beim Überlagern Metadaten, Lesezeichen und eingebettete Dateien von PDF 1 erhalten; PDF 2 liefert ausschließlich Seiteninhalt.
- Backend-Regression für den echten Export ergänzt; PDF/A-Integration kennzeichnet fehlende Voraussetzungen.
- Testmodule für unabhängige GTK-Lebenszyklen in getrennten Prozessen ausführbar.

## 1.39.1

- Suchleiste mittig auf halbe verfügbare Breite begrenzt.
- Zentrierte Überschrift „mintPDF Tools“ und kurzer Einführungstext ergänzt.

## 1.39.0

- Ausgabeordner, Sprache und Hilfedownload in einem scrollbareren Einstellungsdialog mit sichtbaren Trennlinien zusammengefasst.
- Gemeinsames atomisches Speichern und Abbrechen ohne Übernahme.
- Werkzeugsuche beschriftet und Filter unmittelbar an Texteingabe angebunden.

## 1.38.0

- Werkzeugkacheln als durchgehendes Raster ohne Gruppenüberschriften angeordnet.
- Hilfe in DE/EN mit eigener Überschrift für jede der 32 Kacheln neu gegliedert.
- Ungenutzte Xournal++-Abhängigkeit und alte CLI-Aktion entfernt.

## 1.37.2

- Infofenster erkennt die benutzerlokale veraPDF-Installation wie die PDF/A-Funktionen und zeigt deren Version an.

## 1.37.1

- Alle 32 sichtbaren Werkzeug-Icons kontrolliert.
- Anmerkungen, PDF/A-Erzeugung, PDF/A-Prüfung und Dokumenteninformationen an die vorhandene 3D-Kollektion angeglichen.

## 1.37.0

- Dokumenteninformationen mit eigenem Icon und lesender, scrollbarerer Übersicht ergänzt.
- PDF-Eigenschaften, Metadaten, lokale Datumsanzeige und Objektanzahlen anzeigen.

## 1.36.1

- PDF/A: Überdruckmodus und Anmerkungs-Druckflags in einer privaten Kopie normalisieren; Links erhalten.
- Strikte Ghostscript-Konvertierung und veraPDF-Prüfung bleiben aktiv.
- Werkzeugfehler mit Diagnose im Protokoll erfassen.

## 1.36.0

- Vorhandene PDFs über „PDF/A prüfen“ ohne Veränderung validieren.
- PDF/A-Ausgaben vor dem Speichern mit veraPDF gegen PDF/A-2b prüfen.
- Fehlende, fehlerhafte oder negative Validierung verhindert die Ausgabe.
- Erfolgsmeldung bestätigt die bestandene Konformitätsprüfung.

## 1.35.1

- Dateiauswahl: Dateien ohne lokalen Gio-Pfad als temporäre Arbeitskopie übernehmen; Fehler des Speicherorts verständlich melden.
- Folgedialog erst nach Abbau des nativen Dateidialogs öffnen.

## 1.35.0

- PDF/A-2b-Erzeugung mit Ghostscript, eingebettetem Farbprofil und Abbruch bei erkannten Unverträglichkeiten.
- Eigene Icons für Formular aus Muster und PDF/A.

## 1.34.6 — 11.10.2026

- Webseite in PDF: zuerst HTML-/HTM-Quelldatei statt PDF-Ziel wählen; lokale Begleitdateien aus dem Quellordner zulassen, JavaScript deaktivieren.

## 1.34.5 — 11.10.2026

- Wolf-und-D-Wasserzeichen im Hauptfenster ergänzt, ohne Maus- oder Tastaturbedienung zu blockieren. Vorhandene Funktion Webseite in PDF mit wkhtmltopdf nutzbar.

## 1.34.4 — 11.10.2026

- HTML mit eingebetteter gerenderter PDF-Seite, auswählbarer Textebene und klickbaren Linkflächen ausgeben, damit Seiteninhalt einschließlich Scans zuverlässig sichtbar bleibt.

## 1.34.3 — 11.10.2026

- Fehlende HTML-Seitenpositionierung ergänzt: Linkflächen beziehen sich auf ihre PDF-Seite; Text und Bilder verwenden die exportierten Koordinaten.

## 1.34.2 — 11.10.2026

- Originale Linkflächen im HTML anklickbar machen; ODT-Linktexte direkt verknüpfen und blau unterstreichen.

## 1.34.1 — 11.10.2026

- PDF-Linkannotationen beim HTML-/ODT-Export als klickbare, sichtbare Linkliste je Seite übernehmen, einschließlich interner Seitenziele.

## 1.34.0 — 11.10.2026

- Gemeinsame PDF-Konvertierung nach TXT/HTML/ODT/PNG/JPG. Doppelte Kacheln Textextraktion und PDF in Bilder entfernt; eingebettete Bilder weiterhin separat extrahierbar.
- ODT als bearbeitbarer Textexport mit Seitenumbrüchen; keine Layoutrekonstruktion.

## 1.33.0 — 11.10.2026

- PDF-Seiteneditor mit Textfeldern, Bildern, Auswahl, Verschieben/Skalieren per Maus, mehreren Seiten, Format, Hintergrund, Seitenzahlen und Wasserzeichen. Gemeinsamer Renderer für Vorschau und Export.

## 1.32.2 — 11.10.2026

- Linke Einstellungen der PDF-Überlagerung auf 400 logische Pixel fixiert; nur die Vorschau wächst mit dem Fenster.

## 1.32.1 — 11.10.2026

- Vorhandene Ausgabeziele verständlich melden; Warnungen für entfernte Xournal++-Funktion nicht mehr beim Start anzeigen.

## 1.32.0 — 11.10.2026

- PDF-Überlagerung mit beiden Originalansichten und Ergebnisvorschau, Ebenenwechsel, Seitenzuordnung/-auswahl, Deckkraft, Position, Größe und Drehung.

## 1.31.0 — 11.10.2026

- Gemeinsame Funktion Bild / Unterschrift einfügen mit Auswahlrahmen, Drag-and-drop und Eckgriffen. Doppelte Unterschriftskacheln entfernt; bisherige Backend-Funktionen für vorhandene Aufrufe erhalten.

## 1.30.0 — 11.10.2026

- Unterschrift mit sichtbarem Auswahlrahmen und vier Eckgriffen proportional vergrößern/verkleinern. Klick außerhalb hebt die Auswahl auf.

## 1.29.1 — 11.10.2026

- Unterschrift beim Greifen ohne Positionssprung verschieben; laufende Vorschauupdates statt verzögerter Aktualisierung erst nach Bewegungsende.
- Versteckter Projektstarter .start.sh mit Icon-Verknüpfung.

## 1.29.0 — 11.10.2026

- Unterschriftsbild mit eigenem Icon, Live-Vorschau und Mauspositionierung.
- Backend-/GUI-Abhängigkeiten getrennt, Anmerkungsseiten validiert und veralteten Test korrigiert.
- Allgemeine Verarbeitung mit kooperativem Abbruch und kontrolliertem Beenden externer Prozessgruppen.

## 1.28.0 — 11.10.2026

- Anmerkungen in der PDF-Vorschau per Mausklick platzieren und per Drag-and-drop verschieben; Skalierung und Seitenränder berücksichtigen.

## 1.27.0 — 11.10.2026

- Anmerkungen hinzufügen mit eigenem Icon, PDF-Live-Vorschau, Seiten- und Positionswahl.

## 1.26.0 — 11.10.2026

- Seitenzahlen mit Live-Vorschau, Position und Textvorlage Seite ##.

## 1.25.0 — 11.10.2026

- Wasserzeichen-Einstellungen und Live-PDF-Vorschau nebeneinander; Seitenwahl und Export mit identischer Darstellung.

## 1.24.0 — 11.10.2026

- Wasserzeichen diagonal über die Seite; Einstellungen für Winkel, Textgröße, Farbe und Deckkraft. Langer Text passt sich automatisch an.

## 1.23.0 — 11.10.2026

- Text extrahieren mit eigenem Symbol und sicherem UTF-8-TXT-Export ergänzt.
- Textsuche mit verschiebbarer Aufteilung: Treffer links, PDF rechts (Startverhältnis 1:2).

## 1.22.0 — 11.10.2026

- Text suchen mit 3D-Icon, Trefferseitenliste und gelber Markierung in der PDF-Vorschau.
- Hintergrundsuche verwirft veraltete Ergebnisse, Original bleibt unverändert. Hinweis auf OCR bei Scans ohne Textebene.

## 1.21.0 — 11.10.2026

- Bildzuschnitt nachbearbeiten: acht Griffpunkte, Rahmen verschieben, genaue Millimeterränder.
- Vorschau-Zoom 100 bis 400 Prozent ohne Veränderung der Exportgeometrie.

## 1.20.0 — 11.10.2026

- Bild in PDF zuschneiden mit 3D-Icon, sichtbarem Rahmen und abgedunkelten Rändern.
- Gewählten Bildausschnitt übernehmen und in neuer PDF speichern; andere PDF-Inhalte erhalten.

## 1.19.0 — 11.10.2026

- Neues 3D-Icon für Bildgröße und Position ändern.
- Bild in PDF drehen als eigene Kachel: vorhandenes Bild auswählen, 90° links/rechts drehen, neue PDF speichern. Auch im Bildeditor unter Bearbeiten verfügbar.

## 1.18.1 — 11.10.2026

- Vorhandene PDF-Bilder: Seitenwechsel ändert nur die Ansicht und verschiebt kein Bild.
- Auswahl beim Blättern und per Klick auf freie Fläche aufheben. Ohne Auswahl sind Bildmaße gesperrt.

## 1.18.0 — 11.10.2026

- Eigene PDF-Funktion Bildgröße und Position ändern: vorhandene Bilder auswählen, verschieben und skalieren.
- PDF-Inhalte bleiben in der Vorschau sichtbar. Neue PDF speichern; Original bleibt erhalten.
- Überlappende, gedrehte/komplexe Bildobjekte und offene Schwärzungen werden sicher abgewiesen.

## 1.17.1 — 11.10.2026

- Separate Bildgrößenfunktion entfernt. Bildgröße weiterhin direkt innerhalb der PDF-Vorschau über Eckpunkte und Millimeterwerte ändern.
- Einheitliche Kachelgrößen bleiben erhalten.

## 1.17.0 — 11.10.2026

- Einheitliche Kachelgröße über alle Funktionsgruppen.
- Bildgröße ändern mit Pixelmaßen, optionaler Seitenverhältnissperre, Vorschau und geschütztem PNG-Export.

## 1.16.0 — 11.10.2026

- Bilder extrahieren mit Vorschau, Seitenfundstellen, Auflösung und individueller Auswahl.
- Alle auswählen/Auswahl aufheben; nur ausgewählte Bilder in neuer ZIP speichern. Mehrfach verwendete Bildobjekte einmal anzeigen und exportieren.
- Analyse im Hintergrund; Original-PDF bleibt erhalten.

## 1.15.2 — 11.10.2026

- Vier sichtbare Eckpunkte zur proportionalen Größenänderung von Bildern in der PDF-Vorschau.
- Gegenüberliegende Ecke bleibt fest; Seitengrenzen begrenzen die Größe. Bildbreite in Millimetern folgt automatisch.

## 1.15.1 — 11.10.2026

- Bildplatzierung durch Ziehen in der PDF-Vorschau. Blauer Rahmen kennzeichnet das aktuelle Bild.
- Millimeterwerte folgen der Maus; Seitengrenzen verhindern ein Verschieben aus der Seite. Während des Speicherns ist Verschieben gesperrt.

## 1.15.0 — 11.10.2026

- Dateiauswahl benennt benötigte Dateitypen; Speicherziele nennen das Ausgabeformat.
- Bilder in PDF: zuerst vorhandene PDF, dann Bilder auswählen. Vorschau zeigt PDF-Inhalt und alle eingefügten Bilder.
- PDF-Zielseite je Bild, positionsgetreuer Export als neue PDF; Originale erhalten.

## 1.14.0 — 11.10.2026

- 3D-Kachelbild für PDF-Seiten zuschneiden.
- Bilder in PDF mit A4-Vorschau pro Bild, Position und Breite in Millimetern bei erhaltenem Seitenverhältnis.
- Vorschau und Export verwenden dieselbe Geometrie und dieselben Bilddaten. Außerhalb der Seite liegende Bilder verhindern das Speichern.

## 1.13.0 — 11.10.2026

- PDF-Seiten zuschneiden mit sichtbarem Rahmen, abgedunkelten Rändern, Zoom und Millimeterwerten.
- Zuschnitt je Seite, Zurücksetzen und proportionale Übertragung auf alle Seiten.
- Neue PDF atomar speichern; Original und vorhandene Ziele erhalten. Gedrehte und bereits zugeschnittene Seiten geprüft.

## 1.12.4 — 11.10.2026

- Zielauswahl auf asynchrone GTK-Dateiauswahl umgestellt; Startordner wird auf Existenz geprüft.
- Abbrechen bleibt ohne Fehlerdialog und erhält das vorhandene Ziel.
- Keine Verarbeitung oder Speicherung allein durch Auswahl eines Ziels.

## 1.12.3 — 11.10.2026

- Hilfe → Info als gemeinsame Werkzeugübersicht mit Infosymbol, Status, Version, APT-Paket und optionalen Funktionshinweisen.
- Prüfung im Hintergrund, scrollbare Liste und jederzeit erreichbares Schließen.
- Tatsächliche Abhängigkeiten in projekt.json konfiguriert; Über bleibt getrennt.

## 1.12.2 — 11.10.2026

- Menü mit Checkweb, Showipmac, Saveconfig, Pcmonitor und gemeinsamer Vorlage abgeglichen.
- Einstellungen als eigener Abschnitt zwischen zwei sichtbaren Trennlinien vor Beenden.
- Hilfe → Hilfe / Protokoll / Info / Über; Infosymbol ergänzt, Beschriftungen DE/EN vereinheitlicht.
- Strg+Q für Beenden; F1 für Hilfe erhalten.

## 1.12.1 — 11.10.2026

- 24 passende Kachelbilder aus Josefs vorhandenem Bilderbestand eingebunden.
- mintpdf.png als ausdrücklich gewähltes Programmsymbol und Über-Logo verwendet.
- Laufzeit auf mintpdf.py (GUI) und core.py (Katalog/Verarbeitung) zusammengefasst; optionale Bibliotheken weiterhin verzögert geladen.
- Datei/Werkzeuge/Hilfe; Einstellungen unter Datei vor Trennlinie/Beenden, Protokoll unter Hilfe, F1 öffnet Hilfe.
- Bestehende Start-/Installationsvorbereitung und Dokumentation auf die zwei Laufzeitdateien angepasst.

## 1.12.0 — 11.10.2026

- Startseite und Werkzeugmenü mit acht gemeinsamen Gruppen und Suche.
- Zentraler Funktionskatalog, sichtbare Gründe für gesperrte Funktionen und erneute Prüfung vor Ausführung.
- 25 vorhandene Funktionen erhalten; zehn geplante Funktionen sichtbar und gesperrt.
- Hintergrundprüfung, Verarbeitungssperre, Tastaturzugang zur Suche, eigene CC0-Gruppenicons.
- Bestehende Fremdprogramme nicht eingebettet; keine zusätzlichen Qt-/GTK3-Abhängigkeiten.

## 1.11.0
- Neuer PDF-Vergleich mit zwei Dateiauswahlen, fünf Modi, Seitenzuordnung, Kennzahlen, Nebeneinander-/Differenzansicht und exportierbarem Textbericht.

## 1.10.0
- Mehrere Funktionen als geordnete Folge auswählen; dieselbe Funktion mehrfach hinzufügen. Jede Folge-PDF wird automatisch weitergereicht, Zwischenergebnisse bleiben erhalten.

## 1.9.0
- PDF optimieren analysiert die gewählte Datei und zeigt passende Optionen für Struktur, Daten-, Bild- und Schriftkompression, Schriftuntergruppen, Metadaten und Anhänge.
- Nicht anwendbare Optionen sind ausgegraut. Formularfelder, Lesezeichen und Anmerkungen bleiben bei der Standardoptimierung erhalten.

# Änderungen

## 1.8.0

- PDF schwärzen öffnet direkt eine Seitenvorschau.
- Bereiche per Maus markieren, Zoom, Seitenwechsel und Rückgängig/Wiederholen.
- Echte Entfernung markierter Inhalte bei Ausgabe in eine neue PDF.

## 1.7.0

- Passwortschutz vorab prüfen und passende Optionen anbieten.
- Öffnungspasswort und ohne Passwort lesbaren Eigentümerschutz unterscheiden.
- Entschlüsselung erhält Formulare, Lesezeichen und Dokumentmetadaten.

## 1.6.0

- Formular aus Muster erstellen als 25. Funktion mit neuem 3D-Icon.
- Automatische Eignungsprüfung, Erhalt bestehender Formularfelder und transparente neue Text-/Ankreuzfelder.
- Unklare Muster werden mit Erklärung abgelehnt, Layout und Original bleiben erhalten.

## 1.5.0

- PDF bearbeiten wieder mit LibreOffice Draw.
- Direkter Start nach Dateiauswahl, ohne Zwischenfenster oder Startbestätigung.
- Abhängigkeitserkennung und Installationsvorschlag auf LibreOffice umgestellt.

## 1.4.2

- Leere Texte und ungültige Schriftgrößen im Editor mit konkreter Abhilfe melden. Texteingabefeld eindeutig beschriften.

## 1.4.1

- PDF-Editor: Dateiauswahl vor dem Öffnen vollständig schließen; Speicherdialog vor der Ausgabe schließen. Verbliebene Dateidialoge beim Beenden aufräumen.

## 1.4.0

- Eigener GTK-4-Inhaltseditor statt externem LibreOffice-Aufruf.
- Textauswahl/-ersetzung, neue Texte, Schriftart, Größe und Farbe.
- Bilder einfügen, verschieben, skalieren und entfernen.
- Linien, Rechtecke, Kreise/Ellipsen, Freihand, Markierungen und Notizen.
- Links hinzufügen/bearbeiten, einzelne Seiten zuschneiden, Rückgängig/Wiederholen.
- Sichere Ausgabe in neue Dateien; Originale bleiben erhalten.
- Fehlende Abhängigkeiten beim Start mit Installationsvorschlag protokollieren.

## 1.3.1

- Fest zugeordnete Programme sachlich benennen statt ohne Programmauswahl eine Empfehlung anzuzeigen.

## 1.3.0

- Sitzungslog beim Start leeren; Bearbeiten → Logs anzeigen mit Aktualisieren.
- Alle 24 Kacheln bleiben sichtbar; fehlende Funktionen ausgegraut mit Hinweis.
- Jede Funktion beginnt mit passender Datei- oder Ausgabeauswahl.
- Einheitlicher Ablauf: Dateien wählen, Optionen festlegen, Fertigstellen.
- Ghostscript-Kompressionsprofile und umfangreiche OCRmyPDF-Optionen.
- Installierte OCR-Sprachen und Tesseract-Abhängigkeit erkennen.
- PNG-Exportauflösung wählbar.

## 1.2.0
- Bearbeiten → Standard-Ausgabeordner mit dauerhafter Speicherung.
- PDF trennen beginnt direkt mit einer PDF-Dateiauswahl.
- Vier Trennarten mit Vorschau, Eingabeprüfung und Fertigstellen.
- Trennarten auch per Kommandozeile verfügbar.

## 1.1.0
- PDF-Auswahl direkt beim Aufruf von Zusammenführen.
- Eigenes Reihenfolgefenster mit Verschieben, Hinzufügen, Entfernen und Fertigstellen.
- Downloads als Standard-Ausgabeordner; freie Dateinamen vorschlagen.
- Klassische GTK-Menüleiste.

## 1.0.0
- Neue GTK-4-Oberfläche mit 24 PDF-Aktionen und Funktionskacheln.
- Eigenes 3D-Programmsymbol und passende Funktionssymbole.
- Gemeinsame Aktionen für Kacheln und Menü; fehlende Werkzeugkacheln ausblenden.
- Deutsche/englische Oberfläche, dynamische Sprachen und HTML-Hilfe.
- Sichere neue Ausgaben, Hintergrundverarbeitung, CLI und Fehlerprotokoll.
