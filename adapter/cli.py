"""Edge Workspace Icon Adapter - command line entry point.

    python adapter.py scan
    python adapter.py preview --workspace "<workspace name>" --icon default
    python adapter.py apply   --workspace "<workspace name>" --icon default
    python adapter.py verify  --workspace "<workspace name>"
    python adapter.py restore --backup "<backup directory>"
"""

from __future__ import annotations

import argparse
import os
import sys

if __package__ in (None, ''):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from adapter import backup, modifier, paths, scanner, verifier  # type: ignore
else:
    from . import backup, modifier, paths, scanner, verifier

BACKUP_ROOT = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
                           'edge-workspace-adapter', 'backups')


def _argb(value):
    if value is None:
        return 'unset'
    return '0x%08X' % (value & 0xFFFFFFFF)


def cmd_scan(args):
    profile = args.profile_dir
    print('Edge version : %s' % (paths.edge_version() or '?'))
    print('executable   : %s' % paths.edge_exe())
    print('User Data    : %s' % paths.user_data_dir())
    print('profile      : %s' % profile)
    print('profiles     : %s' % ', '.join('%s(%s)' % (n, d) for n, d, _p in paths.profiles()))
    print('sync enabled : %s (workspaces synced: %s)'
          % ('yes' if paths.sync_enabled(profile) else 'no',
             'yes' if paths.sync_enabled(profile) else 'no'))
    print('Edge running : %s' % ('yes' if paths.edge_running() else 'no'))
    detected = scanner.detect_layout(profile)
    print('layout       : %s (%s)' % (detected.get('id') or 'UNKNOWN', detected['status']))
    if detected['reasons']:
        print('               %s' % '; '.join(detected['reasons']))
    ldb = os.path.join(profile, 'Sync Data', 'LevelDB')
    print('data source  : %s' % ldb)
    print('  role       : authoritative local copy of the synced workspace model')
    print('  cache?     : no - it is a leveldb store, not a rendered cache')
    icons_dir = os.path.join(profile, 'JumpListIconsRecentWorkspacesV2')
    print('icon cache   : %s%s' % (icons_dir, '' if os.path.isdir(icons_dir) else ' (absent)'))
    print()

    rows = scanner.workspaces(profile)
    if not rows:
        print('no workspace records found')
        return 0
    print('%-34s %-24s %-10s %-12s %s' % ('id', 'name', 'icon', 'colour', 'sync ver'))
    for record, meta in rows:
        icon = record.emoji if record.emoji else 'DEFAULT'
        state = '' if record.has_emoji_field else ' (field absent)'
        print('%-34s %-24s %-10s %-12s %s'
              % (record.workspace_id, record.name[:22], icon, _argb(record.color),
                 meta.get('sync_version') or '-'))
        if args.verbose:
            print('    details: %s%s' % (record.summary(), state))
    print('\n%d workspace(s); %d with an emoji icon.'
          % (len(rows), sum(1 for r, _m in rows if r.has_emoji_field)))
    return 0


def cmd_preview(args):
    try:
        plan = modifier.build(args.profile_dir, args.workspace, args.icon,
                              allow_unknown=args.allow_unknown)
    except (LookupError, RuntimeError) as exc:
        print('ERROR: %s' % exc, file=sys.stderr)
        return 2
    print(plan.render())
    print('\nno file was written')
    return 0


def cmd_apply(args):
    try:
        plan = modifier.build(args.profile_dir, args.workspace, args.icon,
                              allow_unknown=args.allow_unknown)
    except (LookupError, RuntimeError) as exc:
        print('ERROR: %s' % exc, file=sys.stderr)
        return 2
    if not plan.changed:
        print('nothing to do: %s already has the requested icon' % plan.record.name)
        return 0
    print(plan.render())
    print()
    try:
        backup_path, log_path = modifier.apply(args.profile_dir, plan, args.backup_dir, force=args.force)
    except RuntimeError as exc:
        print('ERROR: %s' % exc, file=sys.stderr)
        return 2
    print('backup       : %s' % backup_path)
    print('new log file : %s' % log_path)
    print('written value verified by re-reading the store')
    return 0


def cmd_restore(args):
    if args.backup:
        target = args.backup
    else:
        items = backup.list_backups(args.backup_dir)
        if not items:
            print('no backups in %s' % args.backup_dir)
            return 1
        target = items[-1][1]
        print('restoring newest backup: %s' % target)
    if paths.edge_running():
        print('ERROR: close Edge before restoring', file=sys.stderr)
        return 2
    backup.restore(target, args.profile_dir)
    print('restored %s' % target)
    print('verifying ...')
    rows = scanner.workspaces(args.profile_dir)
    print('workspaces visible again: %d' % len(rows))
    return 0


def cmd_verify(args):
    ok_all = True
    for ok, message in verifier.check(args.profile_dir, args.workspace):
        print('%s %s' % ('PASS' if ok else 'FAIL', message))
        ok_all = ok_all and ok
    print('\nresult: %s' % ('changed as requested' if ok_all else 'still needs attention'))
    return 0 if ok_all else 1


def cmd_snapshot(args):
    state = verifier.snapshot_state(args.profile_dir)
    if args.out:
        verifier.save(state, args.out)
        print('snapshot written to %s' % args.out)
    else:
        print(verifier.diff(state, state)[0])
        print('%d workspaces, %d cached icons' % (len(state['workspaces']), len(state['jumplist'])))
    return 0


def cmd_backups(args):
    items = backup.list_backups(args.backup_dir)
    if not items:
        print('no backups')
        return 0
    for name, path, meta in items:
        print('%s  %s  %s' % (name, meta.get('created', '?'), meta.get('note', '')))
    return 0


def cmd_diff(args):
    lines = verifier.diff(verifier.load(args.before), verifier.load(args.after))
    print('\n'.join(lines))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='adapter.py', description='Edge Workspace Icon Adapter')
    parser.add_argument('--profile-dir', default=None,
                        help='profile directory (default: the last used Edge profile)')
    parser.add_argument('--backup-dir', default=BACKUP_ROOT)
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('scan', help='list workspaces and their icon configuration')
    p.add_argument('-v', '--verbose', action='store_true')
    p.set_defaults(func=cmd_scan)

    for name, func, text in (('preview', cmd_preview, 'show the change without writing'),
                             ('apply', cmd_apply, 'write the change')):
        p = sub.add_parser(name, help=text)
        p.add_argument('--workspace', required=True)
        p.add_argument('--icon', default='default',
                       help='"default" (bundled glyph) or an emoji such as 📁')
        p.add_argument('--allow-unknown', action='store_true',
                       help='allow writing when the Edge layout was not recognised (diagnostic only)')
        if name == 'apply':
            p.add_argument('--force', action='store_true',
                           help='skip the "Edge must be closed" check (profile copies only)')
        p.set_defaults(func=func)

    p = sub.add_parser('verify', help='check the result for one workspace')
    p.add_argument('--workspace', required=True)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser('restore', help='restore a backup')
    p.add_argument('--backup', default=None)
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser('snapshot', help='dump workspace + icon-cache state as json')
    p.add_argument('--out', default=None)
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser('backups', help='list backups')
    p.set_defaults(func=cmd_backups)

    p = sub.add_parser('diff', help='compare two snapshots')
    p.add_argument('--before', required=True)
    p.add_argument('--after', required=True)
    p.set_defaults(func=cmd_diff)

    args = parser.parse_args(argv)
    if not args.profile_dir:
        args.profile_dir = os.path.join(paths.user_data_dir(), paths.last_used_profile())
    args.profile_dir = os.path.abspath(args.profile_dir)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
