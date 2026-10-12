"""Zielübergabe simuliert; Abbruch mit echter asynchroner GTK-Dateiauswahl."""
import sys,traceback
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mintpdf,gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib,Gio
root=Path(__file__).resolve().parents[1]
errors=[];chosen=[];passed=[];state={}
class FileDialogDouble:
 def __init__(self,**kwargs):self.settings=kwargs
 def set_accept_label(self,value):pass
 def set_initial_folder(self,value):self.folder=value
 def set_initial_name(self,value):self.name=value
 def set_filters(self,value):pass
 def set_default_filter(self,value):pass
 def save(self,parent,cancellable,callback):GLib.idle_add(lambda:(callback(self,None),False)[1])
 def save_finish(self,result):return Gio.File.new_for_path(str(root/'work'/'qa-target.pdf'))
app=Gtk.Application(application_id='eu.dogtruck.mintpdf.target_test')
def activate(app):
 window=Gtk.ApplicationWindow(application=app,title='QA-Zielauswahl',default_width=400,default_height=250);window.present();state['owner']=window
 try:
  with patch.object(Gtk,'FileDialog',FileDialogDouble):
   state['mock']=mintpdf.select_save_target(window,'QA',root/'work'/'fehlend'/'ziel.pdf',chosen.append,errors.append,'Speichern')
  assert state['mock'].folder.get_path()==str(root/'work')
  GLib.timeout_add(200,real_cancel)
 except Exception:errors.append(traceback.format_exc());app.quit()
def real_cancel():
 try:
  assert chosen==[str(root/'work'/'qa-target.pdf')],chosen
  assert not Path(chosen[0]).exists()
  passed.append('Simulierte Zielübernahme, vorhandener Startordner, keine Dateierzeugung')
  state['picker']=mintpdf.select_save_target(state['owner'],'QA-Abbrechen',root/'work'/'behalten.pdf',chosen.append,errors.append,'Speichern')
  GLib.timeout_add(300,lambda:(state['picker']._cancellable.cancel(),False)[1])
  GLib.timeout_add(850,finish)
 except Exception:errors.append(traceback.format_exc());app.quit()
 return False
def finish():
 try:
  assert len(chosen)==1 and not errors,(chosen,errors)
  passed.append('Echte GTK-Dateiauswahl: Abbruch ohne Fehlerrückmeldung und Zieländerung')
 except Exception:errors.append(traceback.format_exc())
 app.quit();return False
app.connect('activate',activate);app.run([])
print({'passed':passed,'errors':[str(e) for e in errors]})
if errors or len(passed)!=2:sys.exit(1)
