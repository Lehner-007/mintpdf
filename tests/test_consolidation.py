"""Regressionen der zusammengeführten Formular-/Optimierungs-/Vergleichsfunktionen."""
import sys, tempfile, unittest, hashlib, subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,pymupdf
ROOT=Path(__file__).resolve().parents[1]
class ConsolidationTests(unittest.TestCase):
 def test_form_optimization_comparison_redaction(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp:
   folder=Path(tmp);source=folder/'source.pdf'
   with pymupdf.open() as doc:
    page=doc.new_page()
    page.insert_text((50,60),'Name:')
    page.draw_rect(pymupdf.Rect(100,45,300,70))
    page.insert_text((50,130),'SECRET alpha')
    doc.save(source)
   original=hashlib.sha256(source.read_bytes()).hexdigest()
   analysis=core.analyse_form(source)
   self.assertEqual(analysis['mode'],'detected')
   core.create_form(source,folder/'form.pdf')
   with pymupdf.open(folder/'form.pdf') as doc:self.assertTrue(list(doc[0].widgets()))
   self.assertEqual(core.analyse_optimization(source)['pages'],1)
   core.process('optimize',[str(source)],folder/'optimized.pdf')
   with pymupdf.open(folder/'optimized.pdf') as doc:self.assertIn('SECRET',doc[0].get_text())
   same=core.compare_documents(source,source,'text');self.assertEqual(same['changed'],0)
   core.redact_regions(source,folder/'redacted.pdf',[(0,(45,110,170,135))])
   with pymupdf.open(folder/'redacted.pdf') as doc:self.assertNotIn('SECRET',doc[0].get_text())
   changed=core.compare_documents(source,folder/'redacted.pdf','text')
   self.assertGreater(changed['changed'],0)
   self.assertTrue(core.comparison_report(changed,lambda key: {'cmp_summary':'Comparison','cmp_method':'Method'}.get(key,key)))
   self.assertEqual(original,hashlib.sha256(source.read_bytes()).hexdigest())
 def test_import_without_optional_pdf_module(self):
  code='''import sys
class Missing:
 def find_spec(self, fullname, path=None, target=None):
  if fullname in ('pymupdf','fitz'):raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0,Missing())
import core,mintpdf
assert not core.can_dispatch('merge')[0]
assert core.can_dispatch('convert')[1]=='tool_missing'
print('lazy imports OK')
'''
  completed=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True)
  self.assertEqual(completed.returncode,0,completed.stderr)
if __name__=='__main__':unittest.main()
