"""Pure-python read-only reader for Chromium LevelDB stores (SSTable + write-ahead log).

Why hand-rolled: the store has to be inspected on a machine where no leveldb
binding is installed, and the adapter must never open the live database with a
writer lock.  Reading is done from a *copy* of the directory, so the browser is
never touched while it runs.

Scope: enough of leveldb 1.x to enumerate every (key, value) pair.
  * .ldb / .sst  -> footer -> index block -> data blocks (snappy or raw)
  * .log         -> 32 KiB framed records -> WriteBatch
No bloom filter / no iterator ordering guarantees beyond "latest sequence wins".
"""

from __future__ import annotations

import glob
import os
import struct

BLOCK_SIZE = 32768
TABLE_MAGIC = 0xDB4775248B80FB57


# --------------------------------------------------------------------------- #
# snappy (raw block format)                                                   #
# --------------------------------------------------------------------------- #
def snappy_decompress(data: bytes) -> bytes:
    i = 0
    shifted = 0
    ulen = 0
    while True:
        c = data[i]
        i += 1
        ulen |= (c & 0x7F) << shifted
        if not (c & 0x80):
            break
        shifted += 7
    out = bytearray()
    n = len(data)
    while i < n:
        tag = data[i]
        i += 1
        kind = tag & 3
        if kind == 0:  # literal
            ln = tag >> 2
            if ln < 60:
                ln += 1
            else:
                extra = ln - 59
                ln = int.from_bytes(data[i:i + extra], 'little') + 1
                i += extra
            out += data[i:i + ln]
            i += ln
        else:
            if kind == 1:
                ln = 4 + ((tag >> 2) & 7)
                off = ((tag >> 5) << 8) | data[i]
                i += 1
            elif kind == 2:
                ln = 1 + (tag >> 2)
                off = int.from_bytes(data[i:i + 2], 'little')
                i += 2
            else:
                ln = 1 + (tag >> 2)
                off = int.from_bytes(data[i:i + 4], 'little')
                i += 4
            start = len(out) - off
            for k in range(ln):
                out.append(out[start + k])
    if ulen != len(out):
        raise ValueError('snappy length mismatch %d != %d' % (ulen, len(out)))
    return bytes(out)


# --------------------------------------------------------------------------- #
# varint helpers                                                              #
# --------------------------------------------------------------------------- #
def read_varint(buf: bytes, pos: int):
    shift = 0
    val = 0
    while True:
        c = buf[pos]
        pos += 1
        val |= (c & 0x7F) << shift
        if not (c & 0x80):
            return val, pos
        shift += 7


# --------------------------------------------------------------------------- #
# SSTable                                                                     #
# --------------------------------------------------------------------------- #
def _read_block(data: bytes, offset: int, size: int) -> bytes:
    block = data[offset:offset + size]
    if not block:
        return b''
    # trailer = compression_type(1 byte) + crc32c(4 bytes), so type sits at -5
    ctype = block[-5]
    payload = block[:-5] if len(block) > 5 else block
    if ctype == 0:
        return payload
    if ctype == 1:
        return snappy_decompress(payload)
    if ctype == 2:
        return payload  # zstd not used by Chromium's sync db
    raise ValueError('unknown block compression %d' % ctype)


def _block_payload(data: bytes, offset: int, size: int) -> bytes:
    """Chromium's on-disk BlockHandle.size covers the payload only.

    Empirically ``size`` excludes the 5-byte trailer (type + crc32c), so the
    block is read as size+5 bytes and the type byte is taken from the end.
    Two attempts keep this robust if a build ever writes the length the
    upstream way (trailer included).
    """
    for length in (size + 5, size):
        raw = data[offset:offset + length]
        if len(raw) != length:
            continue
        ctype = raw[-5]
        if ctype not in (0, 1, 2):
            continue
        try:
            return _read_block(data, offset, length)
        except Exception:
            continue
    return b''


def _parse_block(block: bytes):
    if len(block) < 4:
        return
    n_restarts = struct.unpack('<I', block[-4:])[0]
    end = len(block) - 4 - 4 * n_restarts
    pos = 0
    key = b''
    while pos < end:
        shared, pos = read_varint(block, pos)
        non_shared, pos = read_varint(block, pos)
        vlen, pos = read_varint(block, pos)
        key = key[:shared] + block[pos:pos + non_shared]
        pos += non_shared
        val = block[pos:pos + vlen]
        pos += vlen
        yield key, val


