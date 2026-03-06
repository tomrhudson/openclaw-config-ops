#!/usr/bin/env python3
import argparse
import glob
import json
import shutil
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / '.openclaw' / 'openclaw.json'
BACKUP_GLOB = str(Path.home() / '.openclaw' / 'openclaw.json.backup-*')


def list_backups():
    return [Path(p) for p in sorted(glob.glob(BACKUP_GLOB))]


def latest_backup():
    matches = list_backups()
    return matches[-1] if matches else None


def emit(data, json_only=False):
    if json_only:
        print(json.dumps(data, indent=2))
    else:
        if data.get('ok') and 'backups' in data:
            print('Available backups:')
            for b in data['backups']:
                mark = ' (latest)' if b == data.get('latest') else ''
                print(f'- {b}{mark}')
        elif data.get('ok'):
            print(data.get('message', 'OK'))
        else:
            print(data.get('error', 'Unknown error'), file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description='Restore openclaw.json from a timestamped backup')
    p.add_argument('--backup', help='Specific backup file to restore')
    p.add_argument('--latest', action='store_true', help='Restore latest backup')
    p.add_argument('--list', action='store_true', help='List available backups')
    p.add_argument('--json', action='store_true', help='Emit JSON output')
    p.add_argument('--dry-run', action='store_true', help='Show what would be restored without changing files')
    p.add_argument('--yes', action='store_true', help='Confirm live restore')
    args = p.parse_args()

    if args.list:
        backups = [str(p) for p in list_backups()]
        latest = str(backups[-1]) if backups else None
        payload = {'ok': True, 'backups': backups, 'latest': latest}
        emit(payload, args.json)
        return 0

    backup = Path(args.backup).expanduser() if args.backup else (latest_backup() if args.latest or not args.backup else None)
    if not backup or not backup.exists():
        payload = {'ok': False, 'error': f'Backup not found: {backup}'}
        emit(payload, args.json)
        return 1

    if args.dry_run:
        payload = {
            'ok': True,
            'backup': str(backup),
            'target': str(CONFIG_PATH),
            'message': f'DRY RUN: would restore {CONFIG_PATH} from {backup}'
        }
        emit(payload, args.json)
        return 0

    if not args.yes:
        payload = {'ok': False, 'error': 'Refusing live restore without --yes'}
        emit(payload, args.json)
        return 2

    shutil.copy2(backup, CONFIG_PATH)
    payload = {
        'ok': True,
        'backup': str(backup),
        'target': str(CONFIG_PATH),
        'message': f'Restored {CONFIG_PATH} from {backup}'
    }
    emit(payload, args.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
