#!/bin/sh
# Optionale PDF-Bibliothek im Programmordner installieren.
set -eu
cd -- "$(dirname -- "$0")"
/usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
# Nachinstallierte Bibliotheken für die vollständige Deinstallation erfassen.
.venv/bin/python - <<'PY'
import json
from pathlib import Path
root=Path.cwd(); manifest=root/'installed-files.json'
if manifest.is_file():
    data=json.loads(manifest.read_text())
    for path in (root/'.venv').rglob('*'):
        key='files' if path.is_file() or path.is_symlink() else 'directories'
        if str(path) not in data[key]: data[key].append(str(path))
    data['directories'].append(str(root/'.venv'))
    manifest.write_text(json.dumps(data,indent=2))
PY
