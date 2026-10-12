# mintPDF richtig prüfen

Diese Anleitung gilt für `/home/josef/Labor/Python/mintpdf` und weitergegebene Projektkopien. Testanleitung und Voraussetzungsliste befinden sich zusätzlich unter `tests/README.md` und `tests/test_requirements.json`.

## 1. Prüfumgebung festhalten

Im Projektordner arbeiten. Unter Linux Mint die vorgesehene Projektumgebung verwenden:

```bash
cd /home/josef/Labor/Python/mintpdf
.venv/bin/python --version
.venv/bin/python -c "import core, pymupdf; print('mintPDF', core.VERSION); print('PyMuPDF', pymupdf.VersionBind); print('PDF/A fehlt:', core.missing_tools('pdfa'))"
```

Vorgesehen ist PyMuPDF 1.28.2. Für die vollständige Prüfung werden GTK 4, PyGObject/gi, Cairo und eine erreichbare grafische Sitzung benötigt. LibreOffice, Ghostscript und veraPDF müssen für ihre Integrationstests verfügbar sein. Weitere Werkzeuge wie OCRmyPDF und Tesseract sind für entsprechende zusätzliche Prüfungen erforderlich.

Abweichungen und fehlende Werkzeuge im Prüfbericht nennen. Nichts allein für die Prüfung ungefragt installieren. Eine andere PyMuPDF-Version ist eine Prüfgrenze, kein Nachweis für die vorgesehene Umgebung.

## 2. Vollständigen isolierten Testlauf starten

```bash
.venv/bin/python tests/run_isolated.py > work/prueflauf.log 2>&1
pruefstatus=$?
cat work/prueflauf.log
printf 'Exitstatus: %s\n' "$pruefstatus"
```

`work` muss vorhanden und beschreibbar sein. In einer entpackten Kopie den Pfad entsprechend anpassen; nur bei Bedarf `mkdir -p work` im Projektordner ausführen.

**Den isolierten Starter verwenden.** Ein gemeinsamer `unittest discover`-Lauf über das gesamte Testverzeichnis ist kein Ersatz: Einige Skripte starten GTK-Anwendungen bereits beim Import. Mehrere GTK-Anwendungsläufe im selben Prozess können sich gegenseitig beeinflussen.

Der Starter führt jedes Modul in einem eigenen Prozess aus und verwendet dieselbe Python-Umgebung wie der Aufruf. Voraussetzungen sind ausdrücklich in `tests/test_requirements.json` definiert. Neue Tests dort eintragen; Voraussetzungen niemals aus bloßen Import-Textmustern ableiten.

## 3. Ergebnisse korrekt bewerten

| Status | Bedeutung |
| --- | --- |
| PASS/PASSED | Modul vollständig erfolgreich ausgeführt |
| PARTIAL | unittest-Modul enthält bestandene und übersprungene Testfälle |
| SKIP/SKIPPED | Modul oder alle seine Testfälle wegen fehlender Voraussetzung übersprungen |
| FAIL | Assertion, Werkzeugfehler, Importfehler, Absturz oder Testkonfiguration fehlgeschlagen |

Exitstatus 0 bedeutet: Kein ausgeführter Test ist fehlgeschlagen. **Er bedeutet bei Skips keine vollständige Integrationsprüfung.**

Module und unittest-Einzeltests getrennt zählen. Direkt ausführbare Skripte enthalten zusätzliche Assertions ohne Einzeltestzählung. Ganze wegen fehlender GUI-Voraussetzungen übersprungene Module werden nicht zusätzlich als übersprungene unittest-Einzeltests gezählt.

Kern-Konvertierungen in TXT/HTML/ODT/PNG/JPG laufen unabhängig von LibreOffice. Der separate LibreOffice-Roundtrip wird nur ohne LibreOffice übersprungen. PDF/A-Integration benötigt Ghostscript und veraPDF; die Prüfungen fehlender Abhängigkeiten und ungültiger Validatorberichte bleiben davon unabhängig.

## 4. Fehler gezielt nachprüfen

Direkt ausführbare GUI-Skripte einzeln starten:

```bash
PYTHONPATH=. .venv/bin/python tests/test_home.py
PYTHONPATH=. .venv/bin/python tests/test_settings_search_gui.py
```

unittest-Module gezielt starten:

```bash
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -p test_overlay_preservation.py
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -p test_conversion_libreoffice.py
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -p 'test_pdfa*.py'
```

Bei GUI-Problemen unterscheiden: tatsächlicher Anwendungsfehler, fehlende Voraussetzung oder fehlerhafte Teststeuerung. GTK-Schritte abhängig voneinander ausführen. Nach Sprachwechsel/Neuaufbau keine alten Menüobjekte verwenden. Auf beendete Hintergrundarbeit und tatsächlich zugeteilte Widgetgrößen mit begrenzter Wartefrist prüfen. Feste kurze Wartezeiten beweisen keine Bereitschaft. Assertions bei Zeitüberschreitung beibehalten; echte Fehler nicht durch Skips oder pauschales Abfangen verdecken.

Nach einer Korrektur zuerst betroffene Tests, anschließend den vollständigen isolierten Lauf ausführen.

## 5. Grenzen der automatischen Tests beachten

Für eine umfassende Freigabe zusätzliche reale Benutzer- und Integrationsprüfungen dokumentieren, soweit sie nicht bereits durch einen konkreten Test nachgewiesen sind:

- Deutsch/Englisch, helles/dunkles Theme, kleine/große Fenster, Fokus und Dialogbedienung.
- Vorschau und Export anhand geeigneter Beispieldateien vergleichen.
- Komplexe, gedrehte und gescannte PDFs sowie Links in den Konvertierungen prüfen; ODT tatsächlich in LibreOffice öffnen.
- Laufende OCR-/Ghostscript-Verarbeitung einschließlich Kindprozessen real abbrechen; anschließend prüfen, dass kein veröffentlichtes Ausgabeziel zurückbleibt.
- Originalbytes und Schutz vorhandener Ausgabeziele prüfen.

Nur Testkopien verwenden, persönliche Originale und vorhandene Ausgaben nicht überschreiben. Ein Overlay-Erhaltungstest für Metadaten, Lesezeichen und Anhänge beweist keine Gültigkeit digitaler Signaturen oder bestehender PDF/A-Konformität nach Bearbeitung. PDF/A bei Bedarf erneut validieren.

## 6. Prüfbericht und Abschluss

Einen Markdown-Prüfbericht im Projektordner ablegen. Er enthält:

1. Datum, tatsächliche Programmversion, Betriebssystem und Python-/PyMuPDF-Version.
2. Verfügbare und fehlende Werkzeuge, verwendete Befehle und Protokollpfade.
3. Bestandene, teilweise geprüfte, übersprungene und fehlgeschlagene Module sowie getrennte unittest-Zahlen.
4. Konkrete Fehler, Korrekturen, gezielte Nachtests und Ergebnis des Gesamtlaufs.
5. Offene Integrationsgrenzen und noch ausstehende Benutzerkontrolle.

Keine Freigabe aus einem eingeschränkten Teiltestlauf ableiten. Reine Test- oder Dokumentationsänderungen erhöhen die Anwendungsversion nicht. Eine Veröffentlichung oder Paketierung ist ein gesonderter Auftrag.
