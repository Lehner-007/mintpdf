import sys,json,tempfile,hashlib
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,mintpdf,pymupdf as fitz,gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
root=Path(__file__).resolve().parents[1]
tmp=tempfile.TemporaryDirectory(dir=root/'work');folder=Path(tmp.name)
pix=fitz.Pixmap(fitz.csRGB,fitz.IRect(0,0,200,100),False);pix.clear_with(120);source=folder/'image.png';source.write_bytes(pix.tobytes('png'));raw=source.read_bytes()
layout=[595,842,30,40,200,100]
data=core.images_layout_pdf([raw],[layout])
with fitz.open(stream=data,filetype='pdf') as d:
 assert list(d[0].get_image_info()[0]['bbox'])==[30,40,230,140]
for bad in [[595,842,550,0,200,100],[595,842,0,0,0,0]]:
 try:core.images_layout_pdf([raw],[bad]);raise AssertionError('invalid accepted')
 except ValueError:pass
base=folder/'base.pdf'
with fitz.open() as doc:
 p=doc.new_page(width=595,height=842);p.insert_text((50,70),'EXISTING PDF CONTENT');p.insert_image(fitz.Rect(20,100,220,200),stream=raw)
 p=doc.new_page(width=400,height=600);p.insert_text((50,70),'SECOND PAGE');p.insert_image(fitz.Rect(20,100,220,200),stream=raw)
 doc.save(base)
base_raw=base.read_bytes()
errors=[];messages=[];state={};translations=json.loads((root/'languages/de.json').read_text())
app=Gtk.Application(application_id='eu.dogtruck.mintpdf.imagecroptest')
def activate(a):
 try:
  win=Gtk.ApplicationWindow(application=a);win.present()
  owner=SimpleNamespace(window=win,tr=lambda k:translations.get(k,k),config={},busy=False,function_states={},apply_function_states=lambda *_:None,check_tools=lambda:None,error=errors.append,message=lambda *v:messages.append(v))
  editor=mintpdf.open_image_layout(owner,[],str(base),existing=True,crop_mode=True);state.update(editor=editor,owner=owner)
  scale=editor.preview_scale;pw,ph,x,y,w,h=editor.layouts[0]
  editor.drag_begin(None,(x+w*.25)*scale,(y+h*.2)*scale);editor.drag_end(None,w*.5*scale,h*.6*scale)
  assert all(abs(a-b)<.001 for a,b in zip(editor.crop_frame,(.25,.2,.75,.8)))
  saved=editor.crop_frame;old_width=editor.surface.get_width();editor.set_zoom(2.)
  assert editor.crop_frame==saved and editor.surface.get_width()>=old_width*2-1
  scale=editor.preview_scale
  editor.drag_begin(None,(x+w*.25)*scale,(y+h*.2)*scale);assert editor.crop_handle=='lt'
  editor.drag_end(None,w*.05*scale,h*.05*scale)
  assert abs(editor.crop_frame[0]-.3)<.001 and abs(editor.crop_frame[1]-.25)<.001
  editor.drag_begin(None,(x+w*.525)*scale,(y+h*.525)*scale);assert editor.crop_handle=='move'
  editor.drag_end(None,w*.05*scale,0);assert abs(editor.crop_frame[0]-.35)<.001
  editor.crop_spins['crop_left'].set_value(w*.25*25.4/72)
  assert abs(editor.crop_frame[0]-.25)<.001
  editor.crop_frame=saved;editor.sync_crop_spins()
  editor.apply_crop();assert editor.crop_frame==(0.,0.,1.,1.)
  p=fitz.Pixmap(editor.sources[0]);assert (p.width,p.height)==(100,60),(p.width,p.height)
  editor.navigate(1);assert not editor.selected
  assert editor.image_pages==[0,1]
  editor.write(folder/'result.pdf');GLib.timeout_add(100,finish)
 except Exception as exc:errors.append(exc);app.quit()
def finish():
 if state['editor'].running:return True
 try:
  assert not errors and messages,(errors,messages)
  with fitz.open(folder/'result.pdf') as doc:
   assert len(doc)==2
   assert 'EXISTING PDF CONTENT' in doc[0].get_text()
   assert 'SECOND PAGE' in doc[1].get_text() and doc[1].get_image_info()
   bbox=doc[0].get_image_info()[0]['bbox'];expected=[v*25.4/72 for v in (70,120,170,180)]
   assert all(abs(a-b*72/25.4)<.01 for a,b in zip(bbox,expected)),bbox
  assert source.read_bytes()==raw and base.read_bytes()==base_raw
  core.process('images_pdf',[source],folder/'cli.pdf')
  with fitz.open(folder/'cli.pdf') as d:assert len(d)==1
  print('PASS: GUI preview, position, aspect ratio, navigation, invalid placement, PDF content, target page, export geometry and legacy conversion')
 except Exception as exc:errors.append(exc)
 app.quit();return False
app.connect('activate',activate);app.run([])
tmp.cleanup()
if errors:raise AssertionError(errors)
