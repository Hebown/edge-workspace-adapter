"""Build a throw-away copy of the Edge profile for experiments.

The copy is opened with all network traffic blocked, so nothing that happens
inside it can reach the sync server (and therefore cannot touch the account).

    python tools/make_test_profile.py <destination>
"""

import os
import shutil
import sys

USER_DATA = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data')

TOP_FILES = ['Local State']
PROFILE_FILES = ['Preferences', 'Secure Preferences', 'Bookmarks', 'Favicons']
PROFILE_DIRS = ['Sync Data', 'JumpListIconsRecentWorkspacesV2', 'Workspaces', 'Network',
                'Local Storage']


def _copy_tree(src: str, dst: str, skipped: list):
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target = os.path.join(dst, rel) if rel != '.' else dst
        os.makedirs(target, exist_ok=True)
        for name in files:
            try:
                shutil.copy2(os.path.join(root, name), os.path.join(target, name))
            except OSError:
                skipped.append(os.path.join(root, name))


def build(dest: str):
    skipped = []
    os.makedirs(dest, exist_ok=True)
    for name in TOP_FILES:
        src = os.path.join(USER_DATA, name)
        if os.path.isfile(src):
            try:
                shutil.copy2(src, os.path.join(dest, name))
            except OSError:
                skipped.append(src)

    src_profile = os.path.join(USER_DATA, 'Default')
    dst_profile = os.path.join(dest, 'Default')
    os.makedirs(dst_profile, exist_ok=True)
    for name in PROFILE_FILES:
        src = os.path.join(src_profile, name)
        if os.path.isfile(src):
            try:
                shutil.copy2(src, os.path.join(dst_profile, name))
            except OSError:
                skipped.append(src)
    for name in PROFILE_DIRS:
        src = os.path.join(src_profile, name)
        if os.path.isdir(src):
            _copy_tree(src, os.path.join(dst_profile, name), skipped)
    return dest, skipped


if __name__ == '__main__':
    dest = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), '_test-profile'))
    if os.path.isdir(dest):
        shutil.rmtree(dest, ignore_errors=True)
    path, skipped = build(dest)
    print(path)
    print('locked files skipped:', len(skipped))
    for s in skipped[:10]:
        print('  ', s)
