import sys,json,tempfile,traceback,time
from pathlib import Path
from unittest.mock import patch
import mintpdf,gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
root=Path(__file__).resolve().parents[1];original=Gtk.Application.run;fail=[]
with tempfile.TemporaryDirectory(dir=root/'work') as tmp:
 mintpdf.STATE=Path(tmp)
 for name in ('config','logs','languages','help','output'):(mintpdf.STATE/name).mkdir()
 def run(app,args):
  app.set_application_id('eu.dogtruck.mintpdf.settings_search_test')
  def begin():
   if app._checking:return True
   try:
    app.search.set_text('no-such-tool-xyz');assert app.empty_search.get_visible()
    assert all(not row.get_visible() for row,_,_ in app.tiles.values())
    app.search.set_text('PDF/A');assert app.tiles['pdfa'][0].get_visible();assert app.tiles['pdfa_check'][0].get_visible()
    app.search.set_text('');assert all(row.get_visible() for row,_,_ in app.tiles.values())
    app._qa_config=dict(app.config);mintpdf.write_settings(app.config)
    app._qa_bytes=(mintpdf.STATE/'config/settings.json').read_bytes()
    window=app.settings();window.output_entry.set_text(str(mintpdf.STATE/'output'));window.cancel_button.emit('clicked')
    assert app.config==app._qa_config;assert (mintpdf.STATE/'config/settings.json').read_bytes()==app._qa_bytes
    app._qa_window=app.settings();app._qa_deadline=time.monotonic()+10;GLib.timeout_add(50,light)
   except Exception:fail.append(traceback.format_exc());app.quit()
   return False
  def light():
   try:
    separators=[w for w in mintpdf.descendants(app._qa_window) if isinstance(w,Gtk.Separator)]
    if (len(separators)!=2 or not all(w.get_mapped() and w.get_height()>=1 and w.get_width()>0 for w in separators)) and time.monotonic()<app._qa_deadline:return True
    assert len(separators)==2
    assert all(w.get_mapped() and w.get_height()>=1 and w.get_width()>0 for w in separators), [(w.get_mapped(),w.get_height(),w.get_width()) for w in separators]
    captured=[]
    with patch.object(app,'error',captured.append):
     app._qa_window.output_entry.set_text(str(mintpdf.STATE/'missing'))
     app._qa_window.save_button.emit('clicked')
    assert captured and app.config==app._qa_config
    app._qa_window.output_entry.set_text(str(mintpdf.STATE/'output'));app._qa_window.save_button.emit('clicked')
    assert app.config['output_dir']==str(mintpdf.STATE/'output')
    assert json.loads((mintpdf.STATE/'config/settings.json').read_text())['output_dir']==app.config['output_dir']
    app.language='en';Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',True)
    app._qa_window=app.settings();app._qa_window.set_default_size(440,380);app._qa_deadline=time.monotonic()+10;GLib.timeout_add(50,dark)
   except Exception:fail.append(traceback.format_exc());app.quit()
   return False
  def dark():
   try:
    separators=[w for w in mintpdf.descendants(app._qa_window) if isinstance(w,Gtk.Separator)]
    if (len(separators)!=2 or not all(w.get_mapped() and w.get_height()>=1 and w.get_width()>0 for w in separators)) and time.monotonic()<app._qa_deadline:return True
    assert len(separators)==2
    assert all(w.get_mapped() and w.get_height()>=1 and w.get_width()>0 for w in separators), [(w.get_mapped(),w.get_height(),w.get_width()) for w in separators]
    assert app._qa_window.output_entry.get_text()==app.config['output_dir']
    assert app._qa_window.cancel_button.get_mapped() and app._qa_window.save_button.get_mapped()
    assert app._qa_window.get_width()<=450
    labels=[w.get_label() for w in mintpdf.descendants(app._qa_window) if isinstance(w,Gtk.Label)]
    assert 'Output' in labels and 'Language' in labels
    app._qa_window.close()
   except Exception:fail.append(traceback.format_exc())
   app.quit();return False
  GLib.timeout_add(700,begin);return original(app,[])
 with patch.object(Gtk.Application,'run',run):sys.argv=['mintpdf.py'];mintpdf.main()
if fail:raise AssertionError('\n'.join(fail))
print('Settings: visible separators light/dark, small window, cancel/save/invalid folder and live search typing passed')
