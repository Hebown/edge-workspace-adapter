"""Append-only writer for the Chromium sync LevelDB.

Strategy: never rewrite an existing .ldb/.log.  Instead we create one *new*
write-ahead-log file whose WriteBatch carries the replacement value with a
sequence number greater than anything currently in the database.

Why this is the least invasive option:
  * leveldb replays every log file whose number is >= manifest.log_number, in
    ascending order, right after opening the database.  A new file therefore
    acts exactly like a normal commit made by the browser itself.
  * no SSTable is rebuilt, no MANIFEST/CURRENT line is rewritten, so a failed
    or unwanted change is undone by deleting the single file we added.
  * leveldb assigns our batch the highest sequence number, so it wins over the
    older value stored in the compacted tables.
"""

from __future__ import annotations

import os
import struct

BLOCK_SIZE = 32768

# --------------------------------------------------------------------------- #
# crc32c (Castagnoli) - leveldb checksums every log record                    #
# --------------------------------------------------------------------------- #
_POLY = 0x82F63B78
_TABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ _POLY if _c & 1 else _c >> 1
    _TABLE.append(_c)


def crc32c(data: bytes, crc: int = 0) -> int:
    crc ^= 0xFFFFFFFF
    for b in data:
        crc = _TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def _mask(crc: int) -> int:
    return (((crc >> 15) | (crc << 17)) + 0xA282EAD8) & 0xFFFFFFFF


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        out.append(b | (0x80 if value else 0))
        if not value:
            return bytes(out)


# --------------------------------------------------------------------------- #
# batch + log framing                                                         #
# --------------------------------------------------------------------------- #
def build_batch(sequence: int, puts, deletes=()) -> bytes:
    """puts: iterable of (key, value); deletes: iterable of key."""
    puts = list(puts)
    deletes = list(deletes)
    out = bytearray()
    out += struct.pack('<Q', sequence)
    out += struct.pack('<I', len(puts) + len(deletes))
    for key, value in puts:
        out += b'\x01' + _varint(len(key)) + key + _varint(len(value)) + value
    for key in deletes:
        out += b'\x00' + _varint(len(key)) + key
    return bytes(out)


def _records(payload: bytes, rtype: int = 1):
    """Split payload into 32 KiB framed log records (type 1=full, 2/3/4 split)."""
    out = bytearray()
    pos = 0
    first = True
    while True:
        block_room = BLOCK_SIZE - (len(out) % BLOCK_SIZE)
        if block_room < 7:                       # pad the tail of the block
            out += b'\x00' * block_room
            continue
        chunk = payload[pos:pos + block_room - 7]
        last = pos + len(chunk) >= len(payload)
        if first and last:
            t = 1
        elif first:
            t = 2
        elif last:
            t = 4
        else:
            t = 3
        crc = _mask(crc32c(bytes([t]) + chunk))
        out += struct.pack('<IHB', crc, len(chunk), t)
        out += chunk
        pos += len(chunk)
        first = False
        if last:
            return bytes(out)


def next_log_number(dirpath: str) -> int:
    nums = []
    for name in os.listdir(dirpath):
        stem = name.split('.')[0]
        if stem.isdigit() and name.split('.')[-1] in ('log', 'ldb', 'sst'):
            nums.append(int(stem))
    return (max(nums) if nums else 0) + 1


def append_batch(dirpath: str, puts, sequence: int, deletes=()) -> str:
    """Write one WriteBatch into a brand-new log file; return its path."""
    payload = build_batch(sequence, puts, deletes)
    data = _records(payload)
    number = next_log_number(dirpath)
    path = os.path.join(dirpath, '%06d.log' % number)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path
