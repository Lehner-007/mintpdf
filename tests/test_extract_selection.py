import sys,tempfile,json,zipfile,time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,mintpdf,pymupdf as fitz,gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
root=Path(__file__).resolve().parents[1];tmp=tempfile.TemporaryDirectory(dir=root/'work');folder=Path(tmp.name);source=folder/'source.pdf'
with fitz.open() as doc:
 page=doc.new_page();images=[]
 for color in (30,200):
  pix=fitz.Pixmap(fitz.csRGB,fitz.IRect(0,0,120,80),False);pix.clear_with(color);images.append(pix.tobytes('png'))
 xref=page.insert_image(fitz.Rect(20,20,140,100),stream=images[0]);page.insert_image(fitz.Rect(20,120,140,200),stream=images[1])
 page=doc.new_page();page.insert_image(fitz.Rect(20,20,140,100),xref=xref);doc.save(source)
raw=source.read_bytes();items=core.pdf_image_choices(raw);assert len(items)==2 and items[0]['pages']==[1,2]
try:core.process('extract_images',[source],folder/'bad.zip',{'image_xrefs':[]});raise AssertionError('empty accepted')
except ValueError:assert not (folder/'bad.zip').exists()
errors=[];messages=[];state={};tr=json.loads((root/'languages/de.json').read_text());app=Gtk.Application(application_id='eu.dogtruck.mintpdf.extracttest')
def activate(a):
 win=Gtk.ApplicationWindow(application=a);win.present();owner=SimpleNamespace(window=win,tr=lambda k:tr.get(k,k),config={},busy=False,function_states={},apply_function_states=lambda *_:None,check_tools=lambda:None,error=errors.append,message=lambda *v:messages.append(v))
 state['editor']=mintpdf.open_image_extractor(owner,str(source));state['deadline']=time.monotonic()+10;GLib.timeout_add(100,ready)
def ready():
 e=state['editor']
 if e.loading:
  if time.monotonic()<state['deadline']:return True
  errors.append('timeout');app.quit();return False
 try:
  assert len(e.checks)==2 and not e.actions.lookup_action('save').get_enabled()
  e.select(True);assert all(c.get_active() for c in e.checks.values())
  e.select(False);assert not e.actions.lookup_action('save').get_enabled()
  selected=list(e.checks)[1];state['selected']=selected;e.checks[selected].set_active(True);assert e.actions.lookup_action('save').get_enabled()
  e.write(folder/'selected.zip');GLib.timeout_add(100,finished)
 except Exception as exc:errors.append(exc);app.quit()
 return False
def finished():
 if state['editor'].running:return True
 try:
  assert not errors and messages,(errors,messages)
  with zipfile.ZipFile(folder/'selected.zip') as archive:
   assert len(archive.namelist())==1 and archive.namelist()[0].startswith('image-'+str(state['selected'])+'.')
  assert source.read_bytes()==raw
  core.process('extract_images',[source],folder/'all.zip')
  with zipfile.ZipFile(folder/'all.zip') as archive:assert len(archive.namelist())==2
  print('PASS: previews, reused image page references, empty/all/individual selection, selected ZIP, unchanged source, CLI all images')
 except Exception as exc:errors.append(exc)
 app.quit();return False
app.connect('activate',activate);app.run([]);tmp.cleanup()
if errors:raise AssertionError(errors)
