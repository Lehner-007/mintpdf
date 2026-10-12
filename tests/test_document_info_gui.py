import sys,tempfile,traceback
from pathlib import Path
from unittest.mock import patch
import mintpdf,pymupdf,gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
original=Gtk.Application.run
errors=[]
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'work') as tmp:
 mintpdf.STATE=Path(tmp)
 for name in ('config','logs','languages','help'):(mintpdf.STATE/name).mkdir()
 source=Path(tmp)/'sample.pdf'
 with pymupdf.open() as doc:doc.new_page();doc.set_metadata({'title':'GUI sample'});doc.save(source)
 def run(app,argv):
  app.set_application_id('eu.dogtruck.mintpdf.document_info_test')
  stages=iter([('de',False),('en',True)])
  def start():
   if app._checking:return True
   try:
    assert app.lookup_action('document_info').get_enabled()
    lang,dark=next(stages);app.language=lang
    Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',dark)
    app.tool_dialog('document_info',[str(source)])
    app.test_window=app._document_information;app.test_window.set_default_size(440,320)
    GLib.timeout_add(300,check)
   except StopIteration:app.quit()
   except Exception:errors.append(traceback.format_exc());app.quit()
   return False
  def check():
   if not hasattr(app.test_window,'document_data'):return True
   try:
    assert app.test_window.document_data['title']=='GUI sample'
    assert not app.busy
    labels=[w.get_label() for w in mintpdf.descendants(app.test_window) if isinstance(w,Gtk.Label)]
    assert 'GUI sample' in labels
    assert app.tr('doc_author') in labels
    assert any(isinstance(w,Gtk.ScrolledWindow) for w in mintpdf.descendants(app.test_window))
    app.test_window.close();GLib.timeout_add(100,start)
   except Exception:errors.append(traceback.format_exc());app.quit()
   return False
  GLib.timeout_add(500,start);return original(app,[])
 with patch.object(Gtk.Application,'run',run):
  sys.argv=['mintpdf.py'];mintpdf.main()
if errors:raise AssertionError('\n'.join(errors))
print('Document information GUI DE/EN light/dark small window passed')
