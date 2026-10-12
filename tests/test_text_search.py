import sys,tempfile,json,time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,mintpdf,pymupdf as fitz,gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
root=Path(__file__).resolve().parents[1];tmp=tempfile.TemporaryDirectory(dir=root/'work');source=Path(tmp.name)/'text.pdf'
with fitz.open() as doc:
 p=doc.new_page();p.insert_text((50,70),'Alpha test Alpha')
 p=doc.new_page();p.insert_text((50,70),'Second Alpha')
 doc.save(source)
raw=source.read_bytes();assert len(core.search_pdf_text(raw,'Alpha'))==2;assert not core.search_pdf_text(raw,'absent')
errors=[];state={};tr=json.loads((root/'languages/de.json').read_text());app=Gtk.Application(application_id='eu.dogtruck.mintpdf.searchtest')
def activate(a):
 try:
  win=Gtk.ApplicationWindow(application=a);win.present();owner=SimpleNamespace(window=win,tr=lambda k:tr.get(k,k),error=errors.append)
  e=mintpdf.open_text_search(owner,str(source));state.update(editor=e,deadline=time.monotonic()+10)
  e.entry.set_text('absent');e.search();e.entry.set_text('Alpha');e.search();GLib.timeout_add(100,check)
 except Exception as exc:errors.append(exc);app.quit()
def check():
 e=state['editor']
 if not e.results and time.monotonic()<state['deadline']:return True
 try:
  assert len(e.results)==2 and sum(len(i['rects']) for i in e.results)==3
  e.list.select_row(e.list.get_row_at_index(1));assert e.picture.get_paintable()
  assert source.read_bytes()==raw
  e.entry.set_text('');e.search();assert not e.results
  e.close();assert not e.alive
  print('PASS: text search, multiple pages/hits, missing query, stale result suppression, highlighted GUI preview, source unchanged')
 except Exception as exc:errors.append(exc)
 app.quit();return False
app.connect('activate',activate);app.run([]);tmp.cleanup()
if errors:raise AssertionError(errors)
