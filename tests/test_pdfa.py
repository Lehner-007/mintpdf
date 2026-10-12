import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import core
import pymupdf

class PdfaTests(unittest.TestCase):
 @unittest.skipUnless(core.available("pdfa"), "Integration benötigt Ghostscript, veraPDF und PyMuPDF")
 def test_conversion_and_protected_original(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as tmp:
   root=Path(tmp);source=root/'source.pdf';target=root/'archive.pdf'
   with pymupdf.open() as doc:
    doc.new_page().insert_text((50,50),'Archive sample');doc.save(source)
   digest=hashlib.sha256(source.read_bytes()).digest()
   core.process('pdfa',[str(source)],target)
   with pymupdf.open(target) as doc:
    self.assertEqual(len(doc),1)
    self.assertIn('Archive sample',doc[0].get_text())
    metadata=ET.fromstring(doc.get_xml_metadata())
    ns='{http://www.aiim.org/pdfa/ns/id/}'
    self.assertTrue(any(e.get(ns+'part')=='2' and e.get(ns+'conformance')=='B' for e in metadata.iter()))
    self.assertIn('OutputIntents',doc.xref_object(doc.pdf_catalog()))
   self.assertEqual(digest,hashlib.sha256(source.read_bytes()).digest())
   with self.assertRaises(FileExistsError):core.process('pdfa',[str(source)],target)
   with patch('core.shutil.which',return_value=None):
    self.assertFalse(core.can_dispatch('pdfa')[0])
    with self.assertRaisesRegex(RuntimeError,'E_DEP'):core.process('pdfa',[str(source)],root/'missing.pdf')
   invalid=root/'invalid.pdf';invalid.write_bytes(b'not a pdf')
   with self.assertRaisesRegex(ValueError,'E_INPUT'):core.process('pdfa',[str(invalid)],root/'bad.pdf')
   self.assertFalse((root/'bad.pdf').exists())
 def test_missing_dependencies_without_integration_tools(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as tmp:
   source=Path(tmp)/'source.pdf';target=Path(tmp)/'missing.pdf'
   with pymupdf.open() as doc:
    doc.new_page();doc.save(source)
   with patch('core.shutil.which',return_value=None):
    self.assertFalse(core.can_dispatch('pdfa')[0])
    with self.assertRaisesRegex(RuntimeError,'E_DEP'):
     core.process('pdfa',[str(source)],target)
   self.assertFalse(target.exists())
 def test_dedicated_icons(self):
  root=Path(__file__).resolve().parents[1]
  for key in ('form','pdfa'):
   self.assertEqual(core.FUNCTION_BY_ID[key].icon,key)
   self.assertTrue(any((root/'resources'/f'{key}.{ext}').is_file() for ext in ('png','svg')))
