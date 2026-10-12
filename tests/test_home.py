import sys, json, traceback, subprocess, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mintpdf, core
catalog=core
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk, GLib, Gio
root=Path(__file__).resolve().parents[1]
mintpdf.STATE=root/'work'/'test_profile'
for name in ('config','logs','languages','help'):(mintpdf.STATE/name).mkdir(parents=True,exist_ok=True)
results=[]; failure=[]
run=Gtk.Application.run

def test_start(app, argv):
 app.set_application_id("eu.dogtruck.mintpdf.home_test")
 def checks():
  try:
   assert app.home_watermark.get_opacity() < 0.11
   assert not app.home_watermark.get_can_target()
   assert app.home_overlay.get_child() is not None
   assert not app._checking
   assert len(app.tiles)==len(catalog.FUNCTIONS)==32
   for f in catalog.FUNCTIONS:
    assert app.tiles[f.id][1].get_sensitive()==app.lookup_action(f.id).get_enabled()
    if f.handler is None:
     assert not app.lookup_action(f.id).get_enabled()
     assert 'Noch nicht umgesetzt' in app.tiles[f.id][2].get_text()
   for i,group in enumerate(catalog.GROUPS):
    menu=app.tool_menu.get_item_link(i,'submenu')
    functions=[f for f in catalog.FUNCTIONS if f.group==group]
    assert menu.get_n_items()==len(functions)
    for j,f in enumerate(functions):
     assert menu.get_item_attribute_value(j,'label',None).get_string()==app.tr(f.id)
   assert [app.main_menu.get_item_attribute_value(i,'label',None).get_string() for i in range(3)]==[app.tr('file'),app.tr('tools'),app.tr('help_menu')]
   section=app.file_menu.get_item_link(1,'section')
   assert section.get_item_attribute_value(section.get_n_items()-1,'label',None).get_string()==app.tr('settings')
   assert app.file_menu.get_item_link(2,'section').get_item_attribute_value(0,'label',None).get_string()==app.tr('quit')
   assert 'F1' in app.get_accels_for_action('app.help')
   help_model=app.main_menu.get_item_link(2,'submenu')
   assert [help_model.get_item_attribute_value(i,'label',None).get_string() for i in range(4)]==['Hilfe','Protokoll','Info','Über']
   assert help_model.get_item_attribute_value(2,'icon',None) is not None
   for f in catalog.FUNCTIONS:
    if f.id in core.BY_ID and f.id!='form':assert any((root/'resources'/(f.icon+ext)).is_file() for ext in ('.png','.svg'))
   sizes={(tile.get_width(),tile.get_height()) for _,tile,_ in app.tiles.values()}
   assert len(sizes)==1 and next(iter(sizes))[0]>0,sizes
   results.append('Alle Kacheln gruppenübergreifend gleich groß')
   results.append('Menü Datei/Werkzeuge/Hilfe, Einstellungen vor Trennlinie/Beenden und F1 geprüft')
   results.append('32 Funktionen; Kachel/Aktion stimmen überein; geplante Funktionen gesperrt')
   app.filter_functions('crop')
   assert app.tiles['crop'][0].get_visible() and app.tiles['crop'][1].get_sensitive()
   app.filter_functions('xxxxxxxxxxxxxxxx')
   assert app.empty_search.get_visible()
   app.filter_functions(''); assert not app.empty_search.get_visible()
   results.append('Suche über Gruppen, gesperrte Treffer und leeres Ergebnis geprüft')
   called=[]; old=app.choose_files
   app.choose_files=lambda **kwargs:called.append(kwargs)
   app.tool_dialog('merge');assert called[-1]['tool']=='merge'
   app.choose_files=old
   messages=[]; oldmessage=app.message; app.message=lambda *args:messages.append(args)
   app.choose_files=lambda **kwargs:called.append(kwargs)
   app.tool_dialog('convert');assert called[-1]['tool']=='convert'
   app.choose_files=old
   app.message=oldmessage
   app.busy=True;app.apply_function_states(app.function_states)
   assert all(not app.lookup_action(f.id).get_enabled() for f in catalog.FUNCTIONS)
   app.busy=False;app.apply_function_states(app.function_states)
   results.append('Dateiauswahl ohne offene PDF; direkte Platzhalter-Aufrufe und Verarbeitungssperre geprüft')
   dialog=app.tool_dialog('rotate',[str(root/'work'/'qa-input.pdf')],str(root/'work'/'qa-result.pdf'))
   from mintpdf import descendants
   button=next(w for w in descendants(dialog) if isinstance(w,Gtk.Button) and w.get_label()==app.tr('finish'))
   app._qa_message=app.message;app.message=lambda *args:None
   def fail_process(*args):raise ValueError('E_INPUT')
   app._qa_patch=patch.object(mintpdf,'process',fail_process);app._qa_patch.start()
   app._qa_dialog=dialog
   button.emit('clicked');assert app.busy
   app._qa_deadline=time.monotonic()+10
   GLib.timeout_add(50,error_done)
   app.window.set_default_size(1920,1080)
   Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',False)

  except Exception:failure.append(traceback.format_exc());app.quit()
  return False
 def error_done():
  if (app.busy or app._checking) and time.monotonic()<app._qa_deadline:return True
  try:
   assert not app.busy
   assert app.lookup_action('merge').get_enabled()
   app._qa_patch.stop();app.message=app._qa_message;app._qa_dialog.destroy()
   results.append('Verarbeitungsfehler ausgelöst; Oberfläche danach wieder freigegeben')
   GLib.timeout_add(600,large)
  except Exception:failure.append(traceback.format_exc());app.quit()
  return False
 def large():
  try:
   assert app.window.get_width()>=1600
   app.lookup_action('focus_search').activate(None)
   focus=app.window.get_focus()
   assert focus and (focus==app.search or focus.is_ancestor(app.search))
   subprocess.run(['gnome-screenshot','-f',str(root/'work'/'home-large-light.png')],timeout=10,check=True)
   results.append('Deutsch/Hell, große Ansicht und Tastaturfokus Strg+F geprüft')
   from mintpdf import descendants
   app._file_popup=next(w for w in descendants(app.menu_bar) if isinstance(w,Gtk.PopoverMenu))
   app._file_popup.popup()
   GLib.timeout_add(250,separator_light)
  except Exception:failure.append(traceback.format_exc());app.quit()
  return False
 def check_separator():
  from mintpdf import descendants
  separators=[w for w in descendants(app._file_popup) if isinstance(w,Gtk.Separator)]
  assert app._file_popup.get_mapped()
  assert sum(w.get_mapped() and w.get_width()>0 and w.get_height()>=1 for w in separators)>=2
  app._file_popup.popdown()
 def separator_light():
  try:
   check_separator();results.append('Datei-Menü: Trennlinie im hellen Theme tatsächlich sichtbar')
   app.language='en';app.build()
   GLib.timeout_add(700,small)
  except Exception:failure.append(traceback.format_exc());app.quit()
  return False
 def separator_dark():
  try:
   check_separator();results.append('Datei-Menü: Trennlinie im dunklen Theme tatsächlich sichtbar')
  except Exception:failure.append(traceback.format_exc());app.quit()
  return False
 def small():
  try:
   app.window.set_default_size(680,620)
   Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',True)
   from mintpdf import descendants
   app._file_popup=next(w for w in descendants(app.menu_bar) if isinstance(w,Gtk.PopoverMenu))
   app._file_popup.popup()
   GLib.timeout_add(250,separator_dark)
   # Actual single-entry menu popup and allocation test.
   model=Gio.Menu(); single=Gio.Menu();single.append('Help','app.help');model.append_submenu('Single',single)
   bar=Gtk.PopoverMenuBar.new_from_model(model)
   app.window.get_child().prepend(bar)
   from mintpdf import compact_menus,descendants
   compact_menus(bar)
   app._qa_bar=bar
   GLib.timeout_add(500,menu)
  except Exception:failure.append(traceback.format_exc());app.quit()
  return False
 def menu():
  try:
   from mintpdf import descendants,compact_menus
   pops=[w for w in descendants(app._qa_bar) if isinstance(w,Gtk.PopoverMenu)]
   assert pops
   pops[0].popup();compact_menus(app._qa_bar)
   app._qa_pop=pops[0]
   GLib.timeout_add(500,finish)
  except Exception:failure.append(traceback.format_exc());app.quit()
  return False
 def finish():
  try:
   from mintpdf import descendants
   scrolls=[w for w in descendants(app._qa_pop) if isinstance(w,Gtk.ScrolledWindow)]
   assert app._qa_pop.get_mapped()
   for scroll in scrolls:
    child=scroll.get_child(); natural=child.measure(Gtk.Orientation.VERTICAL,-1).natural
    actual=scroll.get_height()
    assert actual<=natural+12,(actual,natural)
   results.append('Eintragsmenü tatsächlich geöffnet; zugeteilte Höhe gegen natürliche Höhe geprüft')
   app._qa_pop.popdown()
   assert app.window.get_width()<=700,app.window.get_width()
   assert app.search.get_width()>100
   subprocess.run(['gnome-screenshot','-f',str(root/'work'/'home-small-dark.png')],timeout=10,check=True)
   results.append('Englisch/Dunkel und kleines Fenster 680x620 aufgebaut; Bildschirmfoto gespeichert')
  except Exception:failure.append(traceback.format_exc())
  app.quit();return False
 GLib.timeout_add(1300,checks)
 return run(app,[])

with patch.object(Gtk.Application,'run',test_start):
 sys.argv=['mintpdf.py'];mintpdf.main()
(root/'work'/'gui-results.json').write_text(json.dumps({'passed':results,'errors':failure},ensure_ascii=False,indent=2))
print(json.dumps({'passed':results,'errors':failure},ensure_ascii=False))
if failure:sys.exit(1)
