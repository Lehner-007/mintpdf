from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import core,pymupdf

class ValidationTests(unittest.TestCase):
 @unittest.skipUnless(core.available("pdfa"), "Integration benötigt Ghostscript, veraPDF und PyMuPDF")
 def test_real_validator_before_and_after_conversion(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as tmp:
   root=Path(tmp);source=root/'ordinary.pdf';out=root/'archive.pdf'
   with pymupdf.open() as doc:
    doc.new_page().insert_text((50,50),'PDF/A validation sample');doc.save(source)
   original=source.read_bytes()
   with self.assertRaisesRegex(RuntimeError,'E_PDFA_INVALID'):
    core.process('pdfa_check',[str(source)],None)
   self.assertEqual(source.read_bytes(),original)
   core.process('pdfa',[str(source)],out)
   data=out.read_bytes()
   self.assertEqual(core.process('pdfa_check',[str(out)],None),'PDF/A-2b')
   self.assertEqual(out.read_bytes(),data)
   for error in ('E_PDFA_INVALID','E_PDFA_VALIDATION','E_CANCELLED'):
    target=root/(error+'.pdf')
    with patch.object(core,'validate_pdfa',side_effect=RuntimeError(error)):
     with self.assertRaisesRegex(RuntimeError,error):core.process('pdfa',[str(source)],target)
    self.assertFalse(target.exists())
 def test_missing_validator_and_broken_report(self):
  with patch.object(core,'validator_command',return_value=None):
   for key in ('pdfa','pdfa_check'):self.assertFalse(core.available(key))
   with self.assertRaisesRegex(RuntimeError,'E_PDFA_VALIDATOR'):core.validate_pdfa('sample.pdf')
  with patch.object(core,'validator_command',return_value='/fake/verapdf'):
   for report in (b'',b'not xml',b'<report/>',b'<report><jobs><job><validationReport isCompliant="true"/></job></jobs></report>'):
    with patch.object(core,'run_command',return_value=report):
     with self.assertRaisesRegex(RuntimeError,'E_PDFA_VALIDATION'):core.validate_pdfa('sample.pdf')
   with patch.object(core,'run_command',side_effect=RuntimeError('E_TOOL')):
    with self.assertRaisesRegex(RuntimeError,'E_PDFA_VALIDATION'):core.validate_pdfa('sample.pdf')
 @unittest.skipUnless(core.available("pdfa"), "Integration benötigt Ghostscript, veraPDF und PyMuPDF")
 def test_overprint_and_link_print_flags(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as tmp:
   root=Path(tmp);source=root/'overprint.pdf';out=root/'archive.pdf'
   with pymupdf.open() as doc:
    page=doc.new_page();page.insert_text((50,50),'Overprint link sample')
    page.insert_link({'kind':pymupdf.LINK_URI,'from':pymupdf.Rect(50,35,180,55),'uri':'https://example.org'})
    resource=int(doc.xref_get_key(page.xref,'Resources')[1].split()[0])
    state=doc.get_new_xref();doc.update_object(state,'<< /Type /ExtGState /OPM 1 >>')
    doc.xref_set_key(resource,'ExtGState',f'<< /GS1 {state} 0 R >>')
    stream=page.get_contents()[0];doc.update_stream(stream,b'/GS1 gs\n'+doc.xref_stream(stream))
    doc.save(source)
   original=source.read_bytes()
   core.process('pdfa',[str(source)],out)
   self.assertEqual(core.process('pdfa_check',[str(out)],None),'PDF/A-2b')
   self.assertEqual(source.read_bytes(),original)
   with pymupdf.open(out) as doc:
    self.assertIn('Overprint link sample',doc[0].get_text())
    self.assertEqual(doc[0].get_links()[0]['uri'],'https://example.org')
