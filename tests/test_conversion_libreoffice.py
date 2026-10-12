"""Optional real LibreOffice roundtrip; core conversion has its own test."""
import shutil
import tempfile
import unittest
from pathlib import Path
import core
import pymupdf as fitz

class LibreOfficeConversion(unittest.TestCase):
 @unittest.skipUnless(shutil.which('libreoffice'), 'LibreOffice-Roundtrip benötigt libreoffice im PATH')
 def test_odt_roundtrip(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as folder:
   p=Path(folder);source=p/'source.pdf';out=p/'export.odt'
   with fitz.open() as doc:
    doc.new_page().insert_text((50,50),'First page')
    doc.new_page().insert_text((50,50),'Second page')
    doc.save(source)
   raw=source.read_bytes()
   core.process('convert',[source],out,{'convert_format':'odt'})
   core.run_command([shutil.which('libreoffice'),f'-env:UserInstallation={(p/"profile").as_uri()}',
                     '--headless','--convert-to','txt:Text','--outdir',str(p),str(out)])
   text=(p/'export.txt').read_text()
   self.assertIn('First page',text)
   self.assertIn('Second page',text)
   self.assertEqual(source.read_bytes(),raw)

if __name__=='__main__':unittest.main()
