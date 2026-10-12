import sys, unittest, tempfile, hashlib, zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,pymupdf
catalog=core
class CatalogTests(unittest.TestCase):
 def test_catalog_integrity(self):
  self.assertEqual(len(catalog.FUNCTION_BY_ID),32)
  self.assertEqual(set(core.BY_ID)-{'sign','signature_image','text_extract','pdf_images'},{f.id for f in catalog.FUNCTIONS if f.handler})
  for f in catalog.FUNCTIONS:
   if not f.handler:self.assertEqual(catalog.can_dispatch(f.id),(False,'not_implemented',''))
   self.assertFalse(catalog.can_dispatch(f.id,busy=True)[0])
 def test_isolated_missing_and_version(self):
  original=core.available
  with patch.object(core,'available',side_effect=lambda k,**kw:False if k=='ocr' else original(k,**kw)):
   self.assertFalse(catalog.can_dispatch('ocr')[0]);self.assertTrue(catalog.can_dispatch('merge')[0])
  with patch.object(pymupdf,'VersionBind','1.20.0'):
   self.assertEqual(catalog.can_dispatch('merge')[1],'unsupported_version')
 def test_pdf_regressions_and_originals(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/"work") as tmp:
   root=Path(tmp)
   for name,text in [('a','alpha'),('b','beta')]:
    with pymupdf.open() as doc:
     doc.new_page().insert_text((50,50),text);doc.save(root/(name+'.pdf'))
   a,b=root/'a.pdf',root/'b.pdf'; hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (a,b)]
   core.process('merge',[str(a),str(b)],root/'merged.pdf')
   with pymupdf.open(root/'merged.pdf') as doc:self.assertEqual(len(doc),2)
   core.process('sort',[str(root/'merged.pdf')],root/'sorted.pdf',{'pages':'2,1'})
   with pymupdf.open(root/'sorted.pdf') as doc:self.assertIn('beta',doc[0].get_text())
   core.process('rotate',[str(a)],root/'rotated.pdf',{'angle':'90'})
   with pymupdf.open(root/'rotated.pdf') as doc:self.assertEqual(doc[0].rotation,90)
   core.process('split',[str(root/'merged.pdf')],root/'split.zip')
   with zipfile.ZipFile(root/'split.zip') as z:self.assertEqual(len(z.namelist()),2)
   with self.assertRaises(FileExistsError):core.process('merge',[str(a),str(b)],root/'merged.pdf')
   with self.assertRaises(ValueError):core.process('text_extract',[str(a)],root/'crop.pdf')
   self.assertFalse((root/'crop.pdf').exists())
   self.assertEqual(hashes,[hashlib.sha256(p.read_bytes()).hexdigest() for p in (a,b)])
if __name__=='__main__':unittest.main()
