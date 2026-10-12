#!/bin/sh
cd -- "$(dirname -- "$0")" || exit 1
if [ ! -f mintpdf.py ]; then
    printf '%s\n' 'E_START: mintpdf.py fehlt. Bitte Programmpaket wiederherstellen.' >&2
    exit 1
fi
if [ -x .venv/bin/python ]; then
    exec .venv/bin/python mintpdf.py "$@"
fi
exec /usr/bin/python3 mintpdf.py "$@"
