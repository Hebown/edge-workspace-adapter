import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapter import leveldb_reader as lr  # noqa: E402
from adapter import leveldb_writer as lw  # noqa: E402


class LevelDbTests(unittest.TestCase):
    def test_crc32c_known_vector(self):
        self.assertEqual(lw.crc32c(b'123456789'), 0xE3069283)

    def test_write_batch_roundtrip(self):
        puts = [(b'edge_workspace-dt-test', b'\x08\x01\x12\x02ab')]
        batch = lw.build_batch(4242, puts)
        decoded = list(lr._log_batch(batch))
        self.assertEqual(decoded, [(4242, False, puts[0][0], puts[0][1])])

    def test_log_framing_roundtrip(self):
        payload = lw.build_batch(7, [(b'k', b'v' * 100), (b'k2', b'w')])
        framed = lw._records(payload)
        records = list(lr._log_records(framed))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0], payload)

    def test_log_framing_splits_large_batch(self):
        payload = lw.build_batch(7, [(b'k', b'v' * 40000)])
        framed = lw._records(payload)
        self.assertGreater(len(framed), 32768)          # physically split across blocks
        records = list(lr._log_records(framed))
        self.assertEqual(b''.join(records), payload)    # logically reassembled

    def test_varint(self):
        self.assertEqual(lr.read_varint(lw._varint(300), 0), (300, 2))


if __name__ == '__main__':
    unittest.main()
