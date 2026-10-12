from pathlib import Path
import tempfile,unittest
import core,pymupdf
class DocumentInfoTests(unittest.TestCase):
 def test_properties_and_original(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as tmp:
   path=Path(tmp)/'sample.pdf'
   with pymupdf.open() as doc:
    p=doc.new_page(width=595.276,height=841.89)
    p.insert_link({'kind':pymupdf.LINK_URI,'from':pymupdf.Rect(10,10,90,30),'uri':'https://example.org'})
    doc.set_metadata({'title':'Test title','author':'Josef','creationDate':"D:20261012060000Z"});doc.save(path)
   before=path.read_bytes();data=core.process('document_info',[str(path)],None)
   self.assertEqual(data['pages'],1);self.assertEqual(data['links'],1)
   self.assertEqual(data['title'],'Test title');self.assertEqual(data['author'],'Josef')
   self.assertEqual(data['created'],'12.10.2026 08:00:00')
   self.assertEqual(data['page_sizes'][0]['width'],210)
   self.assertFalse(data['encrypted']);self.assertEqual(path.read_bytes(),before)
   with pymupdf.open(path) as doc:doc.save(Path(tmp)/'locked.pdf',encryption=pymupdf.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw='secret')
   with self.assertRaisesRegex(ValueError,'E_PASSWORD'):core.document_information(Path(tmp)/'locked.pdf')
 def test_dates(self):
  self.assertEqual(core.pdf_display_date('D:2026'),'01.01.2026 00:00:00')
  self.assertEqual(core.pdf_display_date("D:20261012090000+03'00'"),'12.10.2026 08:00:00')
  self.assertEqual(core.pdf_display_date('D:20261399'),'')
  self.assertEqual(core.pdf_display_date(None),'')
