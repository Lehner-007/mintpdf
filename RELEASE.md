# mintPDF 1.39.2

Lokale PDF-Werkzeuge für Linux Mint 22.x, Python 3.12 und GTK 4.

Beim Überlagern bleiben Metadaten, Lesezeichen und Anhänge von PDF 1 erhalten. Vorschau und Export verwenden dieselbe Komposition. Die Testorganisation trennt Kernprüfungen und optionale Integrationstests. Die korrigierten GUI-Testabläufe wurden unter Linux Mint geprüft: 31 Module bestanden, keine Fehler oder Skips.

Das DEB ist für amd64 und enthält PyMuPDF 1.28.2 samt Lizenzinformationen. Installation:

```bash
sudo apt install ./mintpdf_1.39.2_amd64.deb
```

Ghostscript, LibreOffice, OCRmyPDF, Tesseract und wkhtmltopdf sind optionale Werkzeuge. veraPDF muss für die PDF/A-Prüfung zusätzlich verfügbar sein. Fehlende Werkzeuge werden in der Oberfläche angezeigt. Die enthaltene Prüfanleitung dokumentiert weitere Integrationsgrenzen; eine echte grafische Paketinstallation/-entfernung wurde nicht im laufenden System durchgeführt.
