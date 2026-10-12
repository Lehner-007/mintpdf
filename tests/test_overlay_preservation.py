"""Backend regression: document information belongs to PDF 1."""
import tempfile
import unittest
from pathlib import Path
import core
import pymupdf as fitz

class OverlayPreservation(unittest.TestCase):
 def test_process_preserves_base_document(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as tmp:
   root=Path(tmp);base=root/'base.pdf';layer=root/'layer.pdf';target=root/'result.pdf'
   with fitz.open() as doc:
    doc.new_page().insert_text((40,40),'Base text')
    doc.set_metadata({'title':'Important title','author':'Author'})
    doc.set_toc([[1,'Chapter',1]])
    doc.embfile_add('note.txt',b'Attachment contents',filename='note.txt')
    doc.save(base)
   with fitz.open() as doc:
    doc.new_page().insert_text((40,80),'Layer text')
    doc.set_metadata({'title':'Conflicting layer'})
    doc.save(layer)
   original=(base.read_bytes(),layer.read_bytes())
   core.process('overlay',[str(base),str(layer)],target)
   with fitz.open(target) as doc:
    self.assertEqual(doc.metadata['title'],'Important title')
    self.assertEqual(doc.metadata['author'],'Author')
    self.assertEqual(doc.get_toc(),[[1,'Chapter',1]])
    self.assertEqual(doc.embfile_get('note.txt'),b'Attachment contents')
    self.assertIn('Base text',doc[0].get_text())
    self.assertIn('Layer text',doc[0].get_text())
   self.assertEqual(original,(base.read_bytes(),layer.read_bytes()))

if __name__=='__main__':unittest.main()
