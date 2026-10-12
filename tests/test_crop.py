import sys,hashlib,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,pymupdf
ROOT=Path(__file__).resolve().parents[1]
class CropTests(unittest.TestCase):
 def test_rotations_existing_crop_and_bytes(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp:
   r=Path(tmp);source=r/'source.pdf'
   with pymupdf.open() as doc:
    for rotation in (0,90,180,270):
     page=doc.new_page(width=400,height=600);page.insert_text((150,200),'Keep me')
     page.set_cropbox(pymupdf.Rect(60,80,360,480));page.set_rotation(rotation)
    doc.set_metadata({'title':'Crop regression'});doc.set_toc([[1,'Bookmark',1]]);doc.save(source)
   data=source.read_bytes();digest=hashlib.sha256(data).hexdigest()
   frame=(.1,.2,.8,.9)
   core.crop_pdf(data,r/'cropped.pdf',{i:frame for i in range(4)})
   with pymupdf.open(source) as a,pymupdf.open(r/'cropped.pdf') as b:
    self.assertEqual(b.metadata['title'],'Crop regression');self.assertEqual(b.get_toc(),a.get_toc())
    for before,after in zip(a,b):
     self.assertEqual(before.rotation,after.rotation)
     self.assertAlmostEqual(after.rect.width,before.rect.width*.7,places=3)
     self.assertAlmostEqual(after.rect.height,before.rect.height*.7,places=3)
   core.process('crop',[str(source)],r/'one.pdf',{'crop_rectangles':{1:frame}})
   with pymupdf.open(source) as a,pymupdf.open(r/'one.pdf') as b:
    self.assertEqual(a[0].cropbox,b[0].cropbox);self.assertNotEqual(a[1].cropbox,b[1].cropbox)
   self.assertEqual(digest,hashlib.sha256(source.read_bytes()).hexdigest())
   with self.assertRaises(FileExistsError):core.crop_pdf(source,r/'cropped.pdf',{0:frame})
 def test_invalid_crop_is_atomic(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp:
   r=Path(tmp);source=r/'source.pdf'
   with pymupdf.open() as doc:doc.new_page();doc.save(source)
   for value in ({},{0:(.8,.2,.1,.5)},{0:(0,0,float('nan'),1)},{2:(0,0,.5,.5)},{0:(0,0,1.1,1)}):
    target=r/'invalid.pdf'
    with self.assertRaises(ValueError):core.crop_pdf(source,target,value)
    self.assertFalse(target.exists())
if __name__=='__main__':unittest.main()
