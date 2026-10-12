import sys,tempfile,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,pymupdf as fitz
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'work') as folder:
 p=Path(folder);source=p/'source.pdf'
 with fitz.open() as doc:
  doc.new_page().insert_text((50,50),'First page')
  doc.new_page().insert_text((50,50),'Second page')
  doc[0].insert_link({'kind':fitz.LINK_URI,'from':fitz.Rect(45,35,120,55),'uri':'https://example.org/?a=1&b=2'})
  doc.save(source)
 raw=source.read_bytes()
 for format in ('txt','html','odt','png','jpg'):
  out=p/(format+core.conversion_suffix(format));core.process('convert',[source],out,{'convert_format':format,'image_dpi':72})
  assert out.exists()
  if format in ('txt','html'):assert 'First page' in out.read_text() and 'Second page' in out.read_text()
  if format=='html':assert 'data:image/png;base64,' in out.read_text();assert 'color:transparent' in out.read_text();assert 'section > div {position:relative;' in out.read_text();assert 'z-index:10' in out.read_text();assert 'href="https://example.org/?a=1&amp;b=2"' in out.read_text()
  elif format=='odt':
   with zipfile.ZipFile(out) as z:
    assert z.namelist()[0]=='mimetype';ET.fromstring(z.read('content.xml'));assert b'xlink:href="https://example.org/?a=1&amp;b=2"' in z.read('content.xml');assert b'First page' in z.read('content.xml')
  elif format in ('png','jpg'):
   with zipfile.ZipFile(out) as z:
    assert len(z.namelist())==2
    for name in z.namelist():assert fitz.Pixmap(z.read(name)).width==595
  try:core.process('convert',[source],out,{'convert_format':format})
  except FileExistsError:pass
  else:raise AssertionError('overwrite')
 assert source.read_bytes()==raw
print('PASS: all 5 core conversion formats, ODT structure/links, numbered image pages, source/target protection')
