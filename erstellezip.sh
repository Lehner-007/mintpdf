#!/usr/bin/env bash
# Erstellt ein bereinigtes, direkt nutzbares mintPDF-Paket.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 - "$SCRIPT_DIR" <<'PYCODE'
from pathlib import Path
import os, re, stat, sys, tempfile, zipfile

root = Path(sys.argv[1]).resolve()
source = (root / "core.py").read_text(encoding="utf-8")
match = re.search(r"^VERSION = ['\"]([^'\"]+)['\"]", source, re.M)
if not match or not re.fullmatch(r"\d+\.\d+\.\d+", match.group(1)):
    raise SystemExit("Zentrale Programmversion in core.py fehlt oder ist ungültig.")
version = match.group(1)
prefix = f"mintpdf-{version}"
files = [root / name for name in (
    "core.py", "mintpdf.py", "install.py", ".start.sh",
    "projekt.json", "requirements.txt", "setup_dependencies.sh",
    "README.md", "CHANGELOG.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
)]
for directory in ("resources", "languages", "help", "assets", "vendor"):
    base = root / directory
    if not base.is_dir():
        raise SystemExit(f"Paketordner fehlt: {directory}")
    files.extend(
        path for path in sorted(base.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".log")
    )
files = sorted(set(files), key=lambda path: path.relative_to(root).as_posix())
for path in files:
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"Fehlende oder verlinkte Paketdatei: {path}")
    if "__pycache__" in path.parts or path.suffix in (".pyc", ".log"):
        raise SystemExit(f"Nicht zulässige Datei im Paketumfang: {path}")

outdir = root / "dist"
outdir.mkdir(exist_ok=True)
output = outdir / f"{prefix}.zip"
if output.exists():
    raise SystemExit(f"Paket existiert bereits; wird nicht überschrieben: {output}")
fd, temp_name = tempfile.mkstemp(prefix=f".{prefix}-", suffix=".zip", dir=outdir)
os.close(fd)
try:
    expected = set()
    with zipfile.ZipFile(temp_name, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = Path(prefix) / path.relative_to(root)
            name = relative.as_posix()
            expected.add(name)
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | (path.stat().st_mode & 0o777)) << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(temp_name) as archive:
        if archive.testzip():
            raise SystemExit("ZIP-Integrität fehlgeschlagen.")
        actual = set(archive.namelist())
        if actual != expected:
            raise SystemExit("ZIP-Inhalt stimmt nicht mit der Dateiliste überein.")
        forbidden = (".venv/", "/config/", "/logs/", "/tests/", "/work/", "/dist/")
        if any(any(token in name for token in forbidden) for name in actual):
            raise SystemExit("Entwicklungs- oder Laufzeitdaten unerwartet im ZIP.")
    os.chmod(temp_name, 0o644)
    os.replace(temp_name, output)
finally:
    if os.path.exists(temp_name):
        os.unlink(temp_name)
print(f"{output}: {len(files)} Laufzeitdateien, ZIP-Integrität und Umfang geprüft.")
PYCODE
