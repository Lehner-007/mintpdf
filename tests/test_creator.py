import sys,tempfile,json,time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,mintpdf,pymupdf as fitz,gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
root=Path(__file__).resolve().parents[1];tmp=tempfile.TemporaryDirectory(dir=root/'work');p=Path(tmp.name);errors=[];state={};tr=json.loads((root/'languages/de.json').read_text());app=Gtk.Application(application_id='eu.dogtruck.creatortest')
def activate(a):
 try:
  owner=SimpleNamespace(window=Gtk.ApplicationWindow(application=a),tr=lambda k:tr.get(k,k),config={},error=errors.append)
  w=mintpdf.open_creator(owner);state['w']=w;w.add_text();w.text.get_buffer().set_text('Editor test');w.render();assert w.valid
  w.add_page();w.add_text();w.text.get_buffer().set_text('Second page');w.move_page(-1);w.move_page(1)
  image=fitz.Pixmap(fitz.csRGB,fitz.IRect(0,0,120,40),False);image.clear_with(80);w.new_item('image',image.tobytes('png'));w.item()['y']=300;w.select_fields();w.numbers.set_active(True);w.watermark.set_text('TEST');w.render()
  state['deadline']=time.monotonic()+10;GLib.timeout_add(100,check)
 except Exception as exc:errors.append(exc);a.quit()
def check():
 w=state['w']
 try:
  if 'saved' not in state:
   bounds=w.bounds();assert bounds
   left,top,sx,sy=bounds;item=w.item();x=left+(item['x']+item['w']/2)*sx;y=top+(item['y']+item['h']/2)*sy
   w.drag_begin(None,x,y);w.drag_update(None,10*sx,20*sy);w.render();assert w.valid
   old=w.item()['w'];item=w.item();w.drag_begin(None,left+(item['x']+item['w'])*sx,top+(item['y']+item['h'])*sy);w.drag_update(None,item['w']*sx*.2,item['h']*sy*.2);assert w.item()['w']>old
   w.render();w.write(p/'created.pdf');state['saved']=True;return True
  if w.running and time.monotonic()<state['deadline']:return True
  with fitz.open(p/'created.pdf') as doc:
   assert len(doc)==2 and 'Editor test' in doc[0].get_text() and 'Second page' in doc[1].get_text()
   assert doc[1].get_images() and 'Seite 2' in doc[1].get_text()
  w.close()
 except Exception as exc:errors.append(exc)
 app.quit();return False
app.connect('activate',activate);app.run([]);tmp.cleanup();assert not errors,errors
try:core.create_document([{'width':595,'height':842,'items':[{'kind':'text','x':1,'y':1,'w':30,'h':5,'text':'Too long text','size':30}]}])
except ValueError as exc:assert str(exc)=='E_EDITOR_TEXT_FIT'
else:raise AssertionError('Text overflow')
print('PASS: editor GUI, multiple pages/reorder, text, image move/resize, watermark/numbers, export, overflow')
