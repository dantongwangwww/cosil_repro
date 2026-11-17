"""Synthetic archive/identity/isolation contracts, not benchmark examples."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from .common import safe_path,write,read
from .prepare import extract


class PreparationTests(unittest.TestCase):
    def test_safe_relative_only(self):
        for path in ('/a.java','../a.java','x/../a.java','x\\a.java',''):
            with self.assertRaises(ValueError):safe_path(path)

    def archive(self,path,rows):
        with tarfile.open(path,'w:gz') as t:
            for name,raw,kind in rows:
                m=tarfile.TarInfo(name);m.size=len(raw);m.type=kind
                t.addfile(m,io.BytesIO(raw) if kind==tarfile.REGTYPE else None)

    def test_archive_keeps_java_bytes_only(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);raw=b'class A { }\r\n'
            self.archive(p/'a.tgz',[('root/src/A.java',raw,tarfile.REGTYPE),('root/gold.json',b'private',tarfile.REGTYPE)])
            hashes=extract(p/'a.tgz',p/'snapshot')
            self.assertEqual(set(hashes),{'src/A.java'});self.assertEqual((p/'snapshot/src/A.java').read_bytes(),raw)
            self.assertFalse((p/'snapshot/gold.json').exists())

    def test_archive_rejects_symlink_and_traversal(self):
        for name,kind in [('root/../A.java',tarfile.REGTYPE),('root/A.java',tarfile.SYMTYPE)]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as td:
                p=Path(td);self.archive(p/'a.tgz',[(name,b'',kind)])
                with self.assertRaises(ValueError):extract(p/'a.tgz',p/'snapshot')
                self.assertFalse((p/'snapshot').exists())

    def test_archive_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'snapshot').mkdir();(p/'snapshot/old.java').write_text('old')
            with self.assertRaises(FileExistsError):extract(p/'missing',p/'snapshot')
            self.assertEqual((p/'snapshot/old.java').read_text(),'old')

    def test_frozen_artifact_rejects_drift(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'f.json';write(p,{'x':1});write(p,{'x':1})
            with self.assertRaises(ValueError):write(p,{'x':2})
            self.assertEqual(read(p),{'x':1})


if __name__=='__main__':unittest.main()
