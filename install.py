#!/usr/bin/env python3
"""Installiert mintPDF benutzerlokal und entfernt erfasste Dateien wieder.

GPL-3.0-only, Josef Lehner. Keine Administratorrechte erforderlich.
--prefix, --desktop und --applications erlauben isolierte Installationsprüfungen.
Fremde vorhandene Dateien werden weder ersetzt noch entfernt.
"""
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys
SOURCE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--uninstall',action='store_true')
 p.add_argument('--prefix',type=Path,default=Path.home()/'.local')
 p.add_argument('--desktop',type=Path)
 p.add_argument('--applications',type=Path)
 a=p.parse_args(); prefix=a.prefix.expanduser().absolute(); target=prefix/'opt/mintpdf'
 manifest=target/'installed-files.json'
 if a.uninstall:
  if not manifest.is_file():p.error('No mintPDF installation manifest found.')
  record=json.loads(manifest.read_text())
  failures=[]
  # Diese Laufzeitdateien erzeugt ausschließlich mintPDF selbst.
  runtime=[target/'logs/mintpdf.log',target/'config/settings.json']
  for module in ('core','mintpdf'): runtime+=list((target/'__pycache__').glob(module+'.cpython-*.pyc'))
  for item in [*reversed(record['files']),*map(str,runtime)]:
   try: Path(item).unlink(missing_ok=True)
   except OSError as exc:failures.append(f'{item}: {exc}')
  if failures:print('\n'.join(failures),file=sys.stderr);return 1
  manifest.unlink()
  for item in sorted([*record['directories'],str(target/'__pycache__')],key=lambda s:len(Path(s).parts),reverse=True):
   try:Path(item).rmdir()
   except OSError:pass  # Fremde oder später hinzugefügte Dateien erhalten.
  print('mintPDF removed. User-created files, if any, were preserved.');return 0
 if target.exists():p.error(f'Already exists: {target}')
 if a.desktop:desktop=a.desktop.expanduser().absolute()
 else:
  try:desktop=Path(subprocess.check_output(['xdg-user-dir','DESKTOP'],text=True).strip())
  except (OSError,subprocess.SubprocessError):p.error('Specify --desktop with your actual desktop folder.')
 apps=(a.applications or prefix/'share/applications').absolute()
 launcher=prefix/'bin/mintpdf'
 menu=apps/'mintpdf.desktop'; shortcut=desktop/'mintpdf.desktop'
 for path in (launcher,menu,shortcut):
  if path.exists() or path.is_symlink():p.error(f'Refusing to replace: {path}')
 files=[]; directories=[]
 def mkdir(path):
  absent=[]; cursor=path
  while not cursor.exists():absent.append(cursor);cursor=cursor.parent
  path.mkdir(parents=True,exist_ok=True);directories.extend(str(x) for x in reversed(absent))
 try:
  mkdir(target)
  names=['mintpdf.py','core.py','mintpdf.pyc','core.pyc','LICENSE','README.md','CHANGELOG.md','projekt.json','requirements.txt','setup_dependencies.sh','install.py','PRUEFBERICHT.txt','REFERENZPROJEKTE.txt']
  for name in names:
   src=SOURCE/name
   if src.is_file():dest=target/name;shutil.copy2(src,dest);files.append(str(dest))
  for name in ('resources','languages','help','assets'):
   for src in (SOURCE/name).rglob('*'):
    if src.is_file():
     dest=target/src.relative_to(SOURCE);mkdir(dest.parent);shutil.copy2(src,dest);files.append(str(dest))
  for name in ('config','logs'):mkdir(target/name)
  mkdir(launcher.parent);entry='mintpdf.py' if (target/'mintpdf.py').exists() else 'mintpdf.pyc'
  import shlex
  launcher.write_text('#!/bin/sh\ncd '+shlex.quote(str(target))+' || exit 1\nif [ -x .venv/bin/python ]; then exec .venv/bin/python '+entry+' "$@"; fi\nexec /usr/bin/python3 '+entry+' "$@"\n');launcher.chmod(0o755);files.append(str(launcher))
  # Desktop Exec wird nach Desktop-Entry-Spezifikation zitiert.
  exec_path=str(launcher).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
  contents=f'[Desktop Entry]\nType=Application\nName=mintPDF\nComment=Local PDF tools\nExec="{exec_path}"\nIcon={target}/resources/mintpdf.png\nTerminal=false\nCategories=Office;Graphics;\nStartupWMClass=mintPDF\n'
  for path in (menu,shortcut):
   mkdir(path.parent);path.write_text(contents);path.chmod(0o755);files.append(str(path))
  try:subprocess.run(['gio','set',str(shortcut),'metadata::trusted','true'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
  except OSError:pass
  manifest.write_text(json.dumps({'files':files,'directories':list(dict.fromkeys(directories))},indent=2))
 except Exception:
  for path in reversed(files):Path(path).unlink(missing_ok=True)
  for path in sorted(set(directories),key=lambda s:len(Path(s).parts),reverse=True):
   try:Path(path).rmdir()
   except OSError:pass
  raise
 print(f'Installed: {target}\nDesktop: {shortcut}\nMenu: {menu}')
 return 0
if __name__=='__main__':raise SystemExit(main())
