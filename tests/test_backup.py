import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapter import backup  # noqa: E402


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ews-test-')
        self.profile = os.path.join(self.tmp, 'Profile')
        os.makedirs(os.path.join(self.profile, 'Sync Data', 'LevelDB'))
        (Path(self.profile) / 'Sync Data' / 'LevelDB' / 'CURRENT').write_text('MANIFEST-1')
        (Path(self.profile) / 'Preferences').write_text('{}')
        self.root = os.path.join(self.tmp, 'backups')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_and_restore(self):
        path = backup.create(self.root, self.profile, 'unit test')
        self.assertTrue(os.path.isfile(os.path.join(path, 'LevelDB', 'CURRENT')))
        self.assertTrue(os.path.isfile(os.path.join(path, 'manifest.json')))

        current = Path(self.profile) / 'Sync Data' / 'LevelDB' / 'CURRENT'
        current.write_text('CHANGED')
        extra = Path(self.profile) / 'Sync Data' / 'LevelDB' / '000999.log'
        extra.write_bytes(b'new log')

        backup.restore(path, self.profile)
        self.assertEqual(current.read_text(), 'MANIFEST-1')
        self.assertFalse(extra.exists())

    def test_list_backups(self):
        backup.create(self.root, self.profile, 'first')
        backup.create(self.root, self.profile, 'second')
        items = backup.list_backups(self.root)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[-1][2]['note'], 'second')


if __name__ == '__main__':
    unittest.main()
