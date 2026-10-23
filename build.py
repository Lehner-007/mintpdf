"""Bereinigte Quellcode-/Bytecode-Pakete erstellen (GPL-3.0-only)."""
from pathlib import Path
import shutil,tempfile,tarfile,py_compile
from core import VERSION
ROOT=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='mintpdf-build-', dir=ROOT/'work') as tmp:
 for kind in ('source','python312'):
  stage=Path(tmp)/kind/f'mintpdf-{VERSION}'
  stage.mkdir(parents=True)
  names=['core.py','mintpdf.py','install.py','build.py','.start.sh','projekt.json','requirements.txt','setup_dependencies.sh','README.md','CHANGELOG.md','LICENSE','THIRD_PARTY_NOTICES.md']
  for name in names:shutil.copy2(ROOT/name,stage/name)
  for name in ('resources','languages','help','assets','vendor'):shutil.copytree(ROOT/name,stage/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo'))
  for name in ('config','logs'):(stage/name).mkdir()
  if kind=='python312':
   for name in ('core','mintpdf'):
    py_compile.compile(str(stage/f'{name}.py'),cfile=str(stage/f'{name}.pyc'),dfile=f'{name}.py',doraise=True)
    (stage/f'{name}.py').unlink()
   (stage/'build.py').unlink()
  (ROOT/'dist').mkdir(exist_ok=True)
  target=ROOT/'dist'/f'mintpdf-{VERSION}-{kind}.tar.gz'
  with tarfile.open(target,'w:gz') as archive:archive.add(stage,arcname=stage.name)
  print(target)
