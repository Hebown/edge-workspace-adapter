"""Post-change verification: did the icon really fall back, and only for one workspace?"""

from __future__ import annotations

import json
import os
import time

from . import paths, scanner


def snapshot_state(profile_dir: str):
    """Everything we compare before/after an experiment."""
    rows = scanner.workspaces(profile_dir)
    state = {}
    for record, _meta in rows:
        state[record.workspace_id] = {
            'name': record.name,
            'emoji': record.emoji,
            'has_field': record.has_emoji_field,
            'color': record.color,
        }
    icons = scanner.jumplist_icons(profile_dir)
    return {
        'at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'workspaces': state,
        'jumplist': [
            {'name': i['name'], 'emoji': i['emoji'], 'workspace': i['workspace'],
             'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(i['mtime']))}
            for i in icons
        ],
    }


def save(state, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def diff(before, after):
    """Human readable difference between two snapshots."""
    lines = []
    b, a = before['workspaces'], after['workspaces']
    for wid in sorted(set(b) | set(a)):
        if wid not in b:
            lines.append('+ workspace added   : %s (%s)' % (a[wid]['name'], wid))
        elif wid not in a:
            lines.append('- workspace removed : %s (%s)' % (b[wid]['name'], wid))
        else:
            if b[wid]['emoji'] != a[wid]['emoji']:
                lines.append('~ %s: emoji %r -> %r' % (b[wid]['name'], b[wid]['emoji'], a[wid]['emoji']))
            elif b[wid]['name'] != a[wid]['name']:
                lines.append('~ %s: name %r -> %r' % (wid, b[wid]['name'], a[wid]['name']))
    bj = {i['name'] for i in before['jumplist']}
    aj = {i['name'] for i in after['jumplist']}
    for name in sorted(aj - bj):
        lines.append('+ jumplist icon     : %s' % name)
    for name in sorted(bj - aj):
        lines.append('- jumplist icon     : %s' % name)
    if not lines:
        lines.append('(no difference)')
    return lines


def check(profile_dir: str, name: str):
    """Verify one workspace after a change; returns [(ok, message)]."""
    results = []
    matches = scanner.find(profile_dir, name)
    if not matches:
        return [(False, 'workspace %r not found any more' % name)]
    record, meta = matches[0]
    results.append((not record.has_emoji_field,
                    'icon field (details.9) removed' if not record.has_emoji_field
                    else 'icon field still present: %r' % record.emoji))

    icons = [i for i in scanner.jumplist_icons(profile_dir)
             if record.workspace_id and i['workspace'] == record.workspace_id]
    with_emoji = [i for i in icons if i['emoji']]
    if with_emoji and not record.has_emoji_field:
        results.append((True,
                        'jump-list icon: an emoji variant is still cached (stale bitmap; '
                        'Edge regenerates it when the workspace is opened)'))
    elif with_emoji:
        results.append((True, 'jump-list icon: emoji variant matches the record'))
    else:
        results.append((True, 'jump-list icon: no emoji variant cached'))

    results.append((paths.sync_enabled(profile_dir),
                    'workspace sync is %s (a server-side update can re-add the emoji)'
                    % ('enabled' if paths.sync_enabled(profile_dir) else 'disabled')))
    return results
