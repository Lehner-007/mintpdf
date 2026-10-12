import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,mintpdf,pymupdf as fitz
with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as folder:
 p=Path(folder);source=p/'source.pdf';target=p/'text.txt'
 with fitz.open() as doc:
  doc.new_page().insert_text((50,70),'First page')
  doc.new_page().insert_text((50,70),'Second page')
  doc.save(source)
 raw=source.read_bytes();core.process('text_extract',[source],target)
 text=target.read_text(encoding='utf-8');assert 'First page' in text and 'Second page' in text and '\f' in text
 assert source.read_bytes()==raw
 try:core.process('text_extract',[source],target)
 except FileExistsError:pass
 else:raise AssertionError('Existing target overwritten')
 empty=p/'empty.pdf'
 with fitz.open() as doc:doc.new_page();doc.save(empty)
 try:core.process('text_extract',[empty],p/'empty.txt')
 except ValueError as exc:assert str(exc)=='E_TEXT_EMPTY'
 else:raise AssertionError('Empty scan accepted')
 assert not (p/'empty.txt').exists()
 assert mintpdf.output_suggestion('text_extract',p).suffix=='.txt'
 assert core.can_dispatch('convert')[0]
print('PASS: text export, page separation, immutable source, existing target protection, scan warning, catalog')
