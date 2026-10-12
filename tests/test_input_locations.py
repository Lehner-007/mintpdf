import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from gi.repository import Gio
from mintpdf import local_input_files

class InputLocations(unittest.TestCase):
 def test_local_path_preserved(self):
  file=Gio.File.new_for_path('/example.pdf')
  self.assertEqual(local_input_files([file],'.'),['/example.pdf'])
 def test_remote_copy_and_failure(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as tmp:
   remote=Mock();remote.get_path.return_value=None;remote.get_basename.return_value='muster.pdf'
   def copy(target,*args):Path(target.get_path()).write_bytes(b'PDF sample')
   remote.copy.side_effect=copy
   paths=local_input_files([remote],tmp)
   self.assertEqual(Path(paths[0]).read_bytes(),b'PDF sample')
   remote.copy.side_effect=OSError('offline')
   with self.assertRaises(OSError):local_input_files([remote],tmp)
