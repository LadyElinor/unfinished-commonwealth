"""Safe extraction, including aliased temporary-directory roots."""

import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from scripts.package import extract_source


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "source.tar.gz"

    def make_archive(self, name, kind=tarfile.REGTYPE):
        with tarfile.open(self.archive, "w:gz") as archive:
            item = tarfile.TarInfo(name)
            item.type = kind
            if kind == tarfile.REGTYPE:
                item.size = 4
                archive.addfile(item, io.BytesIO(b"safe"))
            else:
                item.linkname = "../outside"
                archive.addfile(item)

    def test_extract_regular_file(self):
        self.make_archive("package/README.md")
        extracted = extract_source(self.archive, self.root / "out")
        self.assertEqual((extracted / "package/README.md").read_bytes(), b"safe")

    def test_normalize_aliased_extraction_root(self):
        real = self.root / "real"
        real.mkdir()
        alias = self.root / "alias"
        try:
            alias.symlink_to(real, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Creating directory aliases requires privileges on this host")
        self.make_archive("package/README.md")
        extracted = extract_source(self.archive, alias / "out")
        self.assertEqual(extracted, (real / "out").resolve())
        self.assertEqual((extracted / "package/README.md").read_bytes(), b"safe")

    def test_reject_parent_traversal(self):
        self.make_archive("../escaped.txt")
        with self.assertRaisesRegex(RuntimeError, "unsafe source-archive member"):
            extract_source(self.archive, self.root / "out")
        self.assertFalse((self.root / "escaped.txt").exists())

    def test_reject_absolute_member(self):
        escaped = (self.root / "escaped.txt").resolve()
        self.make_archive(escaped.as_posix())
        with self.assertRaisesRegex(RuntimeError, "unsafe source-archive member"):
            extract_source(self.archive, self.root / "out")
        self.assertFalse(escaped.exists())

    def test_reject_symbolic_and_hard_links(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            with self.subTest(kind=kind):
                self.make_archive("package/link", kind)
                with self.assertRaisesRegex(RuntimeError, "unsafe source-archive member"):
                    extract_source(self.archive, self.root / "out")


if __name__ == "__main__":
    unittest.main()
