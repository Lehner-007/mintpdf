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
 p=doc.new_page(width=595,height=842);p.insert_text((50,70),'EXISTING PDF CONTENT')
 p=doc.new_page(width=400,height=600);p.insert_text((50,70),'SECOND PAGE')
 doc.save(base)
base_raw=base.read_bytes()
errors=[];messages=[];state={};translations=json.loads((root/'languages/de.json').read_text())
app=Gtk.Application(application_id='eu.dogtruck.mintpdf.layouttest')
def activate(a):
 win=Gtk.ApplicationWindow(application=a);win.present()
 owner=SimpleNamespace(window=win,tr=lambda k:translations.get(k,k),config={},busy=False,function_states={},apply_function_states=lambda *_:None,check_tools=lambda:None,error=errors.append,message=lambda *v:messages.append(v))
 editor=mintpdf.open_image_layout(owner,[str(source),str(source)],str(base));state.update(editor=editor,owner=owner)
 editor.spins['layout_x'].set_value(10);editor.spins['layout_y'].set_value(20);editor.spins['layout_width'].set_value(50)
 assert editor.valid and abs(editor.layouts[0][5]-25*72/25.4)<.001
 editor.navigate(1);editor.page_choice.set_selected(1);assert editor.layouts[1][:2]==[400.,600.];editor.navigate(-1);assert abs(editor.spins['layout_x'].get_value()-10)<.01
 editor.spins['layout_width'].set_value(1000);assert not editor.valid and not editor.actions.lookup_action('save').get_enabled()
 editor.spins['layout_width'].set_value(50);assert editor.valid
 scale=editor.preview_scale;x,y=editor.layouts[0][2:4]
 editor.drag_begin(None,0,0);editor.drag_update(None,100,100);assert editor.layouts[0][2:4]==[x,y]
 editor.drag_begin(None,(x+40)*scale,(y+30)*scale);editor.drag_update(None,20*scale,30*scale)
 assert abs(editor.layouts[0][2]-x-20)<.01 and abs(editor.layouts[0][3]-y-30)<.01
 assert abs(editor.spins['layout_x'].get_value()-(x+20)*25.4/72)<.01
 editor.drag_end(None,9999,9999);pw,ph,left,top,w,h=editor.layouts[0];assert abs(left+w-pw)<.01 and abs(top+h-ph)<.01
 editor.running=True;editor.drag_begin(None,left*scale,top*scale);assert editor.drag_origin is None;editor.running=False
 editor.spins['layout_x'].set_value(10);editor.spins['layout_y'].set_value(20)
 for sx,sy in ((-1,-1),(1,-1),(-1,1),(1,1)):
  pw,ph,x,y,w,h=editor.layouts[0];ax=x+(w if sx<0 else 0);ay=y+(h if sy<0 else 0)
  editor.drag_begin(None,(x+(w if sx>0 else 0))*scale,(y+(h if sy>0 else 0))*scale)
  editor.drag_end(None,sx*10*scale,sy*5*scale)
  _,_,nx,ny,nw,nh=editor.layouts[0]
  assert abs(nw-w-10)<.01 and abs(nh/nw-.5)<.001
  assert abs(nx+(nw if sx<0 else 0)-ax)<.01 and abs(ny+(nh if sy<0 else 0)-ay)<.01
  assert abs(editor.spins['layout_width'].get_value()-nw*25.4/72)<.01
 editor.spins['layout_width'].set_value(50);editor.spins['layout_x'].set_value(10);editor.spins['layout_y'].set_value(20)
 editor.write(folder/'result.pdf');GLib.timeout_add(100,finish)
def finish():
 if state['editor'].running:return True
 try:
  assert not errors and messages,(errors,messages)
  with fitz.open(folder/'result.pdf') as doc:
   assert len(doc)==2
   assert 'EXISTING PDF CONTENT' in doc[0].get_text()
   assert 'SECOND PAGE' in doc[1].get_text() and doc[1].get_image_info()
   bbox=doc[0].get_image_info()[0]['bbox'];expected=[10,20,60,45]
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
