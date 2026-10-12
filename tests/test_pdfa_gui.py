import sys,tempfile,traceback
from pathlib import Path
from unittest.mock import patch
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
import mintpdf
root=Path(__file__).resolve().parents[1]
original_run=Gtk.Application.run
failures=[]
def run(app,argv):
 app.set_application_id('eu.dogtruck.mintpdf.pdfa_test')
 def checks():
  try:
   assert app.lookup_action('pdfa').get_enabled()
   assert not app.group_widgets
   assert len(app.tiles)==32
   assert all(row.get_parent() is app.tool_flow for row,button,reason in app.tiles.values())
   app.filter_functions('no-matching-tool-xyz');assert app.empty_search.get_visible()
   assert all(not row.get_visible() for row,button,reason in app.tiles.values())
   app.filter_functions('pdfa');assert app.tiles['pdfa'][0].get_visible()
   app.filter_functions('');assert all(row.get_visible() for row,button,reason in app.tiles.values())
   for key in ('form','pdfa','pdfa_check'):
    assert app.tiles[key][1].get_sensitive()
    image=app.icon(key,64)
    assert image.get_paintable() is not None
   for lang,dark in [('de',False),('en',True)]:
    app.language=lang
    Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',dark)
    app.window.set_default_size(680,620)
    for key in ('pdfa','pdfa_check'):
     app.tool_dialog(key,[str(root/'work'/'gui-source.pdf')])
     dialogs=[w for w in Gtk.Window.get_toplevels() if w!=app.window]
     assert dialogs
     def entries(widget):
      result=[widget] if isinstance(widget,Gtk.Entry) else []
      child=widget.get_first_child()
      while child:
       result.extend(entries(child));child=child.get_next_sibling()
      return result
     if key=='pdfa_check':assert not entries(dialogs[0])
     for dialog in dialogs:dialog.destroy()
  except Exception:failures.append(traceback.format_exc())
  app.quit();return False
 GLib.timeout_add(1500,checks)
 return original_run(app,[])
with tempfile.TemporaryDirectory(dir=root/'work') as tmp:
 mintpdf.STATE=Path(tmp)
 for name in ('config','logs','languages','help'):(mintpdf.STATE/name).mkdir()
 with patch.object(Gtk.Application,'run',run):
  sys.argv=['mintpdf.py'];mintpdf.main()
if failures:raise AssertionError('\n'.join(failures))
print('GUI: icons, enabled actions, DE/EN and light/dark dialogs passed')
