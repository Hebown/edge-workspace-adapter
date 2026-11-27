"""Timestamped, self-describing backups of the workspace data store."""

from __future__ import annotations

import json
import os
import shutil
import time

PREFIX = 'backup-'
MANIFEST = 'manifest.json'


def _stamp() -> str:
    return time.strftime('%Y%m%d-%H%M%S')


def create(backup_root: str, profile_dir: str, note: str = '') -> str:
    """Copy the whole sync LevelDB directory plus the prefs that describe it."""
    ldb = os.path.join(profile_dir, 'Sync Data', 'LevelDB')
    if not os.path.isdir(ldb):
        raise FileNotFoundError(ldb)
    target = os.path.join(backup_root, PREFIX + _stamp())
    suffix = 1
    while os.path.exists(target):
        suffix += 1
        target = os.path.join(backup_root, PREFIX + _stamp() + '-%d' % suffix)
    os.makedirs(target)
    store_copy = os.path.join(target, 'LevelDB')
    shutil.copytree(ldb, store_copy)

    # the plain-text files that decide whether sync is on for workspaces
    for name in ('Preferences', 'Secure Preferences'):
        src = os.path.join(profile_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(target, name))

    manifest = {
        'created': time.strftime('%Y-%m-%d %H:%M:%S'),
        'profile_dir': profile_dir,
        'note': note,
        'files': sorted(os.listdir(store_copy)),
    }
    with open(os.path.join(target, MANIFEST), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return target


def list_backups(backup_root: str):
    out = []
    if not os.path.isdir(backup_root):
        return out
    for name in sorted(os.listdir(backup_root)):
        if not name.startswith(PREFIX):
            continue
        path = os.path.join(backup_root, name)
        meta = {}
        try:
            with open(os.path.join(path, MANIFEST), 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except (OSError, ValueError):
            pass
        out.append((name, path, meta))
    return out


def restore(backup_path: str, profile_dir: str) -> str:
    """Put the store back exactly as it was. Returns the directory restored from."""
    src = os.path.join(backup_path, 'LevelDB')
    if not os.path.isdir(src):
        raise FileNotFoundError('backup has no LevelDB/ directory: %s' % backup_path)
    dst = os.path.join(profile_dir, 'Sync Data', 'LevelDB')
    # remove files that did not exist when the backup was taken (e.g. our log)
    keep = set(os.listdir(src))
    for name in os.listdir(dst):
        if name not in keep:
            full = os.path.join(dst, name)
            if os.path.isfile(full):
                os.remove(full)
    for name in keep:
        shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
    prefs = os.path.join(backup_path, 'Preferences')
    if os.path.isfile(prefs):
        shutil.copy2(prefs, os.path.join(profile_dir, 'Preferences'))
    return backup_path
