"""Codec for Edge's `edge_workspace` sync entities.

Everything here was recovered from a live profile; the byte-level evidence is
in research/experiment-results.md.

Two entity families share the `edge_workspace-dt-<id>` key space:

  workspace  spec.field4 = WorkspaceDetails
      Details: 1 name (string)
               2 ARGB colour (uint32, e.g. 0xFF8CABE4)
               3 last-used (us, Windows epoch)
               4 ? (1 on the two newest records)
               5 share payload { 4: base64 of a 20-byte doc id }
               6 0/1   (1 == shared with someone)
               8 0/1
               9 EMOJI (string)      <-- the icon field
              10 small int (3 on one record)

  tab        spec.field5 = TabDetails
      Details: 1 parent workspace id, 2 {4: bytes}, 3 url, 4 title, 5 favicon

Presence of an emoji string is what switches the rendered workspace icon from
the bundled "stacked rectangles" glyph to an emoji bitmap.
"""

from __future__ import annotations

WORKSPACE_DETAILS = 4
TAB_DETAILS = 5
EMOJI_FIELD = 9


# ---------------------------------------------------------------- varint ----
def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        out.append(b | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _read_varint(buf: bytes, pos: int):
    shift = 0
    val = 0
    while True:
        c = buf[pos]
        pos += 1
        val |= (c & 0x7F) << shift
        if not (c & 0x80):
            return val, pos
        shift += 7


# ----------------------------------------------------------- generic msg ----
def parse_fields(buf: bytes):
    """[(field_number, wire_type, value)] in wire order."""
    fields = []
    pos = 0
    n = len(buf)
    while pos < n:
        key, pos = _read_varint(buf, pos)
        fnum, wt = key >> 3, key & 7
        if wt == 0:
            val, pos = _read_varint(buf, pos)
        elif wt == 1:
            val = buf[pos:pos + 8]
            pos += 8
        elif wt == 2:
            ln, pos = _read_varint(buf, pos)
            val = buf[pos:pos + ln]
            pos += ln
        elif wt == 5:
            val = buf[pos:pos + 4]
            pos += 4
        else:
            raise ValueError('unsupported wire type %d' % wt)
        fields.append((fnum, wt, val))
    return fields


def encode_field(fnum: int, wt: int, val) -> bytes:
    key = _varint((fnum << 3) | wt)
    if wt == 0:
        return key + _varint(int(val))
    if wt == 2:
        return key + _varint(len(val)) + val
    if wt in (1, 5):
        return key + val
    raise ValueError('unsupported wire type %d' % wt)


def encode_fields(fields) -> bytes:
    return b''.join(encode_field(f, w, v) for f, w, v in fields)


def _find(fields, fnum):
    for i, (f, w, v) in enumerate(fields):
        if f == fnum:
            return i, w, v
    return None


def _text(fields, fnum):
    hit = _find(fields, fnum)
    if not hit:
        return None
    try:
        return hit[2].decode('utf-8')
    except UnicodeDecodeError:
        return None


class WorkspaceRecord:
    """Mutable view over one `edge_workspace-dt-<id>` value."""

    def __init__(self, raw: bytes, key: str = '', details_field: int = WORKSPACE_DETAILS,
                 emoji_field: int = EMOJI_FIELD, name_field: int = 1, color_field: int = 2):
        self.raw = raw
        self.key = key
        self.details_field = details_field
        self.emoji_field = emoji_field
        self.name_field = name_field
        self.color_field = color_field
        self.outer = parse_fields(raw)
        hit = _find(self.outer, 2)
        if hit is None:
            raise ValueError('record has no specifics field')
        self.spec = parse_fields(hit[2])
        if _find(self.spec, details_field) is None:
            raise ValueError('not a workspace record (no details field %d)' % details_field)
        self.details = parse_fields(_find(self.spec, details_field)[2])

    # -- readers ------------------------------------------------------------
    @property
    def workspace_id(self):
        return _text(self.spec, 1) or ''

    @property
    def name(self):
        return _text(self.details, self.name_field) or ''

    @property
    def color(self):
        hit = _find(self.details, self.color_field)
        return hit[2] if hit and hit[1] == 0 else None

    @property
    def last_used_us(self):
        hit = _find(self.details, 3)
        return hit[2] if hit and hit[1] == 0 else None

    @property
    def emoji(self):
        return _text(self.details, self.emoji_field)

    @property
    def has_emoji_field(self):
        return _find(self.details, self.emoji_field) is not None

    @property
    def is_shared(self):
        hit = _find(self.details, 6)
        return bool(hit and hit[1] == 0 and hit[2])

    @property
    def share_doc_id(self):
        hit = _find(self.details, 5)
        if not hit or hit[1] != 2:
            return None
        inner = _find(parse_fields(hit[2]), 4)
        if not inner:
            return None
        try:
            return inner[2].decode('utf-8')
        except UnicodeDecodeError:
            return None

    def summary(self):
        bits = []
        for f, w, v in self.details:
            if w == 0:
                bits.append('%d=%d' % (f, v))
            else:
                try:
                    t = v.decode('utf-8')
                except UnicodeDecodeError:
                    t = None
                if t is not None and t.isprintable() and len(t) < 46:
                    bits.append('%d=%r' % (f, t))
                else:
                    bits.append('%d=<%dB>' % (f, len(v)))
        return ' '.join(bits)

    # -- writer -------------------------------------------------------------
    def set_emoji(self, value):
        """value=None removes the field, a str writes it."""
        idx = _find(self.details, self.emoji_field)
        if idx is None:
            if value is not None:
                self.details.append((self.emoji_field, 2, value.encode('utf-8')))
        else:
            if value is None:
                del self.details[idx[0]]
            else:
                self.details[idx[0]] = (self.emoji_field, 2, value.encode('utf-8'))
        return self.rebuild()

    def rebuild(self) -> bytes:
        details = encode_fields(self.details)
        spec = [(f, w, details if f == self.details_field else v) for f, w, v in self.spec]
        outer = [(f, w, encode_fields(spec) if f == 2 else v) for f, w, v in self.outer]
        self.raw = encode_fields(outer)
        return self.raw


def looks_like_workspace(raw: bytes) -> bool:
    try:
        WorkspaceRecord(raw)
        return True
    except Exception:
        return False