def read_sstable(path: str):
    """Yield (sequence, deleted, user_key, value).

    Data blocks hold *internal* keys: user_key + 8-byte trailer where the
    trailer is (sequence << 8 | value_type) little endian.  value_type 1 means
    PUT, 0 means DELETE.
    """
    data = open(path, 'rb').read()
    if len(data) < 48:
        return
    footer = data[-48:]
    magic = struct.unpack('<Q', footer[-8:])[0]
    if magic != TABLE_MAGIC:
        raise ValueError('bad table magic in %s' % path)
    pos = 0
    _, pos = read_varint(footer, pos)          # metaindex offset
    _, pos = read_varint(footer, pos)          # metaindex size
    idx_off, pos = read_varint(footer, pos)
    idx_size, pos = read_varint(footer, pos)
    index = _block_payload(data, idx_off, idx_size)
    for _, handle in _parse_block(index):
        hpos = 0
        off, hpos = read_varint(handle, hpos)
        size, hpos = read_varint(handle, hpos)
        for k, v in _parse_block(_block_payload(data, off, size)):
            if len(k) < 9:
                continue
            user_key, trailer = k[:-8], k[-8:]
            tag = int.from_bytes(trailer, 'little')
            seq, vtype = tag >> 8, tag & 0xFF
            yield seq, vtype == 0, user_key, v


# --------------------------------------------------------------------------- #
# write-ahead log                                                             #
# --------------------------------------------------------------------------- #
def _log_records(data: bytes):
    pos = 0
    cur = bytearray()
    n = len(data)
    while pos + 7 <= n:
        block_off = pos % BLOCK_SIZE
        if BLOCK_SIZE - block_off < 7:
            pos += BLOCK_SIZE - block_off
            continue
        _, length, rtype = struct.unpack('<IHB', data[pos:pos + 7])
        pos += 7
        if length == 0 and rtype == 0:
            pos = (pos // BLOCK_SIZE + 1) * BLOCK_SIZE
            continue
        payload = data[pos:pos + length]
        if len(payload) < length:
            break
        pos += length
        if rtype == 1:
            yield bytes(payload)
            cur = bytearray()
        elif rtype == 2:
            cur = bytearray(payload)
        elif rtype == 3:
            cur += payload
        elif rtype == 4:
            cur += payload
            yield bytes(cur)
            cur = bytearray()


def _log_batch(rec: bytes):
    """Yield (sequence, deleted, key, value)."""
    if len(rec) < 12:
        return
    seq, count = struct.unpack('<QI', rec[:12])
    pos = 12
    for _ in range(count):
        tag = rec[pos]
        pos += 1
        klen, pos = read_varint(rec, pos)
        key = rec[pos:pos + klen]
        pos += klen
        val = b''
        if tag == 1:
            vlen, pos = read_varint(rec, pos)
            val = rec[pos:pos + vlen]
            pos += vlen
        yield seq, tag == 0, key, val
        seq += 1


# --------------------------------------------------------------------------- #
# store                                                                       #
# --------------------------------------------------------------------------- #
class Store:
    """Snapshot of a leveldb directory: key -> (sequence, deleted, value)."""

    def __init__(self):
        self.kv = {}
        self.max_seq = 0

    def put(self, seq, deleted, key, value):
        old = self.kv.get(key)
        if old is None or seq >= old[0]:
            self.kv[key] = (seq, deleted, value)
        if seq > self.max_seq:
            self.max_seq = seq

    def items(self):
        for k, (seq, deleted, v) in self.kv.items():
            if not deleted:
                yield k, v

    def get(self, key):
        rec = self.kv.get(key)
        if not rec or rec[1]:
            return None
        return rec[2]


def open_store(dirpath: str) -> Store:
    store = Store()
    for path in sorted(glob.glob(os.path.join(dirpath, '*.ldb'))) + \
            sorted(glob.glob(os.path.join(dirpath, '*.sst'))):
        try:
            for seq, deleted, key, val in read_sstable(path):
                store.put(seq, deleted, key, val)
        except Exception as exc:  # pragma: no cover - diagnostics only
            print('  ! %s: %s' % (os.path.basename(path), exc))
    for path in sorted(glob.glob(os.path.join(dirpath, '*.log')),
                       key=lambda p: int(''.join(filter(str.isdigit, os.path.basename(p))) or 0)):
        data = open(path, 'rb').read()
        for rec in _log_records(data):
            for seq, deleted, key, val in _log_batch(rec):
                store.put(seq, deleted, key, val)
    return store


if __name__ == '__main__':
    import sys
    st = open_store(sys.argv[1])
    print('entries:', len(st.kv), 'max_seq:', st.max_seq)
    for k, v in st.items():
        print(k[:80], len(v))
