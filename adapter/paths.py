"""Locating the Edge installation, profiles and the workspace data store."""

from __future__ import annotations

import glob
import json
import os
import subprocess

EDGE_EXE_CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]


def user_data_dir() -> str:
    return os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data')


def edge_exe() -> str:
    for path in EDGE_EXE_CANDIDATES:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError('msedge.exe not found in the standard locations')


def edge_version() -> str:
    path = edge_exe()
    versions = []
    app_dir = os.path.dirname(path)
    for name in os.listdir(app_dir):
        full = os.path.join(app_dir, name)
        if os.path.isdir(full) and name[:1].isdigit():
            versions.append(name)
    versions.sort(key=lambda v: [int(x) for x in v.split('.')])
    if versions:
        return versions[-1]
    return ''


def profiles():
    """[(dir_name, display_name, path)] from Local State."""
    ls = os.path.join(user_data_dir(), 'Local State')
    out = []
    try:
        with open(ls, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return out
    info = (data.get('profile') or {}).get('info_cache') or {}
    for name, meta in info.items():
        path = meta.get('path') or name
        out.append((name, meta.get('name') or name, os.path.join(user_data_dir(), path)))
    return out


def last_used_profile() -> str:
    ls = os.path.join(user_data_dir(), 'Local State')
    try:
        with open(ls, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return (data.get('profile') or {}).get('last_used') or 'Default'
    except (OSError, ValueError):
        return 'Default'


def sync_leveldb(profile_dir: str) -> str:
    return os.path.join(profile_dir, 'Sync Data', 'LevelDB')


def jumplist_icon_dir(profile_dir: str) -> str:
    return os.path.join(profile_dir, 'JumpListIconsRecentWorkspacesV2')


def edge_running() -> bool:
    """True when any msedge.exe process is alive (the DB must be closed)."""
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq msedge.exe', '/NH'],
                             capture_output=True, text=True, timeout=20)
        return 'msedge.exe' in out.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return True  # be conservative


def edge_version_from_registry() -> str:
    try:
        import winreg
        for hive, key in (
            (winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Edge\BLBeacon'),
        ):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    return winreg.QueryValueEx(handle, 'version')[0]
            except OSError:
                continue
    except ImportError:
        pass
    return ''


def sync_enabled(profile_dir: str) -> bool:
    try:
        with open(os.path.join(profile_dir, 'Preferences'), 'r', encoding='utf-8') as f:
            prefs = json.load(f)
    except (OSError, ValueError):
        return False
    sync = prefs.get('sync') or {}
    return bool(sync.get('has_been_enabled')) and bool(sync.get('edge_workspaces'))


def store_files(profile_dir: str):
    ldb = sync_leveldb(profile_dir)
    return sorted(glob.glob(os.path.join(ldb, '*')))
