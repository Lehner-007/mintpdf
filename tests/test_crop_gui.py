import sys,traceback,time,json,hashlib
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mintpdf,pymupdf,gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'work'
source=WORK/'crop-gui-source.pdf'
(WORK/'crop-gui-result.pdf').unlink(missing_ok=True)
with pymupdf.open() as doc:
 for w,h in ((500,700),(400,600)):
  p=doc.new_page(width=w,height=h)
  p.draw_rect(pymupdf.Rect(20,20,w-20,h-20),color=(1,0,0),width=3)
  p.insert_text((100,130),'TEST: retained center',fontsize=20)
  p.insert_text((25,h-30),'EDGE: cropped margin',fontsize=12)
 doc.save(source)
original=hashlib.sha256(source.read_bytes()).hexdigest()
errors=[];passed=[];messages=[];state={}
application=Gtk.Application(application_id='eu.dogtruck.mintpdf.crop_test')
translations=json.loads((ROOT/'languages/de.json').read_text())
def activate(application):
 window=Gtk.ApplicationWindow(application=application,title='Crop QA');window.present()
 owner=SimpleNamespace(window=window,tr=lambda key:translations.get(key,key),config={},busy=False,function_states={},apply_function_states=lambda *_:None,check_tools=lambda:None,error=errors.append,message=lambda *args:messages.append(args))
 state['owner']=owner;state['crop']=mintpdf.open_cropper(owner,source);state['deadline']=time.monotonic()+10
 GLib.timeout_add(100,ready)
def ready():
 crop=state['crop']
 if crop.surface is None:
  if time.monotonic()<state['deadline']:return True
  errors.append('Vorschau nicht geladen');application.quit();return False
 try:
  assert crop.surface.get_width()==500
  crop.drag_begin(None,50,70);crop.drag_end(None,350,490)
  assert all(abs(a-b)<.0001 for a,b in zip(crop.frame,(.1,.1,.8,.8)))
  assert crop.actions.lookup_action('crop_save').get_enabled()
  assert abs(crop.spins['crop_left'].get_value()-50*25.4/72)<.01
  crop.apply_all();assert len(crop.rectangles)==2
  crop.navigate(1);assert crop.frame==crop.rectangles[0]
  crop.spins['crop_left'].set_value(2000)
  assert not crop.valid and not crop.actions.lookup_action('crop_save').get_enabled()
  crop.reset();assert crop.valid and 1 not in crop.rectangles and 0 in crop.rectangles
  crop.navigate(-1);crop.set_zoom(.75)
  passed.append('Vorschau, Mausrahmen, mm-Werte, Seitenwechsel, proportional alle Seiten, ungültige Ränder und Rücksetzen geprüft')
  state['deadline']=time.monotonic()+10;GLib.timeout_add(100,snapshot)
 except Exception:errors.append(traceback.format_exc());application.quit()
 return False
def snapshot():
 crop=state['crop']
 if crop.surface is None:
  if time.monotonic()<state['deadline']:return True
  errors.append('Vorschau nach Zoom nicht geladen');application.quit();return False
 try:
  import cairo
  surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,crop.surface.get_width(),crop.surface.get_height())
  ctx=cairo.Context(surface);crop.draw(crop.canvas,ctx,surface.get_width(),surface.get_height())
  surface.write_to_png(str(WORK/'crop-preview.png'))
  crop.write(source)
  GLib.timeout_add(200,failed_save)
 except Exception:errors.append(traceback.format_exc());application.quit()
 return False
def failed_save():
 crop=state['crop']
 if crop.running:return True
 try:
  assert len(errors)==1 and isinstance(errors[0],FileExistsError),errors
  errors.clear();assert not state['owner'].busy and crop.rectangles
  assert hashlib.sha256(source.read_bytes()).hexdigest()==original
  passed.append('Vorhandenes Ziel verweigert; Original und Rahmen erhalten, Oberfläche nach Fehler frei')
  crop.write(WORK/'crop-gui-result.pdf')
  GLib.timeout_add(200,finished)
 except Exception:errors.append(traceback.format_exc());application.quit()
 return False
def finished():
 crop=state['crop']
 if crop.running:return True
 try:
  assert messages and not errors,errors
  assert not crop.alive and not state['owner'].busy
  with pymupdf.open(WORK/'crop-gui-result.pdf') as doc:
   assert abs(doc[0].rect.width-350)<.01 and abs(doc[0].rect.height-490)<.01
   assert doc[1].rect.width==400 and doc[1].rect.height==600
  assert hashlib.sha256(source.read_bytes()).hexdigest()==original
  passed.append('GUI-Verarbeitung erfolgreich, gewünschte Seite zugeschnitten, übrige Seite und Original unverändert')
 except Exception:errors.append(traceback.format_exc())
 application.quit();return False
application.connect('activate',activate);application.run([])
print(json.dumps({'passed':passed,'errors':[str(e) for e in errors]},ensure_ascii=False))
if errors or len(passed)!=3:sys.exit(1)
