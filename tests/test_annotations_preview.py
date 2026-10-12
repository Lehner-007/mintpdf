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
raw=source.read_bytes();errors=[];tr=json.loads((root/'languages/de.json').read_text());app=Gtk.Application(application_id='eu.dogtruck.annotationtest');state={}
def activate(a):
 try:
  owner=SimpleNamespace(window=Gtk.ApplicationWindow(application=a),tr=lambda k:tr.get(k,k),config={},error=errors.append)
  w=mintpdf.open_annotations(owner,source);state['w']=w
  w.text.set_text('Testnotiz');w.render();before=w.picture.get_paintable()
  w.fields['note_x'].set_value(20);w.fields['note_y'].set_value(10);w.page.set_value(2);w.render()
  assert w.picture.get_paintable()!=before and w.save_button.get_sensitive()
  
  deadline=time.monotonic()+2
  while time.monotonic()<deadline and w.picture.get_width()<=1:
   GLib.MainContext.default().iteration(False)
  bounds=w.page_bounds();assert bounds
  left,top,width,height=bounds
  w.drag_begin(w.drag,left+width*.25,top+height*.3)
  w.drag_update(w.drag,width*.2,height*.1)
  assert abs(w.fields['note_x'].get_value()-45)<.01
  assert abs(w.fields['note_y'].get_value()-40)<.01
  w.render();w.write(p/'output.pdf');state['deadline']=time.monotonic()+10;GLib.timeout_add(100,check)
 except Exception as exc:errors.append(exc);a.quit()
def check():
 w=state['w']
 if w.running and time.monotonic()<state['deadline']:return True
 try:
  assert not w.running
  with fitz.open(p/'output.pdf') as doc:
   assert not list(doc[0].annots() or [])
   page=doc[1];note=list(page.annots())[0]
   assert note.info['content']=='Testnotiz'
   assert abs(note.rect.x0/page.rect.width-.45)<.02
   assert abs(note.rect.y0/page.rect.height-.4)<.02
  assert source.read_bytes()==raw
  w.text.set_text('');w.render();assert not w.save_button.get_sensitive()
  w.close()
 except Exception as exc:errors.append(exc)
 app.quit();return False
app.connect('activate',activate);app.run([]);tmp.cleanup()
assert not errors,errors
print('PASS: live settings, page selection, export all pages, source unchanged, empty text blocked')
