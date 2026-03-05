#!/usr/bin/env python3
import argparse
import glob
import shutil
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / '.openclaw' / 'openclaw.json'
BACKUP_GLOB = str(Path.home() / '.openclaw' / 'openclaw.json.backup-*')


def latest_backup():
    matches = sorted(glob.glob(BACKUP_GLOB))
    return Path(matches[-1]) if matches else None


def main():
    p = argparse.ArgumentParser(description='Restore openclaw.json from a timestamped backup')
    p.add_argument('--backup', help='Specific backup file to restore')
    p.add_argument('--latest', action='store_true', help='Restore latest backup')
    p.add_argument('--dry-run', action='store_true', help='Show what would be restored without changing files')
    p.add_argument('--yes', action='store_true', help='Confirm live restore')
    args = p.parse_args()

    backup = Path(args.backup).expanduser() if args.backup else (latest_backup() if args.latest or not args.backup else None)
    if not backup or not backup.exists():
        print(f'Backup not found: {backup}', file=sys.stderr)
        return 1

    if args.dry_run:
        print(f'DRY RUN: would restore {CONFIG_PATH} from {backup}')
        return 0

    if not args.yes:
        print('Refusing live restore without --yes', file=sys.stderr)
        return 2

    shutil.copy2(backup, CONFIG_PATH)
    print(f'Restored {CONFIG_PATH} from {backup}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
