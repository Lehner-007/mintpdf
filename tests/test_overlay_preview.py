import sys,tempfile,json,time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,mintpdf,pymupdf as fitz,gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
root=Path(__file__).resolve().parents[1];tmp=tempfile.TemporaryDirectory(dir=root/'work');p=Path(tmp.name);paths=[p/'first.pdf',p/'second.pdf']
for index,path in enumerate(paths):
 with fitz.open() as doc:
  for i in range(2 if index==0 else 1):
   page=doc.new_page(width=400,height=400);page.draw_rect(page.rect,fill=(1,0,0) if index==0 else (0,0,1));page.insert_text((40,40),'BASE' if index==0 else 'LAYER')
  doc.save(path)
raw=[path.read_bytes() for path in paths]
for behind,expected in [(False,(127,0,126)),(True,(255,0,0))]:
 data=core.overlay_documents(*raw,{'overlay_opacity':50,'overlay_behind':behind})
 with fitz.open(stream=data,filetype='pdf') as doc:
  pix=doc[0].get_pixmap();pixel=pix.pixel(200,200)
  assert all(abs(a-b)<4 for a,b in zip(pixel,expected)),pixel
  assert len(doc)==2
with fitz.open(stream=core.overlay_documents(*raw,{'pages':'2','overlay_scale':50,'overlay_angle':90}),filetype='pdf') as doc:
 assert 'LAYER' not in doc[0].get_text() and 'LAYER' in doc[1].get_text()
errors=[];state={};tr=json.loads((root/'languages/de.json').read_text());app=Gtk.Application(application_id='eu.dogtruck.overlaytest')
def activate(a):
 try:
  owner=SimpleNamespace(window=Gtk.ApplicationWindow(application=a),tr=lambda k:tr.get(k,k),config={},error=errors.append)
  w=mintpdf.open_overlay(owner,paths);state.update(w=w,deadline=time.monotonic()+10,stage=0);GLib.timeout_add(100,check)
 except Exception as exc:errors.append(exc);a.quit()
def check():
 w=state['w']
 if (w.rendering or w.pending or not w.save_button.get_sensitive()) and time.monotonic()<state['deadline']:return True
 try:
  assert all(picture.get_paintable() for picture in w.pictures)
  assert w.settings_panel.get_width()==400,w.settings_panel.get_width()
  if state['stage']==0:
   w.set_default_size(1600,900)
   w.swap.set_active(True);w.fields['overlay_opacity'].set_value(50);w.fields['overlay_scale'].set_value(75);w.fields['overlay_angle'].set_value(30);w.pages.set_text('2');w.page.set_value(2);state['stage']=1;return True
  if state['stage']==1:
   w.write(p/'output.pdf');state['stage']=2;return True
  if w.running:return True
  with fitz.open(p/'output.pdf') as doc:assert len(doc)==2
  assert raw==[path.read_bytes() for path in paths]
  w.close()
 except Exception as exc:errors.append(exc)
 app.quit();return False
app.connect('activate',activate);app.run([]);tmp.cleanup();assert not errors,errors
print('PASS: opacity pixels, layer order, selection, transform, 3 GUI previews, export, source protection')
