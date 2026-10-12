"""Run as each regular user: managed desktop integration and own state cleanup."""
import os,shutil,subprocess,sys
from pathlib import Path
home=Path.home();action=sys.argv[1]
try:
 desktop=Path(subprocess.check_output(['xdg-user-dir','DESKTOP'],text=True).strip())
except (OSError,subprocess.SubprocessError):
 desktop=None
if desktop and desktop!=home and desktop.is_dir() and not desktop.is_symlink():
 target=desktop/'mintpdf.desktop'
 if action=='install':
  if not target.exists() or (not target.is_symlink() and 'X-mintpdf-Managed=true' in target.read_text()):
   shutil.copyfile('/usr/share/applications/mintpdf.desktop',target);target.chmod(0o755)
   subprocess.run(['gio','set',str(target),'metadata::trusted','true'],check=False)
 elif target.is_file() and not target.is_symlink() and 'X-mintpdf-Managed=true' in target.read_text():target.unlink()
if action=='remove':
 state=home/'.local/share/mintpdf'
 # The application uses this fixed location, not arbitrary XDG overrides.
 if state.exists():
  if any(p.is_symlink() for p in [home/'.local',home/'.local/share',state]):
   raise RuntimeError('Linked state path protected: '+str(state))
  shutil.rmtree(state)
 trash=home/'.local/share/Trash/files'
 if trash.is_dir() and not trash.is_symlink():
  for p in trash.glob('mintpdf*.desktop'):
   if p.is_file() and not p.is_symlink() and 'X-mintpdf-Managed=true' in p.read_text():p.unlink()
