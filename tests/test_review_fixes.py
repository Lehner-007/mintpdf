import sys,tempfile,threading,time,subprocess,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,pymupdf as fitz
with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as d:
 p=Path(d);source=p/'a.pdf'
 with fitz.open() as doc:doc.new_page();doc.new_page();doc.save(source)
 raw=source.read_bytes()
 for index in (-1,99,1.5,'0',None,True):
  try:core.process('annotations',[source],p/'bad.pdf',{'text':'note','note_page':index})
  except ValueError:pass
  else:raise AssertionError(index)
  assert not (p/'bad.pdf').exists()
 for index in (0,1):core.process('annotations',[source],p/f'n{index}.pdf',{'text':'note','note_page':index})
 event=threading.Event();event.set()
 try:core.process('numbers',[source],p/'cancel.pdf',{'cancel_event':event})
 except RuntimeError as exc:assert str(exc)=='E_CANCELLED'
 else:raise AssertionError('cancel')
 assert not (p/'cancel.pdf').exists() and source.read_bytes()==raw
 event.clear();result=[]
 def job():
  core._job.cancel=event
  try:core.run_command([sys.executable,'-c','import time;time.sleep(60)'])
  except RuntimeError as exc:result.append(str(exc))
 thread=threading.Thread(target=job);thread.start();time.sleep(.15);event.set();thread.join(5)
 assert not thread.is_alive() and result==['E_CANCELLED']
 code="""import sys
class Missing:
 def find_spec(self,fullname,path=None,target=None):
  if fullname in ('gi','cairo'):raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0,Missing())
import core
assert core.available('crop')
assert not core.can_dispatch('crop')[0]
core.process('crop',[sys.argv[1]],sys.argv[2],{'crop_rectangles':{0:(.1,.1,.9,.9)}})
"""
 completed=subprocess.run([sys.executable,'-c',code,str(source),str(p/'crop.pdf')],capture_output=True,text=True)
 assert completed.returncode==0,completed.stderr
print('PASS: dependency separation, invalid annotation pages, originals, cancellation and process reaping')
