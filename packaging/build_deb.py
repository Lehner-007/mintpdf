"""Build the Mint amd64 package from controlled sources and a pinned wheel."""
import hashlib,os,re,shutil,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
version=re.search(r"VERSION = '([^']+)'",(ROOT/'core.py').read_text())[1]
assert re.fullmatch(r'\d+\.\d+\.\d+',version)
(ROOT/'work').mkdir(exist_ok=True);(ROOT/'dist').mkdir(exist_ok=True)
wheel_dir=ROOT/'work/wheels';wheel_dir.mkdir(exist_ok=True)
wheels=list(wheel_dir.glob('pymupdf-1.28.2-*-manylinux_2_28_x86_64.whl'))
if not wheels:
 subprocess.run(['python3','-m','pip','download','--only-binary=:all:','--no-deps','--platform','manylinux_2_28_x86_64','--python-version','312','--implementation','cp','--abi','abi3','PyMuPDF==1.28.2','-d',str(wheel_dir)],check=True)
 wheels=list(wheel_dir.glob('pymupdf-1.28.2-*-manylinux_2_28_x86_64.whl'))
assert len(wheels)==1
assert hashlib.sha256(wheels[0].read_bytes()).hexdigest()=='397d6715c1f0df7548a92d0afd8ce370fc48fa47aeefac16be2bc04a16a8227f', "Wheel checksum mismatch"
output=ROOT/'dist'/f'mintpdf_{version}_amd64.deb'
if output.exists():raise FileExistsError(output)
with tempfile.TemporaryDirectory(dir=ROOT/'work',prefix='deb-') as tmp:
 stage=Path(tmp);app=stage/'usr/share/mintpdf';app.mkdir(parents=True)
 for name in ['core.py','mintpdf.py','projekt.json']:
  shutil.copy2(ROOT/name,app/name)
 for name in ['assets','resources','languages','help']:
  shutil.copytree(ROOT/name,app/name)
 with zipfile.ZipFile(wheels[0]) as z:z.extractall(app/'vendor')
 docs=stage/'usr/share/doc/mintpdf';docs.mkdir(parents=True)
 for name in ['LICENSE','README.md','CHANGELOG.md']:shutil.copy2(ROOT/name,docs/name)
 shutil.copy2(ROOT/'packaging/user_integration.py',docs/'user_integration.py')
 binary=stage/'usr/bin';binary.mkdir(parents=True)
 launcher=binary/'mintpdf'
 launcher.write_text('#!/bin/sh\nexport PYTHONPATH=/usr/share/mintpdf/vendor\nexec /usr/bin/python3 /usr/share/mintpdf/mintpdf.py "$@"\n');launcher.chmod(0o755)
 applications=stage/'usr/share/applications';applications.mkdir(parents=True)
 shutil.copy2(ROOT/'packaging/mintpdf.desktop',applications/'mintpdf.desktop')
 control=stage/'DEBIAN';control.mkdir()
 (control/'control').write_text(f'''Package: mintpdf
Version: {version}
Architecture: amd64
Maintainer: Josef Lehner <josef@dogtruck.eu>
Depends: python3 (>= 3.12), python3 (<< 3.13), python3-gi, python3-cairo, python3-gi-cairo, python3-packaging, gir1.2-gtk-4.0, libc6 (>= 2.28), libstdc++6
Recommends: ghostscript, libreoffice, ocrmypdf, tesseract-ocr, wkhtmltopdf
Section: office
Priority: optional
Homepage: https://dogtruck.eu
Description: Local PDF tools for Linux Mint
 GTK 4 PDF tools with bundled PyMuPDF 1.28.2. veraPDF is optional
 and must be installed separately for PDF/A validation.
''')
 for name in ['postinst','prerm','postrm']:
  shutil.copy2(ROOT/'packaging'/name,control/name);(control/name).chmod(0o755)
 for path in stage.rglob('*'):
  if path.is_file() and path not in [launcher,control/'postinst',control/'prerm',control/'postrm']:path.chmod(0o644)
 subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(output)],check=True)
 digest=hashlib.sha256(output.read_bytes()).hexdigest()
 output.with_suffix('.deb.sha256').write_text(f'{digest}  {output.name}\n')
 print(output)
