import sys,tempfile,json,time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pymupdf as fitz,gi,mintpdf
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
root=Path(__file__).resolve().parents[1];tmp=tempfile.TemporaryDirectory(dir=root/'work');p=Path(tmp.name);source=p/'source.pdf'
with fitz.open() as doc:
 doc.new_page().insert_text((50,50),'Original');doc.new_page(width=842,height=595);doc.save(source)
raw=source.read_bytes();errors=[];tr=json.loads((root/'languages/de.json').read_text());app=Gtk.Application(application_id='eu.dogtruck.numbertest');state={}
def activate(a):
 try:
  owner=SimpleNamespace(window=Gtk.ApplicationWindow(application=a),tr=lambda k:tr.get(k,k),config={},error=errors.append)
  w=mintpdf.open_page_numbers(owner,source);state['w']=w
  w.text.set_text('Seite ##');w.render();before=w.picture.get_paintable()
  w.fields['number_x'].set_value(20);w.fields['number_y'].set_value(10);w.fields['number_start'].set_value(3);w.page.set_value(2);w.render()
  assert w.picture.get_paintable()!=before and w.save_button.get_sensitive()
  w.write(p/'output.pdf');state['deadline']=time.monotonic()+10;GLib.timeout_add(100,check)
 except Exception as exc:errors.append(exc);a.quit()
def check():
 w=state['w']
 if w.running and time.monotonic()<state['deadline']:return True
 try:
  assert not w.running
  with fitz.open(p/'output.pdf') as doc:
   assert all('Seite '+str(i+3) in page.get_text() for i,page in enumerate(doc))
  assert source.read_bytes()==raw
  w.text.set_text('');w.render();assert not w.save_button.get_sensitive()
  w.close()
 except Exception as exc:errors.append(exc)
 app.quit();return False
app.connect('activate',activate);app.run([]);tmp.cleanup()
assert not errors,errors
print('PASS: live settings, page selection, export all pages, source unchanged, empty text blocked')
