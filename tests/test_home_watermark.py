import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mintpdf
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
run=Gtk.Application.run
fail=[]
def start(app,argv):
 app.set_application_id('eu.dogtruck.mintpdf.watermarktest')
 def check():
  try:
   assert app.home_watermark.get_paintable() is not None
   assert not app.home_watermark.get_can_target()
   assert app.home_watermark.get_opacity()<0.11
   assert app.home_watermark.get_width()>0
   assert app.lookup_action('web').get_enabled()
   calls=[];original=app.choose_files
   app.choose_files=lambda **kw:calls.append(kw)
   app.tool_dialog('web');app.choose_files=original
   assert calls==[{'tool':'web'}]
   app.window.set_default_size(680,650)
   GLib.timeout_add(400,small)
  except Exception as e:fail.append(str(e));app.quit()
  return False
 def small():
  try:
   assert app.home_watermark.get_width()<=app.window.get_width()
   assert app.home_watermark.get_height()<=app.window.get_height()
  except Exception as e:fail.append(str(e))
  app.quit();return False
 GLib.timeout_add(1000,check)
 return run(app,argv)
with patch.object(Gtk.Application,'run',start):
 sys.argv=['mintpdf.py'];mintpdf.main()
assert not fail,fail
print('PASS watermark displayed, non-interactive, small window; webpage action enabled')
