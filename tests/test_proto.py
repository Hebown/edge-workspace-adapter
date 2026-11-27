import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapter import workspace_proto as wp  # noqa: E402


def make_record(name='Test Space', emoji='📁', color=0xFF8CABE4):
    details = [(1, 2, name.encode()), (2, 0, color), (3, 0, 12345), (6, 0, 0)]
    if emoji is not None:
        details.append((9, 2, emoji.encode()))
    spec = [(1, 2, b'11111111-1111-4111-8111-111111111111'), (2, 0, 1), (3, 0, 2),
            (4, 2, wp.encode_fields(details))]
    return wp.encode_fields([(1, 0, 1), (2, 2, wp.encode_fields(spec)), (3, 2, wp.encode_fields([(1, 0, 0)]))])


class ProtoTests(unittest.TestCase):
    def test_varint_roundtrip(self):
        for n in (0, 1, 127, 128, 16383, 2 ** 40, 2 ** 54 + 7):
            fd = wp.parse_fields(wp.encode_field(5, 0, n))
            self.assertEqual(fd[0][2], n)

    def test_decode_fields(self):
        rec = wp.WorkspaceRecord(make_record())
        self.assertEqual(rec.name, 'Test Space')
        self.assertEqual(rec.emoji, '📁')
        self.assertEqual(rec.color, 0xFF8CABE4)
        self.assertEqual(rec.workspace_id, '11111111-1111-4111-8111-111111111111')

    def test_remove_emoji_keeps_everything_else(self):
        raw = make_record()
        out = wp.WorkspaceRecord(raw).set_emoji(None)
        rec = wp.WorkspaceRecord(out)
        self.assertFalse(rec.has_emoji_field)
        self.assertEqual(rec.name, 'Test Space')
        self.assertEqual(rec.color, 0xFF8CABE4)
        self.assertEqual(rec.last_used_us, 12345)
        self.assertLess(len(out), len(raw))

    def test_set_emoji_is_idempotent(self):
        raw = make_record(emoji=None)
        out = wp.WorkspaceRecord(raw).set_emoji('📁')
        self.assertEqual(wp.WorkspaceRecord(out).emoji, '📁')
        self.assertEqual(out, make_record())

    def test_tab_record_is_not_a_workspace(self):
        tab = wp.encode_fields([(2, 2, wp.encode_fields(
            [(1, 2, b'x'), (5, 2, wp.encode_fields([(3, 2, b'https://example.test')]))]))])
        with self.assertRaises(ValueError):
            wp.WorkspaceRecord(tab)


if __name__ == '__main__':
    unittest.main()
