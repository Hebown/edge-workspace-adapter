"""Turn "icon = default" into a concrete byte-level change and apply it."""

from __future__ import annotations

import os
import shutil
import tempfile

from . import backup, leveldb_reader, leveldb_writer, paths, workspace_proto

DT_PREFIX = b'edge_workspace-dt-'


class Plan:
    def __init__(self, record, meta, new_value, target_icon, spec_kwargs=None):
        self.record = record
        self.meta = meta
        self.old_value = record.raw
        self.new_value = new_value
        self.target_icon = target_icon
        self.spec_kwargs = spec_kwargs or {}

    @property
    def changed(self):
        return self.old_value != self.new_value

    def render(self):
        rec = workspace_proto.WorkspaceRecord(self.old_value, **self.spec_kwargs)
        old_emoji = rec.emoji
        field = rec.emoji_field
        rec.set_emoji(None if self.target_icon == 'default' else self.target_icon)
        lines = []
        lines.append('workspace : %s' % rec.name)
        lines.append('id        : %s' % rec.workspace_id)
        lines.append('source    : %s' % self.meta['key'])
        lines.append('current   : %s' % (('<emoji %s>' % old_emoji) if old_emoji else '<default glyph>'))
        lines.append('target    : %s' % ('<default glyph>' if self.target_icon == 'default' else self.target_icon))
        lines.append('field     : details.%d (string, emoji)  ->  %s'
                     % (field, 'removed' if self.target_icon == 'default' else 'written'))
        lines.append('bytes     : %d -> %d' % (len(self.old_value), len(self.new_value)))
        lines.append('')
        lines.append('before: %s' % self.old_value.hex())
        lines.append('after : %s' % self.new_value.hex())
        lines.append('')
        lines.append('details before: %s' % workspace_proto.WorkspaceRecord(
            self.old_value, **self.spec_kwargs).summary())
        after = workspace_proto.WorkspaceRecord(self.new_value, **self.spec_kwargs)
        lines.append('details after : %s' % after.summary())
        return '\n'.join(lines)


def build(profile_dir: str, needle: str, icon: str, allow_unknown: bool = False) -> Plan:
    from . import layout, scanner

    detected = scanner.detect_layout(profile_dir)
    layout.require_writable(detected, allow_unknown)
    spec = detected.get('spec') or layout.DEFAULT_LAYOUT
    kwargs = scanner._spec_kwargs(spec)
    matches = scanner.find(profile_dir, needle, spec=spec)
    if not matches:
        raise LookupError('no workspace matches %r' % needle)
    if len(matches) > 1:
        names = ', '.join(r.name for r, _ in matches)
        raise LookupError('ambiguous match %r: %s' % (needle, names))
    record, meta = matches[0]
    target = 'default' if icon.lower() in ('default', 'none', '') else icon
    clone = workspace_proto.WorkspaceRecord(record.raw, **kwargs)
    new_value = clone.set_emoji(None if target == 'default' else target)
    return Plan(record, meta, new_value, target, kwargs)


def apply(profile_dir: str, plan: Plan, backup_root: str, note: str = '', force: bool = False):
    """Write the change as one extra leveldb log file. Returns (backup_path, log_path)."""
    if not plan.changed:
        return None, None
    if paths.edge_running() and not force:
        raise RuntimeError('Edge is running - close every msedge.exe window first')

    ldb = os.path.join(profile_dir, 'Sync Data', 'LevelDB')
    # read the live sequence counter (not the snapshot) so our batch is newest
    tmp = tempfile.mkdtemp(prefix='ews-seq-')
    try:
        for name in os.listdir(ldb):
            src = os.path.join(ldb, name)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, os.path.join(tmp, name))
                except OSError:
                    pass
        store = leveldb_reader.open_store(tmp)
        sequence = store.max_seq + 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    backup_path = backup.create(backup_root, profile_dir, note or 'before apply')
    key = plan.meta['key'].encode()
    log_path = leveldb_writer.append_batch(ldb, [(key, plan.new_value)], sequence=sequence)

    # verify the value is visible to a fresh reader
    tmp = tempfile.mkdtemp(prefix='ews-verify-')
    try:
        for name in os.listdir(ldb):
            src = os.path.join(ldb, name)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, os.path.join(tmp, name))
                except OSError:
                    pass
        store = leveldb_reader.open_store(tmp)
        value = store.get(key)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if value != plan.new_value:
        raise RuntimeError('write verification failed: stored value differs')
    return backup_path, log_path


def rollback(profile_dir: str, log_path: str):
    """Remove only the log file we added (used when the change must be undone)."""
    if log_path and os.path.isfile(log_path):
        os.remove(log_path)
        return True
    return False
