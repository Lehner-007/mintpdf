import sys,json,traceback,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mintpdf,core,gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
ROOT=Path(__file__).resolve().parents[1]
mintpdf.STATE=ROOT/'work/info_profile'
for name in ('config','logs','languages','help'):(mintpdf.STATE/name).mkdir(parents=True,exist_ok=True)
errors=[];passed=[];original_run=Gtk.Application.run

def run(app,args):
 app.set_application_id("eu.dogtruck.mintpdf.info_test")
 def start():
  try:
   app._test_info=app.info()
   assert app.info() is app._test_info
   app._test_start=time.monotonic()
   GLib.timeout_add(100,ready)
  except Exception:errors.append(traceback.format_exc());app.quit()
  return False
 def ready():
  dialog=app._test_info
  if not hasattr(dialog,'tool_results'):
   if time.monotonic()-app._test_start<20:return True
   errors.append('Info-Prüfung überschreitet 20 Sekunden');app.quit();return False
  try:
   assert len(dialog.tool_results)==len(json.loads((ROOT/'projekt.json').read_text())['tool_info'])
   assert any(t['name']=='veraPDF' and t['available'] and '1.30.3' in t['version'] for t in dialog.tool_results)
   widgets=list(mintpdf.descendants(dialog))
   assert any(isinstance(w,Gtk.Image) and w.get_icon_name()=='dialog-information-symbolic' for w in widgets)
   assert any(isinstance(w,Gtk.ScrolledWindow) for w in widgets)
   assert any(isinstance(w,Gtk.Button) and w.get_label()=='Schließen' for w in widgets)
   assert any(t['name']=='Python' and t['available'] and t['version'] for t in dialog.tool_results)
   dialog.set_default_size(440,320)
   passed.append('Konfigurierte Abhängigkeiten einschließlich benutzerlokalem veraPDF, Versionsprüfung, Infosymbol, Scrollliste, Schließen und Einzelfenster geprüft')
   dialog.close();assert app._info_dialog is None
   app.language='en'
   def slow(tool):time.sleep(.03);return dict(tool,available=False,version='',error='')
   with patch.object(core,'inspect_tool',slow):
    window=app.info()
    assert window.get_title()=='Info'
    assert any(isinstance(w,Gtk.Button) and w.get_label()=='Close' for w in mintpdf.descendants(window))
    window.close();assert app._info_dialog is None
   passed.append('Englisch und Schließen während Hintergrundprüfung geprüft')
   GLib.timeout_add(700,finish)
  except Exception:errors.append(traceback.format_exc());app.quit()
  return False
 def finish():
  passed.append('Späte Hintergrundrückmeldung nach Schließen ohne erneutes Fenster')
  app.quit();return False
 GLib.timeout_add(500,start)
 return original_run(app,[])
with patch.object(Gtk.Application,'run',run):
 sys.argv=['mintpdf.py'];mintpdf.main()
print(json.dumps({'passed':passed,'errors':errors},ensure_ascii=False))
if errors or not passed:sys.exit(1)
