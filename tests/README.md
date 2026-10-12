# mintPDF-Tests

Im Projektordner ausführen:

```sh
.venv/bin/python tests/run_isolated.py
```

Der Starter verwendet das aufrufende Python und startet jedes Testmodul in einem eigenen Prozess. Das ist für GTK erforderlich, weil mehrere Anwendungsläufe im selben Prozess einander beeinflussen können. `unittest discover` über das gesamte Verzeichnis ist daher kein Ersatz für diesen Lauf.

## Voraussetzungen

`test_requirements.json` deklariert jedes Modul ausdrücklich. Neue Module ohne Eintrag führen zu FAIL. Eine leere Liste kennzeichnet Tests ohne GTK/Gio-Voraussetzung. `gtk` verlangt GTK 4, gi, Cairo und eine erreichbare grafische Sitzung; `gio` verlangt gi/Gio ohne grafische Sitzung. Der Starter untersucht keine Import-Textmuster. Importierte Module und Zeichenketten mit Subprozess-Code bewirken keine impliziten Skips.

PDF/A-Integration entscheidet pro unittest-Testfall über Ghostscript/veraPDF/PyMuPDF. Die Abhängigkeitssperren werden unabhängig davon getestet. Die Kern-Konvertierung in `test_conversion.py` benötigt kein LibreOffice. `test_conversion_libreoffice.py` führt mit installiertem LibreOffice den echten ODT-Roundtrip aus; andernfalls wird genau dieser Integrationstest ausdrücklich übersprungen. Echte Werkzeug-/Assertionfehler werden nicht abgefangen.

## Ergebnisbewertung

- PASS: Modul erfolgreich, kein unittest-Test übersprungen.
- PARTIAL: unittest-Modul mit bestandenen und übersprungenen Testfällen.
- SKIPPED/SKIP: alle unittest-Testfälle beziehungsweise das gesamte Modul wegen fehlender Voraussetzung übersprungen.
- FAIL: fehlgeschlagene Assertion, Werkzeug-/Importfehler, Prozessabsturz oder fehlende Deklaration.

Die Zusammenfassung trennt Module nach Status und zählt unittest-Einzeltests separat. Direkt ausführbare Skripte besitzen zusätzliche Assertions ohne Einzeltestzählung; ein erfolgreiches Skript wird ausdrücklich als solches bezeichnet. Ein Skip beweist keine funktionierende Integration. Fehler führen zum Exitstatus 1. Anwendungsversion bleibt bei reinen Teständerungen unverändert.
