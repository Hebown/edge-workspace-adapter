"""Read-only scan of the workspace records.

The live database is never opened: files are copied to a temp directory first,
so scanning works while Edge is running and cannot disturb the store.
"""

from __future__ import annotations

import os
import shutil
import tempfile

from . import leveldb_reader, workspace_proto

DT_PREFIX = 'edge_workspace-dt-'
MD_PREFIX = 'edge_workspace-md-'


def snapshot(profile_dir: str, workdir: str | None = None) -> str:
    src = os.path.join(profile_dir, 'Sync Data', 'LevelDB')
    dst = workdir or tempfile.mkdtemp(prefix='ews-scan-')
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        source = os.path.join(src, name)
        if not os.path.isfile(source):
            continue
        try:
            shutil.copy2(source, os.path.join(dst, name))
        except OSError:
            pass
    return dst


def open_snapshot(profile_dir: str, workdir: str | None = None):
    path = snapshot(profile_dir, workdir)
    return path, leveldb_reader.open_store(path)


def _spec_kwargs(spec):
    if not spec:
        return {}
    return {
        'details_field': spec['details_field'],
        'emoji_field': spec['emoji_field'],
        'name_field': spec['name_field'],
        'color_field': spec['color_field'],
    }


def workspaces(profile_dir: str, spec=None):
    """[(WorkspaceRecord, meta dict)] sorted by last used, newest first."""
    path, store = open_snapshot(profile_dir)
    try:
        rows = []
        kwargs = _spec_kwargs(spec)
        for key, value in store.items():
            if not key.startswith(DT_PREFIX.encode()):
                continue
            try:
                record = workspace_proto.WorkspaceRecord(value, key.decode(), **kwargs)
            except Exception:
                continue
            meta = {
                'key': key.decode(),
                'bytes': len(value),
                'source': path,
                'sequence': store.kv[key][0],
            }
            md = store.get((MD_PREFIX + record.workspace_id).encode())
            if md:
                try:
                    from . import workspace_proto as wp
                    fields = wp.parse_fields(md)
                    meta['sync_version'] = [v for f, w, v in fields if w == 0]
                except Exception:
                    meta['sync_version'] = []
            rows.append((record, meta))
        rows.sort(key=lambda r: (r[0].last_used_us or 0), reverse=True)
        return rows
    finally:
        shutil.rmtree(path, ignore_errors=True)


def find(profile_dir: str, needle: str, spec=None):
    """Match by exact name, then by unique case-insensitive substring."""
    rows = workspaces(profile_dir, spec=spec)
    exact = [r for r in rows if r[0].name == needle]
    if exact:
        return exact
    folded = needle.casefold()
    return [r for r in rows if folded in r[0].name.casefold()]


def detect_layout(profile_dir: str):
    """Combine Edge's version with the structure actually present on disk."""
    from . import layout, paths

    path, store = open_snapshot(profile_dir)
    try:
        samples = [v for k, v in store.items()
                   if k.startswith(DT_PREFIX.encode()) and workspace_proto.looks_like_workspace(v)]
    finally:
        shutil.rmtree(path, ignore_errors=True)
    return layout.detect(paths.edge_version(), samples)


def jumplist_icons(profile_dir: str):
    """Icon files Edge cached for the Windows taskbar jump list."""
    folder = os.path.join(profile_dir, 'JumpListIconsRecentWorkspacesV2')
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        full = os.path.join(folder, name)
        if not os.path.isfile(full):
            continue
        parts = name.split('_')
        out.append({
            'name': name,
            'path': full,
            'color': parts[0],
            'emoji': 'emoji' in parts,
            'workspace': parts[3] if len(parts) > 3 and parts[2] == 'emoji' else None,
            'mtime': os.path.getmtime(full),
        })
    return out
