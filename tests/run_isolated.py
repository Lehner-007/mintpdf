"""Isolated tests with explicit requirements and separate pass/skip/fail counts."""
from pathlib import Path
import ast
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
# unittest's exit code alone cannot distinguish success from skipped integration.
UNIT_RUNNER='''import json,sys,unittest
suite=unittest.defaultTestLoader.discover('tests',pattern=sys.argv[1])
result=unittest.TextTestRunner(verbosity=2).run(suite)
print('MINTPDF_TEST_RESULT='+json.dumps(dict(run=result.testsRun,skipped=len(result.skipped),failed=len(result.failures)+len(result.errors))))
sys.exit(not result.wasSuccessful())
'''

def missing_requirements(requirements, env):
 checks={
  'gtk': ('import gi,cairo;gi.require_version("Gtk","4.0");from gi.repository import Gtk;assert Gtk.init_check()',
          'GTK 4, PyGObject, Cairo und erreichbare grafische Sitzung erforderlich'),
  'gio': ('import gi;from gi.repository import Gio', 'PyGObject/Gio erforderlich'),
 }
 reasons=[]
 for requirement in requirements:
  code,reason=checks[requirement]
  result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,capture_output=True,text=True)
  if result.returncode:reasons.append(reason)
 return reasons

def main():
 env=dict(os.environ,PYTHONPATH=str(ROOT))
 manifest=json.loads((ROOT/'tests/test_requirements.json').read_text())
 summary={'passed':[], 'skipped':[], 'failed':[], 'partial':[]}
 tests={'passed':0,'skipped':0,'failed':0}
 for path in sorted((ROOT/'tests').glob('test_*.py')):
  if path.name not in manifest:
   summary['failed'].append(path.name)
   print(f'{path.name}: FAIL (Testvoraussetzungen nicht deklariert)',flush=True)
   continue
  missing=missing_requirements(manifest[path.name],env)
  if missing:
   summary['skipped'].append(path.name)
   print(f'{path.name}: SKIP ({"; ".join(missing)})',flush=True)
   continue
  tree=ast.parse(path.read_text())
  unit=any(isinstance(node,ast.ClassDef) and any(isinstance(base,ast.Attribute) and base.attr=='TestCase' for base in node.bases) for node in tree.body)
  command=[sys.executable,'-c',UNIT_RUNNER,path.name] if unit else [sys.executable,str(path)]
  result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
  print(result.stdout,end='',flush=True)
  print(result.stderr,end='',file=sys.stderr,flush=True)
  record=next((line.split('=',1)[1] for line in result.stdout.splitlines() if line.startswith('MINTPDF_TEST_RESULT=')),None) if unit else None
  if record is not None:
   counts=json.loads(record)
   tests['passed']+=counts['run']-counts['skipped']-counts['failed']
   tests['skipped']+=counts['skipped'];tests['failed']+=counts['failed']
  if result.returncode:
   summary['failed'].append(path.name)
   print(f'{path.name}: FAIL (Prozessstatus {result.returncode})',flush=True)
  elif unit:
   if record is None:
    summary['failed'].append(path.name)
    print(f'{path.name}: FAIL (kein strukturiertes Testergebnis)',flush=True)
    continue
   category='skipped' if counts['run']==counts['skipped'] else 'partial' if counts['skipped'] else 'passed'
   summary[category].append(path.name)
   print(f'{path.name}: {category.upper()} ({counts})',flush=True)
  else:
   summary['passed'].append(path.name)
   print(f'{path.name}: PASS (Skript-Assertions ausgeführt; keine Einzeltestzählung)',flush=True)
 print('Module: '+json.dumps(summary,ensure_ascii=False),flush=True)
 print('unittest-Einzeltests (Skript-Assertions separat): '+json.dumps(tests),flush=True)
 return bool(summary['failed'])

if __name__=='__main__':sys.exit(main())
